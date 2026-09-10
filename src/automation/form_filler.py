import os
import time
import logging
from typing import Tuple
from playwright.sync_api import sync_playwright
from src.models import Job, CandidateProfile

logger = logging.getLogger(__name__)


class FormFiller:
    """Playwright automated form pre-filler with CAPTCHA detection, multi-step support, and graceful fallback to manual apply."""

    def __init__(
        self,
        profile: CandidateProfile,
        resume_pdf_path: str = "data/resume.pdf",
        headless: bool = False,
    ):
        self.profile = profile
        self.resume_pdf_path = os.path.abspath(resume_pdf_path)

    def detect_captcha_or_blockers(self, page) -> bool:
        """Detects presence of CAPTCHA, Cloudflare, or Bot Protection challenges."""
        captcha_selectors = [
            "iframe[src*='captcha' i]",
            "iframe[title*='recaptcha' i]",
            "div[class*='captcha' i]",
            "div[id*='captcha' i]",
            "div[class*='cf-turnstile' i]",
            "div[id*='cf-turnstile' i]",
        ]
        for sel in captcha_selectors:
            if page.locator(sel).count() > 0:
                logger.warning("CAPTCHA / Security challenge detected via selector '%s'", sel)
                return True
        return False

    def prefill_application(self, job: Job, pause_seconds: int = 10) -> Tuple[bool, str]:
        """
        Launches Playwright, navigates to application link, pre-fills fields, attaches PDF resume.
        Returns: (success: bool, status_message: str)
        Does NOT click submit. If complex form/CAPTCHA is hit, gracefully flags MANUAL_APPLY_NEEDED.
        """
        if not os.path.exists(self.resume_pdf_path):
            logger.warning("Resume PDF file missing at path: %s", self.resume_pdf_path)

        logger.info("Starting Playwright form pre-fill for job '%s' at %s...", job.title, job.company)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()

            try:
                logger.info("Navigating to application link: %s", job.link)
                page.goto(job.link, timeout=35000, wait_until="domcontentloaded")
                time.sleep(3)

                # Check for CAPTCHA
                if self.detect_captcha_or_blockers(page):
                    screenshot_path = f"reports/screenshots/captcha_block_{job.id}.png"
                    os.makedirs("reports/screenshots", exist_ok=True)
                    page.screenshot(path=screenshot_path)
                    logger.warning("CAPTCHA detected on %s. MANUAL_APPLY_NEEDED.", job.link)
                    browser.close()
                    return False, "MANUAL_APPLY_NEEDED: CAPTCHA / Protection Challenge Detected"

                # Fill Full Name
                filled_any = False
                for selector in [
                    "input[name*='name' i]",
                    "input[id*='name' i]",
                    "input[placeholder*='name' i]",
                    "input[aria-label*='name' i]",
                ]:
                    if page.locator(selector).count() > 0:
                        try:
                            page.locator(selector).first.fill(self.profile.name)
                            logger.info("Filled Name field using selector '%s'", selector)
                            filled_any = True
                            break
                        except Exception:
                            pass

                # Fill Email
                for selector in [
                    "input[type='email']",
                    "input[name*='email' i]",
                    "input[id*='email' i]",
                    "input[aria-label*='email' i]",
                ]:
                    if page.locator(selector).count() > 0:
                        try:
                            page.locator(selector).first.fill(self.profile.email)
                            logger.info("Filled Email field using selector '%s'", selector)
                            filled_any = True
                            break
                        except Exception:
                            pass

                # Fill Phone
                for selector in [
                    "input[type='tel']",
                    "input[name*='phone' i]",
                    "input[id*='phone' i]",
                    "input[aria-label*='phone' i]",
                ]:
                    if page.locator(selector).count() > 0:
                        try:
                            page.locator(selector).first.fill(self.profile.phone)
                            logger.info("Filled Phone field using selector '%s'", selector)
                            filled_any = True
                            break
                        except Exception:
                            pass

                # Fill LinkedIn URL
                for selector in [
                    "input[name*='linkedin' i]",
                    "input[id*='linkedin' i]",
                ]:
                    if page.locator(selector).count() > 0:
                        try:
                            page.locator(selector).first.fill(self.profile.linkedin_url)
                            logger.info("Filled LinkedIn URL field")
                            filled_any = True
                            break
                        except Exception:
                            pass

                # Fill Textarea / Essay
                for selector in [
                    "textarea[name*='cover' i]",
                    "textarea[name*='why' i]",
                    "textarea[id*='cover' i]",
                    "textarea",
                ]:
                    if page.locator(selector).count() > 0:
                        try:
                            blurb_text = job.fit_blurb or job.cover_note
                            page.locator(selector).first.fill(blurb_text)
                            logger.info("Filled Cover Note textarea field")
                            filled_any = True
                            break
                        except Exception:
                            pass

                # Attach Resume PDF File
                pdf_attached = False
                if os.path.exists(self.resume_pdf_path):
                    for selector in [
                        "input[type='file']",
                        "input[name*='resume' i]",
                        "input[id*='resume' i]",
                        "input[accept*='pdf']",
                    ]:
                        if page.locator(selector).count() > 0:
                            try:
                                page.locator(selector).first.set_input_files(self.resume_pdf_path)
                                logger.info("Attached Resume PDF '%s' to selector '%s'", self.resume_pdf_path, selector)
                                pdf_attached = True
                                break
                            except Exception as e:
                                logger.warning("Could not set input files on '%s': %s", selector, str(e))

                # Screenshot pre-filled page
                os.makedirs("reports/screenshots", exist_ok=True)
                screenshot_path = f"reports/screenshots/prefilled_{job.id}.png"
                page.screenshot(path=screenshot_path)
                logger.info("Pre-filled form screenshot saved to: %s", screenshot_path)

                if not filled_any and not pdf_attached:
                    logger.info("Complex or non-standard form structure on %s. Flagging MANUAL_APPLY_NEEDED.", job.link)
                    browser.close()
                    return False, "MANUAL_APPLY_NEEDED: Non-standard / Custom Form Structure"

                logger.info("Form pre-filling complete! HALTING before submission button for manual review.")
                if pause_seconds > 0:
                    time.sleep(pause_seconds)

                browser.close()
                return True, "DRAFT_PREFILLED_SUCCESS"

            except Exception as e:
                logger.warning("Error during Playwright form pre-fill on %s: %s", job.link, str(e))
                try:
                    os.makedirs("reports/screenshots", exist_ok=True)
                    page.screenshot(path=f"reports/screenshots/fallback_{job.id}.png")
                except Exception:
                    pass
                try:
                    browser.close()
                except Exception:
                    pass
                return False, f"MANUAL_APPLY_NEEDED: {str(e)[:80]}"
