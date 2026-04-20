# PPT Master SVG 并发优化计划

修订时间：2026-04-20

## 目标重校准

近期目标不是证明 1500 万 TPM 能稳定跑 50 个并发，而是先把 25 个并发请求跑起来，并尽量提高吞吐，同时不牺牲 PPT 质量。

2026-04-20 实施版目标已进一步收敛：

- TPM 预算：优先控制在 1500 万以内。
- 并发任务：先跑 15 个任务。
- 单任务 SVG 并行窗口：默认 3。
- 全局 SVG slot：默认 10，用于更保守地限制同一时刻活跃 SVG batch。
- SVG fair-share：默认开启；单任务最多可吃到请求窗口，多个任务会按活跃 SVG job 数动态分配窗口。
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

## SVG CLI 上下文压缩策略

阶段目标：SVG 生成阶段继续保留 qwen CLI，不切换 direct API；但压缩 CLI 被要求读取的静态上下文。

保留原则：

- `svg_design_cookbook.md` 是视觉质量核心，SVG 阶段继续保留全文。
- `design_spec.md`、当前 batch 的 `slide_plan`、`slide_content_digest`、`available_icon_candidates`、`svg_anchor_context.json` 继续作为每个 batch 的必要输入。
- `svg_quality_checker.py`、`svg_auto_repair.py`、`finalize_svg.py`、`svg_to_pptx.py` 全部保留。

压缩/移除原则：

- SVG executor 阶段不再显式读取 `AGENTS.md`、`QWEN.md`、`SKILL.md`、`repo_skill.md` 这类通用 workflow 文档。
- `executor-base.md`、当前 style reference、`shared-standards.md` 改为 compact excerpt。
- `image-layout-spec.md` 仅在项目实际存在图片资源或 design spec 明确引用图片时加入；无图片场景不读。
- executor skill pack 只作为 SVG 专用上下文包，不承载 source conversion、模板创建、完整 agent 工作流等无关流程。

预期效果：

- 保留 cookbook 对页面质量、卡片规则、布局多样性和 PowerPoint 兼容的约束。
- 减少每个 SVG batch 重复读取的非视觉上下文。
- 降低七路并行下的累计 prompt tokens，尤其是每个 batch 多次 tool/API call 时被反复携带的静态上下文。

## SVG 全局池与错峰策略

当前推荐把 `PPT_API_LLM_SVG_SLOTS` 视为全局 SVG batch 池大小，而不是每个 job 的并行数。

保守默认：

```env
PPT_API_LLM_SVG_SLOTS=10
PPT_API_SVG_FAIR_SHARE=1
PPT_API_SVG_FAIR_SHARE_DELAY_SECONDS=8
PPT_API_SVG_STAGE_STAGGER_SECONDS=0
PPT_API_SVG_BATCH_STAGGER_SECONDS=0
```

fair-share 规则：

- 单任务：`active_svg_jobs=1`，如果请求 `parallelBatchWorkers=7`，有效窗口可到 7。
- 5 个任务：`10 / 5 = 2`，每个 job 有效 SVG 窗口约 2。
- 50 个任务：有效窗口降到 1；全局活跃 SVG batch 仍由 `PPT_API_LLM_SVG_SLOTS=10` 卡住，不会变成 `50*2=100`。

错峰分两层：

- 请求下发错峰：`stress_test.sh` 的 `STAGGER_SECONDS`，用于让 HTTP 请求不要同一秒进入服务。
- SVG 阶段错峰：runner 的 `PPT_API_SVG_STAGE_STAGGER_SECONDS`，进入 SVG 阶段后按 job id 做稳定散列延迟，避免多个 job 在 spec 后同时启动 SVG。
- batch 提交错峰：`PPT_API_SVG_BATCH_STAGGER_SECONDS`，用于一个 job 内多个 SVG batch 提交给线程池时不要同一秒抢 slot。

500 万 TPM、5 任务测试建议：

```env
PPT_API_MAX_CONCURRENT_JOBS=5
PPT_API_LLM_SVG_SLOTS=10
PPT_API_PARALLEL_BATCH_WORKERS=7
PPT_API_SVG_FAIR_SHARE=1
PPT_API_SVG_FAIR_SHARE_DELAY_SECONDS=8
PPT_API_SVG_STAGE_STAGGER_SECONDS=60
PPT_API_SVG_BATCH_STAGGER_SECONDS=5
```

压测命令：

