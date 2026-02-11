"""
Card metadata utilities for field-level timestamp tracking.

This module handles:
- Adding initial metadata to new cards
- Updating timestamps when fields change
- Generating recency indicators for LLM context
- Resetting metadata on user edits
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Set
import json


class CardMetadata:
    """Manage field-level timestamp metadata for cards."""
    
    def __init__(self, card_json: Dict[str, Any]):
        """
        Initialize with existing card JSON.
        
        Args:
            card_json: The full card JSON structure (with or without _metadata)
        """
        self.card_json = card_json
        self._ensure_metadata()
    
    def _ensure_metadata(self):
        """Ensure _metadata field exists in card."""
        if '_metadata' not in self.card_json:
            self.card_json['_metadata'] = {}
    
    def initialize_field(self, field_path: str, source: str = 'llm') -> None:
        """
        Initialize metadata for a new field.
        
        Args:
            field_path: Dot-notation path (e.g., "personality", "emotional_state.user_to_other")
            source: 'llm' or 'user'
        """
        now = datetime.now()
        
        if field_path not in self.card_json['_metadata']:
            self.card_json['_metadata'][field_path] = {
                'first_seen': now.isoformat(),
                'last_updated': now.isoformat(),
                'update_count': 0,
                'source': source
            }
    
    def update_field(self, field_path: str, source: str = 'llm') -> None:
        """
        Update metadata for an existing field.
        
        Args:
            field_path: Dot-notation path (e.g., "personality", "emotional_state.user_to_other")
            source: 'llm' or 'user'
        """
        now = datetime.now()
        
        if field_path not in self.card_json['_metadata']:
            self.initialize_field(field_path, source)
        else:
            metadata = self.card_json['_metadata'][field_path]
            metadata['last_updated'] = now.isoformat()
            metadata['update_count'] += 1
            metadata['source'] = source
    
    def reset_field(self, field_path: str) -> None:
        """
        Reset metadata for a field (user edit).
        
        Sets source to 'user' and updates timestamp.
        
        Args:
            field_path: Dot-notation path (e.g., "personality", "emotional_state.user_to_other")
        """
        self.update_field(field_path, source='user')
    
    def get_recency_indicator(self, field_path: str) -> str:
        """
        Get human-readable recency indicator for a field.
        
        Returns:
            String like "[new]", "[updated today]", "[updated this week]", "[updated 2 weeks ago]", "[established]"
        """
        if field_path not in self.card_json['_metadata']:
            return ""
        
        metadata = self.card_json['_metadata'][field_path]
        try:
            last_updated = datetime.fromisoformat(metadata['last_updated'])
        except (ValueError, KeyError):
            return ""
        
        now = datetime.now()
        diff = now - last_updated
        
        if diff < timedelta(hours=1):
            return "[new]"
        elif diff < timedelta(days=1):
            return "[updated today]"
        elif diff < timedelta(days=7):
            return "[updated this week]"
        elif diff < timedelta(days=14):
            return "[updated 2 weeks ago]"
        elif diff < timedelta(days=30):
            return "[updated this month]"
        else:
            return "[established]"
    
    def get_field_age_days(self, field_path: str) -> Optional[int]:
        """
        Get age of a field in days.
        
        Returns:
            Number of days since last update, or None if field not found
        """
        if field_path not in self.card_json['_metadata']:
            return None
        
        metadata = self.card_json['_metadata'][field_path]
        try:
            last_updated = datetime.fromisoformat(metadata['last_updated'])
            diff = datetime.now() - last_updated
            return diff.days
        except (ValueError, KeyError):
            return None
    
    def get_all_field_metadata(self) -> Dict[str, Any]:
        """Get all metadata for the card."""
        return self.card_json.get('_metadata', {})
    
    def get_json_with_metadata(self) -> Dict[str, Any]:
        """Get the full card JSON with metadata included."""
        return self.card_json
    
    def get_json_without_metadata(self) -> Dict[str, Any]:
        """Get card JSON without metadata (for display/storage if needed)."""
        result = {k: v for k, v in self.card_json.items() if k != '_metadata'}
        return result


def initialize_card_metadata(card_json: Dict[str, Any], source: str = 'llm') -> Dict[str, Any]:
    """
    Initialize metadata for all fields in a new card.
    
    Args:
        card_json: Card JSON to initialize metadata for
        source: 'llm' or 'user'
    
    Returns:
        Card JSON with metadata added
    """
    metadata = CardMetadata(card_json)
    
    def traverse_and_initialize(obj: Any, path: str = ''):
        """Recursively traverse and initialize metadata for fields."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == '_metadata':
                    continue
                new_path = f"{path}.{key}" if path else key
                
                # Initialize metadata for this field
                if not isinstance(value, (dict, list)):
                    metadata.initialize_field(new_path, source)
                else:
                    traverse_and_initialize(value, new_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, (dict, list)):
                    traverse_and_initialize(item, f"{path}[{i}]")
    
    traverse_and_initialize(card_json.get('data', {}))
    
    return metadata.get_json_with_metadata()


def update_card_fields(card_json: Dict[str, Any], updated_fields: Set[str], source: str = 'llm') -> Dict[str, Any]:
    """
    Update metadata for specific fields that were changed.
    
    Args:
        card_json: Existing card JSON
        updated_fields: Set of field paths that were updated
        source: 'llm' or 'user'
    
    Returns:
        Card JSON with updated metadata
    """
    metadata = CardMetadata(card_json)
    
    for field_path in updated_fields:
        metadata.update_field(field_path, source)
    
    return metadata.get_json_with_metadata()


def format_card_with_recency(card_payload: Dict[str, Any]) -> Dict[str, str]:
    """
    Add recency indicators to card payload for LLM context.
    
    This function wraps values in the payload with recency indicators
    for display purposes. It creates a new dict with the same structure
    but values are annotated.
    
    Args:
        card_payload: Card payload (data field from card JSON)
    
    Returns:
        Dict mapping field paths to values with recency indicators
    """
    metadata = CardMetadata(card_payload)
    result = {}
    
    def traverse_and_format(obj: Any, path: str = ''):
        """Recursively traverse and format with recency indicators."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == '_metadata':
                    continue
                new_path = f"{path}.{key}" if path else key
                
                if not isinstance(value, (dict, list)):
                    # Add recency indicator
                    recency = metadata.get_recency_indicator(new_path)
                    if recency:
                        result[new_path] = f"{value} {recency}"
                    else:
                        result[new_path] = str(value)
                else:
                    traverse_and_format(value, new_path)
    
    traverse_and_format(card_payload.get('data', {}))
    
    return result


def reset_card_metadata(card_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reset all metadata for a card (user edit).
    
    Sets all sources to 'user' and updates timestamps.
    
    Args:
        card_json: Card JSON to reset
    
    Returns:
        Card JSON with reset metadata
    """
    metadata = CardMetadata(card_json)
    
    for field_path in metadata.get_all_field_metadata().keys():
        metadata.reset_field(field_path)
    
    return metadata.get_json_with_metadata()
