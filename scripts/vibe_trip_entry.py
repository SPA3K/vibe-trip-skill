#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vibe-trip-skill · cron 入口包装（纯标准库）

为什么存在：Hermes 的 no_agent cron 在 Windows 上没有 bash（.sh 直接报
bash not found），而默认 PATH 的 python 没装 playwright。本入口用标准库
把真正的监控脚本转交给带 playwright 的 Python（如 miniconda），并透传 stdout ——
静默契约不变：监控无输出 = 本入口无输出 = 静默。

可用环境变量覆盖解释器：
  VIBE_TRIP_PYTHON  指定 Python 全路径（优先级最高）
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "vibe_trip_monitor.py")

CANDIDATES = [
    os.environ.get("VIBE_TRIP_PYTHON"),
    os.path.expanduser(r"~\miniconda3\python.exe"),
    os.path.expanduser(r"~\anaconda3\python.exe"),
    os.path.expanduser(r"~\miniconda3\Scripts\python.exe"),
    "python",
]


def pick_python():
    for c in CANDIDATES:
        if not c:
            continue
        if c == "python" or os.path.exists(c):
            return c
    return "python"


def main():
    py = pick_python()
    # 先验证目标解释器真的有 playwright，没有就顺延下一个候选
    for c in CANDIDATES:
        if not c or (c != "python" and not os.path.exists(c)):
            continue
        try:
            r = subprocess.run([c, "-c", "import playwright"],
                               capture_output=True, timeout=30)
            if r.returncode == 0:
                py = c
                break
        except Exception:
            continue
    cmd = [py, TARGET] + sys.argv[1:]
    try:
        proc = subprocess.run(cmd, timeout=1500)
        sys.exit(proc.returncode)
    except subprocess.TimeoutExpired:
        print("⚠️ vibe-trip monitor timeout (>25min)")
        sys.exit(0)
    except Exception as e:
        print(f"⚠️ vibe-trip entry failed: {str(e)[:160]}")
        sys.exit(0)


if __name__ == "__main__":
    main()
