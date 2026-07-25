# -*- coding: utf-8 -*-
"""
一页纸 PDF 占星报告生成器
  Part A: 星盘图（PNG 嵌入 + 左侧数据栏）
  Part B: 行星/宫位/相位数据表
  Part C: 占星判读文字

用法:
  # 完整流程（排盘 + 渲染 + PDF）
  python generate_full.py --time "2026-07-25 18:00" --tz 8 --city 北京 \
      --question "我的猫丢了，能找回来吗？" --verdict "判读文字..." --out report.pdf

  # 如果已有星盘 PNG 和数据 JSON
  python generate_full.py --chart-png chart.png --chart-json chart.json \
      --verdict "判读文字..." --out report.pdf
"""
import sys, os, json, subprocess, argparse, codecs

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")

# ReportLab 中文支持
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 注册中文字体
FONT_PATH = "C:/Windows/Fonts/simhei.ttf"
FONT_NAME = "SimHei"
try:
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
except Exception:
    pass  # 已注册

PAGE_W, PAGE_H = A4  # 210 x 297 mm

# 色彩方案
COLOR_PRIMARY = HexColor("#1a1a2e")
COLOR_ACCENT = HexColor("#c9a95a")
COLOR_BG_LIGHT = HexColor("#faf8f3")
COLOR_TEXT = HexColor("#333333")
COLOR_MUTED = HexColor("#888888")
COLOR_TABLE_HEADER = HexColor("#1a1a2e")
COLOR_TABLE_ROW_ALT = HexColor("#f5f2e8")
COLOR_ASPECT_GOOD = HexColor("#27AE60")
COLOR_ASPECT_BAD = HexColor("#FF4500")
COLOR_LINE = HexColor("#e0d8c8")

STYLES = getSampleStyleSheet()

def _cn_style(name, **kw):
    """创建含中文字体的 ParagraphStyle"""
    kw.setdefault("fontName", FONT_NAME)
    kw.setdefault("leading", kw.get("fontSize", 10) * 1.5)
    return ParagraphStyle(name, **kw)

# === 样式 ===
STYLE_TITLE = _cn_style("CNTitle", fontSize=22, textColor=COLOR_PRIMARY,
                         alignment=TA_CENTER, spaceAfter=4*mm, leading=30)
STYLE_SUBTITLE = _cn_style("CNSubtitle", fontSize=10, textColor=COLOR_MUTED,
                            alignment=TA_CENTER, spaceAfter=8*mm)
STYLE_H2 = _cn_style("CNH2", fontSize=14, textColor=COLOR_PRIMARY,
                      spaceBefore=8*mm, spaceAfter=4*mm, leading=20)
STYLE_BODY = _cn_style("CNBody", fontSize=9.5, textColor=COLOR_TEXT,
                        alignment=TA_LEFT, spaceAfter=1.2*mm, leading=13,
                        firstLineIndent=0)
STYLE_BODY_BOLD = _cn_style("CNBodyBold", fontSize=11, textColor=COLOR_PRIMARY,
                            alignment=TA_LEFT, spaceAfter=1.2*mm, leading=14,
                            firstLineIndent=0)
STYLE_CELL = _cn_style("CNCell", fontSize=8.5, textColor=COLOR_TEXT, leading=12)
STYLE_CELL_HEADER = _cn_style("CNCellHeader", fontSize=8.5,
                               textColor=HexColor("#ffffff"), leading=12)
STYLE_CELL_MUTED = _cn_style("CNCellMuted", fontSize=7.5, textColor=COLOR_MUTED, leading=10)
STYLE_FOOTER = _cn_style("CNFooter", fontSize=7, textColor=COLOR_MUTED,
                          alignment=TA_CENTER)


def get_chart_data(time_str, tz, city):
    """调用 cast_chart.py --json-only"""
    cmd = [
        sys.executable, os.path.join(SCRIPTS_DIR, "cast_chart.py"),
        "--time", time_str, "--tz", str(tz), "--city", city, "--json-only",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"排盘失败: {r.stderr}")
    return json.loads(r.stdout.strip())


def get_chart_png(time_str, tz, city, size=600):
    """调用 render_chart.py 生成 PNG"""
    tmp_png = os.path.join(os.getcwd(), ".chart_tmp_for_pdf.png")
    cmd = [
        sys.executable, os.path.join(SCRIPTS_DIR, "render_chart.py"),
        "--time", time_str, "--tz", str(tz), "--city", city,
        "--out", tmp_png, "--size", str(size),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"渲染失败: {r.stderr}\n{r.stdout}")
    return tmp_png


# === Part B 构建 ===

PLANET_NAMES_CN = ["太阳", "月亮", "水星", "金星", "火星",
                    "木星", "土星", "天王星", "海王星", "冥王星", "北交点"]
