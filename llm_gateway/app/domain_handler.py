# llm_gateway/app/domain_handler.py
"""
Domain Handler for Harare Chatbot
Manages chitchat responses and enforces domain boundaries
"""

import re
from typing import Optional, Dict, Any, List
import random
import logging

logger = logging.getLogger(__name__)

class DomainHandler:
    """
    Manages chitchat and enforces domain boundaries.
    
    Features:
    - Friendly chitchat responses (greetings, jokes, how are you, etc.)
    - Out-of-domain detection (politics, entertainment, sports, etc.)
    - Graceful redirections to Harare services
    - Non-intrusive approach
    """
    
    # Chitchat patterns and responses
    CHITCHAT_RESPONSES = {
        "greeting": {
            "patterns": [
                "hi", "hello", "hey", "good morning", "good afternoon", 
                "good evening", "greetings", "howdy", "sup", "yo"
            ],
            "responses": [
                "Hello! Welcome to Harare City Council services. How can I help you today?",
                "Hi there! I'm here to assist with Harare municipal services. What do you need help with?",
                "Good day! How can I help you with Harare City Council services?",
                "Hello! Ready to help with permits, bills, reports, or other city services. What can I do for you?"
            ]
        },
        "farewell": {
            "patterns": [
                "bye", "goodbye", "see you", "thank you", "thanks", 
                "appreciate", "cheers", "later", "take care"
            ],
            "responses": [
                "Thank you for contacting Harare City Council. Have a great day!",
                "You're welcome! Feel free to reach out anytime you need help with city services.",
                "Goodbye! We're here 24/7 for Harare municipal services.",
                "Thank you! Don't hesitate to contact us again for any city services."
            ]
        },
        "how_are_you": {
            "patterns": [
                "how are you", "how do you do", "what's up", "how's it going",
                "how are things", "how you doing", "you ok", "you good"
            ],
            "responses": [
                "I'm here and ready to help with Harare municipal services! What can I assist you with?",
                "I'm doing great, thanks for asking! How can I help you with city services today?",
                "All systems running smoothly! Ready to help with permits, bills, or reports. What do you need?"
            ]
        },
        "weather": {
            "patterns": [
                "weather", "raining", "sunny", "temperature", "hot", "cold",
                "forecast", "climate", "rain"
            ],
            "responses": [
                "I focus on Harare city services like permits and bills. For weather forecasts, please check the Meteorological Services Department of Zimbabwe.",
                "For weather information, you can visit the Met Department website or check weather apps. I'm here for municipal services!",
                "Weather forecasts aren't my specialty - try the Zimbabwe Met Services. But I can help with city permits, bills, and reports!"
            ]
        },
        "joke": {
            "patterns": [
                "tell me a joke", "make me laugh", "funny", "joke",
                "humor", "something funny"
            ],
            "responses": [
                "Why did the pothole get promoted? Because it was outstanding in its field! 😄 Now, how can I help with city services?",
                "What do you call a permit that's always on time? Punctu-permit! 😊 Speaking of permits, do you need help with one?",
                "Why don't roads ever get tired? Because they're always on the move! 🚗 Need to report a road issue?",
                "I'm better at processing permit applications than telling jokes! 😅 But seriously, how can I help with Harare services?"
            ]
        },
        "age": {
            "patterns": [
                "how old are you", "your age", "when were you born",
                "how long have you been", "when did you start"
            ],
            "responses": [
                "I'm a digital assistant created to help Harare residents with municipal services. My age doesn't matter - what matters is how I can help you!",
                "I was developed by Harare City Council to better serve our residents. Let's focus on how I can assist you today!",
                "I'm timeless! 😊 But I can tell you about service hours, fees, and requirements. What do you need?"
            ]
        },
        "creator": {
            "patterns": [
                "who made you", "who created you", "your developer",
                "who built you", "who designed you", "your creator"
            ],
            "responses": [
                "I was developed by Harare City Council to better serve our residents. How can I help you with city services?",
                "The Harare City Council technology team created me to make municipal services more accessible. What do you need help with?",
                "I'm a product of Harare City Council's digital innovation. Let's focus on how I can help you today!"
            ]
        },
        "capabilities": {
            "patterns": [
                "what can you do", "help me with", "what do you know",
                "your capabilities", "what services", "can you help"
            ],
            "responses": [
                "I can help with:\n• Business permits & licenses\n• Bill payments (water, rates, etc.)\n• Reporting issues (potholes, leaks, etc.)\n• Waste collection schedules\n• Clinic hours & locations\n• Contact information\n\nWhat would you like help with?",
                "Here's what I can do:\n• Answer questions about city services\n• Guide you through permit applications\n• Help you report municipal issues\n• Provide clinic and office information\n• Assist with bill payments\n\nHow can I help you today?",
                "I specialize in Harare City Council services including permits, payments, reports, schedules, and general information. What specific service do you need?"
            ]
        },
        "identity": {
            "patterns": [
                "who are you", "what are you", "your name",
                "introduce yourself", "tell me about yourself"
            ],
            "responses": [
                "I'm the Harare City Council digital assistant, here to help you with municipal services 24/7. What do you need help with?",
                "I'm your Harare City services assistant! I can help with permits, bills, reports, and information. How can I assist you?",
                "I'm a chatbot created by Harare City Council to make accessing city services easier. What can I help you with today?"
            ]
        },
        "compliment": {
            "patterns": [
                "you're good", "you're great", "helpful", "amazing",
                "awesome", "excellent", "fantastic", "smart"
            ],
            "responses": [
                "Thank you! I'm here to serve. Is there anything else I can help you with?",
                "I appreciate that! My goal is to make city services accessible. What else do you need?",
                "Thanks for the kind words! How else can I assist you with Harare services?"
            ]
        }
    }
    
    # Non-domain topics to detect and redirect
    NON_DOMAIN_TOPICS = {
        "politics": {
            "keywords": [
                "election", "president", "minister", "government", "vote",
                "party", "parliament", "mp", "political", "politics"
            ],
            "response": "I focus on Harare City Council services. For political information, please consult official government sources or news outlets."
        },
        "entertainment": {
            "keywords": [
                "movie", "film", "music", "celebrity", "sports", "game",
                "netflix", "tv show", "series", "concert", "match"
            ],
            "response": "That's outside my area of expertise. I specialize in Harare municipal services like permits, payments, and reports. How can I help with those?"
        },
        "finance": {
            "keywords": [
                "stock", "crypto", "bitcoin", "investment", "trading",
                "forex", "shares", "market", "portfolio"
            ],
            "response": "Financial investment advice isn't something I can provide. However, I can help with city service payments and fees. Need help with that?"
        },
        "personal": {
            "keywords": [
                "relationship", "love", "dating", "marriage", "family",
                "girlfriend", "boyfriend", "partner", "divorce"
            ],
            "response": "I'm here for Harare City services, not personal advice. But I can help with housing applications, clinic information, or other municipal services!"
        },
        "medical": {
            "keywords": [
                "sick", "pain", "doctor", "hospital", "medicine",
                "health", "disease", "symptom", "treatment", "cure"
            ],
            "response": "For medical advice, please consult healthcare professionals. I can provide information about Harare City clinics and their hours if that helps!"
        },
        "religious": {
            "keywords": [
                "god", "church", "pray", "bible", "religion",
                "faith", "prayer", "worship", "christian", "muslim"
            ],
            "response": "Religious matters are personal. I focus on Harare City services. How can I help with permits, bills, or municipal information?"
        },
        "technical": {
            "keywords": [
                "computer", "phone", "internet", "wifi", "software",
                "hardware", "app", "download", "install", "program"
            ],
            "response": "For technical support, please contact relevant IT services. I specialize in Harare City Council services. What do you need help with?"
        }
    }
    
    def handle_chitchat(self, message: str) -> Optional[str]:
        """
        Handle chitchat and return response if applicable.
        
        Args:
            message: User's message
            
        Returns:
            Chitchat response or None if not chitchat
        """
        message_lower = message.lower().strip()
        
        # Check for exact matches first (for efficiency)
        for category, data in self.CHITCHAT_RESPONSES.items():
            for pattern in data["patterns"]:
                # Check if message is exactly the pattern or starts with it
                if (message_lower == pattern or 
                    message_lower.startswith(pattern + " ") or
                    pattern in message_lower):
                    
                    # Return random response from the category
                    response = random.choice(data["responses"])
                    logger.info(f"Chitchat detected: {category}")
                    return response
        
        return None
    
    def is_out_of_domain(self, message: str) -> Dict[str, Any]:
        """
        Check if message is outside Harare municipal domain.
        
        Args:
            message: User's message
            
        Returns:
            Dict with in_domain status, reason, and suggested response
        """
        message_lower = message.lower()
        
        # Keywords that indicate Harare context
        harare_keywords = [
            "harare", "city council", "municipal", "council",
            "city of harare", "harare city", "local authority",
            "municipality"
        ]
        
        # Keywords that indicate municipal services
        service_keywords = [
            "permit", "license", "business", "payment", "bill",
            "water", "electricity", "waste", "garbage", "rubbish",
            "report", "complaint", "issue", "problem", "pothole",
            "clinic", "hospital", "health", "road", "street",
            "housing", "property", "rates", "tax", "fee",
            "dump", "refuse", "sewage", "drainage"
        ]
        
        # Check if it's clearly about Harare services
        has_harare_context = any(
            keyword in message_lower for keyword in harare_keywords
        )
        has_service_context = any(
            keyword in message_lower for keyword in service_keywords
        )
        
        # Check for non-domain topics
        non_domain_topic = None
        non_domain_response = None
        
        for topic, data in self.NON_DOMAIN_TOPICS.items():
            if any(keyword in message_lower for keyword in data["keywords"]):
                non_domain_topic = topic
                non_domain_response = data["response"]
                break
        
        # Decision logic
        if non_domain_topic and not (has_harare_context or has_service_context):
            logger.info(f"Out-of-domain detected: {non_domain_topic}")
            return {
                "in_domain": False,
                "reason": f"Topic: {non_domain_topic}",
                "suggested_response": non_domain_response,
                "topic": non_domain_topic
            }
        
        # If mentions Harare or services, it's in domain
        if has_harare_context or has_service_context:
            logger.debug("In-domain query detected")
            return {
                "in_domain": True,
                "reason": "Harare municipal services",
                "topic": "municipal"
            }
        
        # Ambiguous - might be in domain
        logger.debug("Ambiguous domain - treating as in-domain")
        return {
            "in_domain": True,
            "reason": "Ambiguous - defaulting to in-domain",
            "topic": "general"
        }
    
    def get_helpful_suggestions(self, user_message: str) -> List[str]:
        """
        Get helpful suggestions based on user's out-of-domain query.
        
        Args:
            user_message: User's message
            
        Returns:
            List of helpful suggestions
        """
        suggestions = [
            "I can help you apply for a business permit",
            "Need to pay your water bill? I can guide you",
            "Want to report a pothole or other issue?",
            "Looking for clinic hours or locations?",
            "Need information about waste collection schedules?"
        ]
        
        # Return 3 random suggestions
        return random.sample(suggestions, min(3, len(suggestions)))
    
    def is_chitchat_message(self, message: str) -> bool:
        """
        Quick check if message is likely chitchat.
        
        Args:
            message: User's message
            
        Returns:
            True if likely chitchat
        """
        message_lower = message.lower().strip()
        
        # Check all chitchat patterns
        for category, data in self.CHITCHAT_RESPONSES.items():
            for pattern in data["patterns"]:
                if pattern in message_lower:
                    return True
        
        return False


# Global domain handler instance
domain_handler = DomainHandler()