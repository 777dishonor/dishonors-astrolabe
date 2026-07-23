# -*- coding: utf-8 -*-
"""
用 Kerykeion 生成古典风格星盘图（替代手写 draw_chart.py）。

- 古典行星预设：TRADITIONAL_ASTROLOGY_ACTIVE_POINTS
  （日/月/水/金/火/木/土 + 南北交点，自动屏蔽三王星，契合古典/卜卦铁律）
- 宫位制：horary → Regiomontanus('R')，natal → Placidus('P')
- 渲染：Kerykeion 出 SVG → svglib + reportlab(3.6 内置 _renderPM) 转 PNG
  （不依赖 cairo/libcairo，纯 Python，适合 skill 部署）
依赖：dishonors-astrolabe/.venv 的 kerykeion + svglib + reportlab==3.6.13

用法：
  python plot_chart.py --time "1990-06-15 14:30" --lat 39.908 --lon 116.397 \
      --mode natal --out chart.png --name "Demo" --city "Beijing"
"""
import sys, argparse, re, os, tempfile, math

# 数字时区 → IANA 近似映射（中国场景为主，海外常见）
TZ_MAP = {
    8: "Asia/Shanghai", 9: "Asia/Tokyo", 0: "Europe/London",
    -5: "America/New_York", -8: "America/Los_Angeles",
    7: "Asia/Bangkok", 5.5: "Asia/Kolkata", 1: "Europe/Paris",
    -3: "America/Sao_Paulo", 10: "Australia/Sydney", 11: "Australia/Sydney",
}

# 中文字体（覆盖中文标签 + 拉丁字母/数字）。行星/星座符号是矢量 path，不依赖字体。
# 注意：仅 simhei.ttf（纯 TTF）能在 reportlab renderPM 管道下正确渲染中文；
# msyh.ttc（雅黑 TTC）/ simsun.ttc（宋体 TTC）均显示方框（TTC 兼容问题）。
_SIMHEI_PATH = r"C:\Windows\Fonts\simhei.ttf"
if not os.path.exists(_SIMHEI_PATH):
    raise FileNotFoundError("未找到 simhei.ttf 黑体字体文件（路径：%s）" % _SIMHEI_PATH)

_font_registered = False


def _register_font():
    global _font_registered
    if _font_registered:
        return
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase import pdfmetrics
    # simhei.ttf 是纯 TTF（非 TTC），无需 subfontIndex
    pdfmetrics.registerFont(TTFont("SimHei", _SIMHEI_PATH))
    _font_registered = True


def _find_group_end(svg_text, start_pos):
    """给定 <g 开始位置，返回该组对应的 </g> 结束位置（处理嵌套）。"""
    depth = 0
    i = start_pos
    while i < len(svg_text):
        # 先检查 </g>（因为 '/' 可能出现在属性值里，需优先于 '<g' 判断）
        if svg_text[i:i+4] == '</g>':
            depth -= 1
            if depth == 0:
                return i + 4  # 位置在 '</g>' 之后
            i += 4
        elif svg_text[i:i+2] == '<g':
            depth += 1
            gt = svg_text.find('>', i)
            if gt != -1:
                i = gt + 1
            else:
                break
        else:
            i += 1
    return -1


def _shrink_zodiac(svg_text):
    """缩放 Zodiac 组内的所有星座符号 <use>。
    svg2rlg 不支持 <use width/height>，改用在每个 <use> 外包裹
    <g transform="translate(x,y) scale(0.4)"> 并重置 <use> 坐标为 0,0。
    """
    m = re.search(
        r"<g[^>]*kr:node\s*=\s*['\"]Zodiac['\"][^>]*>",
        svg_text)
    if not m:
        return svg_text
    start = m.start()
    end = _find_group_end(svg_text, start)
    if end == -1:
        return svg_text

    body = svg_text[m.end():end]

    def wrap_use(u):
        tag = u.group(0)
        # 提取 x,y
        xm = re.search(r"x\s*=\s*['\"]([^'\"]+)['\"]", tag)
        ym = re.search(r"y\s*=\s*['\"]([^'\"]+)['\"]", tag)
        hm = re.search(r"(xlink:)?href\s*=\s*['\"]([^'\"]+)['\"]", tag)
        if xm and ym and hm:
            x, y, href = xm.group(1), ym.group(1), hm.group(2)
            return f"<g transform='translate({x},{y}) scale(0.4)'><use xlink:href='{href}' /></g>"
        return tag

    new_body = re.sub(r"<use\b[^>]*?\s*/>", wrap_use, body)
    open_tag_end = svg_text.find('>', start) + 1
    return (svg_text[:open_tag_end]
            + new_body
            + svg_text[end:end + 4]
            + svg_text[end + 4:])


