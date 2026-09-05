"""Transactional email adapter.

Two implementations behind one small interface:

* `ResendEmailClient` — sends via Resend (https://resend.com). Used when a
  `CONFIG__RESEND__API_KEY` is present.
* `ConsoleEmailClient` — the dev fallback: it just logs the subject + body (and
  therefore the confirmation / reset link), so the whole email-confirmation and
  password-reset flow works locally with no Resend account.

`build_email_client(config)` picks the right one at bootstrap time.
"""

from __future__ import annotations

import abc

from api.config import Config, ResendConfig
from loguru import logger


class AbstractEmailClient(abc.ABC):
    @abc.abstractmethod
    def send(self, *, to: str, subject: str, html: str, text: str | None = None) -> None:
        """Send one email. Best-effort — must never raise into the caller's
        request path; log and swallow transport errors instead."""


class ConsoleEmailClient(AbstractEmailClient):
    """No-network fallback. Logs the message so links are copy-pasteable in dev."""

    def __init__(self, from_email: str) -> None:
        self._from_email = from_email

    def send(self, *, to: str, subject: str, html: str, text: str | None = None) -> None:
        logger.info(
            "email (console): from={} to={} subject={!r}\n{}",
            self._from_email,
            to,
            subject,
            text or html,
        )


class ResendEmailClient(AbstractEmailClient):
    """Sends through Resend's REST API via the official SDK."""

    def __init__(self, api_key: str, from_email: str) -> None:
        self._api_key = api_key
        self._from_email = from_email

    def send(self, *, to: str, subject: str, html: str, text: str | None = None) -> None:
        try:
            # Imported lazily so the package is only required when Resend is
            # actually configured (dev runs on the console client).
            import resend

            resend.api_key = self._api_key
            params: dict = {
                "from": self._from_email,
                "to": [to],
                "subject": subject,
                "html": html,
            }
            if text:
                params["text"] = text
            resend.Emails.send(params)
            logger.info("email (resend): sent to={} subject={!r}", to, subject)
        except Exception:  # noqa: BLE001 — email is best-effort; never break the request
            logger.exception("email (resend): send failed to={} subject={!r}", to, subject)


def build_email_client(config: Config) -> AbstractEmailClient:
    resend_cfg: ResendConfig = config.resend
    if resend_cfg.api_key:
        return ResendEmailClient(api_key=resend_cfg.api_key, from_email=resend_cfg.from_email)
    logger.warning(
        "email: no CONFIG__RESEND__API_KEY set — using ConsoleEmailClient "
        "(confirmation / reset links will be logged, not emailed)."
    )
    return ConsoleEmailClient(from_email=resend_cfg.from_email)
