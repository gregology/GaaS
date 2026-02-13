import logging
import os
from pathlib import Path

import frontmatter
from dotenv import load_dotenv

from app import queue
from app.mail import Mailbox

load_dotenv()

log = logging.getLogger(__name__)

NOTES_DIR = os.environ.get("NOTES_DIR", "")
EMAIL_DIR = Path(NOTES_DIR) / "emails"


def _known_uids() -> set[str]:
    uids: set[str] = set()
    if not EMAIL_DIR.is_dir():
        log.info("Email directory does not exist: %s", EMAIL_DIR)
        return uids
    for f in EMAIL_DIR.glob("*.md"):
        try:
            post = frontmatter.load(f)
            uid = post.get("uid")
            if uid is not None:
                uids.add(str(uid))
        except Exception:
            log.warning("Failed to parse front matter: %s", f)
    return uids


def handle(task: dict):
    log.info("check_email: starting")

    known = _known_uids()
    log.info("check_email: found %d existing email files", len(known))

    with Mailbox() as mb:
        mb.collect_emails(limit=10)

        existing = []
        new = []
        for email in mb.emails:
            if email._uid in known:
                existing.append(email._uid)
            else:
                new.append(email._uid)

    log.info("check_email: %d existing emails: %s", len(existing), existing)
    log.info("check_email: %d new emails: %s", len(new), new)

    for uid in new:
        queue.enqueue({"type": "collect_email", "uid": uid})
