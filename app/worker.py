import logging
import time

from app import queue
from app.tasks import check_email, classify_email, collect_email

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
}


def handle(task: dict):
    task_type = task["payload"].get("type")
    handler = HANDLERS.get(task_type)
    if handler is None:
        log.warning("Unknown task type: %s", task_type)
        return
    handler(task)


def main():
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
