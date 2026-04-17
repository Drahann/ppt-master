---
name: svg-review
description: >
  Use after Executor Step 6 (SVG generation) and before Step 7 (post-processing).
  Performs structural review and repair of generated SVGs to fix header drift,
  icon misalignment, filter degradation, text overflow, and cross-page consistency
  issues that weaker models produce during long-form generation.
---

# SVG Review — 生成后质量审查与修复

> 在 Executor 生成全部 SVG 后、进入 Step 7 后处理之前执行。
> 目标：修复弱模型生成 SVG 中的系统性错位、语法错误和跨页不一致问题。

## 定位

```
Step 6 (Executor) → ★ SVG Review ★ → Step 7 (Post-processing)
                     ↑ 你在这里
```

## 何时触发

- Executor 阶段完成后，**自动执行**
- 用户手动要求 "review SVG" / "检查SVG" / "修一下SVG"
- `svg_quality_checker.py` 报告 errors > 0 时
- 若 runner 开启 batched mode，可按 batch 单独触发；每个 batch 只修本批 SVG，最终由 runner 汇总报告并做整套校验

## 输入 / 输出

- **输入**: `<project_path>/svg_output/*.svg`
- **输出**: 就地修复的 `<project_path>/svg_output/*.svg`（修改原文件）
- **Batched mode**: 当 runner 传入当前批次清单时，只修复该批次文件；`notes/total.md` 仅在 full-deck review 中允许修改

---

## 检查流水线（6 类 30+ 项）

按以下顺序逐类检查，每类检查完毕后立即修复再进入下一类。

### C1: 骨架一致性（跨页级）

以 **第一个内容页**（通常 slide_02）为基准，逐页比对：

| # | 检查项 | 基准提取方式 | 常见错误 |
|---|--------|------------|---------|
| 1.1 | gradient ID | `id="headerGrad"` | 中段突变为 `titleGradient` |
| 1.2 | gradient 方向 | `x1="0" y1="0" x2="1" y2="0"` | 变为对角线 `x2="100%" y2="100%"` |
| 1.3 | 渐变条 y 坐标 | `y="0" height="6"` | 漂到 `y="40"` 与色条重叠 |
| 1.4 | filter 实现 | 5步 feGaussianBlur (stdDeviation=10) | 降级为 feComponentTransfer 或 feDropShadow |
| 1.5 | 色条 y 坐标 | 色条起始 `y="40"` | 漂到 y=18 或 y=0 |
| 1.6 | 标题 y 坐标 | `y="70"` | 漂移 |
| 1.7 | footer 格式 | 文字内容+页码格式 | 中段丢失机构名/页码格式变化 |
| 1.8 | XML 声明 | `<?xml version="1.0"?>` | 中段丢失 |
| 1.9 | 背景色 | `fill="#F5F7FA"` 或 `#FFFFFF` | 不一致 |

**修复方法**：从基准页提取 defs 块、header 块、footer 块，替换异常页的对应块。

```
修复伪代码：
baseline = parse(slide_02)
for each page in svg_output:
    if page.gradient_id != baseline.gradient_id:
        replace page.defs with baseline.defs
    if page.footer != baseline.footer:
        replace page.footer with baseline.footer (保留页码数字)
```

### C2: 标题图标对齐

逐页检查标题文字与图标的 X 坐标关系：

```
正确的图标 X = 80 + (标题中文字数 × 30) + 12
```

| # | 检查项 | 判定标准 | 常见错误 |
|---|--------|---------|---------|
| 2.1 | 图标 X 偏差 | \|实际X - 理论X\| ≤ 15 | 重叠（X < 右端）或太远（X > 右端+50） |
| 2.2 | 图标 scale | 必须 = 1.875 | 出现 3.0 / 2.25 / 2.0 |
| 2.3 | 图标 Y 坐标 | 必须 = 46 | 漂移到其他值 |

**预计算参考表**：

