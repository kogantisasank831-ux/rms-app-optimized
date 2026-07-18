"""Offer request/response schemas (Pydantic v2)."""
from __future__ import annotations

import datetime

from pydantic import BaseModel, Field


class OfferCreate(BaseModel):
    application_id: str
    candidate_name: str | None = Field(default=None, max_length=120)  # override; defaults to applicant
    designation: str = Field(min_length=1, max_length=120)
    ctc_annual: str = Field(min_length=1, max_length=60)              # Total Cost to Company
    monthly_gross: str | None = Field(default=None, max_length=60)
    joining_date: datetime.date
    work_location: str = Field(min_length=1, max_length=120)          # base / joining location
    valid_until: datetime.date | None = None


class OfferUpdate(BaseModel):
    """Edit a DRAFT offer before generating the letter. All fields optional (partial update)."""
    candidate_name: str | None = Field(default=None, max_length=120)
    designation: str | None = Field(default=None, min_length=1, max_length=120)
    ctc_annual: str | None = Field(default=None, min_length=1, max_length=60)
    monthly_gross: str | None = Field(default=None, max_length=60)
    joining_date: datetime.date | None = None
    work_location: str | None = Field(default=None, min_length=1, max_length=120)
    valid_until: datetime.date | None = None


class OfferTransition(BaseModel):
    action: str = Field(min_length=1)
    comment: str = Field(min_length=1)  # INV-01


class OfferOut(BaseModel):
    offer_id: str
    offer_code: str
    application_id: str
    candidate_name: str | None
    designation: str
    ctc_annual: str
    monthly_gross: str | None
    joining_date: datetime.date
    work_location: str
    status: str
    valid_until: datetime.date | None
    letter_object_key: str | None
    created_at: datetime.datetime


class GenerateLetterOut(BaseModel):
    letter_object_key: str
    download_url: str
    template_version: str = "v1-fixed"
