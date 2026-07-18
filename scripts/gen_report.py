# -*- coding: utf-8 -*-
"""
卜卦判读报告生成器：套用 TEMPLATE.md，产出标准化 md。
用法:
  python3 gen_report.py --title "丢猫" --time "2024-01-01 12:00" --tz 8 --place "北京" \
      --chart chart.txt --verdict "结论..." \
      --cite1 "章节A|行X-Y|原文摘引" \
      --cite2 "章节B|行X-Y|原文摘引" \
      --out report.md
任意 cite 可省略（留空则不写该行）。
"""
import sys, argparse, os

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(SKILL_DIR, "TEMPLATE.md")

def load_template():
    """单一真相源：直接读 TEMPLATE.md，避免内嵌副本与文件不同步。"""
    try:
        with open(TEMPLATE_PATH, encoding="utf-8") as f:
            return f.read()
    except Exception:
        # 兜底内嵌（与 TEMPLATE.md 保持一致）
        return r"""# 🔮 卜卦判读 · {title}

> ⚠️ 判读前已行祈祷。自检通过。

| | |
|---|---|
| **提问时间** | {time}（UTC{tz}） |
| **地点** | {place} |
| **问卜人问题** | *{question}* |
| **宫位制** | Regiomontanus |
| **资料库** | 七库（Frawley 6.0 + 李利 CA1/CA2/CA3 + Horary Examples + 灵体专题 + 莫林本命） |
| **排盘引擎** | dishonors-astrolabe / pyswisseph（Swiss Ephemeris） |

---

## ⚖️ 一、我的判断

{verdict}

---

## 📊 二、星盘数据

{chart}

---

## 🏛️ 三、判断依据

> 每一条论断均可溯源至底本原文。若文档未载，必明说「文档未载」，绝不编造引文与行号。

{{cites}}

---

## 📜 四、诚实声明

- 底本明言：「YOU ARE ALLOWED TO BE WRONG —— 你是容许犯错的」。本判读按书章法推演，不为天意打包票。
- 凡底本未载之处，明说「文档未载」，绝不编造引文与行号。
"""

TEMPLATE = load_template()


def parse_cite(s):
    """book|sect|loc|quote -> (book, sect, loc, quote)
    必须显式带底本名 book（七库之一），不允许省略——这是"七库平等"的硬约束：
    省略底本会系统性偏重某一库，故此处强制报错而非静默默认。
    loc 形如 '段落2（原文行3673-3673）'，直接来自对应 _index*.md。
    """
    if not s:
        return None
    parts = s.split("|", 3)
    if len(parts) >= 4:
        book, sect, loc, quote = (p.strip() for p in parts)
        if not book or not sect or not loc or not quote:
            print("cite 格式错误（四段都必填且不得为空）: %r" % s); sys.exit(2)
        return book, sect, loc, quote
    print("cite 必须含底本名，格式: 底本|章节|段落（行X-Y）|摘引 -> %r" % s)
    sys.exit(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--time", required=True)
    ap.add_argument("--tz", required=True)
    ap.add_argument("--place", required=True)
    ap.add_argument("--question", required=False, default="（未提供）", help="问卜人的问题原文，附在元信息区便于复查复盘")
    ap.add_argument("--chart", required=True, help="星盘文本文件或字符串")
    ap.add_argument("--verdict", required=False, default="")
    ap.add_argument("--verdict-file", default="", help="从文件读取 verdict，避免 shell 多行引号问题")
    for i in range(1, 6):
        ap.add_argument("--cite%d" % i, default="")
    ap.add_argument("--out", required=False, default="",
                    help="输出 md 路径；留空则按『提问时间+问题概括』自动命名")
    args = ap.parse_args()
    verdict = args.verdict
    if args.verdict_file:
        try:
            with open(args.verdict_file, "r", encoding="utf-8") as f:
                verdict = f.read().strip()
        except Exception as e:
            print("读取 verdict-file 失败: %r" % e); sys.exit(3)

    # chart: 若是文件则读，否则当字符串
    chart = args.chart
    try:
        with open(args.chart, "r", encoding="utf-8") as f:
            chart = f.read().strip()
    except Exception:
        pass

    cites_lines = []
    for i in range(1, 6):
        c = parse_cite(getattr(args, "cite%d" % i))
        if c:
            book, sect, loc, quote = c
            cites_lines.append(
                "%d. **%s**：【出处】《%s》「%s」%s：「%s」"
                % (len(cites_lines) + 1, sect, book, sect, loc, quote)
            )
    cites = "\n".join(cites_lines) if cites_lines else "（本案未引用具体章节，或文档未载）"

    # 输出文件名：留空则按『提问时间+问题概括』自动命名
    out_path = args.out
    if not out_path:
        import re as _re
        t = args.time.replace(":", "-").replace(" ", "_")
        ti = _re.sub(r"[\\/:*?\"<>|]", "", t)
        ti = ti.strip().strip("_")
        tt = _re.sub(r"[\\/:*?\"<>|]", "", args.title).strip()
        out_path = "%s_%s.md" % (ti, tt)

    md = TEMPLATE
    for key, val in [
        ("title", args.title), ("time", args.time), ("tz", args.tz),
        ("place", args.place), ("question", args.question), ("chart", chart),
        ("verdict", verdict), ("cites", cites),
    ]:
        md = md.replace("{%s}" % key, str(val))
    # 兜底：残留未替换占位符清空，避免泄露模板变量名
    import re as _re
    md = _re.sub(r"\{[a-z]+\}", "", md)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print("[已生成报告] %s (%d 字节)" % (out_path, len(md.encode("utf-8"))))


if __name__ == "__main__":
    main()
