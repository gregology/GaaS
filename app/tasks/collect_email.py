import logging

from app import queue
from app.mail import Mailbox
from app.store import EmailStore

log = logging.getLogger(__name__)


def handle(task: dict):
    uid = task["payload"]["uid"]
    log.info("collect_email: uid=%s", uid)

    with Mailbox() as mb:
        email = mb.get_email(uid)

    store = EmailStore()
    store.save(email)

    if all(email.authentication.values()):
        queue.enqueue({"type": "classify_email", "uid": uid}, priority=6)
        log.info("collect_email: queued classify_email for uid=%s", uid)
    else:
        queue.enqueue({"type": "classify_email", "uid": uid}, priority=9)
        log.info("collect_email: queued low priority classify_email for uid=%s", uid)
