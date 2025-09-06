from dataclasses import dataclass
from typing import List, Optional
import datetime

@dataclass
class Job:
    title: str
    department: str
    location: str
    type: str  # 'Full-time', 'Part-time', 'Contract'
    experience: str
    salary: str
    description: str
    skills: List[str]
    responsibilities: List[str]
    requirements: List[str]
    benefits: List[str]
    status: str  # 'draft', 'active', 'paused', 'closed'
    created_by: str  # recruiter user_id
    company: Optional[str] = None
    logo: Optional[str] = None
    deadline: Optional[datetime.datetime] = None
    applicants: int = 0
    interviewed: int = 0
    selected: int = 0
    rejected: int = 0
    pending: int = 0
    created_at: datetime.datetime = None
    updated_at: datetime.datetime = None
    
    def __post_init__(self):
        if self.skills is None:
            self.skills = []
        if self.responsibilities is None:
            self.responsibilities = []
        if self.requirements is None:
            self.requirements = []
        if self.benefits is None:
            self.benefits = []
        if self.created_at is None:
            self.created_at = datetime.datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.datetime.utcnow()
    
    def to_dict(self):
        """Convert job object to dictionary for MongoDB storage"""
        return {
            'title': self.title,
            'department': self.department,
            'location': self.location,
            'type': self.type,
            'experience': self.experience,
            'salary': self.salary,
            'description': self.description,
            'skills': self.skills,
            'responsibilities': self.responsibilities,
            'requirements': self.requirements,
            'benefits': self.benefits,
            'status': self.status,
            'created_by': self.created_by,
            'company': self.company,
            'logo': self.logo,
            'deadline': self.deadline,
            'applicants': self.applicants,
            'interviewed': self.interviewed,
            'selected': self.selected,
            'rejected': self.rejected,
            'pending': self.pending,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create Job object from dictionary"""
        return cls(
            title=data.get('title', ''),
            department=data.get('department', ''),
            location=data.get('location', ''),
            type=data.get('type', ''),
            experience=data.get('experience', ''),
            salary=data.get('salary', ''),
            description=data.get('description', ''),
            skills=data.get('skills', []),
            responsibilities=data.get('responsibilities', []),
            requirements=data.get('requirements', []),
            benefits=data.get('benefits', []),
            status=data.get('status', 'draft'),
            created_by=data.get('created_by', ''),
            company=data.get('company'),
            logo=data.get('logo'),
            deadline=data.get('deadline'),
            applicants=data.get('applicants', 0),
            interviewed=data.get('interviewed', 0),
            selected=data.get('selected', 0),
            rejected=data.get('rejected', 0),
            pending=data.get('pending', 0),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
