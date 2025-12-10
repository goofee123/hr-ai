"""ARQ Worker Entry Point.

Run with: arq workers.worker.WorkerSettings

This starts the background worker process that handles:
- Resume parsing (LLM extraction)
- Embedding generation (OpenAI)
- SLA alert checks (scheduled)
- Email notifications
"""

import logging
from datetime import datetime, timezone

from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings
from workers.tasks.sla_alerts import check_sla_alerts
from workers.tasks.resume_parsing import parse_resume, parse_cover_letter
from workers.tasks.embedding_generation import (
    generate_embeddings,
    calculate_match_scores,
    batch_generate_embeddings,
)
from workers.tasks.notifications import (
    send_interview_notification,
    send_offer_notification,
    send_status_update_notification,
    send_sla_alert_notification,
    send_scorecard_reminder_notification,
    send_mention_notification,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


def get_redis_settings() -> RedisSettings:
    """Get Redis connection settings from config."""
    redis_url = settings.redis_url
    if redis_url.startswith("redis://"):
        redis_url = redis_url[8:]

    host_port = redis_url.split(":")
    host = host_port[0] if host_port else "localhost"
    port = int(host_port[1]) if len(host_port) > 1 else 6379

    return RedisSettings(host=host, port=port)


async def startup(ctx):
    """Worker startup - initialize connections and log start."""
    logger.info("=" * 50)
    logger.info("ARQ Worker Starting")
    logger.info(f"Started at: {datetime.now(timezone.utc).isoformat()}")
    logger.info(f"Redis: {settings.redis_url}")
    logger.info("=" * 50)


async def shutdown(ctx):
    """Worker shutdown - cleanup connections."""
    logger.info("ARQ Worker Shutting Down")
    logger.info(f"Stopped at: {datetime.now(timezone.utc).isoformat()}")


class WorkerSettings:
    """ARQ Worker Settings.

    Available tasks:
    - parse_resume: Parse resume using LLM extraction
    - parse_cover_letter: Parse cover letter using LLM
    - generate_embeddings: Generate vector embeddings for candidate/job
    - calculate_match_scores: Calculate candidate-job match scores
    - batch_generate_embeddings: Batch process embeddings
    - check_sla_alerts: Check all SLAs and generate alerts
    - send_interview_notification: Send interview-related emails
    - send_offer_notification: Send offer-related emails
    - send_status_update_notification: Send application status updates
    - send_sla_alert_notification: Send SLA alerts to recruiters
    - send_scorecard_reminder_notification: Remind interviewers to submit scorecards
    - send_mention_notification: Send @mention notifications
    """

    # Redis connection settings
    redis_settings = get_redis_settings()

    # All available task functions
    functions = [
        # Resume & Document Processing
        parse_resume,
        parse_cover_letter,

        # Embeddings & Matching
        generate_embeddings,
        calculate_match_scores,
        batch_generate_embeddings,

        # SLA Monitoring
        check_sla_alerts,

        # Notifications
        send_interview_notification,
        send_offer_notification,
        send_status_update_notification,
        send_sla_alert_notification,
        send_scorecard_reminder_notification,
        send_mention_notification,
    ]

    # Scheduled cron jobs
    cron_jobs = [
        # Check SLAs every hour at minute 0
        cron(check_sla_alerts, hour=None, minute=0),
    ]

    # Lifecycle hooks
    on_startup = startup
    on_shutdown = shutdown

    # Worker configuration
    max_jobs = 10  # Max concurrent jobs
    job_timeout = 300  # 5 minutes per job
    keep_result = 3600  # Keep results for 1 hour
    poll_delay = 0.5  # Poll Redis every 0.5 seconds
    queue_read_limit = 30  # Read up to 30 jobs at once


# For running with: python -m workers.worker
if __name__ == "__main__":
    import asyncio
    from arq import run_worker

    print("Starting ARQ Worker...")
    print(f"Redis: {settings.redis_url}")
    print("Press Ctrl+C to stop")

    asyncio.run(run_worker(WorkerSettings))
