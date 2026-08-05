from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re

from .config import CommandConfig


_REPLACEMENTS = {
    "罗": "螺",
    "落": "螺",
    "裸": "螺",
    "锣": "螺",
    "木": "母",
    "姆": "母",
    "幕": "母",
    "目": "母",
    "住": "柱",
    "柱子": "柱",
    "坪": "平",
    "品": "平",
    "电": "垫",
    "店": "垫",
    "垫片": "平垫",
    "法": "阀",
    "伐": "阀",
    "发": "阀",
    "球法": "球阀",
    "求": "球",
}


@dataclass(frozen=True)
class IntentMatch:
    intent: str
    command_id: int
    name: str
    phrase: str
    score: float


class IntentParser:
    def __init__(self, commands: tuple[CommandConfig, ...], min_score: float = 0.72):
        self.commands = tuple(cmd for cmd in commands if cmd.enabled)
        self.min_score = min_score

    def grammar_phrases(self) -> list[str]:
        phrases: list[str] = []
        for cmd in self.commands:
            phrases.extend(cmd.phrases)
        return phrases

    def parse(self, text: str) -> IntentMatch | None:
        normalized = normalize_text(text)
        if not normalized:
            return None

        best: IntentMatch | None = None
        for cmd in self.commands:
            for phrase in cmd.phrases:
                normalized_phrase = normalize_text(phrase)
                score = self._score(normalized, normalized_phrase)
                if best is None or score > best.score:
                    best = IntentMatch(
                        intent=cmd.intent,
                        command_id=cmd.command_id,
                        name=cmd.name,
                        phrase=phrase,
                        score=score,
                    )

        if best and best.score >= self.min_score:
            return best
        return None

    @staticmethod
    def _score(text: str, phrase: str) -> float:
        if phrase in text or text in phrase:
            return 1.0
        return SequenceMatcher(None, text, phrase).ratio()


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[，。！？,.!?、：:；;\"'“”‘’（）()【】\[\]]", "", text)
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    return text
