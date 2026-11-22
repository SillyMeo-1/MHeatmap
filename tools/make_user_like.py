"""生成与用户实际脚本统计量接近的六轴素材（3:56，含稀疏/爆发段）。"""
from __future__ import annotations

import json
import random
from pathlib import Path

OUT = Path(r"D:\AI自写软件\heatmapgen-ui\refs\user_like")
NAME = "[LikeHugeB] Sex大乱斗照進现实 IN REALITY Evanescia Remielle Dan Raiden Mei"
DURATION_MS = 236_000

# suffix, actions, max speed, avg speed, burst probability
AXES = (
    ("", 2395, 604, 239, 0.55),
    (".surge", 240, 309, 98, 0.30),
    (".sway", 149, 361, 122, 0.30),
    (".twist", 169, 343, 144, 0.35),
    (".roll", 1026, 341, 110, 0.40),
    (".pitch", 2062, 489, 94, 0.30),
)

random.seed(20261124)


def build(count: int, max_speed: float, avg_speed: float, burst: float):
    actions = []
    position = 50.0
    step = DURATION_MS / count
    for index in range(count):
        at = int(round(index * step))
        actions.append({"at": min(DURATION_MS, at), "pos": int(round(max(0, min(100, position))))})
        delta_t = max(16, int(round(step * random.uniform(0.8, 1.2))))
        if random.random() < burst:
            speed = max_speed * random.uniform(0.55, 1.0)
        else:
            speed = avg_speed * random.uniform(0.25, 0.9)
        delta = speed * delta_t / 1000.0
        if delta > 45:
            delta = 45
        direction = 1 if position < 50 else -1
        if position + direction * delta > 100 or position + direction * delta < 0:
            direction = -direction
        position = max(0.0, min(100.0, position + direction * delta))
    return actions


OUT.mkdir(parents=True, exist_ok=True)
for suffix, count, max_speed, avg_speed, burst in AXES:
    actions = build(count, max_speed, avg_speed, burst)
    data = {"version": "1.0", "inverted": False, "range": 100, "actions": actions,
            "metadata": {"title": NAME, "duration": DURATION_MS}}
    path = OUT / f"{NAME}{suffix}.funscript"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    speeds = [abs(b["pos"] - a["pos"]) * 1000 / (b["at"] - a["at"]) for a, b in zip(actions, actions[1:]) if b["at"] > a["at"]]
    print(f"{suffix or '.l0':7s} {len(actions):5d} actions  max={max(speeds):6.0f}  "
          f"avg={sum(speeds)/len(speeds):6.1f}")