| 标题字数 | 理论图标X |
|---------|----------|
| 3 | 182 |
| 4 | 212 |
| 5 | 242 |
| 6 | 272 |
| 7 | 302 |
| 8 | 332 |
| 9 | 362 |
| 10 | 392 |

**修复方法**：
```python
# 提取标题文字
title_text = extract_header_text(page)
char_count = len(title_text)
correct_x = 80 + char_count * 30 + 12

# 修正 translate
icon_group = find_header_icon(page)
icon_group.set_translate(correct_x, 46)
icon_group.set_scale(1.875)
```

### C3: 文字溢出检测

| # | 检查项 | 判定标准 | 修复方式 |
|---|--------|---------|---------|
| 3.1 | 单行文字超出卡片 | 中文字数 × font-size > 卡片宽度 - 2×padding | 截断或拆行 |
| 3.2 | 文字 Y 超出卡片底部 | text.y > card.y + card.height | 上移或删末行 |
| 3.3 | 文字 Y 小于卡片顶部 | text.y < card.y + header.height | 下移 |

**溢出计算公式**：
```
卡片可用宽度 = 卡片width - 2 × 20(padding)
每行最大中文字数 = floor(卡片可用宽度 / font-size)

三栏卡片(370px宽): 可用330px, font-size=13 → 最多25字
三栏卡片(370px宽): 可用330px, font-size=15 → 最多22字
双栏卡片(565px宽): 可用525px, font-size=15 → 最多35字
全宽区域(1160px宽): 可用1100px, font-size=15 → 最多73字
```

### C4: SVG 语法错误

| # | 检查项 | 检测方式 | 常见错误 |
|---|--------|---------|---------|
| 4.1 | 未闭合标签 | XML parser | `<g>` 缺少 `</g>` |
| 4.2 | 嵌套错误 | XML parser | `<g>` 闭合顺序错误 |
| 4.3 | 非法属性值 | regex | `fill="undefined"` |
| 4.4 | 重复 ID | regex | 同一文件内两个 `id="cardShadow"` |
| 4.5 | 引用缺失 | regex | `url(#xxx)` 引用不存在的 ID |
| 4.6 | `&` 未转义 | regex | 文字内 `&` 未写成 `&amp;` |
| 4.7 | `<` / `>` 未转义 | regex | 文字内 `<50ms` 未写成 `&lt;50ms` |

**修复方法**：`svg_quality_checker.py` 已覆盖部分检查。语法错误需用 XML parser 定位后手动修复。

### C5: 大数字与 Badge 完整性

| # | 检查项 | 判定标准 |
|---|--------|---------|
| 5.1 | 大数字字号 | 36-48px，禁止 ≥64px |
| 5.2 | 大数字字体 | 纯数字部分用 Arial |
| 5.3 | 大数字下方有单位文字 | 16px 描述文字 |
| 5.4 | Badge rx = height/2 | 完全药丸形 |
| 5.5 | Badge 底色 opacity | fill-opacity="0.1" |

### C6: 布局单调性

| # | 检查项 | 判定标准 |
|---|--------|---------|
| 6.1 | 连续同布局 | 相邻两页不得使用相同布局模式 |
| 6.2 | 布局类型提取 | 基于卡片数量/宽度/位置自动分类 |

**布局自动分类规则**：
```
3个等宽卡片(~370px) → 三栏
2个等宽卡片(~565px) → 双栏
4个卡片(2行2列)    → 四宫格
1个全宽+2个等宽   → 双栏+总结
中心圆+周围节点    → 辐射图
```

### C7: 图表几何完整性

适用对象：包含弧线命令 (`A rx,ry ...`) 的页面 — 饼图、环形图、进度弧、金字塔等几何图形。

