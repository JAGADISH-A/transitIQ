"""Journey intent extraction service for transit queries."""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from groq import Groq

from app.config import get_settings
from app.models.schemas import JourneyIntentResponse, JourneyContext, IntentType

logger = logging.getLogger(__name__)

class JourneyIntentService:
    def __init__(self):
        self.settings = get_settings()
        self.client = None
        if self.settings.GROQ_API_KEY:
            self.client = Groq(api_key=self.settings.GROQ_API_KEY)
        self.model = self.settings.GROQ_MODEL
        
        # Pre-compile regex patterns for fast-path extraction (order matters — most specific first)
        self.regex_patterns = [
            # "How do I reach Guindy from Avadi after 5 PM?"
            re.compile(r"(?:how\s+do\s+i\s+)?reach\s+(?P<destination>[A-Za-z\s]+?)\s+from\s+(?P<source>[A-Za-z\s]+?)(?:\s+(?:after|at|before|by)\s+(?P<departure_time>[\d:\sAPMapm]+))?(?:\s+(?P<preference>fastest|shortest|cheapest))?$", re.IGNORECASE),
            
            # "I am going from Chennai Central to Avadi", "Take me from Beach to Tambaram"
            re.compile(r"(?:.*?\s)?from\s+(?P<source>[A-Za-z\s]+?)\s+to\s+(?P<destination>[A-Za-z\s]+?)(?:\s+(?:after|at|before|by)\s+(?P<departure_time>[\d:\sAPMapm]+))?$", re.IGNORECASE),

            # "Route from Avadi to Guindy"
            re.compile(r"(?:(?P<preference>fastest|shortest|cheapest)\s+)?route\s+(?:from\s+)?(?P<source>[A-Za-z\s]+?)\s+to\s+(?P<destination>[A-Za-z\s]+?)(?:\s+(?:after|at|before|by)\s+(?P<departure_time>[\d:\sAPMapm]+))?$", re.IGNORECASE),
            
            # "Fastest route to Guindy", "Route to Guindy" (Destination only)
            re.compile(r"(?:(?P<preference>fastest|shortest|cheapest)\s+)?route\s+to\s+(?P<destination>[A-Za-z\s]+?)(?:\s+(?:after|at|before|by)\s+(?P<departure_time>[\d:\sAPMapm]+))?$", re.IGNORECASE),

            # "Avadi -> Central", "Avadi → Central"
            re.compile(r"(?P<source>[A-Za-z\s]+?)\s*(?:->|→)\s*(?P<destination>[A-Za-z\s]+?)$", re.IGNORECASE),

            # "Avadi to Guindy" (short, no filler — only matches 1-3 word locations on each side)
            re.compile(r"^(?P<source>[A-Za-z]{2,}(?:\s+[A-Za-z]{2,}){0,2})\s+to\s+(?P<destination>[A-Za-z]{2,}(?:\s+[A-Za-z]{2,}){0,2})$", re.IGNORECASE),
        ]

    def _fast_extract(self, prompt: str) -> Optional[JourneyIntentResponse]:
        """Attempt to extract intent using regex patterns."""
        for pattern in self.regex_patterns:
            match = pattern.search(prompt.strip().rstrip('?.'))
            if match:
                groups = match.groupdict()
                source = groups.get("source")
                destination = groups.get("destination")
                departure_time = groups.get("departure_time")
                preference = groups.get("preference")
                
                if source or destination:
                    return JourneyIntentResponse(
                        intent_type=IntentType.NEW_SEARCH,
                        source=source.strip() if source else None,
                        destination=destination.strip() if destination else None,
                        departure_time=departure_time.strip() if departure_time else None,
                        preference=preference.strip() if preference else None
                    )
        return None

    def extract_intent(self, prompt: str, context: JourneyContext | None = None) -> JourneyIntentResponse:
        """Extract journey parameters and intent from a natural language prompt."""
        
        # 1. Check Context Expiration
        if context and context.last_updated:
            try:
                from datetime import timedelta
                time_str = context.last_updated.replace('Z', '+00:00')
                last_time = datetime.fromisoformat(time_str)
                
                if last_time.tzinfo is None:
                    last_time = last_time.replace(tzinfo=timezone.utc)

                now = datetime.now(timezone.utc)
                delta = now - last_time
                
                if delta > timedelta(minutes=30):
                    logger.warning("Context expired for prompt: %s", prompt)
                    return JourneyIntentResponse(
                        intent_type=IntentType.CONTEXT_EXPIRED,
                        error_message="I'm not sure which journey you're referring to. Could you tell me the route again?"
                    )
            except Exception as e:
                logger.warning(f"Failed to parse context time: {e}")
                pass

        # 2. Regex Fast Path
        intent = self._fast_extract(prompt)
        
        if not intent and self.client:
            # 3. LLM Fallback Path
            logger.info("Regex failed, falling back to LLM for: %s", prompt)
            try:
                context_str = "None"
                if context:
                    context_str = f"Source: {context.source}, Destination: {context.destination}"

                system_prompt = (
                    "You are a helpful transit routing assistant. Extract the journey parameters and classify the user's intent.\n"
                    f"Current Context: {context_str}\n"
                    "Intent types:\n"
                    "- NEW_SEARCH: 'Avadi to Guindy'\n"
                    "- MODIFY_TIME: 'What about tomorrow morning?'\n"
                    "- MODIFY_FILTER: 'Show direct trains only'\n"
                    "- OPTIMIZE_ROUTE: 'Any faster options?'\n"
                    "- EXPLAIN_ROUTE: 'How long is the transfer?'\n"
                    "- ROUTE_CONTEXT_QA: 'Why was this route recommended?', 'Is the transfer risky?', 'What are the tradeoffs?'\n"
                    "Return ONLY a valid JSON object matching this schema: "
                    "{ \"intent_type\": string, \"source\": string|null, \"destination\": string|null, "
                    "\"departure_time\": string|null, \"preference\": string|null }. "
                    "If a value is not mentioned in the prompt, use null. Do not fill missing locations from context yourself, the system will do it."
                )
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
                
                content = response.choices[0].message.content
                if content:
                    parsed = json.loads(content)
                    intent_str = parsed.get("intent_type", "NEW_SEARCH")
                    try:
                        itype = IntentType(intent_str)
                    except ValueError:
                        itype = IntentType.NEW_SEARCH
                        
                    intent = JourneyIntentResponse(
                        intent_type=itype,
                        source=parsed.get("source"),
                        destination=parsed.get("destination"),
                        departure_time=parsed.get("departure_time"),
                        preference=parsed.get("preference"),
                    )
                    logger.info("LLM extraction — type: %s, source: %s, dest: %s", intent.intent_type, intent.source, intent.destination)
            except Exception as e:
                logger.error("LLM extraction failed: %s", e)
        
        if not intent:
            logger.warning("Could not extract intent from: %s", prompt)
            intent = JourneyIntentResponse(intent_type=IntentType.NEW_SEARCH)
            
        # 4. Context Inheritance
        if intent.intent_type != IntentType.NEW_SEARCH and context:
            if not intent.source and context.source:
                intent.source = context.source
            if not intent.destination and context.destination:
                intent.destination = context.destination

        return intent

journey_intent_service = JourneyIntentService()
