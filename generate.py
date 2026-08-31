"""
Single-call brief generation.

Replaces the Managed Agent session: research runs deterministically in
research.py, then one streamed Sonnet 5 call composes the brief. ~30 sequential
model turns become 1.
"""

import logging
from datetime import date

from anthropic import Anthropic

import prompts
import research

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-5"
MAX_TOKENS = 8000
EFFORT = "medium"


def generate_brief(
    api_key: str,
    tavily_key: str,
    company: str,
    status_callback,
    timeout_seconds: float = 180,
) -> str:
    """Research the company, then compose the brief in one streamed call."""
    status_callback("init")

    result = research.research(company, status_callback, tavily_key)

    client = Anthropic(api_key=api_key, timeout=timeout_seconds)

    status_callback("compose")
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        output_config={"effort": EFFORT},
        system=[
            {
                "type": "text",
                "text": prompts.build_system_prefix(),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": prompts.build_user_message(
                    company, result.payload, date.today()
                ),
            }
        ],
    ) as stream:
        message = stream.get_final_message()

    usage = message.usage
    logger.info(
        "brief=%s cache_read=%s cache_write=%s input=%s output=%s",
        company,
        getattr(usage, "cache_read_input_tokens", 0),
        getattr(usage, "cache_creation_input_tokens", 0),
        usage.input_tokens,
        usage.output_tokens,
    )

    brief = "".join(b.text for b in message.content if b.type == "text")

    if message.stop_reason == "max_tokens":
        raise RuntimeError(
            f"Brief generation for '{company}' was truncated "
            f"(stop_reason=max_tokens, output_tokens={usage.output_tokens})."
        )
    if not brief.strip():
        raise RuntimeError(
            f"Brief generation for '{company}' returned empty output "
            f"(stop_reason={message.stop_reason}, output_tokens={usage.output_tokens})."
        )

    status_callback("done")
    return brief
