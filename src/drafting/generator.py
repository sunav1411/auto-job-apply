import logging
from src.models import Job, CandidateProfile

logger = logging.getLogger(__name__)


class DraftGenerator:
    """Generates tailored application blurbs and cover note drafts for shortlisted jobs."""

    def __init__(self, profile: CandidateProfile):
        self.profile = profile

    def generate_drafts(self, job: Job) -> Job:
        """Generates tailored 'Why I'm a fit' blurb and cover note for a shortlisted job."""
        skills_str = ", ".join(self.profile.skills.get("backend", [])[:3] + self.profile.skills.get("ai_ml", [])[:2])
        dsa_info = self.profile.dsa_highlights.get(
            "achievement", "470+ LeetCode problems solved with peak rating 1692"
        )

        fit_blurb = (
            f"As a 3rd-year B.Tech CSE (AI & ML) student with strong hands-on experience in {skills_str}, "
            f"I am very excited to apply for the {job.title} position at {job.company}. "
            f"My technical background spans Java backend microservices, full-stack development, and applied machine learning models. "
            f"Additionally, I have demonstrated strong problem-solving capabilities by completing {dsa_info}. "
            f"My background aligns directly with the core skills required for this role at {job.company}."
        )

        cover_note = (
            f"Dear Hiring Team at {job.company},\n\n"
            f"I am writing to express my strong interest in the {job.title} role ({job.location}). "
            f"Currently pursuing my B.Tech in Computer Science Engineering (Specialization in AI & ML), I have built robust projects "
            f"in Java backend development, REST API design, and AI/ML model deployment.\n\n"
            f"Key Highlights:\n"
            f"- Technical Stack: Java, Spring Boot, Python, PyTorch/TensorFlow, PostgreSQL, React.\n"
            f"- DSA & Algorithmic Problem Solving: {dsa_info}.\n"
            f"- Practical Experience: Developed scalable REST microservices and ML semantic search models.\n\n"
            f"I would welcome the opportunity to bring my analytical rigor and passion for software engineering to {job.company}.\n\n"
            f"Best regards,\n"
            f"{self.profile.name}\n"
            f"{self.profile.email} | {self.profile.phone}\n"
            f"LinkedIn: {self.profile.linkedin_url} | GitHub: {self.profile.github_url}"
        )

        job.fit_blurb = fit_blurb
        job.cover_note = cover_note
        if job.status in ("NEW", "SHORTLISTED"):
            job.status = "DRAFT_READY"

        logger.info("Generated tailored draft for job: %s at %s", job.title, job.company)
        return job
