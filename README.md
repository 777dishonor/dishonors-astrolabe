# horary-calc · 古典占星排盘与判读（卜卦 & 本命）

一个 OpenClaw skill：给定「时间 + 地点」，用 Swiss Ephemeris 算出真实星盘（卜卦用 Regiomontanus 宫位制，本命用 Placidus），并**严格依据七库资料**的章节-段落索引逐条引用判读，产出标准化 md 报告。

七库资料：
- **卜卦六库**：Frawley《The Horary Textbook 乾坤 6.0版》+ 威廉·李利《基督占星》第一/二/三册选译 + 《Horary Examples翻译》（案例集）+ 《灵体攻击案例专题》。六者一并检索、互参印证，权重平等。
- **本命一库**：《莫林本命占星方法》（Morin 第21卷，易简占星译），覆盖天球决定、行星落宫与守护、多星同宫、相位、推运等全体系。

## 特性
- 真实排盘：基于 `pyswisseph`（Swiss Ephemeris 星历），非随机/象征性生成。
- 双模式：卜卦（Regiomontanus）、本命（Placidus）。`--mode natal` 切换。
- 判读有据：每条论断标注【出处】《<底本名>》「章节」段落N（原文行X-Y）+ 逐字摘引。底本名必须显式写出（七库之一），不得省略。
- 标准输出：固定五段式 md 报告（星盘数据 / 判断 / 依据 / 诚实声明）。
- 自包含：底本与索引已打包在 `references/`，开箱即用（七库）。

## 目录结构
```
horary-calc/
├── SKILL.md            # skill 触发条件、流程、引用铁律、交付铁律
├── TEMPLATE.md         # 报告模板
├── README.md           # 本文件
├── requirements.txt    # Python 依赖
├── scripts/
│   ├── cast_chart.py   # 排盘引擎（--mode natal 切换本命）
│   ├── cities.py       # 城市经纬度查表
│   ├── gen_report.py   # 报告生成器（套模板）
│   ├── build_index.py  # 为 6.0 版底本重建索引
│   ├── build_index_multi.py  # 为任意底本建独立索引
│   └── selfcheck.py    # 七库索引+依赖自检
└── references/
    ├── The Horary Textbook乾坤 6.0版.md   # 判读底本（Frawley 原文）
    ├── 基督占星第一册(Christian Astrology 1)选译.md   # 李利原典一
    ├── 基督占星第二册(Christian Astrology 2)选译.md   # 李利原典二
    ├── 基督占星第三册(Christian Astrology 3)选译.md   # 李利原典三
    ├── Horary Examples翻译.md             # 案例集
    ├── 灵体攻击案例专题.md                # 专题
    ├── 莫林本命占星方法.md                # 本命底本（Morin 第21卷）
    ├── _index.md        # 6.0版索引
    ├── _index_ca1.md    # 李利一索引
    ├── _index_ca2.md    # 李利二索引
    ├── _index_ca3.md    # 李利三索引
    ├── _index_he.md     # 案例集索引
    ├── _index_spirit.md # 专题索引
    └── _index_morin.md  # 莫林本命索引
```

## 安装依赖
```bash
pip install pyswisseph==2.10.3.2
```
> Windows 用户若无法编译老版本 pyswisseph，请用预编译 wheel：PyPI 上已有 cp311 win_amd64 预编译包，无需 VC++。

## 使用流程
1. 收齐输入：
   - 卜卦：问题原文 + 起盘时间（本地，年月日时分）+ 时区 + 地点
   - 本命：出生信息（日期时刻+地点）+ 分析重点
2. 排盘：
   ```bash
   # 卜卦（默认 Regiomontanus）
   python3 scripts/cast_chart.py --time "2026-07-10 03:14" --tz 8 --city 厦门 --out chart.txt
   # 本命（Placidus）
   python3 scripts/cast_chart.py --time "1990-05-15 08:30" --tz 8 --city 北京 --mode natal --out chart.txt
   ```
3. 判读：依据 `references/` 下对应领域索引定位章节，组织论断与引用。
4. 生成报告：
   ```bash
   python3 scripts/gen_report.py --title "失眠睡眠改善" --time "2026-07-10 03:14" \
     --tz 8 --place "厦门" --question "我最近经常失眠..." \
     --chart chart.txt --verdict-file verdict.txt \
     --cite1 "The Horary Textbook 乾坤 6.0版|章节|段落N（原文行X-Y）|摘引"
   # --out 留空时按「提问时间_问题概括」自动命名；--cite 必须显式带底本名
   ```

## 诚实声明（请使用者知悉）
- 本 skill 的判读逻辑锚定七库资料：Frawley《The Horary Textbook 乾坤 6.0版》（作者 John Frawley，译者乾坤）、《基督占星》三册（William Lilly 原典，各册译者）、《Horary Examples翻译》、《灵体攻击案例专题》、《莫林本命占星方法》（Morin 原典，译者易简占星）。
- 卜卦健康类问题（6 宫）原作者明言"要谦虚对待"，本工具**不替代医疗/专业意见**。
- 引用若超出底本覆盖范围，会明示"文档未载"，不编造。

## License
- 本 skill 的代码与脚手架以 MIT 协议开源。
- 七库底本均为翻译/编译作品，版权归各自原作者与译者所有；随本仓库分发仅供个人学习研究，商业使用请取得授权。
