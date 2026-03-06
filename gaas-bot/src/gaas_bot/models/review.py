"""Structured output models for the review pipeline."""

from enum import Enum

from pydantic import BaseModel


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    NOTE = "note"


class AnalysisResult(BaseModel):
    summary: str
    risk_areas: list[str]
    affected_subsystems: list[str]


class ReviewFinding(BaseModel):
    severity: FindingSeverity
    category: str
    file: str
    line: int | None
    description: str
    suggestion: str


class ReviewResult(BaseModel):
    findings: list[ReviewFinding]


class ReviewComment(BaseModel):
    body: str
