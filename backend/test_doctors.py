from app.services.doctor_service import doctor_service
from app.services.appointment_service import appointment_service
from app.models.doctor import Specialization
from datetime import date, time

print("\n=== Testing Doctor Service ===\n")

# Test 1: Get all doctors
doctors = doctor_service.get_all_doctors()
print(f"✓ Total doctors: {len(doctors)}")
for doctor in doctors:
    print(f"  - {doctor}")

# Test 2: Search by specialization
print("\n✓ Cardiologists:")
cardiologists = doctor_service.get_doctors_by_specialization(Specialization.CARDIOLOGIST)
for doc in cardiologists:
    print(f"  - {doc.name} ({doc.experience_years} years exp)")

# Test 3: Search doctors
print("\n✓ Search for 'Rajesh':")
results = doctor_service.search_doctors("Rajesh")
for doc in results:
    print(f"  - {doc.name} - {doc.specialization}")

# Test 4: Get available slots for a doctor
print("\n✓ Available slots for Dr. Rajesh Kumar:")
doctor = doctor_service.get_doctor_by_name("Rajesh")
if doctor:
    slots = appointment_service.get_available_slots(doctor, date.today(), num_days=3)
    print(f"  Found {len(slots)} slots")
    for slot in slots[:3]:
        print(f"  - {slot}")

# Test 5: Create appointment with specific doctor
print("\n✓ Creating appointment with Dr. Priya Sharma:")
doctor = doctor_service.get_doctor_by_name("Priya")
if doctor:
    result = appointment_service.create_appointment(
        patient_name="Test Patient",
        patient_phone="9999999999",
        appointment_date=date.today(),
        appointment_time=time(10, 0),
        doctor=doctor,
        reason="Heart checkup"
    )
    if result.success:
        print(f"  ✓ Appointment created: {result.appointment.to_readable_string()}")
    else:
        print(f"  ✗ Failed: {result.message}")

print("\n✓ All doctor tests completed!\n")