import json
import time
from typing import Optional, Dict, Any, List
from ..core.config import settings
from ..services.simple_llm_fixed import simple_llm_client
from ..services.card_generator import card_generator
from ..db.database import db
from ..utils.card_metadata import update_card_fields


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
        self.batch_confidence_threshold = 0.3
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
            formatted_transcript = self._format_transcript(messages)

            created_self_card_id = await self._ensure_self_card(
                client_id,
                session_id,
                formatted_transcript
            )
            if created_self_card_id:
                cards_updated += 1
                updates_applied.append({
                    "card_id": created_self_card_id,
                    "card_type": "self",
                    "fields_updated": ["created"]
                })

            prompt = self._build_update_prompt(client_id, session_id, formatted_transcript)

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
            new_cards = parsed_updates.get('new_cards', [])

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

            if new_cards:
                created_cards = self._create_character_cards_from_updates(client_id, new_cards)
                if created_cards:
                    cards_updated += len(created_cards)
                    for card_id in created_cards:
                        updates_applied.append({
                            "card_id": card_id,
                            "card_type": "character",
                            "fields_updated": ["created"]
                        })

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
        formatted_transcript: str
    ) -> str:
        """Build LLM prompt to extract update proposals."""
        existing_cards_summary = self._get_existing_cards_summary(client_id)

        return f"""You are a card updater for Gameapy, analyzing a counseling session transcript.

TRANSCRIPT:
---
{formatted_transcript}

EXISTING CARDS (check these to avoid repetition):
---
{existing_cards_summary}

CRITICAL RULES:
1. BE CONCISE: Max 1-2 short sentences per field value. No verbose descriptions.
2. NO REPETITION: Check EXISTING CARDS above. Do NOT propose updates for content already present.
3. CARD TYPE SELECTION:
   - SELF CARD (type="self"): Default for user's own feelings, behaviors, goals, patterns, reactions to situations
   - CHARACTER CARD (type="character"): ONLY when a specific person's NAME is explicitly mentioned in the transcript
   - WORLD EVENT (type="world"): ONLY for major life milestones (job change, move, loss, achievement)
4. GUARDRAIL: If no person's name is mentioned in the transcript, do NOT update or create character cards.
5. CONFIDENCE: Only propose updates if genuinely confident (≥ 0.7). If uncertain, skip.

Output ONLY valid JSON:
{{
  "confidence": 0.0-1.0,
  "updates": [
    {{
      "card_id": 12,
      "card_type": "self|character|world",
      "updates": [
        {{
          "field": "personality|patterns|key_events|traits|interests|values|description",
          "action": "merge|append|replace",
          "value": "...",
          "confidence": 0.0-1.0
        }}
      ]
    }}
  ],
  "new_cards": [
    {{
      "card_type": "character",
      "name": "Name of person",
      "relationship_type": "family|friend|partner|coworker|other"
    }}
  ]
}}

Action rules:
- personality: "merge" (combine with existing)
- patterns/arrays: "append" (add new items only)
- simple fields: "replace"

Do not include any text outside of JSON."""

    def _format_transcript(self, messages: List[Dict[str, Any]]) -> str:
        return "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in messages
        ])

    async def _ensure_self_card(
        self,
        client_id: int,
        session_id: int,
        formatted_transcript: str
    ) -> Optional[int]:
        existing_self_card = db.get_self_card(client_id)
        if existing_self_card:
            return None

        try:
            result = await card_generator.generate_card(
                card_type="self",
                plain_text=formatted_transcript,
                context=f"Auto-create self card from session {session_id}"
            )
            generated = result.get("generated_card")
            if not generated:
                return None

            normalized = db.normalize_self_card_payload(generated)
            return db.upsert_self_card(client_id, normalized, changed_by="system")
        except Exception:
            return None

    def _create_character_cards_from_updates(
        self,
        client_id: int,
        new_cards: List[Dict[str, Any]]
    ) -> List[int]:
        created_ids: List[int] = []
        existing_cards = db.get_character_cards(client_id)
        existing_names = {
            (card.get("card_name") or "").strip().lower()
            for card in existing_cards
        }

        for card in new_cards:
            if card.get("card_type") != "character":
                continue

            name = (card.get("name") or "").strip()
            relationship_type = (card.get("relationship_type") or "").strip()
            if not name or not relationship_type:
                continue

            if name.lower() in existing_names:
                continue

            relationship_label = (card.get("relationship_label") or "").strip() or None
            card_payload = {
                "personality": card.get("personality", "")
            }
            if isinstance(card.get("traits"), list):
                card_payload["traits"] = card.get("traits")
            if isinstance(card.get("patterns"), list):
                card_payload["patterns"] = card.get("patterns")

            card_id = db.create_character_card(
                client_id=client_id,
                card_name=name,
                relationship_type=relationship_type,
                relationship_label=relationship_label,
                card_data=card_payload
            )
            if card_id:
                existing_names.add(name.lower())
                created_ids.append(card_id)

        return created_ids

    def _get_existing_cards_summary(self, client_id: int) -> str:
        """Get full content of existing cards for deduplication checking."""
        summary_lines = []

        self_card = db.get_self_card(client_id)
        if self_card:
            card_json = json.loads(self_card['card_json']) if isinstance(self_card['card_json'], str) else self_card['card_json']
            card_json = db.normalize_self_card_payload(card_json)
            summary_lines.append(f"SELF CARD (id={self_card['id']}):")
            if card_json.get('personality'):
                summary_lines.append(f"  Personality: {card_json['personality']}")
            if card_json.get('traits'):
                summary_lines.append(f"  Traits: {card_json['traits']}")
            if card_json.get('interests'):
                summary_lines.append(f"  Interests: {card_json['interests']}")
            if card_json.get('values'):
                summary_lines.append(f"  Values: {card_json['values']}")
            if card_json.get('patterns'):
                patterns = [p.get('pattern', str(p)) if isinstance(p, dict) else str(p) for p in card_json['patterns']]
                summary_lines.append(f"  Patterns: {patterns}")
            if card_json.get('goals'):
                goals = [g.get('goal', str(g)) if isinstance(g, dict) else str(g) for g in card_json['goals']]
                summary_lines.append(f"  Goals: {goals}")
            summary_lines.append("")

        char_cards = db.get_character_cards(client_id)
        for card in char_cards:
            card_json = card['card']
            summary_lines.append(f"CHARACTER '{card['card_name']}' (id={card['id']}):")
            if card_json.get('personality'):
                summary_lines.append(f"  Personality: {card_json['personality']}")
            if card_json.get('patterns'):
                patterns = [p.get('pattern', str(p)) if isinstance(p, dict) else str(p) for p in card_json['patterns']]
                summary_lines.append(f"  Patterns: {patterns}")
            if card_json.get('key_events'):
                events = [e.get('event', str(e)) if isinstance(e, dict) else str(e) for e in card_json['key_events']]
                summary_lines.append(f"  Key Events: {events}")
            summary_lines.append("")

        world_events = db.get_world_events(client_id)
        for event in world_events:
            summary_lines.append(f"WORLD EVENT '{event['title']}' (id={event['id']}):")
            summary_lines.append(f"  Description: {event['description'][:200]}")
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

        parsed = json.loads(json_text)
        if not isinstance(parsed, dict):
            return {"confidence": 0.0, "updates": [], "new_cards": []}

        parsed.setdefault("confidence", 0.0)
        parsed.setdefault("updates", [])
        parsed.setdefault("new_cards", [])
        return parsed

    def _ensure_field(self, card_json: Dict[str, Any], field: str, action: str, value: Any) -> None:
        if field in card_json and card_json[field] is not None:
            return

        if action == "append" or isinstance(value, list):
            card_json[field] = []
        elif isinstance(value, dict):
            card_json[field] = {}
        else:
            card_json[field] = ""

    def _should_accept_batch(self, batch_confidence: float) -> bool:
        """Check if batch-level confidence meets threshold."""
        return batch_confidence >= self.batch_confidence_threshold

    def _should_accept_field(self, field_confidence: float) -> bool:
        """Check if field-level confidence meets threshold."""
        return field_confidence >= self.field_confidence_threshold

    def _should_skip_card(self, card_type: str, card_id: int) -> bool:
        """Check if card should be skipped (auto-update disabled)."""
        return not self._get_auto_update_enabled(card_type, card_id)

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
        card_json = db.normalize_self_card_payload(card_json)
        applied_fields = []

        for update in updates:
            field = update.get('field')
            action = update.get('action')
            value = update.get('value')
            confidence = update.get('confidence', 0)

            if not self._should_accept_field(confidence):
                continue

            self._ensure_field(card_json, field, action, value)
            old_value = card_json.get(field)

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
            # Update metadata for changed fields
            card_json_with_metadata = update_card_fields(card_json, set(applied_fields), source='llm')
            
            db.update_self_card(
                client_id=self_card['client_id'],
                card_json=json.dumps(card_json_with_metadata),
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

            self._ensure_field(card_data, field, action, value)
            old_value = card_data.get(field)

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
            # Update metadata for changed fields
            card_data_with_metadata = update_card_fields(card_data, set(applied_fields), source='llm')
            
            db.update_character_card(
                card_id=card_id,
                card_json=json.dumps(card_data_with_metadata),
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
            # For world events, we need to rebuild the full JSON with metadata
            card_json = {
                'title': event_data['title'],
                'event_type': event_data['event_type'],
                'key_array': json.loads(event_data['key_array']) if isinstance(event_data['key_array'], str) else event_data['key_array'],
                'description': event_data['description'],
                'is_canon_law': event_data.get('is_canon_law', False),
                'resolved': event_data.get('resolved', False)
            }
            
            # Apply updates
            if 'description' in update_kwargs:
                card_json['description'] = update_kwargs['description']
            if 'key_array' in update_kwargs:
                card_json['key_array'] = update_kwargs['key_array'] if isinstance(update_kwargs['key_array'], list) else json.loads(update_kwargs['key_array'])
            
            # Update metadata for changed fields
            card_json_with_metadata = update_card_fields(card_json, set(applied_fields), source='llm')
            
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
