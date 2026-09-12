import logging
import re
import time
from datetime import datetime
from typing import List, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from src.models import Job, CandidateProfile, MatchResult

logger = logging.getLogger(__name__)


class MatchingEngine:
    """Hybrid scoring & ranking engine using keyword overlap, TF-IDF cosine similarity, and priority company bonuses."""

    def __init__(self, profile: CandidateProfile, resume_text: str):
        self.profile = profile
        self.resume_text = resume_text
        self._prepare_skill_set()

    def _prepare_skill_set(self):
        """Extracts flat list of lowercase skills and keywords from profile."""
        self.skill_keywords = set()
        for category, skill_list in self.profile.skills.items():
            for sk in skill_list:
                self.skill_keywords.add(sk.lower())

        self.target_roles = [r.lower() for r in self.profile.target_roles]
        self.target_companies = [c.lower() for c in self.profile.target_companies]

    def _is_india_location(self, location: str) -> bool:
        """Determines if a job location is in India or a flexible remote position compatible with India."""
        if not location:
            return True

        loc_lower = location.lower()

        # Explicit foreign indicators (countries, US states, foreign cities)
        foreign_patterns = [
            r"\b(usa|us|united states|uk|united kingdom|canada|germany|singapore|australia|france|japan)\b",
            r"\b(london|toronto|oakville|chantilly|palo alto|cambridge|pleasant prairie|seattle|austin|new york|sf|san francisco)\b",
            r"\b(wi|va|tx|ny|ma|wa|ca|il|fl|nc)\b",
        ]

        # Explicit Indian indicators
        india_patterns = [
            r"\b(india|in)\b",
            r"\b(bengaluru|bangalore|gurugram|gurgaon|noida|hyderabad|pune|chennai|mumbai|delhi|dehradun|uttarakhand|ahmedabad|karnataka|telangana|maharashtra|tamil nadu|uttar pradesh|haryana|ncr)\b",
        ]

        has_india = any(re.search(pat, loc_lower) for pat in india_patterns)
        has_foreign = any(re.search(pat, loc_lower) for pat in foreign_patterns)

        if has_india:
            return True

        if has_foreign and not has_india:
            return False

        if "remote" in loc_lower or "anywhere" in loc_lower or "work from home" in loc_lower:
            return True

        return not has_foreign

    def _is_fresh_posting(self, posted_date_str: str, max_hours: int = 48) -> bool:
        """Determines if a job posting was created within max_hours (e.g. 24-48 hours ago)."""
        if not posted_date_str:
            return True

        text = str(posted_date_str).strip().lower()

        # Key phrases indicating recent / fresh posting
        if any(k in text for k in ["just now", "today", "few hours", "recently", "active web opening", "live verified"]):
            return True

        if "yesterday" in text:
            return True

        # Check "X hours ago", "X mins ago", "X days ago"
        hours_match = re.search(r"(\d+)\s*h(?:our)?s?\s*ago", text)
        if hours_match:
            return int(hours_match.group(1)) <= max_hours

        mins_match = re.search(r"(\d+)\s*m(?:in)?s?\s*ago", text)
        if mins_match:
            return True

        days_match = re.search(r"(\d+)\s*d(?:ay)?s?\s*ago", text)
        if days_match:
            days = int(days_match.group(1))
            return days <= max(1, max_hours // 24)  # 48h = <= 2 days

        weeks_match = re.search(r"(\d+)\s*w(?:eek)?s?\s*ago", text)
        if weeks_match:
            return False  # > 48 hours

        months_match = re.search(r"(\d+)\s*m(?:onth)?s?\s*ago", text)
        if months_match:
            return False  # > 48 hours

        # Check Epoch timestamp (seconds)
        if text.isdigit() or (text.replace('.', '', 1).isdigit() and len(text) >= 10):
            try:
                ts = float(text)
                now_ts = time.time()
                age_hours = (now_ts - ts) / 3600.0
                return 0 <= age_hours <= max_hours
            except Exception:
                pass

        # Check ISO / YYYY-MM-DD Date
        date_match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
        if date_match:
            try:
                year, month, day = map(int, date_match.groups())
                post_dt = datetime(year, month, day)
                now_dt = datetime.now()
                age_hours = (now_dt - post_dt).total_seconds() / 3600.0
                return age_hours <= max_hours + 24  # Allow day boundary buffer
            except Exception:
                pass

        return True

    def score_job(self, job: Job) -> Tuple[float, MatchResult]:
        """Calculates 0-100 match score for a job posting."""
        # 0. Location Filter Enforcement
        if getattr(self.profile, "only_india_locations", True):
            if not self._is_india_location(job.location):
                logger.info("Skipping non-India location job: '%s' @ %s (%s)", job.title, job.company, job.location)
                match_result = MatchResult(
                    job_id=job.id,
                    score=0.0,
                    is_shortlisted=False,
                    matched_skills=[],
                    fit_reasons=["Filtered out: Non-India location"],
                )
                job.match_score = 0.0
                return 0.0, match_result

        # 0b. Posting Age Filter Enforcement (Max 48 hours)
        max_age = getattr(self.profile, "max_job_age_hours", 48)
        if not self._is_fresh_posting(job.posted_date, max_hours=max_age):
            logger.info("Skipping old job posting (>%dh ago): '%s' @ %s (Posted: %s)", max_age, job.title, job.company, job.posted_date)
            match_result = MatchResult(
                job_id=job.id,
                score=0.0,
                is_shortlisted=False,
                matched_skills=[],
                fit_reasons=[f"Filtered out: Posted > {max_age}h ago ({job.posted_date})"],
            )
            job.match_score = 0.0
            return 0.0, match_result


        text_content = f"{job.title} {job.company} {job.location} {job.description} {' '.join(job.requirements)}".lower()

        # 1. Target Role Title Match (+25 points max)
        role_score = 0.0
        role_matched = False
        for target_role in self.target_roles:
            if target_role in text_content:
                role_score = 25.0
                role_matched = True
                break
            # Partial match like "intern" + "software" / "engineering" / "ai" / "ml" / "backend"
            elif "intern" in text_content and any(w in text_content for w in ["software", "developer", "backend", "ai", "ml", "machine learning"]):
                role_score = 20.0
                role_matched = True
                break

        # 2. Skill & Keyword Overlap Score (40 points max)
        matched_skills = []
        for skill in self.skill_keywords:
            if re.search(r"\b" + re.escape(skill) + r"\b", text_content):
                matched_skills.append(skill)

        skill_ratio = len(matched_skills) / max(len(self.skill_keywords), 1)
        skill_score = min(skill_ratio * 40.0 * 2.5, 40.0)

        # 3. TF-IDF Cosine Similarity (35 points max)
        corpus = [self.resume_text.lower(), text_content]
        try:
            vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
            tfidf_matrix = vectorizer.fit_transform(corpus)
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            semantic_score = float(similarity) * 35.0 * 3.0  # Scale factor for resume alignment
            semantic_score = min(semantic_score, 35.0)
        except Exception as e:
            logger.warning("TF-IDF similarity calculation failed: %s", str(e))
            semantic_score = 15.0

        # Subtotal calculation (0-100)
        base_score = role_score + skill_score + semantic_score

        # 4. Priority Target Company Bonus (+15 points)
        company_matched = False
        if job.company.lower() in self.target_companies:
            base_score += 15.0
            company_matched = True
            logger.info("Priority target company bonus applied for %s (+15 pts)", job.company)

        # Cap score between 0 and 100
        final_score = round(min(max(base_score, 0.0), 100.0), 1)
        is_shortlisted = final_score >= self.profile.min_match_threshold

        fit_reasons = []
        if matched_skills:
            fit_reasons.append(f"Matched Skills: {', '.join(matched_skills[:5])}")
        if role_matched:
            fit_reasons.append("Matches target SDE / AI-ML Intern role title")
        if company_matched:
            fit_reasons.append(f"Priority Target Company: {job.company}")

        match_result = MatchResult(
            job_id=job.id,
            score=final_score,
            is_shortlisted=is_shortlisted,
            matched_skills=matched_skills,
            fit_reasons=fit_reasons,
        )

        job.match_score = final_score
        if is_shortlisted and job.status == "NEW":
            job.status = "SHORTLISTED"

        return final_score, match_result

