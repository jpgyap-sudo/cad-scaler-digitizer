"""Validation models."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class ValidationIssue(BaseModel):
    severity: str  # error, warning, info
    code: str
    message: str
    suggested_fix: Optional[str] = None
    field: Optional[str] = None


class ValidationReport(BaseModel):
    product_type: str
    template_id: str
    approved_for_drafting: bool
    score: float = Field(default=0.0, ge=0, le=1)
    issues: List[ValidationIssue] = []
    applied_corrections: List[str] = []
