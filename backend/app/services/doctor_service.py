from typing import List, Optional, Dict
from app.models.doctor import Doctor, Specialization, DoctorResponse
from app.utils.logger import app_logger as logger
from app.db.mongodb import get_database


class DoctorService:
    """Service for managing doctors with MongoDB."""
    
    def __init__(self):
        """Initialize doctor service."""
        logger.info("Doctor Service initialized with MongoDB")
    
    def _get_collection(self):
        """Get doctors collection."""
        db = get_database()
        return db.doctors if db is not None else None
    
    async def initialize_doctors(self):
        """Initialize sample doctors in MongoDB if not exists."""
        collection = self._get_collection()
        if collection is None:
            logger.warning("MongoDB not connected, using in-memory doctors")
            return False
        
        # Check if doctors exist
        count = await collection.count_documents({})
        if count > 0:
            logger.info(f"Doctors already initialized: {count} doctors")
            return True
        
        # Sample doctors
        sample_doctors = [
            {
                "doctor_id": "doc-1",
                "name": "Rajesh Kumar",
                "specialization": Specialization.GENERAL_PHYSICIAN.value,
                "qualification": "MBBS, MD",
                "experience_years": 15,
                "email": "dr.rajesh@bookadoc.com",
                "phone": "9876543210",
                "consultation_duration": 30,
                "max_appointments_per_day": 16,
                "is_active": True,
                "is_accepting_new_patients": True,
                "bio": "Experienced general physician with 15+ years of practice",
                "languages": ["English", "Hindi", "Punjabi"]
            },
            {
                "doctor_id": "doc-2",
                "name": "Priya Sharma",
                "specialization": Specialization.CARDIOLOGIST.value,
                "qualification": "MBBS, MD (Cardiology)",
                "experience_years": 12,
                "email": "dr.priya@bookadoc.com",
                "phone": "9876543211",
                "consultation_duration": 45,
                "max_appointments_per_day": 12,
                "is_active": True,
                "is_accepting_new_patients": True,
                "bio": "Specialist in heart diseases and preventive cardiology",
                "languages": ["English", "Hindi"]
            },
            {
                "doctor_id": "doc-3",
                "name": "Amit Verma",
                "specialization": Specialization.DERMATOLOGIST.value,
                "qualification": "MBBS, MD (Dermatology)",
                "experience_years": 8,
                "email": "dr.amit@bookadoc.com",
                "phone": "9876543212",
                "consultation_duration": 30,
                "max_appointments_per_day": 16,
                "is_active": True,
                "is_accepting_new_patients": True,
                "bio": "Expert in skin care and cosmetic dermatology",
                "languages": ["English", "Hindi"]
            },
            {
                "doctor_id": "doc-4",
                "name": "Neha Gupta",
                "specialization": Specialization.PEDIATRICIAN.value,
                "qualification": "MBBS, MD (Pediatrics)",
                "experience_years": 10,
                "email": "dr.neha@bookadoc.com",
                "phone": "9876543213",
                "consultation_duration": 30,
                "max_appointments_per_day": 16,
                "is_active": True,
                "is_accepting_new_patients": True,
                "bio": "Caring for children's health with expertise and compassion",
                "languages": ["English", "Hindi", "Punjabi"]
            },
            {
                "doctor_id": "doc-5",
                "name": "Sandeep Singh",
                "specialization": Specialization.ORTHOPEDIC.value,
                "qualification": "MBBS, MS (Orthopedics)",
                "experience_years": 18,
                "email": "dr.sandeep@bookadoc.com",
                "phone": "9876543214",
                "consultation_duration": 40,
                "max_appointments_per_day": 14,
                "is_active": True,
                "is_accepting_new_patients": True,
                "bio": "Specialist in bone and joint disorders",
                "languages": ["English", "Hindi", "Punjabi"]
            }
        ]
        
        await collection.insert_many(sample_doctors)
        logger.info(f"Initialized {len(sample_doctors)} doctors in MongoDB")
        return True
    
    async def get_all_doctors(self, active_only: bool = True) -> List[Doctor]:
        """Get all doctors from MongoDB."""
        try:
            collection = self._get_collection()
            if collection is None:
                logger.warning("MongoDB not connected")
                return []
            
            query = {}
            if active_only:
                query["is_active"] = True
            
            cursor = collection.find(query)
            doctors = []
            
            async for doc in cursor:
                doctors.append(self._doc_to_model(doc))
            
            return doctors
            
        except Exception as e:
            logger.error(f"Error getting doctors: {e}")
            return []
    
    async def get_doctor_by_id(self, doctor_id: str) -> Optional[Doctor]:
        """Get doctor by ID from MongoDB."""
        try:
            collection = self._get_collection()
            if collection is None:
                logger.warning("MongoDB not connected")
                return None
            
            doc = await collection.find_one({"doctor_id": doctor_id})
            
            if doc:
                return self._doc_to_model(doc)
            return None
            
        except Exception as e:
            logger.error(f"Error getting doctor: {e}")
            return None
    
    async def get_doctor_by_name(self, name: str) -> Optional[Doctor]:
        """Get doctor by name from MongoDB."""
        try:
            collection = self._get_collection()
            if collection is None:
                logger.warning("MongoDB not connected")
                return None
            
            doc = await collection.find_one({
                "name": {"$regex": name, "$options": "i"},
                "is_active": True
            })
            
            if doc:
                return self._doc_to_model(doc)
            return None
        except Exception as e:
            logger.error(f"Error searching doctor: {e}")
            return None
    
    async def get_doctors_by_specialization(
        self,
        specialization: Specialization
    ) -> List[Doctor]:
        """Get doctors by specialization from MongoDB."""
        try:
            collection = self._get_collection()
            if collection is None:
                logger.warning("MongoDB not connected")
                return []
            
            cursor = collection.find({
                "specialization": specialization.value,
                "is_active": True
            })
            
            doctors = []
            async for doc in cursor:
                doctors.append(self._doc_to_model(doc))
            
            return doctors
            
        except Exception as e:
            logger.error(f"Error getting doctors by specialization: {e}")
            return []
    
    async def search_doctors(self, query: str) -> List[Doctor]:
        """Search doctors by name or specialization."""
        try:
            collection = self._get_collection()
            if collection is None:
                logger.warning("MongoDB not connected")
                return []
            
            cursor = collection.find({
                "$or": [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"specialization": {"$regex": query, "$options": "i"}}
                ],
                "is_active": True
            })
            
            doctors = []
            async for doc in cursor:
                doctors.append(self._doc_to_model(doc))
            
            return doctors
            
        except Exception as e:
            logger.error(f"Error searching doctors: {e}")
            return []
    
    def _doc_to_model(self, doc: Dict) -> Doctor:
        """Convert MongoDB document to Doctor model."""
        return Doctor(
            doctor_id=doc["doctor_id"],
            name=doc["name"],
            specialization=Specialization(doc["specialization"]),
            qualification=doc["qualification"],
            experience_years=doc["experience_years"],
            email=doc.get("email"),
            phone=doc.get("phone"),
            consultation_duration=doc.get("consultation_duration", 30),
            max_appointments_per_day=doc.get("max_appointments_per_day", 16),
            is_active=doc.get("is_active", True),
            is_accepting_new_patients=doc.get("is_accepting_new_patients", True),
            bio=doc.get("bio"),
            languages=doc.get("languages", ["English", "Hindi"]),
            available_days=[0, 1, 2, 3, 4]
        )


# Create singleton instance
doctor_service = DoctorService()