# SVG Design Cookbook — 高质量页面视觉设计指南

> **定位**：Executor 的视觉设计强制参考。教你"怎么写出好看的 SVG 代码"。
>
> **阅读时机**：在 Executor Phase 确认设计参数后、生成第一页 SVG 之前，**必须阅读**。

---

## 原则零：不教道理，教做法

本文档不讲"为什么好看"，只讲"怎么写才好看"。每条规则都有 ❌ 和 ✅ 代码对比。**你的工作就是：永远写 ✅ 的代码，永远不写 ❌ 的代码。**

---

## 原则一：防上下文衰减 — 锚点模板

> ⚠️ **你最大的敌人是自己的遗忘**。当你生成到第 10 页时，你会忘掉第 2 页的坐标。这一节帮你锁死不变的部分。

### 锚点规则 A1：每页必须从固定模板开始

**每一个内容页都必须以以下代码开头**，禁止修改任何坐标值：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
  <defs>
    <linearGradient id="headerGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="[PRIMARY]"/>
      <stop offset="100%" stop-color="[ACCENT]"/>
    </linearGradient>
    <filter id="cardShadow" x="-15%" y="-15%" width="140%" height="140%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="10"/>
      <feOffset dx="0" dy="4" result="offsetBlur"/>
      <feFlood flood-color="#000000" flood-opacity="0.1" result="shadowColor"/>
      <feComposite in="shadowColor" in2="offsetBlur" operator="in" result="shadow"/>
      <feMerge><feMergeNode in="shadow"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <rect x="0" y="0" width="1280" height="720" fill="#FFFFFF"/>
  <rect x="0" y="0" width="1280" height="6" fill="url(#headerGrad)"/>
  <g id="header">
    <rect x="60" y="40" width="6" height="36" rx="3" fill="[PRIMARY]"/>
    <text x="80" y="70" font-family="Microsoft YaHei, Arial, sans-serif"
      font-size="32" font-weight="bold" fill="#263238">__TITLE__</text>
    <use data-icon="chunk/__ICON__" x="__TITLE_END__" y="46"
      width="30" height="30" fill="[PRIMARY]"/>
  </g>
  <!-- ======= 内容区从这里开始，y ≥ 105 ======= -->
```

**每一页必须以以下代码结尾**：
```xml
  <!-- ======= 内容区到这里结束 ======= -->
  <g id="footer">
    <rect x="0" y="690" width="1280" height="30" fill="#F0F4F8"/>
    <text x="640" y="710" text-anchor="middle"
      font-family="Microsoft YaHei, Arial, sans-serif"
      font-size="11" fill="#90A4AE">项目名 | 机构名</text>
    <text x="1220" y="710" text-anchor="end"
      font-family="Arial, sans-serif"
      font-size="11" fill="#90A4AE">__PAGE__</text>
  </g>
</svg>
```

**铁律**：
- header 色条 y 永远 = **40**，标题 y 永远 = **70**，图标 y 永远 = **46**
- 内容区 y 永远从 **105** 开始
- footer y 永远 = **690**
- 以上数字**从第一页到最后一页不变**，无论你当前生成到第几页

### 锚点规则 A2：禁止使用 feDropShadow

**❌ 禁止**：
```xml
<filter id="cardShadow">
  <feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="#000000" flood-opacity="0.08"/>
</filter>
```

**✅ 必须使用完整的 5 步 filter**（见锚点模板中的 defs 块）。

`feDropShadow` 产生的阴影太弱、太浅，视觉上卡片会"沉进"页面。

### 锚点规则 A3：图标位置紧跟标题文字

**原则**：图标紧挨标题文字右侧，间距约 12px。

**固定参数**：
- 图标 Y = **46**（与标题 y=70 视觉居中）
- 图标大小：`width="30" height="30"` 或 `scale(1.875)`
- 图标 X ≈ 标题起始 x + 标题文字宽度 + 12

> 精确的 X 坐标在 SVG Review 阶段会自动校验和修正（见 `workflows/svg-review.md` C2 类检查）。
> 生成时只需确保图标**目视紧跟标题**，不要放到页面右端（x>1000）或与标题重叠。

### 锚点规则 A4：每 5 页自检一次一致性

每生成 5 页后，暂停并检查：
```
□ 当前页的 header 色条 y 是否 = 40？（不是 18）
□ 当前页的 filter 是否是 5 步 feGaussianBlur 版本？（不是 feDropShadow）
□ 当前页的图标是否紧跟标题？（不在 x=1190）
□ 当前页的卡片起始 y 是否 ≥ 105？（不是 80）
```
如果任何一项不符，立即回退修正。

---

## 第一部分：最小设计系统

> 在生成第一页 SVG 之前，你必须先从 Design Spec 提取以下变量，并在整套 PPT 中保持不变。

### 1.1 色彩角色表（每个 PPT 必须先定义）

从 Design Spec 中获取 Primary、Accent、Secondary 色值后，按以下表格固定全部色彩角色：

| 角色 | 默认值 | 用途 | 来源 |
|------|--------|------|------|
| `PRIMARY` | Design Spec | 标题栏填充、标题左侧色条、大数字、图标色 | Design Spec |
| `ACCENT` | Design Spec | 封面装饰、渐变条终点色、CTA按钮、数据高亮 | Design Spec |
| `SECONDARY` | Design Spec | 封面背景渐变起点、深色变体 | Design Spec |
| `SUCCESS` | `#2E7D32` | 正面数据（↑增长、✓完成） | 固定 |
| `WARNING` | `#C62828` | 负面数据（痛点、风险、竞争劣势） | 固定 |
| `BODY` | `#263238` | 正文文字 | 固定 |
| `MUTED` | `#546E7A` | 辅助文字、备注 | 固定 |
| `LIGHT` | `#90A4AE` | 页脚、最弱文字 | 固定 |
| `SURFACE` | `#F0F4F8` | 页脚背景、浅灰衬底 | 固定 |
| `BORDER` | `#CFD8DC` | 分割线 | 固定 |

**铁律**：一套 PPT 中 PRIMARY + ACCENT + SECONDARY 共 3 个主题色。每个颜色角色一旦确定，每一页中功能不变。

### 1.2 字号层次表

| 层级 | 字号 | 字重 | 颜色 | 用途 |
|------|------|------|------|------|
| 页面标题 | 28-32px | bold | `BODY` | 每页顶部主标题 |
| 卡片标题 | 17-20px | bold | `#FFFFFF` | 卡片有色标题栏上 |
| 大数字 | 36-48px | bold | `PRIMARY`/`ACCENT` | 核心指标 |
| 正文 | 14-15px | normal | `BODY` | 主要描述文本 |
| 辅助说明 | 12-13px | normal | `MUTED` | 备注、来源 |
| 页脚 | 11px | normal | `LIGHT` | 底部信息 |

### 1.3 标准 defs 块（每个 SVG 文件的开头必须包含）

```xml
<defs>
  <!-- 顶部渐变条 -->
  <linearGradient id="headerGrad" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="[PRIMARY]"/>
    <stop offset="100%" stop-color="[ACCENT]"/>
  </linearGradient>
  <!-- 卡片阴影 -->
  <filter id="cardShadow" x="-15%" y="-15%" width="140%" height="140%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="10"/>
    <feOffset dx="0" dy="4" result="offsetBlur"/>
    <feFlood flood-color="#000000" flood-opacity="0.1" result="shadowColor"/>
    <feComposite in="shadowColor" in2="offsetBlur" operator="in" result="shadow"/>
    <feMerge><feMergeNode in="shadow"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
```

将 `[PRIMARY]` 和 `[ACCENT]` 替换为 Design Spec 中的实际色值。这个 defs 块在每个 SVG 中保持一致。

---

## 第二部分：Card — 卡片是最核心的设计元素

> 80% 的内容页由卡片组成。卡片设计的好坏直接决定整套 PPT 的品质。

### 规则 C1：卡片必须有阴影

**❌ 差（弱模型典型做法）**：
```xml
<rect x="60" y="110" width="565" height="260" rx="12" fill="#F5F5F5"/>
```
灰色平面矩形，没有深度感，与白色背景融为一体。

