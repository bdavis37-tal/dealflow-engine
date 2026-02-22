"""
Shared Claude AI service for the dealflow engine.

All Anthropic API interactions go through this module. Features:
- Centralized API key management
- Graceful fallback when API key is missing or calls fail
- Streaming support via async generators
- Simple in-process cache (field explanations, per-deal narratives)
- Token usage tracking

IMPORTANT: The deterministic financial engine is the source of truth for all numbers.
Claude is used only for interpretation, narrative, and natural language — never for math.
"""
from __future__ import annotations

import json
import logging
import os
import hashlib
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AI_MODEL = os.environ.get("AI_MODEL", "claude-sonnet-4-20250514")
AI_ENABLED = os.environ.get("AI_ENABLED", "true").lower() == "true"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Token budget per feature (configurable via env)
MAX_TOKENS_NARRATIVE = int(os.environ.get("AI_MAX_TOKENS_NARRATIVE", "1500"))
MAX_TOKENS_CHAT = int(os.environ.get("AI_MAX_TOKENS_CHAT", "2000"))
MAX_TOKENS_HELP = int(os.environ.get("AI_MAX_TOKENS_HELP", "300"))
MAX_TOKENS_PARSE = int(os.environ.get("AI_MAX_TOKENS_PARSE", "800"))
MAX_TOKENS_SCENARIO = int(os.environ.get("AI_MAX_TOKENS_SCENARIO", "400"))

# ---------------------------------------------------------------------------
# Simple in-process cache (no Redis needed for V1)
# ---------------------------------------------------------------------------

_cache: dict[str, str] = {}
_token_usage: dict[str, int] = {"input": 0, "output": 0, "calls": 0}


def _cache_key(*parts: str) -> str:
    combined = "|".join(parts)
    return hashlib.md5(combined.encode()).hexdigest()


def _get_cached(key: str) -> str | None:
    return _cache.get(key)


def _set_cached(key: str, value: str) -> None:
    # Simple LRU: evict oldest entries if cache grows large
    if len(_cache) > 500:
        oldest_key = next(iter(_cache))
        del _cache[oldest_key]
    _cache[key] = value


# ---------------------------------------------------------------------------
# Client initialization
# ---------------------------------------------------------------------------

def _get_client():
    """Get Anthropic client, returning None if not configured."""
    if not AI_ENABLED:
        return None
    if not ANTHROPIC_API_KEY:
        logger.debug("ANTHROPIC_API_KEY not set — AI features disabled")
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    except ImportError:
        logger.warning("anthropic package not installed — AI features disabled")
        return None
    except Exception as e:
        logger.warning("Failed to initialize Anthropic client: %s", e)
        return None


def _get_async_client():
    """Get async Anthropic client."""
    if not AI_ENABLED:
        return None
    if not ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
        return anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    except ImportError:
        return None
    except Exception as e:
        logger.warning("Failed to initialize async Anthropic client: %s", e)
        return None


def is_ai_available() -> bool:
    """Check whether AI features are available (key set + package installed)."""
    if not AI_ENABLED or not ANTHROPIC_API_KEY:
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Core ask functions
# ---------------------------------------------------------------------------

def ask_claude(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 1000,
    cache_key: str | None = None,
) -> str | None:
    """
    Make a synchronous Claude API call.

    Args:
        system_prompt: The system prompt that sets Claude's role and context.
        user_message: The user's message or query.
        max_tokens: Maximum tokens in the response.
        cache_key: If provided, cache the result under this key.

    Returns:
        Claude's response text, or None if AI is unavailable or call fails.
        Never raises — always degrades gracefully.
    """
    if cache_key:
        cached = _get_cached(cache_key)
        if cached:
            return cached

    client = _get_client()
    if client is None:
        return None

    try:
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        text = response.content[0].text if response.content else ""

        # Track usage
        if hasattr(response, "usage"):
            _token_usage["input"] += response.usage.input_tokens
            _token_usage["output"] += response.usage.output_tokens
            _token_usage["calls"] += 1

        if cache_key and text:
            _set_cached(cache_key, text)

        return text

    except Exception as e:
        logger.warning("Claude API call failed: %s", e)
        return None


def ask_claude_with_history(
    system_prompt: str,
    messages: list[dict[str, str]],
    max_tokens: int = 2000,
) -> str | None:
    """
    Make a Claude API call with a conversation history.

    Args:
        system_prompt: System prompt.
        messages: List of {"role": "user"|"assistant", "content": "..."} dicts.
        max_tokens: Max response tokens.

    Returns:
        Claude's response text, or None on failure.
    """
    client = _get_client()
    if client is None:
        return None

    try:
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )
        text = response.content[0].text if response.content else ""
        if hasattr(response, "usage"):
            _token_usage["input"] += response.usage.input_tokens
            _token_usage["output"] += response.usage.output_tokens
            _token_usage["calls"] += 1
        return text
    except Exception as e:
        logger.warning("Claude API call failed: %s", e)
        return None


