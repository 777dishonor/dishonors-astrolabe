#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
星盘可视化 v4 — 全面修复版
修复项：
  1. CJK 字体自动检测（微软雅黑/SimHei），消除方框
  2. 行星去重叠从「同宫位内」升级为「全局角度聚类」
  3. 四角判定防御：mc 字段与 cusps[9] 不一致时以 cusps 为准
  4. 宫位数字位置优化（更靠内圈，居中显示）
  5. 整体代码重构为模块化架构
"""

import json
import math
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patches as patches
from matplotlib.patches import Circle, Wedge
import numpy as np

# ── 占星符号 ──────────────────────────────────────────────

PLANET_SYMBOLS = {
    'Sun': '☉', 'Moon': '☽', 'Mercury': '☿', 'Venus': '♀',
    'Mars': '♂', 'Jupiter': '♃', 'Saturn': '♄',
    'Uranus': '♅', 'Neptune': '♆', 'Pluto': '♇',
    'North Node': '☊', 'South Node': '☋',
    'Asc': 'ASC', 'MC': 'MC', 'Desc': 'DSC', 'IC': 'IC',
}

SIGN_SYMBOLS = {
    'Aries': '♈', 'Taurus': '♉', 'Gemini': '♊', 'Cancer': '♋',
    'Leo': '♌', 'Virgo': '♍', 'Libra': '♎', 'Scorpio': '♏',
    'Sagittarius': '♐', 'Capricorn': '♑', 'Aquarius': '♒', 'Pisces': '♓',
}

SIGN_NAMES = [
    'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
    'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces',
]


# ═══════════════════════════════════════════════════════════
#  字体管理（修复项 #1）
# ═══════════════════════════════════════════════════════════

def _find_cjk_font():
    """检测系统中可用的 CJK 字体，返回 FontProperties 或 None"""
    # 按优先级排列
    candidates = [
        'Microsoft YaHei',          # Windows 10/11 首选
        'SimHei',                   # Windows 黑体（备用）
        'Noto Sans CJK SC',         # Linux
        'WenQuanYi Micro Hei',      # Linux 备用
        'PingFang SC',              # macOS
        'Hiragino Sans GB',         # macOS 备用
    ]

    # 重建字体缓存，确保检测到新安装的字体
    try:
        fm._load_fontmanager(try_read_cache=False)
    except Exception:
        pass

    for name in candidates:
        for f in fm.fontManager.ttflist:
            if f.name == name and os.path.exists(f.fname):
                return fm.FontProperties(fname=f.fname)

    # 兜底：直接扫描系统字体目录
    font_dirs = [
        r'C:\Windows\Fonts',
        '/usr/share/fonts',
        '/System/Library/Fonts',
        os.path.expanduser('~/.fonts'),
    ]
    for d in font_dirs:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for fn in files:
                lower = fn.lower()
                if any(k in lower for k in ['msyh', 'simhei', 'yahei', 'noto', 'cjk', 'wenquan']):
                    if fn.endswith(('.ttf', '.ttc', '.otf')):
                        path = os.path.join(root, fn)
                        return fm.FontProperties(fname=path)
            break  # 只扫一层

    return None


# 模块级单例
_cjk_font = None


def get_cjk_font():
    """获取 CJK 字体（惰性加载）"""
    global _cjk_font
    if _cjk_font is None:
        _cjk_font = _find_cjk_font()
    return _cjk_font


def apply_cjk_rcparams():
    """将 CJK 字体设为 matplotlib 全局默认"""
    font = get_cjk_font()
    if font is None:
        return
    fp = font  # FontProperties
    # 尝试通过 rcParams 生效
    try:
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.sans-serif'] = [fp.get_name()]
    except Exception:
        pass
    # 同时通过 font_manager 注册
    try:
        fm.fontManager.addfont(fp.get_file())
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.sans-serif'] = [fp.get_name()]
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════
#  基础工具函数
# ═══════════════════════════════════════════════════════════

def load_chart_data(json_path):
    """加载星盘 JSON（处理 BOM）"""
    with open(json_path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)


def zodiac_pos_to_angle(zodiac_pos, asc_degree):
    """黄经 → matplotlib 极坐标角度（Asc 锚定在左侧 180°）"""
    relative = (zodiac_pos - asc_degree) % 360
    return (180 + relative) % 360


def polar_to_cartesian(angle_deg, radius, center=(0.0, 0.0)):
    """极坐标 → 笛卡尔坐标"""
    rad = math.radians(angle_deg)
    return (center[0] + radius * math.cos(rad),
            center[1] + radius * math.sin(rad))


def format_degree(degree):
    """浮点度数 → D°MM' 格式"""
    d = int(degree)
    m = int(round((degree - d) * 60))
    if m == 60:
        d += 1
        m = 0
    return f"{d}°{m:02d}'"


