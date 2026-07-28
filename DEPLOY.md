# dishonors-astrolabe 完整部署与使用指南

> 让朋友也能拥有「古典占星大师」agent 的完整体验

---

## 一、你需要什么

| 组件 | 用途 | 来源 |
|-----|------|------|
| OpenClaw / QClaw | 运行 agent 的平台 | 自行安装 |
| dishonors-astrolabe skill | 排盘、渲染、PDF 生成 | GitHub 下载 |
| 古典占星大师 agent 配置 | 七库判读能力 | 本指南配置 |
| Node.js + Chrome | Puppeteer 截图依赖 | 自行安装 |

---

## 二、Skill 安装（工具层）

### 2.1 下载 Skill

```bash
# 进入你的 OpenClaw skills 目录
cd ~/.qclaw/skills

# 克隆仓库
git clone https://github.com/777dishonor/dishonors-astrolabe.git

# 安装 Node 依赖（用于 Puppeteer 截图）
cd dishonors-astrolabe/lib/capture
npm install
```

### 2.2 验证安装

```bash
cd ~/.qclaw/skills/dishonors-astrolabe/scripts

# 测试排盘
python cast_chart.py --time "2026-07-25 18:13" --tz 8 --city 厦门

# 测试渲染（需要 Node + Chrome）
python render_chart.py --time "2026-07-25 18:13" --tz 8 --city 厦门 --out test.png
```

看到 `test.png` 生成成功，说明工具层安装完成。

---

## 三、Agent 配置（智能层）

**这是复刻体验的关键步骤。**

### 3.1 创建 Agent 工作区

在你的 OpenClaw workspace 目录下：

```bash
mkdir -p ~/.qclaw/workspace-agent-xxx/memory
```

### 3.2 写入 SOUL.md（角色定义）

创建 `~/.qclaw/workspace-agent-xxx/SOUL.md`：

```markdown
# SOUL.md

你是「古典占星大师」——研习过所有欧洲古典占星典籍，对文艺复兴时期大师之作滚瓜烂熟的占星学者。

## 语气与风格

- **幽默风趣，直白犀利**：说话不绕弯子，该戳破就戳破，但用诙谐的方式
- **论据确凿，引经据典**：每一个论点都必须有扎实的古典文献依据，准确到书名、页码、原文句子
- **先给结论，再摆证据**：先亮明判断，再用典籍原文支撑

## 对待用户

- 称呼对方为「D君」（或自定义）
- 用户偏好**进一步探究问题**——不止要答案，更要挖深一层

## 核心能力

- 卜卦占星（Horary）：以 Regiomontanus 宫位制判读
- 本命占星（Natal）：以 Placidus 宫位制判读
- 七库并检：Frawley 6.0 + Lilly CA1/CA2/CA3 + 案例集 + 灵体专题 + Morin

## 工作流

1. 收到问题 → 确认起盘时间地点
2. 调用 `cast_chart.py` 排盘
3. 调用 `render_chart.py` 生成星盘图
4. 基于七库资料做判读（检索底本、定位引用）
5. 调用 `generate_full.py` 生成 PDF
6. 交付：PDF 附件 + 判读全文
```

### 3.3 写入 IDENTITY.md

创建 `~/.qclaw/workspace-agent-xxx/IDENTITY.md`：

```markdown
# IDENTITY.md

- Name: 古典占星大师
- Vibe: 研习过所有欧洲古典占星典籍，对文艺复兴时期大师之作更是烂熟于心

## 经历

我研习并通读过几乎所有欧洲古典占星学派的著作——从古希腊、中世纪阿拉伯的传承，到文艺复兴时期的大师经典，尤其是那一时期的扛鼎之作，我更是滚瓜烂熟。
```

### 3.4 配置七库资料

在 `~/.qclaw/workspace-agent-xxx/AGENTS.md` 中添加：

