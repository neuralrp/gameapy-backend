import json
import time
from typing import Optional, Dict, Any, List
from ..core.config import settings
from ..services.simple_llm_fixed import simple_llm_client
from ..db.database import db


class CardUpdater:
    """
    Invisible auto-update service for character cards, self cards, and world events.

    Analyzes counseling session transcripts and proposes updates with confidence scores.
    Only applies updates if:
    - auto_update_enabled is True
    - User hasn't manually edited since last AI update
    - Confidence thresholds are met (batch ≥ 0.5, per-field ≥ 0.7)
    """

    def __init__(self):
        self.default_model = settings.default_model or "anthropic/claude-3-haiku"
        self.batch_confidence_threshold = 0.5
        self.field_confidence_threshold = 0.7

    async def analyze_and_update(
        self,
        client_id: int,
        session_id: int,
        messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze session transcript and apply updates invisibly.

        Returns:
            {
                "cards_updated": int,
                "cards_skipped": int,
                "updates_applied": List[Dict]
            }
        """
        start_time = time.time()

        cards_updated = 0
        cards_skipped = 0
        updates_applied = []

        try:
            prompt = self._build_update_prompt(client_id, session_id, messages)

            response = await simple_llm_client.chat_completion(
                messages=[{"role": "system", "content": prompt}],
                model=self.default_model,
                temperature=0.7,
                max_tokens=2000
            )

            duration_ms = int((time.time() - start_time) * 1000)
            content = response['choices'][0]['message']['content']
            parsed_updates = self._parse_llm_updates(content)

            if not self._should_accept_batch(parsed_updates.get('confidence', 0)):
                await db._log_performance_metric(
                    operation="card_update",
                    duration_ms=duration_ms,
                    status="skipped",
                    error_message="Batch confidence below threshold",
                    metadata={
                        "session_id": session_id,
                        "client_id": client_id,
                        "batch_confidence": parsed_updates.get('confidence', 0),
                        "model": self.default_model
                    }
                )
                return {
                    "cards_updated": 0,
                    "cards_skipped": 0,
                    "updates_applied": []
                }

            updates_list = parsed_updates.get('updates', [])

            for update_proposal in updates_list:
                card_id = update_proposal.get('card_id')
                card_type = update_proposal.get('card_type')
                card_updates = update_proposal.get('updates', [])

                if self._should_skip_card(card_type, card_id):
                    cards_skipped += 1
                    continue

                try:
                    applied_fields = self._apply_update(card_type, card_id, card_updates, client_id)
                    if applied_fields:
                        cards_updated += 1
                        updates_applied.append({
                            "card_id": card_id,
                            "card_type": card_type,
                            "fields_updated": applied_fields
                        })
                except Exception as e:
                    cards_skipped += 1
                    continue

            await db._log_performance_metric(
                operation="card_update",
                duration_ms=duration_ms,
                status="success",
                error_message=None,
                metadata={
                    "session_id": session_id,
                    "client_id": client_id,
                    "cards_updated": cards_updated,
                    "cards_skipped": cards_skipped,
                    "model": self.default_model
                }
            )

            return {
                "cards_updated": cards_updated,
                "cards_skipped": cards_skipped,
                "updates_applied": updates_applied
            }

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            await db._log_performance_metric(
                operation="card_update",
                duration_ms=duration_ms,
                status="error",
                error_message=str(e),
                metadata={
                    "session_id": session_id,
                    "client_id": client_id,
                    "model": self.default_model
                }
            )
            raise

    def _build_update_prompt(
        self,
        client_id: int,
        session_id: int,
        messages: List[Dict[str, Any]]
    ) -> str:
        """Build LLM prompt to extract update proposals."""
        formatted_transcript = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in messages
        ])

        existing_cards_summary = self._get_existing_cards_summary(client_id)

        return f"""You are a card updater for Gameapy, analyzing a counseling session transcript.

TRANSCRIPT:
---
{formatted_transcript}

EXISTING CARDS:
---
{existing_cards_summary}

Output ONLY valid JSON proposing updates:
{{
  "confidence": 0.0-1.0,  // Batch-level confidence
  "updates": [
    {{
      "card_id": 12,
      "card_type": "character|self|world",
      "updates": [
        {{
          "field": "personality|patterns|key_events|user_feelings|key_array|description|traits|interests|values",
          "action": "merge|append|replace",
          "value": "...",
          "reason": "...",
          "confidence": 0.0-1.0  // Per-field confidence
        }}
      ]
    }}
  ]
}}

Rules:
- Only propose updates if you're confident (confidence ≥ 0.7 per field)
- For personality: use "merge" action
- For patterns: use "append" action
- For arrays: use "append" action
- For simple fields: use "replace" action
- If batch confidence < 0.5, return empty updates array

Do not include any text outside of JSON."""

    def _get_existing_cards_summary(self, client_id: int) -> str:
        """Get summary of existing cards for context."""
        summary_lines = []

        self_card = db.get_self_card(client_id)
        if self_card:
            card_json = json.loads(self_card['card_json']) if isinstance(self_card['card_json'], str) else self_card['card_json']
            summary_lines.append(f"Self Card (id={self_card['id']}):")
            summary_lines.append(f"  Personality: {card_json.get('personality', 'N/A')}")
            summary_lines.append(f"  Traits: {card_json.get('traits', [])}")
            summary_lines.append("")

        char_cards = db.get_character_cards(client_id)
        for card in char_cards:
            card_json = card['card']
            summary_lines.append(f"Character Card '{card['card_name']}' (id={card['id']}):")
            summary_lines.append(f"  Personality: {card_json.get('personality', 'N/A')}")
            summary_lines.append(f"  Patterns: {len(card_json.get('patterns', []))} patterns")
            summary_lines.append("")

        world_events = db.get_world_events(client_id)
        for event in world_events:
            summary_lines.append(f"World Event '{event['title']}' (id={event['id']}):")
            summary_lines.append(f"  Description: {event['description'][:100]}...")
            summary_lines.append("")

        return "\n".join(summary_lines)

    def _parse_llm_updates(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured updates."""
        json_text = response.strip()

        if "```json" in json_text:
            start = json_text.find("```json") + 7
            end = json_text.find("```", start)
            json_text = json_text[start:end].strip()
        elif "```" in json_text:
            start = json_text.find("```") + 3
            end = json_text.find("```", start)
            json_text = json_text[start:end].strip()

        return json.loads(json_text)

    def _should_accept_batch(self, batch_confidence: float) -> bool:
        """Check if batch-level confidence meets threshold."""
        return batch_confidence >= self.batch_confidence_threshold

    def _should_accept_field(self, field_confidence: float) -> bool:
        """Check if field-level confidence meets threshold."""
        return field_confidence >= self.field_confidence_threshold

    def _should_skip_card(self, card_type: str, card_id: int) -> bool:
        """Check if card should be skipped (user edited or auto-update disabled)."""
        if not self._get_auto_update_enabled(card_type, card_id):
            return True

        last_ai_update = db.get_last_ai_update(card_type, card_id)
        user_edit = db.get_recent_user_edit(
            entity_type=f"{card_type}_card",
            entity_id=card_id,
            since_timestamp=last_ai_update
        )

        return user_edit is not None

    def _get_auto_update_enabled(self, card_type: str, card_id: int) -> Optional[bool]:
        """Get current auto_update_enabled value for a card."""
        return db._get_auto_update_enabled(card_type, card_id)

    def _apply_update(
        self,
        card_type: str,
        card_id: int,
        updates: List[Dict[str, Any]],
        client_id: int
    ) -> List[str]:
        """Apply updates to a card with conflict resolution."""
        applied_fields = []

        if card_type == 'self':
            return self._apply_self_card_update(card_id, updates)
        elif card_type == 'character':
            return self._apply_character_card_update(card_id, updates, client_id)
        elif card_type == 'world':
            return self._apply_world_event_update(card_id, updates, client_id)
        else:
            return []

    def _apply_self_card_update(
        self,
        card_id: int,
        updates: List[Dict[str, Any]]
    ) -> List[str]:
        """Apply updates to self card (read-modify-write)."""
        self_card = db.get_self_card_by_id(card_id)
        if not self_card:
            return []

        card_json = json.loads(self_card['card_json']) if isinstance(self_card['card_json'], str) else self_card['card_json']
        applied_fields = []

        for update in updates:
            field = update.get('field')
            action = update.get('action')
            value = update.get('value')
            confidence = update.get('confidence', 0)

            if not self._should_accept_field(confidence):
                continue

            if field in card_json:
                old_value = card_json[field]

                if action == 'replace':
                    card_json[field] = value
                    applied_fields.append(field)
                elif action == 'merge' and isinstance(old_value, str) and isinstance(value, str):
                    card_json[field] = self._merge_personality(old_value, value)
                    applied_fields.append(field)
                elif action == 'append' and isinstance(old_value, list) and isinstance(value, list):
                    if field == 'patterns':
                        card_json[field] = self._append_patterns(old_value, value)
                    else:
                        card_json[field] = old_value + value
                    applied_fields.append(field)

        if applied_fields:
            db.update_self_card(
                client_id=self_card['client_id'],
                card_json=json.dumps(card_json),
                changed_by='system'
            )

        return applied_fields

    def _apply_character_card_update(
        self,
        card_id: int,
        updates: List[Dict[str, Any]],
        client_id: int
    ) -> List[str]:
        """Apply updates to character card."""
        char_card = db.get_character_cards(client_id)
        if not char_card:
            return []

        card_data = None
        for card in char_card:
            if card['id'] == card_id:
                card_data = card['card']
                break

        if not card_data:
            return []

        applied_fields = []

        for update in updates:
            field = update.get('field')
            action = update.get('action')
            value = update.get('value')
            confidence = update.get('confidence', 0)

            if not self._should_accept_field(confidence):
                continue

            if field in card_data:
                old_value = card_data[field]

                if action == 'replace':
                    card_data[field] = value
                    applied_fields.append(field)
                elif action == 'merge' and isinstance(old_value, str) and isinstance(value, str):
                    card_data[field] = self._merge_personality(old_value, value)
                    applied_fields.append(field)
                elif action == 'append' and isinstance(old_value, list) and isinstance(value, list):
                    if field == 'patterns':
                        card_data[field] = self._append_patterns(old_value, value)
                    else:
                        card_data[field] = old_value + value
                    applied_fields.append(field)

        if applied_fields:
            db.update_character_card(
                card_id=card_id,
                card_json=json.dumps(card_data),
                changed_by='system'
            )

        return applied_fields

    def _apply_world_event_update(
        self,
        card_id: int,
        updates: List[Dict[str, Any]],
        client_id: int
    ) -> List[str]:
        """Apply updates to world event."""
        events = db.get_world_events(client_id)
        if not events:
            return []

        event_data = None
        for event in events:
            if event['id'] == card_id:
                event_data = event
                break

        if not event_data:
            return []

        applied_fields = []
        update_kwargs = {}

        for update in updates:
            field = update.get('field')
            action = update.get('action')
            value = update.get('value')
            confidence = update.get('confidence', 0)

            if not self._should_accept_field(confidence):
                continue

            if field == 'description' or field == 'key_array':
                if action == 'replace':
                    update_kwargs[field] = value
                    applied_fields.append(field)
            elif field in event_data:
                if action == 'replace':
                    update_kwargs[field] = value
                    applied_fields.append(field)

        if applied_fields:
            if 'key_array' in update_kwargs and isinstance(update_kwargs['key_array'], list):
                update_kwargs['key_array'] = json.dumps(update_kwargs['key_array'])
            update_kwargs['changed_by'] = 'system'
            db.update_world_event(card_id, **update_kwargs)

        return applied_fields

    def _merge_personality(self, old: str, new: str) -> str:
        """Merge personality strings with deduplication."""
        old_traits = [t.strip().lower() for t in old.split(',') if t.strip()]
        new_traits = [t.strip().lower() for t in new.split(',') if t.strip()]

        all_traits = old_traits.copy()
        for trait in new_traits:
            if trait and trait not in all_traits:
                all_traits.append(trait)

        return ', '.join([t.capitalize() for t in all_traits])

    def _append_patterns(
        self,
        old_patterns: List,
        new_patterns: List
    ) -> List:
        """Append pattern objects, dedupe by pattern string."""
        existing = {p.get('pattern', '').lower() for p in old_patterns if p.get('pattern')}

        for pattern in new_patterns:
            pattern_key = pattern.get('pattern', '').lower()
            if pattern_key and pattern_key not in existing:
                old_patterns.append(pattern)
                existing.add(pattern_key)

        return old_patterns


# Global card updater instance
card_updater = CardUpdater()
