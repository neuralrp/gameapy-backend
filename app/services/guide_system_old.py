import json
import uuid
from typing import Dict, Any, List, Optional
from ..core.config import settings
from ..services.simple_llm_fixed import simple_llm_client
from ..services.card_generator import card_generator
from ..db.database import db


class GuideSystem:
    """
    Onboarding system that handles initial card creation via 3-phase conversation flow.

    Phases:
    1. About Self - Creates self card
    2. About Important People - Creates character cards
    3. About Personal History - Creates world event cards
    """

    def __init__(self):
        self.default_model = settings.default_model or "openrouter/free"

    async def start_onboarding(self, client_id: int) -> Dict[str, Any]:
        """
        Start guide onboarding conversation.

        Creates a new session with Guide counselor and returns initial message.

        Returns:
            {
                "phase": "self",
                "guide_message": "Welcome to Gameapy...",
                "session_id": int,
                "client_id": int
            }
        """
        guide_counselor_id = self._get_guide_counselor_id()

        session_id = db.create_session(
            client_id=client_id,
            counselor_id=guide_counselor_id
        )

        welcome_message = await self._generate_welcome_message()

        db.create_message(
            session_id=session_id,
            role="assistant",
            content=welcome_message,
            speaker="guide"
        )

        return {
            "phase": "self",
            "guide_message": welcome_message,
            "session_id": session_id,
            "client_id": client_id
        }

    async def process_user_input(
        self,
        session_id: int,
        phase: str,
        user_input: str
    ) -> Dict[str, Any]:
        """
        Process user input during onboarding phase.

        Returns:
            {
                "phase": str,
                "guide_message": str,
                "conversation_complete": bool,
                "cards_generated": []  # Only populated at phase completion
            }
        """
        session = db.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        db.create_message(
            session_id=session_id,
            role="user",
            content=user_input,
            speaker="client"
        )

        transcript = self._get_session_transcript(session_id)

        if phase == "self":
            result = await self._process_self_phase(session_id, transcript, user_input)
        elif phase == "people":
            result = await self._process_people_phase(session_id, transcript, user_input)
        elif phase == "history":
            result = await self._process_history_phase(session_id, transcript, user_input)
        else:
            raise ValueError(f"Invalid phase: {phase}")

        return result

    async def _process_self_phase(
        self,
        session_id: int,
        transcript: str,
        user_input: str
    ) -> Dict[str, Any]:
        """Process self-description phase."""
        check_complete = await self._check_phase_complete(transcript, phase="self")

        if check_complete["complete"]:
            cards = await self._phase_self_complete(session_id, transcript)

            db.create_message(
                session_id=session_id,
                role="assistant",
                content="Thank you for sharing about yourself! I've created your self card. Now let's talk about the important people in your life.",
                speaker="guide"
            )

            return {
                "phase": "people",
                "guide_message": "Now let's talk about the important people in your life. Who are the main people - family, friends, mentors, anyone who matters to you?",
                "conversation_complete": False,
                "cards_generated": cards
            }
        else:
            guide_message = await self._generate_followup_question(transcript, phase="self")

            db.create_message(
                session_id=session_id,
                role="assistant",
                content=guide_message,
                speaker="guide"
            )

            return {
                "phase": "self",
                "guide_message": guide_message,
                "conversation_complete": False,
                "cards_generated": []
            }

    async def _process_people_phase(
        self,
        session_id: int,
        transcript: str,
        user_input: str
    ) -> Dict[str, Any]:
        """Process important people phase."""
        check_complete = await self._check_phase_complete(transcript, phase="people")

        if check_complete["complete"]:
            people_list = await self._extract_people_from_transcript(transcript)
            cards = await self._phase_people_complete(session_id, people_list)

            db.create_message(
                session_id=session_id,
                role="assistant",
                content="Thanks for telling me about the important people in your life! I've created character cards for them. Now let's talk about major events in your history.",
                speaker="guide"
            )

            return {
                "phase": "history",
                "guide_message": "Finally, tell me about major events in your life - achievements, challenges, transitions, anything important that shaped who you are today.",
                "conversation_complete": False,
                "cards_generated": cards
            }
        else:
            guide_message = await self._generate_followup_question(transcript, phase="people")

            db.create_message(
                session_id=session_id,
                role="assistant",
                content=guide_message,
                speaker="guide"
            )

            return {
                "phase": "people",
                "guide_message": guide_message,
                "conversation_complete": False,
                "cards_generated": []
            }

    async def _process_history_phase(
        self,
        session_id: int,
        transcript: str,
        user_input: str
    ) -> Dict[str, Any]:
        """Process personal history phase."""
        check_complete = await self._check_phase_complete(transcript, phase="history")

        if check_complete["complete"]:
            cards = await self._phase_history_complete(session_id, transcript)

            db.create_message(
                session_id=session_id,
                role="assistant",
                content="Thank you for sharing! I've created cards for your important life events. Your onboarding is complete. You can now select a counselor to begin your journey!",
                speaker="guide"
            )

            return {
                "phase": "complete",
                "guide_message": "Your onboarding is complete. You can now select a counselor to begin your journey!",
                "conversation_complete": True,
                "cards_generated": cards
            }
        else:
            guide_message = await self._generate_followup_question(transcript, phase="history")

            db.create_message(
                session_id=session_id,
                role="assistant",
                content=guide_message,
                speaker="guide"
            )

            return {
                "phase": "history",
                "guide_message": guide_message,
                "conversation_complete": False,
                "cards_generated": []
            }

    async def _phase_self_complete(
        self,
        session_id: int,
        transcript: str
    ) -> List[Dict]:
        """Phase 1 complete: Generate self card from transcript."""
        session = db.get_session(session_id)
        client_id = session["client_id"]

        result = await card_generator.generate_card(
            card_type="self",
            plain_text=transcript,
            context="Onboarding phase: User's self-description"
        )

        card_id = db.create_self_card(
            client_id=client_id,
            card_json=json.dumps(result["generated_card"])
        )

        return [{
            "card_id": card_id,
            "card_type": "self",
            "card_data": result["generated_card"]
        }]

    async def _phase_people_complete(
        self,
        session_id: int,
        people_list: List[Dict]
    ) -> List[Dict]:
        """Phase 2 complete: Generate character cards for each person."""
        session = db.get_session(session_id)
        client_id = session["client_id"]

        cards = []
        for person in people_list:
            result = await card_generator.generate_card(
                card_type="character",
                plain_text=person["description"],
                name=person["name"],
                context="Onboarding phase: Important people in user's life"
            )

            card = result["generated_card"]["data"]
            card_id = db.create_character_card(
                client_id=client_id,
                card_name=card["name"],
                relationship_type=card["relationship_type"],
                card_data=card
            )

            cards.append({
                "card_id": card_id,
                "card_type": "character",
                "card_data": card
            })

        return cards

    async def _phase_history_complete(
        self,
        session_id: int,
        transcript: str
    ) -> List[Dict]:
        """Phase 3 complete: Generate world event cards from transcript."""
        session = db.get_session(session_id)
        client_id = session["client_id"]

        events = await self._extract_events_from_transcript(transcript)
        cards = []

        for event in events:
            result = await card_generator.generate_card(
                card_type="world",
                plain_text=event["description"],
                context="Onboarding phase: Major events in user's history"
            )

            card = result["generated_card"]
            card_id = db.create_world_event(
                client_id=client_id,
                entity_id=f"world_{uuid.uuid4().hex}",
                title=card["title"],
                key_array=json.dumps(card["key_array"]),
                description=card["description"],
                event_type=card["event_type"],
                is_canon_law=card.get("is_canon_law", False),
                resolved=card.get("resolved", False)
            )

            cards.append({
                "card_id": card_id,
                "card_type": "world",
                "card_data": card
            })

        return cards

    async def _generate_welcome_message(self) -> str:
        """Generate initial welcome message from Guide."""
        prompt = "Generate a warm, friendly welcome message for a therapeutic storytelling app. The user is starting onboarding. Keep it brief and inviting."

        response = await simple_llm_client.chat_completion(
            messages=[{"role": "system", "content": prompt}],
            model=self.default_model,
            temperature=0.7,
            max_tokens=150
        )

        return response['choices'][0]['message']['content']

    async def _generate_followup_question(
        self,
        transcript: str,
        phase: str
    ) -> str:
        """Generate a follow-up question based on conversation so far."""
        if phase == "self":
            context = "User is describing themselves"
        elif phase == "people":
            context = "User is listing important people in their life"
        elif phase == "history":
            context = "User is sharing major life events"
        else:
            context = "General conversation"

        prompt = f"""Based on this conversation, ask one follow-up question to gather more information.

CONTEXT: {context}
TRANSCRIPT: {transcript}

Guidelines:
- Ask one specific, open-ended question
- Don't repeat information already given
- Keep it warm and conversational
- Don't ask "are you done yet" - that's handled separately
"""

        response = await simple_llm_client.chat_completion(
            messages=[{"role": "system", "content": prompt}],
            model=self.default_model,
            temperature=0.7,
            max_tokens=150
        )

        return response['choices'][0]['message']['content']

    async def _check_phase_complete(
        self,
        transcript: str,
        phase: str
    ) -> Dict[str, Any]:
        """
        Check if phase is complete using user confirmation + heuristics.

        Returns:
            {
                "complete": bool,
                "reason": str
            }
        """
        word_count = len(transcript.split())
        items_count = 0

        if phase == "self":
            items_count = 1
            min_words = 50
        elif phase == "people":
            items_count = len([line for line in transcript.split('\n') if line.strip()])
            min_words = 100
        elif phase == "history":
            items_count = len([line for line in transcript.split('\n') if line.strip()])
            min_words = 100

        transcript_lower = transcript.lower()

        explicit_done = any(phrase in transcript_lower for phrase in [
            "that's everything",
            "i'm done",
            "that's all",
            "nothing else"
        ])

        heuristics_met = word_count >= min_words and items_count >= 1

        if explicit_done and heuristics_met:
            return {
                "complete": True,
                "reason": "User confirmed completion and heuristics met"
            }
        elif explicit_done:
            return {
                "complete": True,
                "reason": "User confirmed completion (override heuristics)"
            }
        elif heuristics_met:
            return {
                "complete": True,
                "reason": "Heuristics met (sufficient content)"
            }
        else:
            return {
                "complete": False,
                "reason": f"Need more content (words: {word_count}, items: {items_count})"
            }

    async def _extract_people_from_transcript(self, transcript: str) -> List[Dict]:
        """Extract list of people with descriptions from transcript."""
        prompt = f"""Extract the list of people mentioned in this conversation. For each person, provide a name and brief description.

TRANSCRIPT:
{transcript}

Output ONLY valid JSON in this format:
[
  {{"name": "Mom", "description": "User's mother, described as overprotective..."}},
  {{"name": "Dad", "description": "User's father, described as distant..."}}
]
"""

        response = await simple_llm_client.chat_completion(
            messages=[{"role": "system", "content": prompt}],
            model=self.default_model,
            temperature=0.7,
            max_tokens=1000
        )

        content = response['choices'][0]['message']['content']

        try:
            people = json.loads(content)
        except:
            people = []

        return people if isinstance(people, list) else []

    async def _extract_events_from_transcript(self, transcript: str) -> List[Dict]:
        """Extract list of events with descriptions from transcript."""
        prompt = f"""Extract the list of major life events mentioned in this conversation. For each event, provide a brief description.

TRANSCRIPT:
{transcript}

Output ONLY valid JSON in this format:
[
  {{"description": "Childhood trauma at age 12"}},
  {{"description": "Graduated college in 2020"}}
]
"""

        response = await simple_llm_client.chat_completion(
            messages=[{"role": "system", "content": prompt}],
            model=self.default_model,
            temperature=0.7,
            max_tokens=1000
        )

        content = response['choices'][0]['message']['content']

        try:
            events = json.loads(content)
        except:
            events = []

        return events if isinstance(events, list) else []

    def _get_session_transcript(self, session_id: int) -> str:
        """Get full transcript of session as plain text."""
        messages = db.get_session_messages(session_id)
        transcript = ""

        for msg in messages:
            speaker = msg.get("speaker", "unknown")
            content = msg.get("content", "")
            transcript += f"{speaker}: {content}\n"

        return transcript

    def _get_guide_counselor_id(self) -> int:
        """Get or create Guide counselor profile."""
        existing = db.get_counselor_by_name("Guide")

        if existing:
            return existing["id"]

        guide_profile = {
            "name": "Guide",
            "specialization": "Onboarding & Updates",
            "therapeutic_style": "Warm, friendly, curious, and supportive. Guides users through onboarding and collects life updates.",
            "credentials": "AI Guide",
            "extensions": {"guide_system": True}
        }

        return db.create_counselor_profile(guide_profile)


# Global guide system instance
guide_system = GuideSystem()
