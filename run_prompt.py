"""
Marketing Consulting Kit — prompt runner.

Works with any OpenAI-compatible endpoint. Two providers are built in:

  * claude       — Anthropic via its OpenAI-compatible endpoint (needs ANTHROPIC_API_KEY)
  * freellmapi   — a local FreeLLMAPI gateway with auto:<profile> routing (default legacy behavior)

Usage:
  # Zero-key smoke test — prints exactly what WOULD be sent, makes no network call:
  python run_prompt.py --dry-run --profile ad-copy --text "Write 10 headlines for..."

  # Live run against Claude (auto-selected when ANTHROPIC_API_KEY is set):
  python run_prompt.py --provider claude --profile seo-research --prompt-file prompts/01-seo-content-package.md

  # Live run against a FreeLLMAPI gateway:
  python run_prompt.py --provider freellmapi --profile ad-copy --text "..."

  python run_prompt.py --list-profiles

Credentials come from env vars (preferred) or --api-key:
  ANTHROPIC_API_KEY   for --provider claude
  FREELLMAPI_KEY      for --provider freellmapi
"""

from __future__ import annotations

import argparse
import os
import sys

PROFILES = {
    "seo-research": "Strategy, audits, SERP research, brand voice",
    "ad-copy": "Ads, emails, landing pages, creative variants",
    "bulk-copy": "Meta tags, local pages, social at scale",
}

DEFAULT_SYSTEM = {
    "seo-research": (
        "You are a senior SEO and content strategist. "
        "Be specific, actionable, and industry-aware. No generic filler."
    ),
    "ad-copy": (
        "You are a direct-response copywriter. "
        "Tight copy, clear CTAs, respect character limits."
    ),
    "bulk-copy": (
        "You are a high-volume content producer. "
        "Consistent quality, scannable output, follow format instructions exactly."
    ),
}

# Anthropic's OpenAI-compatible endpoint. The `openai` SDK talks to Claude when
# pointed here with an ANTHROPIC_API_KEY. Model ids are configurable via env so
# this keeps working as Anthropic's catalog changes; override with --model.
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1/"
CLAUDE_MODELS = {
    "seo-research": os.environ.get("CLAUDE_MODEL_SMART", "claude-3-5-sonnet-latest"),
    "ad-copy": os.environ.get("CLAUDE_MODEL_BALANCED", "claude-3-5-sonnet-latest"),
    "bulk-copy": os.environ.get("CLAUDE_MODEL_FAST", "claude-3-5-haiku-latest"),
}

FREELLMAPI_BASE_URL = os.environ.get("FREELLMAPI_URL", "http://localhost:3001/v1")
FREELLMAPI_PLACEHOLDER_KEY = "freellmapi-your-unified-key"


def load_prompt_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # If file has ## Step sections, user should paste the specific step;
    # for quick runs, use everything after the first ## Step 1 block's user prompt fence.
    if "## Step 1" in content and "**User prompt:**" in content:
        start = content.index("**User prompt:**", content.index("## Step 1"))
        block = content[start:]
        if "```" in block:
            inner = block.split("```", 2)
            if len(inner) >= 2:
                return inner[1].strip()
    return content


def resolve_provider(provider: str) -> str:
    """Turn 'auto' into a concrete provider based on available credentials."""
    if provider != "auto":
        return provider
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude"
    return "freellmapi"


def resolve_endpoint(provider: str, profile: str, api_key: str | None,
                     base_url: str | None, model: str | None):
    """Return (base_url, api_key, model, key_env_name) for the chosen provider."""
    if provider == "claude":
        resolved_base = base_url or ANTHROPIC_BASE_URL
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        resolved_model = model or CLAUDE_MODELS.get(profile, CLAUDE_MODELS["seo-research"])
        return resolved_base, resolved_key, resolved_model, "ANTHROPIC_API_KEY"

    resolved_base = base_url or FREELLMAPI_BASE_URL
    resolved_key = api_key or os.environ.get("FREELLMAPI_KEY", FREELLMAPI_PLACEHOLDER_KEY)
    resolved_model = model or f"auto:{profile}"
    return resolved_base, resolved_key, resolved_model, "FREELLMAPI_KEY"


