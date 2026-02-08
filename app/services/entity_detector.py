"""
Simplified entity detection using keyword matching.
No embeddings, no semantic search - just names and relationship keywords.
"""

import json
from typing import List, Dict, Any, Optional
from ..db.database import db


class EntityDetector:
    """Keyword-based entity detection for cards."""
    
    # Static relationship keywords for matching
    RELATIONSHIP_KEYWORDS = {
        'family': [
            'mom', 'mother', 'mama', 'mum', 'mommy',
            'dad', 'father', 'papa', 'pop', 'daddy',
            'parent', 'parents',
            'brother', 'sister', 'sibling', 'siblings',
            'grandmother', 'grandma', 'grandfather', 'grandpa',
            'grandparent', 'grandparents',
            'aunt', 'uncle', 'cousin',
            'niece', 'nephew'
        ],
        'friend': [
            'friend', 'friends', 'best friend', 'bestfriend',
            'buddy', 'pal', 'bff', 'homie'
        ],
        'romantic': [
            'partner', 'boyfriend', 'bf', 'girlfriend', 'gf',
            'wife', 'husband', 'spouse', 'fiancé', 'fiancée',
            'significant other', 'so'
        ],
        'coworker': [
            'boss', 'manager', 'supervisor', 'director',
            'coworker', 'coworkers', 'colleague', 'colleagues',
            'teammate', 'teammates',
            'teacher', 'professor', 'instructor', 'coach', 'mentor'
        ]
    }
    
    def detect_mentions(
        self,
        message_text: str,
        client_id: int
    ) -> List[Dict[str, Any]]:
        """
        Detect which cards are mentioned in a message.
        
        Returns:
            [{"card_id": int, "card_type": str, "match_type": str}]
        """
        mentions = []
        normalized_text = message_text.lower()
        
        # Load all cards for this client
        char_cards = db.get_character_cards(client_id)
        world_events = db.get_world_events(client_id)
        
        # Check character cards
        for card in char_cards:
            card_id = card['id']
            card_name = card['card_name'].lower()
            relationship_type = card.get('relationship_type', '').lower()
            
            # Check exact name match
            if card_name in normalized_text:
                mentions.append({
                    'card_id': card_id,
                    'card_type': 'character',
                    'match_type': 'name'
                })
                continue
            
            # Check relationship keywords
            if self._matches_relationship_keywords(
                relationship_type, normalized_text
            ):
                mentions.append({
                    'card_id': card_id,
                    'card_type': 'character',
                    'match_type': 'keyword'
                })
        
        # Check world events (life events)
        for event in world_events:
            card_id = event['id']
            event_title = event['title'].lower()
            
            # Check title match
            if event_title in normalized_text:
                mentions.append({
                    'card_id': card_id,
                    'card_type': 'world',
                    'match_type': 'title'
                })
                continue
            
            # Check key_array keywords
            key_array = json.loads(event['key_array']) \
                if isinstance(event['key_array'], str) \
                else event['key_array']
            
            for keyword in key_array:
                if keyword.lower() in normalized_text:
                    mentions.append({
                        'card_id': card_id,
                        'card_type': 'world',
                        'match_type': 'keyword'
                    })
                    break
        
        # Deduplicate by card_id
        seen = set()
        unique_mentions = []
        for m in mentions:
            key = (m['card_id'], m['card_type'])
            if key not in seen:
                seen.add(key)
                unique_mentions.append(m)
        
        return unique_mentions
    
    def _matches_relationship_keywords(
        self,
        relationship_type: str,
        text: str
    ) -> bool:
        """Check if text contains keywords matching relationship type."""
        keywords = self.RELATIONSHIP_KEYWORDS.get(relationship_type, [])
        return any(kw in text for kw in keywords)


# Global instance
entity_detector = EntityDetector()