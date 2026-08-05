from __future__ import annotations


def main() -> int:
    try:
        import sounddevice as sd
    except ImportError:
        print("缺少 sounddevice。请先运行: bash scripts/setup_venv.sh")
        return 1

    devices = sd.query_devices()
    default_input = sd.default.device[0]
    print(f"默认输入设备 index: {default_input}")
    print()
    for index, device in enumerate(devices):
        channels = int(device.get("max_input_channels", 0))
        if channels <= 0:
            continue
        name = device.get("name", "")
        samplerate = device.get("default_samplerate", "")
        marker = " <- default" if index == default_input else ""
        print(f"{index}: {name} | input_channels={channels} | default_samplerate={samplerate}{marker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
