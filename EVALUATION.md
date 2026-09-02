# LLM output evaluation rubric

Each prompt pack in `prompts/` ends with a **human quality checklist**. Model output is not a deliverable until it passes this rubric.

| Criterion | Fail if |
|-----------|---------|
| **Accuracy** | Facts about the business, offer, location, or phone are wrong or invented |
| **Reasoning quality** | Strategy, keyword, or audit claims are not justified |
| **Relevance** | Output ignores the filled variables or the client's actual offer |
| **Instruction adherence** | Misses required sections, format, character limits, or step order |
| **Unsupported claims** | Rankings, results, or competitor statements are not sourced |
| **Source quality** | Competitor/SERP inputs were not used when the prompt required them |
| **Consistency** | Voice, CTA, or naming drifts across steps in the same pack |
| **Formatting** | Not client-ready (broken tables, missing variants, unusable structure) |

## Iteration loop

1. Fill `{{variables}}` in the prompt pack.
2. Run the step (Playground or `run_prompt.py`).
3. Score the output against the table above and the pack's checklist.
4. Tighten constraints (system prompt, format rules, negatives) and re-run.
5. Human-edit, then deliver.

This is applied operator QA on live workflows, not a labeled vendor dataset.
