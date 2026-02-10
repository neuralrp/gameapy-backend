"""
Simplified entity detection using keyword matching.
No embeddings, no semantic search - just names and relationship keywords.

Improvements:
- Word boundary matching to avoid false positives
- Text preprocessing: strip possessives, normalize plurals
- Custom relationship labels for specific matching (e.g., "Sister" for Paula)
- Event type matching for world events
"""

import json
import re
from typing import List, Dict, Any, Optional
from ..db.database import db


class EntityDetector:
    """Keyword-based entity detection for cards."""

    # Static relationship keywords for matching (broad categories)
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

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normalize text for better matching.

        1. Lowercase
        2. Strip possessives: wife's → wife, bosses' → bosses
        3. Normalize common plurals: colleges → college, wives → wife, achievements → achievement
        """
        text = text.lower()

        # Strip possessives (wife's → wife)
        text = re.sub(r"'s\b", '', text)
        text = re.sub(r"'\b", '', text)

        # Irregular plurals
        text = re.sub(r'\bwives\b', 'wife', text)
        text = re.sub(r'\blives\b', 'life', text)

        # Common plurals - handle each word properly
        # Words ending in -es that become singular by removing -es
        for plural, singular in [
            ('bosses', 'boss'),
            ('colleagues', 'colleague'),
            ('coaches', 'coach'),
            ('universities', 'university'),
            ('activities', 'activity'),
        ]:
            text = re.sub(rf'\b{plural}\b', singular, text)

        # Words ending in -s that become singular by removing -s
        for plural, singular in [
            ('friends', 'friend'),
            ('parents', 'parent'),
            ('siblings', 'sibling'),
            ('cousins', 'cousin'),
            ('teachers', 'teacher'),
            ('classmates', 'classmate'),
            ('teammates', 'teammate'),
            ('neighbors', 'neighbor'),
            ('kids', 'kid'),
            ('boys', 'boy'),
            ('girls', 'girl'),
            ('achievements', 'achievement'),
        ]:
            text = re.sub(rf'\b{plural}\b', singular, text)

        # Specific one-offs
        text = re.sub(r'\b(colleges)\b', 'college', text)
        text = re.sub(r'\b(goals)\b', 'goal', text)

        return text

    @staticmethod
    def _word_boundary_match(needle: str, haystack: str) -> bool:
        """
        Check if needle appears as a whole word in haystack.

        Uses regex \b for word boundaries to prevent false matches.
        Example: "achievement" should NOT match "overachievements"
        """
        try:
            pattern = r'\b' + re.escape(needle) + r'\b'
            return re.search(pattern, haystack) is not None
        except re.error:
            # Fallback to simple substring if regex fails
            return needle in haystack

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
        normalized_text = self._normalize_text(message_text)

        # Load all cards for this client
        char_cards = db.get_character_cards(client_id)
        world_events = db.get_world_events(client_id)

        # Track keywords matched by relationship labels to avoid duplicate broad matching
        label_matched_keywords = set()

        # FIRST PASS: Check character cards for name and label matches
        for card in char_cards:
            card_id = card['id']
            card_name = card['card_name'].lower()
            relationship_label = card.get('relationship_label')

            # Priority 1: Check exact name match
            if self._word_boundary_match(card_name, normalized_text):
                mentions.append({
                    'card_id': card_id,
                    'card_type': 'character',
                    'match_type': 'name'
                })
                continue

            # Priority 2: Check custom relationship label (specific matching)
            # Example: Paula's card with label "Sister" matches "my sister"
            if relationship_label and self._word_boundary_match(relationship_label.lower(), normalized_text):
                mentions.append({
                    'card_id': card_id,
                    'card_type': 'character',
                    'match_type': 'label'
                })
                # Track this keyword as matched by a label
                label_matched_keywords.add(relationship_label.lower())
                continue

        # SECOND PASS: Check character cards for generic keyword matches
        # (excluding keywords already matched by specific labels)
        for card in char_cards:
            card_id = card['id']

            # Skip if already matched by name or label
            if any(m['card_id'] == card_id for m in mentions):
                continue

            relationship_type = card.get('relationship_type', '').lower()

            # Priority 3: Check generic relationship keywords (broad matching)
            # Example: "Sister" keyword matches ALL family cards if no label match
            # Skip if this keyword was already matched by a specific label
            if self._matches_relationship_keywords(
                relationship_type, normalized_text, label_matched_keywords
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
            event_type = event.get('event_type', '').lower()

            # Priority 1: Check title match
            if self._word_boundary_match(event_title, normalized_text):
                mentions.append({
                    'card_id': card_id,
                    'card_type': 'world',
                    'match_type': 'title'
                })
                continue

            # Priority 2: Check event type (new feature)
            # Example: "achievement" matches all achievement-type events
            if event_type and self._word_boundary_match(event_type, normalized_text):
                mentions.append({
                    'card_id': card_id,
                    'card_type': 'world',
                    'match_type': 'event_type'
                })
                continue

            # Priority 3: Check key_array keywords
            key_array = json.loads(event['key_array']) \
                if isinstance(event['key_array'], str) \
                else event['key_array']

            for keyword in key_array:
                if self._word_boundary_match(keyword.lower(), normalized_text):
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
        text: str,
        excluded_keywords: set = None
    ) -> bool:
        """
        Check if text contains keywords matching relationship type.

        Args:
            relationship_type: The type of relationship (family, friend, etc.)
            text: The normalized text to search
            excluded_keywords: Keywords to exclude (matched by specific labels)
        """
        if excluded_keywords is None:
            excluded_keywords = set()

        keywords = self.RELATIONSHIP_KEYWORDS.get(relationship_type, [])
        for kw in keywords:
            # Skip this keyword if it was already matched by a specific label
            if kw in excluded_keywords:
                continue
            if self._word_boundary_match(kw, text):
                return True
        return False


# Global instance
entity_detector = EntityDetector()
