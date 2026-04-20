# PPT Master SVG 并发优化计划

修订时间：2026-04-20

## 目标重校准

近期目标不是证明 1500 万 TPM 能稳定跑 50 个并发，而是先把 25 个并发请求跑起来，并尽量提高吞吐，同时不牺牲 PPT 质量。

2026-04-20 实施版目标已进一步收敛：

- TPM 预算：优先控制在 1500 万以内。
- 并发任务：先跑 15 个任务。
- 单任务 SVG 并行窗口：默认 3。
- 全局 SVG slot：默认 45。
- SVG 分组：默认 `2+3+4+5+6+7+8` ramp 分组。
- SVG 并行方式：默认 anchor-first，先生成第一个 anchor batch，再并行后续 batch。

当前判断：

- 3 个并发任务压测时，TPM 峰值约 400 万。
- 每个任务内配置为 `batchMode=parallel`、`batchSize=5`、`parallelBatchWorkers=7`。
- PPT 页数固定上限约 35 页，因此单任务最多约 7 个 SVG batch。
- 如果 25 个任务都按 7 路 SVG 并行，最坏会出现 25 * 7 = 175 个 SVG qwen session，还不包括 spec、notes 和修复回合。这个放大不值得直接尝试。
- 乱码问题只按终端编码问题看待，不作为本计划的优化事项。

本轮计划的验收重点：

1. 15 个并发请求能稳定进入系统并完成；25 并发作为下一阶段目标。
2. SVG 质检、PPTX 导出、讲稿完整性不退化。
3. TPM 峰值优先控制在 1500 万以内，不能因为内部并发乘法导致失控。
4. 为后续 50 并发保留调度接口，但不把 50 并发作为本轮硬验收。
5. 单个 PPT 任务的生成时间尽量控制在 40 分钟内。

## 当前架构摘要

API 层：

- `api_service/app.py` 用 `asyncio.Semaphore(settings.max_concurrent_jobs)` 控制同时执行的任务数。
- 每个请求通过 `asyncio.to_thread(_process_request, ...)` 进入同步生成流程。
- `api_service/runner.py` 为每个任务启动一个 `qwen_ppt_runner.py` 子进程。
- 任务之间有独立 job 目录和独立 project 目录，文件输出基本隔离。

Runner 层：

- 主流程是 markdown 导入、slide plan、design spec、SVG 生成、notes、质检/修复、`finalize_svg.py`、`svg_to_pptx.py`。
- design spec 和 notes 优先走 direct API，失败后回落 qwen CLI。
- SVG 生成有三种模式：
  - `never`：单 session 顺序生成，质量一致性最好，速度慢。
  - `always`：分 batch 串行，每个 batch 内顺序生成。
  - `parallel`：多个 batch 并行，每个 batch 内顺序生成。
- 当前压测脚本把每个任务的 `parallelBatchWorkers` 固定成 7，这对少量并发可用，但对 25 并发风险较大。

质量保护：

- `design_spec.md`、`slide_plan.json`、`svg_anchor_context.json`、executor style、icon candidates 是 SVG 的主要锚点。
- 每个 batch 完成后会检查缺失/多余 SVG、XML 合法性、emoji、icon 引用、图标覆盖率。
- 全量生成后还有 `svg_quality_checker.py`、`svg_auto_repair.py`、`finalize_svg.py`、`svg_to_pptx.py`。
- 这些质量链路不能为了并发而跳过。

## 与 rag-agent 文档生成链路的关系

`W:\AIPPT cli\rag-agent` 中的 `server_v2.py` 当前链路是：

1. `engine.run(initial_state)` 生成最终 Markdown，写入 `final_state["final_planbook"]`。
2. 用同一份 Markdown 生成 PDF：`m2pdf(result_content, output_pdf=output_path)`。
3. 上传 PDF，得到 `file_url`。
4. 用同一份 Markdown 生成 Word：`m2docx(result_content, output_path=w_output_path, base_dir=BASE_DIR)`。
5. 上传 Word，得到 `word_url`。
6. 调用 `send_plant_PPT(final_state, file_url=file_url, word_url=word_url)`。
7. `send_plant_PPT` 给 PPT 服务发送：
   - `fileUrl`
   - `wordUrl`
   - `title`
   - `content = state.get("final_planbook")`

PPT 服务侧的 `api_service/app.py` 只把 `content` 写成 `source.md`，再交给 runner 生成 PPT。`fileUrl` 和 `wordUrl` 只是后续回调字段，不参与 PPT 内容生成。

结论：

