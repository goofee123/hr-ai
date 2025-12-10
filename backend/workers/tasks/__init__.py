"""Background task definitions for ARQ workers."""

from workers.tasks.sla_alerts import check_sla_alerts
from workers.tasks.resume_parsing import parse_resume
from workers.tasks.embedding_generation import generate_embeddings
from workers.tasks.notifications import (
    send_interview_notification,
    send_offer_notification,
    send_status_update_notification,
    send_sla_alert_notification,
)


# ARQ worker configuration - import this in the worker entry point
async def startup(ctx):
    """Worker startup - initialize connections."""
    pass


async def shutdown(ctx):
    """Worker shutdown - cleanup connections."""
    pass


# All available background tasks
BACKGROUND_TASKS = [
    check_sla_alerts,
    parse_resume,
    generate_embeddings,
    send_interview_notification,
    send_offer_notification,
    send_status_update_notification,
    send_sla_alert_notification,
]


class WorkerSettings:
    """ARQ worker settings."""

    functions = BACKGROUND_TASKS
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 300  # 5 minutes
    keep_result = 3600  # Keep results for 1 hour
