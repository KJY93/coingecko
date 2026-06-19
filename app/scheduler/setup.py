from app.core.config import settings
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.scheduler.jobs import poll_market_data, poll_coins
from datetime import datetime

scheduler = AsyncIOScheduler()

def setup_scheduler() -> None:
    scheduler.add_job(
        poll_market_data,
        'interval',
        seconds=settings.scheduler_interval_seconds,
        id='poll_market_data',
        next_run_time=datetime.now()
    )

    scheduler.add_job(
        poll_coins,
        'interval',
        hours=settings.coins_refresh_hours,
        id='poll_coins',
        next_run_time=datetime.now()
    )
    scheduler.start()

def shutdown_scheduler() -> None:
    scheduler.shutdown()