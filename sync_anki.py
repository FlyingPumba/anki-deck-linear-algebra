#!/usr/bin/env python3
"""
Sync Linear Algebra curriculum from JSON to Anki via AnkiConnect.

Requirements:
- Anki must be running with AnkiConnect add-on installed (code: 2055492159)
- AnkiConnect exposes API on http://127.0.0.1:8765

Usage:
    python sync_anki.py [curriculum.json]

If no file is specified, defaults to content/curriculum.json
"""

import json
import sys
from pathlib import Path

import requests

ANKI_URL = "http://127.0.0.1:8765"
API_VERSION = 6


def invoke(action: str, params: dict | None = None) -> any:
    """Call AnkiConnect API."""
    payload = {"action": action, "version": API_VERSION}
    if params is not None:
        payload["params"] = params

    try:
        r = requests.post(ANKI_URL, json=payload, timeout=30)
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot connect to Anki. Make sure Anki is running "
            "and AnkiConnect add-on is installed (code: 2055492159)"
        )

    data = r.json()
    if data.get("error"):
        raise RuntimeError(f"AnkiConnect error: {data['error']}")
    return data.get("result")


def ensure_deck(deck_name: str) -> None:
    """Create deck if it doesn't exist."""
    existing = invoke("deckNames")
    if deck_name not in existing:
        invoke("createDeck", {"deck": deck_name})
        print(f"Created deck: {deck_name}")


def find_note_by_uid(uid_tag: str) -> int | None:
    """Find a note by its UID tag."""
    query = f'tag:"{uid_tag}"'
    note_ids = invoke("findNotes", {"query": query})
    return note_ids[0] if note_ids else None


def get_all_uid_tags_in_deck(deck_name: str) -> set[str]:
    """Get all uid:* tags from notes in the deck."""
    query = f'deck:"{deck_name}"'
    note_ids = invoke("findNotes", {"query": query})

    if not note_ids:
        return set()

    notes_info = invoke("notesInfo", {"notes": note_ids})
    uid_tags = set()
    for note in notes_info:
        for tag in note.get("tags", []):
            if tag.startswith("uid:"):
                uid_tags.add(tag)
    return uid_tags


def upsert_note(deck: str, front: str, back: str, tags: list[str], uid_tag: str) -> tuple[str, int]:
    """
    Add or update a note.

    Uses a unique tag (uid:xxx) to identify existing notes.
    Returns (status, note_id) where status is 'added', 'updated', or 'unchanged'.
    """
    existing_id = find_note_by_uid(uid_tag)
    all_tags = tags + [uid_tag]

    if existing_id:
        # Check if content changed
        notes_info = invoke("notesInfo", {"notes": [existing_id]})
        if notes_info:
            current = notes_info[0]
            current_front = current.get("fields", {}).get("Front", {}).get("value", "")
            current_back = current.get("fields", {}).get("Back", {}).get("value", "")

            if current_front == front and current_back == back:
                return "unchanged", existing_id

        # Update fields
        invoke("updateNoteFields", {
            "note": {
                "id": existing_id,
                "fields": {"Front": front, "Back": back}
            }
        })
        # Update tags
        invoke("addTags", {"notes": [existing_id], "tags": " ".join(all_tags)})
        return "updated", existing_id

    # Add new note
    note = {
        "deckName": deck,
        "modelName": "Basic",
        "fields": {"Front": front, "Back": back},
        "tags": all_tags,
        "options": {
            "allowDuplicate": False
        }
    }
    note_id = invoke("addNote", {"note": note})
    return "added", note_id


def delete_orphaned_notes(deck: str, current_uids: set[str]) -> int:
    """Delete notes that are no longer in the curriculum."""
    existing_uids = get_all_uid_tags_in_deck(deck)
    orphaned_uids = existing_uids - current_uids

    deleted_count = 0
    for uid_tag in orphaned_uids:
        note_id = find_note_by_uid(uid_tag)
        if note_id:
            invoke("deleteNotes", {"notes": [note_id]})
            print(f"  deleted: {uid_tag.replace('uid:', '')}")
            deleted_count += 1

    return deleted_count


def sync(curriculum_path: str) -> None:
    """Sync curriculum JSON to Anki."""
    path = Path(curriculum_path)
    if not path.exists():
        raise FileNotFoundError(f"Curriculum file not found: {curriculum_path}")

    with open(path, "r", encoding="utf-8") as f:
        curriculum = json.load(f)

    deck = curriculum.get("deck", "Linear Algebra")
    course = curriculum.get("course", "Unknown Course")

    print(f"Syncing: {course}")
    print(f"Deck: {deck}")
    print()

    # Ensure deck exists
    ensure_deck(deck)

    # Track all UIDs we process
    current_uids: set[str] = set()

    # Counters
    added = 0
    updated = 0
    unchanged = 0

    for module in curriculum.get("modules", []):
        module_id = module.get("id", "?")
        module_title = module.get("title", "Untitled")
        print(f"Module {module_id}: {module_title}")

        for lesson in module.get("lessons", []):
            lesson_id = lesson.get("id", "?")
            lesson_title = lesson.get("title", "Untitled")

            for card in lesson.get("cards", []):
                uid = card["uid"]
                uid_tag = f"uid:{uid}"
                current_uids.add(uid_tag)

                status, note_id = upsert_note(
                    deck=deck,
                    front=card["front"],
                    back=card["back"],
                    tags=card.get("tags", []),
                    uid_tag=uid_tag
                )

                if status == "added":
                    print(f"  added: {uid}")
                    added += 1
                elif status == "updated":
                    print(f"  updated: {uid}")
                    updated += 1
                else:
                    unchanged += 1

    print()

    # Delete orphaned notes (cards removed from curriculum)
    deleted = delete_orphaned_notes(deck, current_uids)

    # Summary
    print("=" * 40)
    print(f"Added:     {added}")
    print(f"Updated:   {updated}")
    print(f"Unchanged: {unchanged}")
    print(f"Deleted:   {deleted}")
    print("=" * 40)


def main():
    if len(sys.argv) > 1:
        curriculum_path = sys.argv[1]
    else:
        # Default path
        script_dir = Path(__file__).parent
        curriculum_path = script_dir / "content" / "curriculum.json"

    try:
        sync(str(curriculum_path))
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
