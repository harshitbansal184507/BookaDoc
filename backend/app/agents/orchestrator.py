from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

from app.agents.receptionist_agent import ReceptionistAgent
from app.agents.scheduler_agent import SchedulerAgent
from app.agents.confirmation_agent import ConfirmationAgent
from app.models.conversation import ConversationState, AgentType
from app.utils.logger import app_logger as logger
from langsmith import traceable



class WorkflowState(str, Enum):
    """Workflow states for the orchestrator."""
    START = "start"
    GATHERING_INFO = "gathering_info"
    FINDING_SLOTS = "finding_slots"
    PRESENTING_SLOTS = "presenting_slots"
    AWAITING_SELECTION = "awaiting_selection"
    CONFIRMING = "confirming"
    COMPLETED = "completed"
    ERROR = "error"



class StateKeys:
    """Centralized state key definitions."""
    USER_MESSAGE = "user_message"
    CONVERSATION_HISTORY = "conversation_history"
    PATIENT_INFO = "patient_info"
    AVAILABLE_SLOTS = "available_slots"
    SELECTED_SLOT = "selected_slot"
    WORKFLOW_STATE = "workflow_state"
    CURRENT_AGENT = "current_agent"
    AGENT_RESPONSE = "agent_response"
    HAS_REQUIRED_INFO = "has_required_info"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    APPOINTMENT_ID = "appointment_id"
    ERROR = "error"
    SLOT_SELECTION_ATTEMPTS = "slot_selection_attempts"


