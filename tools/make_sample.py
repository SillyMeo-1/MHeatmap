"""Write a small six-axis sample set (for the self test / CI).

    py -3 tools/make_sample.py [out_dir]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "build/sample")
NAME = "demo"
DURATION_MS = 90_000
AXES = (("", 0.55), (".surge", 0.10), (".sway", 0.08), (".twist", 0.30),
        (".roll", 0.35), (".pitch", 0.45))


def build(frequency: float):
    actions, step = [], 40
    for index in range(0, DURATION_MS // step):
        at = index * step
        pos = 50 + 44 * math.sin(2 * math.pi * frequency * at / 1000.0)
        actions.append({"at": at, "pos": int(max(0, min(100, round(pos))))})
    return actions


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for suffix, frequency in AXES:
        path = OUT / f"{NAME}{suffix}.funscript"
        data = {"version": "1.0", "inverted": False, "range": 100,
                "actions": build(frequency),
                "metadata": {"title": "MHeatmap demo", "duration": DURATION_MS}}
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {path} ({len(data['actions'])} actions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
