"""
AdvisorGenerator service tests.

Tests persona generation, retry logic, JSON parsing, validation,
and performance logging.
"""
import pytest
import json
from unittest.mock import AsyncMock, patch
from app.services.advisor_generator import AdvisorGenerator, advisor_generator
from app.db.database import db


@pytest.mark.unit
class TestAdvisorGenerator:
    """Test AdvisorGenerator service methods."""

    def test_initialization(self):
        """Test AdvisorGenerator initializes with correct defaults."""
        generator = AdvisorGenerator()
        assert generator.max_retries == 3
        assert generator.temperature == 0.7
        assert generator.max_tokens == 4000
        assert generator.default_model is not None

    def test_build_advisor_prompt(self):
        """Test prompt construction includes all required elements."""
        generator = AdvisorGenerator()
        prompt = generator._build_advisor_prompt(
            name="Captain Wisdom",
            specialty="Life advice",
            vibe="Gruff but caring"
        )
        
        assert "Captain Wisdom" in prompt
        assert "Life advice" in prompt
        assert "Gruff but caring" in prompt
        assert "Core Truths" in prompt
        assert "persona_profile_v1" in prompt
        assert "crisis_protocol" in prompt
        assert "hotlines" in prompt

    def test_parse_llm_response_clean_json(self):
        """Test parsing clean JSON response."""
        generator = AdvisorGenerator()
        response = '{"spec": "persona_profile_v1", "data": {"name": "Test"}}'
        
        result = generator._parse_llm_response(response)
        
        assert result['spec'] == 'persona_profile_v1'
        assert result['data']['name'] == 'Test'

    def test_parse_llm_response_markdown_json(self):
        """Test parsing JSON from markdown code blocks."""
        generator = AdvisorGenerator()
        response = '''```json
        {"spec": "persona_profile_v1", "data": {"name": "Test"}}
        ```'''
        
        result = generator._parse_llm_response(response)
        
        assert result['spec'] == 'persona_profile_v1'
        assert result['data']['name'] == 'Test'

    def test_parse_llm_response_markdown_no_language(self):
        """Test parsing JSON from generic markdown blocks."""
        generator = AdvisorGenerator()
        response = '''```
        {"spec": "persona_profile_v1", "data": {"name": "Test"}}
        ```'''
        
        result = generator._parse_llm_response(response)
        
        assert result['spec'] == 'persona_profile_v1'
        assert result['data']['name'] == 'Test'

    def test_parse_llm_response_trailing_comma(self):
        """Test handling trailing commas (common LLM error)."""
        generator = AdvisorGenerator()
        response = '{"spec": "persona_profile_v1", "data": {"name": "Test",}}'
        
        result = generator._parse_llm_response(response)
        
        assert result['spec'] == 'persona_profile_v1'
        assert result['data']['name'] == 'Test'

    def test_parse_llm_response_invalid_json(self):
        """Test parsing invalid JSON raises JSONDecodeError."""
        generator = AdvisorGenerator()
        response = 'This is not JSON'
        
        with pytest.raises(json.JSONDecodeError):
            generator._parse_llm_response(response)

    def test_validate_persona_structure_success(self):
        """Test validation passes for valid persona."""
        generator = AdvisorGenerator()
        persona = {
            "spec": "persona_profile_v1",
            "data": {
                "name": "Test Advisor",
                "who_you_are": "A test advisor",
                "your_vibe": "Friendly",
                "your_worldview": "Help people",
                "session_template": "Hello!",
                "session_examples": [
                    {
                        "user_situation": "Test",
                        "your_response": "Response"
                    }
                ],
                "tags": ["test"],
                "visuals": {"icon": "user"},
                "crisis_protocol": "Call 911",
                "hotlines": []
            }
        }
        
        # Should not raise
        generator._validate_persona_structure(persona, "Test Advisor")

    def test_validate_persona_structure_missing_spec(self):
        """Test validation fails with missing spec."""
        generator = AdvisorGenerator()
        persona = {"data": {"name": "Test"}}
        
        with pytest.raises(ValueError, match="Invalid spec"):
            generator._validate_persona_structure(persona, "Test")

    def test_validate_persona_structure_missing_data(self):
        """Test validation fails with missing data."""
        generator = AdvisorGenerator()
        persona = {"spec": "persona_profile_v1"}
        
        with pytest.raises(ValueError, match="missing 'data' key"):
            generator._validate_persona_structure(persona, "Test")

    def test_validate_persona_structure_missing_fields(self):
        """Test validation fails with missing required fields."""
        generator = AdvisorGenerator()
        persona = {
            "spec": "persona_profile_v1",
            "data": {"name": "Test"}
        }
        
        with pytest.raises(ValueError, match="Missing required fields"):
            generator._validate_persona_structure(persona, "Test")

    def test_validate_persona_structure_name_mismatch(self):
        """Test validation fails with name mismatch."""
        generator = AdvisorGenerator()
        persona = {
            "spec": "persona_profile_v1",
            "data": {
                "name": "Wrong Name",
                "who_you_are": "A test advisor",
                "your_vibe": "Friendly",
                "your_worldview": "Help people",
                "session_template": "Hello!",
                "session_examples": [],
                "tags": [],
                "visuals": {},
                "crisis_protocol": "",
                "hotlines": []
            }
        }
        
        with pytest.raises(ValueError, match="Name mismatch"):
            generator._validate_persona_structure(persona, "Test Advisor")

    def test_validate_persona_structure_invalid_examples(self):
        """Test validation fails with invalid session_examples."""
        generator = AdvisorGenerator()
        persona = {
            "spec": "persona_profile_v1",
            "data": {
                "name": "Test",
                "who_you_are": "A test advisor",
                "your_vibe": "Friendly",
                "your_worldview": "Help people",
                "session_template": "Hello!",
                "session_examples": "not a list",
                "tags": [],
                "visuals": {},
                "crisis_protocol": "",
                "hotlines": []
            }
        }
        
        with pytest.raises(ValueError, match="session_examples must be a list"):
            generator._validate_persona_structure(persona, "Test")

    @pytest.mark.asyncio
    async def test_generate_advisor_success(self, mock_llm_success):
        """Test successful advisor generation."""
        generator = AdvisorGenerator()
        
        # Mock LLM response
        with patch.object(generator, '_parse_llm_response', return_value={
            "spec": "persona_profile_v1",
            "data": {
                "name": "Test Advisor",
                "who_you_are": "A test",
                "your_vibe": "Friendly",
                "your_worldview": "Help",
                "session_template": "Hi",
                "session_examples": [],
                "tags": [],
                "visuals": {},
                "crisis_protocol": "",
                "hotlines": []
            }
        }):
            result = await generator.generate_advisor(
                name="Test Advisor",
                specialty="Testing",
                vibe="Friendly"
            )
            
            assert result['spec'] == 'persona_profile_v1'
            assert result['data']['name'] == 'Test Advisor'

    @pytest.mark.asyncio
    async def test_generate_advisor_parse_error_retry(self, mock_llm_success):
        """Test retry logic on JSON parse errors."""
        generator = AdvisorGenerator()
        
        call_count = 0
        
        def mock_parse(content):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise json.JSONDecodeError("Invalid JSON", "", 0)
            return {
                "spec": "persona_profile_v1",
                "data": {
                    "name": "Test Advisor",
                    "who_you_are": "A test",
                    "your_vibe": "Friendly",
                    "your_worldview": "Help",
                    "session_template": "Hi",
                    "session_examples": [],
                    "tags": [],
                    "visuals": {},
                    "crisis_protocol": "",
                    "hotlines": []
                }
            }
        
        with patch.object(generator, '_parse_llm_response', side_effect=mock_parse):
            result = await generator.generate_advisor(
                name="Test Advisor",
                specialty="Testing",
                vibe="Friendly"
            )
            
            assert call_count == 3  # Retried twice before success
            assert result['data']['name'] == 'Test Advisor'

    @pytest.mark.asyncio
    async def test_generate_advisor_max_retries_exceeded(self, mock_llm_success):
        """Test failure after max retries exceeded."""
        generator = AdvisorGenerator()
        
        def mock_parse(content):
            raise json.JSONDecodeError("Invalid JSON", "", 0)
        
        with patch.object(generator, '_parse_llm_response', side_effect=mock_parse):
            with pytest.raises(ValueError, match="Failed to generate advisor after 3 attempts"):
                await generator.generate_advisor(
                    name="Test Advisor",
                    specialty="Testing",
                    vibe="Friendly"
                )

    @pytest.mark.asyncio
    async def test_generate_advisor_unexpected_error(self, mock_llm_success):
        """Test handling unexpected errors."""
        generator = AdvisorGenerator()
        
        def mock_parse(content):
            raise RuntimeError("Unexpected error")
        
        with patch.object(generator, '_parse_llm_response', side_effect=mock_parse):
            with pytest.raises(RuntimeError, match="Unexpected error"):
                await generator.generate_advisor(
                    name="Test Advisor",
                    specialty="Testing",
                    vibe="Friendly"
                )

    @pytest.mark.asyncio
    async def test_generate_advisor_logs_performance(self, mock_llm_success):
        """Test that performance metrics are logged."""
        generator = AdvisorGenerator()
        
        with patch.object(generator, '_parse_llm_response', return_value={
            "spec": "persona_profile_v1",
            "data": {
                "name": "Test Advisor",
                "who_you_are": "A test",
                "your_vibe": "Friendly",
                "your_worldview": "Help",
                "session_template": "Hi",
                "session_examples": [],
                "tags": [],
                "visuals": {},
                "crisis_protocol": "",
                "hotlines": []
            }
        }):
            with patch.object(db, '_log_performance_metric', new_callable=AsyncMock) as mock_log:
                await generator.generate_advisor(
                    name="Test Advisor",
                    specialty="Testing",
                    vibe="Friendly"
                )
                
                # Verify performance logging was called
                mock_log.assert_called_once()
                call_args = mock_log.call_args[1]
                assert call_args['operation'] == 'advisor_generate'
                assert call_args['status'] == 'success'
                assert call_args['duration_ms'] >= 0

    def test_singleton_instance(self):
        """Test that advisor_generator is a singleton."""
        from app.services.advisor_generator import advisor_generator as gen2
        assert advisor_generator is gen2
