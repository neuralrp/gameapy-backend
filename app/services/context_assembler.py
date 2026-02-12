"""
Context assembly for chat - loads relevant cards based on recency and pinning.
"""

from typing import List, Dict, Any, Optional, Set
from ..db.database import db
from ..core.config import settings
import json


class ContextAssembler:
    """Assemble context for chat by loading relevant cards."""
    
    def assemble_context(
        self,
        client_id: int,
        session_id: int,
        user_message: str
    ) -> Dict[str, Any]:
        """
        Assemble full context for chat.
        
        Loading priority:
        1. Self card (always)
        2. Pinned cards (always)
        3. Cards mentioned in current session (always)
        4. Recent cards (top N by recency, from config)
        
        Returns:
            {
                "self_card": Optional[Dict],
                "pinned_cards": List[Dict],
                "current_mentions": List[Dict],
                "recent_cards": List[Dict],
                "total_cards_loaded": int
            }
        """
        context = {
            'self_card': None,
            'pinned_cards': [],
            'current_mentions': [],
            'recent_cards': []
        }
        
        # 1. Always load self card
        self_card = db.get_self_card(client_id)
        if self_card:
            context['self_card'] = self._format_self_card(self_card)
        
        # 2. Always load pinned cards
        pinned = db.get_pinned_cards(client_id)
        context['pinned_cards'] = pinned
        
        # Collect IDs to exclude from recent cards
        exclude_ids: Set[int] = set()
        if self_card:
            exclude_ids.add(self_card['id'])
        for card in pinned:
            exclude_ids.add(card['id'])
        
        # 3. Load cards mentioned in current session
        current_mentions = self._get_current_session_mentions(
            client_id, session_id, exclude_ids
        )
        context['current_mentions'] = current_mentions
        
        for card in current_mentions:
            exclude_ids.add(card['id'])
        
        # 4. Load recent cards (configurable limit)
        recent_limit = settings.recent_card_session_limit
        recent_cards = self._get_recent_cards(
            client_id, exclude_ids, recent_limit
        )
        context['recent_cards'] = recent_cards
        
        # Calculate total
        total = (
            (1 if context['self_card'] else 0) +
            len(context['pinned_cards']) +
            len(context['current_mentions']) +
            len(context['recent_cards'])
        )
        context['total_cards_loaded'] = total
        
        return context
    
    def _format_self_card(self, self_card: Dict) -> Dict:
        """Format self card for context."""
        payload = json.loads(self_card['card_json'])
        normalized_payload = db.normalize_self_card_payload(payload)
        return {
            'id': self_card['id'],
            'card_type': 'self',
            'payload': normalized_payload,
            'auto_update_enabled': self_card.get('auto_update_enabled', True),
            'is_pinned': self_card.get('is_pinned', False)
        }
    
    def _get_current_session_mentions(
        self,
        client_id: int,
        session_id: int,
        exclude_ids: Set[int]
    ) -> List[Dict]:
        """Get cards mentioned in current session."""
        mentions = db.get_entity_mentions(
            client_id=client_id,
            limit=100
        )
        
        cards = []
        seen_ids = set(exclude_ids)
        
        for mention in mentions:
            if mention.get('session_id') != session_id:
                continue
                
            try:
                card_id = int(mention['entity_ref'])
                card_type = mention['entity_type'].replace('_card', '')
                
                if card_id in seen_ids:
                    continue
                seen_ids.add(card_id)
                
                card = self._get_card_by_id(card_type, card_id, client_id)
                if card:
                    cards.append(card)
            except (ValueError, KeyError):
                continue
        
        return cards
    
    def _get_recent_cards(
        self,
        client_id: int,
        exclude_ids: Set[int],
        session_limit: int
    ) -> List[Dict]:
        """
        Get recent cards by recency (mentioned in last N sessions).
        """
        # Get recent mentions
        recent_mentions = db.get_entity_mentions(
            client_id=client_id,
            limit=100
        )

        # Find unique sessions (most recent first)
        session_ids = []
        seen_sessions = set()
        for m in recent_mentions:
            sid = m.get('session_id')
            if sid and sid not in seen_sessions:
                seen_sessions.add(sid)
                session_ids.append(sid)

        # Take last N sessions
        recent_session_ids = set(session_ids[:session_limit])

        # Get unique card IDs from these sessions
        card_refs = {}
        for mention in recent_mentions:
            if mention.get('session_id') not in recent_session_ids:
                continue

            try:
                card_id = int(mention['entity_ref'])
                if card_id in exclude_ids:
                    continue

                card_type = mention['entity_type'].replace('_card', '')
                mentioned_at = mention.get('mentioned_at', '')

                # Keep most recent mention
                if card_id not in card_refs or mentioned_at > card_refs[card_id][1]:
                    card_refs[card_id] = (card_type, mentioned_at)
            except (ValueError, KeyError):
                continue

        # Load cards (sorted by recency)
        cards = []
        for card_id, (card_type, _) in sorted(
            card_refs.items(),
            key=lambda x: x[1][1],
            reverse=True
        ):
            card = self._get_card_by_id(card_type, card_id, client_id)
            if card:
                cards.append(card)

        return cards
    
    def _get_card_by_id(
        self,
        card_type: str,
        card_id: int,
        client_id: int
    ) -> Optional[Dict]:
        """Load card by type and ID."""
        try:
            if card_type == 'self':
                card = db.get_self_card_by_id(card_id)
                if card:
                    return {
                        'id': card['id'],
                        'card_type': 'self',
                        'payload': json.loads(card['card_json']),
                        'auto_update_enabled': card.get('auto_update_enabled', True),
                        'is_pinned': card.get('is_pinned', False)
                    }

            elif card_type == 'character':
                char_cards = db.get_character_cards(client_id)
                for card in char_cards:
                    if card['id'] == card_id:
                        payload = {**card['card'], 'name': card['card_name']}
                        if card.get('relationship_label'):
                            payload['relationship_label'] = card['relationship_label']
                        return {
                            'id': card['id'],
                            'card_type': 'character',
                            'payload': payload,
                            'auto_update_enabled': card.get('auto_update_enabled', True),
                            'is_pinned': card.get('is_pinned', False)
                        }

            elif card_type == 'world':
                events = db.get_world_events(client_id)
                for event in events:
                    if event['id'] == card_id:
                        return {
                            'id': event['id'],
                            'card_type': 'world',
                            'payload': {
                                'title': event['title'],
                                'description': event['description'],
                                'key_array': json.loads(event['key_array']),
                                'event_type': event['event_type'],
                                'resolved': event.get('resolved', False)
                            },
                            'auto_update_enabled': event.get('auto_update_enabled', True),
                            'is_pinned': event.get('is_pinned', False)
                        }

            return None
        except Exception:
            return None


# Global instance
context_assembler = ContextAssembler()
