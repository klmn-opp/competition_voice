from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import socket
import time
from typing import Any

from .config import ModbusConfig


STATE_IDLE = 0
STATE_RUNNING = 1
STATE_DONE = 2
STATE_ERROR = 3


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    message: str
    seq: int
    state: int | None = None
    error_code: int | None = None


class ModbusCommandLink:
    def __init__(self, config: ModbusConfig):
        self.config = config
        self._client: Any | None = None
        self._bound_socket: socket.socket | None = None
        self._send_count = 0
        self._connect_attempts = 3

    def connect(self) -> bool:
        if self.config.dry_run:
            print("[Modbus] dry_run=true，不连接 PLC")
            return True

        self.close()
        last_error = None
        for attempt in range(1, self._connect_attempts + 1):
            try:
                client, bind_ip, bind_source = self._connect_once()
                self._client = client
                if bind_ip:
                    print(
                        f"[Modbus] 已连接 {self.config.host}:{self.config.port} "
                        f"(bind {bind_ip}, {bind_source})"
                    )
                else:
                    print(f"[Modbus] 已连接 {self.config.host}:{self.config.port}")
                return True
            except Exception as exc:
                last_error = self._format_connect_error(exc)
                print(f"[Modbus] 连接尝试 {attempt}/{self._connect_attempts} 失败: {last_error}")
                self.close()
                if attempt < self._connect_attempts:
                    time.sleep(0.5 * attempt)
        print(f"[Modbus] 连接失败，已重试 {self._connect_attempts} 次: {last_error}")
        return False

    def _connect_once(self) -> tuple[Any, str | None, str | None]:
        from pyModbusTCP.client import ModbusClient

        bind_candidates: list[tuple[str, str]] = []
        if self.config.local_bind_ip:
            bind_candidates.append((self.config.local_bind_ip, "config"))
        else:
            detected = self._detect_local_bind_ip()
            if detected:
                bind_candidates.append((detected, "auto"))

        last_error: Exception | None = None
        for bind_ip, source in (*bind_candidates, (None, None)):
            try:
                if bind_ip is not None:
                    client = self._connect_with_bind(ModbusClient, bind_ip)
                    return client, bind_ip, source
                client = ModbusClient(
                    host=self.config.host,
                    port=self.config.port,
                    unit_id=self.config.unit_id,
                    auto_open=True,
                    auto_close=False,
                    timeout=self.config.timeout_seconds,
                )
                if not client.open():
                    last_error_txt = client.last_error_as_txt or "Modbus open() 返回失败"
                    raise RuntimeError(last_error_txt)
                return client, None, None
            except Exception as exc:
                last_error = exc
                if bind_ip is not None:
                    print(
                        f"[Modbus] 绑定本机 {bind_ip} 连接失败，"
                        f"准备尝试其他方式: {self._format_connect_error(exc)}"
                    )
                continue

        raise RuntimeError(self._format_connect_error(last_error or RuntimeError("Modbus connect failed")))

    def _connect_with_bind(self, client_cls: Any, bind_ip: str) -> Any:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((bind_ip, 0))
            sock.settimeout(self.config.timeout_seconds)
            sock.connect((self.config.host, self.config.port))
            client = client_cls(
                host=self.config.host,
                port=self.config.port,
                unit_id=self.config.unit_id,
                auto_open=False,
                auto_close=False,
                timeout=self.config.timeout_seconds,
            )
            client._sock = sock
            client._is_open = True
            self._bound_socket = sock
            return client
        except Exception:
            try:
                sock.close()
            except Exception:
                pass
            raise

    def _detect_local_bind_ip(self) -> str | None:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.settimeout(self.config.timeout_seconds)
            probe.connect((self.config.host, self.config.port))
            local_ip = probe.getsockname()[0]
            ipaddress.ip_address(local_ip)
            if local_ip.startswith("127."):
                return None
            print(f"[Modbus] 自动检测到本机出站 IPv4: {local_ip}")
            return local_ip
        except Exception as exc:
            print(f"[Modbus] 自动检测本机 IPv4 失败，改用系统默认路由: {exc}")
            return None
        finally:
            try:
                probe.close()
            except Exception:
                pass

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
        if self._bound_socket is not None:
            try:
                self._bound_socket.close()
            except Exception:
                pass
        self._client = None
        self._bound_socket = None

    def send_command(self, command_id: int) -> CommandResult:
        if self.config.dry_run:
            self._send_count += 1
            print(
                f"[Modbus] dry_run 写入 {self.config.registers.command_status}={command_id}, "
                f"count={self._send_count}"
            )
            return CommandResult(True, "dry_run 命令已模拟写入", self._send_count, STATE_DONE)

        if self._client is None and not self.connect():
            return CommandResult(False, "无法连接 PLC/机器人 Modbus 服务", self._send_count)

        self._send_count += 1
        send_count = self._send_count

        if not self._write_register(self.config.registers.command_status, command_id):
            if self._reconnect_once():
                return self._send_after_reconnect(command_id, send_count)
            return CommandResult(False, "写入命令寄存器失败", send_count)

        if not self.config.wait_for_completion:
            return CommandResult(True, "命令已写入", send_count)

        return self._wait_for_single_register(command_id, send_count)

    def _send_after_reconnect(self, command_id: int, send_count: int) -> CommandResult:
        if not self._write_register(self.config.registers.command_status, command_id):
            return CommandResult(False, "重连后写入命令寄存器失败", send_count)
        if not self.config.wait_for_completion:
            return CommandResult(True, "命令已写入", send_count)
        return self._wait_for_single_register(command_id, send_count)

    def _wait_for_single_register(self, command_id: int, send_count: int) -> CommandResult:
        deadline = time.time() + self.config.done_timeout_seconds
        while time.time() < deadline:
            value = self._read_register(self.config.registers.command_status)

            if value is None:
                time.sleep(self.config.poll_interval_seconds)
                continue

            if value >= self.config.error_min_value:
                return CommandResult(False, "PLC/机器人返回错误状态", send_count, STATE_ERROR, value)

            if self._is_done_value(value, command_id):
                return CommandResult(True, "执行完成", send_count, STATE_DONE)

            time.sleep(self.config.poll_interval_seconds)

        return CommandResult(False, "等待执行完成超时", send_count)

    def _is_done_value(self, value: int, command_id: int) -> bool:
        mode = self.config.completion_mode
        if mode == "cleared_to_zero":
            return value == 0
        if mode == "fixed_done_value":
            return value == self.config.done_value
        if mode == "done_offset_100":
            return value == command_id + 100
        raise RuntimeError(f"不支持的 completion_mode: {mode}")

    def _write_register(self, display_addr: int, value: int) -> bool:
        client = self._client
        if client is None:
            return False
        try:
            ok = bool(client.write_single_register(_holding_offset(display_addr), value))
            if not ok:
                print(
                    f"[Modbus] 写寄存器 {display_addr} 失败: "
                    f"{client.last_error_as_txt or client.last_except_as_txt or 'unknown'}"
                )
            return ok
        except Exception as exc:
            print(f"[Modbus] 写寄存器 {display_addr} 异常: {self._format_connect_error(exc)}")
            return False

    def _read_register(self, display_addr: int) -> int | None:
        client = self._client
        if client is None:
            return None
        try:
            values = client.read_holding_registers(_holding_offset(display_addr), 1)
            if values:
                return int(values[0])
        except Exception as exc:
            print(f"[Modbus] 读寄存器 {display_addr} 异常: {self._format_connect_error(exc)}")
        return None

    def _reconnect_once(self) -> bool:
        if not self.config.auto_reconnect:
            return False
        print("[Modbus] 尝试重连...")
        return self.connect()

    def _format_connect_error(self, exc: Exception) -> str:
        client = self._client
        if client is not None:
            parts = [
                client.last_error_as_txt or "",
                client.last_except_as_txt or "",
                client.last_except_as_full_txt or "",
            ]
            parts = [part for part in parts if part]
            if parts:
                return " | ".join(parts)
        return str(exc)


def _holding_offset(display_addr: int) -> int:
    if display_addr < 40001:
        return display_addr
    return display_addr - 40001
