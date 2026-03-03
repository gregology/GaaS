import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from app.config import config

BASE_DIR = Path(config.directories.task_queue)
DIRS = ("pending", "active", "done", "failed")


def init():
    for d in DIRS:
        (BASE_DIR / d).mkdir(parents=True, exist_ok=True)


def _now():
    return datetime.now(timezone.utc)


def fingerprint(payload: dict) -> str:
    """Canonical JSON -> SHA-256 -> first 8 hex chars."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:8]


def task_type_from_payload(payload: dict) -> str:
    """Extract the task type string from a payload dict."""
    return payload.get("type", "unknown")


def parse_filename(filename: str) -> dict | None:
    """Parse a task filename into its components.

    Expected format: {priority}_{timestamp}_{uuid}--{fingerprint}--{task_type}.yaml
    Returns dict with keys: priority, timestamp, uuid, fingerprint, task_type
    or None if the filename doesn't match the expected format.
    """
    stem = filename.removesuffix(".yaml") if filename.endswith(".yaml") else filename

    parts = stem.split("--")
    if len(parts) != 3:
        return None

    prefix, fp, task_type = parts

    # prefix is {priority}_{timestamp}_{uuid}
    prefix_parts = prefix.split("_", 2)
    if len(prefix_parts) != 3:
        return None

    return {
        "priority": prefix_parts[0],
        "timestamp": prefix_parts[1],
        "uuid": prefix_parts[2],
        "fingerprint": fp,
        "task_type": task_type,
    }


def has_pending_duplicate(fp: str, task_type: str) -> bool:
    """Check if a task with the same fingerprint and type is already pending."""
    pending_dir = BASE_DIR / "pending"
    pattern = f"*--{fp}--{task_type}.yaml"
    return any(pending_dir.glob(pattern))


def count_recent(task_type: str, seconds: int) -> int:
    """Count tasks of a given type across all dirs within a time window."""
    cutoff = _now().timestamp() - seconds
    count = 0
    pattern = f"*--*--{task_type}.yaml"

    for d in DIRS:
        dir_path = BASE_DIR / d
        for f in dir_path.glob(pattern):
            parsed = parse_filename(f.name)
            if parsed is None:
                continue
            try:
                ts = datetime.strptime(parsed["timestamp"], "%Y%m%dT%H%M%SZ").replace(
                    tzinfo=timezone.utc
                )
                if ts.timestamp() >= cutoff:
                    count += 1
            except ValueError:
                continue

    return count


def _make_id(priority: int, fp: str, task_type: str) -> str:
    ts = _now().strftime("%Y%m%dT%H%M%SZ")
    short_uuid = uuid.uuid4().hex[:8]
    return f"{priority}_{ts}_{short_uuid}--{fp}--{task_type}"


def enqueue(payload: dict, priority: int = 5, provenance: str | None = None) -> str:
    fp = fingerprint(payload)
    task_type = task_type_from_payload(payload)
    task_id = _make_id(priority, fp, task_type)
    task = {
        "id": task_id,
        "created_at": _now().isoformat(),
        "status": "pending",
        "priority": priority,
        "payload": payload,
    }
    if provenance is not None:
        task["provenance"] = provenance
    path = BASE_DIR / "pending" / f"{task_id}.yaml"
    path.write_text(yaml.dump(task, default_flow_style=False, sort_keys=False))
    return task_id


def dequeue() -> dict | None:
    pending_dir = BASE_DIR / "pending"
    files = sorted(f.name for f in pending_dir.iterdir() if f.suffix == ".yaml")
    if not files:
        return None

    filename = files[0]
    src = pending_dir / filename
    dst = BASE_DIR / "active" / filename

    try:
        os.rename(src, dst)
    except FileNotFoundError:
        # Another worker grabbed it first
        return None

    task = yaml.safe_load(dst.read_text())
    task["status"] = "active"
    dst.write_text(yaml.dump(task, default_flow_style=False, sort_keys=False))
    return task


def complete(task_id: str, result: dict | None = None):
    filename = f"{task_id}.yaml"
    src = BASE_DIR / "active" / filename
    dst = BASE_DIR / "done" / filename

    task = yaml.safe_load(src.read_text())
    task["status"] = "done"
    task["completed_at"] = _now().isoformat()
    if result is not None:
        task["result"] = result
    src.write_text(yaml.dump(task, default_flow_style=False, sort_keys=False))

    os.rename(src, dst)


def fail(task_id: str, error: str):
    filename = f"{task_id}.yaml"
    src = BASE_DIR / "active" / filename
    dst = BASE_DIR / "failed" / filename

    task = yaml.safe_load(src.read_text())
    task["status"] = "failed"
    task["failed_at"] = _now().isoformat()
    task["error"] = error
    src.write_text(yaml.dump(task, default_flow_style=False, sort_keys=False))

    os.rename(src, dst)
