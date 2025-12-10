"""Shared services module."""

from app.services.email_service import EmailService, get_email_service
from app.services.job_queue import JobQueue, job_queue

__all__ = ["EmailService", "get_email_service", "JobQueue", "job_queue"]
