# Competition Voice Controller

离线比赛用语音命令控制程序。它不修改上层目录里的原始程序，目标是用最小、稳定的流程完成：

```text
中文短语 -> 固定意图 -> Modbus TCP 写寄存器 -> PLC/视觉/机器人执行
```

## 设计原则

- 不使用 Whisper、Ollama 或联网服务。
- 程序启动一次后常驻运行，比赛任务二可以连续完成螺柱、平垫、螺母三次验收。
- 语音提示词放在 `prompt.md`，现场题目变化时只改这个文件。
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
  prompt.md
  requirements.txt
```

## 安装依赖

必须使用虚拟环境，避免影响原系统：

```bash
cd competition_voice
bash scripts/setup_venv.sh
```

如果比赛现场不能联网，提前在可联网环境完成安装，并把整个 `competition_voice/.venv` 和 `models/sherpa/` 一起带到比赛电脑。

## 提示词修改

只改 `prompt.md`，不要改主程序。格式如下：

```text
PICK_STUD: 识别螺柱, 抓取螺柱, 安装螺柱, 识别螺丝, 抓取螺丝
PICK_NUT: 识别螺母, 抓取螺母, 安装螺帽, 抓取螺帽
PICK_WASHER: 识别平垫, 抓取平垫, 识别垫片, 抓取垫片
START_ASSEMBLY: 启动装配, 开始球阀装配, 执行总流程
STOP: 停止, 退出, 结束任务
```

程序还带关键词兜底，即使只识别到 `螺丝`、`螺帽`、`垫片`、`阀体` 这类核心词，也会尽量映射到对应动作。

## 语音模型

正式和测试都默认使用本地 `sherpa-onnx + Silero VAD` 常驻识别链路：

```text
models/sherpa/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17
models/sherpa/silero_vad.onnx
```

对应配置：

```json
"input_mode": "sherpa",
"sherpa_language": "zh"
```

`sherpa_language` 建议固定为 `zh`，避免中文被识别成日文或韩文。

如果要回退到 Vosk，可把 `input_mode` 改回 `vosk`，再放置本地 Vosk 模型。

没连接 PLC 但要测试语音功能，使用：

```bash
cd /home/klmn/gongye_yuyin/competition_voice
bash scripts/run.sh --config config.voice_test.json
```

这个配置仍然调用麦克风和本地 sherpa 模型，但 `dry_run=true`，不会连接 PLC，只打印本该写入 `40016` 的值。

## 麦克风

默认配置：

```json
"microphone_index": null
```

表示使用系统默认输入设备。一般建议先保持 `null`。

如果识别不到声音，列出本机麦克风：

```bash
cd /home/klmn/gongye_yuyin/competition_voice
bash scripts/list_mics.sh
```

找到正确的输入设备编号后，改 `config.json` 或 `config.voice_test.json`：

```json
"microphone_index": 0
```

程序录音参数默认是 `16000Hz`、单声道、持续监听。说完一句后由 VAD 切段，再送入本地识别。

没有 PLC/机器人时，可以使用内置调试配置：

```bash
bash scripts/run.sh --config config.dry_run.json
```

它会使用键盘输入，并打印本该写入的 `command_id` 和 `seq`，不访问网络。

## 启动方式

```bash
cd competition_voice
bash scripts/run.sh
```

运行后程序会常驻，直接说话即可。识别一条命令，写入 PLC，然后继续等待下一条命令。

完整首次启动流程：

```bash
cd /home/klmn/gongye_yuyin/competition_voice
bash scripts/setup_venv.sh
bash scripts/run.sh
```

如果已经安装过依赖，之后只需要：

```bash
cd /home/klmn/gongye_yuyin/competition_voice
bash scripts/run.sh
```

没有语音模型、没有 PLC 时，先用键盘 dry-run 验证：

```bash
cd /home/klmn/gongye_yuyin/competition_voice
python3 -m competition_voice.app --config config.dry_run.json
```

## Linux root 权限注意事项

本程序默认只作为 Modbus TCP client 主动连接 PLC 的 `502` 端口，不监听本机 `502` 端口，因此一般不需要 root。

需要 root 的典型情况是：程序要在本机启动 Modbus server 并绑定 `502` 这样的低端口。Linux 上绑定小于 `1024` 的端口通常需要 root 或 `CAP_NET_BIND_SERVICE` 权限。本项目不这么做。

如果必须本机开 Modbus server，建议改用 `1502` 这类高端口，或只给 Python 解释器授予绑定低端口能力。不要整场比赛直接用 root 跑机器人控制程序，避免误操作影响系统文件和设备权限。

## 单寄存器协议

当前按比赛现场限制，只使用一个寄存器，默认展示地址为：

```text
40016 command_status
```

PC 识别到语音命令后写入：

```text
1  = 螺柱
2  = 螺母
3  = 平垫
4  = 弹垫
5  = 阀体/上球阀
10 = 完整装配流程
99 = 停止
```

默认完成方式为 `cleared_to_zero`：

```text
PLC/机器人检测到 40016 非 0 -> 读取动作编号并执行
PLC/机器人执行中可以保持原动作编号
PLC/机器人执行完成后写 40016 = 0
PC 连续轮询读到 0 -> 判定完成并播报
```

也支持其他单寄存器完成编码，在 `config.json` 里改：

```json
"completion_mode": "fixed_done_value",
"done_value": 100
```

表示 PLC 完成后统一写 `100`。

或者：

```json
"completion_mode": "done_offset_100"
```

表示 PLC 完成后写 `100 + command_id`，例如螺柱完成写 `101`。

如果 PLC 侧暂时不会回写完成状态，可以设置：

```json
"wait_for_completion": false
```

程序会只写 `40016`，不等待完成。
