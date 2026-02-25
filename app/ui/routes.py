from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from app.ui.presenters import (
    config_context,
    dashboard_context,
    log_detail_context,
    log_list_context,
    queue_context,
)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)

router = APIRouter(prefix="/ui")


@router.get("/", response_class=HTMLResponse)
async def dashboard():
    template = _env.get_template("dashboard.html")
    return template.render(**dashboard_context())


@router.get("/config", response_class=HTMLResponse)
async def config_page():
    template = _env.get_template("config.html")
    return template.render(**config_context())


@router.get("/queue", response_class=HTMLResponse)
async def queue_page():
    template = _env.get_template("queue.html")
    return template.render(**queue_context())


@router.get("/logs", response_class=HTMLResponse)
async def logs_page():
    template = _env.get_template("logs.html")
    ctx = log_list_context()
    ctx["date"] = None
    ctx["content"] = None
    return template.render(**ctx)


@router.get("/logs/{date}", response_class=HTMLResponse)
async def log_detail(date: str):
    template = _env.get_template("logs.html")
    return template.render(**log_detail_context(date))