class OrchestratorAgent:
    """
    Main orchestrator using LangGraph to coordinate all agents.
    Manages the appointment booking workflow with clear state transitions.
    """
    
    MAX_SLOT_SELECTION_ATTEMPTS = 3
    
    def __init__(self):
        """Initialize orchestrator with all agents."""
        self.receptionist = ReceptionistAgent()
        self.scheduler = SchedulerAgent()
        self.confirmation = ConfirmationAgent()
        
        # Initialize workflow graph
        self.workflow = self._build_workflow()
        
        logger.info("Orchestrator initialized with LangGraph workflow")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow with proper state management."""
        workflow = StateGraph(dict)
        
        # Add nodes (processing states)
        workflow.add_node("gather_info", self._gather_info_node)
        workflow.add_node("find_slots", self._find_slots_node)
        workflow.add_node("present_slots", self._present_slots_node)
        workflow.add_node("await_selection", self._await_selection_node)
        workflow.add_node("confirm", self._confirm_node)
        workflow.add_node("finalize", self._finalize_node)
        
        # Set entry point
        workflow.set_entry_point("gather_info")
        
        # Add edges with clear transition logic
        workflow.add_conditional_edges(
            "gather_info",
            self._route_from_gather_info,
            {
                "find_slots": "find_slots",
                "gather_info": "gather_info",
                END: END
            }
        )
        
        workflow.add_edge("find_slots", "present_slots")
        workflow.add_edge("present_slots", "await_selection")
        
        workflow.add_conditional_edges(
            "await_selection",
            self._route_from_await_selection,
            {
                "confirm": "confirm",
                "await_selection": "await_selection",
                "present_slots": "present_slots",
                END: END
            }
        )
        
        workflow.add_conditional_edges(
            "confirm",
            self._route_from_confirm,
            {
                "finalize": "finalize",
                "await_selection": "await_selection",
                END: END
            }
        )
        
        workflow.add_edge("finalize", END)
        
        return workflow.compile()
    
    async def _gather_info_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node for gathering patient information.
        Collects required info before proceeding to scheduling.
        """
        logger.info("Node: Gathering information")
        
        user_message = state.get(StateKeys.USER_MESSAGE, "")
        conversation_history = state.get(StateKeys.CONVERSATION_HISTORY, [])
        
        try:
            # Get response from receptionist
            response = await self.receptionist.process(
                user_message=user_message,
                context=state.get(StateKeys.PATIENT_INFO, {})
            )
            
            # Extract information from conversation
            extracted = await self.receptionist.extract_information(
                conversation_history=conversation_history,
                latest_message=user_message
            )
            
            # Merge extracted info with existing patient info
            current_info = state.get(StateKeys.PATIENT_INFO, {})
            updated_info = {**current_info}
            
            # Only update non-empty values
            for key, value in extracted.items():
                if value:
                    updated_info[key] = value
            
            # Check if we have all required information
            has_required = self.receptionist.has_required_info(updated_info)
            
            # Update state
            state[StateKeys.PATIENT_INFO] = updated_info
            state[StateKeys.AGENT_RESPONSE] = response
            state[StateKeys.CURRENT_AGENT] = AgentType.RECEPTIONIST
            state[StateKeys.HAS_REQUIRED_INFO] = has_required
            
            if has_required:
                state[StateKeys.WORKFLOW_STATE] = WorkflowState.FINDING_SLOTS
                logger.info(f"Required info collected: {updated_info}")
            else:
                state[StateKeys.WORKFLOW_STATE] = WorkflowState.GATHERING_INFO
                logger.info(f"Still gathering info. Current: {updated_info}")
            
            return state
            
        except Exception as e:
            logger.error(f"Error in gather_info_node: {e}")
            state[StateKeys.AGENT_RESPONSE] = "I'm having trouble processing that. Could you please repeat your information?"
            state[StateKeys.WORKFLOW_STATE] = WorkflowState.GATHERING_INFO
            return state
    
    async def _find_slots_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node for finding available appointment slots.
        """
        logger.info("Node: Finding slots")
        
        patient_info = state.get(StateKeys.PATIENT_INFO, {})
        
        try:
            # Get available slots
            slots = await self.scheduler.get_available_slots(
                patient_info=patient_info,
                num_slots=5
            )
            
            if not slots:
                state[StateKeys.AGENT_RESPONSE] = "I'm sorry, I couldn't find any available slots. Would you like to try different preferences?"
                state[StateKeys.WORKFLOW_STATE] = WorkflowState.GATHERING_INFO
                state[StateKeys.HAS_REQUIRED_INFO] = False
            else:
                state[StateKeys.AVAILABLE_SLOTS] = slots
                state[StateKeys.WORKFLOW_STATE] = WorkflowState.PRESENTING_SLOTS
                state[StateKeys.CURRENT_AGENT] = AgentType.SCHEDULER
                logger.info(f"Found {len(slots)} available slots")
            
            return state
            
        except Exception as e:
            logger.error(f"Error finding slots: {e}")
            state[StateKeys.AGENT_RESPONSE] = "I encountered an error while searching for appointments. Let me try again."
            state[StateKeys.WORKFLOW_STATE] = WorkflowState.ERROR
            return state
    
    async def _present_slots_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node for presenting available slots to the user.
        """
        logger.info("Node: Presenting slots")
        
        slots = state.get(StateKeys.AVAILABLE_SLOTS, [])
        
        try:
            # Format slots message
            message = await self.scheduler.format_slots_message(slots)
            
            state[StateKeys.AGENT_RESPONSE] = message
            state[StateKeys.WORKFLOW_STATE] = WorkflowState.AWAITING_SELECTION
            state[StateKeys.SLOT_SELECTION_ATTEMPTS] = 0
            
            return state
            
        except Exception as e:
            logger.error(f"Error presenting slots: {e}")
            state[StateKeys.AGENT_RESPONSE] = "I had trouble formatting the available times. Please try again."
            state[StateKeys.WORKFLOW_STATE] = WorkflowState.ERROR
            return state
    
    async def _await_selection_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node for processing user's slot selection.
        """
        logger.info("Node: Awaiting slot selection")
        
        user_message = state.get(StateKeys.USER_MESSAGE, "").lower().strip()
        slots = state.get(StateKeys.AVAILABLE_SLOTS, [])
        attempts = state.get(StateKeys.SLOT_SELECTION_ATTEMPTS, 0)
        
        # Parse slot selection
        selected_slot, error_message = self._parse_slot_selection(user_message, slots)
        
        if selected_slot:
            state[StateKeys.SELECTED_SLOT] = selected_slot
            state[StateKeys.WORKFLOW_STATE] = WorkflowState.CONFIRMING
            state[StateKeys.CURRENT_AGENT] = AgentType.CONFIRMATION
            logger.info(f"Slot selected: {selected_slot}")
        else:
            attempts += 1
            state[StateKeys.SLOT_SELECTION_ATTEMPTS] = attempts
            
            if attempts >= self.MAX_SLOT_SELECTION_ATTEMPTS:
                state[StateKeys.AGENT_RESPONSE] = "I'm having trouble understanding your selection. Let me show you the available slots again."
                state[StateKeys.WORKFLOW_STATE] = WorkflowState.PRESENTING_SLOTS
            else:
                state[StateKeys.AGENT_RESPONSE] = error_message or "Please select a slot by entering its number (e.g., 1, 2, 3)."
                state[StateKeys.WORKFLOW_STATE] = WorkflowState.AWAITING_SELECTION
        
        return state
    
    async def _confirm_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node for confirming the selected appointment with the user.
        """
        logger.info("Node: Confirming appointment")
        
        selected_slot = state.get(StateKeys.SELECTED_SLOT)
        patient_info = state.get(StateKeys.PATIENT_INFO, {})
        
        try:
            # Create confirmation message
            message = await self.confirmation.create_confirmation_message(
                patient_info=patient_info,
                selected_slot=selected_slot
            )
            
            state[StateKeys.AGENT_RESPONSE] = message
            state[StateKeys.WORKFLOW_STATE] = WorkflowState.CONFIRMING
            state[StateKeys.AWAITING_CONFIRMATION] = True
            state[StateKeys.CURRENT_AGENT] = AgentType.CONFIRMATION
            
            return state
            
        except Exception as e:
            logger.error(f"Error in confirm_node: {e}")
            state[StateKeys.AGENT_RESPONSE] = "I had trouble preparing the confirmation. Please try again."
            state[StateKeys.WORKFLOW_STATE] = WorkflowState.ERROR
            return state
    
    async def _finalize_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node for finalizing the appointment booking.
        """
        logger.info("Node: Finalizing appointment")
        
        user_message = state.get(StateKeys.USER_MESSAGE, "").lower().strip()
        
        # Check for confirmation
        is_confirmed = self._is_confirmation(user_message)
        is_rejected = self._is_rejection(user_message)
        
        if is_confirmed:
            try:
                # Finalize appointment
                result = await self.confirmation.finalize_appointment(
                    patient_info=state.get(StateKeys.PATIENT_INFO, {}),
                    selected_slot=state.get(StateKeys.SELECTED_SLOT, {})
                )
                
                if result and result.get("appointment_id"):
                    message = await self.confirmation.create_success_message(result)
                    state[StateKeys.AGENT_RESPONSE] = message
                    state[StateKeys.WORKFLOW_STATE] = WorkflowState.COMPLETED
                    state[StateKeys.APPOINTMENT_ID] = result["appointment_id"]
                    logger.info(f"Appointment finalized: {result['appointment_id']}")
                else:
                    state[StateKeys.AGENT_RESPONSE] = "I'm sorry, there was an error creating your appointment. Please try again or contact support."
                    state[StateKeys.WORKFLOW_STATE] = WorkflowState.ERROR
                
            except Exception as e:
                logger.error(f"Error finalizing appointment: {e}")
                state[StateKeys.AGENT_RESPONSE] = "An error occurred while booking your appointment. Please try again."
                state[StateKeys.WORKFLOW_STATE] = WorkflowState.ERROR
                
        elif is_rejected:
            state[StateKeys.AGENT_RESPONSE] = "No problem! Would you like to select a different time slot?"
            state[StateKeys.WORKFLOW_STATE] = WorkflowState.AWAITING_SELECTION
            state[StateKeys.AWAITING_CONFIRMATION] = False
        else:
            state[StateKeys.AGENT_RESPONSE] = "I didn't catch that. Please reply 'yes' to confirm or 'no' to choose a different time."
            state[StateKeys.WORKFLOW_STATE] = WorkflowState.CONFIRMING
        
        return state
    
    def _parse_slot_selection(self, user_message: str, slots: List[Dict]) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Parse user's slot selection from their message.
        
        Returns:
            Tuple of (selected_slot, error_message)
        """
        if not slots:
            return None, "No slots available to select from."
        
        # Extract numbers from message
        numbers = [int(char) for char in user_message if char.isdigit()]
        
        if not numbers:
            return None, "Please enter the number of the slot you'd like to book."
        
        # Take the first number found
        slot_num = numbers[0] - 1  # Convert to 0-based index
        
        if 0 <= slot_num < len(slots):
            return slots[slot_num], None
        else:
            return None, f"Please select a number between 1 and {len(slots)}."
    
    def _is_confirmation(self, message: str) -> bool:
        """Check if message is a confirmation."""
        confirmations = ["yes", "confirm", "ok", "sure", "correct", "right", "yep", "yeah", "y"]
        return any(word in message for word in confirmations)
    
    def _is_rejection(self, message: str) -> bool:
        """Check if message is a rejection."""
        rejections = ["no", "nope", "cancel", "different", "change", "n"]
        return any(word in message for word in rejections)
    
    # Routing functions for conditional edges
    
    def _route_from_gather_info(self, state: Dict[str, Any]) -> str:
        """Route from info gathering based on completeness."""
        has_info = state.get(StateKeys.HAS_REQUIRED_INFO, False)
        workflow_state = state.get(StateKeys.WORKFLOW_STATE)
        
        if workflow_state == WorkflowState.ERROR:
            return END
        elif has_info:
            return "find_slots"
        else:
            return "gather_info"
    
    def _route_from_await_selection(self, state: Dict[str, Any]) -> str:
        """Route from slot selection based on user choice."""
        workflow_state = state.get(StateKeys.WORKFLOW_STATE)
        
        if workflow_state == WorkflowState.ERROR:
            return END
        elif workflow_state == WorkflowState.CONFIRMING:
            return "confirm"
        elif workflow_state == WorkflowState.PRESENTING_SLOTS:
            return "present_slots"
        else:
            return "await_selection"
    
    def _route_from_confirm(self, state: Dict[str, Any]) -> str:
        """Route from confirmation based on user response."""
        workflow_state = state.get(StateKeys.WORKFLOW_STATE)
        awaiting = state.get(StateKeys.AWAITING_CONFIRMATION, False)
        
        if workflow_state == WorkflowState.ERROR:
            return END
        elif awaiting and workflow_state == WorkflowState.CONFIRMING:
            return "finalize"
        elif workflow_state == WorkflowState.AWAITING_SELECTION:
            return "await_selection"
        else:
            return END
    
    async def process_message(
        self,
        user_message: str,
        conversation_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a user message through the workflow.
        
        Args:
            user_message: User's message
            conversation_context: Current conversation context
            
        Returns:
            Updated state with agent response
        """
        try:
            # Initialize state from conversation context
            state = self._initialize_state(user_message, conversation_context)
            
            # Route to appropriate node based on current workflow state
            result = await self._route_and_process(state)
            
            logger.info(
                f"Workflow transition: {conversation_context.get(StateKeys.WORKFLOW_STATE)} -> "
                f"{result.get(StateKeys.WORKFLOW_STATE)} | Agent: {result.get(StateKeys.CURRENT_AGENT)}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in orchestrator.process_message: {e}", exc_info=True)
            return self._create_error_state(str(e))
    
    def _initialize_state(self, user_message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize state from user message and conversation context."""
        return {
            StateKeys.USER_MESSAGE: user_message,
            StateKeys.CONVERSATION_HISTORY: context.get(StateKeys.CONVERSATION_HISTORY, []),
            StateKeys.PATIENT_INFO: context.get(StateKeys.PATIENT_INFO, {}),
            StateKeys.AVAILABLE_SLOTS: context.get(StateKeys.AVAILABLE_SLOTS, []),
            StateKeys.SELECTED_SLOT: context.get(StateKeys.SELECTED_SLOT),
            StateKeys.WORKFLOW_STATE: context.get(StateKeys.WORKFLOW_STATE, WorkflowState.START),
            StateKeys.CURRENT_AGENT: context.get(StateKeys.CURRENT_AGENT, AgentType.RECEPTIONIST),
            StateKeys.HAS_REQUIRED_INFO: context.get(StateKeys.HAS_REQUIRED_INFO, False),
            StateKeys.AWAITING_CONFIRMATION: context.get(StateKeys.AWAITING_CONFIRMATION, False),
            StateKeys.SLOT_SELECTION_ATTEMPTS: context.get(StateKeys.SLOT_SELECTION_ATTEMPTS, 0)
        }
    
    async def _route_and_process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Route to appropriate node and process based on current workflow state."""
        current_state = state.get(StateKeys.WORKFLOW_STATE)
        
        # State transition logic
        if current_state in [WorkflowState.START, WorkflowState.GATHERING_INFO]:
            result = await self._gather_info_node(state)
            
            # If we have required info, automatically find and present slots
            if result.get(StateKeys.HAS_REQUIRED_INFO):
                result = await self._find_slots_node(result)
                if result.get(StateKeys.WORKFLOW_STATE) == WorkflowState.PRESENTING_SLOTS:
                    result = await self._present_slots_node(result)
            
            return result
            
        elif current_state == WorkflowState.AWAITING_SELECTION:
            result = await self._await_selection_node(state)
            
            # If slot selected, move to confirmation
            if result.get(StateKeys.WORKFLOW_STATE) == WorkflowState.CONFIRMING:
                result = await self._confirm_node(result)
            
            return result
            
        elif current_state == WorkflowState.CONFIRMING:
            return await self._finalize_node(state)
            
        elif current_state == WorkflowState.COMPLETED:
            return {
                **state,
                StateKeys.AGENT_RESPONSE: "Your appointment has been confirmed! Is there anything else I can help you with?"
            }
            
        else:
            logger.warning(f"Unexpected workflow state: {current_state}")
            return self._create_error_state("Unexpected workflow state")
    
    def _create_error_state(self, error_message: str) -> Dict[str, Any]:
        """Create an error state with reset to beginning."""
        return {
            StateKeys.AGENT_RESPONSE: "I apologize, but I encountered an error. Let's start over. What can I help you with today?",
            StateKeys.WORKFLOW_STATE: WorkflowState.START,
            StateKeys.CURRENT_AGENT: AgentType.RECEPTIONIST,
            StateKeys.ERROR: error_message,
            StateKeys.HAS_REQUIRED_INFO: False,
            StateKeys.AWAITING_CONFIRMATION: False
        }
    
    async def start_conversation(self) -> str:
        """Get initial greeting message."""
        try:
            greeting = await self.receptionist.process(
                user_message="",
                context={"is_initial": True}
            )
            
            # Fallback to default greeting if needed
            if not greeting or len(greeting) < 10:
                greeting = (
                    "Hello! Welcome to BookaDoc. I'm here to help you schedule an appointment. "
                    "To get started, may I have your full name, please?"
                )
            
            logger.info("Conversation started with greeting")
            return greeting
            
        except Exception as e:
            logger.error(f"Error starting conversation: {e}")
            return "Hello! Welcome to BookaDoc. How can I help you today?"