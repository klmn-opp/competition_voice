from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol


class VoiceInput(Protocol):
    def listen(self) -> str:
        ...


class KeyboardInput:
    def listen(self) -> str:
        return input("请输入命令文字> ").strip()


class VoskVoiceInput:
    def __init__(
        self,
        model_path: Path,
        grammar_phrases: list[str],
        use_grammar: bool,
        sample_rate: int,
        record_seconds: float,
        microphone_index: int | None,
        push_to_talk: bool,
    ):
        try:
            from vosk import KaldiRecognizer, Model, SetLogLevel
        except ImportError as exc:
            raise RuntimeError("缺少 vosk 依赖，请先在虚拟环境安装 requirements.txt") from exc

        if not model_path.exists():
            raise RuntimeError(f"Vosk 模型目录不存在: {model_path}")

        SetLogLevel(-1)
        self._model = Model(str(model_path))
        self._recognizer_cls = KaldiRecognizer
        self._grammar = json.dumps(grammar_phrases, ensure_ascii=False) if use_grammar else None
        self._sample_rate = sample_rate
        self._record_seconds = record_seconds
        self._microphone_index = microphone_index
        self._push_to_talk = push_to_talk

    def listen(self) -> str:
        try:
            import numpy as np
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("缺少 sounddevice/numpy 依赖，请先在虚拟环境安装 requirements.txt") from exc

        if self._push_to_talk:
            input("按 Enter 开始说话...")

        audio = sd.rec(
            int(self._record_seconds * self._sample_rate),
            samplerate=self._sample_rate,
            channels=1,
            dtype=np.int16,
            device=self._microphone_index,
            blocking=True,
        )
        sd.stop()

        if self._grammar:
            recognizer = self._recognizer_cls(self._model, self._sample_rate, self._grammar)
        else:
            recognizer = self._recognizer_cls(self._model, self._sample_rate)
        recognizer.AcceptWaveform(audio.tobytes())
        result = json.loads(recognizer.FinalResult())
        return str(result.get("text", "")).replace(" ", "").strip()


class Speaker:
    def __init__(self, enabled: bool):
        self.enabled = enabled
        self._engine = None

    def say(self, text: str) -> None:
        print(f"[播报] {text}")
        if not self.enabled:
            return
        try:
            if self._engine is None:
                import pyttsx3

                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", 145)
                self._engine.setProperty("volume", 1.0)
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception as exc:
            print(f"[TTS] 播报失败: {exc}")
