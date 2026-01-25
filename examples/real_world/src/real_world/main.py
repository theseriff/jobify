"""A backup application.

that send an email alert and backs up a database file and syncs changes to
GitHub 3 times a day.
"""

import asyncio
import logging

from jobify import Cron, Jobify, JobRouter, MisfirePolicy
from real_world.backup_db import backup_router, schedule_daily_backups
from real_world.configs import load_configs
from real_world.notifications import notifications_router, send_email_alert

logger = logging.getLogger(__name__)


def setup_routes(app: Jobify) -> None:
    """Register API routes (v1)."""
    router_v1 = JobRouter(prefix="v1")

    # Include both routers
    router_v1.include_router(backup_router)
    router_v1.include_router(notifications_router)

    app.include_router(router_v1)


def create_app() -> Jobify:
    """Create and configure Jobify application instance."""
    configs = load_configs()
    app = Jobify(tz=configs.tz)
    app.state.configs = configs
    setup_routes(app)
    return app


async def _main() -> None:
    """Entry point to run the Jobify app."""
    app = create_app()
    cron: str = app.state.configs.cron
    async with app:
        logger.info("Application started!")

        # 1. Schedule the daily planning task for backups
        _job = await schedule_daily_backups.schedule().cron(
            Cron(cron, max_runs=1, misfire_policy=MisfirePolicy.ONCE),
            job_id="plan_daily_backups",
            replace=True,
        )

        # 2. Schedule a startup notification (demonstrates the middleware)
        _job = await send_email_alert.schedule(
            recipient="admin@example.com",
            subject="Backup Service Started",
        ).delay(
            1.0,  # Run 1 second after startup
            job_id="startup_notification",
        )

        await app.wait_all()

        logger.info("Application stopped!")


def main() -> None:  # noqa: D103
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    asyncio.run(_main())
