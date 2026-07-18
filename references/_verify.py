# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import swisseph as swe

# Xiamen 2026-07-17 22:00 TZ+8
lat, lon, tz = 24.48, 118.09, 8
y,mo,d,h,mi = 2026,7,17,22,0
ut = h - tz + mi/60.0
jd = swe.julday(y,mo,d,ut)

SIGNS = ["白羊","金牛","双子","巨蟹","狮子","处女","天秤","天蝎","射手","摩羯","水瓶","双鱼"]

cusps, angles = swe.houses(jd, lat, lon, b'R')
asc = angles[0]; mc = angles[1]

def sign_of(lon): return SIGNS[int(lon//30)]
def deg_in(lon): return lon - int(lon//30)*30
def house_of(lon):
    for i in range(12):
        s=cusps[i]; e=cusps[(i+1)%12]
        if e>s:
            if s<=lon<e: return i+1
        else:
            if lon>=s or lon<e: return i+1
    return 1

classical = {0:"太阳",1:"月亮",2:"水星",3:"金星",4:"火星",5:"木星",6:"土星"}
data = {}
for pid,name in classical.items():
    xx = swe.calc_ut(jd, pid)
    lon_p = xx[0][0]; speed = xx[0][3]
    data[name] = (lon_p, speed < 0, speed)

print("=== 行星精确数据 ===")
for name in classical.values():
    lon_p, rx, speed = data[name]
    print(f"{name}: {sign_of(lon_p)} {deg_in(lon_p):.4f}°  落第{house_of(lon_p)}宫  {'逆行' if rx else '顺行'}  (日速: {speed:.4f}°/d)")

# Key significators
jup_lon = data["木星"][0]  # Lord 1
merc_lon = data["水星"][0]  # Lord 7
moon_lon = data["月亮"][0]  # co-sig
venus_lon = data["金星"][0]  # Lord 2
mars_lon = data["火星"][0]  # Lord 8
sun_lon = data["太阳"][0]
sat_lon = data["土星"][0]

def asp_angle(a,b):
    d = abs(a-b) % 360
    return min(d, 360-d)

majors = {0:"合",60:"六合",90:"刑",120:"拱",180:"冲"}

print("\n=== 关键相位 ===")
pairs = [
    ("木星(1宫主)", jup_lon, "水星(7宫主/客户)", merc_lon),
    ("月亮(共同征象)", moon_lon, "水星(7宫主/客户)", merc_lon),
    ("月亮(共同征象)", moon_lon, "木星(1宫主)", jup_lon),
    ("金星(2宫主/💰)", venus_lon, "木星(1宫主)", jup_lon),
    ("火星(8宫主/客户钱)", mars_lon, "木星(1宫主)", jup_lon),
    ("水星(7宫主)", merc_lon, "金星(2宫主)", venus_lon),
]
for nm1, lon1, nm2, lon2 in pairs:
    ang = asp_angle(lon1, lon2)
    best = min(majors, key=lambda m: abs(ang-m))
    diff = abs(ang-best)
    print(f"  {nm1} vs {nm2}: 夹角 {ang:.2f}°, 最近 {majors[best]}({best}°), 偏差 {diff:.2f}°")

# Moon's next aspects before leaving Virgo
moon_sign_start = int(moon_lon//30) * 30
moon_sign_end = moon_sign_start + 30
print(f"\n=== 月亮离座前入相位(月亮在{sign_of(moon_lon)}，离座需到 {moon_sign_end}°) ===")
moon_speed = data["月亮"][2]
void = True
for name in classical.values():
    if name=="月亮": continue
    p_lon, rx, speed = data[name]
    for maj in majors:
        for target_dir in [maj, 360-maj]:
            target = moon_lon + target_dir
            if target <= moon_sign_end + 0.5:
                a = abs(asp_angle(target, p_lon) - maj)
                if a < 0.5:  # within half a degree of perfect aspect
                    # account for planet motion
                    moon_to_target = target - moon_lon
                    # time for moon to reach target = moon_to_target / moon_speed
                    # in that time, planet moves planet_speed * time
                    # effective aspect distance
                    eff_dist = moon_to_target
                    if abs(moon_speed - speed) > 1e-9:
                        eff_dist = moon_to_target * abs(moon_speed) / abs(moon_speed - speed)
                    print(f"  月亮将{'' if rx else ''}与 {name} 成{majors[maj]}({maj}°) 在 {sign_of(target)} {deg_in(target):.2f}° (有效距离约{eff_dist:.1f}°)")
                    void=False
if void:
    print("  月亮在离座前不与任何古典行星成精确主相位 → 空亡")

# Check combustion
print("\n=== 燃烧检查 ===")
for name in classical.values():
    lon_p, rx, speed = data[name]
    d = asp_angle(lon_p, sun_lon)
    if d < 8.5 and name != "太阳":
        print(f"  {name}: 距太阳 {d:.2f}° (<8.5°) → 燃烧(combust)")
    elif d < 17 and d >= 8.5 and name != "太阳":
        print(f"  {name}: 距太阳 {d:.2f}° → 日光下(sub radiis)")

# Receptions - basic
print("\n=== 接纳关系(简易) ===")
# Dignities table simplified
dignities = {
    "太阳": {"rulership":["狮子"], "exaltation":["白羊"], "detriment":["水瓶"], "fall":["天秤"]},
    "月亮": {"rulership":["巨蟹"], "exaltation":["金牛"], "detriment":["摩羯"], "fall":["天蝎"]},
    "水星": {"rulership":["双子","处女"], "exaltation":["处女"], "detriment":["射手","双鱼"], "fall":["双鱼"]},
    "金星": {"rulership":["金牛","天秤"], "exaltation":["双鱼"], "detriment":["天蝎","白羊"], "fall":["处女"]},
    "火星": {"rulership":["白羊","天蝎"], "exaltation":["摩羯"], "detriment":["天秤","金牛"], "fall":["巨蟹"]},
    "木星": {"rulership":["射手","双鱼"], "exaltation":["巨蟹"], "detriment":["双子","处女"], "fall":["摩羯"]},
    "土星": {"rulership":["摩羯","水瓶"], "exaltation":["天秤"], "detriment":["巨蟹","狮子"], "fall":["白羊"]},
}
for nm1 in classical.values():
    lon1, rx1, sp1 = data[nm1]
    s1 = sign_of(lon1)
    for nm2 in classical.values():
        if nm1==nm2: continue
        d = dignities[nm2]
        for cat, signs in d.items():
            if s1 in signs:
                print(f"  {nm1}(在{s1}) 于 {nm2} 的 {cat}")

# Saturn 1H, Venus state
print("\n=== 特殊状态 ===")
v_s = sign_of(venus_lon)
print(f"  金星(2宫主): {v_s} {deg_in(venus_lon):.2f}° 落第{house_of(venus_lon)}宫 → 弱势(fall:{'是' if v_s in dignities['金星']['fall'] else '否'})")
s_s = sign_of(sat_lon)
print(f"  土星: {s_s} {deg_in(sat_lon):.2f}° 落第{house_of(sat_lon)}宫 → 弱势(fall:{'是' if s_s in dignities['土星']['fall'] else '否'})")
j_s = sign_of(jup_lon)
print(f"  木星(1宫主): {j_s} {deg_in(jup_lon):.2f}° 落第{house_of(jup_lon)}宫 → 失势(detriment:{'是' if j_s in dignities['木星']['detriment'] else '否'}), 弱势(fall:{'是' if j_s in dignities['木星']['fall'] else '否'})")
# triplicity check: Jupiter in fire at night
print(f"  木星在狮子(火象/夜生盘): 三分为木星 → 三分守护(小尊贵)")

# Moon triplicity
m_s = sign_of(moon_lon)
print(f"  月亮在{m_s}(土象/夜生盘): 三分为月亮 → 三分守护(小尊贵)")

# 5H house matters
print(f"\n  木星+水星+太阳同落第5宫 → 创意/投机/展示之宫")
print(f"  月亮+金星同落第6宫 → 劳作/服务/日常之宫")
print(f"  3宫主=水星, 3宫=双子/水星 → 广告/沟通由水星(即7宫主)管")
