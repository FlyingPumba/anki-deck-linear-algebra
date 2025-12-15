# Project Instructions

## Package Management
- Use `uv` for Python dependency management (not pip)
- Run scripts with `uv run python <script>`

## Card Content Formatting

### LaTeX
- Use LaTeX for all mathematical equations
- Inline math: `\( ... \)`
- Matrices: `\begin{bmatrix} ... \end{bmatrix}`
- Vectors: `\vec{v}`, `\hat{i}`
- Greek letters: `\lambda`, `\theta`, etc.

### Lists
- Add an extra newline before lists so they display correctly in Anki
- Use `\n\n-` instead of `\n-` before list items

### Example
```json
{
  "back": "The determinant tells you:\n\n- How much areas/volumes scale\n- Whether orientation flips (negative)\n\nFormula: \\( \\det(A) = ad - bc \\)"
}
```

## File Structure

### Lesson Files
- One JSON file per lesson: `content/lesson_XX.json`
- Title format: `"Lesson XX: {title}"` (for proper Anki sorting)

### Card UIDs
- Format: `linear-algebra-XX-YYY` where XX is lesson number, YYY is card number
- Example: `linear-algebra-01-001`, `linear-algebra-14-005`
- The prefix is configured in `content/config.json` as `uid_prefix`

### Tags
- Always include chapter tag: `chXX`
- Add 1-2 topic tags: `vectors`, `determinant`, `eigenvalue`, etc.

## Content Source
- Based on 3Blue1Brown's "Essence of Linear Algebra" series
- https://www.3blue1brown.com/topics/linear-algebra
