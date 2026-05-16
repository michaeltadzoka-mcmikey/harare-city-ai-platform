# llm_gateway/app/form_continuation.py
"""
Form Continuation Handler for Harare Chatbot
Prevents users from losing form progress when they switch topics
"""

import re
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class FormContinuationHandler:
    """
    Handles form continuation and prevents unwanted context switching.
    
    Workflow:
    1. User starts form (e.g., report issue)
    2. User asks unrelated question (e.g., clinic hours)
    3. Handler detects context switch
    4. Ask user if they want to continue form or abandon it
    5. Resume or exit based on user's choice
    """
    
    # Form-specific configuration
    FORM_CONFIGS = {
        "report_issue_form": {
            "display_name": "Issue Report",
            "continue_triggers": [
                "location", "describe", "urgency", "yes", "confirm",
                "continue", "proceed", "go ahead"
            ],
            "cancel_triggers": [
                "cancel", "stop", "abort", "nevermind", "forget it",
                "no", "quit", "exit"
            ],
            "step_questions": {
                "location": ["where", "location", "address", "place", "area"],
                "description": ["what", "describe", "details", "issue", "problem"],
                "urgency": ["urgent", "important", "priority", "emergency", "how urgent"]
            }
        },
        "business_permit_form": {
            "display_name": "Business Permit Application",
            "continue_triggers": [
                "business", "type", "location", "details", "yes",
                "continue", "proceed"
            ],
            "cancel_triggers": [
                "cancel", "stop", "later", "no", "nevermind"
            ]
        },
        "payment_form": {
            "display_name": "Payment Processing",
            "continue_triggers": [
                "pay", "amount", "method", "yes", "confirm"
            ],
            "cancel_triggers": [
                "cancel", "stop", "no", "abort"
            ]
        }
    }
    
    async def should_continue_form(
        self, 
        message: str, 
        form_context: Dict
    ) -> Dict[str, Any]:
        """
        Determine if message should continue current form or start new context.
        
        Args:
            message: User's current message
            form_context: Current form context from session manager
            
        Returns:
            Dict with continue_form decision, reason, and action
        """
        form_name = form_context.get("form_name")
        current_step = form_context.get("step", 0)
        data_collected = form_context.get("data_collected", {})
        
        if not form_name:
            return {
                "continue_form": False,
                "reason": "No active form",
                "action": "none"
            }
        
        message_lower = message.lower().strip()
        
        # Get form configuration
        form_config = self.FORM_CONFIGS.get(form_name, {})
        
        # STEP 1: Check for explicit cancellation
        if self._is_cancellation(message_lower, form_config):
            logger.info(f"User cancelled form: {form_name}")
            return {
                "continue_form": False,
                "reason": "User cancelled form",
                "action": "cancel_form",
                "response": "Form cancelled. How else can I help you with Harare City services?"
            }
        
        # STEP 2: Check if user is asking about form status
        if self._is_form_status_query(message_lower):
            logger.info(f"User asking about form status: {form_name}")
            return {
                "continue_form": True,
                "reason": "User asking about form status",
                "action": "show_form_summary",
                "response": self._generate_form_summary(form_name, data_collected, current_step)
            }
        
        # STEP 3: Check if message matches current step expectations
        step_name = self._get_step_name(form_name, current_step)
        step_keywords = form_config.get("step_questions", {}).get(step_name, [])
        
        if step_keywords and any(keyword in message_lower for keyword in step_keywords):
            logger.debug(f"Message matches current step keywords for {form_name}")
            return {
                "continue_form": True,
                "reason": "Message matches current step keywords",
                "action": "continue_step"
            }
        
        # STEP 4: Check for general continuation triggers
        continue_triggers = form_config.get("continue_triggers", [])
        if any(trigger in message_lower for trigger in continue_triggers):
            logger.debug(f"Message contains continuation trigger for {form_name}")
            return {
                "continue_form": True,
                "reason": "Message contains continuation trigger",
                "action": "continue_step"
            }
        
        # STEP 5: Check if message seems unrelated to form
        if self._is_topic_switch(message_lower, form_name, form_config):
            logger.info(f"Detected topic switch during {form_name}")
            return {
                "continue_form": False,
                "reason": "Message appears to be a topic switch",
                "action": "ask_confirmation",
                "response": self._get_continuation_prompt(form_name, current_step, data_collected)
            }
        
        # STEP 6: Default - continue form (assume user is answering)
        logger.debug(f"Defaulting to continue form: {form_name}")
        return {
            "continue_form": True,
            "reason": "Default: assuming user is responding to form",
            "action": "continue_step"
        }
    
    def _is_cancellation(self, message: str, form_config: Dict) -> bool:
        """
        Check if user wants to cancel the form.
        
        Args:
            message: User's message (lowercased)
            form_config: Form configuration
            
        Returns:
            True if user wants to cancel
        """
        cancel_triggers = form_config.get("cancel_triggers", [])
        
        # Check for explicit cancellation words
        if any(word in message for word in cancel_triggers):
            return True
        
        # Check for "no" in response to continuation prompt
        if message in ["no", "nope", "nah"]:
            return True
        
        return False
    
    def _is_form_status_query(self, message: str) -> bool:
        """
        Check if user is asking about form status.
        
        Args:
            message: User's message (lowercased)
            
        Returns:
            True if asking about status
        """
        status_phrases = [
            "where am i", "what step", "what's left", "how far",
            "what have i filled", "what did i provide", "show me",
            "what do you have", "what information", "form status"
        ]
        
        return any(phrase in message for phrase in status_phrases)
    
    def _is_topic_switch(
        self, 
        message: str, 
        form_name: str, 
        form_config: Dict
    ) -> bool:
        """
        Detect if message is switching to a different topic.
        
        Args:
            message: User's message (lowercased)
            form_name: Current form name
            form_config: Form configuration
            
        Returns:
            True if topic switch detected
        """
        # Topic switch indicators
        switch_indicators = {
            "report_issue_form": [
                "clinic", "hours", "permit", "license", "payment",
                "bill", "when does", "what are the", "how do i get"
            ],
            "business_permit_form": [
                "report", "pothole", "clinic", "hours", "payment",
                "bill", "water", "garbage"
            ],
            "payment_form": [
                "report", "permit", "clinic", "hours", "application"
            ]
        }
        
        indicators = switch_indicators.get(form_name, [])
        
        # Check if message contains topic switch indicators
        if any(indicator in message for indicator in indicators):
            # But not if it also contains form-related keywords
            form_keywords = form_config.get("continue_triggers", [])
            if not any(keyword in message for keyword in form_keywords):
                return True
        
        # Check for question patterns that suggest new query
        question_patterns = [
            "what is", "what are", "when is", "when are",
            "where is", "where can", "how do i", "how can i",
            "tell me about", "can you tell me"
        ]
        
        if any(pattern in message for pattern in question_patterns):
            # Likely a new question if it doesn't relate to current form
            form_related = any(
                keyword in message 
                for keyword in form_config.get("continue_triggers", [])
            )
            if not form_related:
                return True
        
        return False
    
    def _get_continuation_prompt(
        self, 
        form_name: str, 
        step: int, 
        data_collected: Dict
    ) -> str:
        """
        Get prompt to ask user if they want to continue the form.
        
        Args:
            form_name: Form name
            step: Current step number
            data_collected: Data collected so far
            
        Returns:
            Continuation prompt
        """
        form_config = self.FORM_CONFIGS.get(form_name, {})
        display_name = form_config.get("display_name", "form")
        
        # Build progress summary
        fields_collected = len([v for v in data_collected.values() if v])
        
        prompts = [
            f"You're in the middle of filling a {display_name}. You've provided {fields_collected} field(s). "
            f"Do you want to continue with the form? (Yes/No)",
            
            f"I notice you're asking about something else, but we're still completing your {display_name}. "
            f"Would you like to continue the form or start a new query? (Continue/New Query)",
            
            f"You were filling out a {display_name}. Should we continue with that, or would you like to do something else? (Continue/Something Else)"
        ]
        
        # Choose prompt based on step (vary for user experience)
        return prompts[step % len(prompts)]
    
    def _generate_form_summary(
        self, 
        form_name: str, 
        data_collected: Dict, 
        current_step: int
    ) -> str:
        """
        Generate summary of form progress.
        
        Args:
            form_name: Form name
            data_collected: Data collected so far
            current_step: Current step number
            
        Returns:
            Summary string
        """
        form_config = self.FORM_CONFIGS.get(form_name, {})
        display_name = form_config.get("display_name", "form")
        
        summary_parts = [f"**{display_name} Progress:**\n"]
        
        if data_collected:
            summary_parts.append("**Information Provided:**")
            for field, value in data_collected.items():
                if value:
                    field_display = field.replace("_", " ").title()
                    # Truncate long values
                    display_value = str(value)[:50]
                    if len(str(value)) > 50:
                        display_value += "..."
                    summary_parts.append(f"• {field_display}: {display_value}")
        else:
            summary_parts.append("No information provided yet.")
        
        summary_parts.append(f"\n**Current Step:** {current_step + 1}")
        summary_parts.append("\nReady to continue? Please provide the requested information.")
        
        return "\n".join(summary_parts)
    
    def _get_step_name(self, form_name: str, step: int) -> str:
        """
        Get the name of a form step.
        
        Args:
            form_name: Form name
            step: Step number
            
        Returns:
            Step name
        """
        step_names = {
            "report_issue_form": ["location", "description", "urgency"],
            "business_permit_form": ["business_type", "location", "details"],
            "payment_form": ["amount", "method", "confirmation"]
        }
        
        steps = step_names.get(form_name, [])
        if 0 <= step < len(steps):
            return steps[step]
        
        return "unknown"
    
    def should_save_form_progress(self, form_name: str, step: int) -> bool:
        """
        Determine if form progress should be saved for recovery.
        
        Args:
            form_name: Form name
            step: Current step
            
        Returns:
            True if should save
        """
        # Save progress after first step or every 2 steps
        return step > 0 or step % 2 == 0


# Global form continuation handler instance
form_handler = FormContinuationHandler()