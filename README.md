# Codex-Lite (smaller assistant, stronger coding quality)

`mini_codex.py` is a compact assistant scaffold tuned specifically for coding tasks.

## What changed

Compared with the previous version, this one is much stricter about code quality:

- Uses a **plan -> draft -> critique -> final** generation pipeline.
- Enforces a coding-focused output contract (approach, implementation, verification, risks).
- Improves reliability by adding an explicit critique pass before final output.
- Keeps offline mode useful with a structured coding response template.

## Why this is closer to "just as good at coding"

Small models can approach stronger coding quality by using process discipline:

1. Plan first (requirements + tests + edge cases).
2. Draft full answer.
3. Critique for correctness/omissions.
4. Regenerate a better final answer using that critique.

This script implements exactly that process while staying lightweight.

## Usage

```bash
python3 mini_codex.py "Implement a Python LRU cache with tests"
```

Optional tuning:

```bash
python3 mini_codex.py \
  "Build a Flask endpoint that validates JWT and returns user profile" \
  --model gpt-4o-mini \
  --temperature 0.1 \
  --max-tokens 1000 \
  --planning-tokens 320 \
  --critique-tokens 320
```

## Notes

- If `OPENAI_API_KEY` is set and the `openai` package is installed, API mode is used.
- Otherwise the script falls back to an offline structured coaching response.
