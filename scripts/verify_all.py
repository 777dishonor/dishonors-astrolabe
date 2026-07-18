# -*- coding: utf-8 -*-
"""dishonors-astrolabe 全链路验证：四库索引 + 排盘 + 报告生成 + 宫位制确认。"""
import os, sys, subprocess, re

SK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(SK, "references")
SCR = os.path.join(SK, "scripts")
out = []

def run(py, *args):
    r = subprocess.run([sys.executable, os.path.join(SCR, py)] + list(args),
                       capture_output=True, text=True, cwd=SCR, timeout=120)
    return r.returncode, r.stdout.strip(), r.stderr.strip()

# 1. 四库索引重建（catch 报错）
out.append("=== 1. 索引重建 ===")
rc, so, se = run("build_index.py")
out.append("6.0版 build_index: rc=%d %s" % (rc, "OK" if rc == 0 else "ERR: " + se[:200]))
for fn, tag in [("基督占星第一册(Christian Astrology 1)选译.md","ca1"),
                ("基督占星第二册(Christian Astrology 2)选译.md","ca2"),
                ("基督占星第三册(Christian Astrology 3)选译.md","ca3")]:
    rc, so, se = run("build_index_multi.py", fn, tag)
    out.append("%s: rc=%d %s" % (tag, rc, "OK" if rc==0 else "ERR: "+se[:200]))

# 索引文件存在性 + 大小
out.append("--- 索引文件 ---")
for f in ["_index.md","_index_ca1.md","_index_ca2.md","_index_ca3.md"]:
    p = os.path.join(REF, f)
    out.append("  %s: %s (%d字节)" % (f, "存在" if os.path.exists(p) else "缺失", os.path.getsize(p) if os.path.exists(p) else 0))

# 2. 排盘引擎（用厦门时间）
out.append("")
out.append("=== 2. 排盘引擎 ===")
rc, so, se = run("cast_chart.py", "--time", "2026-07-10 03:14", "--tz", "8", "--city", "厦门")
ok = rc == 0 and "ASC" in so and "Regiomontanus" in so
out.append("cast_chart 厦门: rc=%d %s" % (rc, "OK" if ok else "ERR: "+se[:200]))
# 抓 ASC 与宫位制行
for line in so.splitlines():
    if "宫位制" in line or line.strip().startswith("ASC"):
        out.append("   " + line.strip())

# 3. 报告生成器（多底本引用）
out.append("")
out.append("=== 3. 报告生成器（多底本）===")
chart = os.path.join(REF, "..", "scripts", "x.txt")  # 占位，实际用工作区 chart
chart = r"C:\Users\WH\.qclaw\workspace-agent-cacd0e12\refs\horary\case_insomnia_chart.txt"
if not os.path.exists(chart):
    chart = so  # fallback: 不读文件当字符串
rc, so, se = run("gen_report.py",
    "--title", "验证报告", "--time", "2026-07-11 01:05", "--tz", "8", "--place", "厦门",
    "--question", "验证", "--chart", chart,
    "--verdict", "验证多底本渲染",
    "--cite1", "6 和 8 宫的问题|段落5（原文行4704-4704）|The significator of the illness will be whichever planet is harming Lord 1",
    "--cite2", "基督占星第二册(Christian Astrology 2)选译|第三章 判断总论|段落37（原文行35-35）|象征星在吉宫",
    "--out", r"C:\Users\WH\.qclaw\workspace-agent-cacd0e12\refs\horary\_verify_report.md")
out.append("gen_report: rc=%d %s" % (rc, "OK" if rc==0 else "ERR: "+se[:300]))

# 4. 宫位制确认：源码里 hsys 默认值
out.append("")
out.append("=== 4. 宫位制硬编码确认 ===")
src = open(os.path.join(SCR, "cast_chart.py"), encoding="utf-8").read()
m = re.search(r'hsys[^\n]*=\s*b?[\'"][^\'"]*[\'"]', src)
out.append("cast_chart.py 中 hsys 默认: %s" % (m.group(0) if m else "未找到"))
out.append("是否出现其他宫位制关键字(Placidus/Koch/Porphyrius等): %s" % (
    "是!!!" if re.search(r'Placidus|Koch|Porphyrius|Campanus|Equal', src) else "否（仅 Regiomontanus）"))

# 5. selfcheck
out.append("")
out.append("=== 5. 自检 ===")
rc, so, se = run("selfcheck.py")
out.append(so)
out.append("selfcheck rc=%d" % rc)

open(r"C:\Users\WH\.qclaw\workspace-agent-cacd0e12\refs\horary\_verify_all.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
