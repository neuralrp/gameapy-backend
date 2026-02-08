"""
Phase 2 Test Suite

Tests for CardGenerator, GuideSystem, and API endpoints.
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from app.services.card_generator import CardGenerator
from app.services.guide_system import GuideSystem
from app.api.cards import router as cards_router
from app.api.guide import router as guide_router
from app.db.database import db
from fastapi.testclient import TestClient


# ============================================
# CardGenerator Tests
# ============================================

class TestCardGenerator:
    """Test cases for CardGenerator service."""

    def setup_method(self):
        """Setup for each test."""
        self.generator = CardGenerator()

    @pytest.mark.asyncio
    async def test_generate_self_card(self):
        """Test generating a self card from plain text."""
        plain_text = "I'm 25, work in tech, love playing guitar and hiking. I struggle with anxiety sometimes but I'm working on it."

        with patch('app.services.card_generator.simple_llm_client') as mock_llm:
            mock_llm.chat_completion = AsyncMock(return_value={
                'choices': [{
                    'message': {
                        'content': json.dumps({
                            "spec": "gameapy_self_card_v1",
                            "spec_version": "1.0",
                            "data": {
                                "name": "User",
                                "summary": "25-year-old tech worker who loves guitar and hiking",
                                "personality": "Anxious but working on it",
                                "traits": ["creative", "anxious", "resilient"],
                                "interests": ["guitar", "hiking", "technology"],
                                "values": ["growth", "creativity"],
                                "strengths": ["resilient", "creative"],
                                "challenges": ["anxiety"],
                                "goals": [{"goal": "manage anxiety", "timeframe": "ongoing"}],
                                "triggers": ["stress at work"],
                                "coping_strategies": ["playing guitar", "hiking"],
                                "patterns": [],
                                "current_themes": ["anxiety management"],
                                "risk_flags": {
                                    "crisis": False,
                                    "self_harm_history": False,
                                    "substance_misuse_concern": False,
                                    "notes": None
                                }
                            }
                        })
                    }
                }]
            })

            with patch.object(db, '_log_performance_metric', new_callable=AsyncMock):
                result = await self.generator.generate_card(
                    card_type="self",
                    plain_text=plain_text
                )

                assert result["card_type"] == "self"
                assert result["preview"] is True
                assert result["fallback"] is False
                assert "generated_card" in result
                assert result["generated_card"]["spec"] == "gameapy_self_card_v1"

    @pytest.mark.asyncio
    async def test_generate_character_card(self):
        """Test generating a character card from plain text."""
        plain_text = "My mom is overprotective but means well. She always worries about me and checks in constantly."
        name = "Mom"

        with patch('app.services.card_generator.simple_llm_client') as mock_llm:
            mock_llm.chat_completion = AsyncMock(return_value={
                'choices': [{
                    'message': {
                        'content': json.dumps({
                            "spec": "gameapy_character_card_v1",
                            "spec_version": "1.0",
                            "data": {
                                "name": "Mom",
                                "relationship_type": "family",
                                "personality": "Overprotective, caring",
                                "patterns": [
                                    {"pattern": "checks in constantly", "weight": 0.8, "mentions": 1}
                                ],
                                "key_events": [],
                                "user_feelings": [
                                    {"feeling": "loved but smothered", "weight": 0.7}
                                ],
                                "emotional_state": {
                                    "user_to_other": {
                                        "trust": 40,
                                        "emotional_bond": 80,
                                        "conflict": 60,
                                        "power_dynamic": -20,
                                        "fear_anxiety": 30
                                    },
                                    "other_to_user": None
                                }
                            }
                        })
                    }
                }]
            })

            with patch.object(db, '_log_performance_metric', new_callable=AsyncMock):
                result = await self.generator.generate_card(
                    card_type="character",
                    plain_text=plain_text,
                    name=name
                )

                assert result["card_type"] == "character"
                assert result["preview"] is True
                assert result["fallback"] is False
                assert result["generated_card"]["data"]["name"] == "Mom"

    @pytest.mark.asyncio
    async def test_generate_world_event(self):
        """Test generating a world event card from plain text."""
        plain_text = "When I was 12, I was assaulted by my uncle. This caused trust issues that I'm still working through."

        with patch('app.services.card_generator.simple_llm_client') as mock_llm:
            mock_llm.chat_completion = AsyncMock(return_value={
                'choices': [{
                    'message': {
                        'content': json.dumps({
                            "title": "Childhood assault",
                            "event_type": "trauma",
                            "key_array": ["assault", "childhood", "trauma", "uncle", "trust issues"],
                            "description": "[Trauma: Childhood assault, type(trauma), time(age 12), actor(uncle), result(trust issues), legacy(ongoing therapy)]",
                            "is_canon_law": True,
                            "resolved": False
                        })
                    }
                }]
            })

            with patch.object(db, '_log_performance_metric', new_callable=AsyncMock):
                result = await self.generator.generate_card(
                    card_type="world",
                    plain_text=plain_text
                )

                assert result["card_type"] == "world"
                assert result["preview"] is True
                assert result["fallback"] is False
                assert result["generated_card"]["event_type"] == "trauma"
                assert result["generated_card"]["is_canon_law"] is True

    @pytest.mark.asyncio
    async def test_invalid_card_type(self):
        """Test that invalid card type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await self.generator.generate_card(
                card_type="invalid",
                plain_text="test"
            )

        assert "Invalid card_type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retry_on_json_error(self):
        """Test retry logic when JSON parsing fails."""
        plain_text = "Test text"

        with patch('app.services.card_generator.simple_llm_client') as mock_llm:
            mock_llm.chat_completion = AsyncMock(return_value={
                'choices': [{
                    'message': {
                        'content': 'Not valid JSON'
                    }
                }]
            })

            with patch.object(db, '_log_performance_metric', new_callable=AsyncMock):
                result = await self.generator.generate_card(
                    card_type="character",
                    plain_text=plain_text
                )

                assert result["fallback"] is True
                assert result["generated_card"]["fallback"] is True

    @pytest.mark.asyncio
    async def test_extract_json_from_markdown(self):
        """Test JSON extraction from markdown code blocks."""
        markdown_response = """
        ```json
        {"test": "value"}
        ```
        """

        parsed = self.generator._parse_llm_response(markdown_response, "world")

        assert parsed["test"] == "value"


