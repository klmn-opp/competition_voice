from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from competition_voice.config import load_config
from competition_voice.intent import IntentParser


DEFAULT_MODEL_DIR = ROOT / "models" / "sherpa" / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17"
DEFAULT_VAD_MODEL = ROOT / "models" / "sherpa" / "silero_vad.onnx"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test always-on VAD + sherpa-onnx SenseVoice recognition without PLC output."
    )
    parser.add_argument("--config", default=str(ROOT / "config.voice_test.json"))
    parser.add_argument("--device", type=int, default=None, help="Override microphone index.")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--num-threads", type=int, default=2)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--vad-model", type=Path, default=DEFAULT_VAD_MODEL)
    parser.add_argument("--min-silence", type=float, default=0.35)
    parser.add_argument("--read-seconds", type=float, default=0.1)
    args = parser.parse_args()

    try:
        import numpy as np
        import sounddevice as sd
        import sherpa_onnx
    except ImportError as exc:
        print(f"缺少依赖: {exc}")
        print("请先运行: bash scripts/setup_sherpa.sh")
        return 1

    cfg = load_config(args.config)
    intent_parser = IntentParser(cfg.commands)
    input_device = cfg.microphone_index if args.device is None else args.device

    model_file = args.model_dir / "model.int8.onnx"
    tokens_file = args.model_dir / "tokens.txt"
    for path in (args.vad_model, model_file, tokens_file):
        if not path.is_file():
            print(f"缺少模型文件: {path}")
            print("请先运行: bash scripts/download_sherpa_models.sh")
            return 1

    print("输入设备列表:")
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        if int(dev.get("max_input_channels", 0)) > 0:
            marker = " <- selected" if idx == input_device else ""
            print(f"  {idx}: {dev['name']} | inputs={dev['max_input_channels']}{marker}")
    print()

    print("创建 sherpa-onnx SenseVoice 识别器...")
    recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=str(model_file),
        tokens=str(tokens_file),
        num_threads=args.num_threads,
        use_itn=True,
        debug=False,
    )

    vad_config = sherpa_onnx.VadModelConfig()
    vad_config.silero_vad.model = str(args.vad_model)
    vad_config.silero_vad.min_silence_duration = args.min_silence
    vad_config.sample_rate = args.sample_rate
    window_size = vad_config.silero_vad.window_size
    vad = sherpa_onnx.VoiceActivityDetector(vad_config, buffer_size_in_seconds=30)

    samples_per_read = int(args.read_seconds * args.sample_rate)
    buffer = np.array([], dtype=np.float32)
    count = 0

    print("已启动常驻监听。直接说话即可，Ctrl+C 退出。")
    print("本测试只打印识别文本和匹配动作，不写 PLC。")

    with sd.InputStream(
        channels=1,
        dtype="float32",
        samplerate=args.sample_rate,
        device=input_device,
    ) as stream:
        while True:
            samples, _ = stream.read(samples_per_read)
            buffer = np.concatenate([buffer, samples.reshape(-1)])

            while len(buffer) > window_size:
                vad.accept_waveform(buffer[:window_size])
                buffer = buffer[window_size:]

            while not vad.empty():
                segment = vad.front.samples
                vad.pop()

                asr_stream = recognizer.create_stream()
                asr_stream.accept_waveform(args.sample_rate, segment)
                recognizer.decode_stream(asr_stream)
                text = asr_stream.result.text.strip()
                if not text:
                    continue

                count += 1
                print(f"\n[{count}] 识别文本: {text}")
                match = intent_parser.parse(text)
                if match:
                    print(
                        f"    匹配动作: {match.intent} / {match.name} / "
                        f"command_id={match.command_id} / score={match.score:.2f}"
                    )
                    if match.intent == "STOP":
                        print("收到停止意图，测试退出。")
                        return 0
                else:
                    print("    未匹配到动作")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n用户中断，测试退出。")