**✅ 好**：
```xml
<rect x="60" y="110" width="565" height="260" rx="12" fill="#FFFFFF" filter="url(#cardShadow)"/>
```
白色卡片 + 投影阴影 = 浮起的立体感。

### 规则 C2：卡片必须有带颜色的标题栏

**❌ 差（弱模型典型做法）**：
```xml
<rect x="60" y="110" width="370" height="400" rx="12" fill="#F0F0F0"/>
<text x="80" y="145" font-size="18" font-weight="bold" fill="#333333">标题</text>
```
灰色背景 + 黑色文字标题，没有视觉吸引力，所有卡片看起来一样。

**✅ 好**：
```xml
<!-- 白底卡片容器 -->
<rect x="60" y="110" width="370" height="400" rx="12" fill="#FFFFFF" filter="url(#cardShadow)"/>
<!-- 有色标题栏 -->
<rect x="60" y="110" width="370" height="55" rx="12" fill="[PRIMARY]"/>
<!-- 标题栏底部圆角修补 -->
<rect x="60" y="153" width="370" height="12" fill="[PRIMARY]"/>
<!-- 白色图标 + 白色标题 -->
<use data-icon="chunk/star" x="80" y="122" width="28" height="28" fill="#FFFFFF"/>
<text x="118" y="145" font-size="17" font-weight="bold" fill="#FFFFFF">标题</text>
```

**为什么有"圆角修补"？**

标题栏 `<rect rx="12">` 四个角都是圆的，但底部与白色 body 相接的地方不应该有圆角。解决办法是在标题栏下方叠一个同色矩形覆盖底部圆角。**每个有色标题栏的卡片都必须这样做。**

### 规则 C3：并列卡片必须用不同颜色的标题栏

**❌ 差**：三张卡片标题栏全部是同一个蓝色。看起来是重复的，无法快速区分。

**✅ 好**：
```
卡片1 标题栏: [PRIMARY]    例如 #1565C0
卡片2 标题栏: [ACCENT]     例如 #00BCD4
卡片3 标题栏: [SECONDARY]  例如 #0D47A1
```
卡片 body 内容区域保持一致（都是白底），只通过标题栏颜色区分。卡片内的大数字和 Badge 颜色跟随该卡片的标题栏颜色。

**四张并列卡片（2×2）**：第四张引入功能色（如 `#2E7D32` 绿色）。

### 规则 C4：大数字的正确用法（附滑稽反例）

大数字是卡片的视觉焦点，但用错了比没有更糟糕。

**❌ 滑稽的大数字（弱模型典型做法）**：
```xml
<!-- 错误1：用字母当大数字 -->
<text font-size="48" font-weight="bold" fill="#2E7D32">N</text>
<text font-size="15">多项国家级课题</text>
<!-- "N" 不是数据！没有具体数字就不要用大数字 -->

<!-- 错误2：大数字太大，喧宾夺主 -->
<text font-size="64" font-weight="bold" fill="#2E7D32">300%</text>
<!-- 64px 在 370px 宽的卡片上比例失调，占据大量空间 -->

<!-- 错误3：大数字裸放，没有搭配元素 -->
<text font-size="48" fill="#1565C0">50+</text>
<!-- 下面直接就是列表，没有Badge、没有单位说明 -->

<!-- 错误4：同一张卡片两个大数字紧挨着 -->
<text y="250" font-size="48">0.1mm</text>
<text y="250" x="250" font-size="48">&lt;50ms</text>
<!-- 两个 48px 数字挤在一行，视觉混乱 -->
```

**✅ 大数字的完整组合（4 件套）**：

大数字永远不单独出现。它必须搭配 3 个伴随元素，组成一个"数字信息块"：

```xml
<!-- ① 大数字（居中，Arial，36-48px，主题色） -->
<text x="245" y="220" text-anchor="middle"
  font-family="Arial, sans-serif" font-size="48"
  font-weight="bold" fill="[PRIMARY]">9</text>

<!-- ② 单位说明（紧跟大数字下方，16px，BODY色） -->
<text x="245" y="250" text-anchor="middle"
  font-family="Microsoft YaHei, Arial, sans-serif"
  font-size="16" fill="#263238">篇学术论文</text>

<!-- ③ Badge标签（药丸形，大数字下方8px处） -->
<rect x="170" y="262" width="150" height="28" rx="14"
  fill="[PRIMARY]" fill-opacity="0.1"/>
<text x="245" y="281" text-anchor="middle"
  font-size="13" fill="[PRIMARY]">SCI收录 8篇</text>

<!-- ④ 分割线（Badge下方12px处，引出下面的列表） -->
<rect x="84" y="300" width="322" height="1" fill="#CFD8DC"/>
```

**大数字使用铁律**：

| 规则 | 说明 |
|------|------|
| 字号 = **36~48px**，不超过 48px | 64px 在卡片内太大，比例失调 |
| 字体 = **Arial**（纯数字部分） | 中文字体的数字不好看 |
| 每张卡片 **最多 1 个** 大数字 | 2 个大数字 = 没有焦点 |
| 必须是**具体数字** | 禁止用 "N"、"多"、"若干" 当大数字 |
| 没有数据就**不放**大数字 | 用标题栏+图标+列表代替 |
| 大数字下方必须有**单位说明** | "9" 下面要有 "篇学术论文" |
| 大数字下方必须有 **Badge** | 提供定性描述 |

### 规则 C4b：Badge 标签的设计

```xml
<!-- Badge = 药丸底色 + 同色文字 -->
<rect x="170" y="265" width="150" height="28" rx="14"
  fill="[PRIMARY]" fill-opacity="0.1"/>
<text x="245" y="284" text-anchor="middle"
  font-size="13" fill="[PRIMARY]">SCI收录 8篇</text>
```

**设计要点**：
- `rx` = 高度的一半（28px 高 → rx=14，完全药丸形）
- 底色 = 主题色 + `fill-opacity="0.1"`
- 文字颜色 = 主题色（同色系，不是黑色）
- Badge 宽度根据文字自适应（约 每字 15px + 左右 padding 24px）

### 规则 C5：卡片内用分割线分隔不同信息区块

**❌ 差**：列表项和总结文字之间没有任何分隔，视觉上混为一体。

**✅ 好**：
```xml
<!-- 最后一个列表项 -->
<text x="84" y="470" font-size="13" fill="#546E7A">• 最后一项</text>
<!-- 分割线 -->
<rect x="84" y="490" width="322" height="1" fill="#CFD8DC"/>
<!-- 底部总结 -->
<text x="84" y="515" font-size="12" fill="[PRIMARY]">底部总结信息</text>
```

### 规则 C6：卡片坐标必须精确计算

**三栏等宽（最常用）**：
```
总宽度 = 1280, 页边距 = 60, 间距 = 25
卡片宽度 = (1280 - 60×2 - 25×2) / 3 = 370

卡片1: x=60
卡片2: x=60+370+25 = 455
卡片3: x=455+370+25 = 850
```

**双栏等宽**：
```
卡片宽度 = (1280 - 60×2 - 30) / 2 = 565

卡片1: x=60
卡片2: x=60+565+30 = 655
```

**四宫格（2×2）**：
```
列: x=60, x=655 (宽度 565)
行: y=105, y=105+card_h+25
```

**铁律**：同一行的卡片必须等宽、等高、间距相等。用公式算，不要目测。

### 规则 C7：卡片内必须使用 ≥3 种信息元素

**❌ 差（弱模型典型做法 — 只有一种元素）**：
```xml
<!-- 卡片内只有文字列表，540px高的卡片塞了4行文字 -->
<text y="165" font-size="15">中国兵器工业集团</text>
<text y="200" font-size="15">先进装备研制核心院所</text>
<text y="235" font-size="15">维护保障技术领先</text>
<!-- 然后就没了。卡片下方 300px 全是空白 -->
```

**✅ 好（多种元素交替形成丰富层次）**：

每张卡片必须从以下 7 种元素中选择 **≥3 种** 来填充内容区：

