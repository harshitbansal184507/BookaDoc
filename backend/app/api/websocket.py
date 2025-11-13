from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict
import json
from datetime import datetime

from app.models.conversation import (
    ConversationContext,
    ConversationState,
    AgentType,
    WebSocketMessage
)
from app.agents.orchestrator import OrchestratorAgent, WorkflowState
from app.utils.logger import app_logger as logger

router = APIRouter()

# Store active WebSocket connections
active_connections: Dict[str, WebSocket] = {}

# Store conversation contexts (shared with routes.py)
from app.api.routes import conversations


class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.orchestrator = OrchestratorAgent()
    
    async def connect(self, conversation_id: str, websocket: WebSocket):
        """Accept and store a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[conversation_id] = websocket
        logger.info(f"WebSocket connected: {conversation_id}")
    
    def disconnect(self, conversation_id: str):
        """Remove a WebSocket connection."""
        if conversation_id in self.active_connections:
            del self.active_connections[conversation_id]
            logger.info(f"WebSocket disconnected: {conversation_id}")
    
    async def send_message(self, conversation_id: str, message: dict):
        """Send message to a specific connection."""
        if conversation_id in self.active_connections:
            websocket = self.active_connections[conversation_id]
            await websocket.send_json(message)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connections."""
        for connection in self.active_connections.values():
            await connection.send_json(message)


manager = ConnectionManager()


