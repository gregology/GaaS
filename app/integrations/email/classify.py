import logging
import secrets
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.config import ClassificationConfig, config
from app.llm import LLMConversation
from .mail import Mailbox
from .store import EmailStore

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

DEFAULT_CLASSIFICATIONS: dict[str, ClassificationConfig] = {
    "human": ClassificationConfig(prompt="is this a personal email written by a human?"),
    "user_agreement_update": ClassificationConfig(prompt="is this email about a user agreement update?", type="boolean"),
    "requires_response": ClassificationConfig(prompt="does this email require a response?", type="boolean"),
    "priority": ClassificationConfig(prompt="what is the priority of this email?", type="enum", values=["low", "medium", "high", "critical"]),
}

_TYPE_TO_SCHEMA = {
    "confidence": lambda _cls: {"type": "number"},
    "boolean": lambda _cls: {"type": "boolean"},
    "enum": lambda cls: {"type": "string", "enum": cls.values},
}


def _build_schema(classifications: dict[str, ClassificationConfig]) -> dict:
    properties = {}
    for name, cls in classifications.items():
        properties[name] = _TYPE_TO_SCHEMA[cls.type](cls)
    return {
        "properties": properties,
        "required": list(classifications.keys()),
    }


def _render_prompt(email, classifications: dict[str, ClassificationConfig]) -> str:
    template = jinja_env.get_template("classify_email.jinja")
    return template.render(
        beginning_salt=secrets.token_hex(16),
        end_salt=secrets.token_hex(16),
        email=email,
        classifications=classifications,
    )


def handle(task: dict):
    integration_name = task["payload"]["integration"]
    integration = config.get_integration(integration_name)
    uid = task["payload"]["uid"]
    log.info("email.classify: uid=%s (integration=%s)", uid, integration_name)

    classifications = integration.classifications or DEFAULT_CLASSIFICATIONS

    with Mailbox(
        imap_server=integration.imap_server,
        imap_port=integration.imap_port,
        username=integration.username,
        password=integration.password,
    ) as mb:
        email = mb.get_email(uid)

    prompt = _render_prompt(email, classifications)
    log.info("email.classify prompt:\n%s", prompt)
    conversation = LLMConversation(
        model=integration.llm,
        system="Disable internal monologue. Answer directly. Respond with JSON.",
    )
    schema = _build_schema(classifications)
    classification = conversation.message(prompt=prompt, schema=schema)

    log.info("email.classify: uid=%s result=%s", uid, classification)

    notes_dir = config.directories.notes
    store = EmailStore(path=notes_dir / "emails" / integration.username)
    store.update(uid, classification=classification)