```bash
STAGGER_SECONDS=30 \
PARALLEL_BATCH_WORKERS=7 \
BATCH_PARTITION=ramp_2_3_4_5_6_7_8 \
bash stress_test.sh 5 http://localhost:3001
```

这里 `parallelBatchWorkers=7` 表示单任务上限；真正活跃窗口由 `PPT_API_LLM_SVG_SLOTS=10` 和 fair-share 共同决定。

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

## 最终并发设计：Redis 预算调度器

前一版固定 slot/文件 lease 只能止血，不够严谨。最终方案应抛弃“手工猜一个 SVG slot 数”的思路，改成 Redis 中央调度器：用 TPM 预算动态计算全局可运行 SVG batch 数，用公平队列分配给不同 job，用 SLA 反馈调整优先级。

### 设计目标

- 预算可变：500 万 TPM、1500 万 TPM 或更高预算都走同一套公式。
- 公平：单任务可以吃满 7 路；5 任务时自动约 2 路；50 任务时不会变成 `50*2=100`，全局活跃 batch 仍受预算控制。
- 错峰：请求进入、SVG 阶段启动、batch 启动都可以错开，削平第一分钟峰值。
- SLA 可解释：如果生成时间变长，调度器知道是预算限制、队列堆积、还是单 batch 慢，并给出扩并发/排队/拒绝的依据。
- 质量不降级：不通过删除 cookbook、跳过校验、跳过 finalize/export 换速度。

### Redis 数据结构

```text
ppt:jobs:pending                 # job 队列，按提交时间/优先级
ppt:jobs:running                 # 当前运行 job
ppt:jobs:{job_id}:meta           # deadline、页数、剩余 batch、当前 stage、模型

ppt:svg:jobs                     # 活跃 SVG job 集合
ppt:svg:queue:{job_id}           # 每个 job 自己的 SVG batch 队列
ppt:svg:ready                    # 已到可运行时间的 job_id 集合
ppt:svg:delayed                  # ZSET，score=earliest_run_at，用于错峰
ppt:svg:running                  # 当前运行 batch lease

llm:budget:{model}:tokens        # 滑动窗口 token 记录，或秒级 bucket
llm:ewma:{stage}:{model}         # 估计每个 stage/模型的 token 速率
llm:reservation:{batch_id}       # batch 开跑前的 token 预留
```

调度器只有一个逻辑职责：从 Redis 队列中挑选“现在可以启动”的 batch。worker 只是执行者，不能自己随意开 batch。

### TPM 到并发上限的计算

不再手写 `SVG_SLOTS=10/45`，而是动态算：

```text
usable_tpm = tpm_budget * target_utilization
worker_tpm = EWMA(svg_batch_tpm_per_active_worker)
global_svg_concurrency = floor(usable_tpm / worker_tpm)
```

建议初始参数：

```text
target_utilization = 0.70 ~ 0.80
min_svg_concurrency = 1
single_job_cap = 7
hard_max_svg_concurrency = 由机器 CPU/内存/qwen 子进程上限决定
```

`worker_tpm` 不是常量。它来自最近 N 个 SVG batch 的实际观测：

```text
batch_tpm = actual_prompt_tokens / batch_elapsed_minutes
worker_tpm = EWMA(batch_tpm)
```

如果只能在 qwen CLI turn 结束后拿到 usage，也可以先做“batch 级预估”：

```text
estimated_batch_tokens = EWMA(prompt_tokens_per_svg_batch)
estimated_batch_minutes = EWMA(elapsed_minutes_per_svg_batch)
worker_tpm = estimated_batch_tokens / estimated_batch_minutes
```

每次 batch 开跑前向 Redis token bucket 预留：

```text
reserve_tokens = estimated_batch_tokens * safety_factor
safety_factor = 1.2 ~ 1.5
```

batch 完成后用实际 usage 修正 EWMA，并退还或补记差额。

### 预算示例

用公式说明，而不是固定写死：

```text
global_svg_concurrency = floor(tpm_budget * target_utilization / worker_tpm)
```

假设最近观测到：

```text
worker_tpm = 350,000
target_utilization = 0.75
```

则：

```text
500万 TPM:  floor(5,000,000 * 0.75 / 350,000)  = 10
1500万 TPM: floor(15,000,000 * 0.75 / 350,000) = 32
```

如果压缩上下文后 `worker_tpm` 下降到 250,000：

```text
500万 TPM:  floor(5,000,000 * 0.75 / 250,000)  = 15
1500万 TPM: floor(15,000,000 * 0.75 / 250,000) = 45
```

