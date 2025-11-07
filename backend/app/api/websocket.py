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
    
    # Send welcome message
    await manager.send_message(conversation_id, {
        "type": "connected",
        "conversation_id": conversation_id,
        "message": "Connected to appointment booking assistant",
        "timestamp": datetime.now().isoformat()
    })
    
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
    Handle incoming WebSocket message.
    
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
        
        # Echo back (placeholder - will be replaced by agent in Phase 5)
        await manager.send_message(conversation_id, {
            "type": "agent_message",
            "content": f"I received your message: {content}",
            "agent_type": "receptionist",
            "timestamp": datetime.now().isoformat()
        })
        
        # Send status update
        await manager.send_message(conversation_id, {
            "type": "status_update",
            "state": context.state,
            "message": "Processing your request...",
            "timestamp": datetime.now().isoformat()
        })
    
    elif message_type == "get_slots":
        # Handle slot request
        from app.services.appointment_service import appointment_service
        from datetime import date
        
        slots = appointment_service.get_available_slots(date.today(), num_days=3)
        
        await manager.send_message(conversation_id, {
            "type": "slot_proposal",
            "slots": [
                {
                    "slot_id": slot.slot_id,
                    "date": slot.date.isoformat(),
                    "start_time": slot.start_time.isoformat(),
                    "formatted": str(slot)
                }
                for slot in slots[:5]
            ],
            "timestamp": datetime.now().isoformat()
        })
    
    elif message_type == "select_slot":
        # Handle slot selection
        slot_id = message_data.get("slot_id")
        context.selected_slot_id = slot_id
        context.state = ConversationState.CONFIRMING
        
        await manager.send_message(conversation_id, {
            "type": "confirmation_request",
            "slot_id": slot_id,
            "message": "Please confirm your appointment details",
            "timestamp": datetime.now().isoformat()
        })
    
    elif message_type == "confirm_appointment":
        # Handle appointment confirmation
        context.state = ConversationState.COMPLETED
        
        await manager.send_message(conversation_id, {
            "type": "appointment_confirmed",
            "message": "Your appointment has been confirmed!",
            "appointment_id": "APT-12345",  # Placeholder
            "timestamp": datetime.now().isoformat()
        })
    
    else:
        await manager.send_message(conversation_id, {
            "type": "error",
            "message": f"Unknown message type: {message_type}",
            "timestamp": datetime.now().isoformat()
        })