#!/usr/bin/env python3
"""
Sync flashcard curriculum from JSON to Anki via AnkiConnect.

Requirements:
- Anki must be running with AnkiConnect add-on installed (code: 2055492159)
- AnkiConnect exposes API on http://127.0.0.1:8765

Usage:
    python sync_anki.py

Reads config.json and all lesson_*.json files from the content/ directory.

Config file (content/config.json) must contain:
- course: Display name for the course
- deck: Anki deck name
- uid_prefix: Unique prefix for card UIDs (e.g., "linear-algebra", "deep-learning")
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


def find_note_by_uid(uid_tag: str, parent_deck: str) -> int | None:
    """Find a note by its UID tag, scoped to the deck tree."""
    query = f'deck:"{parent_deck}*" tag:"{uid_tag}"'
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

    IMPORTANT: Only returns notes that do NOT already have a uid:* tag.
    This prevents merging different cards that happen to have the same question.
    """
    # Search across the whole parent deck tree,
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
            # Check if this note already has a uid tag - if so, don't reuse it
            # (it belongs to a different card with the same question)
            has_uid = any(tag.startswith("uid:") for tag in note.get("tags", []))
            if has_uid:
                continue
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


def get_all_uid_tags_in_deck_tree(parent_deck: str, uid_prefix: str) -> set[str]:
    """Get all uid:* tags from notes in the deck and all subdecks.

    Only returns tags that match the uid_prefix to avoid conflicts with other decks.
    """
    notes_info = get_all_notes_in_deck_tree(parent_deck)
    uid_tags = set()
    tag_prefix = f"uid:{uid_prefix}-"
    for note in notes_info:
        for tag in note.get("tags", []):
            if tag.startswith(tag_prefix):
                uid_tags.add(tag)
    return uid_tags


SUBDECK_CONFIG_NAME = "Lesson Subdecks (unlimited new)"

# Cache for the subdeck config ID to avoid creating duplicates
_subdeck_config_id: int | None = None


def get_or_create_subdeck_config(parent_deck: str, new_per_day: int = 9999) -> int:
    """
    Get or create a dedicated config for lesson subdecks.

    Returns the config ID.
    """
    global _subdeck_config_id

    if _subdeck_config_id is not None:
        return _subdeck_config_id

    # Check if any deck is already using our custom config
    for deck in invoke("deckNames"):
        config = invoke("getDeckConfig", {"deck": deck})
        if config and config.get("name") == SUBDECK_CONFIG_NAME:
            _subdeck_config_id = config["id"]
            # Ensure it has the right settings
            if config["new"]["perDay"] != new_per_day:
                config["new"]["perDay"] = new_per_day
                invoke("saveDeckConfig", {"config": config})
            return _subdeck_config_id

    # Create new config by cloning from parent's config
    parent_config = invoke("getDeckConfig", {"deck": parent_deck})
    _subdeck_config_id = invoke("cloneDeckConfigId", {"name": SUBDECK_CONFIG_NAME, "cloneFrom": parent_config["id"]})

    return _subdeck_config_id


def configure_subdeck_new_cards(deck_name: str, parent_deck: str, new_per_day: int = 9999, dry_run: bool = False) -> bool:
    """
    Configure a subdeck to show many new cards per day using a dedicated config.

    Creates a shared config group for all lesson subdecks if needed, so the parent
    deck's config remains untouched.
    Returns True if config was changed, False if already correct.
    """
    # Get current config for the deck
    config = invoke("getDeckConfig", {"deck": deck_name})
    if not config:
        return False

    # Already using our subdeck config with correct settings
    if config.get("name") == SUBDECK_CONFIG_NAME and config.get("new", {}).get("perDay") == new_per_day:
        return False

    if dry_run:
        return True

    # Get or create the subdeck config
    subdeck_config_id = get_or_create_subdeck_config(parent_deck, new_per_day)

    # Assign this deck to use the subdeck config
    invoke("setDeckConfigId", {"decks": [deck_name], "configId": subdeck_config_id})

    # Ensure the config has the right perDay setting
    config = invoke("getDeckConfig", {"deck": deck_name})
    if config["new"]["perDay"] != new_per_day:
        config["new"]["perDay"] = new_per_day
        invoke("saveDeckConfig", {"config": config})

    return True


