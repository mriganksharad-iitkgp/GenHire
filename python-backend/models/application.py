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
    cv_score_breakdown: Optional[Dict[str, Any]] = None
    interview_score: Optional[float] = None
    proctoring_score: Optional[float] = None
    student_profile: Optional[Dict[str, Any]] = None
    applied_at: datetime.datetime = None
    updated_at: datetime.datetime = None
    updated_by: Optional[str] = None
    # NEW: CV PDF support
    cv_id: Optional[str] = None  # Reference to specific CV used from cv_uploads
    cv_snapshot: Optional[Dict[str, Any]] = None  # Snapshot of CV at application time
    jd_snapshot: Optional[str] = None  # JD text snapshot at application time
    # NEW: Background processing support
    processing_status: str = 'pending'  # 'pending', 'processing', 'completed', 'failed'
    is_visible: bool = False  # Only show to users when True (after CV score calculated)
    cv_score_calculated_at: Optional[datetime.datetime] = None  # When CV scoring completed
    processing_error: Optional[str] = None  # Error message if processing failed
    
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
            'cv_score_breakdown': self.cv_score_breakdown,
            'interview_score': self.interview_score,
            'proctoring_score': self.proctoring_score,
            'student_profile': self.student_profile,
            'applied_at': self.applied_at,
            'updated_at': self.updated_at,
            'updated_by': self.updated_by,
            'cv_id': self.cv_id,
            'cv_snapshot': self.cv_snapshot,
            'jd_snapshot': self.jd_snapshot,
            'processing_status': self.processing_status,
            'is_visible': self.is_visible,
            'cv_score_calculated_at': self.cv_score_calculated_at,
            'processing_error': self.processing_error
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
            cv_score_breakdown=data.get('cv_score_breakdown'),
            interview_score=data.get('interview_score'),
            proctoring_score=data.get('proctoring_score'),
            student_profile=data.get('student_profile', {}),
            applied_at=data.get('applied_at'),
            updated_at=data.get('updated_at'),
            updated_by=data.get('updated_by'),
            cv_id=data.get('cv_id'),
            cv_snapshot=data.get('cv_snapshot'),
            jd_snapshot=data.get('jd_snapshot'),
            processing_status=data.get('processing_status', 'pending'),
            is_visible=data.get('is_visible', False),
            cv_score_calculated_at=data.get('cv_score_calculated_at'),
            processing_error=data.get('processing_error')
        )
