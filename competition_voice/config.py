from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class RegisterConfig:
    command_status: int


@dataclass(frozen=True)
class ModbusConfig:
    host: str
    port: int
    dry_run: bool
    unit_id: int
    timeout_seconds: float
    local_bind_ip: str | None
    auto_reconnect: bool
    wait_for_completion: bool
    done_timeout_seconds: float
    poll_interval_seconds: float
    completion_mode: str
    done_value: int
    error_min_value: int
    registers: RegisterConfig


@dataclass(frozen=True)
class CommandConfig:
    intent: str
    command_id: int
    name: str
    phrases: tuple[str, ...]
    enabled: bool = True


@dataclass(frozen=True)
class AppConfig:
    input_mode: str
    push_to_talk: bool
    record_seconds: float
    sample_rate: int
    microphone_index: int | None
    vosk_model: str
    vosk_model_path: Path
    use_vosk_grammar: bool
    prompt_path: Path
    tts_enabled: bool
    modbus: ModbusConfig
    commands: tuple[CommandConfig, ...]
    base_dir: Path


VOSK_MODEL_DIRS = {
    "small-cn": "vosk-model-small-cn-0.22",
    "cn": "vosk-model-cn-0.22",
    "multi-cn": "vosk-model-cn-kaldi-multicn-0.15",
}


def load_config(path: str | Path, model_override: str | None = None) -> AppConfig:
    config_path = Path(path).resolve()
    base_dir = config_path.parent
    raw = json.loads(config_path.read_text(encoding="utf-8"))

    modbus_raw = raw["modbus"]
    regs_raw = modbus_raw["registers"]
    registers = RegisterConfig(
        command_status=int(regs_raw["command_status"]),
    )
    modbus = ModbusConfig(
        host=str(modbus_raw["host"]),
        port=int(modbus_raw["port"]),
        dry_run=bool(modbus_raw.get("dry_run", False)),
        unit_id=int(modbus_raw.get("unit_id", 1)),
        timeout_seconds=float(modbus_raw.get("timeout_seconds", 2.0)),
        local_bind_ip=modbus_raw.get("local_bind_ip"),
        auto_reconnect=bool(modbus_raw.get("auto_reconnect", True)),
        wait_for_completion=bool(modbus_raw.get("wait_for_completion", True)),
        done_timeout_seconds=float(modbus_raw.get("done_timeout_seconds", 60.0)),
        poll_interval_seconds=float(modbus_raw.get("poll_interval_seconds", 0.2)),
        completion_mode=str(modbus_raw.get("completion_mode", "cleared_to_zero")),
        done_value=int(modbus_raw.get("done_value", 0)),
        error_min_value=int(modbus_raw.get("error_min_value", 900)),
        registers=registers,
    )

    prompt_path = Path(str(raw.get("prompt_path", "prompt.md")))
    if not prompt_path.is_absolute():
        prompt_path = base_dir / prompt_path
    commands = load_prompt_commands(prompt_path)

    model_name = str(model_override or raw.get("vosk_model", "small-cn"))
    model_path_raw = raw.get("vosk_model_path")
    if model_override or not model_path_raw:
        if model_name not in VOSK_MODEL_DIRS:
            known = ", ".join(sorted(VOSK_MODEL_DIRS))
            raise ValueError(f"未知 Vosk 模型名称: {model_name}，可选: {known}")
        model_path = base_dir / "models" / VOSK_MODEL_DIRS[model_name]
    else:
        model_path = Path(str(model_path_raw))
        if not model_path.is_absolute():
            model_path = base_dir / model_path

    return AppConfig(
        input_mode=str(raw.get("input_mode", "vosk")),
        push_to_talk=bool(raw.get("push_to_talk", True)),
        record_seconds=float(raw.get("record_seconds", 2.0)),
        sample_rate=int(raw.get("sample_rate", 16000)),
        microphone_index=raw.get("microphone_index"),
        vosk_model=model_name,
        vosk_model_path=model_path,
        use_vosk_grammar=bool(raw.get("use_vosk_grammar", False)),
        prompt_path=prompt_path,
        tts_enabled=bool(raw.get("tts_enabled", True)),
        modbus=modbus,
        commands=commands,
        base_dir=base_dir,
    )


_COMMAND_META = {
    "PICK_STUD": (1, "螺柱"),
    "PICK_NUT": (2, "螺母"),
    "PICK_WASHER": (3, "平垫"),
    "PICK_SPRING_WASHER": (4, "弹垫"),
    "PICK_VALVE_BODY": (5, "上球阀"),
    "START_ASSEMBLY": (10, "完整装配"),
    "STOP": (99, "停止"),
}


def load_prompt_commands(path: Path) -> tuple[CommandConfig, ...]:
    commands: list[CommandConfig] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"{path}:{line_no} 格式错误，应该是 意图: 提示词1, 提示词2")
        intent, phrase_text = line.split(":", 1)
        intent = intent.strip()
        if intent not in _COMMAND_META:
            raise ValueError(f"{path}:{line_no} 未知意图: {intent}")
        phrases = tuple(
            part.strip()
            for part in phrase_text.replace("，", ",").split(",")
            if part.strip()
        )
        if not phrases:
            raise ValueError(f"{path}:{line_no} 没有配置提示词")
        command_id, name = _COMMAND_META[intent]
        commands.append(CommandConfig(intent=intent, command_id=command_id, name=name, phrases=phrases))

    if not commands:
        raise ValueError(f"{path} 没有任何有效提示词")
    return tuple(commands)