def get_sign(degree):
    """度数 → 星座名"""
    return SIGN_NAMES[int(degree / 30) % 12]


def determine_house(lon, cusps):
    """判断黄经属于哪个宫位（1-12）"""
    for i in range(12):
        start = cusps[i]
        end = cusps[(i + 1) % 12]
        if end < start:  # 跨 0°
            if lon >= start or lon < end:
                return i + 1
        else:
            if start <= lon < end:
                return i + 1
    return 1  # 兜底


# ═══════════════════════════════════════════════════════════
#  绘制组件
# ═══════════════════════════════════════════════════════════

def draw_zodiac_wheel(ax, outer_r, inner_r, asc_degree, font):
    """外圈星座环（符号 + 刻度）"""
    for i, sign in enumerate(SIGN_NAMES):
        sign_start = i * 30
        sign_end = (i + 1) * 30

        end_angle = zodiac_pos_to_angle(sign_end, asc_degree)
        start_angle = zodiac_pos_to_angle(sign_start, asc_degree)
        if end_angle < start_angle:
            end_angle += 360

        # 星座楔形
        wedge = Wedge((0, 0), outer_r, start_angle, end_angle,
                      width=outer_r - inner_r,
                      facecolor='white', edgecolor='black', linewidth=0.5)
        ax.add_patch(wedge)

        # 星座符号（Unicode，不需要 CJK 字体）
        mid_angle = (start_angle + end_angle) / 2
        if mid_angle > 360:
            mid_angle -= 360
        x, y = polar_to_cartesian(mid_angle, (outer_r + inner_r) / 2)
        ax.text(x, y, SIGN_SYMBOLS[sign], ha='center', va='center',
                fontsize=16, fontweight='bold')

        # 度数刻度（每 10°）
        for deg in (10, 20):
            tick_lon = sign_start + deg
            tick_angle = zodiac_pos_to_angle(tick_lon, asc_degree)
            x1, y1 = polar_to_cartesian(tick_angle, outer_r + 0.015)
            x2, y2 = polar_to_cartesian(tick_angle, outer_r - 0.015)
            ax.plot([x1, x2], [y1, y2], 'k-', linewidth=0.4, alpha=0.6)


def draw_house_wedges(ax, cusps, house_r, font):
    """宫位区域 + 宫位数字（修复项 #4：数字靠内圈居中）"""
    asc_degree = cusps[0]
    for i in range(12):
        hnum = i + 1
        start_angle = zodiac_pos_to_angle(cusps[i], asc_degree)
        end_angle = zodiac_pos_to_angle(cusps[(i + 1) % 12], asc_degree)
        if end_angle < start_angle:
            end_angle += 360

        # 宫位区域（淡灰边框）
        wedge = Wedge((0, 0), house_r, start_angle, end_angle,
                      facecolor='white', edgecolor='#AAAAAA',
                      linewidth=0.5, alpha=0.3)
        ax.add_patch(wedge)

        # —— 宫位数字：宫位中心，靠内圈 ——
        # 用扇形几何中心的角度
        # 对于扇形，中心角度 = start + width/2
        # 径向位置放内圈：house_r * 0.30（更靠内，给行星留空间）
        mid_angle = start_angle + (end_angle - start_angle) / 2
        if mid_angle > 360:
            mid_angle -= 360

        # 数字放在半径的 30% 处（内圈）
        num_r = house_r * 0.30
        x, y = polar_to_cartesian(mid_angle, num_r)

        # 使用 CJK 字体（如果可用），否则 fallback 到默认
        kw = {'ha': 'center', 'va': 'center', 'fontsize': 10,
              'fontweight': 'bold', 'color': '#3767a8'}
        if font:
            kw['fontproperties'] = font

        ax.text(x, y, str(hnum), **kw)


def draw_house_cusps(ax, cusps, outer_r):
    """宫头线（四轴加粗）"""
    asc_degree = cusps[0]
    axes_idx = {0, 3, 6, 9}  # Asc/IC/Desc/MC
    for i, cusp in enumerate(cusps):
        angle = zodiac_pos_to_angle(cusp, asc_degree)
        x, y = polar_to_cartesian(angle, outer_r)
        lw = 1.0 if i in axes_idx else 0.5
        ax.plot([0, x], [0, y], 'k-', linewidth=lw, alpha=0.7 if i in axes_idx else 0.5)


