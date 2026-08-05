# Competition Voice Controller

离线比赛用语音命令控制程序。它不修改上层目录里的原始程序，目标是用最小、稳定的流程完成：

```text
中文短语 -> 固定意图 -> Modbus TCP 写寄存器 -> PLC/视觉/机器人执行
```

## 设计原则

- 不使用 Whisper、Ollama 或联网服务。
- 程序启动一次后常驻运行，比赛任务二可以连续完成螺柱、平垫、螺母三次验收。
- 语音提示词放在 `config.json`，现场题目变化时只改配置。
- 零件编号沿用原程序：
  - 螺柱: `1`
  - 螺母: `2`
  - 平垫: `3`
  - 弹垫: `4`
  - 阀体/上球阀: `5`
- 任务三完整装配启动命令额外使用 `10`。

## 目录

```text
competition_voice/
  competition_voice/
    app.py
    config.py
    intent.py
    modbus_link.py
    voice.py
  scripts/
    setup_venv.sh
    run.sh
  config.json
  requirements.txt
```

## 安装依赖

必须使用虚拟环境，避免影响原系统：

```bash
cd competition_voice
bash scripts/setup_venv.sh
```

如果比赛现场不能联网，提前在可联网环境完成安装，并把整个 `competition_voice/.venv` 和 Vosk 中文小模型一起带到比赛电脑。

## Vosk 模型

推荐使用小中文模型，例如 `vosk-model-small-cn-*`。下载后放到：

```text
competition_voice/models/vosk-cn-small
```

然后在 `config.json` 里配置：

```json
"vosk_model_path": "models/vosk-cn-small"
```

没有模型时可以设置：

```json
"input_mode": "keyboard"
```

用于离线调试通信和 PLC 逻辑。

没有 PLC/机器人时，可以使用内置调试配置：

```bash
bash scripts/run.sh --config config.dry_run.json
```

它会使用键盘输入，并打印本该写入的 `command_id` 和 `seq`，不访问网络。

## 启动

```bash
cd competition_voice
bash scripts/run.sh
```

运行后程序会常驻。默认按 Enter 开始一次录音，识别一条命令，写入 PLC，然后继续等待下一条命令。

## Linux root 权限注意事项

本程序默认只作为 Modbus TCP client 主动连接 PLC 的 `502` 端口，不监听本机 `502` 端口，因此一般不需要 root。

需要 root 的典型情况是：程序要在本机启动 Modbus server 并绑定 `502` 这样的低端口。Linux 上绑定小于 `1024` 的端口通常需要 root 或 `CAP_NET_BIND_SERVICE` 权限。本项目不这么做。

如果必须本机开 Modbus server，建议改用 `1502` 这类高端口，或只给 Python 解释器授予绑定低端口能力。不要整场比赛直接用 root 跑机器人控制程序，避免误操作影响系统文件和设备权限。

## PLC 寄存器握手

默认寄存器为展示地址：

```text
40016 command_id
40017 seq
40018 ack_seq
40019 state
40020 error_code
```

程序写入：

```text
command_id = 命令编号
seq = 每次递增
```

PLC 回写：

```text
ack_seq = 已接收的 seq
state = 0 空闲, 1 运行中, 2 完成, 3 错误
error_code = 错误码
```

如果 PLC 暂时只支持旧方案，可以在 `config.json` 中设置：

```json
"wait_for_completion": false
```

程序会只写 `40016`，不强制等待 `ack/state`。