def delete_empty_subdecks(parent_deck: str, dry_run: bool = False) -> list[str]:
    """
    Delete subdecks that have no cards.

    Returns list of deleted deck names.
    """
    deleted = []
    all_decks = invoke("deckNames")

    # Find subdecks of the parent deck
    subdecks = [d for d in all_decks if d.startswith(f"{parent_deck}::")]

    for deck in subdecks:
        # Count cards in this specific deck (not including child decks)
        card_ids = invoke("findCards", {"query": f'deck:"{deck}"'})
        if not card_ids:
            if not dry_run:
                invoke("deleteDecks", {"decks": [deck], "cardsToo": True})
            deleted.append(deck)

    return deleted


def _normalize_for_comparison(text: str) -> str:
    """Normalize text for comparison, handling Anki's HTML formatting."""
    # Convert <br> tags to newlines
    text = text.replace("<br>", "\n").replace("<br />", "\n").replace("<br/>", "\n")
    # Remove other HTML tags
    text = re.sub(r"<[^>]*>", "", text)
    # Normalize HTML entities
    text = text.replace("&nbsp;", " ")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&amp;", "&")
    # Normalize whitespace
    text = text.strip()
    return text


def upsert_note(
    deck: str,
    front: str,
    back: str,
    tags: list[str],
    uid_tag: str,
    parent_deck: str,
    json_mod_time: float | None = None,
    dry_run: bool = False
) -> tuple[str, int | None, str, dict | None]:
    """
    Add or update a note.

    Uses a unique tag (uid:xxx) to identify existing notes.
    Returns (status, note_id, reason, back_sync_data) where:
      - status is 'added', 'updated', 'unchanged', or 'back_sync'
      - back_sync_data is a dict with 'front' and 'back' from Anki if back-sync is needed
    If dry_run is True, no changes are made to Anki.
    """
    existing_id = find_note_by_uid(uid_tag, parent_deck)
    if existing_id is None:
        # Handle pre-existing notes that do not yet have a uid:* tag but
        # already contain (up to HTML formatting) the same Front content
        # somewhere in the course's deck tree.
        existing_id = find_note_in_deck_by_front(deck, front)
    all_tags = tags + [uid_tag]

    if existing_id:
        # Check if content or tags changed
        notes_info = invoke("notesInfo", {"notes": [existing_id]})
        if notes_info:
            current = notes_info[0]
            current_front = current.get("fields", {}).get("Front", {}).get("value", "")
            current_back = current.get("fields", {}).get("Back", {}).get("value", "")
            current_tags = set(current.get("tags", []))
            # Anki mod time is in seconds since epoch
            anki_mod_time = current.get("mod", 0)

            # Normalize for comparison
            norm_current_front = _normalize_for_comparison(current_front)
            norm_current_back = _normalize_for_comparison(current_back)
            norm_new_front = _normalize_for_comparison(front)
            norm_new_back = _normalize_for_comparison(back)

            # Check what needs to change
            content_changed = norm_current_front != norm_new_front or norm_current_back != norm_new_back

            # Compare tags case-insensitively (Anki treats tags as case-insensitive)
            current_tags_lower = {t.lower() for t in current_tags}
            desired_tags_lower = {t.lower() for t in all_tags}
            tags_to_add = {t for t in all_tags if t.lower() not in current_tags_lower}
            tags_to_remove = {t for t in current_tags if t.lower() not in desired_tags_lower}

            if not content_changed and not tags_to_add and not tags_to_remove:
                return "unchanged", existing_id, "", None

            # Check if we should back-sync (Anki is newer than JSON)
            if content_changed and json_mod_time is not None and anki_mod_time > json_mod_time:
                # Anki card was modified more recently than the JSON file
                # Back-sync: update JSON from Anki
                details = []
                if norm_current_front != norm_new_front:
                    details.append(f"front (json): {front}")
                    details.append(f"front (anki): {current_front}")
                if norm_current_back != norm_new_back:
                    details.append(f"back (json): {back}")
                    details.append(f"back (anki): {current_back}")
                reason = "\n      ".join(details)

                back_sync_data = {
                    "front": current_front,
                    "back": current_back
                }
                return "back_sync", existing_id, reason, back_sync_data

            # Forward sync: update Anki from JSON
            # Determine what changed for logging with details
            details = []
            if norm_current_front != norm_new_front:
                details.append(f"front (before): {current_front}")
                details.append(f"front (after):  {front}")
            if norm_current_back != norm_new_back:
                details.append(f"back (before): {current_back}")
                details.append(f"back (after):  {back}")
            if tags_to_add:
                details.append(f"tags added: {tags_to_add}")
            if tags_to_remove:
                details.append(f"tags removed: {tags_to_remove}")
            reason = "\n      ".join(details)

        else:
            reason = "note info not found"
            content_changed = True
            tags_to_add = set(all_tags)
            tags_to_remove = set()

        if not dry_run:
            # Update fields if content changed
            if content_changed:
                invoke("updateNoteFields", {
                    "note": {
                        "id": existing_id,
                        "fields": {"Front": front, "Back": back}
                    }
                })
            # Add missing tags
            if tags_to_add:
                invoke("addTags", {"notes": [existing_id], "tags": " ".join(tags_to_add)})
            # Remove incorrect tags
            if tags_to_remove:
                for tag in tags_to_remove:
                    invoke("removeTags", {"notes": [existing_id], "tags": tag})
        return "updated", existing_id, reason, None

    # Add new note
    if dry_run:
        return "added", None, "new card", None

    note = {
        "deckName": deck,
        "modelName": "Basic",
        "fields": {"Front": front, "Back": back},
        "tags": all_tags,
        "options": {
            "allowDuplicate": True,
            "duplicateScope": "deck",
            "duplicateScopeOptions": {
                "deckName": deck,
                "checkChildren": False,
                "checkAllModels": False
            }
        }
    }
    note_id = invoke("addNote", {"note": note})
    return "added", note_id, "new card", None


