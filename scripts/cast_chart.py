# -*- coding: utf-8 -*-
"""
古典占星排盘引擎（基于 pyswisseph 底层 API）
- 卜卦模式（默认）：Regiomontanus 宫位制
- 本命模式（--mode natal）：Placidus 宫位制
用法:
  python3 cast_chart.py --time "2024-01-01 12:00" --tz 8 --city 北京
  python3 cast_chart.py --time "1990-05-15 08:30" --tz 8 --city 北京 --mode natal
  python3 cast_chart.py --time "2024-01-01 12:00" --tz 8 --lat 39.908 --lon 116.397
  python3 cast_chart.py --time "2024-01-01 12:00" --tz 8 --city 北京 --out chart.txt
依赖: pyswisseph==2.10.3.2 (Swiss Ephemeris)
"""
import sys, argparse, codecs
import swisseph as swe

# Windows GBK 编码兼容：输出强制 UTF-8
if sys.stdout.encoding != "utf-8":
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
if sys.stderr.encoding != "utf-8":
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

SIGNS = ["白羊", "金牛", "双子", "巨蟹", "狮子", "处女",
         "天秤", "天蝎", "射手", "摩羯", "水瓶", "双鱼"]
PLANETS = [
    (0, "太阳"), (1, "月亮"), (2, "水星"), (3, "金星"), (4, "火星"),
    (5, "木星"), (6, "土星"), (7, "天王星"), (8, "海王星"), (9, "冥王星"),
    (10, "北交点"),
]
CLASSICAL = [0, 1, 2, 3, 4, 5, 6]  # 七曜，仅用于尊贵/相位

# === 古典尊贵体系 ===
# 入庙（domicile）：行星守护的星座
DOMICILE_SIGNS = {
    0: [4],          # 太阳 → 狮子
    1: [3],          # 月亮 → 巨蟹
    2: [2, 5],       # 水星 → 双子、处女
    3: [1, 6],       # 金星 → 金牛、天秤
    4: [0, 7],       # 火星 → 白羊、天蝎
    5: [8, 11],      # 木星 → 射手、双鱼
    6: [9, 10],      # 土星 → 摩羯、水瓶
}
# 擢升（exaltation）：(星座索引, 精确度数)
EXALTATION = {
    0: (0, 19),      # 太阳 19° 白羊
    1: (1, 3),       # 月亮 3° 金牛
    2: (5, 15),      # 水星 15° 处女
    3: (11, 27),     # 金星 27° 双鱼
    4: (9, 28),      # 火星 28° 摩羯
    5: (3, 15),      # 木星 15° 巨蟹
    6: (6, 21),      # 土星 21° 天秤
}
# 失势（detriment）= domicile 对面星座
# 落陷（fall）= exaltation 对面：星座=(exaltation_sign+6)%12，度数=exaltation_degree

# 宫头星座 → 守护星（传统七曜）
SIGN_RULER = {
    0: 4, 1: 3, 2: 2, 3: 1, 4: 0, 5: 2,
    6: 3, 7: 4, 8: 5, 9: 6, 10: 6, 11: 5,
}
RULER_NAMES = {0: "太阳", 1: "月亮", 2: "水星", 3: "金星", 4: "火星", 5: "木星", 6: "土星"}

# 相位弧与容许度
ASPECTS = [
    (0, "合", 8.0),
    (60, "六合", 6.0),
    (90, "刑", 7.0),
    (120, "拱", 8.0),
    (180, "冲", 8.0),
]

try:
    from cities import lookup as city_lookup
except ImportError:
    sys.path.insert(0, __file__.rsplit("\\", 1)[0])
    from cities import lookup as city_lookup


