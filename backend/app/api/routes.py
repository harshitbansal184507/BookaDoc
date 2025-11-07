from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import date, datetime

from app.services.doctor_service import doctor_service
from app.models.doctor import Doctor, Specialization

from app.models.appointment import (
    AppointmentRequest,
    Appointment,
    AppointmentResponse,
    AppointmentStatus
)
from app.models.conversation import ConversationContext
from app.services.appointment_service import appointment_service
from app.utils.logger import app_logger as logger

router = APIRouter(prefix="/api", tags=["appointments"])

conversations = {}


@router.post("/appointments", response_model=AppointmentResponse)
async def create_appointment(request: AppointmentRequest):
    """
    Create a new appointment.
    
    Args:
        request: Appointment request data
        
    Returns:
        AppointmentResponse with created appointment
    """
    try:
        logger.info(f"Creating appointment for {request.patient_name}")
        doctor = None
        if request.doctor_preference:
            # Try to find doctor by name
            doctor = doctor_service.get_doctor_by_name(request.doctor_preference)
            
            if not doctor:
                # Try to search
                doctors = doctor_service.search_doctors(request.doctor_preference)
                if doctors:
                    doctor = doctors[0]
        
        # If no doctor found, get first available general physician
        if not doctor:
            doctors = doctor_service.get_doctors_by_specialization(
                Specialization.GENERAL_PHYSICIAN
            )
            if doctors:
                doctor = doctors[0]
            else:
                # Fallback to any available doctor
                all_doctors = doctor_service.get_all_doctors()
                if all_doctors:
                    doctor = all_doctors[0]
                else:
                    raise HTTPException(status_code=500, detail="No doctors available")
        
        
        # Parse date if provided as string
        appointment_date = request.preferred_date or date.today()
        
        # Default time if not specified
        from datetime import time
        appointment_time = time(10, 0)  
        
        if request.preferred_time:
            slots = appointment_service.find_slots_by_preference(
                preferred_date=appointment_date,
                preferred_time=request.preferred_time,
                num_slots=1
            )
            if slots:
                appointment_time = slots[0].start_time
        
        # Create the appointment
        result = appointment_service.create_appointment(
            patient_name=request.patient_name,
            patient_phone=request.patient_phone,
            patient_email=request.patient_email,
            appointment_date=appointment_date,
            doctor=doctor,
            appointment_time=appointment_time,
            reason=request.reason,
            doctor_name=request.doctor_preference or "Dr. Smith"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error creating appointment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/appointments/{appointment_id}", response_model=Appointment)
async def get_appointment(appointment_id: str):
    """
    Get appointment by ID.
    
    Args:
        appointment_id: Appointment ID
        
    Returns:
        Appointment details
    """
    appointment = appointment_service.get_appointment(appointment_id)
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    return appointment


@router.get("/appointments", response_model=List[Appointment])
async def list_appointments(
    status: Optional[AppointmentStatus] = Query(None),
    patient_phone: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None)
):
    """
    List appointments with optional filters.
    
    Args:
        status: Filter by status
        patient_phone: Filter by patient phone
        date_from: Filter by date range (from)
        date_to: Filter by date range (to)
        
    Returns:
        List of appointments
    """
    appointments = appointment_service.get_all_appointments()
    
    # Apply filters
    if status:
        appointments = [apt for apt in appointments if apt.status == status]
    
    if patient_phone:
        appointments = [apt for apt in appointments if apt.patient_phone == patient_phone]
    
    if date_from:
        appointments = [apt for apt in appointments if apt.appointment_date >= date_from]
    
    if date_to:
        appointments = [apt for apt in appointments if apt.appointment_date <= date_to]
    
    return appointments


@router.patch("/appointments/{appointment_id}/status", response_model=AppointmentResponse)
async def update_appointment_status(
    appointment_id: str,
    status: AppointmentStatus
):
    """
    Update appointment status.
    
    Args:
        appointment_id: Appointment ID
        status: New status
        
    Returns:
        Updated appointment
    """
    result = appointment_service.update_appointment_status(appointment_id, status)
    
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error)
    
    return result


@router.delete("/appointments/{appointment_id}", response_model=AppointmentResponse)
async def cancel_appointment(appointment_id: str):
    """
    Cancel an appointment.
    
    Args:
        appointment_id: Appointment ID
        
    Returns:
        Cancellation confirmation
    """
    result = appointment_service.cancel_appointment(appointment_id)
    
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error)
    
    return result


