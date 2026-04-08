from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import datetime

# Valid user types
USER_TYPES = ['candidate', 'recruiter', 'admin']

# Available permissions for granular access control
AVAILABLE_PERMISSIONS = [
    'users.read',      # View user list
    'users.write',     # Edit user details
    'users.verify',    # Verify recruiters
    'users.delete',    # Delete users
    'jobs.read',       # View all jobs
    'jobs.write',      # Create/edit jobs
    'jobs.delete',     # Delete jobs
    'applications.read',   # View all applications
    'applications.write',  # Manage applications
    'stats.read',      # View platform statistics
    '*',               # Super admin (all permissions)
]

@dataclass
class User:
    name: str
    email: str
    user_type: str  # 'candidate', 'recruiter', or 'admin'
    phone: Optional[str] = None
    location: Optional[str] = None
    title: Optional[str] = None
    about: Optional[str] = None
    skills: List[str] = None
    cv_path: Optional[str] = None  # Legacy: single CV path (kept for backward compatibility)
    cv_details: Optional[dict] = None  # Manual CV entry (kept for backward compatibility)
    cv_uploads: List[Dict[str, Any]] = None  # NEW: Multiple CV PDFs with metadata
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
    
    # Verification fields (for recruiters)
    is_verified: bool = True  # Default True for candidates/admins, False for new recruiters
    verified_by: Optional[str] = None  # Admin user ID who verified
    verified_at: Optional[datetime.datetime] = None  # When verification occurred
    rejection_reason: Optional[str] = None  # If rejected, why
    
    # Permission system (for admins and managers)
    permissions: List[str] = None  # List of permission strings
    
    def __post_init__(self):
        if self.skills is None:
            self.skills = []
        if self.cv_uploads is None:
            self.cv_uploads = []
        if self.permissions is None:
            self.permissions = []
        if self.created_at is None:
            self.created_at = datetime.datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.datetime.utcnow()
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission"""
        if '*' in self.permissions:
            return True
        return permission in self.permissions
    
    def is_admin(self) -> bool:
        """Check if user is an admin"""
        return self.user_type == 'admin'
    
    def is_recruiter(self) -> bool:
        """Check if user is a recruiter"""
        return self.user_type == 'recruiter'
    
    def is_candidate(self) -> bool:
        """Check if user is a candidate"""
        return self.user_type == 'candidate'
    
    def can_post_jobs(self) -> bool:
        """Check if user can post jobs (verified recruiter or admin)"""
        if self.user_type == 'admin':
            return True
        if self.user_type == 'recruiter' and self.is_verified:
            return True
        return False
    
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
            'cv_uploads': self.cv_uploads,
            'profile_photo': self.profile_photo,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'company_name': self.company_name,
            'company_logo': self.company_logo,
            'company_description': self.company_description,
            'company_website': self.company_website,
            'company_size': self.company_size,
            'company_industry': self.company_industry,
            # Verification fields
            'is_verified': self.is_verified,
            'verified_by': self.verified_by,
            'verified_at': self.verified_at,
            'rejection_reason': self.rejection_reason,
            # Permission fields
            'permissions': self.permissions
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
            cv_uploads=data.get('cv_uploads', []),
            profile_photo=data.get('profile_photo'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            company_name=data.get('company_name'),
            company_logo=data.get('company_logo'),
            company_description=data.get('company_description'),
            company_website=data.get('company_website'),
            company_size=data.get('company_size'),
            company_industry=data.get('company_industry'),
            # Verification fields
            is_verified=data.get('is_verified', True),
            verified_by=data.get('verified_by'),
            verified_at=data.get('verified_at'),
            rejection_reason=data.get('rejection_reason'),
            # Permission fields
            permissions=data.get('permissions', [])
        )
