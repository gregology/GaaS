import argparse
import logging
import time

import app.human_log  # noqa: F401 — registers log.human()
from app import queue
from app.config import config
from app.tasks import (
    check_email, classify_email, classify_github_pr, collect_email, update_github_prs,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

POLL_INTERVAL = 1  # seconds


HANDLERS = {
    "check_email": check_email.handle,
    "collect_email": collect_email.handle,
    "classify_email": classify_email.handle,
    "classify_github_pr": classify_github_pr.handle,
    "update_github_prs": update_github_prs.handle,
}


def handle(task: dict):
    task_type = task["payload"].get("type")
    handler = HANDLERS.get(task_type)
    if handler is None:
        log.warning("Unknown task type: %s", task_type)
        return
    handler(task)


def main():
    parser = argparse.ArgumentParser(description="GaaS task worker")
    parser.add_argument("--llm_base_url", help="Override the default LLM base URL from config.yaml")
    args = parser.parse_args()

    if args.llm_base_url and "default" in config.llms:
        config.llms["default"].base_url = args.llm_base_url

    queue.init()
    log.info("Worker started, polling every %ss", POLL_INTERVAL)

    while True:
        task = queue.dequeue()
        if task is None:
            time.sleep(POLL_INTERVAL)
            continue

        log.info("Dequeued task %s", task["id"])
        try:
            handle(task)
            queue.complete(task["id"])
            log.info("Completed task %s", task["id"])
        except Exception as exc:
            log.exception("Task %s failed", task["id"])
            queue.fail(task["id"], str(exc))


if __name__ == "__main__":
    main()
