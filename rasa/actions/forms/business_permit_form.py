# rasa/actions/forms/business_permit_form.py
from rasa_sdk.forms import FormValidationAction
from typing import Text, Dict, Any, List
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk import Tracker

class ValidateBusinessPermitForm(FormValidationAction):
    """Validate business permit form slots."""
    
    def name(self) -> Text:
        return "validate_business_permit_form"
    
    async def validate_permit_type(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Validate permit_type."""
        
        valid_types = ["business", "construction", "event"]
        
        if slot_value.lower() in valid_types:
            return {"permit_type": slot_value}
        else:
            dispatcher.utter_message(
                text="Please choose: business, construction, or event permit."
            )
            return {"permit_type": None}
    
    async def validate_business_type(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Validate business_type."""
        
        permit_type = tracker.get_slot("permit_type")
        
        if permit_type == "business":
            valid_types = ["restaurant", "retail", "manufacturing", "service"]
        elif permit_type == "construction":
            valid_types = ["residential", "commercial", "renovation"]
        elif permit_type == "event":
            valid_types = ["wedding", "concert", "festival", "protest"]
        else:
            valid_types = []
        
        if slot_value.lower() in valid_types:
            return {"business_type": slot_value}
        else:
            dispatcher.utter_message(
                text=f"For {permit_type} permits, valid types are: {', '.join(valid_types)}"
            )
            return {"business_type": None}
    
    async def validate_location(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Validate location."""
        
        # Simple validation - just check it's not empty
        if slot_value and len(slot_value.strip()) > 2:
            return {"location": slot_value}
        else:
            dispatcher.utter_message(
                text="Please provide a valid location (e.g., Borrowdale, Ward 17)."
            )
            return {"location": None}