import os
import logging
import requests
from typing import List
from datetime import datetime
from src.models import Job

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Delivers daily digest notifications via Telegram Bot API or fallback local report generator."""

    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    def send_digest(self, jobs: List[Job], total_scraped: int) -> bool:
        """Formats daily digest and dispatches via Telegram API or saves local report."""
        now_str = datetime.now().strftime("%Y-%m-%d")

        shortlisted = [j for j in jobs if j.match_score >= 70.0 or j.status in ("SHORTLISTED", "DRAFT_READY")]

        # Build Markdown Digest
        lines = []
        lines.append(f"🚀 *Daily Internship Match Digest* - `{now_str}`")
        lines.append(f"📊 *Summary*: {total_scraped} Evaluated | {len(shortlisted)} Top Matches Found\n")

        if not shortlisted:
            lines.append("ℹ️ No new listings exceeded the 70% match threshold today.")
        else:
            for idx, job in enumerate(shortlisted[:10], start=1):
                lines.append(f"*{idx}. {job.title}* @ *{job.company}*")
                lines.append(f"🎯 *Match Score*: `{job.match_score:.1f}%` | 📍 `{job.location}`")
                lines.append(f"🌐 *Source*: {job.source}")
                lines.append(f"🔗 [Job Application Link]({job.link})")
                if job.fit_blurb:
                    lines.append(f"💡 *Why Fit*: _{job.fit_blurb[:180]}..._")
                lines.append(f"⚡ *Mark Applied Command*: `python main.py mark-applied {job.id}`")
                lines.append("―" * 20)

        message_text = "\n".join(lines)

        # 1. Local Markdown Report Generation (Always created for reference)
        os.makedirs("reports", exist_ok=True)
        report_filename = f"reports/daily_digest_{now_str}.md"
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write(message_text)
        logger.info("Daily digest report generated at: %s", report_filename)

        # 2. Telegram Dispatch if configured
        if self.bot_token and self.chat_id:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                payload = {
                    "chat_id": self.chat_id,
                    "text": message_text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                }
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    logger.info("Successfully sent daily digest to Telegram chat %s", self.chat_id)
                    return True
                else:
                    logger.warning("Telegram API error (%d): %s", response.status_code, response.text)
            except Exception as e:
                logger.error("Failed to post message to Telegram: %s", str(e))

        logger.info("Telegram credentials not configured. Digest saved to '%s'", report_filename)
        return True
