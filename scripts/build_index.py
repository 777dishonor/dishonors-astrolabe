# -*- coding: utf-8 -*-
"""索引构建器（随 skill 发布）：基于 references/ 内的底本生成 _index.md。
解析 md 标题层级，将每个标题下的自然段顺编段落号，记录每段原文行号区间与段首预览。
用法: python3 build_index.py
"""
import sys, os, re

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(SKILL, "references", "The Horary Textbook乾坤 6.0版.md")
OUTDIR = os.path.join(SKILL, "references")

if not os.path.exists(SRC):
    print("底本不存在: %s" % SRC); sys.exit(1)

os.makedirs(OUTDIR, exist_ok=True)
fname = os.path.basename(SRC)
dest_base = os.path.join(OUTDIR, fname)
# 字节级复制底本（先读内存再写回，避免 SRC 与 dest 同名时先清空后读导致 0 字节）
with open(SRC, "rb") as fsrc:
    _raw = fsrc.read()
with open(dest_base, "wb") as fdst:
    fdst.write(_raw)

with open(SRC, "r", encoding="utf-8") as f:
    content = f.read()
lines = content.split("\n")
lines = [ln.rstrip("\r") for ln in lines]
total = len(lines)

out = []
heading_count = 0
para_total = 0
current_title = "(文件开头/无标题)"
para_count = 0
in_para = False
para_start = 0
para_text = []

def emit(title, num, start, end, txt):
    global para_total
    text = "\n".join(txt).strip()
    preview = text[:60] + ("..." if len(text) > 60 else "")
    preview = preview.replace("\n", " ").replace("\r", " ")
    out.append("  - 段落 %d（原文行 %d-%d）：%s" % (num, start, end, preview))
    para_total += 1

i = 0
while i < total:
    line = lines[i]
    hm = re.match(r"^(#{1,6})\s+(.*)$", line)
    if hm:
        if in_para:
            emit(current_title, para_count, para_start, i, para_text)
            in_para = False; para_text = []
        level = len(hm.group(1))
        title = hm.group(2).strip()
        heading_count += 1
        indent = "  " * level
        out.append("")
        out.append(indent + "# " + title)
        current_title = title
        para_count = 0
    else:
        if line.strip() == "":
            if in_para:
                emit(current_title, para_count, para_start, i, para_text)
                in_para = False; para_text = []
        else:
            if not in_para:
                in_para = True
                para_start = i + 1
                para_text = [line]
            else:
                para_text.append(line)
    i += 1
if in_para:
    emit(current_title, para_count, para_start, total, para_text)

idx_path = os.path.join(OUTDIR, "_index.md")
header = (
    "# 卜卦底本索引\n\n"
    "- 底本文件：%s\n" % fname +
    "- 底本路径：%s\n" % dest_base +
    "- 总行数：%d\n" % total +
    "- 标题数：%d\n" % heading_count +
    "- 段落总数：%d\n\n" % para_total +
    "---\n\n"
)
with open(idx_path, "w", encoding="utf-8") as f:
    f.write(header + "\n".join(out) + "\n")

print("索引已生成: %s" % idx_path)
print("总行数 %d / 标题 %d / 段落 %d" % (total, heading_count, para_total))
