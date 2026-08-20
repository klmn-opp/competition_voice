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
    "骆": "螺",
    "洛": "螺",
    "木": "母",
    "姆": "母",
    "幕": "母",
    "目": "母",
    "沐": "母",
    "姆": "母",
    "住": "柱",
    "注": "柱",
    "助": "柱",
    "朱": "柱",
    "祝": "柱",
    "煮": "柱",
    "柱子": "柱",
    "思": "丝",
    "司": "丝",
    "死": "丝",
    "丝子": "丝",
    "四": "丝",
    "坪": "平",
    "品": "平",
    "屏": "平",
    "频": "平",
    "贫": "平",
    "瓶": "平",
    "评": "平",
    "凭": "平",
    "苹": "平",
    "电": "垫",
    "店": "垫",
    "点": "垫",
    "典": "垫",
    "垫片": "平垫",
    "商": "上",
    "尚": "上",
    "伤": "上",
    "赏": "上",
    "赏": "上",
    "熵": "上",
    "法": "阀",
    "伐": "阀",
    "发": "阀",
    "罚": "阀",
    "乏": "阀",
    "球法": "球阀",
    "求": "球",
}

_KEYWORD_FALLBACKS = (
    ("START_ASSEMBLY", 10, "完整装配", ("启动装配", "开始装配",  "总流程", "全流程")),
    ("STOP", 99, "停止", ("停止", "退出", "结束")),
    ("PICK_STUD", 1, "螺柱", ("螺柱", "螺丝", "丝杆", "螺杆")),
    ("PICK_NUT", 2, "螺母", ("螺母", "螺帽")),
    ("PICK_WASHER", 3, "平垫", ("平垫", "垫片")),
    ("PICK_SPRING_WASHER", 4, "弹垫", ("弹垫",)),
    ("PICK_VALVE_BODY", 5, "上球阀", ("上阀体", "上球阀", "球阀")),
)


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

        keyword_match = self._keyword_fallback(normalized)
        if keyword_match is not None:
            return keyword_match

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

    def _keyword_fallback(self, normalized: str) -> IntentMatch | None:
        enabled_intents = {cmd.intent for cmd in self.commands}
        for intent, command_id, name, keywords in _KEYWORD_FALLBACKS:
            if intent not in enabled_intents:
                continue
            for keyword in keywords:
                if normalize_text(keyword) in normalized:
                    return IntentMatch(
                        intent=intent,
                        command_id=command_id,
                        name=name,
                        phrase=keyword,
                        score=0.95,
                    )
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
