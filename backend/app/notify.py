"""Optional email to a citizen who left an address, when their report is assigned or resolved.

Runs only if SMTP_HOST is set. Sending happens in a background task so a slow mail server never delays a request.
"""
import logging
import smtplib
from email.message import EmailMessage

from .config import Settings

log = logging.getLogger("rastescan")

MESSAGES = {
    "assigned": ("Your road report {code} has been assigned",
                 "Good news: report {code} ({hazard}) has been assigned to {assignee}.\n\nTrack it: {link}\n"),
    "verified": ("Your road report {code} is resolved",
                 "Report {code} ({hazard}) has been repaired and the repair photo was checked.\n\nSee before and after: {link}\n"),
    "dismissed": ("Update on your road report {code}",
                  "Report {code} was closed without repair. Reason: {reason}\n\nDetails: {link}\n"),
}


def enabled(settings: Settings) -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def report_link(settings: Settings, code: str) -> str:
    return f"{settings.public_base_url}/#/r/{code}" if settings.public_base_url else f"#/r/{code}"


def send(settings: Settings, to: str, kind: str, **fields) -> None:
    if not enabled(settings) or kind not in MESSAGES or not to:
        return
    subject, body = MESSAGES[kind]
    fields.setdefault("link", report_link(settings, fields.get("code", "")))
    msg = EmailMessage()
    msg["From"], msg["To"] = settings.smtp_from, to
    msg["Subject"] = subject.format(**fields)
    msg.set_content(body.format(**fields) + f"\n— {settings.site_name}\nThis is an automatic message.")
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException):
        log.exception("could not send %s email for %s", kind, fields.get("code"))
