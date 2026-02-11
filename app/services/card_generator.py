import json
import time
from typing import Optional, Dict, Any, List
from ..core.config import settings
from ..services.simple_llm_fixed import simple_llm_client
from ..db.database import db
from ..utils.card_metadata import initialize_card_metadata


class CardGenerator:
    """
    LLM-based plain text → structured JSON conversion service.

    Supports 3 card types: self, character, world
    Uses retry logic with fallback to plain text
    Logs failures to performance_metrics table
    """

    def __init__(self):
        self.default_model = settings.default_model or "openrouter/free"

    async def generate_card(
        self,
        card_type: str,
        plain_text: str,
        context: Optional[str] = None,
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a structured card from plain text.

        Args:
            card_type: "self", "character", or "world"
            plain_text: User's description to convert
            context: Optional extra background for improved generation
            name: Optional name for character cards

        Returns:
            {
                "card_type": "self|character|world",
                "generated_card": {...full card JSON...},
                "preview": true,
                "fallback": false
            }
        """
        if card_type not in ["self", "character", "world"]:
            raise ValueError(f"Invalid card_type: {card_type}")

        prompt = self._build_prompt(card_type, plain_text, context, name)
        model = self.default_model

        for attempt in range(3):
            start_time = time.time()
            try:
                response = await simple_llm_client.chat_completion(
                    messages=[{"role": "system", "content": prompt}],
                    model=model,
                    temperature=0.7,
                    max_tokens=4000
                )

                duration_ms = int((time.time() - start_time) * 1000)
                content = response['choices'][0]['message']['content']
                parsed_card = self._parse_llm_response(content, card_type)
                
                # Initialize metadata for all fields in the generated card
                parsed_card_with_metadata = initialize_card_metadata(parsed_card, source='llm')

                await db._log_performance_metric(
                    operation="card_generate",
                    duration_ms=duration_ms,
                    status="success",
                    error_message=None,
                    metadata={"model": model, "attempt": attempt + 1, "card_type": card_type}
                )

                return {
                    "card_type": card_type,
                    "generated_card": parsed_card_with_metadata,
                    "preview": True,
                    "fallback": False
                }

            except (json.JSONDecodeError, KeyError) as e:
                duration_ms = int((time.time() - start_time) * 1000)
                if attempt == 2:
                    await db._log_performance_metric(
                        operation="card_generate",
                        duration_ms=duration_ms,
                        status="fallback",
                        error_message=str(e),
                        metadata={"model": model, "attempt": attempt + 1, "card_type": card_type}
                    )

                    return {
                        "card_type": card_type,
                        "generated_card": {
                            "plain_text": plain_text,
                            "fallback": True,
                            "name": name if name else "Untitled"
                        },
                        "preview": True,
                        "fallback": True
                    }
                continue

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                await db._log_performance_metric(
                    operation="card_generate",
                    duration_ms=duration_ms,
                    status="error",
                    error_message=str(e),
                    metadata={"model": model, "attempt": attempt + 1, "card_type": card_type}
                )
                raise

    def _build_prompt(
        self,
        card_type: str,
        plain_text: str,
        context: Optional[str] = None,
        name: Optional[str] = None
    ) -> str:
        """Build LLM prompt based on card type."""

        context_section = f"""
CONTEXT:
---
{context}
""" if context else ""

        name_section = f"""
NAME:
---
{name}
""" if name and card_type == "character" else ""

        if card_type == "self":
            return f"""You are a card generator for Gameapy, a therapeutic storytelling app.

Convert this plain text description into a structured self-card:

PLAIN TEXT:
---
{plain_text}
{context_section}

Output ONLY valid JSON in this format:
{{
  "spec": "gameapy_self_card_v1",
  "spec_version": "1.0",
  "data": {{
    "name": "optional_display_name",
    "summary": "1-2 sentence overview",
    "personality": "Short description",
    "traits": ["trait1", "trait2"],
    "interests": ["interest1", "interest2"],
    "values": ["value1", "value2"],
    "strengths": ["strength1", "strength2"],
    "challenges": ["challenge1", "challenge2"],
    "goals": [
      {{"goal": "...", "timeframe": "..."}}
    ],
    "triggers": ["trigger1", "trigger2"],
    "coping_strategies": ["strategy1", "strategy2"],
    "patterns": [
      {{"pattern": "...", "weight": 0.0-1.0, "mentions": 1}}
    ],
    "current_themes": ["theme1", "theme2"],
    "risk_flags": {{
      "crisis": false,
      "self_harm_history": false,
      "substance_misuse_concern": false,
      "notes": null
    }}
  }}
}}

Do not include any text outside of JSON."""

        elif card_type == "character":
            return f"""You are a card generator for Gameapy, a therapeutic storytelling app.

Convert this plain text description into a structured character card:

PLAIN TEXT:
---
{plain_text}
{context_section}
{name_section}

Output ONLY valid JSON in this format:
{{
  "spec": "gameapy_character_card_v1",
  "spec_version": "1.0",
  "data": {{
    "name": "...",
    "relationship_type": "family|friend|coworker|romantic|other",
    "personality": "...",
    "patterns": [
      {{"pattern": "...", "weight": 0.0-1.0, "mentions": 1}}
    ],
    "key_events": [
      {{"event": "...", "date": "...", "impact": "..."}}
    ],
    "user_feelings": [
      {{"feeling": "...", "weight": 0.0-1.0}}
    ],
    "emotional_state": {{
      "user_to_other": {{
        "trust": 0-100,
        "emotional_bond": 0-100,
        "conflict": 0-100,
        "power_dynamic": -100 to 100,
        "fear_anxiety": 0-100
      }},
      "other_to_user": null
    }}
  }}
}}

Do not include any text outside of JSON."""

        elif card_type == "world":
            return f"""You are a card generator for Gameapy, a therapeutic storytelling app.

Convert this plain text description into a structured world event card:

PLAIN TEXT:
---
{plain_text}
{context_section}

Output ONLY valid JSON in this format:
{{
  "title": "...",
  "event_type": "achievement|trauma|transition|unresolved",
  "key_array": ["keyword1", "keyword2", ...],
  "description": "[Event: type(...)]",
  "is_canon_law": true|false,
  "resolved": true|false
}}

Do not include any text outside of JSON."""

        else:
            raise ValueError(f"Unknown card_type: {card_type}")

    def _parse_llm_response(self, response: str, card_type: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured JSON.

        Extracts JSON from markdown code blocks if present.
        """
        json_text = response.strip()

        if "```json" in json_text:
            start = json_text.find("```json") + 7
            end = json_text.find("```", start)
            json_text = json_text[start:end].strip()
        elif "```" in json_text:
            start = json_text.find("```") + 3
            end = json_text.find("```", start)
            json_text = json_text[start:end].strip()

        parsed = json.loads(json_text)

        if card_type == "world":
            parsed["spec"] = "gameapy_world_event_v1"
            parsed["spec_version"] = "1.0"

        return parsed


# Global card generator instance
card_generator = CardGenerator()
