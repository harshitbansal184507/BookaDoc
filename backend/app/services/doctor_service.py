from typing import List, Optional, Dict
from app.models.doctor import Doctor, Specialization, DoctorResponse
from app.utils.logger import app_logger as logger


class DoctorService:
    """Service for managing doctors."""
    
    def __init__(self):
        """Initialize doctor service with predefined doctors."""
        self.doctors: Dict[str, Doctor] = {}
        self._initialize_doctors()
        logger.info(f"Doctor Service initialized with {len(self.doctors)} doctors")
    
    def _initialize_doctors(self):
        """Initialize with sample doctors."""
        sample_doctors = [
            Doctor(
                name="Rajesh Kumar",
                specialization=Specialization.GENERAL_PHYSICIAN,
                qualification="MBBS, MD",
                experience_years=15,
                email="dr.rajesh@bookadoc.com",
                phone="9876543210",
                available_days=[0, 1, 2, 3, 4], 
                bio="Experienced general physician with 15+ years of practice",
                languages=["English", "Hindi", "Punjabi"]
            ),
            Doctor(
                name="Priya Sharma",
                specialization=Specialization.CARDIOLOGIST,
                qualification="MBBS, MD (Cardiology)",
                experience_years=12,
                email="dr.priya@bookadoc.com",
                phone="9876543211",
                available_days=[0, 2, 4],  
                consultation_duration=45,
                bio="Specialist in heart diseases and preventive cardiology",
                languages=["English", "Hindi"]
            ),
            Doctor(
                name="Amit Verma",
                specialization=Specialization.DERMATOLOGIST,
                qualification="MBBS, MD (Dermatology)",
                experience_years=8,
                email="dr.amit@bookadoc.com",
                phone="9876543212",
                available_days=[1, 2, 3, 4, 5],  # Tue-Sat
                bio="Expert in skin care and cosmetic dermatology",
                languages=["English", "Hindi"]
            ),
            Doctor(
                name="Neha Gupta",
                specialization=Specialization.PEDIATRICIAN,
                qualification="MBBS, MD (Pediatrics)",
                experience_years=10,
                email="dr.neha@bookadoc.com",
                phone="9876543213",
                available_days=[0, 1, 2, 3, 4],  
                bio="Caring for children's health with expertise and compassion",
                languages=["English", "Hindi", "Punjabi"]
            ),
            Doctor(
                name="Sandeep Singh",
                specialization=Specialization.ORTHOPEDIC,
                qualification="MBBS, MS (Orthopedics)",
                experience_years=18,
                email="dr.sandeep@bookadoc.com",
                phone="9876543214",
                available_days=[0, 1, 3, 4],  
                consultation_duration=40,
                bio="Specialist in bone and joint disorders",
                languages=["English", "Hindi", "Punjabi"]
            )
        ]
        
        for doctor in sample_doctors:
            self.doctors[doctor.doctor_id] = doctor
    
    def get_all_doctors(self, active_only: bool = True) -> List[Doctor]:
        """
        Get all doctors.
        
        Args:
            active_only: Return only active doctors
            
        Returns:
            List of doctors
        """
        doctors = list(self.doctors.values())
        
        if active_only:
            doctors = [d for d in doctors if d.is_active]
        
        return doctors
    
    def get_doctor_by_id(self, doctor_id: str) -> Optional[Doctor]:
        """Get doctor by ID."""
        return self.doctors.get(doctor_id)
    
    def get_doctor_by_name(self, name: str) -> Optional[Doctor]:
        """
        Get doctor by name (case-insensitive partial match).
        
        Args:
            name: Doctor's name or partial name
            
        Returns:
            Doctor if found, None otherwise
        """
        name_lower = name.lower()
        
        for doctor in self.doctors.values():
            if name_lower in doctor.name.lower():
                return doctor
        
        return None
    
    def get_doctors_by_specialization(
        self,
        specialization: Specialization
    ) -> List[Doctor]:
        """
        Get doctors by specialization.
        
        Args:
            specialization: Medical specialization
            
        Returns:
            List of doctors with that specialization
        """
        return [
            doctor for doctor in self.doctors.values()
            if doctor.specialization == specialization and doctor.is_active
        ]
    
    def find_available_doctors(
        self,
        specialization: Optional[Specialization] = None,
        day_of_week: Optional[int] = None
    ) -> List[Doctor]:
        """
        Find available doctors with optional filters.
        
        Args:
            specialization: Filter by specialization
            day_of_week: Filter by day (0=Monday, 6=Sunday)
            
        Returns:
            List of available doctors
        """
        doctors = [d for d in self.doctors.values() if d.is_active]
        
        if specialization:
            doctors = [d for d in doctors if d.specialization == specialization]
        
        if day_of_week is not None:
            doctors = [d for d in doctors if d.is_available_on_day(day_of_week)]
        
        return doctors
    
    def add_doctor(self, doctor: Doctor) -> DoctorResponse:
        """
        Add a new doctor.
        
        Args:
            doctor: Doctor object
            
        Returns:
            DoctorResponse
        """
        if doctor.doctor_id in self.doctors:
            return DoctorResponse(
                success=False,
                message="Doctor already exists",
                error="Duplicate doctor ID"
            )
        
        self.doctors[doctor.doctor_id] = doctor
        logger.info(f"Added doctor: {doctor.name}")
        
        return DoctorResponse(
            success=True,
            message="Doctor added successfully",
            doctor=doctor
        )
    
    def update_doctor(self, doctor_id: str, updates: Dict) -> DoctorResponse:
        """
        Update doctor information.
        
        Args:
            doctor_id: Doctor ID
            updates: Dictionary of fields to update
            
        Returns:
            DoctorResponse
        """
        doctor = self.doctors.get(doctor_id)
        
        if not doctor:
            return DoctorResponse(
                success=False,
                message="Doctor not found",
                error="Invalid doctor ID"
            )
        
        # Update fields
        for key, value in updates.items():
            if hasattr(doctor, key):
                setattr(doctor, key, value)
        
        logger.info(f"Updated doctor: {doctor.name}")
        
        return DoctorResponse(
            success=True,
            message="Doctor updated successfully",
            doctor=doctor
        )
    
    def get_doctor_names(self) -> List[str]:
        """Get list of all doctor names."""
        return [f"Dr. {doctor.name}" for doctor in self.doctors.values() if doctor.is_active]
    
    def search_doctors(self, query: str) -> List[Doctor]:
        """
        Search doctors by name or specialization.
        
        Args:
            query: Search query
            
        Returns:
            List of matching doctors
        """
        query_lower = query.lower()
        results = []
        
        for doctor in self.doctors.values():
            if not doctor.is_active:
                continue
            
            # Search in name
            if query_lower in doctor.name.lower():
                results.append(doctor)
                continue
            
            # Search in specialization
            if query_lower in doctor.specialization.value.lower():
                results.append(doctor)
                continue
        
        return results


# Create singleton instance
doctor_service = DoctorService()