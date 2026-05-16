"""
Harare City Council Chatbot – Custom Actions
RASA 3.6.15 compatible
Spec: Unified System Doc v3.2 §4.3 / RASA Integration Doc v1.0

Changes from original:
  - Removed all non-reporting actions (water services, etc.) – handled by LLM Gateway + RAG.
  - Dead-letter queue now writes to PostgreSQL table (file fallback retained for safety).
  - Rate limit counter now only increments on SUCCESSFUL submission, not on failures caused
    by gateway outage (prevents penalising citizens for infrastructure issues).
  - Idempotency-Key header added to Gateway POST (doc §4.3).
  - Enhanced logging throughout.
  - Updated status endpoint path to /api/reports/status (aligned with Gateway).
  - [FIX] Report submission endpoint changed from /api/reports/confirmed to /webhook/rasa.
  - [FIX] Reference ID now displayed directly in utterance (not via template) to ensure visibility.
  - [REMOVED] All Redis auto-start code - using InMemoryTrackerStore (RASA default).
"""

import logging
import re
import time
import os
import json
import uuid
from typing import Any, Dict, List, Text, Optional
from datetime import datetime, timezone, timedelta

import requests
from rasa_sdk import Action, FormValidationAction, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, ActiveLoop
from rasa_sdk.types import DomainDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration – all values read from environment variables.
# See RASA Integration Doc §9 for the full list.
# ---------------------------------------------------------------------------
LLM_GATEWAY_URL: str = os.getenv("LLM_GATEWAY_URL", "http://localhost:8001")
DASHBOARD_URL: str = os.getenv("DASHBOARD_URL", "http://localhost:5000")
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
DASHBOARD_API_KEY: str = os.getenv("DASHBOARD_API_KEY", "")

# Doc §3.5: RASA posts the confirmed event to this LLM Gateway endpoint.
REPORT_ENDPOINT: str = f"{LLM_GATEWAY_URL}/webhook/rasa"
# Doc §4.5: Status checks hit the Dashboard's public API directly via Gateway.
STATUS_ENDPOINT: str = f"{DASHBOARD_URL}/api/reports/status"

# Retry / timeout constants (doc §3.8)
MAX_RETRIES: int = 5
RETRY_DELAYS: List[int] = [5, 10, 20, 30, 40]   # Increased for slow hardware
REQUEST_TIMEOUT: int = 60                        # Increased from 10 to 60 seconds

# Rate limiting (doc §2.7: max 3 SUCCESSFUL submissions per session per hour)
MAX_REPORTS_PER_SESSION_PER_HOUR: int = 3

# Minimum description length (doc §3.3)
MIN_DESCRIPTION_LENGTH: int = 10

# Dead-letter storage paths
DEAD_LETTER_LOG: str = os.getenv("DEAD_LETTER_LOG", "dead_letter_queue.jsonl")

# Optional PostgreSQL dead-letter table (preferred over file in production)
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# Known Harare suburbs/wards for location validation (doc §3.2)
KNOWN_SUBURBS: frozenset = frozenset({
    "mbare", "budiriro", "highfield", "kuwadzana", "warren park",
    "glen view", "glenview", "dzivarasekwa", "tafara", "mabvuku",
    "hatfield", "borrowdale", "mount pleasant", "avondale", "eastlea",
    "waterfalls", "greendale", "msasa", "workington", "southerton",
    "belvedere", "meyrick park", "strathaven", "highlands", "vainona",
    "chitungwiza", "zengeza", "seke", "st marys", "saint marys",
})

# Spam blacklist file path (doc §2.7.1)
SPAM_BLACKLIST_FILE: str = os.getenv("SPAM_BLACKLIST_FILE", "spam_blacklist.txt")

# ---------------------------------------------------------------------------
# Spam Blacklist Loader
# ---------------------------------------------------------------------------

def load_spam_blacklist() -> List[str]:
    """Load spam keywords from file; fall back to safe defaults."""
    defaults = [
        "bomb", "kill", "terrorist", "hack", "attack", "explosive",
        "fuck", "shit", "mboro", "idiot", "stupid",
    ]
    try:
        if os.path.exists(SPAM_BLACKLIST_FILE):
            with open(SPAM_BLACKLIST_FILE, "r", encoding="utf-8") as f:
                words = [line.strip().lower() for line in f if line.strip()]
                if words:
                    logger.info(f"Spam blacklist loaded: {len(words)} entries")
                    return words
    except Exception as exc:
        logger.warning(f"Could not load spam blacklist from {SPAM_BLACKLIST_FILE}: {exc}")
    logger.info("Using default spam blacklist")
    return defaults

