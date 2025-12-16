# Project Instructions

## Package Management
- Use `uv` for Python dependency management (not pip)
- Run scripts with `uv run python <script>`

## Card Content Formatting

### Style
- Lead with **intuition** using everyday analogies (coin flips, dice, paint mixing, hills, shadows, etc.)
- Include concrete **examples** where helpful
- Preserve key **formulas** for reference, but don't make them the focus
- Add practical notes like **Why useful** or **Trade-offs** where relevant
- Avoid dry, formula-first definitions - make concepts memorable and relatable

### Pedagogical Principles
- **Teach concepts, not just examples**: Explain what something *is* and *why* it works that way. Specific models/algorithms are examples of deeper concepts.
- **Build understanding progressively**: Each card should help the learner build a mental model, not just memorize facts.
- **Explain the "why"**: Why does this design choice matter? What problem does it solve? What are the trade-offs?
- **Connect to intuition**: Help the learner see *why* something makes sense, not just *what* it is.
- **Avoid information dumps**: A card that lists 10 bullet points teaches nothing. Focus on one clear insight per card.
- **Be exhaustive**: Cover a topic thoroughly with multiple cards from different angles rather than one overloaded card.

### Good Question Types
- **Structural**: "How is X structured?" - explain the components and how they fit together
- **Comparative**: "Why use X instead of Y for Z?" - forces understanding of trade-offs and design choices
- **Reasoning**: "Why does X work?" or "Why can't X do Y?" - builds deeper understanding
- **Mechanism**: "What does X do?" or "What is the purpose of X?" - clarifies function
- **Consequences**: "What information does X have access to?" - traces through implications

### Question Phrasing
- Ask about the concept, not the specific instance (e.g., "How is an encoder-only transformer structured?" not "How is BERT structured?")
- Comparative questions should highlight the relevant context (e.g., "Why use encoder-decoder for translation instead of decoder-only?")
- Avoid yes/no questions - prefer "why" and "how"

### LaTeX
- Use LaTeX for all mathematical equations
- Inline math: `\( ... \)`
- Matrices: `\begin{bmatrix} ... \end{bmatrix}`
- Vectors: `\vec{v}`, `\hat{i}`
- Greek letters: `\lambda`, `\theta`, etc.

### Text Formatting
- Use HTML tags for formatting (not Markdown)
- Bold: `<b>text</b>` (not `**text**`)
- Italics: `<i>text</i>` (not `*text*`)
- Line breaks: `<br>` (not `\n`)
- Unordered lists: `<ul><li>item</li></ul>`
- Ordered lists: `<ol><li>item</li></ol>`

### Example
```json
{
  "back": "The determinant tells you:<br><ul><li>How much areas/volumes scale</li><li>Whether orientation flips (negative)</li></ul>Formula: \\( \\det(A) = ad - bc \\)"
}
```

## File Structure

### Lesson Files
- One JSON file per lesson: `content/lesson_XX.json`
- Title format: `"Lesson XX: {title}"` (for proper Anki sorting)

### Card UIDs
- Format: `{uid_prefix}-XX-YYY` where XX is lesson number, YYY is card number
- The `uid_prefix` is configured in `content/config.json`
- Example: `uid_prefix-01-001`

### Tags
- Always include chapter tag: `chXX`
- Add 1-2 topic tags: `neural-networks`, `backpropagation`, `cnn`, etc.

### Images
- Store images in `content/images/`
- Naming convention: `{full_card_uid}_{sequence}.{ext}`
  - Example: `deep-learning-foundations-and-concepts-12-071_01.png`
  - Multiple images for same card: `..._01.png`, `..._02.png`, etc.
- Supported formats: png, jpg, jpeg, gif, webp, svg
- Reference in card JSON using HTML img tags:
  ```json
  {
    "back": "See diagram:<br><img src=\"deep-learning-foundations-and-concepts-12-071_01.png\">"
  }
  ```
- Images are automatically:
  - Uploaded to Anki when syncing
  - Deleted from Anki when the corresponding card is removed or when the image file is deleted from `content/images/`

