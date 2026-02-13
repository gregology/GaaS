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


def handle(task: dict):
    uid = task["payload"]["uid"]
    log.info("collect_email: uid=%s", uid)

    EMAIL_DIR.mkdir(parents=True, exist_ok=True)

    with Mailbox() as mb:
        email = mb.get_email(uid)

    filename = email.date.strftime("%Y_%m_%d_%H_%M_%S") + f"__{uid}.md"
    filepath = EMAIL_DIR / filename

    post = frontmatter.Post(
        "",
        uid=uid,
        from_address=email.from_address,
        to_address=email.to_address,
        subject=email.subject,
        recieved_at=email.date.isoformat(),
        dkim_pass=email.dkim_pass,
        dmarc_pass=email.dmarc_pass,
        spf_pass=email.spf_pass,
    )

    filepath.write_text(frontmatter.dumps(post))
    log.info("collect_email: saved %s", filepath)

    if email.dkim_pass and email.dmarc_pass and email.spf_pass:
        queue.enqueue({"type": "classify_email", "uid": uid})
        log.info("collect_email: queued classify_email for uid=%s", uid)