def _localize_bottom_text(svg_text):
    """左下角只保留宫位制英文原文，其余改中文。
    Kerykeion 的 lang=EN 下默认输出英文，我们需要：
      Zodiac: Tropical       → 黄道：回归
      Houses: Regiomontanus  → 保留英文
      Lunation Day: 8        → 月日：8
      Lunar phase: First Quarter → 月相：上弦月
      Perspective: Apparent Geocentric → 视角：视地心
    """
    # 黄道（保留中文冒号便于对齐）
    svg_text = re.sub(r'[Zz]odiac[\s]*:[\s]*Tropical', '黄道：回归', svg_text)
    # 宫位制必须保留英文 Regiomontanus
    svg_text = re.sub(r'Domification[\s]*:[\s]*[^<]+', 'Houses: Regiomontanus', svg_text)
    svg_text = re.sub(r'宫位划分[\s]*[：:][\s]*[^<]+', 'Houses: Regiomontanus', svg_text)
    # 月日/月相/视角
    svg_text = re.sub(r'Lunation Day[\s]*:[\s]*', '月日：', svg_text)
    svg_text = re.sub(r'Lunar phase[\s]*:[\s]*First Quarter', '月相：上弦月', svg_text)
    svg_text = re.sub(r'Lunar phase[\s]*:[\s]*Last Quarter', '月相：下弦月', svg_text)
    svg_text = re.sub(r'Lunar phase[\s]*:[\s]*New Moon', '月相：新月', svg_text)
    svg_text = re.sub(r'Lunar phase[\s]*:[\s]*Full Moon', '月相：满月', svg_text)
    svg_text = re.sub(r'Lunar phase[\s]*:[\s]*Waning Crescent', '月相：残月', svg_text)
    svg_text = re.sub(r'Lunar phase[\s]*:[\s]*Waning Gibbous', '月相：亏凸月', svg_text)
    svg_text = re.sub(r'Lunar phase[\s]*:[\s]*Waxing Crescent', '月相：娥眉月', svg_text)
    svg_text = re.sub(r'Lunar phase[\s]*:[\s]*Waxing Gibbous', '月相：盈凸月', svg_text)
    svg_text = re.sub(r'Perspective[\s]*:[\s]*Apparent Geocentric', '视角：视地心', svg_text)
    return svg_text


def _localize_top_left(svg_text):
    """左上角信息全部改成中文。
    修改 kr:node='Top_Left_Text' 组内的固定英文标签。
    """
    replacements = {
        'Location:': '位置：',
        'Latitude:': '纬度：',
        'Longitude:': '经度：',
        'Day of Week:': '星期：',
        'Monday': '星期一',
        'Tuesday': '星期二',
        'Wednesday': '星期三',
        'Thursday': '星期四',
        'Friday': '星期五',
        'Saturday': '星期六',
        'Sunday': '星期日',
        'Elements:': '四元素：',
        'Fire': '火',
        'Earth': '土',
        'Air': '风',
        'Water': '水',
        'Qualities:': '三性质：',
        'Cardinal': '开创',
        'Fixed': '固定',
        'Mutable': '变动',
    }
    for pat, repl in replacements.items():
        svg_text = svg_text.replace(pat, repl)
    return svg_text


def _reposition_house_numbers(svg_text):
    """调整宫位数字：缩小字体、强制黑色，微调拥挤位置。
    保持 Kerykeion 原始坐标（避免 svglib 对 text-anchor 支持不佳导致数字消失）。
    """
    # 找到 Houses_Wheel 内的所有 HouseNumber 组
    hw_match = re.search(r"<g\b[^>]*kr:node\s*=\s*['\"]Houses_Wheel['\"][^>]*>", svg_text)
    if not hw_match:
        return svg_text
    hw_start = hw_match.end()
    hw_end = _find_group_end(svg_text, hw_match.start())
    if hw_end == -1:
        return svg_text

    hw_body = svg_text[hw_start:hw_end]

    # 微调表：把拥挤的右上角 7/8/9 稍微挪开
    tweaks = {
        '7': ('424', '195'),   # 原 424,199 → 上移一点
        '8': ('377', '112'),   # 原 377,112 → 基本不变
        '9': ('280', '55'),    # 原 280,56 → 上移一点
    }

    def tweak_hn(m):
        block = m.group(0)
        # 提取数字
        nm = re.search(r"<tspan[^>]*>(\d+)</tspan>", block)
        if not nm:
            return block
        num = nm.group(1)
        # 强制黑色 + 缩小字体到 10px
        block = re.sub(r"fill:\s*[^;]+", "fill:black", block)
        block = re.sub(r"font-size:\s*[\d.]+px", "font-size:10px", block)
        block = re.sub(r"fill-opacity:\s*[\d.]+;?", "", block)
        # 应用微调
        if num in tweaks:
            nx, ny = tweaks[num]
            block = re.sub(r"x\s*=\s*['\"][^'\"]+['\"]", f"x='{nx}'", block, count=1)
            block = re.sub(r"y\s*=\s*['\"][^'\"]+['\"]", f"y='{ny}'", block, count=1)
        return block

    new_hw_body = re.sub(
        r"<g\b[^>]*kr:node\s*=\s*['\"]HouseNumber['\"][^>]*>.*?</g>",
        tweak_hn, hw_body, flags=re.S)

    return svg_text[:hw_start] + new_hw_body + svg_text[hw_end:]