- PPT 依赖 Markdown，也就是 `final_planbook`。
- PPT 不依赖已生成的 Word 或 PDF 文件。
- 当前“PDF/Word 生成与上传完成后才开始 PPT”是业务回调顺序导致的串行等待，不是技术输入依赖。
- 因此可以把 PPT 触发前移到 Markdown 完成后，并让 PDF/Word 生成上传与 PPT 生成并行执行。

需要注意：

- 当前 PPT API 会在生成完成后自己回调，并把传入的 `fileUrl/wordUrl` 带回去。
- 如果 PPT 提前启动时还没有 `fileUrl/wordUrl`，不能让 PPT API 直接提前回调最终业务方，否则会缺 PDF/Word 链接。
- 推荐改成“最终聚合回调”：rag-agent 同时启动 PPT、PDF、Word，等三个 URL 都齐后由 rag-agent 统一回调；或者给 PPT API 增加 `callbackMode=none/defer`，让它只返回 PPT 结果，不直接回调业务方。

## 40 分钟时间预算

已知单任务 7 路 SVG 并行约 13 分钟，这是一个很有价值的基线。它说明在单任务环境下，PPT 生成有约 3 倍延迟余量可以用来换并发资源。

但 25 并发下要区分两个时间口径：

1. 从 Markdown 准备好开始计时。

   这是 PPT 服务自身的生成耗时。因为 PPT 只依赖 MD，这个口径更适合评估 PPT worker 配置。

2. 从用户提交问卷开始计时。

   这是端到端耗时，包含 rag-agent 文档生成、Mermaid 转图、PDF/Word 生成上传、PPT 生成、PPT 上传和回调。这个口径下，PPT 实际可用时间是 `40 分钟 - 文档生成耗时 - 必要回调/上传耗时`。

当前 `rag-agent` 是文档完成后才开始 PPT，因此如果端到端 SLA 是 40 分钟，PPT 并没有完整 40 分钟。把 PPT 提前到 Markdown 完成后立即启动，并与 PDF/Word 并行，是释放时间预算的最直接办法。

另外，`rag-agent/server_v2.py` 中 `requests.post(url, json=send_info, timeout=900)` 只给 PPT 请求 900 秒，也就是 15 分钟。这个值低于 40 分钟。如果继续使用同步调用，25 并发降速后很可能出现客户端超时。需要把这里改成异步 job 模式，或至少把 timeout 调到覆盖目标 SLA。

基于 35 页上限和 `2+3+4+5+6+7+8` 分组，可以粗略估算任务内窗口的时间放大：

- 窗口 7：所有 batch 同时跑，接近当前 13 分钟基线，但资源峰值最高。
- 窗口 4：两轮完成，理论 SVG 段放大约 1.6 倍。
- 窗口 3：三轮完成，理论 SVG 段放大约 2.4 倍。
- 窗口 2：四轮完成，理论 SVG 段放大约 2.9 倍。

所以：

- 如果 40 分钟是“Markdown 已完成后的 PPT SLA”，窗口 2 可以作为 25 并发首轮尝试。
- 如果 40 分钟是“用户提交后的端到端 SLA”，窗口 2 可能偏紧，应该优先使用窗口 3，配合全局 slot 限制总 SVG session。
- 如果 25 并发窗口 3 的 TPM 峰值不可接受，再退到动态窗口：活跃任务少时给 3-4，活跃任务多时给 2。

## 对 2+3+4+5+6+7+8 的判断

这个思路是可取的，但要定义清楚：它应该是“页数组块策略”，不是“固定同时开 7 路”。

因为 2+3+4+5+6+7+8 正好覆盖 35 页，它比固定 `batchSize=5` 有几个优势：

- 前 2 页可以作为视觉锚点，通常包括封面和第一张内容页。
- 前部小 batch 更容易快速产出样板，降低后续 batch 风格漂移。
- 后部较大 batch 可以摊薄 prompt/context 成本，减少过多小 session 的重复开销。
- 单任务最多仍然是 7 个 batch，不会随着页数继续膨胀。

但如果 7 个 batch 全部同时启动，25 并发时仍然可能是 175 个 SVG session，所以还需要“并行窗口”控制。

建议把它拆成两个概念：

1. `batch_partition = 2+3+4+5+6+7+8`

   负责把一套 PPT 切成最多 7 个连续页组。

2. `parallel_window = 1/2/3/...`

   负责控制同一个任务内同时跑几个 SVG batch。25 并发下不建议一开始超过 2。

## 推荐 SVG 分组算法

设总页数为 `N`，最大 35。

基础分组：

```text
target_groups = [2, 3, 4, 5, 6, 7, 8]
```

从第一页开始连续切分：

