import logging
import re
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