def _shrink_zodiac(svg_text):
    """缩放 Zodiac 组内的所有星座符号 <use>，并将符号中心对齐到各星座扇区中心。
    svg2rlg 不支持 <use width/height>，改用在每个 <use> 外包裹
    <g transform="translate(x,y) scale(0.4)"> 并重置 <use> 坐标为 0,0。
    """
    m = re.search(
        r"<g[^>]*kr:node\s*=\s*['\"]Zodiac['\"][^>]*>",
        svg_text)
    if not m:
        return svg_text
    start = m.start()
    end = _find_group_end(svg_text, start)
    if end == -1:
        return svg_text

    body = svg_text[m.end():end]

    def wrap_use(u):
        tag = u.group(0)
        xm = re.search(r"x\s*=\s*['\"]([^'\"]+)['\"]", tag)
        ym = re.search(r"y\s*=\s*['\"]([^'\"]+)['\"]", tag)
        hm = re.search(r"(xlink:)?href\s*=\s*['\"]([^'\"]+)['\"]", tag)
        if xm and ym and hm:
            x, y, href = xm.group(1), ym.group(1), hm.group(2)
            # scale(0.4) 后符号中心偏移：先 translate 到中心，再 scale，再移回原位
            # 符号原始大小约 32x32，中心在 (16,16)
            # translate(x,y) → 把符号左上角放到 (x,y)
            # 要居中：translate(x-6.4, y-6.4) scale(0.4) （因为 16*0.4=6.4）
            cx_off = 6.4
            return f"<g transform='translate({float(x)-cx_off},{float(y)-cx_off}) scale(0.4)'><use xlink:href='{href}' /></g>"
        return tag

    new_body = re.sub(r"<use\b[^>]*?\s*/>", wrap_use, body)
    open_tag_end = svg_text.find('>', start) + 1
    return (svg_text[:open_tag_end]
            + new_body
            + svg_text[end:end + 4]
            + svg_text[end + 4:])


def svg_to_png(svg_text, png_path, dpi=330):
    """Kerykeion SVG → PNG：后处理（宫数字黑、星座符号缩小、字体雅黑、CSS 变量）+ reportlab 渲染。
    dpi 默认 330（约为早期 110 的 3 倍），输出更高清。
    """
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    _register_font()

    # 1) 收集 <style> 块 CSS 变量 + 预置默认值
    vmap = {
        "--kerykeion-chart-color-fire-percentage": "#FF0000",
        "--kerykeion-chart-color-earth-percentage": "#8B4513",
        "--kerykeion-chart-color-water-percentage": "#0000FF",
    }
    for sm in re.finditer(r"<style[^>]*>(.*?)</style>", svg_text, re.S):
        for nm, val in re.findall(r"(--[\w-]+)\s*:\s*([^;]+)", sm.group(1)):
            vmap[nm.strip()] = val.strip()
    # 宫位数字改黑色
    vmap["--kerykeion-chart-color-house-number"] = "black"

    # 2) 替换 var(--name) 为具体值（未定义兜底 black），
    #    注意 Kerykeion 生成的 var 括号内可能有空白甚至跨行
    #    "var(\n        --kerykeion-chart-color-fire-percentage\n    )"
    def _replace_var(m):
        name = m.group(1).strip()
        return vmap.get(name, "black")
    svg_text = re.sub(r"var\s*\(([^)]+)\)", _replace_var, svg_text, flags=re.S)

    # 3) 宫数字去 fill-opacity（保持纯黑，而非半透明灰）
    #    Kerykeion 把 kr:node='HouseNumber' 放在父 <g> 而非 <text> 上，
    #    需要匹配完整块并清除内部 text 的 fill-opacity
    def _strip_fill_opacity(m):
        block = m.group(0)
        return re.sub(r"(fill-opacity:\s*[\d.]+;?)", "", block)
    svg_text = re.sub(
        r"<g\b[^>]*kr:node='HouseNumber'[^>]*>.*?</g>",
        _strip_fill_opacity, svg_text, flags=re.S)

    # 4) 星座符号缩小（仅 Zodiac 组内）
    svg_text = _shrink_zodiac(svg_text)

    # 5) 底部文本：保留 Regiomontanus 英文，其余改中文
    svg_text = _localize_bottom_text(svg_text)

    # 6) 左上角改中文
    svg_text = _localize_top_left(svg_text)

    # 7) 重新计算所有宫位数字位置
    svg_text = _reposition_house_numbers(svg_text)

    # 8) 字体注入：所有 text 用 SimHei（含中文+拉丁；符号为矢量 path 不依赖字体）
    svg_text = re.sub(
        r"(<text\b)([^>]*)",
        lambda m: (m.group(1) + " font-family='SimHei'" + m.group(2))
        if "font-family" not in m.group(2)
        else (m.group(1) + re.sub(r"font-family='[^']*'",
                                  "font-family='SimHei'", m.group(2))),
        svg_text)

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False,
                                      encoding="utf-8")
    tmp.write(svg_text)
    tmp.close()
    try:
        drawing = svg2rlg(tmp.name)
        renderPM.drawToFile(drawing, png_path, fmt="PNG", dpi=dpi)
    finally:
        os.unlink(tmp.name)


