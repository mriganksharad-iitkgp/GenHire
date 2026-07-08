"""Mongo data-access layer.

Repositories own query construction so controllers/services stay free of raw
pymongo calls. Adopted first by the auth controller and admin mixins; the
remaining raw call sites migrate opportunistically whenever their module is
next touched (see docs).
"""

from repositories.base_repository import BaseRepository
from repositories.user_repository import UserRepository
from repositories.recruiter_repository import RecruiterRepository
from repositories.job_repository import JobRepository
from repositories.application_repository import ApplicationRepository
from repositories.interview_repository import InterviewRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "RecruiterRepository",
    "JobRepository",
    "ApplicationRepository",
    "InterviewRepository",
]
