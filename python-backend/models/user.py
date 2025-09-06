from dataclasses import dataclass
from typing import Optional, List
import datetime

@dataclass
class User:
    name: str
    email: str
    user_type: str  # 'candidate' or 'recruiter'
    phone: Optional[str] = None
    location: Optional[str] = None
    title: Optional[str] = None
    about: Optional[str] = None
    skills: List[str] = None
    cv_path: Optional[str] = None
    cv_details: Optional[dict] = None
    profile_photo: Optional[str] = None
    created_at: datetime.datetime = None
    updated_at: datetime.datetime = None
    
    # Recruiter-specific fields
    company_name: Optional[str] = None
    company_logo: Optional[str] = None
    company_description: Optional[str] = None
    company_website: Optional[str] = None
    company_size: Optional[str] = None
    company_industry: Optional[str] = None
    
    def __post_init__(self):
        if self.skills is None:
            self.skills = []
        if self.created_at is None:
            self.created_at = datetime.datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.datetime.utcnow()
    
    def to_dict(self):
        """Convert user object to dictionary for MongoDB storage"""
        return {
            'name': self.name,
            'email': self.email,
            'user_type': self.user_type,
            'phone': self.phone,
            'location': self.location,
            'title': self.title,
            'about': self.about,
            'skills': self.skills,
            'cv_path': self.cv_path,
            'cv_details': self.cv_details,
            'profile_photo': self.profile_photo,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'company_name': self.company_name,
            'company_logo': self.company_logo,
            'company_description': self.company_description,
            'company_website': self.company_website,
            'company_size': self.company_size,
            'company_industry': self.company_industry
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create User object from dictionary"""
        return cls(
            name=data.get('name', ''),
            email=data.get('email', ''),
            user_type=data.get('user_type', 'candidate'),
            phone=data.get('phone'),
            location=data.get('location'),
            title=data.get('title'),
            about=data.get('about'),
            skills=data.get('skills', []),
            cv_path=data.get('cv_path'),
            cv_details=data.get('cv_details'),
            profile_photo=data.get('profile_photo'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            company_name=data.get('company_name'),
            company_logo=data.get('company_logo'),
            company_description=data.get('company_description'),
            company_website=data.get('company_website'),
            company_size=data.get('company_size'),
            company_industry=data.get('company_industry')
        )