SPAM_BLACKLIST: List[str] = load_spam_blacklist()

# ---------------------------------------------------------------------------
# Spam Detection  (doc §3.3)
# Returns {"is_spam": bool, "reason": str | None}
# The reason is stored in the payload for admin false-positive review (doc §2.7.3).
# Zero-rejection principle: spam-flagged reports are accepted, not discarded.
# ---------------------------------------------------------------------------

def check_spam(text: str) -> Dict[str, Any]:
    text_lower = text.lower()

    # 1. Blacklist keyword match
    for word in SPAM_BLACKLIST:
        if word in text_lower:
            return {"is_spam": True, "reason": f"blacklist_match:{word}"}

    # 2. Repeated character gibberish (>10 consecutive identical chars)
    if re.search(r"(.)\1{10,}", text):
        return {"is_spam": True, "reason": "gibberish:repeated_chars"}

    # 3. Low alphabetic / readable character ratio (< 30 %)
    readable = sum(c.isalpha() or c.isspace() or c in ".,!?-'" for c in text)
    if len(text) > 5 and (readable / len(text)) < 0.30:
        return {"is_spam": True, "reason": "gibberish:non_alphabetic_ratio"}

    # 4. HTML / script injection attempt
    if re.search(r"<[^>]+>|javascript:", text, re.IGNORECASE):
        return {"is_spam": True, "reason": "injection:html_or_script"}

    return {"is_spam": False, "reason": None}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_location_known(location: str) -> bool:
    """Check whether the location string matches a known Harare suburb."""
    return location.lower().strip() in KNOWN_SUBURBS

def get_recent_submission_count(tracker: Tracker) -> int:
    """
    Doc §2.7: Count SUCCESSFUL submissions in the last hour for this session.
    Reads the 'submission_timestamps' slot (JSON list of ISO-8601 strings).
    """
    raw = tracker.get_slot("submission_timestamps")
    if not raw:
        return 0
    try:
        timestamps: List[str] = json.loads(raw)
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        return sum(
            1 for ts in timestamps
            if datetime.fromisoformat(ts) > one_hour_ago
        )
    except Exception as exc:
        logger.warning(f"Could not parse submission_timestamps: {exc}")
        return 0

def append_submission_timestamp(tracker: Tracker) -> str:
    """
    Return a JSON string of recent timestamps (last hour) with now() appended.
    Called ONLY on successful submission to avoid penalising citizens for
    gateway outages.
    """
    raw = tracker.get_slot("submission_timestamps")
    existing: List[str] = []
    if raw:
        try:
            existing = json.loads(raw)
        except Exception:
            existing = []

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = [
        ts for ts in existing
        if datetime.fromisoformat(ts) > one_hour_ago
    ]
    recent.append(datetime.now(timezone.utc).isoformat())
    return json.dumps(recent)

def log_dead_letter_file(payload: Dict, reason: str) -> None:
    """File-based dead-letter fallback (doc §3.8). Used when DB is unavailable."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "reason": reason,
        "payload": payload,
    }
    try:
        with open(DEAD_LETTER_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info(f"Dead-letter file entry written. Reason: {reason}")
    except Exception as exc:
        logger.error(f"Could not write dead-letter file entry: {exc}")

def log_dead_letter_db(payload: Dict, reason: str) -> bool:
    """
    Preferred dead-letter storage: PostgreSQL table.
    Returns True on success so the caller can skip the file fallback.
    Table DDL (run once):
        CREATE TABLE IF NOT EXISTS rasa_dead_letter_queue (
            id          SERIAL PRIMARY KEY,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            reason      TEXT        NOT NULL,
            payload     JSONB       NOT NULL,
            retried     BOOLEAN     NOT NULL DEFAULT FALSE,
            retry_at    TIMESTAMPTZ
        );
    """
    if not DATABASE_URL:
        return False
    try:
        import psycopg2  # type: ignore
        conn = psycopg2.connect(DATABASE_URL)
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rasa_dead_letter_queue (reason, payload, retry_at)
                    VALUES (%s, %s, NOW() + INTERVAL '1 hour')
                    """,
                    (reason, json.dumps(payload)),
                )
        conn.close()
        logger.info(f"Dead-letter DB entry written. Reason: {reason}")
        return True
    except Exception as exc:
        logger.error(f"Could not write dead-letter DB entry: {exc}")
        return False

def log_dead_letter(payload: Dict, reason: str) -> None:
    """Try DB first, fall back to file. Both may be written if DB write fails."""
    if not log_dead_letter_db(payload, reason):
        log_dead_letter_file(payload, reason)

