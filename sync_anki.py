#!/usr/bin/env python3
"""
Sync Linear Algebra curriculum from JSON to Anki via AnkiConnect.

Requirements:
- Anki must be running with AnkiConnect add-on installed (code: 2055492159)
- AnkiConnect exposes API on http://127.0.0.1:8765

Usage:
    python sync_anki.py

Reads config.json and all lesson_*.json files from the content/ directory.
"""

import json
from pathlib import Path
import re

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


def _canonicalize_front(value: str) -> str:
    """
    Put Anki's HTML-formatted Front field into a rough text form so we can
    match it against the plain-text `front` we send when creating notes.

    This is intentionally minimal: handle <br> and remove other tags.
    """
    text = value.replace("<br>", "\n").replace("<br />", "\n")
    text = re.sub(r"<[^>]*>", "", text)
    text = text.replace("&nbsp;", " ")
    return text.strip()


def find_note_in_deck_by_front(deck: str, front: str) -> int | None:
    """
    Find a note in the course's deck tree whose Front field matches (up to simple HTML formatting).

    This is used to upgrade existing notes that predate uid:* tags,
    so we do not create duplicate notes when the content already exists.
    """
    # Search across the whole parent deck tree (e.g., "Linear Algebra::*"),
    # since earlier experiments may have created notes in a slightly different subdeck.
    parent = deck.split("::", 1)[0]
    note_ids = invoke("findNotes", {"query": f'deck:"{parent}*"'})
    if not note_ids:
        return None

    notes_info = invoke("notesInfo", {"notes": note_ids})
    target = front.strip()
    for note in notes_info:
        current_front = note.get("fields", {}).get("Front", {}).get("value", "")
        canon = _canonicalize_front(current_front)
        if canon == target:
            # AnkiConnect uses the key "noteId" for the identifier in notesInfo
            return note.get("noteId")

    return None


def get_all_notes_in_deck_tree(parent_deck: str) -> list[dict]:
    """Get all notes from the deck and all subdecks."""
    query = f'deck:"{parent_deck}*"'
    note_ids = invoke("findNotes", {"query": query})

    if not note_ids:
        return []

    return invoke("notesInfo", {"notes": note_ids})


def get_all_uid_tags_in_deck_tree(parent_deck: str) -> set[str]:
    """Get all uid:* tags from notes in the deck and all subdecks."""
    notes_info = get_all_notes_in_deck_tree(parent_deck)
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
    if existing_id is None:
        # Handle pre-existing notes that do not yet have a uid:* tag but
        # already contain (up to HTML formatting) the same Front content
        # somewhere in the course's deck tree.
        existing_id = find_note_in_deck_by_front(deck, front)
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


def load_lessons(content_dir: Path) -> tuple[dict, list[dict]]:
    """Load config and all lesson files from content directory."""
    config_path = content_dir / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Find and sort lesson files
    lesson_files = sorted(content_dir.glob("lesson_*.json"))
    if not lesson_files:
        raise FileNotFoundError(f"No lesson files found in {content_dir}")

    lessons = []
    for lesson_file in lesson_files:
        with open(lesson_file, "r", encoding="utf-8") as f:
            lessons.append(json.load(f))

    return config, lessons


def sync(content_dir: Path) -> None:
    """Sync all lessons to Anki."""
    config, lessons = load_lessons(content_dir)

    parent_deck = config.get("deck", "Linear Algebra")
    course = config.get("course", "Unknown Course")

    print(f"Syncing: {course}")
    print(f"Parent deck: {parent_deck}")
    print(f"Lessons: {len(lessons)}")
    print()

    # Ensure parent deck exists
    ensure_deck(parent_deck)

    # Track all UIDs and front texts we process
    current_uids: set[str] = set()
    current_fronts: set[str] = set()

    # Counters
    added = 0
    updated = 0
    unchanged = 0

    for lesson in lessons:
        lesson_id = lesson.get("id", "?")
        lesson_title = lesson.get("title", "Untitled")

        # Create subdeck for each lesson: "Parent::Lesson Title"
        lesson_deck = f"{parent_deck}::{lesson_title}"
        ensure_deck(lesson_deck)

        print(f"Lesson {lesson_id}: {lesson_title}")

        for card in lesson.get("cards", []):
            uid = card["uid"]
            uid_tag = f"uid:{uid}"
            current_uids.add(uid_tag)
            current_fronts.add(card["front"].strip())

            status, note_id = upsert_note(
                deck=lesson_deck,
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

    # Delete orphaned notes (cards removed from curriculum) across all subdecks
    existing_uids = get_all_uid_tags_in_deck_tree(parent_deck)
    orphaned_uids = existing_uids - current_uids

    deleted = 0
    for uid_tag in orphaned_uids:
        note_id = find_note_by_uid(uid_tag)
        if note_id:
            invoke("deleteNotes", {"notes": [note_id]})
            print(f"  deleted: {uid_tag.replace('uid:', '')}")
            deleted += 1

    # Also delete notes without uid tags that don't match any current card's front
    all_notes = get_all_notes_in_deck_tree(parent_deck)
    for note in all_notes:
        has_uid = any(tag.startswith("uid:") for tag in note.get("tags", []))
        if has_uid:
            continue
        note_id = note.get("noteId")
        if not note_id:
            continue
        current_front = note.get("fields", {}).get("Front", {}).get("value", "")
        canon_front = _canonicalize_front(current_front)
        if canon_front not in current_fronts:
            invoke("deleteNotes", {"notes": [note_id]})
            preview = canon_front[:50] + "..." if len(canon_front) > 50 else canon_front
            print(f"  deleted (no uid): {preview}")
            deleted += 1

    # Summary
    print("=" * 40)
    print(f"Added:     {added}")
    print(f"Updated:   {updated}")
    print(f"Unchanged: {unchanged}")
    print(f"Deleted:   {deleted}")
    print("=" * 40)


def main():
    import sys

    script_dir = Path(__file__).parent
    content_dir = script_dir / "content"

    try:
        sync(content_dir)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