| # | 检查项 | 判定标准 | 修复方式 |
|---|--------|---------|--------|
| 7.1 | 弧线端点在圆上 | 所有弧线端点到圆心的距离 = 声明的半径 (±2px) | 用三角函数重新计算端点坐标 |
| 7.2 | 相邻扇区共享端点 | 前扇区终点的 M/L 坐标 = 下一扇区的起点 | 统一到正确坐标 |
| 7.3 | 扇区角度总和 | 所有扇区的弧度之和 ≈ 360° (±1°) | 重新按比例分配角度 |
| 7.4 | 遮罩圆圆心对齐 | `<circle>` 的 cx,cy = 弧线的数学圆心 | 修正 cx,cy |
| 7.5 | 金字塔/三角形对称 | 左右两侧斜边关于中心 x 轴对称 (±3px) | 以中心线镜像修正 |
| 7.6 | 图形不超出容器 | 图表的最大外接矩形不超出其所在卡片的边界 | 缩小半径或偏移圆心 |

**环形图三步验证法**：

```python
# Step 1: 从 <circle> 提取圆心和内径
cx, cy = mask_circle.cx, mask_circle.cy
inner_r = mask_circle.r

# Step 2: 从最大弧线的 A 命令提取外径
outer_r = largest_arc.rx  # A rx,ry 中的 rx

# Step 3: 验证每个弧线端点
for segment in arc_segments:
    for point in [segment.start, segment.line_to]:
        dist = sqrt((point.x - cx)² + (point.y - cy)²)
        expected = outer_r if is_outer_arc else inner_r
        if abs(dist - expected) > 2:
            # 端点坐标错误 → 重新计算
            angle = atan2(point.y - cy, point.x - cx)
            correct_x = cx + expected * cos(angle)
            correct_y = cy + expected * sin(angle)
```

### C8: 元素重叠检查

适用对象：同层级的多个卡片（`<rect>` 或 `<path>` 带 `filter="url(#cardShadow)"`），以及卡片内部的子元素。

| # | 检查项 | 判定标准 | 修复方式 |
|---|--------|---------|--------|
| 8.1 | 同层卡片无水平重叠 | card_A.x + card_A.width ≤ card_B.x | 等分重新计算宽度和位置 |
| 8.2 | 同层卡片无垂直重叠 | card_A.y + card_A.height ≤ card_B.y | 重新分配垂直空间 |
| 8.3 | 子元素不超出父卡片 | child 的 x,y,width,height 全在 parent 内 | 缩放或重新定位 |
| 8.4 | 文字不超出卡片右边界 | text.x + (字数 × font-size) ≤ card.x + card.width - padding | 截断或拆行 |

**同层卡片等分公式**：
```
给定 N 张卡片在 [x_start, x_end] 范围内，间距 gap：
  card_width = (x_end - x_start - (N-1) × gap) / N
  card_i_x = x_start + i × (card_width + gap)

例：3张卡片在 [80, 740]，gap=20px：
  width = (740-80-2×20)/3 = 206.7px ≈ 200px
  card_0: x=80, card_1: x=300, card_2: x=520
```

---

## 执行流程