- `N=10` -> `[2, 3, 4, 1]`，最后 1 页建议并入前一组，得到 `[2, 3, 5]`。
- `N=18` -> `[2, 3, 4, 5, 4]`。
- `N=25` -> `[2, 3, 4, 5, 6, 5]`。
- `N=30` -> `[2, 3, 4, 5, 6, 7, 3]`。
- `N=35` -> `[2, 3, 4, 5, 6, 7, 8]`。

尾部规则：

- 如果最后一组只有 1 页，并入前一组。
- 如果最后一组 2 页及以上，可以保留。
- 单组建议不超过 8 页，避免一次 qwen turn 输出过长导致失败或质量下降。

## 推荐调度方式

### 方案 A：25 并发首轮保守压测

目标：先证明 25 个并发请求能完成。这个方案适用于“PPT 从 Markdown 完成后开始计时”的口径。

配置建议：

- `PPT_API_MAX_CONCURRENT_JOBS=25`
- `batchMode=parallel`
- `batchPartition=2+3+4+5+6+7+8`
- `parallelBatchWorkers=2`
- `specModel=qwen3.6-plus`
- `notesModel=qwen3.5-flash`

预期：

- 每个任务最多 2 个 SVG batch 同时活跃。
- 25 个任务的 SVG 高峰约 50 个 qwen session。
- 用当前 3 并发 21 个 SVG session 约 400 万 TPM 粗估，50 个 SVG session 可能在 950 万 TPM 左右，再加 spec/notes 和重试开销，仍属于可以尝试的区间。

质量策略：

- 第一个 2 页 batch 必须先完成，作为 anchor batch。
- 后续 batch prompt 必须读取第一个 batch 的 SVG，尤其是封面和第一张内容页。
- 如果暂时不改代码做 anchor-first，则首轮可以先保留当前流程，但 workers 不要超过 2。
- 如果 40 分钟按用户提交端到端计算，首轮可直接改用 `parallelBatchWorkers=3`，否则文档生成耗时会挤压 PPT 可用时间。

### 方案 B：25 并发第二轮进取压测

目标：观察系统是否能承受更高吞吐，或满足端到端 40 分钟 SLA。

配置建议：

- `PPT_API_MAX_CONCURRENT_JOBS=25`
- `batchMode=parallel`
- `batchPartition=2+3+4+5+6+7+8`
- `parallelBatchWorkers=3`

预期：

- SVG 高峰约 75 个 qwen session。
- 按粗估可能接近或短时超过 1500 万 TPM，虽然本轮不强制满足 1500 万，但要重点观察失败率、重试次数和最终 PPT 质量。

停止条件：

- SVG batch follow-up 明显增加。
- `svg_quality_checker.py` 错误率上升。
- qwen CLI 子进程大量失败或超时。
- 内存/CPU/文件 I/O 出现持续瓶颈。

### 方案 C：不建议直接跑

不建议 25 并发直接使用：

- `parallelBatchWorkers=7`
- 固定 `batchSize=5`
- 无全局 slot

原因：

- 25 * 7 = 175 个 SVG session，TPM 和子进程数量都会显著放大。
- batch 之间没有真实的前序视觉 anchor，风格一致性风险也会升高。
- 一旦失败触发修复回合，token 消耗会进一步放大。

## Anchor-first 并行策略

为了兼顾质量和并发，推荐把 SVG parallel 改成两阶段：

### 第 1 阶段：锚点 batch

先生成第一个 batch，页数为 2：

- 通常是封面 + 第一张内容页。
- 这个 batch 串行执行，不与后续 batch 同时跑。
- 完成后写入 `svg_anchor_context.json`：
  - `global_anchor_svg_paths`
  - `anchor_style_summary`
  - `header_footer_rules`
  - `color_role_examples`
  - `card_and_icon_examples`

### 第 2 阶段：窗口并行

后续 batch 进入并行窗口：

- 25 并发首轮：每任务窗口 = 2。
- 如果质量稳定，再尝试窗口 = 3。
- 每个 batch prompt 都强制读取 anchor SVG。
- batch 内仍然按页序顺序生成。

这样可以避免“所有 batch 互相不知道彼此视觉结果”的问题。

## 全局并发预算

如果要把 25 并发跑稳，最好不要只靠每个任务自己的 `parallelBatchWorkers`，还需要全局预算。

建议先做轻量版：

- `PPT_API_LLM_SVG_SLOTS=50` 用于 25 并发首轮。
- `PPT_API_LLM_SPEC_SLOTS=6`
- `PPT_API_LLM_NOTES_SLOTS=10`
- `PPT_API_POSTPROCESS_SLOTS=4`

实现方式：