def draw_four_angles(ax, cusps, chart_data, outer_r, font):
    """四角标注（修复项 #3：防御 mc 字段不一致）

    在 Regiomontanus 宫中，四角 = 对应宫头：
      Asc  = cusps[0]  (1宫头)
      MC   = cusps[9]  (10宫头)
      Desc = cusps[6]  (7宫头)
      IC   = cusps[3]  (4宫头)

    如果 chart_data 中有独立的 ascendant/mc 字段且与 cusps 一致则用，
    否则以 cusps 为准（cusps 是确定宫位边界的官方数据）。
    """
    asc_degree = cusps[0]

    # 从 JSON 读取精确值（如果有），否则用 cusps
    asc_val = chart_data.get('ascendant', cusps[0])
    mc_val = chart_data.get('mc', cusps[9])

    # 防御：如果 mc 字段与 cusps[9] 差异 >5°，以 cusps 为准
    mc_cusp = cusps[9]
    if abs(mc_val - mc_cusp) > 5.0:
        mc_val = mc_cusp

    angles = [
        ('ASC', asc_val, cusps[0]),
        ('MC',  mc_val,  cusps[9]),
        ('DSC', cusps[6], cusps[6]),
        ('IC',  cusps[3], cusps[3]),
    ]

    for label, degree, _cusp in angles:
        angle = zodiac_pos_to_angle(degree, asc_degree)

        # 标注文字（外圈外侧）
        x_label, y_label = polar_to_cartesian(angle, outer_r + 0.08)
        kw = {'ha': 'center', 'va': 'center', 'fontsize': 9,
              'fontweight': 'bold', 'color': '#1a4080'}
        if font:
            kw['fontproperties'] = font
        ax.text(x_label, y_label, label, **kw)

        # 度数文字
        x_deg, y_deg = polar_to_cartesian(angle, outer_r + 0.15)
        kw2 = {'ha': 'center', 'va': 'center', 'fontsize': 7, 'color': 'black'}
        if font:
            kw2['fontproperties'] = font
        ax.text(x_deg, y_deg, format_degree(degree % 30), **kw2)


