1	#!/usr/bin/env python3
     2	"""Codex-Lite: a compact coding assistant with a quality-focused pipeline.
     3	
     4	Design goals:
     5	- Keep the implementation small and easy to audit.
     6	- Preserve coding quality with a structured multi-pass workflow.
     7	- Work in offline mode without API credentials.
     8	"""
     9	
    10	from __future__ import annotations
    11	
    12	import argparse
    13	import importlib
    14	import importlib.util
    15	import os
    16	import textwrap
    17	from dataclasses import dataclass
    18	from typing import List
    19	
    20	SYSTEM_PROMPT = textwrap.dedent(
    21	    """
    22	    You are Codex-Lite, a high-signal coding assistant.
    23	
    24	    Core behavior:
    25	    - Prioritize correctness, then clarity, then brevity.
    26	    - Provide complete code when asked for code.
    27	    - Explain assumptions and call out uncertainty explicitly.
    28	    - Include tests/checks and exact commands to validate.
    29	    - Prefer practical, idiomatic patterns over clever tricks.
    30	
    31	    Output format for coding tasks:
    32	    1) Brief approach summary.
    33	    2) Implementation (code/steps).
    34	    3) Verification commands.
    35	    4) Risks or edge cases.
    36	    """
    37	).strip()
    38	
    39	
    40	def _get_openai_client() -> object | None:
    41	    """Return an OpenAI client if SDK + credentials are available."""
    42	    if not os.getenv("OPENAI_API_KEY"):
    43	        return None
    44	    if importlib.util.find_spec("openai") is None:
    45	        return None
    46	    openai_module = importlib.import_module("openai")
    47	    return openai_module.OpenAI()
    48	
    49	
    50	@dataclass
    51	class LiteConfig:
    52	    model: str = "gpt-4o-mini"
    53	    temperature: float = 0.1
    54	    max_tokens: int = 900
    55	    planning_tokens: int = 280
    56	    critique_tokens: int = 280
    57	
    58	
    59	class CodexLite:
    60	    """Small assistant wrapper using a plan -> draft -> critique -> final loop."""
    61	
    62	    def __init__(self, config: LiteConfig):
    63	        self.config = config
    64	        self.client = _get_openai_client()
    65	
    66	    def _offline_answer(self, user_input: str) -> str:
    67	        return "\n".join(
    68	            [
    69	                "Offline mode (no OpenAI SDK and/or OPENAI_API_KEY).",
    70	                "",
    71	                "Approach summary:",
    72	                "- I will still optimize for coding quality by using a strict response scaffold.",
    73	                "",
    74	                "Implementation:",
    75	                f"- Restate request: {user_input}",
    76	                "- Break work into: requirements -> design -> implementation -> tests.",
    77	                "- Produce minimal, runnable code and avoid hidden assumptions.",
    78	                "",
    79	                "Verification commands:",
    80	                "- Run formatter/linter for your language (e.g., ruff, black, eslint, gofmt).",
    81	                "- Run unit tests and a focused smoke test of the changed behavior.",
    82	                "",
    83	                "Risks or edge cases:",
    84	                "- Missing constraints (runtime, framework, API shape) can cause wrong choices.",
    85	                "- If you share those constraints, I can return a concrete production-ready patch.",
    86	            ]
    87	        )
    88	
    89	    def answer(self, user_input: str) -> str:
    90	        if not self.client:
    91	            return self._offline_answer(user_input)
    92	
    93	        plan = self.client.responses.create(
    94	            model=self.config.model,
    95	            temperature=self.config.temperature,
    96	            max_output_tokens=self.config.planning_tokens,
    97	            input=[
    98	                {"role": "system", "content": SYSTEM_PROMPT},
    99	                {
   100	                    "role": "user",
   101	                    "content": (
   102	                        "Create a concise implementation plan for this coding request. "
   103	                        "Include assumptions, test strategy, and likely edge cases.\n\n"
   104	                        f"Request: {user_input}"
   105	                    ),
   106	                },
   107	            ],
   108	        )
   109	
   110	        draft = self.client.responses.create(
   111	            model=self.config.model,
   112	            temperature=self.config.temperature,
   113	            max_output_tokens=self.config.max_tokens,
   114	            input=[
   115	                {"role": "system", "content": SYSTEM_PROMPT},
   116	                {
   117	                    "role": "user",
   118	                    "content": (
   119	                        f"User request: {user_input}\n\n"
   120	                        f"Implementation plan: {plan.output_text}\n\n"
   121	                        "Write the best possible answer for a coding user."
   122	                    ),
   123	                },
   124	            ],
   125	        )
   126	
   127	        critique = self.client.responses.create(
   128	            model=self.config.model,
   129	            temperature=0.0,
   130	            max_output_tokens=self.config.critique_tokens,
   131	            input=[
   132	                {"role": "system", "content": SYSTEM_PROMPT},
   133	                {
   134	                    "role": "user",
   135	                    "content": (
   136	                        "Critique the draft answer for correctness, omissions, weak tests, "
   137	                        "and unclear assumptions. Return only actionable improvements.\n\n"
   138	                        f"User request: {user_input}\n\n"
   139	                        f"Draft answer: {draft.output_text}"
   140	                    ),
   141	                },
   142	            ],
   143	        )
   144	
   145	        final = self.client.responses.create(
   146	            model=self.config.model,
   147	            temperature=self.config.temperature,
   148	            max_output_tokens=self.config.max_tokens,
   149	            input=[
   150	                {"role": "system", "content": SYSTEM_PROMPT},
   151	                {
   152	                    "role": "user",
   153	                    "content": (
   154	                        f"User request: {user_input}\n\n"
   155	                        f"Plan: {plan.output_text}\n\n"
   156	                        f"Draft: {draft.output_text}\n\n"
   157	                        f"Critique: {critique.output_text}\n\n"
   158	                        "Produce the improved final answer, incorporating critique fixes."
   159	                    ),
   160	                },
   161	            ],
   162	        )
   163	        return final.output_text
   164	
   165	
   166	def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
   167	    parser = argparse.ArgumentParser(description="Run Codex-Lite.")
   168	    parser.add_argument("prompt", help="User prompt to answer")
   169	    parser.add_argument("--model", default="gpt-4o-mini", help="Model name")
   170	    parser.add_argument("--temperature", type=float, default=0.1)
   171	    parser.add_argument("--max-tokens", type=int, default=900)
   172	    parser.add_argument("--planning-tokens", type=int, default=280)
   173	    parser.add_argument("--critique-tokens", type=int, default=280)
   174	    return parser.parse_args(argv)
   175	
   176	
   177	def main() -> None:
   178	    args = parse_args()
   179	    assistant = CodexLite(
   180	        LiteConfig(
   181	            model=args.model,
   182	            temperature=args.temperature,
   183	            max_tokens=args.max_tokens,
   184	            planning_tokens=args.planning_tokens,
   185	            critique_tokens=args.critique_tokens,
   186	        )
   187	    )
   188	    print(assistant.answer(args.prompt))
   189	
   190	
   191	if __name__ == "__main__":
   192	    main()
