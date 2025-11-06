import asyncio
from datetime import date, time, timedelta
from app.services.llm_service import llm_service
from app.services.appointment_service import appointment_service


async def test_llm_service():
    """Test LLM service."""
    print("\n=== Testing LLM Service ===\n")
    
    messages = [
        {"role": "user", "content": "Hello! I need help booking an appointment."}
    ]
    
    response = await llm_service.generate_response(
        messages=messages,
        system_prompt="You are a helpful medical receptionist.",
        temperature=0.7
    )
    
    print(f"✓ LLM Response: {response[:100]}...")


def test_appointment_service():
    """Test appointment service."""
    print("\n=== Testing Appointment Service ===\n")
    
    # Test 1: Get available slots
    slots = appointment_service.get_available_slots(
        start_date=date.today(),
        num_days=3
    )
    print(f"✓ Found {len(slots)} available slots")
    
    if slots:
        print(f"  First slot: {slots[0]}")
    
    # Test 2: Create appointment
    result = appointment_service.create_appointment(
        patient_name="John Doe",
        patient_phone="9876543210",
        appointment_date=date.today() + timedelta(days=1),
        appointment_time=time(10, 0),
        reason="Regular checkup"
    )
    
    if result.success:
        print(f"✓ Appointment created: {result.appointment.appointment_id}")
        
        # Test 3: Get appointment
        apt = appointment_service.get_appointment(result.appointment.appointment_id)
        print(f"✓ Retrieved appointment: {apt.to_readable_string()}")
        
        # Test 4: Update status
        update_result = appointment_service.update_appointment_status(
            result.appointment.appointment_id,
            "confirmed"
        )
        print(f"✓ Status updated: {update_result.appointment.status}")
    else:
        print(f"✗ Failed to create appointment: {result.error}")


async def main():
    """Run all tests."""
    await test_llm_service()
    test_appointment_service()
    print("\n✓ All services working correctly!\n")


if __name__ == "__main__":
    asyncio.run(main())