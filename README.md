# Marketing Consulting Kit

Reusable prompt packs, model-routing profiles, and human QA checklists for SEO and content operations.

**Zeshan Khalid** · Delray Beach, FL · [365householdgoods@gmail.com](mailto:365householdgoods@gmail.com)

This kit turns ambiguous client work into a repeatable AI workflow: fill variables, run a multi-step prompt, score the output, iterate, then human-edit before delivery.

## What's inside

| File | Purpose |
|------|---------|
| [`EVALUATION.md`](EVALUATION.md) | Rubric used to score LLM output (accuracy, reasoning, relevance, instruction adherence, formatting) |
| [`routing-profiles.md`](routing-profiles.md) | Model routing profiles for research, ad copy, and bulk generation |
| [`client-proposal.md`](client-proposal.md) | One-page proposal template |
| [`prompts/`](prompts/) | Seven fill-in prompt packs, each with a human quality checklist |
| [`run_prompt.py`](run_prompt.py) | Small runner for local OpenAI-compatible APIs |

## Prompt packs

| Service | Profile | File |
|---------|---------|------|
| SEO content package | `seo-research` | [`prompts/01-seo-content-package.md`](prompts/01-seo-content-package.md) |
| Ad copy sprint | `ad-copy` | [`prompts/02-ad-copy-sprint.md`](prompts/02-ad-copy-sprint.md) |
| Content audit | `seo-research` | [`prompts/03-content-audit.md`](prompts/03-content-audit.md) |
| Local SEO pages | `bulk-copy` | [`prompts/04-local-seo-pages.md`](prompts/04-local-seo-pages.md) |
| Social media | `bulk-copy` | [`prompts/05-social-media.md`](prompts/05-social-media.md) |
| Brand voice guide | `seo-research` | [`prompts/06-brand-voice-guide.md`](prompts/06-brand-voice-guide.md) |
| Email sequence | `ad-copy` | [`prompts/07-email-sequence.md`](prompts/07-email-sequence.md) |

## How evaluation works

Every pack ends with a checklist the operator completes — not the model. Typical loop:

1. Fill `{{variables}}`.
2. Generate.
3. Score against [`EVALUATION.md`](EVALUATION.md) and the pack checklist.
4. Tighten constraints and re-run until the output is usable.
5. Human-edit, then deliver.

## Quick start

Works with any OpenAI-compatible endpoint. The notes below use [FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi) locally; you can point `run_prompt.py` at another base URL.

1. Create routing profiles from [`routing-profiles.md`](routing-profiles.md) (or skip if you call a single model).
2. Pick a prompt from `prompts/`, fill in the `{{variables}}`.
3. Run via your playground, or:

```bash
pip install openai
python run_prompt.py --profile seo-research --prompt-file prompts/01-seo-content-package.md
```

4. Score the output with the pack checklist and [`EVALUATION.md`](EVALUATION.md).
5. Human-edit before anything goes to a client.
6. Use [`client-proposal.md`](client-proposal.md) for prospects.

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:3001/v1",
    api_key="freellmapi-your-unified-key",
)

resp = client.chat.completions.create(
    model="auto:seo-research",  # or auto:ad-copy, auto:bulk-copy
    messages=[
        {"role": "system", "content": "You are an expert SEO strategist..."},
        {"role": "user", "content": "YOUR FILLED PROMPT HERE"},
    ],
)
print(resp.choices[0].message.content)
```

Set `FREELLMAPI_KEY` (or `--api-key`) rather than hard-coding secrets.

## License

MIT. See [LICENSE](LICENSE).
