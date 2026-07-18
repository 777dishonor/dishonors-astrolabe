# -*- coding: utf-8 -*-
"""horary-calc 预热脚本：提前加载星历 + 七库索引到系统文件缓存。

QClaw 每次重启后的第一次卜卦判读会慢（冷启动 I/O），本脚本提前把
pyswisseph 星历数据和七库索引文件都「摸」一遍，让操作系统把它们
缓存到内存。之后正式判读时所有 I/O 从内存走，速度接近热启动。

用法:
  python3 scripts/warmup.py
  python3 scripts/warmup.py --light   # 仅加载索引，不跑排盘（更快）
"""
import os, sys, time

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFS_DIR = os.path.join(SKILL_DIR, "references")
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")

# 七库索引文件列表
INDEX_FILES = [
    "_index.md",
    "_index_ca1.md", "_index_ca2.md", "_index_ca3.md",
    "_index_he.md", "_index_spirit.md",
    "_index_morin.md",
]

# 七库底本（大文件，可选预热）
REFERENCE_FILES = [
    "The Horary Textbook乾坤 6.0版.md",
    "基督占星第一册(Christian Astrology 1)选译.md",
    "基督占星第二册(Christian Astrology 2)选译.md",
    "基督占星第三册(Christian Astrology 3)选译.md",
    "Horary Examples翻译.md",
    "灵体攻击案例专题.md",
    "莫林本命占星方法.md",
]


def cache_file(path):
    """读取整个文件到内存，强迫操作系统缓存它。"""
    try:
        with open(path, "rb") as f:
            _ = f.read()
        return True
    except Exception:
        return False


def main():
    light = "--light" in sys.argv
    t0 = time.time()
    results = []

    # 1. 索引文件（小，全缓存）
    for fname in INDEX_FILES:
        fp = os.path.join(REFS_DIR, fname)
        ok = cache_file(fp)
        results.append(("索引", fname, ok))

    # 2. 底本文件（大，仅在非 light 模式下缓存）
    if not light:
        for fname in REFERENCE_FILES:
            fp = os.path.join(REFS_DIR, fname)
            ok = cache_file(fp)
            results.append(("底本", fname, ok))

    # 3. 跑一次排盘 + selfcheck，触发 pyswisseph 加载星历
    if not light:
        try:
            sys.path.insert(0, SCRIPTS_DIR)
            import subprocess
            # 跑一次本命盘（Placidus）+ 一次卜卦盘（Regiomontanus），
            # 确保两种星历路径都预热
            for mode, tz, city in [("--mode natal", "8", "北京"), ("", "8", "北京")]:
                cmd = [
                    sys.executable,
                    os.path.join(SCRIPTS_DIR, "cast_chart.py"),
                    "--time", "2026-01-01 12:00",
                    "--tz", tz,
                    "--city", city,
                ]
                if mode:
                    cmd.append(mode)
                subprocess.run(cmd, capture_output=True, timeout=30,
                               cwd=SCRIPTS_DIR)

            # 跑 selfcheck
            subprocess.run(
                [sys.executable, os.path.join(SCRIPTS_DIR, "selfcheck.py")],
                capture_output=True, timeout=10,
                cwd=SCRIPTS_DIR,
            )
            results.append(("排盘", "cast_chart + selfcheck", True))
        except Exception as e:
            results.append(("排盘", f"失败: {e}", False))

    elapsed = time.time() - t0
    ok_count = sum(1 for _, _, ok in results if ok)
    fail_count = len(results) - ok_count

    print(f"=== horary-calc 预热{'（轻量）' if light else ''}完成 ===")
    print(f"耗时: {elapsed:.1f}秒  |  缓存文件: {ok_count}/{len(results)}")
    if fail_count:
        print(f"⚠ 失败: {fail_count}")
    print()

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