def draw_planets(ax, planets, retro_data, cusps, house_r, font):
    """绘制行星 — 全局去重叠（修复项 #2）

    算法：
      1. 所有行星按图上角度排序
      2. 相邻角度差 < 阈值 → 归入同一「碰撞簇」
      3. 簇内行星按径向交替错开，保证标签/符号不重叠
    """
    asc_degree = cusps[0]
    OVERLAP_THRESHOLD = 4.0   # 角度差阈值（度）
    RADIUS_STEP = 0.07        # 径向错开步长

    base_radius = house_r * 0.62

    # ── Step 1: 收集所有行星 ──
    entries = []
    for name, lon in planets.items():
        if name in ('Asc', 'MC', 'Desc', 'IC'):
            continue
        angle = zodiac_pos_to_angle(lon, asc_degree)
        entries.append({
            'name': name,
            'lon': lon,
            'angle': angle,
            'retro': retro_data.get(name, False),
            'radius': base_radius,
        })

    if not entries:
        return

    # ── Step 2: 按图上角度排序 ──
    entries.sort(key=lambda e: e['angle'])

    # ── Step 3: 碰撞聚类 ──
    clusters = []
    current = [entries[0]]
    for i in range(1, len(entries)):
        prev_angle = entries[i - 1]['angle']
        curr_angle = entries[i]['angle']
        diff = abs(curr_angle - prev_angle)
        # 处理环状回绕
        if diff > 180:
            diff = 360 - diff
        if diff < OVERLAP_THRESHOLD:
            current.append(entries[i])
        else:
            if len(current) > 1:
                clusters.append(current)
            current = [entries[i]]

    # 处理最后一个簇 + 环状首尾碰撞
    if len(current) > 1:
        clusters.append(current)

    # 检查首尾（entries[0] 和 entries[-1] 跨越 0°/360° 边界）
    if entries[0] not in (current if len(current) > 1 else []):
        first_angle = entries[0]['angle']
        last_angle = entries[-1]['angle']
        diff = (first_angle + 360) - last_angle
        if diff < OVERLAP_THRESHOLD and len(entries) >= 2:
            # 合并首尾行星所在的簇
            # 检查 entries[0] 是否已在某个簇中
            in_first_cluster = any(entries[0] in c for c in clusters)
            in_last_cluster = any(entries[-1] in c for c in clusters)
            if in_first_cluster and in_last_cluster:
                # 两个簇要合并
                c1 = next(c for c in clusters if entries[0] in c)
                c2 = next(c for c in clusters if entries[-1] in c)
                if c1 is not c2:
                    c1.extend(c2)
                    clusters.remove(c2)
            elif not in_first_cluster and not in_last_cluster:
                clusters.append([entries[0], entries[-1]])

    # ── Step 4: 簇内径向错开 ──
    for cluster in clusters:
        n = len(cluster)
        for idx, entry in enumerate(cluster):
            # 对称分布：中间行星在 base_radius，两头交替内外
            offset = (idx - (n - 1) / 2) * RADIUS_STEP
            entry['radius'] = base_radius - offset

    # ── Step 5: 绘制 ──
    z_base = 10
    for idx, entry in enumerate(entries):
        angle = entry['angle']
        r = entry['radius']
        z = z_base + idx * 2

        x, y = polar_to_cartesian(angle, r)

        # 行星符号
        symbol = PLANET_SYMBOLS.get(entry['name'], entry['name'][:2])
        if entry['retro']:
            symbol += ' R'
        ax.text(x, y, symbol, ha='center', va='center',
                fontsize=11, fontweight='bold', color='#8b0000',
                bbox=dict(boxstyle='circle,pad=0.06', facecolor='white',
                          edgecolor='#8b0000', linewidth=0.8),
                zorder=z)
        z += 1

        # 度数标签 — 根据角度选位置
        deg_text = format_degree(entry['lon'] % 30)
        deg_r_offset = 0.09  # 标签离符号的距离

        a = angle % 360
        if 45 < a < 135:       # 右侧 → 标签在内侧（左）
            deg_r = r - deg_r_offset
            va = 'center'
        elif 225 < a < 315:    # 左侧 → 标签在外侧（右）
            deg_r = r + deg_r_offset
            va = 'center'
        elif 135 <= a <= 225:  # 下方 → 标签在上面
            deg_r = r
            va = 'bottom'
        else:                  # 上方 → 标签在下面
            deg_r = r
            va = 'top'

        dx, dy = polar_to_cartesian(angle, deg_r)
        kw = {'ha': 'center', 'va': va, 'fontsize': 6.5,
              'color': '#333333', 'zorder': z}
        if font:
            kw['fontproperties'] = font
        ax.text(dx, dy, deg_text, **kw)


def draw_aspect_grid(ax, aspects, inner_r):
    """中心相位圈（装饰性）"""
    circle = Circle((0, 0), inner_r * 0.35, fill=False,
                    edgecolor='#CCCCCC', linewidth=0.8, linestyle='--', alpha=0.5)
    ax.add_patch(circle)


