from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from competition_voice.config import load_config
from competition_voice.intent import IntentParser


def main() -> int:
    parser = argparse.ArgumentParser(description="Check phrase to command_id mapping.")
    parser.add_argument("--config", default=str(ROOT / "config.json"))
    args = parser.parse_args()

    config = load_config(args.config)
    parser_ = IntentParser(config.commands)
    failed = False

    for command in config.commands:
        if not command.enabled:
            continue
        for phrase in command.phrases:
            match = parser_.parse(phrase)
            if match is None or match.command_id != command.command_id:
                failed = True
                print(f"FAIL {phrase}: expected {command.command_id}, got {match}")
            else:
                print(f"OK   {phrase} -> {match.command_id} ({match.intent})")

    fallback_cases = {
        "螺丝": 1,
        "抓螺丝": 1,
        "螺帽": 2,
        "拿螺帽": 2,
        "垫片": 3,
        "拿垫片": 3,
        "阀体": 5,
        "球阀装配": 10,
    }
    for text, expected_id in fallback_cases.items():
        match = parser_.parse(text)
        if match is None or match.command_id != expected_id:
            failed = True
            print(f"FAIL fallback {text}: expected {expected_id}, got {match}")
        else:
            print(f"OK   fallback {text} -> {match.command_id} ({match.intent})")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
