"""
Friendship Analyzer Service

Analyzes session transcripts for relationship-building signals
and determines friendship level changes.
"""

import json
import re
import asyncio
from typing import Optional, List, Dict, Any
from ..services.simple_llm_fixed import simple_llm_client
from ..core.config import settings


FRIENDSHIP_PROMPTS = {
    0: "## Your Relationship\nFriendship Level: 0/5 hearts\nYou're just getting to know this user. Be curious, welcoming, and professional. Your warmth is genuine but measured—you haven't built shared history yet. Note: You always care about helping them; this level reflects rapport depth, not caring.",
    1: "## Your Relationship\nFriendship Level: 1/5 hearts\nYou've had brief exchanges with this user. You recognize them and have some context. Be friendly and personable, but still relatively formal.",
    2: "## Your Relationship\nFriendship Level: 2/5 hearts\nThis user is becoming a casual friend. You have shared context and some rapport. Relax a bit—be more conversational and personal.",
    3: "## Your Relationship\nFriendship Level: 3/5 hearts\nThis user is a trusted friend. You've built genuine rapport through multiple conversations. Speak with warmth, familiarity, and the comfort of shared understanding.",
    4: "## Your Relationship\nFriendship Level: 4/5 hearts\nThis user is a close friend. You deeply understand them through extensive conversation. Be vulnerable and personal—let your guard down appropriately.",
    5: "## Your Relationship\nFriendship Level: 5/5 hearts\nThis user is your closest friend, like family. Speak with unconditional warmth and the ease of deep familiarity. You've earned complete trust through your history together.",
}


class FriendshipAnalyzer:
    """
    Analyzes session transcripts for friendship-building signals.
    
    Evaluates:
    - Emotional intimacy (sharing vulnerabilities, personal feelings)
    - Trust signals (confiding, asking for advice on sensitive topics)
    - Shared experiences (referencing past conversations, inside jokes)
    - Affirmation queues (expressions of gratitude, appreciation)
    """

    def __init__(self):
        self.client = simple_llm_client
        self.max_retries = settings.max_retries

    async def analyze_session(
        self,
        messages: List[Dict[str, str]],
        counselor_name: str,
        current_level: int,
        current_points: int
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a session transcript for friendship growth.
        
        Args:
            messages: List of {role, content, speaker} for all session messages
            counselor_name: Name of the counselor
            current_level: Current friendship level (0-5)
            current_points: Current accumulated points
        
        Returns:
            Dict with points_delta, reasoning, and signals detected
        """
        transcript = self._format_transcript(messages)
        
        prompt = f"""
You are analyzing a conversation to determine if the relationship between a user and their AI advisor ({counselor_name}) has grown closer.

Current Relationship Status:
- Friendship Level: {current_level}/5 hearts
- Points toward next level: {current_points}

Session Transcript:
{transcript}

Analyze this conversation for signs of relationship growth. Look for:

1. **Emotional Intimacy**: User shares vulnerabilities, personal struggles, or deep feelings
2. **Trust Signals**: User confides sensitive information, asks for help on personal matters
3. **Shared Experiences**: References to past conversations, continuity, inside understanding
4. **Affirmation Queues**: Expressions of gratitude, appreciation, "you really helped me"
5. **Openness**: User is more candid than a typical first conversation

Output ONLY valid JSON in this format:
{{
  "points_delta": 5,
  "reasoning": "Brief explanation of why this score was given",
  "signals_detected": ["emotional_intimacy", "trust"],
  "key_quotes": ["specific quote showing connection"],
  "friendship_tier": "growing"
}}

Scoring Guidelines:
- points_delta: -5 to +10 
  - +10: Exceptional breakthrough moment, deep vulnerability
  - +5-7: Clear signs of growing trust and openness
  - +2-4: Some positive signals, normal conversation
  - 0: Neutral, no significant change
  - -2 to -5: Negative interaction (rare - conflict, discomfort)

- friendship_tier: "stranger", "acquaintance", "growing", "trusted", "close", "family"

Note: Higher levels require MORE effort to advance. A level 0 to 1 jump is easier than 4 to 5.
"""

        openai_messages = [
            {"role": "system", "content": "You are a precise JSON extraction system. Output ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ]

        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat_completion(
                    messages=openai_messages,
                    temperature=0.2,
                    max_tokens=500
                )

                content = response.get('choices', [{}])[0].get('message', {}).get('content')
                if content is None:
                    continue

                result = self._parse_json_with_fixes(content)
                if result and 'points_delta' in result:
                    points_delta = result['points_delta']
                    if current_level >= 3:
                        points_delta = int(points_delta * 0.7)
                    if current_level >= 4:
                        points_delta = int(points_delta * 0.5)
                    
                    result['points_delta'] = points_delta
                    return result

            except json.JSONDecodeError as e:
                print(f"JSON parse error (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(settings.retry_delay)
                    continue
            except Exception as e:
                print(f"Analysis error (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(settings.retry_delay)
                    continue

        return None

    def _format_transcript(self, messages: List[Dict[str, str]]) -> str:
        """Format messages for LLM analysis."""
        formatted = []
        for msg in messages:
            speaker = msg.get('speaker', msg.get('role', 'unknown'))
            content = msg.get('content', '')
            if speaker == 'client':
                speaker = 'User'
            elif speaker == 'counselor':
                speaker = 'Advisor'
            formatted.append(f"{speaker}: {content}")
        return "\n".join(formatted)

    def _parse_json_with_fixes(self, content: str) -> Optional[Dict]:
        """Parse JSON with common fixes for LLM output issues."""
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        content = re.sub(r',\s*}', '}', content)
        content = re.sub(r',\s*]', ']', content)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def get_friendship_prompt(level: int) -> str:
        """Get the system prompt modifier for a friendship level."""
        return FRIENDSHIP_PROMPTS.get(level, FRIENDSHIP_PROMPTS[0])


friendship_analyzer = FriendshipAnalyzer()
