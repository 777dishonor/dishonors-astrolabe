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
import sys, argparse, re, os, tempfile

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
    """缩放 Zodiac 组内的所有星座符号 <use>——添加 width/height=15px。
    svg2rlg 不支持 <use transform>，但支持 <use width/height>。
    注意：Kerykeion 的 Zodiac 组有嵌套 <g> 结构，
    用非贪婪 .*? 会提前碰到内层 </g>，需用 _find_group_end 精确定位边界。
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

    head = svg_text[start:end + 4]  # 含首尾标签
    body = svg_text[m.end():end]

    def shrink_use(u):
        tag = u.group(0)
        if re.search(r"width\s*=", tag, re.I):
            tag = re.sub(
                r"width\s*=\s*['\"]([\d.]+)['\"]",
                lambda m2: "width='%.1f'" % (float(m2.group(1)) / 2), tag)
            tag = re.sub(
                r"height\s*=\s*['\"]([\d.]+)['\"]",
                lambda m2: "height='%.1f'" % (float(m2.group(1)) / 2), tag)
        else:
            # 替换末尾的 '/>' 为 ' width="15" height="15" />'
            if tag.rstrip().endswith('/>'):
                tag = tag.rstrip()[:-2].rstrip() + " width='15' height='15' />"
            else:
                tag = tag + " width='15' height='15' />"
        return tag

    new_body = re.sub(r"<use\b[^>]*?\s*/>", shrink_use, body)
    # 重建完整 Zodiac 组（保留首尾标签）
    open_tag_end = svg_text.find('>', start) + 1
    return (svg_text[:open_tag_end]
            + new_body
            + svg_text[end:end + 4]
            + svg_text[end + 4:])


def _localize_bottom_text(svg_text):
    """将底部左下角的中文标签改为英文。
    Kerykeion 的 lang=CN 下输出繁体中文，如：
      黃道: 熱帶       →  Zodiac: Tropical
      宫位划分: 雷焦蒙塔努斯 →  Houses: Regiomontanus
      朔望月日: 8      →  (保留)
      月相: 上弦月      →  (保留)
      视角: 視地心      →  (保留)
    注意：繁体字（黃/熱）与常见简体不匹配，需分别处理。
    """
    # 黄道/热带（繁体+简体+全角/半角冒号）
    svg_text = re.sub(r'[黄黃]道[\s]*[：:][\s]*[热熱][帶带]', 'Zodiac: Tropical', svg_text)
    # 宫位划分制度
    svg_text = re.sub(r'宫位划分[\s]*[：:][\s]*[^<]+', 'Houses: Regiomontanus', svg_text)
    return svg_text


def _adjust_house_numbers(svg_text):
    """调整宫位数字位置，解决右上角7/8/9宫数字拥挤问题。
    通过微调坐标让数字分布更均匀。
    """
    # 用正则匹配 tspan 元素，支持单引号和双引号
    # 目标：7→(410,185)、8→(365,135)、9→(275,85)
    for num, new_x, new_y in [("7", "410", "185"),
                              ("8", "365", "135"),
                              ("9", "275", "85")]:
        svg_text = re.sub(
            r"<tspan\s+x\s*=\s*['\"]([^'\"]+)['\"]\s+y\s*=\s*['\"]([^'\"]+)['\"]>\s*"
            + re.escape(num) + r"\s*</tspan>",
            lambda m: f"<tspan x='{new_x}' y='{new_y}'>{num}</tspan>",
            svg_text)
    return svg_text


def svg_to_png(svg_text, png_path, dpi=330):
    """Kerykeion SVG → PNG：后处理（宫数字黑、星座符号缩小、字体雅黑、CSS 变量）+ reportlab 渲染。
    dpi 默认 330（约为早期 110 的 3 倍），输出更高清。
    """
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    _register_font()

    # 1) 收集 <style> 块 CSS 变量
    vmap = {}
    for sm in re.finditer(r"<style[^>]*>(.*?)</style>", svg_text, re.S):
        for nm, val in re.findall(r"(--[\w-]+)\s*:\s*([^;]+)", sm.group(1)):
            vmap[nm.strip()] = val.strip()
    # 宫位数字改黑色
    vmap["--kerykeion-chart-color-house-number"] = "black"

    # 2) 替换 var(--name) 为具体值（未定义兜底 black），
    #    注意 Kerykeion 生成的 var 括号内可能有空白
    #    "var(         --kerykeion-chart-color-fire-percentage     )"
    svg_text = re.sub(r"var\s*\(\s+([^)]+)\s+\)",
                      lambda m: vmap.get(m.group(1).strip(), "black"), svg_text)
    svg_text = re.sub(r"var\(([^)]+)\)",
                      lambda m: vmap.get(m.group(1).strip(), "black"), svg_text)

    # 3) 宫数字去 fill-opacity（保持纯黑，而非半透明灰）
    svg_text = re.sub(
        r"(<text\b[^>]*kr:node='HouseNumber'[^>]*style=')([^']*)(')",
        lambda m: m.group(1) + re.sub(r"fill-opacity:\s*[^;]+;?", "", m.group(2)) + m.group(3),
        svg_text)

    # 4) 星座符号缩小（仅 Zodiac 组内）
    svg_text = _shrink_zodiac(svg_text)

    # 5) 底部文本英文化
    svg_text = _localize_bottom_text(svg_text)

    # 6) 调整宫位数字位置
    svg_text = _adjust_house_numbers(svg_text)

    # 7) 字体注入：所有 text 用 SimHei（含中文+拉丁；符号为矢量 path 不依赖字体）
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
