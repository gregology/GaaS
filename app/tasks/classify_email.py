import logging
import os
import secrets
from pathlib import Path

import frontmatter
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

from app.llm import LLMConversation
from app.mail import Mailbox

load_dotenv()

log = logging.getLogger(__name__)

NOTES_DIR = os.environ.get("NOTES_DIR", "")
EMAIL_DIR = Path(NOTES_DIR) / "emails"

TEMPLATES_DIR = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

CLASSIFY_SCHEMA = {
    "properties": {
        "human": {"type": "number"},
        "robot": {"type": "number"},
        "requires_response": {"type": "number"},
        "requires_action": {"type": "number"},
        "urgency": {"type": "number"},
    },
    "required": ["human", "robot", "requires_response", "requires_action", "urgency"],
}


def _find_email_file(uid: str) -> Path | None:
    for f in EMAIL_DIR.glob("*.md"):
        try:
            post = frontmatter.load(f)
            if str(post.get("uid")) == uid:
                return f
        except Exception:
            log.warning("Failed to parse front matter: %s", f)
    return None


def _render_prompt(email_contents_clean: str) -> str:
    template = jinja_env.get_template("classify_email.jinja")
    return template.render(
        beginning_salt=secrets.token_hex(16),
        end_salt=secrets.token_hex(16),
        email_contents_clean=email_contents_clean,
    )


def handle(task: dict):
    uid = task["payload"]["uid"]
    log.info("classify_email: uid=%s", uid)

    with Mailbox() as mb:
        email = mb.get_email(uid)

    prompt = _render_prompt(email.contents_clean)
    conversation = LLMConversation(model="fast")
    classification = conversation.message(prompt=prompt, schema=CLASSIFY_SCHEMA)

    log.info("classify_email: uid=%s result=%s", uid, classification)

    filepath = _find_email_file(uid)
    if filepath is None:
        log.error("classify_email: no file found for uid=%s", uid)
        return

    post = frontmatter.load(filepath)
    for key, value in classification.items():
        post[key] = value
    filepath.write_text(frontmatter.dumps(post))
    log.info("classify_email: updated %s", filepath)