| # | 元素名 | 模板代码 | 占用高度 |
|---|--------|---------|----------|
| E1 | 有色标题栏 | 见规则 C2 | 55px |
| E2 | 大数字 4 件套 | 见规则 C4 | 75-85px |
| E3 | Badge 标签 | `<rect rx="14" fill-opacity="0.1"/>` | 28px |
| E4 | 信息卡（图标+标题+说明）| 见下方 C8 | 70px |
| E5 | 并排 Badge 行 | 见下方 C9 | 30-35px |
| E6 | 嵌套白卡（指标块） | 见下方 C10 | 90px |
| E7 | 分割线 + 底注 | `<rect height="1"/> + <text>` | 30px |

**典型组合（三栏卡片 500px 高）**：
```
E1 标题栏(55px) + E2 大数字(80px) + E3 Badge(28px) 
+ 分割线(1px) + E4 信息列表3行(90px) 
+ 分割线(1px) + E7 底注(30px)
= 285px 内容 + 间距 ≈ 380px → 空白率 24% ✅
```

### 规则 C8：信息卡 — 图标+标题+一句说明

这是弱模型**完全不会**的元素。用于在卡片内部展示 3~5 个并列能力/特性。

```xml
<!-- 信息卡：浅色底+左侧图标+右侧标题和说明 -->
<rect x="674" y="195" width="520" height="70" rx="8" fill="#F0F4F8"/>
<use data-icon="chunk/microchip" x="690" y="213" width="28" height="28" fill="[PRIMARY]"/>
<text x="730" y="228" font-family="Microsoft YaHei, Arial, sans-serif"
  font-size="15" font-weight="bold" fill="#263238">柔性传感材料研发</text>
<text x="730" y="248" font-family="Microsoft YaHei, Arial, sans-serif"
  font-size="13" fill="#546E7A">高性能柔性传感阵列设计与复合材料体系</text>
```

**多个信息卡竖直叠放**（间距 15px）：
```
信息卡1: y=195 (h=70)
信息卡2: y=280 (195+70+15)
信息卡3: y=365 (280+70+15)
信息卡4: y=450 (365+70+15)
```

**对比效果**：

| 弱模型做法 | Claude 做法 |
|-----------|------------|
| `<text>柔性传感材料研发</text>` | 浅灰底框 + microchip图标 + 粗体标题 + 灰色说明 |
| 一行裸文字 | 70px 高的视觉组件 |
| 0 种元素 | 3 种元素（底框+图标+文字） |

### 规则 C9：并排 Badge 行

用于展示 3~5 个并列的标签/关键词/学科方向。

```xml
<!-- 4 个 Badge 并排（间距 10px） -->
<rect x="84" y="260" width="110" height="30" rx="15"
  fill="[PRIMARY]" fill-opacity="0.1"/>
<text x="139" y="280" text-anchor="middle"
  font-size="13" fill="[PRIMARY]">材料科学</text>

<rect x="204" y="260" width="110" height="30" rx="15"
  fill="[PRIMARY]" fill-opacity="0.1"/>
<text x="259" y="280" text-anchor="middle"
  font-size="13" fill="[PRIMARY]">人工智能</text>

<rect x="324" y="260" width="110" height="30" rx="15"
  fill="[PRIMARY]" fill-opacity="0.1"/>
<text x="379" y="280" text-anchor="middle"
  font-size="13" fill="[PRIMARY]">算法设计</text>

<rect x="444" y="260" width="110" height="30" rx="15"
  fill="[PRIMARY]" fill-opacity="0.1"/>
<text x="499" y="280" text-anchor="middle"
  font-size="13" fill="[PRIMARY]">系统工程</text>
```

**坐标公式**：Badge 宽度 110px + 间距 10px = 步长 120px。

**适用场景**：学科方向、技术标签、能力维度、竞争优势关键词。

### 规则 C10：嵌套白卡 — 卡中卡指标块

在大卡片（灰底或白底）内部嵌套小白卡，用于展示 2~3 个关键指标。

```xml
<!-- 大卡片内部嵌套 2 个白色指标小卡 -->
<rect x="84" y="390" width="200" height="90" rx="10" fill="#FFFFFF"/>
<text x="184" y="425" text-anchor="middle"
  font-family="Arial, sans-serif" font-size="32"
  font-weight="bold" fill="[PRIMARY]">50+</text>
<text x="184" y="455" text-anchor="middle"
  font-size="13" fill="#546E7A">核心期刊论文</text>

<rect x="304" y="390" width="200" height="90" rx="10" fill="#FFFFFF"/>
<text x="404" y="425" text-anchor="middle"
  font-family="Arial, sans-serif" font-size="32"
  font-weight="bold" fill="[ACCENT]">10+</text>
<text x="404" y="455" text-anchor="middle"
  font-size="13" fill="#546E7A">授权发明专利</text>
```

**注意**：嵌套白卡内的数字用 **32px**（不是 48px），因为这是卡中卡，空间更小。

---

## 第三部分：Page Skeleton — 页面骨架

> 每一页都有完全相同的骨架：顶部渐变条 → 标题区 → 内容区 → 页脚。

### 规则 P1：每个内容页的标题区完全相同

**✅ 标题三件套（每页必须有，格式完全一致）**：
```xml
<!-- 顶部渐变薄条（6px，跨全宽） -->
<rect x="0" y="0" width="1280" height="6" fill="url(#headerGrad)"/>

<!-- 标题区 -->
<g id="header">
  <!-- 左侧色条装饰 -->
  <rect x="60" y="40" width="6" height="36" rx="3" fill="[PRIMARY]"/>
  <!-- 页面标题 -->
  <text x="80" y="70" font-family="Microsoft YaHei, Arial, sans-serif"
    font-size="32" font-weight="bold" fill="#263238">页面标题</text>
  <!-- 标题右侧图标 -->
  <use data-icon="chunk/lightbulb" x="[标题文字右端+12]" y="46"
    width="30" height="30" fill="[PRIMARY]"/>
</g>
```

**三个元素缺一不可**：左侧色条(6×36px) + 标题文字(32px bold) + 主题图标(30×30px)。

**铁律**：从第 2 页到最后一页，这三个元素的 x/y 坐标完全不变，只改文字内容和图标名称。

### 规则 P2：每页必须有统一格式的页脚

**✅ 标准页脚**：
```xml
<g id="footer">
  <rect x="0" y="690" width="1280" height="30" fill="#F0F4F8"/>
  <text x="640" y="710" text-anchor="middle"
    font-family="Microsoft YaHei, Arial, sans-serif"
    font-size="11" fill="#90A4AE">项目名称 | 机构名称</text>
  <text x="1220" y="710" text-anchor="end"
    font-family="Arial, sans-serif"
    font-size="11" fill="#90A4AE">02</text>
</g>
```

**铁律**：每页的页脚代码完全相同，仅页码数字不同。

### 规则 P3：封面页必须有丰富的视觉层次

**❌ 差（弱模型典型封面）**：
```xml
<rect x="0" y="0" width="1280" height="720" fill="#1565C0"/>
<text x="640" y="360" text-anchor="middle" font-size="48"
  font-weight="bold" fill="#FFFFFF">项目标题</text>
```
纯色背景 + 居中标题，极其单调。