def main():
    ap = argparse.ArgumentParser(description="Kerykeion 古典星盘出图")
    ap.add_argument("--time", required=True, help="本地时间 YYYY-MM-DD HH:MM")
    ap.add_argument("--tz", type=float, default=8, help="数字时区，东为正（默认8）")
    ap.add_argument("--tz_str", help="IANA 时区（优先于 --tz）")
    ap.add_argument("--lat", type=float, required=True, help="纬度(北纬正)")
    ap.add_argument("--lon", type=float, required=True, help="经度(东经正)")
    ap.add_argument("--mode", default="horary", choices=["horary", "natal"],
                    help="horary(卜卦/Regiomontanus) 或 natal(本命/Placidus)")
    ap.add_argument("--name", default="Chart",
                    help="盘主名/标识（显示用，建议英文/拼音）")
    ap.add_argument("--city", help="城市名（仅显示用，不影响计算；建议英文/拼音）")
    ap.add_argument("--nation", default="CN", help="国家代码（默认 CN）")
    ap.add_argument("--title", help="自定义标题（覆盖默认 Birth Chart；建议英文）")
    ap.add_argument("--out", required=True, help="输出 PNG 路径")
    ap.add_argument("--svg", help="可选：同时输出 SVG 路径")
    ap.add_argument("--lang", default="EN",
                    choices=["CN", "EN", "FR", "PT", "IT", "ES", "RU", "TR", "DE", "HI"])
    ap.add_argument("--theme", default="classic",
                    choices=["light", "dark", "dark-high-contrast", "classic",
                             "strawberry", "black-and-white"])
    ap.add_argument("--wheel-only", action="store_true",
                    help="只画星盘轮（不含底部相位表）")
    ap.add_argument("--dpi", type=int, default=330, help="输出分辨率（默认330≈原110的3倍，更高清）")
    args = ap.parse_args()

    from kerykeion import (AstrologicalSubjectFactory, ChartDataFactory,
                           ChartDrawer)
    from kerykeion.settings.config_constants import TRADITIONAL_ASTROLOGY_ACTIVE_POINTS

    ymd, hm = args.time.split(" ")
    y, mo, d = [int(x) for x in ymd.split("-")]
    h, mi = [int(x) for x in hm.split(":")]

    hs_id = 'R' if args.mode == "horary" else 'P'
    tz_str = args.tz_str or TZ_MAP.get(args.tz, "Asia/Shanghai")
    effective_title = (args.title or
                       ("Natal Chart" if args.mode == "natal" else "Horary Chart"))

    subject = AstrologicalSubjectFactory.from_birth_data(
        args.name, y, mo, d, h, mi,
        city=args.city, nation=args.nation, lng=args.lon, lat=args.lat, tz_str=tz_str,
        online=False,
        houses_system_identifier=hs_id,
        active_points=TRADITIONAL_ASTROLOGY_ACTIVE_POINTS,
    )
    chart_data = ChartDataFactory.create_natal_chart_data(
        subject, active_points=TRADITIONAL_ASTROLOGY_ACTIVE_POINTS)
    drawer = ChartDrawer(chart_data, theme=args.theme,
                         chart_language=args.lang, custom_title=effective_title)

    svg = (drawer.generate_wheel_only_svg_string() if args.wheel_only
           else drawer.generate_svg_string())
    if args.svg:
        with open(args.svg, "w", encoding="utf-8") as f:
            f.write(svg)

    svg_to_png(svg, args.out, dpi=args.dpi)
    print("[Kerykeion 星盘图已生成] %s | 宫位制=%s(%s) | 时区=%s | 语言=%s | 标题=%s"
          % (args.out, hs_id,
             "Regiomontanus" if hs_id == 'R' else "Placidus",
             tz_str, args.lang, effective_title))


if __name__ == "__main__":
    main()
