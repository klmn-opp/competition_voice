from __future__ import annotations

import argparse
import sys

from .config import AppConfig, load_config
from .intent import IntentParser
from .modbus_link import ModbusCommandLink
from .voice import KeyboardInput, Speaker, VoskVoiceInput, VoiceInput


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline competition voice controller")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument(
        "--keyboard",
        action="store_true",
        help="Force keyboard text input instead of speech recognition",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    intent_parser = IntentParser(config.commands)
    speaker = Speaker(config.tts_enabled)
    voice_input = _build_voice_input(config, intent_parser, force_keyboard=args.keyboard)
    link = ModbusCommandLink(config.modbus)

    print("比赛语音控制程序已启动。")
    print("零件编号: 螺柱=1, 螺母=2, 平垫=3, 弹垫=4, 阀体/上球阀=5, 完整装配=10")
    print(f"单寄存器模式: 写入 {config.modbus.registers.command_status}，完成模式={config.modbus.completion_mode}")
    print("输入/说出停止、退出或 Ctrl+C 可结束程序。")

    if not link.connect():
        print("警告: 初始 Modbus 连接失败。程序会在发送命令时按配置尝试重连。")

    speaker.say("语音控制已就绪")

    try:
        while True:
            raw_text = voice_input.listen()
            if not raw_text:
                print("[语音] 未识别到有效命令")
                continue

            print(f"[识别] {raw_text}")
            match = intent_parser.parse(raw_text)
            if match is None:
                speaker.say("未匹配到比赛命令")
                continue

            print(
                f"[意图] {match.intent} -> {match.name}, "
                f"command_id={match.command_id}, score={match.score:.2f}"
            )

            if match.intent == "STOP":
                result = link.send_command(match.command_id)
                if result.ok:
                    speaker.say("已发送停止命令")
                else:
                    speaker.say("停止命令发送失败")
                break

            speaker.say(f"开始{match.name}")
            result = link.send_command(match.command_id)
            if result.ok:
                speaker.say(f"{match.name}完成")
            else:
                detail = result.message
                if result.error_code is not None:
                    detail = f"{detail}，错误码{result.error_code}"
                print(f"[执行失败] {detail}")
                speaker.say(f"{match.name}执行失败")

    except KeyboardInterrupt:
        print("\n用户中断，程序退出。")
    finally:
        link.close()
        speaker.say("程序已退出")

    return 0


def _build_voice_input(
    config: AppConfig,
    intent_parser: IntentParser,
    force_keyboard: bool,
) -> VoiceInput:
    if force_keyboard or config.input_mode == "keyboard":
        return KeyboardInput()
    if config.input_mode != "vosk":
        raise RuntimeError(f"不支持的 input_mode: {config.input_mode}")
    return VoskVoiceInput(
        model_path=config.vosk_model_path,
        grammar_phrases=intent_parser.grammar_phrases(),
        sample_rate=config.sample_rate,
        record_seconds=config.record_seconds,
        microphone_index=config.microphone_index,
        push_to_talk=config.push_to_talk,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
