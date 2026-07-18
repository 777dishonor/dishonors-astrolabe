# -*- coding: utf-8 -*-
"""dishonors-astrolabe 自包含性自检：确认底本/索引/依赖均就位且可用。"""
import os, sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = []

def check(cond, msg):
    out.append(("OK " if cond else "FAIL") + " " + msg)
    return cond

# 1. 底本
base = os.path.join(SKILL, "references", "The Horary Textbook乾坤 6.0版.md")
ok1 = check(os.path.exists(base) and os.path.getsize(base) > 1000000, "底本存在 (>1MB): %s" % base)
# 2. 索引
idx = os.path.join(SKILL, "references", "_index.md")
ok2 = check(os.path.exists(idx) and os.path.getsize(idx) > 100000, "索引存在: %s" % idx)
# 2b. 六库索引齐全
for tag in ["_index.md", "_index_ca1.md", "_index_ca2.md", "_index_ca3.md",
            "_index_he.md", "_index_spirit.md"]:
    p = os.path.join(SKILL, "references", tag)
    check(os.path.exists(p) and os.path.getsize(p) > 1000, "索引存在: %s" % tag)
# 3. 依赖
try:
    import swisseph
    out.append("OK  pyswisseph 已安装: %s" % getattr(swisseph, "__version__", "?"))
    ok3 = True
except Exception as e:
    out.append("FAIL pyswisseph 未安装: %r" % e)
    ok3 = False
# 4. 排盘可跑
if ok3:
    try:
        import subprocess, sys as _sys
        r = subprocess.run([_sys.executable, os.path.join(SKILL, "scripts", "cast_chart.py"),
                             "--time", "2026-07-10 03:14", "--tz", "8", "--city", "厦门"],
                            capture_output=True, text=True, timeout=60)
        ok4 = check(r.returncode == 0 and "ASC" in r.stdout, "排盘脚本可运行")
    except Exception as e:
        out.append("FAIL 排盘运行异常: %r" % e)
        ok4 = False
# 5. 索引里能查到关键章节
if ok2:
    txt = open(idx, encoding="utf-8").read()
    for kw in ["6 和 8 宫的问题", "核心法则", "应期"]:
        out.append(("OK " if kw in txt else "FAIL") + " 索引含章节: " + kw)
# 5b. 新案例库索引含关键内容
he = os.path.join(SKILL, "references", "_index_he.md")
sp = os.path.join(SKILL, "references", "_index_spirit.md")
if os.path.exists(he):
    ht = open(he, encoding="utf-8").read()
    out.append(("OK " if ("案例" in ht or "Example" in ht) else "FAIL") + " 索引含案例: Horary Examples")
if os.path.exists(sp):
    st = open(sp, encoding="utf-8").read()
    out.append(("OK " if ("灵体" in st or "巫术" in st or "12" in st) else "FAIL") + " 索引含专题: 灵体攻击")
# 5c. 莫林本命书
morin_idx = os.path.join(SKILL, "references", "_index_morin.md")
if os.path.exists(morin_idx):
    mt = open(morin_idx, encoding="utf-8").read()
    out.append(("OK " if ("第一章" in mt or "天球" in mt) else "FAIL") + " 索引含: 莫林本命占星方法")
# 5d. 六库+莫林底本存在
for fname in ["莫林本命占星方法.md"]:
    p = os.path.join(SKILL, "references", fname)
    check(os.path.exists(p) and os.path.getsize(p) > 10000, "底本存在: %s" % fname)

with open(os.path.join(SKILL, "scripts", "_selfcheck.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
print("\n".join(out))
print("\n总体:", "通过" if all([ok1, ok2, ok3, ok4]) else "有失败项")
