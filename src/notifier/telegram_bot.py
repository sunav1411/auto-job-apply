import os
import html
import logging
import requests
from typing import List
from datetime import datetime
from src.models import Job

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Delivers daily digest notifications via Telegram Bot API with chunking support for long digests."""

    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    def _post_telegram_chunk(self, text: str) -> bool:
        """Helper to post a single message chunk to Telegram API."""
        if not (self.bot_token and self.chat_id):
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("Successfully sent digest chunk to Telegram chat %s", self.chat_id)
                return True
            else:
                logger.warning("Telegram API error (%d): %s", response.status_code, response.text)
                return False
        except Exception as e:
            logger.error("Failed to post message to Telegram: %s", str(e))
            return False

    def send_digest(self, jobs: List[Job], total_scraped: int) -> bool:
        """Formats daily digest and dispatches via Telegram API or saves local report."""
        now_str = datetime.now().strftime("%Y-%m-%d")

        shortlisted = [j for j in jobs if j.match_score >= 50.0 or j.status in ("SHORTLISTED", "DRAFT_READY")]

        # Build Full Report text for file
        header_file = f"🚀 Daily Internship Match Digest - {now_str}\n📊 Summary: {total_scraped} Evaluated | {len(shortlisted)} Top Matches Found\n"
        
        # 1. Save Full Local Report File
        os.makedirs("reports", exist_ok=True)
        report_filename = f"reports/daily_digest_{now_str}.md"
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write(header_file + "\n")
            for idx, job in enumerate(shortlisted, start=1):
                f.write(f"### {idx}. {job.title} @ {job.company} (Match: {job.match_score:.1f}%)\n")
                f.write(f"- Location: {job.location} | Source: {job.source}\n")
                f.write(f"- Link: {job.link}\n")
                f.write(f"- Why Fit: {job.fit_blurb}\n\n")

        logger.info("Daily digest report saved to: %s", report_filename)

        # 2. Dispatch to Telegram in safe chunks if credentials present
        if self.bot_token and self.chat_id:
            header_html = (
                f"🚀 <b>Daily Internship Match Digest</b> - <code>{now_str}</code>\n"
                f"📊 <b>Summary</b>: {total_scraped} Evaluated | {len(shortlisted)} Top Matches Found\n"
            )

            if not shortlisted:
                self._post_telegram_chunk(header_html + "\nℹ️ No new listings exceeded the match threshold today.")
                return True

            # Send header chunk
            self._post_telegram_chunk(header_html)

            # Send job items in small batches of 3 to avoid character limits
            batch_size = 3
            for i in range(0, min(len(shortlisted), 12), batch_size):
                batch = shortlisted[i:i + batch_size]
                chunk_lines = []
                for idx, job in enumerate(batch, start=i + 1):
                    safe_title = html.escape(job.title)
                    safe_company = html.escape(job.company)
                    safe_location = html.escape(job.location)
                    safe_blurb = html.escape(job.fit_blurb[:140]) if job.fit_blurb else ""

                    chunk_lines.append(f"<b>{idx}. {safe_title}</b> @ <b>{safe_company}</b>")
                    chunk_lines.append(f"🎯 <b>Match Score</b>: <code>{job.match_score:.1f}%</code> | 📍 <code>{safe_location}</code>")
                    chunk_lines.append(f"🌐 <b>Source</b>: {job.source}")
                    chunk_lines.append(f"🔗 <a href=\"{job.link}\">Apply Link</a>")
                    if safe_blurb:
                        chunk_lines.append(f"💡 <b>Why Fit</b>: <i>{safe_blurb}...</i>")
                    chunk_lines.append(f"⚡ <b>Mark Applied</b>: <code>python main.py mark-applied {job.id}</code>")
                    chunk_lines.append("―" * 20)

                self._post_telegram_chunk("\n".join(chunk_lines))

            return True

        logger.info("Telegram credentials omitted. Local digest saved to '%s'", report_filename)
        return True

