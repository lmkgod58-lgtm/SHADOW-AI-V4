import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

OPENAI_URL = "https://api.openai.com/v1/responses"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


class AIRouter:
    """Provider router for real OpenAI and Anthropic APIs.

    No OpenAI-compatible proxy is used. Providers are called directly with
    their official HTTP APIs. Keys stay on the backend and are never sent to
    the APK.
    """

    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-5").strip()
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5").strip()
        self.timeout = int(os.getenv("AI_TIMEOUT_SECONDS", "45"))

    def status(self) -> Dict[str, Any]:
        return {
            "openai_configured": bool(self.openai_key),
            "anthropic_configured": bool(self.anthropic_key),
            "openai_model": self.openai_model,
            "anthropic_model": self.anthropic_model,
        }

    @staticmethod
    def _history_text(history: List[Dict[str, str]], limit: int = 16) -> str:
        lines = []
        for item in history[-limit:]:
            role = item.get("role", "user")
            content = str(item.get("content", "")).strip()
            if content:
                lines.append(f"{role.upper()}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _system(royal_mode: bool) -> str:
        if royal_mode:
            identity = (
                "You are Shadow AI in Royal Mode. Treat Lindo as your king with respectful knight-like loyalty. "
                "Use tasteful royal language and call him Lindo or my king when natural. Stay genuinely useful."
            )
        else:
            identity = "You are Shadow AI, a capable, warm, direct general-purpose AI assistant."
        return (
            identity + "\n\n"
            "You can explain, research, compare, plan, code, troubleshoot, and advise. "
            "Never claim you searched the web unless research evidence is actually supplied. "
            "When evidence is supplied, synthesize it, resolve contradictions when possible, and mark uncertainty. "
            "Prefer useful conclusions over dumping raw search results. Be concise for simple requests and detailed when needed. "
            "For coding, provide correct runnable code and explain important changes."
        )

    def _openai(self, user_prompt: str, system: str, max_output_tokens: int = 1000) -> Optional[str]:
        if not self.openai_key:
            return None
        payload = {
            "model": self.openai_model,
            "instructions": system,
            "input": user_prompt,
            "max_output_tokens": max_output_tokens,
        }
        try:
            r = requests.post(
                OPENAI_URL,
                headers={"Authorization": f"Bearer {self.openai_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
            r.raise_for_status()
            data = r.json()
            text = data.get("output_text")
            if text:
                return text.strip()
            # Defensive parser for response blocks.
            parts = []
            for item in data.get("output", []) or []:
                for content in item.get("content", []) or []:
                    if content.get("type") in ("output_text", "text") and content.get("text"):
                        parts.append(content["text"])
            return "\n".join(parts).strip() or None
        except Exception as exc:
            print(f"[AI/OpenAI] {type(exc).__name__}: {exc}")
            return None

    def _anthropic(self, user_prompt: str, system: str, max_tokens: int = 1000) -> Optional[str]:
        if not self.anthropic_key:
            return None
        payload = {
            "model": self.anthropic_model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        try:
            r = requests.post(
                ANTHROPIC_URL,
                headers={
                    "x-api-key": self.anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
            r.raise_for_status()
            data = r.json()
            parts = [x.get("text", "") for x in data.get("content", []) if x.get("type") == "text"]
            return "\n".join(parts).strip() or None
        except Exception as exc:
            print(f"[AI/Anthropic] {type(exc).__name__}: {exc}")
            return None

    def answer(
        self,
        message: str,
        history: List[Dict[str, str]],
        research: str = "",
        royal_mode: bool = False,
        deep_search: bool = False,
    ) -> Dict[str, Any]:
        system = self._system(royal_mode)
        history_text = self._history_text(history)
        prompt = (
            f"CURRENT USER REQUEST:\n{message}\n\n"
            f"RECENT CONVERSATION:\n{history_text or '[none]'}\n\n"
            f"RESEARCH / TOOL EVIDENCE:\n{research or '[none]'}\n\n"
            "Answer the current request. Use the evidence when relevant."
        )

        complex_task = deep_search or len(message.split()) >= 24 or any(
            word in message.lower() for word in ["research", "compare", "latest", "deep", "analyze", "multiple", "sources"]
        )

        if complex_task and self.openai_key and self.anthropic_key:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = {
                    pool.submit(self._openai, prompt, system, 1100): "openai",
                    pool.submit(self._anthropic, prompt, system, 1100): "anthropic",
                }
                answers: Dict[str, Optional[str]] = {}
                for future in as_completed(futures):
                    answers[futures[future]] = future.result()

            candidates = []
            if answers.get("openai"):
                candidates.append(f"OPENAI DRAFT:\n{answers['openai']}")
            if answers.get("anthropic"):
                candidates.append(f"CLAUDE DRAFT:\n{answers['anthropic']}")
            combined = "\n\n".join(candidates)

            if combined:
                synth_prompt = (
                    "You are the final editor for Shadow AI. Two expert systems analyzed the same request.\n\n"
                    f"REQUEST:\n{message}\n\n"
                    f"RESEARCH EVIDENCE:\n{research or '[none]'}\n\n"
                    f"EXPERT ANALYSES:\n{combined}\n\n"
                    "Produce one accurate, useful final answer. Reconcile contradictions instead of blindly combining them. "
                    "Do not mention the internal models or this orchestration unless the user asks."
                )
                final = self._openai(synth_prompt, system, 1300) or self._anthropic(synth_prompt, system, 1300)
                if final:
                    return {"response": final, "mode": "team", "providers": [k for k, v in answers.items() if v]}

        # Normal fast path: OpenAI first, Claude second.
        result = self._openai(prompt, system) if self.openai_key else None
        provider = "openai"
        if not result and self.anthropic_key:
            result = self._anthropic(prompt, system)
            provider = "anthropic"

        if result:
            return {"response": result, "mode": provider, "providers": [provider]}

        return {
            "response": None,
            "mode": "unavailable",
            "providers": [],
            "error": "No configured AI provider returned a response.",
        }
