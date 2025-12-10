"""Job Queue Service - Helper to enqueue background jobs from the API."""

import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from arq import create_pool
from arq.connections import RedisSettings, ArqRedis

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Global connection pool
_redis_pool: Optional[ArqRedis] = None


def get_redis_settings() -> RedisSettings:
    """Get Redis connection settings from config."""
    redis_url = settings.redis_url
    if redis_url.startswith("redis://"):
        redis_url = redis_url[8:]

    host_port = redis_url.split(":")
    host = host_port[0] if host_port else "localhost"
    port = int(host_port[1]) if len(host_port) > 1 else 6379

    return RedisSettings(host=host, port=port)


async def get_redis_pool() -> ArqRedis:
    """Get or create the Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = await create_pool(get_redis_settings())
    return _redis_pool


async def close_redis_pool():
    """Close the Redis connection pool."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None


class JobQueue:
    """Service for enqueuing background jobs."""

    @staticmethod
    async def enqueue_resume_parsing(
        resume_id: str,
        tenant_id: str,
        delay: Optional[timedelta] = None,
    ) -> Optional[str]:
        """
        Enqueue a resume parsing job.

        Args:
            resume_id: UUID of the resume
            tenant_id: UUID of the tenant
            delay: Optional delay before processing

        Returns:
            Job ID if enqueued successfully, None otherwise
        """
        try:
            pool = await get_redis_pool()
            job = await pool.enqueue_job(
                "parse_resume",
                resume_id,
                tenant_id,
                _defer_by=delay,
            )
            logger.info(f"Enqueued resume parsing job: {job.job_id}")
            return job.job_id
        except Exception as e:
            logger.error(f"Failed to enqueue resume parsing: {str(e)}")
            return None

    @staticmethod
    async def enqueue_cover_letter_parsing(
        application_id: str,
        cover_letter_text: str,
        tenant_id: str,
    ) -> Optional[str]:
        """Enqueue a cover letter parsing job."""
        try:
            pool = await get_redis_pool()
            job = await pool.enqueue_job(
                "parse_cover_letter",
                application_id,
                cover_letter_text,
                tenant_id,
            )
            logger.info(f"Enqueued cover letter parsing job: {job.job_id}")
            return job.job_id
        except Exception as e:
            logger.error(f"Failed to enqueue cover letter parsing: {str(e)}")
            return None

    @staticmethod
    async def enqueue_embedding_generation(
        entity_type: str,  # 'candidate' or 'job'
        entity_id: str,
        tenant_id: str,
        delay: Optional[timedelta] = None,
    ) -> Optional[str]:
        """
        Enqueue an embedding generation job.

        Args:
            entity_type: 'candidate' or 'job'
            entity_id: UUID of the entity
            tenant_id: UUID of the tenant
            delay: Optional delay before processing

        Returns:
            Job ID if enqueued successfully, None otherwise
        """
        try:
            pool = await get_redis_pool()
            job = await pool.enqueue_job(
                "generate_embeddings",
                entity_type,
                entity_id,
                tenant_id,
                _defer_by=delay,
            )
            logger.info(f"Enqueued embedding generation job: {job.job_id}")
            return job.job_id
        except Exception as e:
            logger.error(f"Failed to enqueue embedding generation: {str(e)}")
            return None

    @staticmethod
    async def enqueue_match_calculation(
        job_id: str,
        tenant_id: str,
        candidate_ids: Optional[list] = None,
    ) -> Optional[str]:
        """Enqueue a match score calculation job."""
        try:
            pool = await get_redis_pool()
            job = await pool.enqueue_job(
                "calculate_match_scores",
                job_id,
                tenant_id,
                candidate_ids,
            )
            logger.info(f"Enqueued match calculation job: {job.job_id}")
            return job.job_id
        except Exception as e:
            logger.error(f"Failed to enqueue match calculation: {str(e)}")
            return None

    @staticmethod
    async def enqueue_interview_notification(
        interview_id: str,
        tenant_id: str,
        notification_type: str = "scheduled",
        delay: Optional[timedelta] = None,
    ) -> Optional[str]:
        """
        Enqueue an interview notification job.

        Args:
            interview_id: UUID of the interview
            tenant_id: UUID of the tenant
            notification_type: 'scheduled', 'reminder', or 'cancelled'
            delay: Optional delay (useful for reminders)

        Returns:
            Job ID if enqueued successfully
        """
        try:
            pool = await get_redis_pool()
            job = await pool.enqueue_job(
                "send_interview_notification",
                interview_id,
                tenant_id,
                notification_type,
                _defer_by=delay,
            )
            logger.info(f"Enqueued interview notification job: {job.job_id}")
            return job.job_id
        except Exception as e:
            logger.error(f"Failed to enqueue interview notification: {str(e)}")
            return None

    @staticmethod
    async def enqueue_offer_notification(
        offer_id: str,
        tenant_id: str,
        notification_type: str = "extended",
    ) -> Optional[str]:
        """Enqueue an offer notification job."""
        try:
            pool = await get_redis_pool()
            job = await pool.enqueue_job(
                "send_offer_notification",
                offer_id,
                tenant_id,
                notification_type,
            )
            logger.info(f"Enqueued offer notification job: {job.job_id}")
            return job.job_id
        except Exception as e:
            logger.error(f"Failed to enqueue offer notification: {str(e)}")
            return None

    @staticmethod
    async def enqueue_status_update_notification(
        application_id: str,
        tenant_id: str,
        new_status: str,
        custom_message: Optional[str] = None,
    ) -> Optional[str]:
        """Enqueue an application status update notification."""
        try:
            pool = await get_redis_pool()
            job = await pool.enqueue_job(
                "send_status_update_notification",
                application_id,
                tenant_id,
                new_status,
                custom_message,
            )
            logger.info(f"Enqueued status update notification job: {job.job_id}")
            return job.job_id
        except Exception as e:
            logger.error(f"Failed to enqueue status update notification: {str(e)}")
            return None

    @staticmethod
    async def enqueue_sla_alert_notification(
        alert_id: str,
        tenant_id: str,
    ) -> Optional[str]:
        """Enqueue an SLA alert notification."""
        try:
            pool = await get_redis_pool()
            job = await pool.enqueue_job(
                "send_sla_alert_notification",
                alert_id,
                tenant_id,
            )
            logger.info(f"Enqueued SLA alert notification job: {job.job_id}")
            return job.job_id
        except Exception as e:
            logger.error(f"Failed to enqueue SLA alert notification: {str(e)}")
            return None

    @staticmethod
    async def enqueue_scorecard_reminder(
        interview_id: str,
        tenant_id: str,
        delay: Optional[timedelta] = None,
    ) -> Optional[str]:
        """Enqueue a scorecard reminder notification."""
        try:
            pool = await get_redis_pool()
            job = await pool.enqueue_job(
                "send_scorecard_reminder_notification",
                interview_id,
                tenant_id,
                _defer_by=delay,
            )
            logger.info(f"Enqueued scorecard reminder job: {job.job_id}")
            return job.job_id
        except Exception as e:
            logger.error(f"Failed to enqueue scorecard reminder: {str(e)}")
            return None

    @staticmethod
    async def enqueue_mention_notification(
        comment_id: str,
        mentioned_user_id: str,
        tenant_id: str,
    ) -> Optional[str]:
        """Enqueue a mention notification."""
        try:
            pool = await get_redis_pool()
            job = await pool.enqueue_job(
                "send_mention_notification",
                comment_id,
                mentioned_user_id,
                tenant_id,
            )
            logger.info(f"Enqueued mention notification job: {job.job_id}")
            return job.job_id
        except Exception as e:
            logger.error(f"Failed to enqueue mention notification: {str(e)}")
            return None

    @staticmethod
    async def enqueue_sla_check() -> Optional[str]:
        """Manually trigger an SLA check (normally runs on cron)."""
        try:
            pool = await get_redis_pool()
            job = await pool.enqueue_job("check_sla_alerts")
            logger.info(f"Enqueued SLA check job: {job.job_id}")
            return job.job_id
        except Exception as e:
            logger.error(f"Failed to enqueue SLA check: {str(e)}")
            return None

    @staticmethod
    async def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a job."""
        try:
            pool = await get_redis_pool()
            job = await pool.job(job_id)
            if job:
                return {
                    "job_id": job_id,
                    "status": job.status,
                    "result": job.result,
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            return None


# Singleton instance
job_queue = JobQueue()