SIGNS_CN = ["白羊", "金牛", "双子", "巨蟹", "狮子", "处女",
            "天秤", "天蝎", "射手", "摩羯", "水瓶", "双鱼"]

def lon_to_sign_deg(lon):
    sign_idx = int(lon // 30)
    deg = lon - sign_idx * 30
    return SIGNS_CN[sign_idx], round(deg, 2)

def house_of(lon, cusps):
    for i in range(12):
        s = cusps[i]; e = cusps[(i+1)%12]
        if e > s:
            if s <= lon < e: return i + 1
        else:
            if lon >= s or lon < e: return i + 1
    return 1

def sign_ruler_name(sign_idx):
    rulers = {0:"火星",1:"金星",2:"水星",3:"月亮",4:"太阳",5:"水星",
              6:"金星",7:"火星",8:"木星",9:"土星",10:"土星",11:"木星"}
    return rulers.get(sign_idx, "?")


def build_planet_table(data):
    """行星数据表"""
    header = ["行星", "黄经", "星座", "落宫", "逆行"]
    rows = [header]
    for name in PLANET_NAMES_CN:
        if name not in data["planets"]:
            continue
        val = data["planets"][name]
        lon = val[0]
        sign, deg = lon_to_sign_deg(lon)
        house = str(house_of(lon, data["cusps"]))
        retro = "逆" if (len(val) > 1 and val[1] < 0) else "顺"
        rows.append([name, f"{deg}°", sign, house, retro])
    return rows


def build_house_table(data):
    """宫位数据表"""
    header = ["宫位", "宫头经度", "星座", "度数", "宫主星"]
    rows = [header]
    for i, cusp in enumerate(data["cusps"]):
        sign, deg = lon_to_sign_deg(cusp)
        sign_idx = int(cusp // 30)
        ruler = sign_ruler_name(sign_idx)
        rows.append([str(i+1), f"{cusp:.2f}°", sign, f"{deg:.2f}°", ruler])
    return rows


def build_aspect_table(data):
    """相位表：调用 cast_chart.py 非 json-only 模式的相位段"""
    cmd = [
        sys.executable, os.path.join(SCRIPTS_DIR, "cast_chart.py"),
        "--time", data["datetime"], "--tz", str(data["tz"]),
        "--lat", str(data["lat"]), "--lon", str(data["lon"]),
        "--mode", "horary" if data["mode"] == "卜卦" else "natal",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    # 提取 "🔗 七曜相位" 段
    lines = r.stdout.split("\n")
    aspect_lines = []
    in_section = False
    for line in lines:
        if "七曜相位" in line:
            in_section = True
            continue
        if in_section:
            stripped = line.strip()
            if stripped.startswith("（") or not stripped:
                continue
            if stripped.startswith("===") or stripped.startswith("---"):
                break
            if stripped:
                aspect_lines.append(stripped)
    header = ["相位", "角度", "偏差", "入相/分离"]
    rows = [header]
    for al in aspect_lines:
        # 格式："太阳 拱 月亮  偏差 1.2° （精准）"
        parts = al.strip().split()
        if len(parts) >= 5:
            name1 = parts[0]
            asp = parts[1]
            name2 = parts[2]
            orb = parts[4] if len(parts) > 4 and parts[3] == "偏差" else parts[3]
            sep = " ".join(parts[5:]) if len(parts) > 5 else " ".join(parts[4:]) if len(parts) > 4 else ""
            # 去掉括号避免溢出
            sep = sep.replace("（", "").replace("）", "").replace("(", "").replace(")", "")
            rows.append([f"{name1} {asp} {name2}", asp, f"{orb}°", sep])
    return rows


def make_table(rows, col_widths, title=None):
    """构建格式化表格的 Flowable 列表"""
    elements = []
    if title:
        elements.append(Paragraph(title, STYLE_H2))

    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_TABLE_HEADER),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLOR_BG_LIGHT, HexColor("#ffffff")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    tbl.setStyle(TableStyle(style_cmds))
    elements.append(tbl)
    elements.append(Spacer(1, 4*mm))
    return elements


# === Part A 构建 ===

def _apply_bold_to_key_phrases(text):
    """给判读中的小标题和关键句加粗，并用更大字号包裹"""
    import re
    # ReportLab Paragraph 支持 <font name="..." size="12"> 或 <b>
    # 1) 小标题：一、二、三、... 用 11pt 加粗
    text = re.sub(r'^(一、|二、|三、|四、|五、|六、|七、|八、|九、|十、)', r'<font size="11"><b>\1</b></font>', text)
    text = re.sub(r'(问一：|问二：|问三：)', r'<font size="10"><b>\1</b></font>', text)
    # 2) 【出处】
    text = re.sub(r'(【出处】)', r'<font size="10"><b>\1</b></font>', text)
    # 3) ①②③ 编号项
    text = re.sub(r'(①|②|③|④|⑤|⑥|⑦|⑧|⑨|⑩)', r'<b>\1</b>', text)
    # 4) 结论句（→ 开头）
    text = re.sub(r'(→)', r'<b>\1</b>', text)
    return text


def _extract_verdict_body(text):
    """从完整 MD 中提取判读正文部分（跳过星盘数据表格）"""
    lines = text.split('\n')
    start_idx = 0
    for i, line in enumerate(lines):
        # 找到第一个以 "一、" 开头的行，或 "## 一" 或 "一、我的判断"
        if line.strip().startswith('一、') or '一、我的判断' in line or '一、判断' in line:
            start_idx = i
            break
        # 备选：找到 "我的判断" 或 "结论"
        if '我的判断' in line and start_idx == 0:
            start_idx = i
    if start_idx > 0:
        return '\n'.join(lines[start_idx:])
    return text


def _clean_verdict(text):
    """清理判读文字中的 Markdown 格式残渣和特殊字符"""
    import re
    # 1) 清除标题符号（但保留 ①②③ 编号段落前的结构）
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    # 2) 清除粗体/斜体标记
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    # 3) 清除分隔线
    text = re.sub(r'^---+\s*$', '', text, flags=re.MULTILINE)
    # 4) 清除特殊图标字符（天平、星星、对勾、方框等）
    text = re.sub(r'[⚖️⭐✅🔮📋⚖□🔴🟢🟡]', '', text)
    # 5) 清除 HTML 注释
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    # 6) 清除多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 7) 清除行首/行尾空格
    text = re.sub(r'^[ \t]+|[ \t]+$', '', text, flags=re.MULTILINE)
    return text


def build_part_a(chart_png_path, data):
    """星盘图 + 左侧信息栏 → 居中放置的 Flowable 列表"""
    elements = []
    # 标题
    elements.append(Paragraph(
        f"占星报告 · {data['datetime']}",
        STYLE_TITLE
    ))
    elements.append(Paragraph(
        f"{data['mode']} · {data['house_system']} 宫位制 · 纬度{data['lat']:.2f}° 经度{data['lon']:.2f}°",
        STYLE_SUBTITLE
    ))

    # 星盘图：只裁剪上下白边，左右保留原样（保护左侧数据栏）
    from PIL import Image as PILImage
    import numpy as np
    from io import BytesIO
    pil_img = PILImage.open(chart_png_path)
    # 按非白色像素检测上下边界（AstroChart 输出为 RGB 白底）
    arr = np.array(pil_img.convert('RGB'))
    bg = np.array([255, 255, 255], dtype=float)
    diff = np.abs(arr.astype(float) - bg).sum(axis=2)
    mask = diff > 25  # 非背景像素
    rows = mask.any(axis=1)
    if rows.any():
        top = int(np.argmax(rows))
        bottom = int(len(rows) - np.argmax(rows[::-1]))
        # 左右不动
        pil_img = pil_img.crop((0, top, pil_img.width, bottom))
    # 缩放至合适尺寸（宽度不超过页面 70%）
    max_img_w = PAGE_W * 0.70
    img_w, img_h = pil_img.size
    scale = min(max_img_w / img_w, max_img_w / img_h)
    new_w, new_h = img_w * scale, img_h * scale
    # 转为 ReportLab Image
    buf = BytesIO()
    pil_img.save(buf, format='PNG')
    buf.seek(0)
    img = Image(buf, width=new_w, height=new_h)
    elements.append(img)
    elements.append(Spacer(1, 1*mm))

    # 关键数据摘要
    asc_sign, asc_deg = lon_to_sign_deg(data["asc"])
    mc_sign, mc_deg = lon_to_sign_deg(data["mc"])
    summary = [
        f"ASC: {asc_sign} {asc_deg:.2f}°  |  MC: {mc_sign} {mc_deg:.2f}°  |  "
        f"宫位制: {data['house_system']}  |  模式: {data['mode']}",
    ]
    for line in summary:
        elements.append(Paragraph(line, _cn_style("CNSummary", fontSize=8.5,
                          textColor=COLOR_MUTED, alignment=TA_CENTER)))

    return elements


# === 主流程 ===

def generate_pdf(chart_png, chart_data, verdict_text, question, out_path):
    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=12*mm, bottomMargin=12*mm,
        title=f"占星报告 · {chart_data['datetime']}",
        author="dishonors-astrolabe",
    )

    story = []

    # === Part A ===
    story.extend(build_part_a(chart_png, chart_data))

    # 提问
    if question:
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(
            f"<b>提问：</b>{question}",
            _cn_style("CNQuestion", fontSize=9.5, textColor=COLOR_PRIMARY,
                       alignment=TA_CENTER, spaceAfter=4*mm)
        ))

    # 分隔线
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "━" * 40,
        _cn_style("CNDivider", fontSize=6, textColor=COLOR_LINE,
                   alignment=TA_CENTER, spaceAfter=4*mm)
    ))

    # === Part B ===
    # 行星表
    planet_rows = build_planet_table(chart_data)
    story.extend(make_table(planet_rows, [50, 55, 50, 35, 35]))

    # 宫位表
    house_rows = build_house_table(chart_data)
    story.extend(make_table(house_rows, [35, 60, 50, 55, 50]))

    # 相位表
    aspect_rows = build_aspect_table(chart_data)
    story.extend(make_table(aspect_rows, [140, 45, 55, 60]))

    # 分隔线
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "━" * 40,
        _cn_style("CNDivider", fontSize=6, textColor=COLOR_LINE,
                   alignment=TA_CENTER, spaceAfter=4*mm)
    ))

    # === Part C ===
    if verdict_text:
        # 清理并提取判读正文（跳过前面的数据表格，从"一、"或"## 一"开始）
        cleaned = _extract_verdict_body(verdict_text)
        cleaned = _clean_verdict(cleaned)
        prev_para = None
        for para in cleaned.strip().split("\n\n"):
            text = para.strip().replace("\n", "<br/>")
            # 跳过空段落和表格残渣
            if not text or len(text) < 3:
                continue
            if text.startswith("|") and text.count("|") > 2:
                continue  # 跳过表格行
            # 如果当前段落是 ①②③ 或 一、二、三 开头，且前面有段落，加空行
            if prev_para and (text.startswith('①') or text.startswith('②') or text.startswith('③') or
                              text.startswith('一、') or text.startswith('二、') or text.startswith('三、') or
                              text.startswith('四、') or text.startswith('五、')):
                story.append(Spacer(1, 2.5*mm))
            # 给小标题和关键句加粗
            text = _apply_bold_to_key_phrases(text)
            story.append(Paragraph(text, STYLE_BODY))
            prev_para = para
    else:
        story.append(Paragraph(
            "（判读文字由古典占星大师 AI agent 生成，此处为占位内容。"
            "完整报告将包含基于七库底本的详细判读、典籍引用及结论。）",
            _cn_style("CNPlaceholder", fontSize=9, textColor=COLOR_MUTED,
                       alignment=TA_LEFT, spaceAfter=3*mm)
        ))

    # 页脚
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph(
        f"dishonors-astrolabe · {chart_data['datetime']} · "
        f"{chart_data['house_system']} 宫位制 · 古典占星七库判读",
        STYLE_FOOTER
    ))

    doc.build(story)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="一页纸 PDF 占星报告生成器")
    ap.add_argument("--time", help="本地时间 YYYY-MM-DD HH:MM")
    ap.add_argument("--tz", type=float, default=8, help="时区（默认8）")
    ap.add_argument("--city", default="北京", help="城市名")
    ap.add_argument("--chart-png", help="已有星盘 PNG 路径（跳过渲染）")
    ap.add_argument("--chart-json", help="已有 JSON 数据路径（跳过排盘）")
    ap.add_argument("--question", default="", help="问卜问题")
    ap.add_argument("--verdict", default="", help="判读文字（支持换行）")
    ap.add_argument("--verdict-file", help="从文件读取判读文字")
    ap.add_argument("--out", default="report.pdf", help="输出 PDF 路径")
    ap.add_argument("--size", type=int, default=600, help="星盘尺寸（默认600）")
    args = ap.parse_args()

    # 加载数据
    if args.chart_json:
        with open(args.chart_json, "r", encoding="utf-8") as f:
            chart_data = json.load(f)
    elif args.time:
        chart_data = get_chart_data(args.time, args.tz, args.city)
    else:
        print("必须提供 --time 或 --chart-json"); sys.exit(2)

    # 获取星盘 PNG
    chart_png = args.chart_png
    tmp_png = None
    if not chart_png:
        if args.time:
            chart_png = get_chart_png(args.time, args.tz, args.city, size=args.size)
            chart_png = tmp_png = chart_png  # 标记为临时
        else:
            print("必须提供 --chart-png 或 --time"); sys.exit(2)

    # 判读文字
    verdict = args.verdict
    if args.verdict_file:
        with open(args.verdict_file, "r", encoding="utf-8") as f:
            verdict = f.read()

    # 生成 PDF
    out = generate_pdf(chart_png, chart_data, verdict, args.question, args.out)
    print(f"PDF 已生成: {out}")

    # 清理临时文件
    if tmp_png and os.path.exists(tmp_png):
        os.remove(tmp_png)


if __name__ == "__main__":
    main()