def draw_left_table(ax_left, chart_data, font):
    """左侧行星数据表（修复项 #1：使用 CJK 字体）"""
    planets = chart_data.get('planets', {})
    retro_data = chart_data.get('retrograde', {})

    planet_order = [
        'Sun', 'Moon', 'Mercury', 'Venus', 'Mars',
        'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto',
        'North Node', 'South Node',
    ]

    ax_left.axis('off')
    ax_left.set_xlim(0, 1)
    ax_left.set_ylim(0, 1)

    # 标题
    kw_title = {'ha': 'center', 'va': 'top', 'fontsize': 12,
                'fontweight': 'bold', 'transform': ax_left.transAxes}
    if font:
        kw_title['fontproperties'] = font
    ax_left.text(0.5, 0.97, 'Planets', **kw_title)

    # 表头
    headers = ['Planet', 'Sign', 'Deg', 'R']
    x_pos = [0.08, 0.24, 0.40, 0.56]
    y0 = 0.90
    row_h = 0.042

    kw_hdr = {'ha': 'left', 'va': 'top', 'fontsize': 9,
              'fontweight': 'bold', 'transform': ax_left.transAxes}
    if font:
        kw_hdr['fontproperties'] = font
    for ci, h in enumerate(headers):
        ax_left.text(x_pos[ci], y0, h, **kw_hdr)

    # 数据行
    kw_row = {'ha': 'left', 'va': 'top', 'fontsize': 8.5,
              'transform': ax_left.transAxes}

    row_idx = 0
    # 行星
    for pname in planet_order:
        if pname not in planets:
            continue
        lon = planets[pname]
        sign = get_sign(lon)
        deg = format_degree(lon % 30)
        ret = 'R' if retro_data.get(pname) else ''

        sym = PLANET_SYMBOLS.get(pname, pname)
        sign_sym = SIGN_SYMBOLS.get(sign, sign[:3])

        y = y0 - (row_idx + 1) * row_h
        if y < 0.05:
            break

        cells = [sym, sign_sym, deg, ret]
        for ci, cell in enumerate(cells):
            ax_left.text(x_pos[ci], y, cell, **kw_row)
        row_idx += 1

    # 四角
    cusps = chart_data.get('cusps', [0] * 12)
    asc_val = chart_data.get('ascendant', cusps[0])
    mc_val = chart_data.get('mc', cusps[9])
    if abs(mc_val - cusps[9]) > 5.0:
        mc_val = cusps[9]

    angle_entries = [
        ('ASC', asc_val),
        ('MC',  mc_val),
        ('DSC', cusps[6]),
        ('IC',  cusps[3]),
    ]
    for label, lon in angle_entries:
        y = y0 - (row_idx + 1) * row_h
        if y < 0.05:
            break
        sign = get_sign(lon)
        deg = format_degree(lon % 30)
        sign_sym = SIGN_SYMBOLS.get(sign, sign[:3])
        cells = [label, sign_sym, deg, '']
        for ci, cell in enumerate(cells):
            ax_left.text(x_pos[ci], y, cell, **kw_row)
        row_idx += 1


# ═══════════════════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════════════════

def draw_chart(chart_data, output_path='chart_v4.png'):
    """主绘制函数"""
    # ── 字体 ──
    cjk = get_cjk_font()
    if cjk is None:
        print("[draw_chart] ⚠ CJK font not found — non-ASCII text may display as boxes")
    else:
        print(f"[draw_chart] CJK font: {cjk.get_name()} ({cjk.get_file()})")

    # ── 画布 ──
    fig = plt.figure(figsize=(14, 10))

    ax_left = fig.add_axes([0.02, 0.10, 0.25, 0.80])
    ax_chart = fig.add_axes([0.30, 0.05, 0.65, 0.90])

    ax_chart.set_xlim(-1.3, 1.3)
    ax_chart.set_ylim(-1.3, 1.3)
    ax_chart.set_aspect('equal')
    ax_chart.axis('off')

    # ── 半径参数 ──
    outer_r = 1.00    # 星座外圈
    zodiac_r = 0.84   # 星座符号圈
    house_r = 0.73    # 宫位圈
    inner_r = 0.22    # 中心圈

    cusps = chart_data.get('cusps', [0] * 12)
    planets = chart_data.get('planets', {})
    asc_degree = cusps[0] if cusps[0] else 0

    # ── 绘制层次（由外到内） ──
    draw_zodiac_wheel(ax_chart, outer_r, zodiac_r, asc_degree, cjk)
    draw_house_wedges(ax_chart, cusps, house_r, cjk)
    draw_house_cusps(ax_chart, cusps, house_r)
    draw_planets(ax_chart, planets, chart_data.get('retrograde', {}),
                 cusps, house_r, cjk)
    draw_four_angles(ax_chart, cusps, chart_data, outer_r, cjk)
    draw_aspect_grid(ax_chart, chart_data.get('aspects', []), inner_r)

    # ── 左侧表格 ──
    draw_left_table(ax_left, chart_data, cjk)

    # ── 图表标题 ──
    date_str = chart_data.get('time', '')
    chart_type = chart_data.get('chart_type', 'Natal')
    kw = {'fontsize': 12, 'fontweight': 'bold'}
    if cjk:
        kw['fontproperties'] = cjk
    fig.suptitle(f'{chart_type} Chart', **kw, y=0.98)
    if date_str:
        kw2 = {'fontsize': 9, 'color': '#555555'}
        if cjk:
            kw2['fontproperties'] = cjk
        fig.text(0.5, 0.94, date_str, ha='center', **kw2)

    # ── 输出 ──
    plt.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    print(f"[draw_chart] Saved: {output_path}")


# ═══════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    json_path = sys.argv[1] if len(sys.argv) > 1 else 'test_chart.json'
    out_path = sys.argv[2] if len(sys.argv) > 2 else 'chart_v4.png'
    chart_data = load_chart_data(json_path)
    draw_chart(chart_data, out_path)
