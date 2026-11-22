"""生成与参考图统计量接近的六轴脚本（用于对比配色/样式）。"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

OUT = Path(r"D:\AI自写软件\heatmapgen-ui\refs\reference_like")
NAME = "[Gerrry] 大凤Taiho Bunny Girl - Casino Chapter [碧蓝航线Azur lane]"
DURATION_MS = 880_000

# axis token -> (action count, max speed, burstiness)
AXES = (
    ("", 3150, 586, 0.55),
    (".surge", 188, 234, 0.25),
    (".sway", 150, 283, 0.2),
    (".twist", 766, 426, 0.5),
    (".roll", 950, 450, 0.5),
    (".pitch", 2433, 458, 0.6),
)

random.seed(20261123)


def build(count: int, target: float, burst: float):
    """Random walk whose segment speeds peak near ``target``."""
    actions, position = [], 50.0
    step = DURATION_MS / max(1, count)
    for index in range(count):
        at = int(index * step + random.uniform(-step * 0.3, step * 0.3))
        at = max(0, min(DURATION_MS, at))
        actions.append([at, int(round(position))])
        delta_t = max(16, int(step * random.uniform(0.5, 1.5)))
        # bursts: most segments slow, some reach the target speed
        if random.random() < burst:
            speed = target * random.uniform(0.45, 1.0)
        else:
            speed = target * random.uniform(0.01, 0.18)
        change = speed * delta_t / 1000.0
        if position + change > 100:
            position = 100 - (change - (100 - position))
        elif position - change < 0:
            position = -(position - change) if (position - change) > -100 else 0
        else:
            position += change * random.choice((-1, 1))
        position = max(0.0, min(100.0, position))
    actions.sort(key=lambda item: item[0])
    # 去重时间戳
    dedup, seen = [], set()
    for at, pos in actions:
        if at in seen:
            continue
        seen.add(at)
        dedup.append({"at": at, "pos": pos})
    return dedup


OUT.mkdir(parents=True, exist_ok=True)
for suffix, count, target, burst in AXES:
    actions = build(count, target, burst)
    data = {"version": "1.0", "inverted": False, "range": 100, "actions": actions,
            "metadata": {"title": NAME, "duration": DURATION_MS}}
    path = OUT / f"{NAME}{suffix}.funscript"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    speeds = [abs(b["pos"] - a["pos"]) * 1000 / (b["at"] - a["at"])
              for a, b in zip(actions, actions[1:]) if b["at"] > a["at"]]
    print(f"{suffix or '.l0':7s} {len(actions):5d} actions  max={max(speeds):6.0f}  "
          f"avg={sum(speeds)/len(speeds):6.1f}  -> {path.name}")
