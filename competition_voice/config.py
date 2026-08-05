from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RegisterConfig:
    command_id: int
    seq: int
    ack_seq: int
    state: int
    error_code: int


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
    ack_timeout_seconds: float
    done_timeout_seconds: float
    poll_interval_seconds: float
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
    vosk_model_path: Path
    tts_enabled: bool
    modbus: ModbusConfig
    commands: tuple[CommandConfig, ...]
    base_dir: Path


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).resolve()
    base_dir = config_path.parent
    raw = json.loads(config_path.read_text(encoding="utf-8"))

    modbus_raw = raw["modbus"]
    regs_raw = modbus_raw["registers"]
    registers = RegisterConfig(
        command_id=int(regs_raw["command_id"]),
        seq=int(regs_raw["seq"]),
        ack_seq=int(regs_raw["ack_seq"]),
        state=int(regs_raw["state"]),
        error_code=int(regs_raw["error_code"]),
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
        ack_timeout_seconds=float(modbus_raw.get("ack_timeout_seconds", 5.0)),
        done_timeout_seconds=float(modbus_raw.get("done_timeout_seconds", 60.0)),
        poll_interval_seconds=float(modbus_raw.get("poll_interval_seconds", 0.2)),
        registers=registers,
    )

    commands = tuple(_load_command(item) for item in raw["commands"])
    model_path = Path(str(raw.get("vosk_model_path", "")))
    if not model_path.is_absolute():
        model_path = base_dir / model_path

    return AppConfig(
        input_mode=str(raw.get("input_mode", "vosk")),
        push_to_talk=bool(raw.get("push_to_talk", True)),
        record_seconds=float(raw.get("record_seconds", 2.0)),
        sample_rate=int(raw.get("sample_rate", 16000)),
        microphone_index=raw.get("microphone_index"),
        vosk_model_path=model_path,
        tts_enabled=bool(raw.get("tts_enabled", True)),
        modbus=modbus,
        commands=commands,
        base_dir=base_dir,
    )


def _load_command(item: dict[str, Any]) -> CommandConfig:
    return CommandConfig(
        intent=str(item["intent"]),
        command_id=int(item["command_id"]),
        name=str(item["name"]),
        phrases=tuple(str(p) for p in item["phrases"]),
        enabled=bool(item.get("enabled", True)),
    )