def lon_to_sign_dms(lon):
    sign = int(lon // 30)
    rel = lon - sign * 30
    deg = int(rel)
    minute = int(round((rel - deg) * 60))
    if minute == 60:
        deg += 1; minute = 0
    return SIGNS[sign], deg, minute


def house_of(lon, cusps):
    for i in range(12):
        start = cusps[i]
        end = cusps[(i + 1) % 12]
        if end > start:
            if start <= lon < end:
                return i + 1
        else:
            if lon >= start or lon < end:
                return i + 1
    return 1


def essential_dignity(pid, lon):
    """返回古典尊贵状态字符串。七曜专用，三王星/北交点返回 '-'。"""
    if pid not in CLASSICAL:
        return "-"
    sign_idx = int(lon // 30)
    deg_in_sign = lon - sign_idx * 30
    states = []
    # 入庙
    if sign_idx in DOMICILE_SIGNS.get(pid, []):
        states.append("入庙")
    # 擢升
    ex_info = EXALTATION.get(pid)
    if ex_info and sign_idx == ex_info[0]:
        if deg_in_sign < ex_info[1]:
            states.append("擢升（度内）")
        else:
            states.append("擢升（度外）")
    # 失势 = 入庙对面
    detriment_signs = [(s + 6) % 12 for s in DOMICILE_SIGNS.get(pid, [])]
    if sign_idx in detriment_signs:
        states.append("失势")
    # 落陷 = 擢升对面
    if ex_info:
        fall_sign = (ex_info[0] + 6) % 12
        if sign_idx == fall_sign:
            if deg_in_sign < ex_info[1]:
                states.append("落陷")
            else:
                states.append("落陷（度外）")
    if not states:
        states.append("peregrine")
    return "、".join(states)


def compute_aspects(planet_lons):
    """计算七曜之间的相位，返回列表。"""
    lines = []
    for i, (pid_i, name_i, lon_i) in enumerate(planet_lons):
        if pid_i not in CLASSICAL:
            continue
        for j, (pid_j, name_j, lon_j) in enumerate(planet_lons):
            if j <= i or pid_j not in CLASSICAL:
                continue
            diff = abs(lon_i - lon_j)
            if diff > 180:
                diff = 360 - diff
            for arc, aspect_name, orb in ASPECTS:
                if abs(diff - arc) <= orb:
                    aorb = abs(diff - arc)
                    app_sep = "入相" if diff < arc else "（分离中）" if diff > arc else "（精准）"
                    lines.append("  %s %s %s  偏差 %.1f° %s" % (name_i, aspect_name, name_j, aorb, app_sep))
                    break  # 每对只记最接近的相位
    return lines


def ruler_of(sign_idx):
    """返回星座的七曜守护星名称。"""
    return RULER_NAMES.get(SIGN_RULER.get(sign_idx), "?")


def cast(year, month, day, hour, minute, tz, lat, lon, hsys=b'R', mode_label='卜卦'):
    ut_hour = hour - tz + minute / 60.0
    carry = 0
    if ut_hour < 0:
        ut_hour += 24; carry = -1
    elif ut_hour >= 24:
        ut_hour -= 24; carry = 1
    jd = swe.julday(year, month, day + carry, ut_hour)
    cusps, angles = swe.houses(jd, lat, lon, hsys)
    asc, mc = angles[0], angles[1]

    L = []
    hs_label = "Regiomontanus" if hsys == b'R' else "Placidus"
    L.append("=== %s星盘 (%s 宫位制) ===" % (mode_label, hs_label))
    L.append("时间(本地): %04d-%02d-%02d %02d:%02d (TZ=%+g)" % (year, month, day, hour, minute, tz))
    L.append("地点: 纬度 %.4f, 经度 %.4f" % (lat, lon))
    L.append("Julian Day: %.6f" % jd)
    L.append("")

    # 1) 宫头 + 守护星
    L.append("--- 📍 十二宫（宫头 + 宫主星） ---")
    for i in range(12):
        s, d, m = lon_to_sign_dms(cusps[i])
        sign_idx = int(cusps[i] // 30)
        r = ruler_of(sign_idx)
        L.append("  第%2d宫  %s %d°%d'  → 宫主：%s" % (i + 1, s, d, m, r))
    L.append("")
    a_s, a_d, a_m = lon_to_sign_dms(asc)
    m_s, m_d, m_m = lon_to_sign_dms(mc)
    L.append("  ASC: %s %d°%d'    MC: %s %d°%d'" % (a_s, a_d, a_m, m_s, m_d, m_m))
    L.append("")

    # 2) 行星：黄经 + 落宫 + 尊贵状态
    L.append("--- 🌟 行星（黄经 / 落宫 / 尊贵） ---")
    planet_data = []
    for pid, name in PLANETS:
        xx, _ = swe.calc_ut(jd, pid)
        lon_p = xx[0]
        s, d, m = lon_to_sign_dms(lon_p)
        h = house_of(lon_p, list(cusps))
        dign = essential_dignity(pid, lon_p)
        is_classical = "" if pid in CLASSICAL else "（非七曜）"
        L.append("  %-4s  %s %d°%d'  落第%d宫  [%s] %s" % (name, s, d, m, h, dign, is_classical))
        planet_data.append((pid, name, lon_p))
    L.append("")

    # 3) 相位（仅七曜之间）
    L.append("--- 🔗 七曜相位 ---")
    aspect_lines = compute_aspects(planet_data)
    if aspect_lines:
        for al in aspect_lines:
            L.append(al)
    else:
        L.append("  （无相位）")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--time", required=True, help="本地时间 YYYY-MM-DD HH:MM")
    ap.add_argument("--tz", type=float, required=True, help="时区，东为正，如北京时间填 8")
    ap.add_argument("--city", help="城市名(查表)")
    ap.add_argument("--lat", type=float, help="纬度(北纬正)")
    ap.add_argument("--lon", type=float, help="经度(东经正)")
    ap.add_argument("--out", help="输出文件(可选)")
    ap.add_argument("--mode", default="horary", choices=["horary", "natal"],
                    help="模式: horary(卜卦/Regiomontanus) 或 natal(本命/Placidus)")
    args = ap.parse_args()

    hsys = b'P' if args.mode == 'natal' else b'R'
    mode_label = '本命' if args.mode == 'natal' else '卜卦'

    lat, lon = args.lat, args.lon
    if args.city:
        c = city_lookup(args.city)
        if c is None:
            print("未知城市: %s (可在 cities.py 增补)" % args.city); sys.exit(2)
        lat, lon, tz_city = c
        if lat is None or lon is None:
            print("城市 %s 缺经纬度" % args.city); sys.exit(2)
    if lat is None or lon is None:
        print("必须提供 --city 或 --lat/--lon"); sys.exit(2)

    ymd, hm = args.time.split(" ")
    y, mo, d = map(int, ymd.split("-"))
    h, mi = map(int, hm.split(":"))
    res = cast(y, mo, d, h, mi, args.tz, lat, lon, hsys=hsys, mode_label=mode_label)
    print(res)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(res + "\n")
        print("[已写出到 %s]" % args.out)


if __name__ == "__main__":
    main()