def build_messages(profile: str, user_prompt: str, system: str | None):
    sys_msg = system or DEFAULT_SYSTEM.get(profile, DEFAULT_SYSTEM["seo-research"])
    return [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": user_prompt},
    ]


def key_is_usable(provider: str, api_key: str) -> bool:
    if not api_key:
        return False
    if provider == "freellmapi" and api_key == FREELLMAPI_PLACEHOLDER_KEY:
        return False
    return True


def run(provider: str, profile: str, user_prompt: str, system: str | None,
        temperature: float, api_key: str | None, base_url: str | None,
        model: str | None, dry_run: bool) -> None:
    provider = resolve_provider(provider)
    resolved_base, resolved_key, resolved_model, key_env = resolve_endpoint(
        provider, profile, api_key, base_url, model
    )
    messages = build_messages(profile, user_prompt, system)

    if dry_run:
        key_state = "set" if key_is_usable(provider, resolved_key) else "MISSING/placeholder"
        print("DRY RUN — no API call made")
        print(f"Provider:  {provider}")
        print(f"Profile:   {profile}")
        print(f"Model:     {resolved_model}")
        print(f"Base URL:  {resolved_base}")
        print(f"API key:   {key_state} (env {key_env})")
        print(f"Temp:      {temperature}")
        print("-" * 60)
        for m in messages:
            print(f"[{m['role']}]")
            print(m["content"])
            print()
        return

    try:
        from openai import OpenAI
    except ImportError:
        print("Install: pip install openai")
        sys.exit(1)

    if provider == "claude" and not key_is_usable(provider, resolved_key):
        print(
            "ANTHROPIC_API_KEY is not set. Add it as a secret / env var, pass "
            "--api-key, or use --dry-run to smoke-test without a key."
        )
        sys.exit(1)

    client = OpenAI(base_url=resolved_base, api_key=resolved_key or "placeholder")

    print(f"Provider: {provider}")
    print(f"Model: {resolved_model}")
    print(f"Base URL: {resolved_base}")
    print("-" * 60)

    resp = client.chat.completions.create(
        model=resolved_model,
        messages=messages,
        temperature=temperature,
    )

    print(resp.choices[0].message.content)
    routed = getattr(resp, "headers", None)
    if routed:
        via = routed.get("x-routed-via") or routed.get("X-Routed-Via")
        if via:
            print("-" * 60)
            print(f"Routed via: {via}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run marketing prompts via Claude or a FreeLLMAPI gateway"
    )
    parser.add_argument(
        "--profile",
        choices=list(PROFILES),
        default="seo-research",
        help="Routing profile (see routing-profiles.md)",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "claude", "freellmapi"],
        default="auto",
        help="LLM provider. 'auto' uses claude when ANTHROPIC_API_KEY is set, else freellmapi.",
    )
    parser.add_argument("--prompt-file", help="Path to a prompt markdown file")
    parser.add_argument("--text", help="Raw user prompt text")
    parser.add_argument("--system", help="Override system prompt")
    parser.add_argument("--model", help="Override the model id for the chosen provider")
    parser.add_argument("--api-key", default=None, help="API key (else read from env)")
    parser.add_argument("--base-url", default=None, help="Override the endpoint base URL")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved request without calling any API (no key needed)",
    )
    parser.add_argument("--list-profiles", action="store_true")
    args = parser.parse_args()

    if args.list_profiles:
        for name, desc in PROFILES.items():
            print(f"  {name:15} — {desc}")
        return

    if args.text:
        user_prompt = args.text
    elif args.prompt_file:
        user_prompt = load_prompt_file(args.prompt_file)
    else:
        parser.error("Provide --text or --prompt-file (or --dry-run with one of them)")

    run(
        provider=args.provider,
        profile=args.profile,
        user_prompt=user_prompt,
        system=args.system,
        temperature=args.temperature,
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