@router.get("/slots/available")
async def get_available_slots(
    start_date: Optional[date] = Query(None),
    num_days: int = Query(7, ge=1, le=30),
    preferred_time: Optional[str] = Query(None)
):
    """
    Get available appointment slots.
    
    Args:
        start_date: Starting date (default: today)
        num_days: Number of days to look ahead (1-30)
        preferred_time: Preferred time of day (morning/afternoon/evening)
        
    Returns:
        List of available slots
    """
    start = start_date or date.today()
    
    if preferred_time:
        slots = appointment_service.find_slots_by_preference(
            preferred_date=start,
            preferred_time=preferred_time,
            num_slots=num_days * 3  # Multiple slots per day
        )
    else:
        slots = appointment_service.get_available_slots(start, num_days)
    
    # Convert to dict for JSON serialization
    return [
        {
            "slot_id": slot.slot_id,
            "date": slot.date.isoformat(),
            "start_time": slot.start_time.isoformat(),
            "end_time": slot.end_time.isoformat(),
            "doctor_name": slot.doctor_name,
            "formatted": str(slot)
        }
        for slot in slots
    ]


@router.post("/conversations")
async def create_conversation():
    """
    Create a new conversation context.
    
    Returns:
        Conversation ID and initial context
    """
    context = ConversationContext()
    conversations[context.conversation_id] = context
    
    logger.info(f"Created conversation: {context.conversation_id}")
    
    return {
        "conversation_id": context.conversation_id,
        "state": context.state,
        "message": "Conversation started"
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """
    Get conversation context.
    
    Args:
        conversation_id: Conversation ID
        
    Returns:
        Conversation context
    """
    context = conversations.get(conversation_id)
    
    if not context:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return context


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    Delete a conversation.
    
    Args:
        conversation_id: Conversation ID
        
    Returns:
        Deletion confirmation
    """
    if conversation_id in conversations:
        del conversations[conversation_id]
        return {"message": "Conversation deleted", "conversation_id": conversation_id}
    
    raise HTTPException(status_code=404, detail="Conversation not found")


@router.get("/doctors", response_model=List[Doctor])
async def list_doctors(
    specialization: Optional[Specialization] = Query(None),
    active_only: bool = Query(True)
):
    """
    List all doctors with optional filters.
    
    Args:
        specialization: Filter by specialization
        active_only: Return only active doctors
        
    Returns:
        List of doctors
    """
    if specialization:
        doctors = doctor_service.get_doctors_by_specialization(specialization)
    else:
        doctors = doctor_service.get_all_doctors(active_only)
    
    return doctors


@router.get("/doctors/{doctor_id}", response_model=Doctor)
async def get_doctor(doctor_id: str):
    """
    Get doctor by ID.
    
    Args:
        doctor_id: Doctor ID
        
    Returns:
        Doctor details
    """
    doctor = doctor_service.get_doctor_by_id(doctor_id)
    
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    return doctor


@router.get("/doctors/search/{query}")
async def search_doctors(query: str):
    """
    Search doctors by name or specialization.
    
    Args:
        query: Search query
        
    Returns:
        List of matching doctors
    """
    doctors = doctor_service.search_doctors(query)
    return doctors


@router.get("/doctors/{doctor_id}/slots")
async def get_doctor_slots(
    doctor_id: str,
    start_date: Optional[date] = Query(None),
    num_days: int = Query(7, ge=1, le=30),
    preferred_time: Optional[str] = Query(None)
):
    """
    Get available slots for a specific doctor.
    
    Args:
        doctor_id: Doctor ID
        start_date: Starting date (default: today)
        num_days: Number of days to look ahead
        preferred_time: Preferred time of day (morning/afternoon/evening)
        
    Returns:
        List of available slots
    """
    doctor = doctor_service.get_doctor_by_id(doctor_id)
    
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    start = start_date or date.today()
    
    if preferred_time:
        slots = appointment_service.find_slots_by_preference(
            doctor=doctor,
            preferred_date=start,
            preferred_time=preferred_time,
            num_slots=num_days * 3
        )
    else:
        slots = appointment_service.get_available_slots(doctor, start, num_days)
    
    return [
        {
            "slot_id": slot.slot_id,
            "date": slot.date.isoformat(),
            "start_time": slot.start_time.isoformat(),
            "end_time": slot.end_time.isoformat(),
            "doctor_name": slot.doctor_name,
            "doctor_id": slot.doctor_id,
            "formatted": str(slot)
        }
        for slot in slots
    ]