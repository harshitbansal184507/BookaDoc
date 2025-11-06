from app.models.appointment import (
    AppointmentRequest, 
    AppointmentSlot, 
    Appointment,
    AppointmentStatus
)
from app.models.conversation import (
    ConversationContext,
    ConversationState,
    AgentType
)
from datetime import date, time, datetime


def test_appointment_request():
    """Test appointment request model."""
    request = AppointmentRequest(
        patient_name="John Doe",
        patient_phone="9876543210",
        patient_email="john@example.com",
        reason="Regular checkup",
        preferred_date=date.today()
    )
    print("✓ AppointmentRequest created:", request.patient_name)
    return request


def test_appointment_slot():
    """Test appointment slot model."""
    slot = AppointmentSlot(
        date=date.today(),
        start_time=time(10, 0),
        end_time=time(10, 30),
        doctor_name="Dr. Smith"
    )
    print("✓ AppointmentSlot created:", str(slot))
    return slot


def test_appointment():
    """Test appointment model."""
    appointment = Appointment(
        patient_name="John Doe",
        patient_phone="9876543210",
        appointment_date=date.today(),
        appointment_time=time(10, 0),
        doctor_name="Dr. Smith",
        reason="Regular checkup"
    )
    print("✓ Appointment created:", appointment.to_readable_string())
    return appointment


def test_conversation_context():
    """Test conversation context."""
    context = ConversationContext()
    context.add_message("user", "I need to book an appointment")
    context.add_message("assistant", "I'd be happy to help!", AgentType.RECEPTIONIST)
    
    context.patient_name = "John Doe"
    context.patient_phone = "9876543210"
    context.reason = "Checkup"
    
    print("✓ ConversationContext created:", context.conversation_id)
    print(f"  Has required info: {context.has_required_info()}")
    print(f"  Message count: {len(context.messages)}")
    return context


if __name__ == "__main__":
    print("\n=== Testing Models ===\n")
    test_appointment_request()
    test_appointment_slot()
    test_appointment()
    test_conversation_context()
    print("\n✓ All models working correctly!\n")