**✅ 好（封面的 7 层叠加结构）**：
```xml
<!-- 第1层：深色渐变背景 (SECONDARY → PRIMARY 对角线) -->
<defs>
  <linearGradient id="coverBg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="[SECONDARY]"/>
    <stop offset="100%" stop-color="[PRIMARY]"/>
  </linearGradient>
  <radialGradient id="coverGlow" cx="70%" cy="30%" r="50%">
    <stop offset="0%" stop-color="[ACCENT]" stop-opacity="0.15"/>
    <stop offset="100%" stop-color="[ACCENT]" stop-opacity="0"/>
  </radialGradient>
</defs>
<rect x="0" y="0" width="1280" height="720" fill="url(#coverBg)"/>

<!-- 第2层：辉光叠加（增加深度） -->
<rect x="0" y="0" width="1280" height="720" fill="url(#coverGlow)"/>

<!-- 第3层：几何装饰（旋转半透明矩形，2~3个） -->
<rect x="950" y="-80" width="200" height="200" rx="20"
  fill="#FFFFFF" fill-opacity="0.04" transform="rotate(25, 1050, 20)"/>
<rect x="80" y="500" width="120" height="120" rx="14"
  fill="#FFFFFF" fill-opacity="0.03" transform="rotate(15, 140, 560)"/>

<!-- 第4层：辉光圆（ACCENT 色光晕，1~2个） -->
<circle cx="200" cy="150" r="60" fill="[ACCENT]" fill-opacity="0.06"/>
<circle cx="1100" cy="550" r="90" fill="[ACCENT]" fill-opacity="0.05"/>

<!-- 第5层：微小散点（2~4个3px圆点，增加质感） -->
<circle cx="100" cy="100" r="3" fill="#FFFFFF" fill-opacity="0.15"/>
<circle cx="1180" cy="650" r="3" fill="#FFFFFF" fill-opacity="0.12"/>

<!-- 第6层：居中内容 -->
<use data-icon="chunk/hand" x="580" y="180" width="56" height="56" fill="[ACCENT]"/>
<rect x="490" y="260" width="300" height="3" rx="1" fill="url(#accentLine)"/>
<text x="640" y="320" text-anchor="middle" font-size="48"
  font-weight="bold" fill="#FFFFFF">项目标题第一行</text>
<text x="640" y="380" text-anchor="middle" font-size="48"
  font-weight="bold" fill="#FFFFFF">项目标题第二行</text>
<text x="640" y="430" text-anchor="middle" font-size="20"
  fill="#FFFFFF" fill-opacity="0.85">副标题 · 用中点分隔关键词</text>

<!-- 第7层：底部信息 + 装饰条 -->
<text x="640" y="560" text-anchor="middle" font-size="18"
  fill="#FFFFFF" fill-opacity="0.7">机构名称</text>
<text x="640" y="590" text-anchor="middle" font-size="14"
  fill="#FFFFFF" fill-opacity="0.5">2026年4月</text>
<rect x="0" y="700" width="1280" height="20" fill="[ACCENT]" fill-opacity="0.3"/>
```

**封面自检**：渐变背景？辉光叠加？几何装饰？辉光圆？微小散点？图标？渐变分割线？标题？副标题？机构信息？底部装饰条？—— 缺任何一项都不合格。

### 规则 P4：每 3~5 页内容页后插入一个"呼吸页"

呼吸页 = 全屏深色渐变背景 + 居中文字 + 半透明装饰，与封面视觉风格呼应。用于缓冲信息密集的节奏。

```xml
<!-- 深色渐变背景（与封面同色系） -->
<rect x="0" y="0" width="1280" height="720" fill="url(#bgGrad)"/>
<rect x="0" y="0" width="1280" height="720" fill="url(#glow)"/>

<!-- 居中大文字 -->
<text x="640" y="300" text-anchor="middle" font-size="42"
  font-weight="bold" fill="#FFFFFF">核心精神标语</text>
<rect x="440" y="320" width="400" height="3" rx="1"
  fill="[ACCENT]" fill-opacity="0.5"/>

<!-- 2~3个半透明小卡片 -->
<rect x="180" y="430" width="260" height="70" rx="12"
  fill="#FFFFFF" fill-opacity="0.08"/>
<text x="200" y="472" font-size="16" font-weight="bold" fill="#FFFFFF">关键词一</text>
```

---

## 第四部分：Color — 颜色使用规则

### 规则 K1：卡片主体背景只能是纯白 `#FFFFFF`

弱模型最常犯的错误：因为主题色是蓝色，就用蓝调浅灰色（`#F0F4F8`、`#E8EAF6`、`#ECEFF1`）来填充卡片背景。结果整页看起来灰蒙蒙的，没有任何层次感。

**❌ 禁止用于卡片主体背景的颜色**：
```
#F0F4F8  ← 最常见的错误！看起来"高级灰"实际很廉价
#F5F5F5, #E0E0E0, #EEEEEE  ← 纯灰色系列
#E8EAF6, #E3F2FD, #ECEFF1  ← 主题色浅灰变体
任何 fill-opacity < 1 的主题色  ← 如 fill="#1565C0" fill-opacity="0.05"
```

**✅ 卡片主体背景**：`fill="#FFFFFF" filter="url(#cardShadow)"`

**`#F0F4F8` 的正确用途（SURFACE 色）**：

| ✅ 可以用 `#F0F4F8` 的地方 | ❌ 不能用的地方 |
|--------------------------|---------------|
| 页脚背景条（30px高） | 卡片主体背景 |
| 表格交替行底色 | 整个卡片填充 |
| 底部指标行小框底色 | 页面大面积背景 |
| 卡片内嵌小条目底色（如奖项条） | — |
| 底部总结框底色 | — |

**关键区分**：`#F0F4F8` 只用于**卡片内部的小区域衬底**（如一个 50px 高的条目框），**不用于卡片本身的 400~500px 高的主体背景**。

```xml
<!-- ❌ 错误：整个卡片都是灰蓝底 -->
<rect x="60" y="110" width="370" height="500" rx="12" fill="#F0F4F8"/>

<!-- ✅ 正确：卡片白底+阴影，内部小区域用 SURFACE 衬底 -->
<rect x="60" y="110" width="370" height="500" rx="12" fill="#FFFFFF" filter="url(#cardShadow)"/>
<!-- 卡片内部的一个小条目 -->
<rect x="84" y="350" width="322" height="45" rx="8" fill="#F0F4F8"/>
```

### 规则 K2：颜色使用的唯一对照表

