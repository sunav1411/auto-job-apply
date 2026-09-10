import hashlib
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class Job(BaseModel):
    id: str = Field(default="")
    title: str
    company: str
    location: str = "Remote / Flexible"
    link: str
    description: str
    posted_date: str = ""
    source: str
    requirements: List[str] = Field(default_factory=list)
    match_score: float = 0.0
    status: str = "NEW"  # NEW, SHORTLISTED, DRAFT_READY, APPLIED, REJECTED
    fit_blurb: str = ""
    cover_note: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def compute_id(self) -> str:
        """Generates a stable unique hash identifier for deduplication."""
        raw_key = f"{self.company.lower().strip()}:{self.title.lower().strip()}:{self.link.strip()}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]

    def __init__(self, **data: Any):
        super().__init__(**data)
        if not self.id:
            self.id = self.compute_id()


class CandidateProfile(BaseModel):
    name: str
    email: str
    phone: str
    linkedin_url: str = ""
    github_url: str = ""
    location: str = "India"
    education: Dict[str, Any] = Field(default_factory=dict)
    target_roles: List[str] = Field(default_factory=list)
    target_companies: List[str] = Field(default_factory=list)
    open_to_other_companies: bool = True
    skills: Dict[str, List[str]] = Field(default_factory=dict)
    dsa_highlights: Dict[str, Any] = Field(default_factory=dict)
    min_match_threshold: float = 70.0


class MatchResult(BaseModel):
    job_id: str
    score: float
    is_shortlisted: bool
    matched_skills: List[str]
    fit_reasons: List[str]
