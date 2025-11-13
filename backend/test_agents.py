import asyncio
import sys
from datetime import datetime
from typing import Dict, Any
from colorama import init, Fore, Back, Style
from app.agents.orchestrator import OrchestratorAgent, WorkflowState
from app.utils.logger import app_logger as logger
from app.db.mongodb import connect_to_mongo, close_mongo_connection, get_database

init(autoreset=True)


class InteractiveAgentTester:
    """Interactive terminal-based agent tester - conversation only."""
    
    def __init__(self):
        """Initialize the interactive tester."""
        self.orchestrator = OrchestratorAgent()
        self.conversation_context = self._init_context()
        self.conversation_history = []
        self.db = None
        self.conversation_id = None
        
    def _init_context(self) -> Dict[str, Any]:
        """Initialize conversation context."""
        return {
            "messages": [],
            "patient_info": {},
            "available_slots": [],
            "selected_slot": None,
            "workflow_state": "start",
            "current_agent": "receptionist",
            "has_required_info": False,
            "awaiting_confirmation": False
        }
    
    def print_banner(self):
        print(Fore.CYAN + Style.BRIGHT + "  🏥 BookaDoc - Interactive Agent Testing Terminal")
        
    def print_help(self):
        """Print help information."""
        print(Fore.CYAN + "\n📋 Available Commands:")
        print(Fore.WHITE + "  /help       - Show this help message")
        print(Fore.WHITE + "  /reset      - Reset the conversation")
        print(Fore.WHITE + "  /quit       - Exit the program")
        print()
    
    def print_agent_message(self, message: str, agent: str):
        """Print agent message with formatting."""
        agent_emoji = {
            'receptionist': '👨‍💼',
            'scheduler': '📅',
            'confirmation': '✅',
            'orchestrator': '🎯'
        }
        
        emoji = agent_emoji.get(agent.lower(), '🤖')
        agent_name = agent.capitalize()
        
        print(Fore.BLUE + f"\n{emoji} {agent_name}:")
        print(Fore.WHITE + f"  {message}\n")
    
    def print_user_prompt(self):
        """Print user input prompt."""
        print(Fore.GREEN + "You: " + Fore.WHITE, end='')
    
    async def save_conversation(self):
        """Save conversation to MongoDB."""
        try:
            if self.db is None:
                return
            
            if not self.conversation_history:
                return
            
            # Create conversation document
            conversation_doc = {
                "conversation_id": self.conversation_id or str(datetime.now().timestamp()),
                "messages": [
                    {
                        "role": msg['role'],
                        "content": msg['content'],
                        "timestamp": msg['timestamp']
                    }
                    for msg in self.conversation_history
                ],
                "patient_info": self.conversation_context.get('patient_info', {}),
                "workflow_state": str(self.conversation_context.get('workflow_state', 'unknown')),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            result = await self.db.conversations.insert_one(conversation_doc)
            self.conversation_id = str(result.inserted_id)
            
            print(Fore.GREEN + f"\n✅ Conversation saved to MongoDB")
            print(Fore.WHITE + f"   ID: {Fore.CYAN}{self.conversation_id}\n")
            
        except Exception as e:
            print(Fore.RED + f"❌ Error saving conversation: {e}\n")
    
    async def process_command(self, command: str) -> bool:
        """
        Process special commands.
        
        Args:
            command: Command string
            
        Returns:
            True if should continue, False if should quit
        """
        command = command.lower().strip()
        
        if command == '/help':
            self.print_help()
        elif command == '/reset':
            print(Fore.YELLOW + "\n🔄 Resetting conversation...\n")
            
            # Save before reset
            if self.conversation_history and self.db is not None:
                save = input(Fore.CYAN + "Save conversation before reset? (yes/no): " + Fore.WHITE)
                if save.lower() in ['yes', 'y']:
                    await self.save_conversation()
            
            self.conversation_context = self._init_context()
            self.conversation_history = []
            self.conversation_id = None
            
            # Get new greeting
            greeting = await self.orchestrator.start_conversation()
            self.print_agent_message(greeting, "receptionist")
        elif command == '/quit' or command == '/exit':
            # Save before quit
            if self.conversation_history and self.db is not None:
                save = input(Fore.CYAN + "\nSave conversation before exit? (yes/no): " + Fore.WHITE)
                if save.lower() in ['yes', 'y']:
                    await self.save_conversation()
            
            print(Fore.YELLOW + "\n👋 Thank you for testing BookaDoc! Goodbye!\n")
            return False
        else:
            print(Fore.RED + f"\n❌ Unknown command: {command}")
            print(Fore.YELLOW + "   Type /help for available commands\n")
        
        return True
    
    async def process_user_message(self, user_input: str):
        """
        Process user message through orchestrator.
        
        Args:
            user_input: User's message
        """
        # Add to history
        self.conversation_history.append({
            'role': 'user',
            'content': user_input,
            'timestamp': datetime.now()
        })
        
        # Show processing indicator
        print(Fore.YELLOW + "\n⏳ Processing..." + Style.RESET_ALL, end='', flush=True)
        
        try:
            # Process through orchestrator
            result = await self.orchestrator.process_message(
                user_message=user_input,
                conversation_context=self.conversation_context
            )
            
            # Clear processing indicator
            print("\r" + " " * 20 + "\r", end='')
            
            # Update context
            self.conversation_context.update(result)
            
            # Get response
            response = result.get("agent_response", "")
            agent = result.get("current_agent", "assistant")
            workflow_state = result.get("workflow_state", "unknown")
            
            # Add to history
            self.conversation_history.append({
                'role': 'assistant',
                'content': response,
                'agent': agent,
                'timestamp': datetime.now()
            })
            
            # Display agent response
            self.print_agent_message(response, str(agent))
            
            # Check if completed
            if str(workflow_state) == "WorkflowState.COMPLETED":
                appointment_id = result.get("appointment_id", "N/A")
                print(Fore.GREEN + Style.BRIGHT + "="*70)
                print(Fore.GREEN + Style.BRIGHT + "  ✅ APPOINTMENT SUCCESSFULLY BOOKED!")
                print(Fore.GREEN + Style.BRIGHT + f"  📋 Appointment ID: {appointment_id}")
                print(Fore.GREEN + Style.BRIGHT + "="*70 + "\n")
                
                # Auto-save conversation
                if self.db is not None:
                    print(Fore.YELLOW + "💾 Saving conversation to database...")
                    await self.save_conversation()
                
        except Exception as e:
            print("\r" + " " * 20 + "\r", end='')
            print(Fore.RED + f"\n❌ Error: {str(e)}\n")
            logger.error(f"Error processing message: {e}", exc_info=True)
    
    async def run(self):
        """Run the interactive testing session."""
        self.print_banner()
        
        # Connect to MongoDB
        try:
            print(Fore.YELLOW + "🔌 Connecting to MongoDB...\n")
            await connect_to_mongo()
            self.db = get_database()
            
            if self.db is not None:
                print(Fore.GREEN + "✅ MongoDB connected successfully!\n")
            else:
                print(Fore.YELLOW + "⚠️  MongoDB not available - running without database\n")
                
        except Exception as e:
            print(Fore.YELLOW + f"⚠️  Could not connect to MongoDB: {e}")
            print(Fore.YELLOW + "   Running without database persistence\n")
        
        self.print_help()
        
        # Get initial greeting
        print(Fore.YELLOW + "🔄 Initializing agent system...\n")
        greeting = await self.orchestrator.start_conversation()
        self.print_agent_message(greeting, "receptionist")
        
        # Main interaction loop
        while True:
            try:
                self.print_user_prompt()
                user_input = input().strip()
                
                # Skip empty input
                if not user_input:
                    continue
                
                # Check for commands
                if user_input.startswith('/'):
                    should_continue = await self.process_command(user_input)
                    if not should_continue:
                        break
                else:
                    # Process as regular message
                    await self.process_user_message(user_input)
                    
            except KeyboardInterrupt:
                print(Fore.YELLOW + "\n\n👋 Interrupted. Type /quit to exit or continue chatting.\n")
                continue
            except EOFError:
                print(Fore.YELLOW + "\n\n👋 Goodbye!\n")
                break
            except Exception as e:
                print(Fore.RED + f"\n❌ Unexpected error: {str(e)}\n")
                logger.error(f"Unexpected error: {e}", exc_info=True)
        
        # Cleanup
        await close_mongo_connection()


async def main():
    """Main entry point."""
    tester = InteractiveAgentTester()
    await tester.run()


if __name__ == "__main__":
    try:
        # Check if colorama is installed
        try:
            import colorama
        except ImportError:
            print("\n⚠️  colorama not installed. Installing for better terminal colors...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "colorama"])
            print("✅ colorama installed successfully!\n")
            import colorama
        
        # Run the interactive tester
        asyncio.run(main())
        
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}\n")
        sys.exit(1)