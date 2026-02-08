import json
import re
import asyncio
from typing import Optional, List, Dict, Any
from functools import lru_cache
from ..services.simple_llm_fixed import simple_llm_client
from ..core.config import settings


class InsightExtractor:
    """
    Extracts clinical insights from counseling sessions using LLM.

    Borrowed from NeuralRP's snapshot analyzer:
    - LLM-based JSON extraction
    - Retry logic for reliability
    - Structured output parsing
    """

    def __init__(self):
        self.client = simple_llm_client
        self.max_retries = settings.max_retries

    async def extract_session_insights(
        self,
        messages: List[Dict[str, str]],
        client_profile: Dict[str, Any],
        dimensions: List[str],
        session_metadata: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract clinical insights from session transcript.

        Args:
            messages: List of {role, content} for recent messages
            client_profile: Client's profile JSON
            dimensions: Dimensions to analyze (e.g., ["engagement", "mood"])
            session_metadata: Session context (number, duration, etc.)

        Returns:
            Structured insights as JSON or None if extraction fails
        """

        # Extract relevant dimensions for this session
        dimensions_str = ", ".join(f'"{dim}"' for dim in dimensions)

        # Build extraction prompt
        prompt = f"""
You are a clinical insight extraction system for Gameapy, a therapeutic storytelling app.

Client Profile:
{json.dumps(client_profile, indent=2)}

Session Context:
- Session Number: {session_metadata.get('session_number', 1)}
- Duration: {session_metadata.get('duration_minutes', 0)} minutes

Session Transcript (last 20 messages):
{self._format_messages(messages)}

Extract insights for these dimensions: [{dimensions_str}]

For each dimension, provide:
1. "score": 0-100 (higher = better for engagement/insight/functioning, lower = better for crisis)
2. "indicators": Array of specific quotes or observations (2-4 items)
3. "notes": Brief summary of findings (2-3 sentences)

If no relevant data for a dimension, set "score": null

Output ONLY valid JSON in this format:
{{
  "dimensions": {{
    "engagement": {{
      "score": 75,
      "indicators": ["client shared personal story", "asked follow-up questions"],
      "notes": "Client showed good engagement by sharing openly and showing interest"
    }},
    "mood": {{
      "score": 60,
      "indicators": ["expressed anxiety about work", "felt hopeful at end"],
      "notes": "Client started anxious but mood improved during session"
    }},
    ...
  }},
  "session_summary": "Brief 2-3 sentence summary of session",
  "detected_concerns": ["workplace stress", "perfectionism"],
  "suggested_focus_areas": ["assertive communication", "self-compassion"],
  "risk_assessment": {{
    "level": "none",  // "none", "low", "medium", "high"
    "concerns": []
  }}
}}

Do not include any text outside the JSON.
"""

        # Convert messages to OpenAI format
        openai_messages = [
            {"role": "system", "content": "You are a precise JSON extraction system. Output ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ]

        # Retry logic (borrowed from NeuralRP)
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat_completion(
                    messages=openai_messages,
                    temperature=0.1,  # Low temperature for consistency
                    max_tokens=1000
                )

                content = response.get('choices', [{}])[0].get('message', {}).get('content')
                if content is None:
                    continue

                # Parse JSON
                insights = self._parse_json_with_fixes(content)

                if insights:
                    return insights

            except json.JSONDecodeError as e:
                print(f"JSON parse error (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(settings.retry_delay)
                    continue
            except Exception as e:
                print(f"Extraction error (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(settings.retry_delay)
                    continue

        return None

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format messages for LLM context."""
        formatted = []
        for msg in messages:
            speaker = msg.get('speaker', 'unknown')
            content = msg.get('content', '')
            formatted.append(f"{speaker}: {content}")
        return "\n".join(formatted)

    def _parse_json_with_fixes(self, content: str) -> Optional[Dict]:
        """
        Parse JSON with common fixes for LLM output issues.

        Borrowed from NeuralRP's snapshot analyzer.
        """
        # Remove markdown code blocks
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        # Remove trailing commas (common LLM issue)
        content = re.sub(r',\s*}', '}', content)
        content = re.sub(r',\s*]', ']', content)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None


# Global instance
insight_extractor = InsightExtractor()