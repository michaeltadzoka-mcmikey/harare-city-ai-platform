"""
Complete Report Issue Form with Ticket Generation
Implements FIX 3.1 from the comprehensive documentation
"""

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, ActiveLoop, AllSlotsReset, FollowupAction
from rasa_sdk.types import DomainDict
from typing import Any, Text, Dict, List, Optional
import logging
import datetime
import random
import sqlite3
import json
import hashlib
import os
import re

logger = logging.getLogger(__name__)

# Database path - adjust based on your setup
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "municipal_data.db")

class ValidateReportIssueForm(FormValidationAction):
    """Complete report issue form with ticket generation."""
    
    def name(self) -> Text:
        return "validate_report_issue_form"
    
    @staticmethod
    def required_slots(tracker: Tracker) -> List[Text]:
        """Dynamic slot requirements."""
        required = []
        
        # Always start with confirmation
        if tracker.get_slot("report_confirm_proceed") is None:
            required.append("report_confirm_proceed")
        
        # If user doesn't want to report, stop
        if tracker.get_slot("report_confirm_proceed") == False:
            return []
        
        # Add form slots in order
        slots_in_order = ["report_location", "report_description", "report_urgency", "confirm_submission"]
        
        for slot in slots_in_order:
            if tracker.get_slot(slot) is None:
                required.append(slot)
        
        return required
    
    async def validate_report_confirm_proceed(
        self,
        value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate if user wants to proceed."""
        intent = tracker.latest_message.get("intent", {}).get("name")
        
        if intent == "affirm":
            dispatcher.utter_message(
                text="Great! I'll help you submit a formal report to Harare City Council. "
                     "I need a few details to create your report."
            )
            return {"report_confirm_proceed": True}
        
        elif intent == "deny":
            dispatcher.utter_message(response="utter_report_cancelled")
            return {
                "report_confirm_proceed": False,
                "requested_slot": None
            }
        
        dispatcher.utter_message(text="Please confirm: Do you want to file a formal report? (Yes/No)")
        return {"report_confirm_proceed": None}
    
    async def validate_report_location(
        self,
        value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate and normalize location."""
        if not value:
            return {"report_location": None}
        
        location = str(value).strip()
        
        # Check for skip intent
        intent = tracker.latest_message.get("intent", {}).get("name")
        if intent == "skip":
            validation_attempts = tracker.get_slot("validation_attempts") or 0
            if validation_attempts > 0:
                return {
                    "report_location": location,
                    "validation_attempts": 0
                }
        
        # Vague terms check
        vague_terms = ["here", "there", "somewhere", "my area", "near", "around", "over there", "my place"]
        is_vague = any(term in location.lower() for term in vague_terms)
        
        # Length check
        is_too_short = len(location) < 10
        
        # Get validation attempts
        attempts = tracker.get_slot("validation_attempts") or 0
        
        if is_vague or is_too_short:
            if attempts < 2:
                dispatcher.utter_message(response="utter_location_too_vague")
                dispatcher.utter_message(response="utter_clarify_or_skip")
                return {
                    "report_location": None,
                    "validation_attempts": attempts + 1
                }
            else:
                # After 2 attempts, accept what they have
                dispatcher.utter_message(text="Using the location as provided.")
                return {
                    "report_location": location,
                    "validation_attempts": 0
                }
        
        # Check if it mentions Harare or has street/suburb context
        has_context = any(word in location.lower() for word in 
                         ["harare", "suburb", "ave", "avenue", "street", "road", "drive", "way"])
        
        if not has_context and attempts == 0:
            dispatcher.utter_message(
                text="Is this location in Harare? Please include the suburb or area name."
            )
            return {
                "report_location": None,
                "validation_attempts": 1
            }
        
        # Valid location
        dispatcher.utter_message(text=f"📍 Location noted: {location}")
        return {
            "report_location": location,
            "validation_attempts": 0
        }
    
    async def validate_report_description(
        self,
        value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate description with relevance check."""
        if not value:
            return {"report_description": None}
        
        description = str(value).strip()
        
        # Check for skip intent
        intent = tracker.latest_message.get("intent", {}).get("name")
        if intent == "skip":
            validation_attempts = tracker.get_slot("validation_attempts") or 0
            if validation_attempts > 0:
                return {
                    "report_description": description,
                    "validation_attempts": 0
                }
        
        # Length check
        is_too_short = len(description) < 15
        
        # Word count check
        word_count = len(description.split())
        has_few_words = word_count < 3
        
        # Get validation attempts
        attempts = tracker.get_slot("validation_attempts") or 0
        
        if is_too_short or has_few_words:
            if attempts < 2:
                dispatcher.utter_message(response="utter_description_too_short")
                dispatcher.utter_message(response="utter_clarify_or_skip")
                return {
                    "report_description": None,
                    "validation_attempts": attempts + 1
                }
            else:
                # Accept after 2 attempts
                dispatcher.utter_message(text="Using the description as provided.")
                return {
                    "report_description": description,
                    "validation_attempts": 0
                }
        
        # Valid description
        return {
            "report_description": description,
            "validation_attempts": 0
        }
    
    async def validate_report_urgency(
        self,
        value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate urgency level."""
        if not value:
            return {"report_urgency": None}
        
        urgency = str(value).lower().strip()
        
        # Normalize urgency values
        urgency_mapping = {
            "low": "low",
            "medium": "medium",
            "high": "high",
            "emergency": "emergency",
            "l": "low",
            "m": "medium",
            "h": "high",
            "e": "emergency",
            "not urgent": "low",
            "somewhat urgent": "medium",
            "very urgent": "high",
            "critical": "emergency",
            "minor": "low",
            "moderate": "medium",
            "severe": "high",
            "urgent": "high",
            "asap": "high",
            "immediate": "emergency"
        }
        
        # Try to map the value
        normalized = urgency_mapping.get(urgency)
        
        if normalized:
            # Show confirmation
            urgency_descriptions = {
                "low": "Not urgent - will be addressed in regular schedule",
                "medium": "Moderate urgency - standard response time",
                "high": "Urgent - prioritized response",
                "emergency": "Emergency - immediate attention required"
            }
            
            dispatcher.utter_message(
                text=f"⚠️ Urgency level set to: {normalized.title()} "
                     f"({urgency_descriptions[normalized]})"
            )
            return {"report_urgency": normalized}
        
        # Try to extract from text
        for key, val in urgency_mapping.items():
            if key in urgency:
                return {"report_urgency": val}
        
        # Invalid urgency
        dispatcher.utter_message(
            text="Please specify the urgency as: Low, Medium, High, or Emergency"
        )
        return {"report_urgency": None}
    
    async def validate_confirm_submission(
        self,
        value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Final confirmation before submission."""
        intent = tracker.latest_message.get("intent", {}).get("name")
        
        if intent == "affirm":
            return {
                "confirm_submission": True,
                "requested_slot": None
            }
        else:
            # User cancelled
            dispatcher.utter_message(text="Report cancelled. How else can I help?")
            return {
                "confirm_submission": False,
                "report_confirm_proceed": False,
                "requested_slot": None
            }


class ActionSubmitReport(Action):
    """Submit report and generate ticket - implements complete ticket generation."""
    
    def name(self) -> Text:
        return "action_submit_report"
    
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        
        # Check if submission was confirmed
        if tracker.get_slot("confirm_submission") != True:
            return [AllSlotsReset(), ActiveLoop(None)]
        
        # Get all slot values
        location = tracker.get_slot("report_location")
        description = tracker.get_slot("report_description")
        urgency = tracker.get_slot("report_urgency")
        
        # Generate unique ticket ID
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        random_code = random.randint(1000, 9999)
        ticket_id = f"TICKET-{timestamp}-{random_code}"
        
        # Determine department based on description
        department = self._determine_department(description)
        
        # Create report data
        report_data = {
            "ticket_id": ticket_id,
            "user_id": tracker.sender_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "location": location,
            "description": description,
            "urgency": urgency,
            "status": "submitted",
            "department": department,
            "created_at": datetime.datetime.now().isoformat()
        }
        
        # Save to database
        saved = self._save_to_database(report_data)
        
        if saved:
            # Generate summary
            summary = self._generate_summary(report_data)
            dispatcher.utter_message(text=summary)
            
            # Also send ticket info separately
            dispatcher.utter_message(
                text=f"📋 **Your Ticket ID:** {ticket_id}\n"
                     f"🔍 **Check status anytime:** Say 'Check ticket {ticket_id}'"
            )
            
            logger.info(f"Report submitted successfully: {ticket_id}")
            
            return [
                SlotSet("reference_number", ticket_id),
                SlotSet("ticket_id", ticket_id),
                SlotSet("report_status", "submitted"),
                AllSlotsReset()
            ]
        else:
            dispatcher.utter_message(
                text="⚠️ Technical error submitting report. Please try again later."
            )
            return [AllSlotsReset()]
    
    def _determine_department(self, description: str) -> str:
        """Determine which department should handle this report."""
        description_lower = description.lower()
        
        departments = {
            "roads": ["pothole", "road", "street", "bridge", "drain", "pavement", "traffic"],
            "water": ["water", "leak", "pipe", "flood", "sewage", "drainage", "burst"],
            "electricity": ["electricity", "power", "light", "pole", "wire", "outage"],
            "waste": ["garbage", "waste", "rubbish", "dump", "litter", "bin", "refuse"],
            "health": ["clinic", "hospital", "sanitation", "toilet", "clean", "hygiene"],
            "parks": ["park", "grass", "tree", "garden", "playground", "recreation"]
        }
        
        for dept, keywords in departments.items():
            if any(keyword in description_lower for keyword in keywords):
                return dept
        
        return "general"
    
    def _save_to_database(self, report_data: Dict) -> bool:
        """Save report to database."""
        try:
            # Ensure database and table exist
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Create reports table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    location TEXT NOT NULL,
                    description TEXT NOT NULL,
                    urgency TEXT NOT NULL,
                    status TEXT DEFAULT 'submitted',
                    department TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert report
            cursor.execute("""
                INSERT INTO reports 
                (ticket_id, user_id, location, description, urgency, department, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                report_data["ticket_id"],
                report_data["user_id"],
                report_data["location"],
                report_data["description"],
                report_data["urgency"],
                report_data.get("department", "general"),
                report_data["created_at"]
            ))
            
            conn.commit()
            
            # Also create ticket tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ticket_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id TEXT NOT NULL,
                    update_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    updated_by TEXT DEFAULT 'system',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ticket_id) REFERENCES reports (ticket_id)
                )
            """)
            
            # Log initial update
            cursor.execute("""
                INSERT INTO ticket_updates (ticket_id, update_type, description, updated_by)
                VALUES (?, 'created', 'Report submitted via chatbot', 'system')
            """, (report_data["ticket_id"],))
            
            conn.commit()
            conn.close()
            
            # Also log to JSON file for backup
            log_dir = os.path.join(os.path.dirname(__file__), "..", "simulation_logs")
            os.makedirs(log_dir, exist_ok=True)
            
            with open(os.path.join(log_dir, "reports.jsonl"), "a") as f:
                f.write(json.dumps(report_data) + "\n")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save to database: {e}")
            return False
    
    def _generate_summary(self, report_data: Dict) -> str:
        """Generate user-friendly summary."""
        urgency_icons = {
            "low": "🟢",
            "medium": "🟡", 
            "high": "🟠",
            "emergency": "🔴"
        }
        
        icon = urgency_icons.get(report_data["urgency"], "⚪")
        
        return f"""
✅ **Report Submitted Successfully!**

{icon} **Ticket Summary:**
• **Ticket ID:** {report_data['ticket_id']}
• **Location:** {report_data['location']}
• **Issue:** {report_data['description'][:100]}{'...' if len(report_data['description']) > 100 else ''}
• **Urgency:** {report_data['urgency'].title()}
• **Department:** {report_data.get('department', 'General').title()}
• **Status:** Submitted
• **Time:** {datetime.datetime.now().strftime('%H:%M %d/%m/%Y')}

📋 **Next Steps:**
1. Our {report_data.get('department', 'relevant')} team will review within 24-48 hours
2. You'll receive updates on this ticket
3. Check status anytime with: "Check ticket {report_data['ticket_id']}"

📞 **Emergency Contact:** 04-700600 (for urgent matters only)

Thank you for helping keep Harare clean and safe!
"""