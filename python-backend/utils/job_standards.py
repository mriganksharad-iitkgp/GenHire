import re

STANDARD_JOB_ROLES = [
    "Software Engineer",
    "Software Developer",
    "Full Stack Developer",
    "Frontend Developer",
    "Backend Developer",
    "DevOps Engineer",
    "Data Scientist",
    "Data Analyst",
    "Machine Learning Engineer",
    "Product Manager",
    "Business Analyst",
    "UI/UX Designer",
    "Finance Analyst",
]

INDIA_LOCATION_OPTIONS = [
    "Remote (India)",
    "Bangalore, Karnataka",
    "Mumbai, Maharashtra",
    "Delhi, NCR",
    "Hyderabad, Telangana",
    "Chennai, Tamil Nadu",
    "Pune, Maharashtra",
    "Kolkata, West Bengal",
    "Ahmedabad, Gujarat",
    "Gurgaon, Haryana",
    "Noida, Uttar Pradesh",
    "Kochi, Kerala",
    "Indore, Madhya Pradesh",
    "Jaipur, Rajasthan",
    "Lucknow, Uttar Pradesh",
    "Bhubaneswar, Odisha",
    "Coimbatore, Tamil Nadu",
    "Chandigarh, Punjab",
    "Thiruvananthapuram, Kerala",
    "Nagpur, Maharashtra",
    "Surat, Gujarat",
    "Visakhapatnam, Andhra Pradesh",
    "Hybrid - Bangalore, Karnataka",
    "Hybrid - Mumbai, Maharashtra",
    "Hybrid - Delhi, NCR",
    "Hybrid - Hyderabad, Telangana",
    "Hybrid - Pune, Maharashtra",
    "Hybrid - Chennai, Tamil Nadu",
]

_ROLE_NORMALIZATION_RULES = [
    (re.compile(r"(data\s*scientist|ml\s*scientist)", re.I), "Data Scientist"),
    (re.compile(r"(data\s*analyst|analytics\s*analyst|bi\s*analyst)", re.I), "Data Analyst"),
    (re.compile(r"(machine\s*learning\s*engineer|ml\s*engineer|ai\s*engineer)", re.I), "Machine Learning Engineer"),
    (re.compile(r"(software\s*engineer|\bswe\b)", re.I), "Software Engineer"),
    (re.compile(r"(software\s*developer|\bsde\b)", re.I), "Software Developer"),
    (re.compile(r"(full\s*stack|fullstack)", re.I), "Full Stack Developer"),
    (re.compile(r"(front\s*end|frontend)", re.I), "Frontend Developer"),
    (re.compile(r"(back\s*end|backend)", re.I), "Backend Developer"),
    (re.compile(r"devops", re.I), "DevOps Engineer"),
    (re.compile(r"(product\s*manager|\bpm\b)", re.I), "Product Manager"),
    (re.compile(r"(business\s*analyst|\bba\b)", re.I), "Business Analyst"),
    (re.compile(r"(ui\/?ux|ux\s*designer|ui\s*designer|product\s*designer)", re.I), "UI/UX Designer"),
    (re.compile(r"(finance\s*analyst|financial\s*analyst)", re.I), "Finance Analyst"),
]

def canonicalize_job_role(title):
    value = str(title or "").strip()
    if not value:
        return ""

    for regex, canonical in _ROLE_NORMALIZATION_RULES:
        if regex.search(value):
            return canonical

    normalized = re.sub(r"[_-]+", " ", value)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.title()


def is_india_location(location):
    return str(location or "").strip() in INDIA_LOCATION_OPTIONS