| 我要表达... | 用什么颜色 | 示例 |
|------------|-----------|------|
| 重要标题/结构 | `PRIMARY` | 卡片标题栏、左侧色条 |
| 亮点/点缀 | `ACCENT` | 数据高亮、CTA按钮 |
| 深沉/权威 | `SECONDARY` | 封面背景、第一张卡片 |
| 正面数据 | `SUCCESS` (#2E7D32) | ↑300%、↓40%成本 |
| 负面/痛点 | `WARNING` (#C62828) | 竞争劣势、痛点卡片 |
| 正文文字 | `BODY` (#263238) | 所有正文 |
| 辅助文字 | `MUTED` (#546E7A) | 备注、来源 |
| 最弱文字 | `LIGHT` (#90A4AE) | 页脚 |
| 分割线 | `BORDER` (#CFD8DC) | 1px 横线 |
| 浅灰衬底 | `SURFACE` (#F0F4F8) | 页脚背景、表格交替行、指标卡底色 |

**铁律**：除了上表中的颜色，不使用任何其他颜色。

### 规则 K3：数据指标的颜色表达

```xml
<!-- 正面数据框 -->
<rect x="84" y="330" width="240" height="60" rx="8"
  fill="#2E7D32" fill-opacity="0.08"/>
<text x="204" y="355" text-anchor="middle" font-family="Arial, sans-serif"
  font-size="24" font-weight="bold" fill="#2E7D32">↓40%</text>
<text x="204" y="378" text-anchor="middle" font-size="12"
  fill="#2E7D32">培训周期缩短</text>
```

公式：`底色 = 数据色 + fill-opacity 0.08` / `文字色 = 数据色`

### 规则 K4："左右对比"页必须用红绿或红蓝对比

```
左卡片（问题/痛点）: 标题栏 fill="#C62828"
右卡片（优势/方案）: 标题栏 fill="#2E7D32"
```

---

## 第五部分：Icon — 图标使用规则

### 规则 I1：图标必须出现在以下 3 个位置

| 位置 | 大小 | 颜色 | 作用 |
|------|------|------|------|
| 页面标题右侧 | 30×30px | `PRIMARY` | 标题主题标识 |
| 卡片标题栏内 | 28-32px | `#FFFFFF` | 卡片内容暗示 |
| 列表项/功能框前 | 24-28px | 对应主题色 | 视觉引导 |

```xml
<!-- 位置1: 页面标题右侧 -->
<use data-icon="chunk/lightbulb" x="[标题文字右端+12]" y="46" width="30" height="30" fill="[PRIMARY]"/>

<!-- 位置2: 卡片标题栏内 -->
<use data-icon="chunk/book-open" x="80" y="122" width="28" height="28" fill="#FFFFFF"/>

<!-- 位置3: 列表项前 -->
<use data-icon="chunk/bolt" x="84" y="233" width="24" height="24" fill="[PRIMARY]"/>
```

### 规则 I2：图标选择速查

| 内容主题 | 推荐图标 |
|---------|---------|
| 数据/分析 | `chart-bar`, `chart-line` |
| 技术/创新 | `microchip`, `bolt`, `lightbulb` |
| 团队/人员 | `users`, `user` |
| 成果/奖项 | `trophy`, `star`, `badge-check` |
| 资金/财务 | `money`, `wallet`, `dollar` |
| 安全/保障 | `shield-check`, `shield` |
| 目标/战略 | `target`, `flag` |
| 教育/学术 | `book-open`, `graduation-cap` |
| 增长/趋势 | `arrow-trend-up` |
| 全球/国际 | `globe` |
| 产业/工厂 | `factory`, `building` |
| 连接/协同 | `link` |
| 流程/循环 | `arrows-rotate-clockwise` |
| 推广/传播 | `megaphone`, `rocket` |
| 生态/环保 | `leaf` |
| 代码/软件 | `code` |
| 用户/体验 | `hand` |
| 钥匙/专利 | `key` |
| 地图/区域 | `map` |

### 规则 I3：图标的验证

在使用图标前，必须通过 `ls | grep` 验证图标存在：
```bash
ls skills/ppt-master/templates/icons/chunk/ | grep lightbulb
```

如果找不到精确匹配，用最接近的替代品。**一套 PPT 只用一个图标库**（默认 `chunk/`）。

---

## 第六部分：Layout Variety — 布局多样性

### 规则 L1：禁止连续 2 页使用相同布局

**❌ 差**：第3页三栏 → 第4页三栏（连续 2 页同布局就不行）

**✅ 好**：第3页三栏 → 第4页双栏+总结条 → 第5页四宫格 → 第6页中心辐射

**弱模型后段的典型退化**：从第 13 页到第 27 页，全部都是三栏卡片。这是不合格的。

### 规则 L2：可用布局模式清单

| 模式 | 结构 | 适合内容 |
|------|------|---------|
| **三栏卡片** | 3 × 370px 等宽卡片 | 三要素并列、人物介绍 |
| **双栏卡片 + 底部总结** | 2 × 565px 卡片 + 全宽横条 | 案例展示、对比分析 |
| **四宫格** | 2×2 卡片矩阵 | 四大技术、四象限 |
| **全宽指标条 + 双栏对比** | 顶部蓝色大数字条 + 红绿对比 | 市场分析 |
| **左侧可视化 + 右侧信息栈** | 左:圆/金字塔 右:3个色条卡片 | 定位图、结构图 |
| **中心辐射图** | 中心圆 + 周围矩形节点 + 连接线 | 商业模式、生态系统 |
| **层级组织架构** | 顶部→部门→成员的树形 | 团队结构 |
| **里程碑表格** | 表头行 + 交替色行 + 合计行 | 财务、时间线 |
| **五步流程条** | 5 个窄卡片 + 编号圆 + 底部Badge总结 | 研发流程、执行步骤 |

### 规则 L3："总结条"的设计

当页面底部需要一个总结区域时，**必须用以下完整格式**：

**❌ 差（弱模型后段的退化做法）**：
```xml
<!-- 灰底裸文字 — 没有色条、没有图标、没有粗体标题 -->
<rect x="60" y="520" width="1160" height="70" rx="8" fill="#F0F4F8"/>
<text x="90" y="548" font-size="14" fill="#546E7A">一句话总结</text>
```

**✅ 好（4 元素总结条：色底+色条+图标+粗体标题+内容）**：
```xml
<g id="summary">
  <rect x="60" y="540" width="1160" height="100" rx="12"
    fill="[PRIMARY]" fill-opacity="0.06"/>
  <!-- 左侧色条 -->
  <rect x="60" y="540" width="8" height="100" rx="4" fill="[ACCENT]"/>
  <!-- 图标 -->
  <use data-icon="chunk/badge-check" x="84" y="565" width="32" height="32" fill="[PRIMARY]"/>
  <!-- 标题 -->
  <text x="130" y="585" font-size="16" font-weight="bold" fill="[PRIMARY]">总结标题</text>
  <!-- 内容 -->
  <text x="130" y="615" font-size="14" fill="#263238">总结内容</text>
</g>
```

**铁律**：总结条必须有这 4 个元素：**浅色底框 + 左色条 + 图标 + 粗体标题**。缺任何一个都退化为"灰底裸文字"——这是不合格的。

### 规则 L4：底部指标行的设计

当需要并排展示 3~4 个关键指标时：

```xml
<!-- 平分宽度 -->
<g id="km1">
  <rect x="60" y="550" width="380" height="90" rx="12" fill="#F0F4F8"/>
  <text x="250" y="585" text-anchor="middle" font-family="Arial, sans-serif"
    font-size="28" font-weight="bold" fill="[PRIMARY]">5亿</text>
  <text x="250" y="615" text-anchor="middle" font-size="14" fill="#546E7A">第5年总产值</text>
</g>
```

### 规则 L7：彩色背景摘要卡（通用组件）

**用途**：KPI 概览条、章节总述、数据高亮行。可配合任意布局使用。每 8 页最多用 1 次。

```xml
<!-- ✅ 彩色背景摘要卡 — 主色大面积铺底，白色文字 -->
<g id="summary-highlight">
  <rect x="60" y="105" width="1160" height="70" rx="12" fill="[PRIMARY]"/>
  <use data-icon="chunk/chart-bar" x="88" y="118"
    width="28" height="28" fill="#FFFFFF"/>
  <text x="128" y="132" font-family="Microsoft YaHei, Arial, sans-serif"
    font-size="20" font-weight="bold" fill="#FFFFFF">行业现状一览</text>
  <text x="128" y="155" font-family="Microsoft YaHei, Arial, sans-serif"
    font-size="14" fill="#FFFFFF" fill-opacity="0.85">
    全球XR市场规模4500亿 · 复合增长40%+ · 国产替代窗口期已至</text>
  <!-- 右侧 pill badge -->
  <rect x="960" y="118" width="220" height="34" rx="17"
    fill="#FFFFFF" fill-opacity="0.2"/>
  <text x="1070" y="140" text-anchor="middle"
    font-size="14" font-weight="bold" fill="#FFFFFF">国产化率 → 35%</text>
</g>
```

**与 K1 规则的关系**：K1 说"卡片主体背景只能纯白"。摘要卡不是内容卡片，它是 70px 高的**横条元素**，不受 K1 约束。

### 规则 L8：SVG 原生表格（通用组件）

**用途**：竞品对比、参数表、多维评价矩阵。数据 ≥ 3 行 × 3 列时使用。可配合任意布局使用。

```xml
<!-- ✅ SVG 原生表格 — rect + text + line 排列 -->
<g id="comparison-table">
  <!-- 表头行 — 主色背景 -->
  <rect x="60" y="200" width="1160" height="40" rx="8" fill="[PRIMARY]"/>
  <text x="230" y="226" text-anchor="middle" font-size="14"
    font-weight="bold" fill="#FFFFFF">维度</text>
  <text x="530" y="226" text-anchor="middle" font-size="14"
    font-weight="bold" fill="#FFFFFF">龙影手套</text>
  <text x="830" y="226" text-anchor="middle" font-size="14"
    font-weight="bold" fill="#FFFFFF">进口竞品</text>
  <text x="1080" y="226" text-anchor="middle" font-size="14"
    font-weight="bold" fill="#FFFFFF">开源方案</text>

  <!-- 奇数行 — SURFACE 底色 -->
  <rect x="60" y="240" width="1160" height="36" fill="#F0F4F8"/>
  <text x="230" y="264" text-anchor="middle" font-size="13"
    fill="#263238">价格</text>
  <text x="530" y="264" text-anchor="middle" font-size="13"
    font-weight="bold" fill="#2E7D32">＜5000元 ✓</text>
  <text x="830" y="264" text-anchor="middle" font-size="13"
    fill="#C62828">＞10000元</text>
  <text x="1080" y="264" text-anchor="middle" font-size="13"
    fill="#546E7A">N/A</text>

  <!-- 偶数行 — 白底 -->
  <rect x="60" y="276" width="1160" height="36" fill="#FFFFFF"/>
  <text x="230" y="300" text-anchor="middle" font-size="13"
    fill="#263238">精度</text>
  <text x="530" y="300" text-anchor="middle" font-size="13"
    font-weight="bold" fill="#2E7D32">0.1mm ✓</text>
  <text x="830" y="300" text-anchor="middle" font-size="13"
    fill="#546E7A">0.5mm</text>
  <text x="1080" y="300" text-anchor="middle" font-size="13"
    fill="#546E7A">1mm+</text>

  <!-- 更多行... 交替 F0F4F8 / FFFFFF -->

  <!-- 列分隔线 -->
  <line x1="370" y1="200" x2="370" y2="420" stroke="#CFD8DC" stroke-width="1"/>
  <line x1="680" y1="200" x2="680" y2="420" stroke="#CFD8DC" stroke-width="1"/>
  <line x1="960" y1="200" x2="960" y2="420" stroke="#CFD8DC" stroke-width="1"/>
</g>
```

**列宽计算**：内容区宽度 1160px，N 列等分。4 列时每列 290px，5 列时每列 232px。text-anchor="middle" 放在每列中心 x 坐标。

**颜色语义**：优势用 `SUCCESS`(`#2E7D32`)，劣势用 `WARNING`(`#C62828`)，中性用 `MUTED`(`#546E7A`)。

### 规则 L5：布局使用记录

在生成过程中，你必须在脑中维护一个布局记录表，确保不重复：

```
第02页: 双栏+总结
第03页: 双栏
第04页: 三栏      ← 与第03页不同 ✅
第05页: 四宫格    ← 与第04页不同 ✅
第06页: 双栏对比  ← 与第05页不同 ✅
...
```

如果即将生成的布局与前一页相同，**必须切换**到另一种布局。

### 规则 L6：人物卡模板（团队/导师/专家页专用）

人物页不能只放几行裸文字。以下是**完整的人物卡结构**：

```xml
<!-- 人物卡（三栏中的一栏, 370px宽, 520px高） -->
<g id="mentor1">
  <!-- 白底卡片 -->
  <rect x="60" y="110" width="370" height="520" rx="12" fill="#FFFFFF" filter="url(#cardShadow)"/>
  <!-- 全色标题栏（比普通标题栏更高：70px） -->
  <rect x="60" y="110" width="370" height="70" rx="12" fill="[PRIMARY]"/>
  <rect x="60" y="168" width="370" height="12" fill="[PRIMARY]"/>

  <!-- 头像占位圆（主题色淡底+图标） -->
  <circle cx="245" cy="225" r="45" fill="[PRIMARY]" fill-opacity="0.1"/>
  <use data-icon="chunk/user" x="217" y="197" width="56" height="56" fill="[PRIMARY]"/>

  <!-- 姓名（22px bold，居中） -->
  <text x="245" y="295" text-anchor="middle"
    font-size="22" font-weight="bold" fill="#263238">张展 教授</text>

  <!-- 角色 Badge（药丸形，居中） -->
  <rect x="170" y="305" width="150" height="26" rx="13"
    fill="[PRIMARY]" fill-opacity="0.1"/>
  <text x="245" y="323" text-anchor="middle"
    font-size="13" fill="[PRIMARY]">技术顾问</text>

  <!-- 分割线 -->
  <rect x="84" y="345" width="322" height="1" fill="#CFD8DC"/>

  <!-- 背景信息 -->
  <text x="84" y="375" font-size="14" fill="#263238">哈尔滨工业大学教授、博导</text>

  <!-- 研究方向标题 -->
  <text x="84" y="400" font-size="14" fill="#546E7A">研究方向：</text>
  <text x="84" y="425" font-size="14" fill="#263238">• 可穿戴计算</text>
  <text x="84" y="450" font-size="14" fill="#263238">• 边缘智能</text>
  <text x="84" y="475" font-size="14" fill="#263238">• 人机交互</text>

  <!-- 分割线 -->
  <rect x="84" y="500" width="322" height="1" fill="#CFD8DC"/>

  <!-- 底部贡献框（浅色底） -->
  <rect x="84" y="515" width="322" height="50" rx="8"
    fill="[PRIMARY]" fill-opacity="0.05"/>
  <text x="245" y="545" text-anchor="middle"
    font-size="13" fill="[PRIMARY]">为柔性传感与低延迟算法</text>
  <text x="245" y="563" text-anchor="middle"
    font-size="13" fill="[PRIMARY]">提供理论指导</text>
</g>
```

**对比效果**：

| 弱模型人物卡（540px高） | Claude人物卡（520px高） |
|----------------------|---------------------|
| 标题栏 55px | 标题栏 **70px**（更宽） |
| 无头像 | **头像占位圆** 90px |
| 裸文字"技术顾问" 14px | **角色Badge药丸标签** 26px |
| 3行文字 = 90px | 职称+方向标题+3项列表 = 175px |
| 无底部 | **贡献总结框** 50px |
| 空白率 **75%** | 空白率 **20%** |

---

## 第七部分：Content — 内容密度与信息编排

> 视觉再好看，内容空洞或堆砌就是失败。本部分教你**怎么从源文档中提取信息、怎么分层放进卡片、怎么控制密度不溢出也不留空**。

### 规则 T1：每页内容必须经过"信息漏斗"三层过滤

拿到源文档中某个章节（通常是一个二级标题）后，**禁止直接把原文搬上 SVG**。必须经过以下三层过滤：

```
源文档原文（可能500字）
       ↓ 第1层过滤：提取核心论点
  核心结论（1~2句话）
       ↓ 第2层过滤：提炼支撑要点
  支撑要点（3~6个bullet，每个≤15字）
       ↓ 第3层过滤：萃取亮点数据
  关键数据（1~3个数字/百分比）
```

**最终放上 SVG 的只有第2层和第3层的产物**。第1层的核心结论用于 speaker notes，不放在页面上。

**❌ 差（直接搬原文）**：
```xml
<text x="84" y="200" font-size="14">
  我们依托哈工大在智能人机交互领域的深厚积累，
  团队成员涵盖材料科学、人工智能、电子信息和系统工程
  四大学科方向，拥有跨学科融合的独特优势，
  发表了50余篇核心期刊论文...
</text>
```
大段文字，密不透风，观众看不到重点。

**✅ 好（经过漏斗过滤后）**：
```xml
<!-- 亮点数据层（第3层产物）→ 大数字 -->
<text font-size="48" font-weight="bold" fill="[PRIMARY]">50+</text>
<text font-size="16">核心期刊论文</text>
<!-- Badge -->
<rect ... fill="[PRIMARY]" fill-opacity="0.1"/>
<text font-size="13" fill="[PRIMARY]">国际先进水平鉴定</text>
<!-- 支撑要点层（第2层产物）→ 列表 -->
<text font-size="14">• 材料科学+AI+电子 跨学科</text>
<text font-size="14">• 10+ 项授权发明专利</text>
<text font-size="14">• 国防科工局鉴定认可</text>
```

### 规则 T2：每页的内容必须分配到 5 个视觉层级

源文档内容经过漏斗过滤后，必须分配到以下 5 个层级中。**每个层级有固定的视觉表达方式**：

| 层级 | 内容类型 | 视觉表达 | 字号/颜色 | 例子 |
|------|---------|---------|----------|------|
| **L1 标题栏** | 该页/卡片的主题名称 | 有色标题栏 + 白色文字 | 17-20px bold 白色 | "学术论文" |
| **L2 大数字** | 最震撼的 1 个数据 | 居中超大字 | 36-48px bold 主题色 | "9" |
| **L3 Badge** | 数据的定性描述 | 药丸形标签 | 13px 主题色 | "SCI收录 8篇" |
| **L4 列表** | 3~6 个支撑要点 | • 前缀列表 | 13-14px 灰色 | "• IEEE Sensors Journal" |
| **L5 底注** | 总结/补充/信誉背书 | 分割线下方文字 | 12px 主题色 | "团队核心成员均为第一作者" |

**❌ 差（全部堆在同一个层级）**：
```xml
<text font-size="14">我们发表了9篇学术论文</text>
<text font-size="14">其中SCI/EI收录8篇</text>
<text font-size="14">包括IEEE Sensors Journal</text>
<text font-size="14">IMWUT/UbiComp等顶级期刊</text>
<text font-size="14">团队核心成员均为第一作者</text>
```
全部 14px、同颜色、同格式——没有任何视觉层次，观众不知道该看哪里。

**✅ 好（分配到 5 个层级）**：
```xml
<!-- L1: 标题栏 -->
<rect ... fill="[PRIMARY]"/>
<text fill="#FFFFFF" font-size="17" font-weight="bold">学术论文</text>

<!-- L2: 大数字 -->
<text font-size="48" font-weight="bold" fill="[PRIMARY]">9</text>
<text font-size="16" fill="#263238">篇学术论文</text>

<!-- L3: Badge -->
<rect rx="14" fill="[PRIMARY]" fill-opacity="0.1"/>
<text font-size="13" fill="[PRIMARY]">SCI/EI收录 8篇</text>

<!-- L4: 列表 -->
<text font-size="13" fill="#546E7A">• IEEE Sensors Journal</text>
<text font-size="13" fill="#546E7A">• IMWUT/UbiComp</text>
<text font-size="13" fill="#546E7A">• ICASSP 2023/2024</text>

<!-- L5: 底注 -->
<rect ... height="1" fill="#CFD8DC"/>  <!-- 分割线 -->
<text font-size="12" fill="[PRIMARY]">团队核心成员均为第一/通讯作者</text>
```

同样的信息，视觉层次完全不同。观众 3 秒内就知道"9 篇论文、8 篇 SCI"。

### 规则 T3：列表项的写法规则

**❌ 差（整句话搬上去）**：
```
• 我们开发了基于仿生水膜鱼网结构的液态金属柔性应变传感器，具有优异的灵敏度
```
太长，一行放不下，视觉上溢出卡片。

**✅ 好（压缩到 ≤15 个中文字）**：
```
• 仿生液态金属柔性传感器
```

**列表项精简公式**：

```
原文句子 → 删除所有修饰语 → 删除"我们""本项目" → 保留名词+动词核心 → ≤15字
```

| 原文 | 精简后 |
|------|-------|
| 我们开发了基于仿生水膜鱼网结构的液态金属柔性应变传感器 | 仿生液态金属柔性传感器 |
| 该方案在中航光电完成了深度产业验证，培训周期缩短了40% | 中航光电验证 · 培训周期↓40% |
| 团队成员涵盖材料科学、人工智能、电子信息 | 材料+AI+电子 跨学科团队 |
| 获得了黑龙江省互联网+省赛金奖 | 互联网+省赛金奖 |

**技巧**：

- 用 `·` 或 `|` 分隔同一行的两个信息点
- 用 `+` 连接并列名词（"材料+AI+电子"）
- 用 `↑` `↓` 表达增减趋势
- 用 `→` 表达因果或流向

### 规则 T4：每页的信息密度上限

| 布局类型 | 每张卡片最大列表项 | 每页最大总文字元素 | 每页大数字数量 |
|---------|-----------------|------------------|-------------|
| 三栏卡片 | 5~6 项 | 30 个 `<text>` | 3（每卡片 1 个） |
| 双栏卡片 | 6~8 项 | 25 个 `<text>` | 2（每卡片 1 个） |
| 四宫格 | 3~4 项 | 28 个 `<text>` | 4（每格 1 个） |
| 全宽+双栏 | 4~5 项 | 25 个 `<text>` | 1~2 |

**超过上限怎么办？** → 砍内容。具体的砍法：

1. 先砍列表中最不重要的项（通常是最后一项）
2. 如果还是超，合并两个相关列表项为一项
3. 如果还是超，这页的内容应该拆成两页

**绝对禁止**为了塞更多内容而缩小字号。最小正文字号 13px 不可突破。

### 规则 T5：文字长度与卡片宽度的适配

一行文字不能超出卡片的可用宽度。计算方法：

```
卡片可用文字宽度 = 卡片宽度 - 左内距(24px) - 右内距(24px)

三栏卡片(370px宽): 可用 = 370 - 48 = 322px
双栏卡片(565px宽): 可用 = 565 - 48 = 517px

中文14px ≈ 每字宽度 14~16px（含字间距）
三栏卡片每行最多: 322 / 15 ≈ 21 个中文字
双栏卡片每行最多: 517 / 15 ≈ 34 个中文字

英文14px ≈ 每字宽度 8~9px
三栏卡片每行最多: 322 / 8.5 ≈ 38 个英文字符
```

**超出行宽时**：
1. 首选：精简文字使其适配一行
2. 次选：拆为两行（第二行缩进到 `x+16`）
3. 禁止：缩小字号

```xml
<!-- 文字过长需要手动拆行 -->
<text x="479" y="345" font-size="13" fill="#546E7A">② 光纤与惯性单元融合手部</text>
<text x="495" y="365" font-size="13" fill="#546E7A">动作捕捉方法</text>
```

### 规则 T6：不同页面类型的内容结构模板

**类型 A：数据展示页（适用于：成果、财务、市场规模）**
```
每张卡片的内容结构：
├── L1 标题栏: 类别名 + 图标
├── L2 大数字: 最核心的 1 个数据
├── L3 Badge: 数据的定性标签
├── 分割线
├── L4 列表: 3~6 项细节
├── 分割线
└── L5 底注: 1 句总结
```

**类型 B：论述页（适用于：背景、现状、策略）**
```
每张卡片的内容结构：
├── L1 标题栏: 论点名 + 图标
├── 小标题: 论据类别（16px bold, BODY色）
├── L4 列表: 3~4 项论据
├── 分割线
├── 小标题: 第二组论据类别
├── L4 列表: 2~3 项论据
├── 分割线
└── 底部总结框: 浅色底 + 居中总结语
```

**类型 C：人物页（适用于：团队、导师、专家）**
```
每张卡片的内容结构：
├── L1 标题栏: 全色背景
├── 头像占位: 圆形区域（主题色淡底 + 图标）
├── 姓名: 22px bold BODY色
├── 角色 Badge: 药丸标签
├── 分割线
├── 背景: 14px（职称/机构）
├── 方向标题: "研究方向" 16px bold
├── L4 列表: 3~4 项专长
├── 分割线
└── 底部贡献框: 浅色底 + 居中贡献说明
```

### 规则 T7：怎么为卡片选择"大数字"

每张卡片的大数字是**这张卡片最想让观众记住的一个数据**。选择规则：

| 优先级 | 选什么 | 例子 |
|--------|-------|------|
| 1（最优） | 有冲击力的绝对数字 | `9`篇论文、`4`项专利、`3500亿` |
| 2 | 百分比变化 | `↓40%`成本、`↑300%`效率 |
| 3 | 倍数对比 | `10×`速度提升、`50%`成本优势 |
| 4 | 概括性名词 | 仅在没有数据时使用，如卡片标题 |

**铁律**：如果源文档中某节有数据，卡片中必须有大数字。没有大数字的卡片 = 没有焦点的卡片。

### 规则 T8：怎么为每页选择内容焦点

一页中只能有 **1 个核心信息**。选择方法：

```
问自己：如果观众只记住这一页的 1 句话，应该记住什么？
↓
那句话就是这页的核心信息
↓
核心信息的数据 → 放在大数字位置
核心信息的结论 → 放在总结条/底注位置
其他内容都是支撑材料 → 放在列表中
```

**❌ 差**：一页上 3 个同样大的数字、5 个同等重要的论点，观众什么都记不住。

**✅ 好**：一页上 1 个最大最亮的数字（48px主题色），2~3 个支撑数据（24px, 在卡片内），其余是列表文字。

### 规则 T9：副标题的作用和写法

页面标题下方可以放一行副标题，用于**用一句话概括本页的核心论点**：

```xml
<!-- 页面标题 -->
<text x="80" y="70" font-size="32" font-weight="bold" fill="#263238">创新成果</text>
<!-- 副标题（紧跟标题下方） -->
<text x="80" y="105" font-size="15" fill="#546E7A">"理论-专利-软硬协同"三位一体知识产权体系</text>
```

**写法**：
- 字号 15px，颜色 `MUTED`（#546E7A）
- 内容用引号或破折号包裹的核心概念
- 长度 ≤ 25 个中文字
- 不是每页都需要，只在信息结构复杂的页面使用

### 规则 T10：底部总结框的内容写法

底部总结框是卡片或页面底部的"一句话带走"：

**❌ 差**：`"我们的团队在多个领域取得了优异成绩"` → 空话，没有信息量

**✅ 好**：
- `"以赛促学 · 以赛促创"` → 精炼的行动纲领
- `"苗圃→孵化→加速 全程护航"` → 用箭头表达流程
- `"学中做、做中学 的良性循环"` → 对偶句式增加记忆点

**写法公式**：
```
方式1: 动词对仗     "学中做 · 做中学"
方式2: 流程箭头     "立项→研发→验证→转化"
方式3: 数据总结     "累计覆盖 50+ 企业 · 服务 1000+ 用户"
方式4: 核心主张     "国产高精度交互装备引领者"
```

**铁律**：总结框的文字 ≤ 20 个字。超过就不是总结，是段落。

---

## 第八部分：Forbidden — 绝对禁止清单

| # | 禁止行为 | 为什么差 | 正确做法 |
|---|---------|---------|---------|
| F1 | 卡片用灰色/灰蓝背景 | 看起来廉价、沉闷 | 白底 + 阴影 |
| F2 | 所有卡片标题栏同色 | 无法区分并列元素 | 每栏不同主题色 |
| F3 | 没有图标 | 页面缺少视觉锚点 | 标题旁+卡片内+列表前 |
| F4 | 正文字号 < 13px | PPTX 中无法阅读 | 最小 13px |
| F5 | 没有顶部渐变条 | 缺少品牌统一感 | 每页 6px 条 |
| F6 | 页脚不一致或缺失 | 不专业 | 每页完全相同的 footer |
| F7 | 封面只有标题文字 | 极其simplistic | 7 层叠加结构 |
| F8 | 连续 2+ 页相同布局 | 单调乏味 | 每页必须变换布局 |
| F9 | 没有任何大数字 | 缺乏视觉冲击力 | 核心数据 ≥ 36px |
| F10 | 颜色超出色板范围 | 不协调 | 只用色彩角色表中的颜色 |
| F11 | 直接对源文档"原文照搬" | 密度失控，无焦点 | 信息漏斗三层过滤 |
| F12 | 卡片中没有大数字 | 所有文字同层级 | 至少 1 个 ≥36px 数据 |
| F13 | 列表项超过 15 个中文字 | 溢出卡片宽度 | 精简文字 ≤15字/项 |
| F14 | 为了塞内容缩小字号 | 违反最小字号规则 | 砍内容，不缩字号 |
| F15 | 总结框超过 20 字 | 不是总结，是段落 | 精炼为口号/公式 |
| F16 | 使用 `feDropShadow` | 阴影太弱，卡片沉进页面 | 5步 feGaussianBlur 链 |
| F17 | header 色条 y≠40 或 y=18 | 上下文衰减，坐标漂移 | 每页原样复制锚点模板 |
| F18 | 图标X与标题不匹配 | 重叠或离太远 | 查A3参考表：80+(字数×30)+12 |
| F19 | 卡片内只有裸文字列表 | 没有层次/空白过多 | ≥3 种元素（C7 规则） |
| F20 | 用 "N"、"多" 当大数字 | 滑稽，不是数据 | 只用具体数字或不放 |
| F21 | 大数字 ≥ 64px | 比例失调，喧宾夺主 | 大数字 36-48px |
| F22 | 总结条只有灰底+裸文字 | 丢失了色条/图标/粗体 | 4元素总结条 |
| F23 | 人物卡没有头像占位圆 | 极其简陋 | 用 L6 人物卡模板 |
| F24 | 后半段放弃前半段的元素 | 上下文遗忘 | 每 5 页执行 A4 自检 |
| F25 | 图标 scale ≠ 1.875 | 图标大小不统一 | 永远 scale(1.875) |
| F26 | 超过 8 页不做重锚 | 上下文窗口溢出→风格断裂 | 每 8 页粘贴锚点代码块（B1 规则） |

---

## 第九部分：Quick Self-Check — 每页生成后的 10 秒自检

生成每一页后，快速检查以下 **12 项**：

```
=== 骨架检查 ===
□ 顶部 6px 渐变条在 y=0？（不是 y=40）
□ 标题三件套（y=40色条 + y=70标题 + 紧跟图标）坐标正确？
□ 图标目视紧跟标题？（不在 x>1000，不与文字重叠）
□ 图标 scale = 1.875？（不是 3.0 或 2.25）
□ 页脚 y=690，格式与前一页完全一致？
□ filter 是 5 步 feGaussianBlur 版本（不是 feDropShadow/feComponentTransfer）？

=== 内容检查 ===
□ 卡片内包含 ≥3 种元素（标题栏/大数字/Badge/信息卡/列表/底注）？
□ 卡片空白率 ≤ 40%（没有大片空白）？
□ 大数字有完整 4 件套（数字+单位+Badge+分割线）？
□ 每个列表项 ≤ 15 个中文字？

=== 布局检查 ===
□ 这一页的布局与前一页不同？
□ 总结条有 4 元素（色底+色条+图标+粗体标题）？
```

全部打 ✓ 才可以继续下一页。

**每 8 页执行一次 B1 重锚（粘贴锚点代码块）+ A4 一致性自检。**

---

## 第十部分：长文档注意力锚定

> ⚠️ 生成 20+ 页 PPT 时，本节**必须遵守**。

### 为什么会出问题？

每页 SVG 约 10-16KB（~3K-4K tokens）。生成到第 16 页时，仅 SVG 输出就累计 **~50K tokens**。加上 system prompt、源文档、设计规格，总 token 已接近模型上下文窗口上限。

**后果**：早期的设计指令（defs 模板、filter 代码、坐标规则）被挤出注意力窗口。模型从第 17 页开始"失忆"，自行发明新的 gradient ID、filter 实现和坐标体系。这不是渐变衰减，是**断崖式切换**——前一页还完美，下一页整套设计系统全变了。

### 规则 B1：每 8 页粘贴一次锚点代码块

每生成 **8 页**后，在继续下一页之前，**必须在输出中重复一次以下锚点代码块**：

```xml
<!-- ===== 锚点重锚 ===== -->
<!-- 以下页面继续使用完全相同的设计系统，不允许修改任何参数 -->
<defs>
  <linearGradient id="headerGrad" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="[PRIMARY]"/>
    <stop offset="100%" stop-color="[SECONDARY]"/>
  </linearGradient>
  <filter id="cardShadow" x="-15%" y="-15%" width="140%" height="140%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="10"/>
    <feOffset dx="0" dy="4" result="offsetBlur"/>
    <feFlood flood-color="#000000" flood-opacity="0.1" result="shadowColor"/>
    <feComposite in="shadowColor" in2="offsetBlur" operator="in" result="shadow"/>
    <feMerge><feMergeNode in="shadow"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
<!-- 渐变条: y=0 h=6 | 色条: y=40 | 标题: y=70 | 图标: y=46 -->
<!-- 背景: #F5F7FA | 页脚: y=690 -->
```

**效果**：将设计参数从"远端记忆"拉回"近端上下文"，防止注意力窗口挤出关键指令。

### 规则 B2：锚定时机的量化标准

| 页面号 | 累计 SVG tokens | 风险等级 | 操作 |
|-------|----------------|---------|------|
| 1-8 | ~25K | 🟢 安全 | 正常生成 |
| 8→9 | ~25K | — | **第一次重锚** |
| 9-16 | ~50K | 🟡 警戒 | 正常生成 |
| 16→17 | ~50K | — | **第二次重锚** |
| 17-24 | ~75K | 🔴 危险 | 正常生成 |
| 24→25 | ~75K | — | **第三次重锚** |
| 25+ | ~100K | 🔴 极危险 | 正常生成 |

### 规则 B3：SVG Review 是最终安全网

即使执行了重锚，仍然可能出现注意力漂移。**所有设计一致性问题都将在 Step 6.5 SVG Review 阶段被检测和修复**（见 `workflows/svg-review.md`）。

重锚是"尽力预防"，SVG Review 是"兜底修复"。两者缺一不可。


