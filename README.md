# Linear Algebra Anki Deck

A Linear Algebra curriculum synced to Anki, based on 3Blue1Brown's "Essence of Linear Algebra" video series.

## Prerequisites

1. [Anki](https://apps.ankiweb.net/) installed
2. [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on installed (code: 2055492159)
3. Python 3.13+ with [uv](https://github.com/astral-sh/uv)

## Setup

```bash
# Clone the repository
git clone <repo-url>
cd anki-deck-linear-algebra

# Install dependencies
uv sync
```

## Usage

1. Open Anki (AnkiConnect runs on port 8765)
2. Run the sync script:

```bash
uv run python sync_anki.py
```

The script will:
- Create the "Linear Algebra" deck with subdecks for each lesson
- Add new cards
- Update modified cards
- Remove cards that no longer exist in the JSON files

## Curriculum Structure

16 lessons covering:

| Lesson | Topic |
|--------|-------|
| 01 | Vectors |
| 02 | Linear Combinations, Span, and Basis Vectors |
| 03 | Linear Transformations and Matrices |
| 04 | Matrix Multiplication as Composition |
| 05 | Three-Dimensional Linear Transformations |
| 06 | The Determinant |
| 07 | Inverse Matrices, Column Space, and Null Space |
| 08 | Nonsquare Matrices |
| 09 | Dot Products and Duality |
| 10 | Cross Products |
| 11 | Cross Products and Linear Transformations |
| 12 | Cramer's Rule |
| 13 | Change of Basis |
| 14 | Eigenvectors and Eigenvalues |
| 15 | Quick Eigenvalue Computation |
| 16 | Abstract Vector Spaces |

## File Structure

```
anki-deck-linear-algebra/
├── sync_anki.py          # Sync script
├── content/
│   ├── config.json       # Deck configuration
│   ├── lesson_01.json    # Lesson 1 cards
│   ├── lesson_02.json
│   └── ...
├── pyproject.toml
└── README.md
```

## Editing Cards

Each lesson file follows this structure:

```json
{
  "id": "01",
  "title": "Lesson 01: Vectors",
  "lesson_title": "Vectors, what even are they?",
  "objectives": ["..."],
  "cards": [
    {
      "uid": "01-001",
      "front": "Question text with \\( LaTeX \\)",
      "back": "Answer text",
      "tags": ["ch01", "vectors", "definition"]
    }
  ]
}
```

After editing, run `uv run python sync_anki.py` to update Anki.

## Card Tracking

Cards are tracked by UID tags (e.g., `uid:01-001`). This allows the sync script to:
- Identify existing cards for updates
- Detect orphaned cards for removal
- Preserve your Anki review progress
