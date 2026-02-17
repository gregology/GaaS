from __future__ import annotations

import logging
import re

from fastapi import FastAPI
from fastapi_crons import Crons

from app import queue
from app.config import cfg

log = logging.getLogger(__name__)


def interval_to_cron(interval: str) -> str:
    """Convert a friendly interval like '30m' or '2h' to a cron expression."""
    match = re.fullmatch(r"(\d+)\s*([mhd])", interval.strip().lower())
    if not match:
        raise ValueError(f"Invalid interval format: {interval!r} (expected e.g. '30m', '2h', '1d')")

    value, unit = int(match.group(1)), match.group(2)

    if unit == "m":
        if value < 1 or value > 59:
            raise ValueError(f"Minute interval must be 1-59, got {value}")
        return f"*/{value} * * * *"
    if unit == "h":
        if value < 1 or value > 23:
            raise ValueError(f"Hour interval must be 1-23, got {value}")
        return f"0 */{value} * * *"
    if unit == "d":
        if value != 1:
            raise ValueError(f"Day interval only supports '1d' (daily), got {value}d")
        return "0 0 * * *"

    raise ValueError(f"Unknown unit: {unit}")


def _resolve_expr(schedule: dict) -> str:
    if "cron" in schedule:
        return schedule["cron"]
    if "every" in schedule:
        return interval_to_cron(schedule["every"])
    raise ValueError(f"Schedule must have 'cron' or 'every' key: {schedule}")


def init_schedules(app: FastAPI) -> Crons:
    schedules = cfg("schedules", [])
    if not schedules:
        log.info("No schedules configured")
        return Crons(app)

    crons = Crons(app)

    for i, schedule in enumerate(schedules):
        task_type = schedule["task"]
        expr = _resolve_expr(schedule)
        options = schedule.get("options", {})
        name = f"{task_type}_{i}"

        def make_job(t=task_type, o=options):
            def job():
                log.info("Scheduled job: enqueueing %s with %s", t, o)
                queue.enqueue({"type": t, **o})
            return job

        crons.cron(expr, name=name)(make_job())
        log.info("Registered schedule: %s [%s]", name, expr)

    return crons
