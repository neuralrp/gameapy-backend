import json
import time
from typing import Dict, Any, Optional
from ..core.config import settings
from ..services.simple_llm_fixed import simple_llm_client
from ..db.database import db
from ..config.core_truths import get_core_truths


class AdvisorGenerator:
    """
    LLM-based advisor persona generation service.
    
    Takes 3 simple inputs from the user and generates a complete, usable
    AI counselor persona with session examples, crisis protocol, and styling.
    
    Attributes:
        default_model: LLM model to use (from settings)
        max_retries: Number of retry attempts for failed generations
        temperature: LLM temperature for generation (0.7 for creative but consistent)
    
    Example:
        >>> generator = AdvisorGenerator()
        >>> persona = await generator.generate_advisor(
        ...     name="Captain Wisdom",
        ...     specialty="Life advice with maritime metaphors",
        ...     vibe="Gruff but caring old sea captain"
        ... )
        >>> print(persona['data']['name'])  # "Captain Wisdom"
        >>> print(persona['data']['who_you_are'])  # Generated description
    """
    
    def __init__(self):
        self.default_model = settings.default_model or "openrouter/free"
        self.max_retries = 3
        self.temperature = 0.7
        self.max_tokens = 4000
    
    async def generate_advisor(
        self,
        name: str,
        specialty: str,
        vibe: str
    ) -> Dict[str, Any]:
        """
        Generate a complete advisor persona from 3 user inputs.
        
        This method makes an LLM call to expand the user's brief description
        into a full persona suitable for use as an AI counselor.
        
        Args:
            name: Advisor's display name (max 50 chars, validated by caller)
            specialty: What they specialize in (max 200 chars)
            vibe: Their personality/style (max 200 chars)
        
        Returns:
            Complete persona JSON dict with structure:
            {
                "spec": "persona_profile_v1",
                "spec_version": "1.0", 
                "data": {
                    "name": str,
                    "who_you_are": str,
                    "your_vibe": str,
                    "your_worldview": str,
                    "session_template": str,
                    "session_examples": list[dict],
                    "tags": list[str],
                    "visuals": dict,
                    "crisis_protocol": str,
                    "hotlines": list[dict]
                }
            }
        
        Raises:
            ValueError: If generation fails after max_retries attempts
            Exception: If LLM service is unavailable
        
        Performance:
            - Logs timing metrics to database
            - Retries up to 3 times on parse failures
            - Typical latency: 2-5 seconds depending on model
        """
        prompt = self._build_advisor_prompt(name, specialty, vibe)
        
        for attempt in range(self.max_retries):
            start_time = time.time()
            
            try:
                # Make LLM call
                response = await simple_llm_client.chat_completion(
                    messages=[{"role": "system", "content": prompt}],
                    model=self.default_model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                
                # Calculate duration for metrics
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Extract content from response
                content = response['choices'][0]['message']['content']
                
                # Parse JSON from response
                persona = self._parse_llm_response(content)
                
                # Validate structure
                self._validate_persona_structure(persona, name)
                
                # Log success metric
                await db._log_performance_metric(
                    operation="advisor_generate",
                    duration_ms=duration_ms,
                    status="success",
                    error_message=None,
                    metadata={
                        "model": self.default_model,
                        "attempt": attempt + 1,
                        "name": name,
                        "specialty_preview": specialty[:50]
                    }
                )
                
                return persona
                
            except (json.JSONDecodeError, KeyError) as e:
                # Parse failure - retry if attempts remain
                duration_ms = int((time.time() - start_time) * 1000)
                
                if attempt == self.max_retries - 1:
                    # Final attempt failed - log and raise
                    await db._log_performance_metric(
                        operation="advisor_generate",
                        duration_ms=duration_ms,
                        status="error",
                        error_message=f"Parse failed: {str(e)}",
                        metadata={
                            "model": self.default_model,
                            "attempt": attempt + 1,
                            "error_type": "parse_error"
                        }
                    )
                    raise ValueError(
                        f"Failed to generate advisor after {self.max_retries} attempts. "
                        f"Last error: {str(e)}"
                    )
                
                # Log retry but continue
                await db._log_performance_metric(
                    operation="advisor_generate",
                    duration_ms=duration_ms,
                    status="retry",
                    error_message=str(e),
                    metadata={
                        "model": self.default_model,
                        "attempt": attempt + 1
                    }
                )
                continue
                
            except Exception as e:
                # Unexpected error - log and raise immediately
                duration_ms = int((time.time() - start_time) * 1000)
                await db._log_performance_metric(
                    operation="advisor_generate",
                    duration_ms=duration_ms,
                    status="error",
                    error_message=str(e),
                    metadata={
                        "model": self.default_model,
                        "attempt": attempt + 1,
                        "error_type": "unexpected"
                    }
                )
                raise
    
    def _build_advisor_prompt(
        self,
        name: str,
        specialty: str,
        vibe: str
    ) -> str:
        """
        Construct the LLM prompt for persona generation.
        
        Combines user's 3 inputs with core_truths (universal AI behavior)
        and a detailed JSON template to guide generation.
        
        Args:
            name: Advisor name
            specialty: Advisor specialty  
            vibe: Advisor personality
        
        Returns:
            Complete prompt string for LLM
        """
        core_truths = get_core_truths()
        
        return f"""You are a persona generator for Gameapy, a therapeutic storytelling app.

Your task is to create a complete AI counselor persona based on the user's brief description.

## User Input

**Name:** {name}
**Specialty:** {specialty}
**Vibe:** {vibe}

## Core Truths (Apply to ALL personas)

{core_truths}

## Output Format

Generate ONLY valid JSON in this exact structure:

{{
  "spec": "persona_profile_v1",
  "spec_version": "1.0",
  "data": {{
    "name": "{name}",
    
    "who_you_are": "A detailed description (2-3 sentences) expanding on the specialty. Be specific about their expertise and approach.",
    
    "your_vibe": "{vibe} - expanded into detailed communication style (2-3 sentences). How do they speak? What's their energy like?",
    
    "your_worldview": "A philosophy or worldview (2-3 sentences) that aligns with their specialty and vibe. What do they believe about helping people?",
    
    "session_template": "A warm, welcoming opening statement that reflects their vibe. 1-2 sentences. This is their first message to users.",
    
    "session_examples": [
      {{
        "user_situation": "I'm feeling anxious about work.",
        "your_response": "A response in the advisor's voice that demonstrates their specialty and vibe. Should be practical and warm. 2-4 sentences.",
        "approach": "Brief description (1 sentence) of the approach shown."
      }},
      {{
        "user_situation": "I keep making the same mistakes—I'm stuck.",
        "your_response": "Another response showing a different situation but same consistent voice and approach.",
        "approach": "Brief description of this approach."
      }}
    ],
    
    "tags": [
      "3-5 relevant keywords based on specialty and vibe",
      "Examples: 'wisdom', 'maritime', 'practical', 'warm', 'mentor'"
    ],
    
    "visuals": {{
      "primaryColor": "#E8D0A0",
      "secondaryColor": "#D8C090",
      "borderColor": "#B8A070",
      "textColor": "#483018",
      "chatBubble": {{
        "backgroundColor": "#F8F0D8",
        "borderColor": "#B8A070",
        "borderWidth": "2px",
        "borderStyle": "solid",
        "borderRadius": "8px",
        "textColor": "#483018"
      }},
      "selectionCard": {{
        "backgroundColor": "#E8D0A0",
        "hoverBackgroundColor": "#E8D0A0CC",
        "borderColor": "#B8A070",
        "textColor": "#483018"
      }},
      "chatBackdrop": {{
        "type": "gradient",
        "gradient": "linear-gradient(180deg, #E8D0A0 0%, #D8C090 50%, #C8B080 100%)",
        "patternOpacity": 0,
        "overlayColor": "rgba(255, 255, 255, 0.05)"
      }},
      "icon": "lucide:user"
    }},
    
    "crisis_protocol": "If user expresses self-harm, suicidal thoughts, or immediate danger: (1) Prioritize safety and validate their courage in sharing. (2) Assess immediacy: 'Are you safe right now? Do you have a plan?' (3) Provide resources immediately: **988 Suicide & Crisis Lifeline** (call or text 988, available 24/7) or **Crisis Text Line** (text HOME to 741741). (4) If imminent danger, encourage calling 911 or going to nearest ER. (5) Do not end session abruptly—stay present until safety plan is established.",
    
    "hotlines": [
      {{
        "name": "988 Suicide & Crisis Lifeline",
        "contact": "Call or text 988",
        "available": "24/7"
      }},
      {{
        "name": "Crisis Text Line",
        "contact": "Text HOME to 741741",
        "available": "24/7"
      }},
      {{
        "name": "SAMHSA National Helpline",
        "contact": "1-800-662-4357",
        "info": "Mental health and substance abuse referrals"
      }}
    ]
  }}
}}

## Guidelines

1. **Voice Consistency**: Both session_examples must sound like the same person
2. **Practical Advice**: Responses should offer concrete next steps, not just validation
3. **Warmth**: Even "gruff" advisors should show they care
4. **Specificity**: Expand on the specialty with concrete examples
5. **Visuals**: Use the GBA color palette provided (warm off-whites, browns, tans)
6. **Icon**: Choose an appropriate Lucide icon based on specialty:
   - "lucide:anchor" for maritime/nautical
   - "lucide:compass" for guidance/mentorship
   - "lucide:sparkles" for spiritual/mystical
   - "lucide:heart" for emotional support
   - "lucide:book-open" for wisdom/learning
   - "lucide:user" as default

## Critical Rules

- Output ONLY the JSON object
- No markdown code blocks (```)
- No explanatory text
- Ensure valid JSON syntax
- Name field must exactly match: "{name}"

Generate the persona now:"""
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parse and clean LLM response into structured JSON.
        
        Handles various LLM output formats including markdown code blocks.
        
        Args:
            response: Raw text from LLM
        
        Returns:
            Parsed JSON dict
        
        Raises:
            json.JSONDecodeError: If response isn't valid JSON
        """
        json_text = response.strip()
        
        # Extract from markdown code blocks
        if "```json" in json_text:
            start = json_text.find("```json") + 7
            end = json_text.find("```", start)
            if end == -1:
                end = len(json_text)
            json_text = json_text[start:end].strip()
        elif "```" in json_text:
            start = json_text.find("```") + 3
            end = json_text.find("```", start)
            if end == -1:
                end = len(json_text)
            json_text = json_text[start:end].strip()
        
        # Remove any trailing commas before closing braces (common LLM error)
        json_text = json_text.replace(',\n}', '\n}').replace(',\n  }', '\n  }').replace(',}', '}')
        
        return json.loads(json_text)
    
    def _validate_persona_structure(
        self,
        persona: Dict[str, Any],
        expected_name: str
    ) -> None:
        """
        Validate that generated persona has required structure.
        
        Args:
            persona: Parsed persona dict
            expected_name: Name that should be in persona
        
        Raises:
            ValueError: If structure is invalid
        """
        # Check top-level structure
        if not isinstance(persona, dict):
            raise ValueError("Persona must be a dictionary")
        
        if persona.get('spec') != 'persona_profile_v1':
            raise ValueError(f"Invalid spec: {persona.get('spec')}")
        
        if 'data' not in persona:
            raise ValueError("Persona missing 'data' key")
        
        data = persona['data']
        
        # Check required data fields
        required = ['name', 'who_you_are', 'your_vibe', 'your_worldview', 
                   'session_template', 'session_examples', 'tags', 'visuals',
                   'crisis_protocol', 'hotlines']
        
        missing = [f for f in required if f not in data]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
        
        # Verify name matches
        if data['name'] != expected_name:
            raise ValueError(
                f"Name mismatch: expected '{expected_name}', got '{data['name']}'"
            )
        
        # Validate session_examples structure
        if not isinstance(data['session_examples'], list):
            raise ValueError("session_examples must be a list")
        
        for i, example in enumerate(data['session_examples']):
            if not isinstance(example, dict):
                raise ValueError(f"session_examples[{i}] must be an object")
            if 'user_situation' not in example or 'your_response' not in example:
                raise ValueError(
                    f"session_examples[{i}] missing required fields"
                )


# Global singleton instance
advisor_generator = AdvisorGenerator()
