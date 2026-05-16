# llm_gateway/app/rewriter.py
import ollama
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class MessageRewriter:
    """Optimized message rewriter with better prompts."""
    
    def __init__(self):
        self.system_prompt = """You are a helpful assistant for Harare City Council.
        
        Your task is to:
        1. Check if user messages are clear enough to proceed
        2. Ask ONE clarifying question if the message is unclear
        3. Otherwise, return the original message
        
        Common unclear patterns:
        - "I need a permit" → Ask: "What type of permit? (business, construction, event)"
        - "I want to pay" → Ask: "What would you like to pay? (water bill, business license fee, etc.)"
        - "Tell me about requirements" → Ask: "Requirements for what specific service?"
        
        Return JSON format:
        {
            "needs_clarification": boolean,
            "clarification_question": "string (if needed)",
            "rewritten_message": "string (original or clarified)"
        }
        
        Be concise and specific in clarification questions."""
    
    async def clarify_if_needed(self, message: str) -> Dict[str, Any]:
        """Check if message needs clarification."""
        try:
            # Quick check for very short/vague messages
            if len(message.strip()) < 5:
                return {
                    "needs_clarification": True,
                    "clarification_question": "Could you please provide more details about what you need help with?",
                    "rewritten_message": message
                }
            
            # Check for common vague patterns
            vague_patterns = [
                ("need a permit", "What type of permit do you need help with?"),
                ("want to pay", "What specific payment would you like to make?"),
                ("requirements", "Requirements for which specific service?"),
                ("how to", "How to do what specifically?"),
                ("tell me about", "What specifically would you like to know about?")
            ]
            
            message_lower = message.lower()
            for pattern, question in vague_patterns:
                if pattern in message_lower and len(message_lower.split()) < 8:
                    return {
                        "needs_clarification": True,
                        "clarification_question": question,
                        "rewritten_message": message
                    }
            
            # Use LLM for more complex cases
            response = ollama.chat(
                model="llama3.2:1b",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Message: {message}"}
                ],
                format="json",
                options={"temperature": 0.1, "num_predict": 100}
            )
            
            result_str = response['message']['content'].strip()
            result = json.loads(result_str)
            
            return result
            
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse rewriter response")
            return {
                "needs_clarification": False,
                "clarification_question": "",
                "rewritten_message": message
            }
        except Exception as e:
            logger.error(f"Rewriter error: {e}")
            # Default: no clarification needed
            return {
                "needs_clarification": False,
                "clarification_question": "",
                "rewritten_message": message
            }
    
    async def expand_query_for_rag(self, message: str, context: Dict[str, Any] = None) -> str:
        """Expand queries for better RAG search."""
        try:
            if not context:
                return message
            
            # Add context to improve search
            if "entities" in context:
                entities = context["entities"]
                service_type = entities.get("service_type", "")
                
                if service_type and service_type != "general":
                    # Add service-specific keywords
                    if service_type == "waste_collection":
                        expanded = f"{message} schedule days timing collection garbage"
                    elif service_type == "business_permit":
                        expanded = f"{message} requirements documents application process"
                    elif service_type == "water_bill":
                        expanded = f"{message} payment invoice account charges"
                    else:
                        expanded = message
                    
                    return expanded
            
            return message
            
        except Exception as e:
            logger.error(f"Query expansion error: {e}")
            return message