async def stream_claude(
    system_prompt: str,
    messages: list[dict[str, str]],
    max_tokens: int = 2000,
) -> AsyncGenerator[str, None]:
    """
    Stream a Claude response as an async generator of text chunks.

    Used for chat, narrative generation, and scenario stories.
    Yields text chunks as they arrive. Yields nothing if AI unavailable.

    Usage:
        async for chunk in stream_claude(system, messages, max_tokens):
            # send chunk to client via SSE
    """
    client = _get_async_client()
    if client is None:
        return

    try:
        async with client.messages.stream(
            model=AI_MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

            # Track final usage
            final_msg = await stream.get_final_message()
            if hasattr(final_msg, "usage"):
                _token_usage["input"] += final_msg.usage.input_tokens
                _token_usage["output"] += final_msg.usage.output_tokens
                _token_usage["calls"] += 1

    except Exception as e:
        logger.warning("Claude streaming failed: %s", e)
        return


def get_token_usage() -> dict[str, int]:
    """Return cumulative token usage statistics (for dev monitoring)."""
    return dict(_token_usage)


# ---------------------------------------------------------------------------
# System prompt builders
# ---------------------------------------------------------------------------

def deal_parser_system_prompt() -> str:
    """System prompt for the conversational deal entry parser."""
    return """You are a senior M&A advisor helping a user model a potential acquisition.
Your job is to extract deal parameters from natural language and ask smart follow-up questions.

EXTRACTION RULES:
1. Extract any financial figures mentioned: revenue, EBITDA, margins, deal size, industry, company names
2. If the user mentions a margin (e.g., "18% EBITDA margin"), compute the dollar amount if you know revenue
3. For any fields the user doesn't mention, use industry benchmarks — don't ask about them
4. Ask ONE follow-up question at a time. Never interrogate with multiple questions.
5. If you have enough for a Quick Model (revenue, EBITDA, deal size, industry for both parties), confirm and stop asking

RESPONSE FORMAT:
Always respond with valid JSON in exactly this structure:
{
  "status": "need_more_info" | "ready_to_model",
  "follow_up_question": "string (only when status=need_more_info)",
  "extracted": {
    "acquirer_name": null | "string",
    "acquirer_revenue": null | number,
    "acquirer_ebitda": null | number,
    "acquirer_industry": null | "string",
    "target_name": null | "string",
    "target_revenue": null | number,
    "target_ebitda": null | number,
    "target_ebitda_margin": null | number,
    "target_industry": null | "string",
    "acquisition_price": null | number,
    "cash_percentage": null | number,
    "debt_percentage": null | number,
    "synergy_description": null | "string"
  },
  "confidence": {
    "acquirer_revenue": 0.0-1.0,
    "target_revenue": 0.0-1.0,
    "acquisition_price": 0.0-1.0
  },
  "summary": "string — brief confirmation of what you understood, shown to user"
}

TONE: Conversational, professional but not stuffy. Like a smart advisor at a coffee meeting."""


def narrative_system_prompt(mode: str) -> str:
    """System prompt for deal narrative generation."""
    language_note = (
        "Write in plain English that a business owner can understand. Avoid jargon."
        if mode == "quick"
        else "You can use standard finance terminology — the user is finance-literate."
    )
    return f"""You are a senior M&A advisor writing a deal assessment. {language_note}

RULES:
- Reference specific numbers from the deal data. Never say "significant savings" — say "$4.2M in annual savings."
- Be honest about risks. If the deal looks risky, say so directly.
- Write like you're presenting to a board, not filing a textbook entry.
- Keep the verdict narrative to 3-5 sentences. Punchy and direct.
- Each risk narrative: 2-3 sentences max. What it means and what to watch.
- Executive summary: 3-4 paragraphs. Deal rationale → financial impact → risks → recommendation.
- Do not hedge every statement with "it depends." Take a position.
- The numbers from the engine are exact. Trust them. Your job is to interpret, not recalculate.

OUTPUT FORMAT: Respond with valid JSON:
{{
  "verdict_narrative": "string",
  "risk_narratives": {{"metric_name": "narrative string", ...}},
  "executive_summary": "string (markdown formatted, 3-4 paragraphs)"
}}"""


def chat_system_prompt(deal_context: dict[str, Any]) -> str:
    """System prompt for the AI co-pilot chat."""
    context_json = json.dumps(deal_context, indent=2, default=str)
    return f"""You are a senior M&A advisor with deep expertise. You have full context of the deal being modeled.

DEAL CONTEXT:
{context_json}

YOUR ROLE:
- Act as the user's trusted advisor on this specific deal. You know their numbers.
- Be direct and opinionated. If the leverage is too high, say so.
- Reference specific numbers from the deal context — never give generic advice.
- When the user asks "what if" questions about parameters, provide BOTH qualitative insight AND a JSON block of suggested changes.
- For "what if" parameter suggestions, include them as: <parameter_changes>{{...}}</parameter_changes>
- Keep responses concise. 2-4 paragraphs max unless the user asks for more.
- If asked about comparable deals or market data, use your training knowledge but note the caveat.

PARAMETER CHANGE FORMAT (when suggesting deal modifications):
<parameter_changes>
{{
  "description": "What this change represents",
  "changes": {{
    "structure.cash_percentage": 0.5,
    "structure.debt_percentage": 0.3,
    "structure.stock_percentage": 0.2
  }},
  "apply_label": "Apply: 50/20/30 cash/stock/debt split"
}}
</parameter_changes>"""


def field_help_system_prompt(industry: str) -> str:
    """System prompt for contextual field help."""
    return f"""You are a senior M&A advisor explaining financial concepts in context.
The user is modeling an acquisition involving a {industry} company.
Explain concepts as they apply to THIS industry and deal type.
Be specific. Give ranges and benchmarks. 2-4 sentences maximum.
Plain English — no jargon unless you explain it."""


def scenario_system_prompt() -> str:
    """System prompt for sensitivity scenario storytelling."""
    return """You are an M&A advisor explaining what a specific deal scenario means.
Write ONE paragraph (4-6 sentences) in plain English telling the story of this scenario.
- What changed vs the base case
- What that means for the deal outcome
- What the key risk or opportunity is in this scenario
- Whether you'd still do the deal at these terms
Be direct. Don't hedge. Make it vivid."""
