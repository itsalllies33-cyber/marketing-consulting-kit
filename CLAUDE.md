# Marketing Consulting Kit — notes for Claude

## Working rule: verify before you build
Before starting any piece of work, say in one or two lines how you will verify it
(which command, which test, or which human check), then do the work and run that check.

## Working rule: show the work as you go
Narrate each step briefly while working: what you're about to do, then the result
(diffs, command output, test results). Don't batch everything into a final summary.

## What this repo is
- `prompts/` — seven fill-in prompt packs (`{{variables}}`), each ending in a human QA checklist.
- `run_prompt.py` — small CLI that sends a filled prompt to any OpenAI-compatible endpoint
  (providers: `claude`, `freellmapi`; `auto` picks Claude when `ANTHROPIC_API_KEY` is set).
- `EVALUATION.md` — human scoring rubric. `routing-profiles.md` — model routing profiles.
- `client-proposal.md` — proposal template. `tests/` — offline smoke tests.

Code only moves a prompt to a model; output quality is judged by a human with the
checklist + `EVALUATION.md`. Don't try to auto-grade deliverables.

## Commands
- Install: `pip install -r requirements-dev.txt`
- Tests (offline, no keys): `python3 -m pytest -q`
- Zero-key smoke test: `python3 run_prompt.py --dry-run --profile ad-copy --text "hi"`
- Test a prompt pack: `python3 run_prompt.py --dry-run --profile seo-research --prompt-file prompts/01-seo-content-package.md`
- List profiles: `python3 run_prompt.py --list-profiles`

## Verification tools by change type
| Change | Verify with |
|--------|-------------|
| `run_prompt.py` | `python3 -m pytest -q`, then a `--dry-run` |
| Provider/endpoint wiring | `--dry-run` → the local mock server in `tests/` → a real key |
| A prompt pack | `--dry-run --prompt-file ...` to see what's sent; then score a live output with the pack checklist |
| Docs / templates | Re-read rendered Markdown; check links and tables |

CI (`.github/workflows/ci.yml`) runs the syntax check + pytest on every push/PR.

## Gotchas
- Run tests with `python3 -m pytest`, not bare `pytest`: in cloud sessions `pytest`
  can be a standalone tool install whose Python lacks `openai`, which fails tests.
- Keep `--dry-run` and `--list-profiles` dependency-free: import `openai` lazily,
  only in the live request path, and after the API-key check.
- Declare `global` before first use — a global-after-use `SyntaxError` once broke the script.
- Never commit API keys; use env vars (`ANTHROPIC_API_KEY`, `FREELLMAPI_KEY`) or `--api-key`.
- Every client deliverable gets a human edit before delivery.