def load_lessons(content_dir: Path) -> tuple[dict, list[tuple[dict, Path, float]]]:
    """Load config and all lesson files from content directory.

    Returns (config, lessons) where lessons is a list of (lesson_data, file_path, mod_time) tuples.
    """
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
            lesson_data = json.load(f)
        # Get file modification time as Unix timestamp
        mod_time = lesson_file.stat().st_mtime
        lessons.append((lesson_data, lesson_file, mod_time))

    return config, lessons


def update_card_in_json(file_path: Path, uid: str, new_front: str, new_back: str, dry_run: bool = False) -> bool:
    """Update a card in a JSON file by its UID.

    Returns True if the card was found and updated.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for card in data.get("cards", []):
        if card.get("uid") == uid:
            card["front"] = new_front
            card["back"] = new_back
            if not dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.write("\n")
            return True
    return False


def sync(content_dir: Path, dry_run: bool = False) -> None:
    """Sync all lessons to Anki."""
    config, lessons = load_lessons(content_dir)

    # Validate required config fields
    if "deck" not in config:
        raise ValueError("Config must contain 'deck' field")
    if "uid_prefix" not in config:
        raise ValueError("Config must contain 'uid_prefix' field")

    parent_deck = config["deck"]
    course = config.get("course", parent_deck)
    uid_prefix = config["uid_prefix"]

    if dry_run:
        print("=== DRY RUN MODE (no changes will be made) ===")
        print()

    print(f"Syncing: {course}")
    print(f"Parent deck: {parent_deck}")
    print(f"UID prefix: {uid_prefix}")
    print(f"Lessons: {len(lessons)}")
    print()

    # Ensure parent deck exists
    if not dry_run:
        ensure_deck(parent_deck)

    # Track all UIDs and front texts we process
    current_uids: set[str] = set()
    current_fronts: set[str] = set()

    # Counters
    added = 0
    updated = 0
    unchanged = 0
    back_synced = 0

    for lesson_data, lesson_file, json_mod_time in lessons:
        lesson_id = lesson_data.get("id", "?")
        lesson_title = lesson_data.get("title", "Untitled")

        # Create subdeck for each lesson: "Parent::Lesson Title"
        lesson_deck = f"{parent_deck}::{lesson_title}"
        if not dry_run:
            ensure_deck(lesson_deck)
            # Configure subdeck to show unlimited new cards
            if configure_subdeck_new_cards(lesson_deck, parent_deck, new_per_day=9999):
                print(f"Configured {lesson_title}: new cards/day = 9999")

        print(f"Lesson {lesson_id}: {lesson_title}")

        for card in lesson_data.get("cards", []):
            uid = card["uid"]
            uid_tag = f"uid:{uid}"
            current_uids.add(uid_tag)
            current_fronts.add(card["front"].strip())

            status, note_id, reason, back_sync_data = upsert_note(
                deck=lesson_deck,
                front=card["front"],
                back=card["back"],
                tags=card.get("tags", []),
                uid_tag=uid_tag,
                parent_deck=parent_deck,
                json_mod_time=json_mod_time,
                dry_run=dry_run
            )

            if status == "added":
                print(f"  added: {uid} ({reason})")
                added += 1
            elif status == "updated":
                print(f"  updated: {uid}")
                print(f"      {reason}")
                updated += 1
            elif status == "back_sync":
                print(f"  back-sync: {uid} (Anki is newer)")
                print(f"      {reason}")
                if back_sync_data:
                    update_card_in_json(
                        lesson_file,
                        uid,
                        back_sync_data["front"],
                        back_sync_data["back"],
                        dry_run=dry_run
                    )
                back_synced += 1
            else:
                unchanged += 1

    print()

    # Delete orphaned notes (cards removed from curriculum) across all subdecks
    existing_uids = get_all_uid_tags_in_deck_tree(parent_deck, uid_prefix)
    orphaned_uids = existing_uids - current_uids

    deleted = 0
    for uid_tag in orphaned_uids:
        note_id = find_note_by_uid(uid_tag, parent_deck)
        if note_id:
            if not dry_run:
                invoke("deleteNotes", {"notes": [note_id]})
            print(f"  deleted: {uid_tag.replace('uid:', '')}")
            deleted += 1

    # Also delete notes without uid tags that don't match any current card's front
    # Only consider notes that don't have a uid tag with our prefix
    all_notes = get_all_notes_in_deck_tree(parent_deck)
    tag_prefix = f"uid:{uid_prefix}-"
    for note in all_notes:
        has_our_uid = any(tag.startswith(tag_prefix) for tag in note.get("tags", []))
        if has_our_uid:
            continue
        note_id = note.get("noteId")
        if not note_id:
            continue
        current_front = note.get("fields", {}).get("Front", {}).get("value", "")
        canon_front = _canonicalize_front(current_front)
        if canon_front not in current_fronts:
            if not dry_run:
                invoke("deleteNotes", {"notes": [note_id]})
            preview = canon_front[:50] + "..." if len(canon_front) > 50 else canon_front
            print(f"  deleted (no uid): {preview}")
            deleted += 1

    # Delete empty subdecks
    deleted_decks = delete_empty_subdecks(parent_deck, dry_run=dry_run)
    for deck_name in deleted_decks:
        print(f"  deleted deck: {deck_name}")

    # Summary
    print("=" * 40)
    print(f"Added:       {added}")
    print(f"Updated:     {updated}")
    print(f"Back-synced: {back_synced}")
    print(f"Unchanged:   {unchanged}")
    print(f"Deleted:     {deleted}")
    print("=" * 40)


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Sync Anki deck from JSON files")
    parser.add_argument("-d", "--dry-run", action="store_true",
                        help="Show what would be done without making changes")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    content_dir = script_dir / "content"

    try:
        sync(content_dir, dry_run=args.dry_run)
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