```
┌──────────────────────────────────────┐
│ 1. 运行 svg_quality_checker.py      │
│    → 发现语法级错误(C4)              │
└───────────┬──────────────────────────┘
            ↓
┌──────────────────────────────────────┐
│ 2. 提取基准页(slide_02)的设计指纹    │
│    → gradient ID, filter, footer     │
└───────────┬──────────────────────────┘
            ↓
┌──────────────────────────────────────┐
│ 3. 逐页比对骨架一致性(C1)            │
│    → 标记所有偏离基准的页面          │
└───────────┬──────────────────────────┘
            ↓
┌──────────────────────────────────────┐
│ 4. 逐页检查图标对齐(C2)              │
│    → 计算正确X坐标，标记偏差>15的     │
└───────────┬──────────────────────────┘
            ↓
┌──────────────────────────────────────┐
│ 5. 逐页检查文字溢出(C3)              │
│    → 标记超出卡片边界的文字          │
└───────────┬──────────────────────────┘
            ↓
┌──────────────────────────────────────┐
│ 5b. 逐页检查图表几何(C7)             │
│    → 验证弧线端点、扇区角度、对称性  │
└───────────┬──────────────────────────┘
            ↓
┌──────────────────────────────────────┐
│ 5c. 逐页检查元素重叠(C8)             │
│    → 检测同层卡片重叠、子元素越界    │
└───────────┬──────────────────────────┘
            ↓
┌──────────────────────────────────────┐
│ 6. 批量修复                          │
│    C1: 替换异常页的defs/header/footer│
│    C2: 修正图标translate和scale       │
│    C3: 截断溢出文字                   │
│    C4: 修复语法错误                   │
│    C7: 重新计算弧线/几何端点坐标      │
│    C8: 等分重新分配重叠卡片的宽度     │
└───────────┬──────────────────────────┘
            ↓
┌──────────────────────────────────────┐
│ 7. 输出修复报告                      │
│    → 列出每页的修改项                │
└──────────────────────────────────────┘
```

## 修复报告格式

修复完成后输出结构化报告：

```markdown
## SVG Review Report

### 骨架一致性 (C1)
- slide_17~24: defs 替换为基准版本（gradient ID/filter/渐变条位置）
- slide_17~24: footer 格式统一

### 图标对齐 (C2)
- slide_03: 图标X 184→212 (4字标题)
- slide_05: 图标X 184→212 (4字标题)
- slide_17~24: 图标X 1070→212, scale 3.0→1.875

### 文字溢出 (C3)
- slide_09 line 66: "发表于 IEEE Trans..." 超出卡片宽度，已截断

### 语法 (C4)
- 无错误

### 总计
- 检查: 32 页
- 修复: 18 处
- 类型: C1×8, C2×10, C3×0, C4×0
```

## 与 svg_quality_checker.py 的关系

| 维度 | svg_quality_checker.py | svg-review workflow |
|------|----------------------|-------------------|
| 检查级别 | 语法/兼容性（C4） | 设计/对齐/一致性（C1-C6） |
| 执行者 | 自动化脚本 | AI agent + 手动修复 |
| 依赖 | 无 | 需要 cookbook 参考表 |
| 时机 | 随时可跑 | Step 6 → Step 7 之间 |

**推荐执行顺序**：
1. 先跑 `svg_quality_checker.py` 修复硬性语法错误
2. 再执行本 workflow 修复设计级问题
3. 最后进入 Step 7 post-processing

## 常见错误速查

| 症状 | 根因 | 检查类 | 快速修复 |
|------|------|-------|---------|
| 中段页面"风格突变" | 分批生成上下文断裂 | C1 | 从基准页复制 defs 块 |
| 图标和标题重叠 | 中文字宽计算错误 | C2 | 查参考表改 translate X |
| 图标在页面最右端 | 上下文断裂 | C2 | translate X 改为 212(4字) |
| 图标太大 | scale 不一致 | C2 | 改为 scale(1.875) |
| 文字超出卡片右边 | 列表项太长 | C3 | 截断到 ≤15 中文字 |
| 阴影看不见 | feDropShadow/弱filter | C1 | 替换为 5 步 filter |
| 渐变条和色条重叠 | 渐变条 y=40 | C1 | 改为 y=0 |
| 后半段页脚消失/变化 | 上下文遗忘 | C1 | 从基准页复制 footer |
| 环形图/饼图"扭曲"或缝隙 | 内弧端点坐标计算错误 | C7 | 用三角函数重新计算端点 |
| 金字塔/三角形歪斜 | 左右不对称 | C7 | 以中心线镜像修正 |
| 同级卡片互相遮挡 | N张卡片总宽>可用空间 | C8 | 等分重新计算宽度 |
| 文字溢出卡片底部 | 内容太多或卡片太矮 | C8 | 扩高卡片或删末行 |