所以“500 万时全局 10 路”只是某个观测条件下的结果；1500 万时不是拍脑袋改成 30/45，而是由实时 EWMA 算出来。

### 每个 job 的窗口怎么算

每个 job 的有效 SVG 窗口：

```text
fair_share = max(1, floor(global_svg_concurrency / active_svg_jobs))
urgent_bonus = SLA 调度器给临近 deadline 的 job 额外配额
job_window = min(single_job_cap, requested_parallel_workers, remaining_batches, fair_share + urgent_bonus)
```

示例，`global_svg_concurrency=10`、`single_job_cap=7`：

```text
1 个活跃 job:  min(7, 10/1) = 7
5 个活跃 job:  min(7, 10/5) = 2
50 个活跃 job: min(7, 10/50) => 1，但全局同时运行仍最多 10 个 batch
```

关键点：50 个任务时不是每个任务固定 1 个同步开跑，而是调度器 round-robin 地从各 job 队列取 batch，全局总量始终不超过 `global_svg_concurrency`。

### 错峰策略

错峰不应该只在 `stress_test.sh` 做。最终应在 Redis 调度器中做三层错峰：

1. 请求接入错峰：

   压测或网关层可设置 `STAGGER_SECONDS`，避免同一秒打满 API。

2. SVG 阶段错峰：

   job 从 spec 进入 SVG 时，不立刻把所有 batch 推到 ready 队列，而是写入 delayed queue：

   ```text
   earliest_run_at = now + stable_hash(job_id) % stage_stagger_window
   ```

3. batch 级错峰：

   同一 job 的 batch 进入 ready 队列时，按页组顺序增加微小间隔：

   ```text
   batch_1: now
   batch_2: now + 5s
   batch_3: now + 10s
   ...
   ```

这样第一分钟峰值会被自然削平，而不是所有 spec 完成后同时启动 SVG。

### SLA 与生成时间权衡

不能只用“降低并发”来控 TPM，因为会把单任务时间拖长。调度器需要同时看：

```text
remaining_time = deadline_at - now
remaining_batches = job 剩余 SVG batch 数
avg_batch_duration = EWMA(svg_batch_elapsed_seconds)
required_window = ceil(remaining_batches * avg_batch_duration / remaining_time)
```

然后：

- 如果 `required_window <= fair_share`：按公平配额跑。
- 如果 `required_window > fair_share` 且 TPM 预算有余量：给这个 job `urgent_bonus`。
- 如果所有 job 都需要额外配额但 TPM 不够：维持预算，返回 ETA/排队状态，不假装能满足 SLA。
- 如果 job 已经无法在 40 分钟 SLA 内完成：应尽早暴露 `at_risk` 状态，而不是最后超时。

质量边界：

- 不删 cookbook。
- 不跳过 SVG quality check。
- 不跳过 auto repair/finalize/export。
- 不用低质量模型替换 SVG 主生成，除非另做质量回归。

可调的只有：

- active SVG batch 数。
- batch 分组大小。
- job 优先级。
- 是否提前启动 PPT 与 PDF/Word 并行。
- 是否接收新 job 或返回排队 ETA。

### Job 队列/池子的价值

Redis job queue 有帮助，而且是最终应该做的形态。

当前同步 API 的问题：

- 请求一进来就占住 HTTP 连接。
- job 并发由 FastAPI semaphore 粗控。
- runner 自己开 batch，调度权分散。
- 无法精确做 admission control。

Redis queue 后：

- API 只负责创建 job，快速返回 `job_id`。
- worker 从队列取 job。
- SVG batch 由中央 scheduler 取，不由 runner 自己抢。
- 可以对外提供状态：
  - `queued`
  - `spec`
  - `svg`
  - `notes`
  - `postprocess`
  - `upload`
  - `succeeded`
  - `failed`
  - `at_risk`
- 可以根据当前队列和 TPM 预算决定是否接收新任务，或返回预计等待时间。

### 最终架构

```text
API
  -> Redis job queue
  -> Spec worker pool
  -> SVG scheduler
      -> Redis token bucket
      -> Redis fair queue by job_id
      -> SVG worker pool (qwen CLI retained)
  -> Notes worker pool
  -> Postprocess worker pool
  -> Upload/callback
```

SVG 仍然可以保留 qwen CLI，区别是：

- qwen CLI 不再自行决定何时并发启动 batch。
- qwen CLI 只执行被 scheduler 分配到的 batch。
- cookbook 保留全文，其它上下文压缩。
- usage 回写 Redis，用于下一轮动态计算并发。

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