- 单容器可用 SQLite lease 或文件锁。
- 每个 qwen CLI/direct API 调用前申请 slot。
- 调用完成、失败或超时后释放 slot。
- lease 记录 `job_id`、`stage`、`pid`、`timestamp`，支持超时回收。

这样即使某个请求传了 `parallelBatchWorkers=7`，系统也不会无限放大。

## 压测矩阵

先围绕 25 并发设计，不急着跑 50。

| 轮次 | 并发请求 | API max jobs | 任务内窗口 | SVG 分组 | 目的 |
|---|---:|---:|---:|---|---|
| baseline | 3 | 3 | 7 | 5*最多7组 | 对齐当前 400 万 TPM 现状 |
| T1 | 10 | 10 | 2 | 2+3+4+5+6+7+8 | 验证分组和质量 |
| T2 | 25 | 25 | 2 | 2+3+4+5+6+7+8 | 首次 25 并发目标 |
| T3 | 25 | 25 | 3 | 2+3+4+5+6+7+8 | 进取吞吐测试 |
| T4 | 25 | 25 | 动态 2-3 | 2+3+4+5+6+7+8 | 根据全局 slot 自动调度 |

每轮记录：

- 成功率。
- P50/P90/P99 完成时间。
- TPM 峰值和 1 分钟滑动平均。
- qwen CLI 子进程峰值。
- runner 子进程数量。
- CPU、RSS、系统内存。
- spec/svg/notes/postprocess 各阶段耗时。
- `usage_summary.json` 中的 per-stage token。
- SVG 质检错误数。
- SVG batch follow-up 次数。
- 最终 PPTX 是否可打开、页数是否正确、notes 是否完整。

## 代码改造顺序

### 第一步：压测脚本参数化

把 `stress_test.sh` 中硬编码的：

- `batchSize=5`
- `parallelBatchWorkers=7`
- `specModel=qwen3.6-plus`
- `notesModel=qwen3.5-flash`

改成可由命令行或环境变量覆盖。

建议默认：

- `parallelBatchWorkers=2`
- `batchPartition=adaptive_2_3_4_5_6_7_8`

如果暂时没实现新分组，先只把 workers 从 7 降到 2 做 25 并发首测。

### 第二步：实现 adaptive batch partition

在 `qwen_ppt_runner.py` 中替换或扩展 `split_plan_into_batches`：

- 保留旧的 `batch_size` 兼容。
- 新增 `batch_partition`：
  - `fixed`：旧逻辑。
  - `ramp_2_3_4_5_6_7_8`：新逻辑。
- API 请求模型增加可选字段 `batchPartition`。
- 未传时默认仍可用旧逻辑，避免破坏兼容。

### 第三步：实现 anchor-first parallel

改造 `execute_parallel_svg_generation`：

1. 先取第一个 batch，单独执行。
2. 将第一个 batch 产出的 SVG 写入 `svg_anchor_context.json`。
3. 后续 batch 用 `ThreadPoolExecutor` 并行执行。
4. prompt 中加入 anchor SVG 路径。

### 第四步：加全局 LLM slot

先只对 SVG batch 做 slot：

- 每个 batch 调用 qwen 前申请 `svg_slot`。
- 获取不到就等待。
- `/metrics` 显示 active/waiting slots。

然后再把 spec、notes、postprocess 纳入 slot。

### 第五步：质量回归检查

固定抽检每轮压测产物：

- 每轮至少抽 3 个 PPT。
- 检查封面、第一内容页、中部页、尾页。
- 看标题栏、footer、图标、卡片、配色、图表风格是否跨 batch 漂移。
- 只要质量明显下降，就先回退窗口数，不再继续提高并发。

## 推荐当前行动

最小尝试路径：

1. 先确认 SLA 口径：如果只算 PPT，25 并发首测用窗口 2；如果算端到端，25 并发首测用窗口 3。
2. 先不改 SVG 分组，只把 25 并发压测的 `parallelBatchWorkers` 从 7 降到 2 或 3。
3. 同时把 rag-agent 中 PPT 触发前移到 Markdown 完成后，PDF/Word 和 PPT 并行跑，避免无谓串行等待。
4. 如果 25 并发能完成，再实现 `2+3+4+5+6+7+8` 分组。
5. 新分组上线后，跑 10 并发验证质量，再跑 25 并发窗口 2/3。
6. 25 并发窗口 3 稳定后，再考虑窗口 4 或 50 并发承载。

不建议的路径：

- 不建议跳过质量检查换速度。
- 不建议直接把 `PPT_API_MAX_CONCURRENT_JOBS` 和 `parallelBatchWorkers` 同时拉高。
- 不建议在没有全局 slot 的情况下把 25 并发跑到任务内 7 路。
