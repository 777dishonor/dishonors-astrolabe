# -*- coding: utf-8 -*-
"""通用索引构建器：为 references/ 下指定的任一底本生成 _index_<tag>.md。
用法: python3 build_index_multi.py <底本文件名> <索引tag>
例:   python3 build_index_multi.py "基督占星第一册(Christian Astrology 1)选译.md" ca1
"""
import sys, os, re

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(SKILL, "references")

if len(sys.argv) != 3:
    print("用法: build_index_multi.py <底本文件名> <索引tag>")
    sys.exit(1)

fname = sys.argv[1]
tag = sys.argv[2]
SRC = os.path.join(REF, fname)
if not os.path.exists(SRC):
    print("底本不存在: %s" % SRC); sys.exit(1)

with open(SRC, "rb") as f:
    _raw = f.read()
with open(SRC, "wb") as f:
    f.write(_raw)  # 确保底本完好（先读内存再写回，防自覆盖）

with open(SRC, "r", encoding="utf-8") as f:
    content = f.read()
lines = [ln.rstrip("\r") for ln in content.split("\n")]
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

def is_heading(line):
    """识别标题：markdown # 或中文序号（第X章/第X册/X、/X. ）"""
    s = line.strip()
    if not s:
        return None
    # markdown 标题
    m = re.match(r"^(#{1,6})\s+(.*)$", line)
    if m:
        return m.group(2).strip()
    # 中文序号标题：第一章 / 第一册 / 第 102 章 38（允许“第”与序号、序号与“章”间有空格）
    if re.match(r"^第\s*[一二三四五六七八九十百零\d]+\s*[章册节卷篇]", s):
        return s
    # 二级：一、二、三、 （中文数字后接顿号）
    if re.match(r"^[一二三四五六七八九十]+、", s):
        return s
    # 罗马/数字章：Chapter 1 / 第1章 等已被上面覆盖；也认 'X.' 列表式大标题（行较短且以数字.开头）
    if re.match(r"^\d+[.、]", s) and len(s) <= 40:
        return s
    return None

i = 0
while i < total:
    line = lines[i]
    hm = is_heading(line)
    if hm is not None:
        if in_para:
            emit(current_title, para_count, para_start, i, para_text)
            in_para = False; para_text = []
        title = hm
        heading_count += 1
        out.append("")
        out.append("# " + title)
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

idx_path = os.path.join(REF, "_index_%s.md" % tag)
header = (
    "# 索引：%s\n\n" % fname +
    "- 底本文件：%s\n" % fname +
    "- 底本路径：%s\n" % SRC +
    "- 总行数：%d\n" % total +
    "- 标题数：%d\n" % heading_count +
    "- 段落总数：%d\n\n" % para_total +
    "---\n\n"
)
with open(idx_path, "w", encoding="utf-8") as f:
    f.write(header + "\n".join(out) + "\n")

print("索引已生成: %s" % idx_path)
print("总行数 %d / 标题 %d / 段落 %d" % (total, heading_count, para_total))
