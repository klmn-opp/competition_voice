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
        silence_threshold: float = 0.015,
        silence_duration_seconds: float = 0.8,
        min_voice_seconds: float = 0.25,
        max_segment_seconds: float = 4.0,
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
        self._silence_threshold = silence_threshold
        self._silence_duration_seconds = silence_duration_seconds
        self._min_voice_seconds = min_voice_seconds
        self._max_segment_seconds = max_segment_seconds

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
        else:
            audio = self._listen_continuous(sd, np)

        if self._grammar:
            recognizer = self._recognizer_cls(self._model, self._sample_rate, self._grammar)
        else:
            recognizer = self._recognizer_cls(self._model, self._sample_rate)
        recognizer.AcceptWaveform(audio.tobytes())
        result = json.loads(recognizer.FinalResult())
        return str(result.get("text", "")).replace(" ", "").strip()

    def _listen_continuous(self, sd, np):
        blocksize = 1024
        frames = []
        speaking = False
        voiced_seconds = 0.0
        silent_seconds = 0.0
        min_voice_frames = self._min_voice_seconds
        max_segment_seconds = self._max_segment_seconds
        with sd.InputStream(
            channels=1,
            samplerate=self._sample_rate,
            dtype=np.int16,
            device=self._microphone_index,
            blocksize=blocksize,
        ) as stream:
            print("[监听] 常驻监听中，直接说话即可...")
            while True:
                block, _ = stream.read(blocksize)
                if block is None:
                    continue
                energy = _rms(block)
                block_seconds = len(block) / float(self._sample_rate)
                if energy >= self._silence_threshold:
                    speaking = True
                    silent_seconds = 0.0
                    voiced_seconds += block_seconds
                    frames.append(block.copy())
                elif speaking:
                    silent_seconds += block_seconds
                    frames.append(block.copy())

                if speaking:
                    if voiced_seconds >= min_voice_frames and silent_seconds >= self._silence_duration_seconds:
                        break
                    if voiced_seconds >= max_segment_seconds:
                        break

        if not frames:
            return np.zeros((0, 1), dtype=np.int16)
        return np.concatenate(frames, axis=0)


class SherpaVoiceInput:
    def __init__(
        self,
        model_dir: Path,
        vad_model_path: Path,
        sample_rate: int,
        microphone_index: int | None,
        num_threads: int = 2,
        language: str = "zh",
        min_silence_duration: float = 0.35,
        read_seconds: float = 0.1,
    ):
        try:
            import sherpa_onnx  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("缺少 sherpa-onnx 依赖，请先在虚拟环境安装 requirements-sherpa.txt") from exc

        model_file = model_dir / "model.int8.onnx"
        tokens_file = model_dir / "tokens.txt"
        for path in (model_file, tokens_file, vad_model_path):
            if not path.is_file():
                raise RuntimeError(f"缺少模型文件: {path}")

        self._model_file = model_file
        self._tokens_file = tokens_file
        self._vad_model_path = vad_model_path
        self._sample_rate = sample_rate
        self._microphone_index = microphone_index
        self._num_threads = num_threads
        self._language = language
        self._min_silence_duration = min_silence_duration
        self._read_seconds = read_seconds
        self._recognizer = None
        self._vad = None
        self._window_size = None

    def listen(self) -> str:
        try:
            import numpy as np
            import sounddevice as sd
            import sherpa_onnx
        except ImportError as exc:
            raise RuntimeError("缺少 sounddevice/numpy/sherpa-onnx 依赖，请先安装 requirements-sherpa.txt") from exc

        self._ensure_models(sherpa_onnx)
        assert self._recognizer is not None
        assert self._vad is not None

        samples_per_read = int(self._read_seconds * self._sample_rate)
        buffer = np.array([], dtype=np.float32)
        count = 0

        print(f"已启动常驻监听。直接说话即可，Ctrl+C 退出。SenseVoice language={self._language}")
        print("本测试只打印识别文本和匹配动作，不写 PLC。")

        with sd.InputStream(
            channels=1,
            dtype="float32",
            samplerate=self._sample_rate,
            device=self._microphone_index,
        ) as stream:
            while True:
                samples, _ = stream.read(samples_per_read)
                buffer = np.concatenate([buffer, samples.reshape(-1)])

                window_size = self._window_size or 512
                while len(buffer) > window_size:
                    self._vad.accept_waveform(buffer[:window_size])
                    buffer = buffer[window_size:]

                while not self._vad.empty():
                    segment = self._vad.front.samples
                    self._vad.pop()

                    count += 1
                    asr_stream = self._recognizer.create_stream()
                    asr_stream.accept_waveform(self._sample_rate, segment)
                    self._recognizer.decode_stream(asr_stream)
                    text = asr_stream.result.text.strip()
                    if not text:
                        continue

                    return text.replace(" ", "").strip()

    def _ensure_models(self, sherpa_onnx) -> None:
        if self._recognizer is None:
            self._recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=str(self._model_file),
                tokens=str(self._tokens_file),
                num_threads=self._num_threads,
                language=self._language,
                use_itn=True,
                debug=False,
            )
        if self._vad is None:
            vad_config = sherpa_onnx.VadModelConfig()
            vad_config.silero_vad.model = str(self._vad_model_path)
            vad_config.silero_vad.min_silence_duration = self._min_silence_duration
            vad_config.sample_rate = self._sample_rate
            self._window_size = vad_config.silero_vad.window_size
            self._vad = sherpa_onnx.VoiceActivityDetector(vad_config, buffer_size_in_seconds=30)


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


def _rms(block) -> float:
    import numpy as np

    data = block.astype(np.float32)
    if data.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(data))) / 32768.0)