def cleared_form_slots() -> List[Dict[Text, Any]]:
    """Return SlotSet events that reset all report form slots to None."""
    return [
        SlotSet("report_description", None),
        SlotSet("report_location", None),
        SlotSet("report_landmark", None),
        SlotSet("spam_flag", None),
        SlotSet("spam_reason", None),
        SlotSet("location_known", None),
        SlotSet("report_confirmed", None),
    ]

# ---------------------------------------------------------------------------
# Form Validation  (doc §3.2 – §3.4)
# ---------------------------------------------------------------------------

class ValidateReportForm(FormValidationAction):

    def name(self) -> Text:
        return "validate_report_form"

    # ── Description slot ────────────────────────────────────────────────────
    def validate_report_description(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:

        if not slot_value or not isinstance(slot_value, str):
            dispatcher.utter_message(response="utter_ask_report_description")
            return {"report_description": None}

        text = slot_value.strip()

        if len(text) < MIN_DESCRIPTION_LENGTH:
            dispatcher.utter_message(
                text=(
                    f"Please provide more detail (at least {MIN_DESCRIPTION_LENGTH} "
                    "characters) so we can log your issue accurately."
                )
            )
            return {"report_description": None}

        spam_result = check_spam(text)
        if spam_result["is_spam"]:
            logger.warning(
                f"Spam flagged for session {tracker.sender_id}: {spam_result['reason']}"
            )
            dispatcher.utter_message(response="utter_spam_warning")
            # Zero-rejection: accept but flag (doc §3.3)
            return {
                "report_description": text,
                "spam_flag": True,
                "spam_reason": spam_result["reason"],
            }

        return {"report_description": text, "spam_flag": False, "spam_reason": None}

    # ── Location slot ────────────────────────────────────────────────────────
    def validate_report_location(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:

        if not slot_value or not isinstance(slot_value, str):
            dispatcher.utter_message(response="utter_ask_report_location")
            return {"report_location": None}

        location = slot_value.strip()

        if not is_location_known(location):
            # Zero-rejection: proceed but note discrepancy (doc §3.2)
            logger.info(
                f"Unknown location '{location}' for session {tracker.sender_id}. "
                "Proceeding with location_known=False."
            )
            dispatcher.utter_message(response="utter_location_clarification")
            return {"report_location": location, "location_known": False}

        return {"report_location": location, "location_known": True}

    # ── Landmark slot ────────────────────────────────────────────────────────
    def validate_report_landmark(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:

        if not slot_value or not isinstance(slot_value, str):
            dispatcher.utter_message(response="utter_ask_report_landmark")
            return {"report_landmark": None}

        landmark = slot_value.strip()
        no_landmark_keywords = {
            "none", "no landmark", "n/a", "na", "nothing", "no",
            "i don't know", "i do not know", "nothing nearby",
            "i cannot think of one",
        }
        if landmark.lower() in no_landmark_keywords:
            landmark = "Not provided"

        return {"report_landmark": landmark}

# ---------------------------------------------------------------------------
# Submit Report  (doc §3.4, §3.5, §3.8)
# ---------------------------------------------------------------------------

class ActionSubmitReport(Action):

    def name(self) -> Text:
        return "action_submit_report"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:

        session_id = tracker.sender_id

        # ── Per-hour rate limiting (doc §2.7) ────────────────────────────────
        # Only SUCCESSFUL submissions count toward the limit.
        if get_recent_submission_count(tracker) >= MAX_REPORTS_PER_SESSION_PER_HOUR:
            logger.warning(
                f"Rate limit hit for session {session_id}. "
                f"Max {MAX_REPORTS_PER_SESSION_PER_HOUR} per hour exceeded."
            )
            dispatcher.utter_message(response="utter_rate_limit_warning")
            return cleared_form_slots()

        # ── Read collected slot values ────────────────────────────────────────
        description: Optional[str] = tracker.get_slot("report_description")
        location: Optional[str] = tracker.get_slot("report_location")
        landmark: str = tracker.get_slot("report_landmark") or "Not provided"
        spam_flag: bool = tracker.get_slot("spam_flag") or False
        spam_reason: Optional[str] = tracker.get_slot("spam_reason")

        if not description or not location:
            logger.error(
                f"Missing required slot values for session {session_id}. "
                f"description={bool(description)}, location={bool(location)}"
            )
            dispatcher.utter_message(
                text=(
                    "Something went wrong retrieving your report details. "
                    "Please try again from the beginning."
                )
            )
            return cleared_form_slots()

        # ── Build report_confirmed event payload (doc §3.5 / §8.1) ───────────
        payload = {
            "event_type": "report_confirmed",
            "payload": {
                "raw_text": description,
                "landmark": landmark,
                "citizen_session_id": session_id,
                "spam_flag": spam_flag,
                "spam_reason": spam_reason if spam_flag else None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

        # Idempotency key: stable per submission attempt (doc §4.3).
        # Using a UUID v4 per action run; the Gateway can safely retry with
        # the same key without creating duplicate reports.
        idempotency_key = str(uuid.uuid4())

        headers = {
            "Content-Type": "application/json",
            "X-API-Key": LLM_API_KEY,
            "Idempotency-Key": idempotency_key,
        }

        reference_id: Optional[str] = None
        gateway_reachable: bool = False

        # ── Exponential backoff retry loop (doc §3.8: 5s, 10s, 20s, 30s, 40s) ─
        for attempt, delay in enumerate(RETRY_DELAYS[:MAX_RETRIES], start=1):
            try:
                logger.info(
                    f"[{session_id}] Submit attempt {attempt}/{MAX_RETRIES} "
                    f"to {REPORT_ENDPOINT} (key={idempotency_key})"
                )
                resp = requests.post(
                    REPORT_ENDPOINT,
                    json=payload,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )

                if resp.status_code in (200, 201, 202):
                    gateway_reachable = True
                    reference_id = resp.json().get("reference_id")
                    logger.info(
                        f"[{session_id}] Report submitted. "
                        f"ref={reference_id}, status={resp.status_code}"
                    )
                    break
                else:
                    logger.warning(
                        f"[{session_id}] Gateway returned {resp.status_code} "
                        f"on attempt {attempt}."
                    )

            except requests.exceptions.Timeout:
                logger.warning(
                    f"[{session_id}] Timeout on attempt {attempt} "
                    f"(>{REQUEST_TIMEOUT}s)."
                )
            except requests.exceptions.ConnectionError as exc:
                logger.warning(
                    f"[{session_id}] Connection error on attempt {attempt}: {exc}"
                )
            except Exception as exc:
                logger.error(
                    f"[{session_id}] Unexpected error on attempt {attempt}: {exc}"
                )

            if attempt < MAX_RETRIES:
                logger.info(f"[{session_id}] Waiting {delay}s before retry…")
                time.sleep(delay)

        # ── Success path ──────────────────────────────────────────────────────
        if gateway_reachable and reference_id:
            # Rate-limit counter only incremented on success (fix from original).
            new_timestamps = append_submission_timestamp(tracker)
            # --- FIX: Use direct text instead of template to ensure reference ID is shown ---
            dispatcher.utter_message(
                text=f"✅ Your report has been received!\n\nReference Number: **{reference_id}**\n\nSend this number anytime to check your report status. Thank you for helping improve Harare!"
            )
            return (
                [
                    SlotSet("submission_reference_id", reference_id),
                    SlotSet("submission_timestamps", new_timestamps),
                    SlotSet("gateway_unreachable", False),
                ]
                + cleared_form_slots()
            )

        # ── Dead-letter path (doc §3.8) ───────────────────────────────────────
        # DO NOT show a locally-generated reference ID – the citizen is told
        # their reference will follow once connectivity is restored (doc §3.8).
        reason = (
            "gateway_unreachable"
            if not gateway_reachable
            else "no_reference_returned"
        )
        log_dead_letter(payload, reason)
        logger.error(
            f"[{session_id}] Report dead-lettered. Reason: {reason}. "
            f"idempotency_key={idempotency_key}"
        )

        dispatcher.utter_message(response="utter_report_submitted_delayed")
        # Rate-limit counter NOT incremented – the submission did not succeed.
        return (
            [SlotSet("gateway_unreachable", True)]
            + cleared_form_slots()
        )

# ---------------------------------------------------------------------------
# Check Report Status  (doc §4.5, §5.2)
# ---------------------------------------------------------------------------

class ActionCheckReportStatus(Action):

    def name(self) -> Text:
        return "action_check_report_status"

    # Reference ID regex pattern (doc Appendix A)
    REF_PATTERN = re.compile(r"HCC-RPT-\d{4}-\d{5}", re.IGNORECASE)

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:

        reference_id: Optional[str] = tracker.get_slot("reference_id")

        # Fallback: extract reference ID from raw message text (doc §4.5)
        if not reference_id:
            last_msg = tracker.latest_message.get("text", "")
            match = self.REF_PATTERN.search(last_msg)
            if match:
                reference_id = match.group(0).upper()
                logger.info(
                    f"[{tracker.sender_id}] Reference ID extracted from raw text: "
                    f"{reference_id}"
                )

        if not reference_id:
            dispatcher.utter_message(response="utter_ask_reference_id")
            return []

        # Validate format before hitting the API
        reference_id = reference_id.strip().upper()
        if not re.match(r"^HCC-RPT-\d{4}-\d{5}$", reference_id):
            dispatcher.utter_message(
                text=(
                    f"The reference number '{reference_id}' does not look right. "
                    "It should follow the format HCC-RPT-YYYY-XXXXX, "
                    "for example HCC-RPT-2026-00001. Please check and try again."
                )
            )
            return [SlotSet("reference_id", None)]

        try:
            headers = {"X-API-Key": DASHBOARD_API_KEY}
            resp = requests.get(
                f"{STATUS_ENDPOINT}?ref={reference_id}",
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "Unknown")
                description = data.get("status_description", "")
                last_update = data.get("last_updated", "")

                # Duplicate notice (doc §5.3)
                if data.get("duplicate_flag") and data.get("duplicate_of"):
                    original = data["duplicate_of"]
                    dispatcher.utter_message(
                        text=(
                            f"Your report {reference_id} is a duplicate of "
                            f"report {original}. Status updates will be reflected "
                            f"on the original report.\n\n"
                            f"Current status: **{status}**."
                            + (f"\n{description}" if description else "")
                        )
                    )
                else:
                    msg = (
                        f"📋 Report Status\n\n"
                        f"Reference: {reference_id}\n"
                        f"Status: **{status}**"
                    )
                    if description:
                        msg += f"\nDetails: {description}"
                    if last_update:
                        msg += f"\nLast updated: {last_update}"
                    dispatcher.utter_message(text=msg)

                return [SlotSet("reference_id", reference_id)]

            elif resp.status_code == 404:
                logger.info(
                    f"[{tracker.sender_id}] Reference {reference_id} not found."
                )
                dispatcher.utter_message(response="utter_reference_not_found")
                return [SlotSet("reference_id", None)]

            else:
                logger.error(
                    f"[{tracker.sender_id}] Status API returned "
                    f"{resp.status_code} for {reference_id}."
                )
                dispatcher.utter_message(
                    text=(
                        "We are unable to retrieve your report status right now. "
                        "Please try again shortly or contact digital@harare.gov.zw"
                    )
                )
                return []

        except requests.exceptions.ConnectionError:
            logger.error(
                f"[{tracker.sender_id}] Cannot connect to Dashboard for "
                f"ref: {reference_id}"
            )
            dispatcher.utter_message(
                text=(
                    "Our status service is temporarily unavailable. "
                    "Please try again or contact digital@harare.gov.zw"
                )
            )
            return []

        except Exception as exc:
            logger.error(
                f"[{tracker.sender_id}] Unexpected error checking status "
                f"for {reference_id}: {exc}"
            )
            dispatcher.utter_message(
                text="An unexpected error occurred. Please try again."
            )
            return []

# ---------------------------------------------------------------------------
# Handle Restart  (doc §3.4)
# ---------------------------------------------------------------------------

class ActionHandleRestart(Action):

    def name(self) -> Text:
        return "action_handle_restart"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        logger.info(f"[{tracker.sender_id}] Report restarted by citizen.")
        # utter_report_restarted is fired by the rule after this action.
        return cleared_form_slots() + [ActiveLoop(None)]

# ---------------------------------------------------------------------------
# Handle Cancel  (doc §3.4)
# ---------------------------------------------------------------------------

class ActionHandleCancel(Action):

    def name(self) -> Text:
        return "action_handle_cancel"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        logger.info(f"[{tracker.sender_id}] Report cancelled by citizen.")
        # utter_report_cancelled is fired by the rule after this action.
        return cleared_form_slots() + [ActiveLoop(None)]

# ---------------------------------------------------------------------------
# NEW: Activate Form from Gateway Trigger
# ---------------------------------------------------------------------------

class ActionActivateTriggerForm(Action):
    def name(self) -> str:
        return "action_activate_trigger_form"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        # Read the trigger_form from the metadata of the incoming message
        metadata = tracker.latest_message.get('metadata')
        form_name = metadata.get('trigger_form') if metadata else None
        if form_name:
            logger.info(f"Activating form {form_name} via gateway trigger")
            return [ActiveLoop(form_name)]
        logger.warning("No trigger_form in metadata, cannot activate form")
        dispatcher.utter_message(text="Sorry, I couldn't start the form. Please try again.")
        return []