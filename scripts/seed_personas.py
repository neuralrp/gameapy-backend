#!/usr/bin/env python3
"""
Seed Personas from JSON Files

This script reads counselor persona JSON files from data/personas/ and
syncs them to the database. It uses upsert logic (delete by name, then insert)
so you can edit JSONs freely and re-run this script.

Usage:
    python scripts/seed_personas.py                    # Sync all personas
    python scripts/seed_personas.py --name "Marina"    # Sync specific persona
    python scripts/seed_personas.py --list             # List available personas
"""

import sys
import os
import json
import argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import Database


PERSONAS_DIR = Path("app/data/personas")


def validate_persona(profile_data):
    """Validate persona JSON structure."""
    required = ["spec", "spec_version", "data"]
    missing = [f for f in required if f not in profile_data]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    data = profile_data.get("data", {})
    required_data = ["name", "who_you_are", "your_vibe", "your_worldview",
                     "session_template", "session_examples"]
    missing_data = [f for f in required_data if f not in data]
    if missing_data:
        raise ValueError(f"Missing required data fields: {', '.join(missing_data)}")

    if not data["session_examples"]:
        raise ValueError("session_examples must contain at least one example")

    # Validate example structure
    for i, example in enumerate(data["session_examples"]):
        if "user_situation" not in example:
            raise ValueError(f"Example {i+1}: Missing 'user_situation' field")
        if "your_response" not in example:
            raise ValueError(f"Example {i+1}: Missing 'your_response' field")
        if "approach" not in example:
            raise ValueError(f"Example {i+1}: Missing 'approach' field")

    # Validate optional is_hidden field
    is_hidden = data.get("is_hidden", False)
    if not isinstance(is_hidden, bool):
        raise ValueError("is_hidden must be a boolean (true/false)")

    return True


def load_persona_files(name_filter=None):
    """Load all persona JSON files (or specific one if name_filter provided)."""
    if not PERSONAS_DIR.exists():
        print(f"Error: Personas directory not found: {PERSONAS_DIR}")
        print("Create it with: mkdir -p data/personas")
        sys.exit(1)
    
    persona_files = list(PERSONAS_DIR.glob("*.json"))
    
    if not persona_files:
        print(f"No JSON files found in {PERSONAS_DIR}")
        sys.exit(1)
    
    personas = []
    for filepath in persona_files:
        with open(filepath, 'r', encoding='utf-8') as f:
            profile_data = json.load(f)
            
            # Filter by name if specified
            if name_filter:
                if profile_data['data']['name'].lower() != name_filter.lower():
                    continue
            
            personas.append({
                'filepath': filepath,
                'data': profile_data
            })
    
    return personas


def get_counselor_by_name(db, name):
    """Get counselor ID by name."""
    with db._get_connection() as conn:
        cursor = conn.cursor()
        result = cursor.execute(
            "SELECT id FROM counselor_profiles WHERE name = ? AND is_active = TRUE",
            (name,)
        ).fetchone()
        return result[0] if result else None


def seed_personas(db, personas):
    """Upsert personas to database (delete + insert by name)."""
    summary = {
        'created': [],
        'updated': [],
        'failed': []
    }
    
    print(f"\n[INFO] Starting seed process for {len(personas)} personas")
    print(f"[INFO] Database path: {db.db_path}")
    
    for persona_info in personas:
        filepath = persona_info['filepath']
        profile_data = persona_info['data']
        
        try:
            name = profile_data['data']['name']
            print(f"\n[INFO] Processing: {name}")
            
            # Validate
            validate_persona(profile_data)
            print(f"[INFO]   Validation passed")
            
            # Check if exists
            existing_id = get_counselor_by_name(db, name)
            print(f"[INFO]   Existing ID: {existing_id}")
            
            if existing_id:
                print(f"[INFO]   Deleting old version (ID: {existing_id})")
                # Delete old version
                with db._get_connection() as conn:
                    conn.execute(
                        "DELETE FROM counselor_profiles WHERE id = ?",
                        (existing_id,)
                    )
                    conn.commit()
                print(f"[INFO]   Deleted successfully")
                
                # Insert new version
                print(f"[INFO]   Inserting new version...")
                profile_id = db.create_counselor_profile(profile_data)
                print(f"[INFO]   Created with ID: {profile_id}")
                summary['updated'].append(name)
            else:
                print(f"[INFO]   Inserting new counselor...")
                # Insert new
                profile_id = db.create_counselor_profile(profile_data)
                print(f"[INFO]   Created with ID: {profile_id}")
                summary['created'].append(name)
            
        except Exception as e:
            print(f"[ERROR] Failed to process {profile_data.get('data', {}).get('name', 'Unknown')}: {e}")
            import traceback
            traceback.print_exc()
            summary['failed'].append({
                'name': profile_data['data'].get('name', 'Unknown'),
                'file': filepath.name,
                'error': str(e)
            })
    
    return summary


def list_personas():
    """List all available persona JSON files."""
    if not PERSONAS_DIR.exists():
        print(f"Error: Personas directory not found: {PERSONAS_DIR}")
        sys.exit(1)
    
    persona_files = list(PERSONAS_DIR.glob("*.json"))
    
    if not persona_files:
        print(f"No JSON files found in {PERSONAS_DIR}")
        sys.exit(1)
    
    print("Available Personas:")
    print()
    
    for filepath in sorted(persona_files):
        with open(filepath, 'r', encoding='utf-8') as f:
            profile_data = json.load(f)
            data = profile_data.get('data', {})
            name = data.get('name', 'Unknown')
            who_you_are = data.get('who_you_are', 'Unknown')
            your_vibe = data.get('your_vibe', 'Unknown')
            
            print(f"  • {name}")
            print(f"    File: {filepath.name}")
            print(f"    Who you are: {who_you_are}")
            print(f"    Your vibe: {your_vibe}")
            print()


def main():
    parser = argparse.ArgumentParser(
        description="Seed counselor personas from JSON files to database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/seed_personas.py                    # Sync all personas
  python scripts/seed_personas.py --name "Marina"    # Sync specific persona
  python scripts/seed_personas.py --list             # List available personas

Workflow:
  1. Edit persona JSON in data/personas/*.json
  2. Run: python scripts/seed_personas.py
  3. Test in app
  4. Repeat as needed
        """
    )
    
    parser.add_argument('--name', type=str,
                        help='Sync only specific persona by name')
    parser.add_argument('--list', action='store_true',
                        help='List available personas without syncing')
    
    args = parser.parse_args()
    
    if args.list:
        list_personas()
        sys.exit(0)
    
    # Load personas
    personas = load_persona_files(name_filter=args.name)
    
    if not personas:
        if args.name:
            print(f"No persona found matching name: {args.name}")
        else:
            print(f"No persona JSON files found in {PERSONAS_DIR}")
        sys.exit(1)
    
    # Seed to database
    db = Database()
    summary = seed_personas(db, personas)
    
    # Print summary
    print("\n=== Seed Summary ===")

    if summary['created']:
        print(f"\nCreated ({len(summary['created'])}):")
        for name in summary['created']:
            print(f"  - {name}")

    if summary['updated']:
        print(f"\nUpdated ({len(summary['updated'])}):")
        for name in summary['updated']:
            print(f"  - {name}")

    if summary['failed']:
        print(f"\nFailed ({len(summary['failed'])}):")
        for failure in summary['failed']:
            print(f"  - {failure['name']} ({failure['file']})")
            print(f"    Error: {failure['error']}")


if __name__ == "__main__":
    main()