@router.websocket("/ws/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str):
    """
    WebSocket endpoint for real-time conversation.
    
    Args:
        websocket: WebSocket connection
        conversation_id: Conversation ID
    """
    await manager.connect(conversation_id, websocket)
    
    # Get or create conversation context
    if conversation_id not in conversations:
        context = ConversationContext(conversation_id=conversation_id)
        conversations[conversation_id] = context
    else:
        context = conversations[conversation_id]
    
    # Send welcome message with initial greeting
    try:
        initial_greeting = await manager.orchestrator.start_conversation()
        
        await manager.send_message(conversation_id, {
            "type": "connected",
            "conversation_id": conversation_id,
            "message": "Connected to BookaDoc appointment assistant",
            "timestamp": datetime.now().isoformat()
        })
        
        # Send initial greeting from receptionist
        await manager.send_message(conversation_id, {
            "type": "agent_message",
            "content": initial_greeting,
            "agent_type": "receptionist",
            "timestamp": datetime.now().isoformat()
        })
        
        # Add to conversation history
        context.add_message("assistant", initial_greeting, AgentType.RECEPTIONIST)
        
    except Exception as e:
        logger.error(f"Error sending initial greeting: {e}")
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
                await handle_message(conversation_id, message_data, context)
            except json.JSONDecodeError:
                await manager.send_message(conversation_id, {
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.now().isoformat()
                })
            
    except WebSocketDisconnect:
        manager.disconnect(conversation_id)
        logger.info(f"Client disconnected: {conversation_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(conversation_id)


async def handle_message(
    conversation_id: str,
    message_data: dict,
    context: ConversationContext
):
    """
    Handle incoming WebSocket message using orchestrator.
    
    Args:
        conversation_id: Conversation ID
        message_data: Message data from client
        context: Conversation context
    """
    message_type = message_data.get("type")
    content = message_data.get("content", "")
    
    logger.info(f"Received message type '{message_type}': {content[:50]}...")
    
    if message_type == "user_message":
        # Add user message to context
        context.add_message("user", content)
        
        # Send typing indicator
        await manager.send_message(conversation_id, {
            "type": "typing",
            "timestamp": datetime.now().isoformat()
        })
        
        # Prepare conversation context for orchestrator
        conversation_context = {
            "messages": context.get_conversation_history(),
            "patient_info": {
                "patient_name": context.patient_name,
                "patient_phone": context.patient_phone,
                "patient_email": context.patient_email,
                "reason": context.reason,
                "preferred_date": context.preferred_date,
                "preferred_time": context.preferred_time,
                "doctor_preference": context.doctor_preference
            },
            "available_slots": context.proposed_slots,
            "selected_slot": None,  # Will be set during workflow
            "workflow_state": _map_conversation_state_to_workflow(context.state),
            "current_agent": context.current_agent,
            "has_required_info": context.has_required_info(),
            "awaiting_confirmation": context.state == ConversationState.CONFIRMING
        }
        
        # Process through orchestrator
        try:
            result = await manager.orchestrator.process_message(
                user_message=content,
                conversation_context=conversation_context
            )
            
            # Update context with results
            _update_context_from_result(context, result)
            
            # Send agent response
            await manager.send_message(conversation_id, {
                "type": "agent_message",
                "content": result.get("agent_response", ""),
                "agent_type": result.get("current_agent", "receptionist"),
                "timestamp": datetime.now().isoformat()
            })
            
            # Add agent message to context
            context.add_message(
                "assistant",
                result.get("agent_response", ""),
                result.get("current_agent", AgentType.RECEPTIONIST)
            )
            
            # Send status update
            await manager.send_message(conversation_id, {
                "type": "status_update",
                "state": _map_workflow_to_conversation_state(result.get("workflow_state")),
                "workflow_state": result.get("workflow_state"),
                "timestamp": datetime.now().isoformat()
            })
            
            # If slots are available, send them separately
            if result.get("available_slots"):
                await manager.send_message(conversation_id, {
                    "type": "slots_available",
                    "slots": result.get("available_slots", []),
                    "timestamp": datetime.now().isoformat()
                })
            
            # If appointment is completed
            if result.get("workflow_state") == WorkflowState.COMPLETED:
                await manager.send_message(conversation_id, {
                    "type": "appointment_confirmed",
                    "appointment_id": result.get("appointment_id"),
                    "timestamp": datetime.now().isoformat()
                })
                context.state = ConversationState.COMPLETED
                context.appointment_id = result.get("appointment_id")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await manager.send_message(conversation_id, {
                "type": "error",
                "message": "I apologize, but I encountered an error. Please try again.",
                "timestamp": datetime.now().isoformat()
            })
    
    elif message_type == "reset_conversation":
        # Reset conversation
        context.state = ConversationState.INITIATED
        context.current_agent = AgentType.RECEPTIONIST
        context.messages = []
        context.patient_name = None
        context.patient_phone = None
        context.reason = None
        
        await manager.send_message(conversation_id, {
            "type": "conversation_reset",
            "message": "Conversation has been reset",
            "timestamp": datetime.now().isoformat()
        })
        
        # Send new greeting
        greeting = await manager.orchestrator.start_conversation()
        await manager.send_message(conversation_id, {
            "type": "agent_message",
            "content": greeting,
            "agent_type": "receptionist",
            "timestamp": datetime.now().isoformat()
        })
    
    else:
        await manager.send_message(conversation_id, {
            "type": "error",
            "message": f"Unknown message type: {message_type}",
            "timestamp": datetime.now().isoformat()
        })


def _map_conversation_state_to_workflow(state: ConversationState) -> WorkflowState:
    """Map ConversationState to WorkflowState."""
    mapping = {
        ConversationState.INITIATED: WorkflowState.START,
        ConversationState.GATHERING_INFO: WorkflowState.GATHERING_INFO,
        ConversationState.CHECKING_AVAILABILITY: WorkflowState.FINDING_SLOTS,
        ConversationState.PROPOSING_SLOTS: WorkflowState.PRESENTING_SLOTS,
        ConversationState.CONFIRMING: WorkflowState.CONFIRMING,
        ConversationState.COMPLETED: WorkflowState.COMPLETED,
        ConversationState.FAILED: WorkflowState.ERROR
    }
    return mapping.get(state, WorkflowState.START)


def _map_workflow_to_conversation_state(workflow_state) -> ConversationState:
    """Map WorkflowState to ConversationState."""
    if isinstance(workflow_state, str):
        workflow_state = WorkflowState(workflow_state)
    
    mapping = {
        WorkflowState.START: ConversationState.INITIATED,
        WorkflowState.GATHERING_INFO: ConversationState.GATHERING_INFO,
        WorkflowState.FINDING_SLOTS: ConversationState.CHECKING_AVAILABILITY,
        WorkflowState.PRESENTING_SLOTS: ConversationState.PROPOSING_SLOTS,
        WorkflowState.CONFIRMING: ConversationState.CONFIRMING,
        WorkflowState.FINALIZING: ConversationState.CONFIRMING,
        WorkflowState.COMPLETED: ConversationState.COMPLETED,
        WorkflowState.ERROR: ConversationState.FAILED
    }
    return mapping.get(workflow_state, ConversationState.INITIATED)


def _update_context_from_result(context: ConversationContext, result: Dict):
    """Update conversation context with orchestrator result."""
    # Update patient info
    if result.get("patient_info"):
        info = result["patient_info"]
        context.patient_name = info.get("patient_name") or context.patient_name
        context.patient_phone = info.get("patient_phone") or context.patient_phone
        context.patient_email = info.get("patient_email") or context.patient_email
        context.reason = info.get("reason") or context.reason
        context.preferred_date = info.get("preferred_date") or context.preferred_date
        context.preferred_time = info.get("preferred_time") or context.preferred_time
        context.doctor_preference = info.get("doctor_preference") or context.doctor_preference
    
    # Update slots
    if result.get("available_slots"):
        context.proposed_slots = result["available_slots"]
    
    # Update selected slot
    if result.get("selected_slot"):
        context.selected_slot_id = result["selected_slot"].get("slot_id")
    
    # Update state
    if result.get("workflow_state"):
        context.state = _map_workflow_to_conversation_state(result["workflow_state"])
    
    # Update current agent
    if result.get("current_agent"):
        context.current_agent = result["current_agent"]
    
    # Update appointment ID
    if result.get("appointment_id"):
        context.appointment_id = result["appointment_id"]