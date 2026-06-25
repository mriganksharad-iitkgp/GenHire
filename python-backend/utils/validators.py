"""
Input validation helpers for the GenHire application
"""
import re
from typing import List, Dict, Any

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password: str) -> Dict[str, Any]:
    """Validate password strength"""
    errors = []
    
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one digit")
    
    return {
        'is_valid': len(errors) == 0,
        'errors': errors
    }

def validate_user_type(user_type: str) -> bool:
    """Validate user type"""
    return user_type in ['candidate', 'recruiter']

def validate_job_status(status: str) -> bool:
    """Validate job status"""
    return status in ['draft', 'active', 'paused', 'closed']

def validate_application_status(status: str) -> bool:
    """Validate application status"""
    return status in ['pending', 'reviewed', 'shortlisted', 'interviewed', 'selected', 'rejected']

def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """Validate file extension"""
    if not filename or '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in allowed_extensions

def sanitize_string(input_str: str) -> str:
    """Basic string sanitization"""
    if not input_str:
        return ""
    return input_str.strip()

def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> Dict[str, Any]:
    """Validate that all required fields are present and not empty"""
    errors = []
    
    for field in required_fields:
        if field not in data or not data[field]:
            errors.append(f"{field} is required")
    
    return {
        'is_valid': len(errors) == 0,
        'errors': errors
    }