# ============================================
# GuideSystem Tests
# ============================================

class TestGuideSystem:
    """Test cases for GuideSystem service."""

    def setup_method(self):
        """Setup for each test."""
        self.guide = GuideSystem()

    def test_get_guide_counselor_id(self):
        """Test getting or creating Guide counselor profile."""
        with patch.object(db, 'get_counselor_by_name', return_value=None):
            with patch.object(db, 'create_counselor_profile') as mock_create:
                mock_create.return_value = 1

                counselor_id = self.guide._get_guide_counselor_id()

                assert counselor_id == 1
                mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_onboarding(self):
        """Test starting onboarding creates session and returns initial message."""
        with patch.object(self.guide, '_get_guide_counselor_id', return_value=1):
            with patch.object(db, 'create_session', return_value=10):
                with patch.object(self.guide, '_generate_welcome_message') as mock_welcome:
                    mock_welcome.return_value = "Welcome to Gameapy!"

                    with patch.object(db, 'create_message'):
                        result = await self.guide.start_onboarding(client_id=1)

                        assert result["phase"] == "self"
                        assert result["session_id"] == 10
                        assert result["client_id"] == 1
                        assert "guide_message" in result

    @pytest.mark.asyncio
    async def test_phase_completion_check_explicit_done(self):
        """Test phase completion with explicit user confirmation."""
        transcript = "I'm 25 years old. That's everything about me."
        result = await self.guide._check_phase_complete(transcript, phase="self")

        assert result["complete"] is True
        assert "confirmed" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_phase_completion_insufficient_content(self):
        """Test phase completion fails with insufficient content."""
        transcript = "I'm 25."
        result = await self.guide._check_phase_complete(transcript, phase="self")

        assert result["complete"] is False
        assert "Need more content" in result["reason"]

    @pytest.mark.asyncio
    async def test_extract_people_from_transcript(self):
        """Test extracting people from transcript."""
        transcript = "client: My mom is overprotective. guide: Tell me more. client: She checks in constantly."

        with patch('app.services.guide_system.simple_llm_client') as mock_llm:
            mock_llm.chat_completion = AsyncMock(return_value={
                'choices': [{
                    'message': {
                        'content': json.dumps([
                            {"name": "Mom", "description": "Overprotective mother who checks in constantly"}
                        ])
                    }
                }]
            })

            people = await self.guide._extract_people_from_transcript(transcript)

            assert len(people) == 1
            assert people[0]["name"] == "Mom"
            assert "overprotective" in people[0]["description"].lower()

    @pytest.mark.asyncio
    async def test_extract_events_from_transcript(self):
        """Test extracting events from transcript."""
        transcript = "client: When I was 12, I was assaulted. guide: That sounds difficult. client: It affected my trust."

        with patch('app.services.guide_system.simple_llm_client') as mock_llm:
            mock_llm.chat_completion = AsyncMock(return_value={
                'choices': [{
                    'message': {
                        'content': json.dumps([
                            {"description": "Assault at age 12 that affected trust"}
                        ])
                    }
                }]
            })

            events = await self.guide._extract_events_from_transcript(transcript)

            assert len(events) == 1
            assert "assault" in events[0]["description"].lower()


