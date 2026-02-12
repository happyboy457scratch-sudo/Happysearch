#!/usr/bin/env python3
"""Codex-Lite: a compact coding assistant with a quality-focused pipeline.

Design goals:
- Keep the implementation small and easy to audit.
- Preserve coding quality with a structured multi-pass workflow.
- Work in offline mode without API credentials.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import textwrap
from dataclasses import dataclass
from typing import List

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are Codex-Lite, a high-signal coding assistant.

    Core behavior:
    - Prioritize correctness, then clarity, then brevity.
    - Provide complete code when asked for code.
    - Explain assumptions and call out uncertainty explicitly.
    - Include tests/checks and exact commands to validate.
    - Prefer practical, idiomatic patterns over clever tricks.

    Output format for coding tasks:
    1) Brief approach summary.
    2) Implementation (code/steps).
    3) Verification commands.
    4) Risks or edge cases.
    """
).strip()


def _get_openai_client() -> object | None:
    """Return an OpenAI client if SDK + credentials are available."""
    if not os.getenv("OPENAI_API_KEY"):
        return None
    if importlib.util.find_spec("openai") is None:
        return None
    openai_module = importlib.import_module("openai")
    return openai_module.OpenAI()


@dataclass
class LiteConfig:
    model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: int = 900
    planning_tokens: int = 280
    critique_tokens: int = 280


class CodexLite:
    """Small assistant wrapper using a plan -> draft -> critique -> final loop."""

    def __init__(self, config: LiteConfig):
        self.config = config
        self.client = _get_openai_client()

    def _offline_answer(self, user_input: str) -> str:
        return "\n".join(
            [
                "Offline mode (no OpenAI SDK and/or OPENAI_API_KEY).",
                "",
                "Approach summary:",
                "- I will still optimize for coding quality by using a strict response scaffold.",
                "",
                "Implementation:",
                f"- Restate request: {user_input}",
                "- Break work into: requirements -> design -> implementation -> tests.",
                "- Produce minimal, runnable code and avoid hidden assumptions.",
                "",
                "Verification commands:",
                "- Run formatter/linter for your language (e.g., ruff, black, eslint, gofmt).",
                "- Run unit tests and a focused smoke test of the changed behavior.",
                "",
                "Risks or edge cases:",
                "- Missing constraints (runtime, framework, API shape) can cause wrong choices.",
                "- If you share those constraints, I can return a concrete production-ready patch.",
            ]
        )

    def answer(self, user_input: str) -> str:
        if not self.client:
            return self._offline_answer(user_input)

        plan = self.client.responses.create(
            model=self.config.model,
            temperature=self.config.temperature,
            max_output_tokens=self.config.planning_tokens,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Create a concise implementation plan for this coding request. "
                        "Include assumptions, test strategy, and likely edge cases.\n\n"
                        f"Request: {user_input}"
                    ),
                },
            ],
        )

        draft = self.client.responses.create(
            model=self.config.model,
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_tokens,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"User request: {user_input}\n\n"
                        f"Implementation plan: {plan.output_text}\n\n"
                        "Write the best possible answer for a coding user."
                    ),
                },
            ],
        )

        critique = self.client.responses.create(
            model=self.config.model,
            temperature=0.0,
            max_output_tokens=self.config.critique_tokens,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Critique the draft answer for correctness, omissions, weak tests, "
                        "and unclear assumptions. Return only actionable improvements.\n\n"
                        f"User request: {user_input}\n\n"
                        f"Draft answer: {draft.output_text}"
                    ),
                },
            ],
        )

        final = self.client.responses.create(
            model=self.config.model,
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_tokens,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"User request: {user_input}\n\n"
                        f"Plan: {plan.output_text}\n\n"
                        f"Draft: {draft.output_text}\n\n"
                        f"Critique: {critique.output_text}\n\n"
                        "Produce the improved final answer, incorporating critique fixes."
                    ),
                },
            ],
        )
        return final.output_text


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Codex-Lite.")
    parser.add_argument("prompt", help="User prompt to answer")
    parser.add_argument("--model", default="gpt-4o-mini", help="Model name")
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-tokens", type=int, default=900)
    parser.add_argument("--planning-tokens", type=int, default=280)
    parser.add_argument("--critique-tokens", type=int, default=280)
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    assistant = CodexLite(
        LiteConfig(
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            planning_tokens=args.planning_tokens,
            critique_tokens=args.critique_tokens,
        )
    )
    print(assistant.answer(args.prompt))


if __name__ == "__main__":
    main()
