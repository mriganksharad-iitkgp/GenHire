from dataclasses import dataclass
from typing import Optional, Dict, Any
import datetime

@dataclass
class Application:
    job_id: str
    student_id: str
    student_name: str
    student_email: str
    cover_letter: str
    status: str  # 'pending', 'reviewed', 'shortlisted', 'interviewed', 'selected', 'rejected'
    job_title: str
    recruiter_id: str
    cv_score: Optional[float] = 85.0
    interview_score: Optional[float] = None
    proctoring_score: Optional[float] = None
    student_profile: Optional[Dict[str, Any]] = None
    applied_at: datetime.datetime = None
    updated_at: datetime.datetime = None
    updated_by: Optional[str] = None
    
    def __post_init__(self):
        if self.applied_at is None:
            self.applied_at = datetime.datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.datetime.utcnow()
        if self.student_profile is None:
            self.student_profile = {}
    
    def to_dict(self):
        """Convert application object to dictionary for MongoDB storage"""
        return {
            'job_id': self.job_id,
            'student_id': self.student_id,
            'student_name': self.student_name,
            'student_email': self.student_email,
            'cover_letter': self.cover_letter,
            'status': self.status,
            'job_title': self.job_title,
            'recruiter_id': self.recruiter_id,
            'cv_score': self.cv_score,
            'interview_score': self.interview_score,
            'proctoring_score': self.proctoring_score,
            'student_profile': self.student_profile,
            'applied_at': self.applied_at,
            'updated_at': self.updated_at,
            'updated_by': self.updated_by
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create Application object from dictionary"""
        return cls(
            job_id=data.get('job_id', ''),
            student_id=data.get('student_id', ''),
            student_name=data.get('student_name', ''),
            student_email=data.get('student_email', ''),
            cover_letter=data.get('cover_letter', ''),
            status=data.get('status', 'pending'),
            job_title=data.get('job_title', ''),
            recruiter_id=data.get('recruiter_id', ''),
            cv_score=data.get('cv_score', 85.0),
            interview_score=data.get('interview_score'),
            proctoring_score=data.get('proctoring_score'),
            student_profile=data.get('student_profile', {}),
            applied_at=data.get('applied_at'),
            updated_at=data.get('updated_at'),
            updated_by=data.get('updated_by')
        )