# ============================================
# API Tests
# ============================================

class TestCardsAPI:
    """Test cases for Cards API endpoints."""

    def setup_method(self):
        """Setup for each test."""
        from main import app
        self.client = TestClient(app)

    def test_post_generate_from_text(self):
        """Test POST /cards/generate-from-text endpoint."""
        with patch('app.api.cards.card_generator') as mock_generator:
            mock_generator.generate_card = AsyncMock(return_value={
                "card_type": "self",
                "generated_card": {"test": "data"},
                "preview": True,
                "fallback": False
            })

            response = self.client.post(
                "/api/v1/cards/generate-from-text",
                json={
                    "card_type": "self",
                    "plain_text": "Test text"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["card_type"] == "self"

    def test_post_save_card(self):
        """Test POST /cards/save endpoint."""
        with patch.object(db, 'create_self_card', return_value=1):
            response = self.client.post(
                "/api/v1/cards/save",
                json={
                    "client_id": 1,
                    "card_type": "self",
                    "card_data": {"test": "card"}
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["card_id"] == 1

    def test_post_save_card_invalid_type(self):
        """Test POST /cards/save with invalid card type."""
        response = self.client.post(
            "/api/v1/cards/save",
            json={
                "client_id": 1,
                "card_type": "invalid",
                "card_data": {}
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


class TestGuideAPI:
    """Test cases for Guide API endpoints."""

    def setup_method(self):
        """Setup for each test."""
        from main import app
        self.client = TestClient(app)

    def test_post_onboarding_start(self):
        """Test POST /guide/onboarding endpoint."""
        with patch('app.api.guide.guide_system') as mock_guide:
            mock_guide.start_onboarding = AsyncMock(return_value={
                "phase": "self",
                "guide_message": "Welcome!",
                "session_id": 1,
                "client_id": 1
            })

            response = self.client.post(
                "/api/v1/guide/onboarding",
                json={"client_id": 1}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["phase"] == "self"

    def test_post_onboarding_input(self):
        """Test POST /guide/onboarding/input endpoint."""
        with patch('app.api.guide.guide_system') as mock_guide:
            mock_guide.process_user_input = AsyncMock(return_value={
                "phase": "self",
                "guide_message": "Tell me more...",
                "conversation_complete": False,
                "cards_generated": []
            })

            response = self.client.post(
                "/api/v1/guide/onboarding/input",
                json={
                    "session_id": 1,
                    "phase": "self",
                    "user_input": "I'm 25"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


# ============================================
# Run Tests
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