```markdown
## 七库资料位置

卜卦占星底本位于：
`~/.qclaw/skills/dishonors-astrolabe/references/`

- `_index.md` —— 总索引
- `_index_frawley.md` —— Frawley 6.0 索引
- `_index_lilly.md` —— Lilly CA 索引
- `_index_morin.md` —— Morin 本命索引
- `The_Horary_Textbook_6.0_乾坤版.md`
- `Lilly_Christian_Astrology_Book_1.md`
- `Lilly_Christian_Astrology_Book_2.md`
- `Lilly_Christian_Astrology_Book_3.md`
- `Horary_Examples.md`
- `灵体召唤专题.md`
- `莫林本命占星方法.md`

判读时必须检索这些底本，给出准确的行号引用。
```

### 3.5 配置 HEARTBEAT.md（预热）

创建 `~/.qclaw/workspace-agent-xxx/HEARTBEAT.md`：

```markdown
# 启动预热：dishonors-astrolabe 冷启动 I/O 缓存

每次 heartbeat 执行：
1. 运行 `python ~/.qclaw/skills/dishonors-astrolabe/scripts/warmup.py`
2. 如果报错，静默记录，不阻断其他任务
```

---

## 四、完整使用流程

配置完成后，用户（或 AI）的使用体验：

### 4.1 用户提问

> 「帮我看看明天能不能收到学生的报名，能不能赚到钱？」

### 4.2 Agent 自动执行

```python
# 1. 确认起盘信息（当前时间/地点）
# 2. 排盘
python cast_chart.py --time "2026-07-25 18:13" --tz 8 --city 厦门 --json-only

# 3. 渲染星盘图
python render_chart.py --time "2026-07-25 18:13" --tz 8 --city 厦门 --out chart.png

# 4. AI 基于七库做判读（检索底本、引用原文）
# 5. 生成 PDF
python generate_full.py --chart-png chart.png --chart-json chart.json \
    --verdict "判读文字..." --question "明天能不能..." --out report.pdf
```

### 4.3 交付产物

- **PDF 附件**：包含星盘图、数据表、判读文字
- **判读全文**：贴出完整文字 + 典籍引用

---

## 五、常见问题

### Q1: 没有 Node.js 怎么办？

星盘图渲染依赖 Puppeteer，必须安装 Node.js + Chrome。

替代方案：
- 用 `cast_chart.py` 排盘后，手动打开生成的 HTML 截图
- 或改用 matplotlib 版 `draw_chart.py`（效果较差）

### Q2: 判读文字是占位符？

说明 agent 没有正确加载七库资料。检查：
- SOUL.md 是否要求「检索底本」
- AGENTS.md 是否指定了正确的资料路径
- skill 的 `references/` 目录是否存在

### Q3: 中文显示方框？

系统需要安装中文字体：
- Windows：默认有 SimHei/SimSun，无需操作
- macOS：`brew install font-noto-sans-cjk`
- Linux：`apt install fonts-noto-cjk`

### Q4: 如何自定义判读风格？

修改 SOUL.md 中的「语气与风格」部分，agent 会遵循新的指令。

---

## 六、文件结构总览

```
~/.qclaw/
├── skills/dishonors-astrolabe/          # 本仓库
│   ├── scripts/
│   │   ├── cast_chart.py               # 排盘
│   │   ├── render_chart.py             # 渲染 PNG
│   │   ├── generate_full.py            # PDF 打包
│   │   └── warmup.py                   # 预热
│   ├── references/                     # 七库底本
│   └── lib/capture/                    # Puppeteer 截图
│
└── workspace-agent-xxx/                # 你的 agent 配置
    ├── SOUL.md                         # 角色定义
    ├── IDENTITY.md                     # 身份介绍
    ├── AGENTS.md                       # 工具路径
    ├── HEARTBEAT.md                    # 预热任务
    └── memory/                         # 每日记忆
```

---

## 七、更新维护

```bash
cd ~/.qclaw/skills/dishonors-astrolabe
git pull origin main
```

---

**至此，你的朋友应该能复刻「古典占星大师」的完整体验。**

如果仍有差异，检查：
1. Node.js 和 Chrome 是否正常
2. Agent 是否正确加载了 SOUL.md
3. 七库资料路径是否正确
