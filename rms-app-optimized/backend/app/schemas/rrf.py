"""RRF request/response schemas (Pydantic v2)."""
from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field

ProjectType = Literal["T_AND_M", "FIXED_FEE"]
ReqType = Literal["ESSENTIAL", "DESIRED"]


class RrfSkillIn(BaseModel):
    skill_id: int
    req_type: ReqType
    priority: int = Field(default=3, ge=1, le=5)


class TransitionRequest(BaseModel):
    action: str = Field(min_length=1)
    comment: str = Field(min_length=1)  # INV-01; whitespace-only rejected server-side


class RrfCreate(BaseModel):
    position_title: str = Field(min_length=1, max_length=120)
    positions_count: int = Field(ge=1)
    assignment_location: str = Field(min_length=1, max_length=80)
    base_location: str | None = None
    justification: str = Field(min_length=1)
    project_name: str = Field(min_length=1, max_length=120)
    project_type: ProjectType
    needed_by_date: datetime.date
    salary_range: str | None = None
    wfh_allowed: bool = False
    shift_hours: str | None = None
    reporting_to: str | None = None
    scope_of_work: str | None = None
    responsibilities: str | None = None
    education_qualification: str | None = None
    min_experience_years: float = Field(default=0, ge=0)
    bu_id: int
    hr_rep_user_id: str | None = None
    skills: list[RrfSkillIn] = Field(default_factory=list)


class RrfUpdate(BaseModel):
    """All fields optional; only DRAFT/REJECTED RRFs are editable (service-enforced)."""
    position_title: str | None = Field(default=None, max_length=120)
    positions_count: int | None = Field(default=None, ge=1)
    assignment_location: str | None = Field(default=None, max_length=80)
    base_location: str | None = None
    justification: str | None = None
    project_name: str | None = Field(default=None, max_length=120)
    project_type: ProjectType | None = None
    needed_by_date: datetime.date | None = None
    salary_range: str | None = None
    wfh_allowed: bool | None = None
    shift_hours: str | None = None
    reporting_to: str | None = None
    scope_of_work: str | None = None
    responsibilities: str | None = None
    education_qualification: str | None = None
    min_experience_years: float | None = Field(default=None, ge=0)
    hr_rep_user_id: str | None = None
    skills: list[RrfSkillIn] | None = None  # if provided, replaces the full skill set


class RrfSkillOut(BaseModel):
    skill_id: int
    skill_name: str
    req_type: str
    priority: int


class RrfListItem(BaseModel):
    rrf_id: str
    rrf_code: str
    position_title: str
    positions_count: int
    status: str
    project_name: str
    bu_id: int
    bu_name: str | None = None
    needed_by_date: datetime.date
    created_at: datetime.datetime


class RrfOut(RrfListItem):
    assignment_location: str
    base_location: str | None
    justification: str
    project_type: str
    salary_range: str | None
    wfh_allowed: bool
    shift_hours: str | None
    reporting_to: str | None
    scope_of_work: str | None
    responsibilities: str | None
    education_qualification: str | None
    min_experience_years: float
    created_by: str
    hr_rep_user_id: str | None
    approved_by: str | None
    positions_filled: int
    skills: list[RrfSkillOut]
