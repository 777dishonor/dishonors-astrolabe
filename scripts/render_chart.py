# -*- coding: utf-8 -*-
"""
星盘渲染脚本：cast_chart.py (pyswisseph) → AstroChart HTML → puppeteer PNG
用法:
  python render_chart.py --time "2026-07-25 18:00" --tz 8 --city 北京 --out chart.png
  python render_chart.py --time "2026-07-25 18:00" --tz 8 --city 北京 --html my.html
"""
import argparse, subprocess, sys, os, json, codecs

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
ASTROCHART_JS = os.path.join(SKILL_DIR, "lib", "astrochart.js")
CAPTURE_JS = os.path.join(SKILL_DIR, "lib", "capture", "capture.js")


def cast_json(time_str, tz, city):
    """调用 cast_chart.py --json-only 获取 JSON 数据"""
    cmd = [
        sys.executable,
        os.path.join(SCRIPTS_DIR, "cast_chart.py"),
        "--time", time_str,
        "--tz", str(tz),
        "--city", city,
        "--json-only",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"排盘失败: {result.stderr}")
    return json.loads(result.stdout.strip())


def build_html(data, size=700):
    """用 AstroChart 数据生成自包含 HTML"""
    # 行星名映射：中文 → AstroChart 英文
    planet_map = {
        "太阳": "Sun", "月亮": "Moon", "水星": "Mercury", "金星": "Venus",
        "火星": "Mars", "木星": "Jupiter", "土星": "Saturn", "天王星": "Uranus",
        "海王星": "Neptune", "冥王星": "Pluto", "北交点": "NNode",
    }
    planets_en = {}
    for cn, en in planet_map.items():
        if cn in data["planets"]:
            planets_en[en] = data["planets"][cn]

    chart_data = {
        "planets": planets_en,
        "cusps": data["cusps"],
    }
    chart_json = json.dumps(chart_data)
    title = f"{data['datetime']} (TZ={data['tz']:+g}) · {data['house_system']}"

    with open(ASTROCHART_JS, "r", encoding="utf-8") as f:
        astro_js = f.read()

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8">
<title>{title}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Microsoft YaHei','SimHei',sans-serif;background:#fff;color:#333;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.wrapper{{display:flex;max-width:960px;width:100%;gap:0}}
.sidebar{{width:260px;padding:20px 16px;background:#f8f8f8;font-size:13px;line-height:1.7;display:flex;flex-direction:column;gap:10px}}
.sidebar h2{{font-size:16px;margin-bottom:4px;border-bottom:2px solid #ccc;padding-bottom:4px}}
.sidebar .row{{display:flex;justify-content:space-between}}
.sidebar .lbl{{color:#666}}
.chart-area{{flex:1;display:flex;align-items:center;justify-content:center}}
</style>
</head>
<body>
<div class="wrapper">
<div class="sidebar">
<h2>星盘数据</h2>
<div class="row"><span class="lbl">日期</span><span>{data['datetime']}</span></div>
<div class="row"><span class="lbl">宫位制</span><span>{data['house_system']}</span></div>
<div class="row"><span class="lbl">模式</span><span>{data['mode']}</span></div>
<div class="row"><span class="lbl">纬度</span><span>{data['lat']:.4f}</span></div>
<div class="row"><span class="lbl">经度</span><span>{data['lon']:.4f}</span></div>
<div class="row"><span class="lbl">ASC</span><span>{data['asc']:.2f}°</span></div>
<div class="row"><span class="lbl">MC</span><span>{data['mc']:.2f}°</span></div>
<h2>行星经度</h2>
"""
    for cn, en in planet_map.items():
        if cn in data["planets"]:
            val = data["planets"][cn]
            degree = val[0]
            retro = " ℞" if (len(val) > 1 and val[1] < 0) else ""
            html += f'<div class="row"><span class="lbl">{cn}</span><span>{degree:.2f}°{retro}</span></div>\n'

    html += f"""</div>
<div class="chart-area"><div id="paper"></div></div>
</div>
<script>
var data = {chart_json};
</script>
<script>{astro_js}</script>
<script>
window.onload = function() {{
  var size = {size};
  var chart = new astrochart.Chart('paper', size, size);
  var radix = chart.radix(data);
  radix.addPointsOfInterest({{
    "As": [data.cusps[0]],
    "Ds": [data.cusps[6]],
    "Mc": [data.cusps[9]],
    "Ic": [data.cusps[3]]
  }});
  radix.aspects();
}};
</script>
</body>
</html>"""
    return html


def html_to_png(html_path, png_path, size=700):
    """调用 puppeteer 将 HTML 截图保存为 PNG"""
    cmd = [sys.executable]  # 用 node 而非 python
    # 实际用 node 跑 capture.js
    cmd = [
        "node",
        CAPTURE_JS,
        html_path,
        png_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"截图失败: {result.stderr}\n{result.stdout}")
    return png_path


def main():
    ap = argparse.ArgumentParser(description="星盘渲染：排盘→HTML→PNG")
    ap.add_argument("--time", required=True, help="本地时间 YYYY-MM-DD HH:MM")
    ap.add_argument("--tz", type=float, required=True, help="时区，东为正")
    ap.add_argument("--city", required=True, help="城市名")
    ap.add_argument("--out", help="输出 PNG 文件路径")
    ap.add_argument("--html", help="仅输出 HTML 文件路径")
    ap.add_argument("--size", type=int, default=700, help="星盘尺寸（默认700）")
    args = ap.parse_args()

    # Step 1: 排盘
    print("排盘中...")
    data = cast_json(args.time, args.tz, args.city)

    # Step 2: 生成 HTML
    html = build_html(data, size=args.size)
    html_path = args.html or os.path.join(os.getcwd(), "chart_out.html")

    # 如果 --html 给了路径，写到指定路径
    if args.html:
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML 已写入: {args.html}")

    if args.out:
        # 写临时 HTML
        tmp_html = os.path.join(os.getcwd(), ".chart_tmp.html")
        with open(tmp_html, "w", encoding="utf-8") as f:
            f.write(html)
        print("截图中...")
        html_to_png(tmp_html, args.out, size=args.size)
        print(f"PNG 已写入: {args.out}")
        # 清理临时 HTML
        os.remove(tmp_html)
    elif not args.html:
        # 没有指定任何输出，打印 JSON
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
