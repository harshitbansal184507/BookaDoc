from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import date

from app.models.appointment import (
    AppointmentRequest,
    Appointment,
    AppointmentResponse,
    AppointmentStatus
)
from app.models.conversation import ConversationContext
from app.models.doctor import Doctor, Specialization
from app.services.appointment_service import appointment_service
from app.services.doctor_service import doctor_service
from app.utils.logger import app_logger as logger

router = APIRouter(prefix="/api", tags=["appointments"])

# In-memory storage for conversations
conversations = {}


@router.post("/appointments", response_model=AppointmentResponse)
async def create_appointment(request: AppointmentRequest):
    """Create a new appointment."""
    try:
        logger.info(f"Creating appointment for {request.patient_name}")
        
        # Get doctor
        doctor = None
        if request.doctor_preference:
            doctor = await doctor_service.get_doctor_by_name(request.doctor_preference)
            
            if not doctor:
                doctors = await doctor_service.search_doctors(request.doctor_preference)
                if doctors:
                    doctor = doctors[0]
        
        if not doctor:
            doctors = await doctor_service.get_doctors_by_specialization(
                Specialization.GENERAL_PHYSICIAN
            )
            if doctors:
                doctor = doctors[0]
            else:
                all_doctors = await doctor_service.get_all_doctors()
                if all_doctors:
                    doctor = all_doctors[0]
                else:
                    raise HTTPException(status_code=500, detail="No doctors available")
        
        appointment_date = request.preferred_date or date.today()
        
        slots = await appointment_service.find_slots_by_preference(
            doctor_id=doctor.doctor_id,
            doctor_name=f"Dr. {doctor.name}",
            preferred_date=appointment_date,
            preferred_time=request.preferred_time,
            num_slots=1
        )
        
        if not slots:
            raise HTTPException(
                status_code=400,
                detail=f"No available slots found for Dr. {doctor.name}"
            )
        
        appointment_time = slots[0].start_time
        
        result = await appointment_service.create_appointment(
            patient_name=request.patient_name,
            patient_phone=request.patient_phone,
            patient_email=request.patient_email,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            doctor_id=doctor.doctor_id,
            doctor_name=f"Dr. {doctor.name}",
            reason=request.reason,
            duration_minutes=doctor.consultation_duration
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating appointment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/appointments/{appointment_id}", response_model=Appointment)
async def get_appointment(appointment_id: str):
    """Get appointment by ID."""
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
    """List appointments with optional filters."""
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
    """Update appointment status."""
    result = appointment_service.update_appointment_status(appointment_id, status)
    
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error)
    
    return result


@router.delete("/appointments/{appointment_id}", response_model=AppointmentResponse)
async def cancel_appointment(appointment_id: str):
    """Cancel an appointment."""
    result = appointment_service.cancel_appointment(appointment_id)
    
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error)
    
    return result

@router.get("/slots/available")
async def get_available_slots(
    doctor_id: Optional[str] = Query(None),
    doctor_name: Optional[str] = Query(None),
    specialization: Optional[Specialization] = Query(None),
    start_date: Optional[date] = Query(None),
    num_days: int = Query(7, ge=1, le=30),
    preferred_time: Optional[str] = Query(None)
):
    """Get available appointment slots."""
    start = start_date or date.today()
    all_slots = []
    
    # Determine which doctors to check
    doctors = []
    
    if doctor_id:
        doctor = await doctor_service.get_doctor_by_id(doctor_id)
        if doctor:
            doctors = [doctor]
    elif doctor_name:
        doctor = await doctor_service.get_doctor_by_name(doctor_name)
        if doctor:
            doctors = [doctor]
    elif specialization:
        doctors = await doctor_service.get_doctors_by_specialization(specialization)
    else:
        doctors = await doctor_service.get_all_doctors()
    
    # Get slots for each doctor
    for doctor in doctors:
        if preferred_time:
            slots =  appointment_service.find_slots_by_preference(
                doctor_id=doctor.doctor_id,
                doctor_name=f"Dr. {doctor.name}",
                preferred_date=start,
                preferred_time=preferred_time,
                num_slots=num_days * 3
            )
        else:
            slots = appointment_service.get_available_slots(
                doctor_id=doctor.doctor_id,
                doctor_name=f"Dr. {doctor.name}",
                start_date=start,
                num_days=num_days
            )
        
        all_slots.extend(slots)
    
    # Fetch all appointments once (outside the loop)
    try:
        all_appointments = appointment_service.get_all_appointments() or []
    except Exception as e:
        logger.error(f"Error fetching appointments: {e}")
        all_appointments = []
    
    # Create a set of booked slots for efficient lookup
    booked_slots = {
        (apt.doctor_id, apt.appointment_date, apt.appointment_time)
        for apt in all_appointments
        if apt.status in [AppointmentStatus.CONFIRMED, AppointmentStatus.COMPLETED]
    }
    
    # Filter out booked slots from all collected slots
    available_slots = [
        slot for slot in all_slots
        if (slot.doctor_id, slot.date, slot.start_time) not in booked_slots
    ]
    
    # Return formatted response
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
        for slot in available_slots
    ]


@router.get("/doctors", response_model=List[Doctor])
async def list_doctors(
    specialization: Optional[Specialization] = Query(None),
    active_only: bool = Query(True)
):
    """List all doctors."""
    if specialization:
        doctors = await doctor_service.get_doctors_by_specialization(specialization)
    else:
        doctors = await doctor_service.get_all_doctors(active_only)
    
    return doctors


@router.get("/doctors/{doctor_id}", response_model=Doctor)
async def get_doctor(doctor_id: str):
    """Get doctor by ID."""
    doctor = await doctor_service.get_doctor_by_id(doctor_id)
    
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    return doctor


@router.get("/doctors/search/{query}")
async def search_doctors(query: str):
    """Search doctors."""
    doctors = await doctor_service.search_doctors(query)
    return doctors


@router.get("/doctors/{doctor_id}/slots")
async def get_doctor_slots(
    doctor_id: str,
    start_date: Optional[date] = Query(None),
    num_days: int = Query(7, ge=1, le=30),
    preferred_time: Optional[str] = Query(None)
):
    """Get available slots for a specific doctor."""
    doctor = await doctor_service.get_doctor_by_id(doctor_id)
    
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    start = start_date or date.today()
    
    if preferred_time:
        slots = appointment_service.find_slots_by_preference(
            doctor_id=doctor.doctor_id,
            doctor_name=f"Dr. {doctor.name}",
            preferred_date=start,
            preferred_time=preferred_time,
            num_slots=num_days * 3
        )
    else:
        slots = appointment_service.get_available_slots(
            doctor_id=doctor.doctor_id,
            doctor_name=f"Dr. {doctor.name}",
            start_date=start,
            num_days=num_days
        )
    
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


@router.post("/conversations")
async def create_conversation():
    """Create a new conversation."""
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
    """Get conversation context."""
    context = conversations.get(conversation_id)
    
    if not context:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return context


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    if conversation_id in conversations:
        del conversations[conversation_id]
        return {"message": "Conversation deleted", "conversation_id": conversation_id}
    
    raise HTTPException(status_code=404, detail="Conversation not found")