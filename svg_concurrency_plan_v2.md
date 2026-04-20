# PPT Master SVG 并发治理计划 v2

修订时间：2026-04-20  
适用范围：`ppt-master` API 服务、`qwen_ppt_runner.py` 自动化生成链路、`rag-agent` 触发 PPT 的业务链路。  
目标状态：替代 `svg_concurrency_plan.md` 作为下一轮实施依据；原文件保留为历史讨论记录。

---

## 0. 一句话结论

当前系统已经具备一层可用的“本机止血调度”：ramp 分组、anchor-first、文件 slot、fair-share、错峰和压测参数化都已在代码中出现。但它还不是严格意义上的并发治理系统，因为 API 仍是同步长请求，调度权仍分散在每个 runner 内，文件 slot 只能限制本机活跃 turn，不能表达 TPM 预算、排队 ETA、SLA 风险或跨实例公平性。

新的方向应分两步走：

1. 近期用现有机制稳定 15 个运行中任务，并让 25 个请求可被系统接收、排队、观测、完成。
2. 中期把 SVG batch 启动权从 runner 内部迁移到 Redis 中央预算调度器，由 token 预算、fair queue、deadline 和 EWMA 实测共同决定什么时候开 batch。

不要再把 `parallelBatchWorkers` 当作“越大越快”的旋钮。它只能是单 job 的请求上限，真正并发上限必须来自全局调度。

---

## 1. 当前事实复核

### 1.1 已经落地的基线能力

| 能力 | 当前证据 | 判断 |
|---|---|---|
| API 级任务并发粗控 | `api_service/app.py:26` 创建 `asyncio.Semaphore(settings.max_concurrent_jobs)`；`app.py:93-107` 在两个入口中持有 semaphore 执行 `_process_request` | 可限制同时运行 job，但仍是同步长请求 |
| 默认配置已收敛 | `api_service/config.py:59-85` 默认 `batch_mode=parallel`、`parallel_batch_workers=3`、`batch_partition=ramp_2_3_4_5_6_7_8`、`llm_svg_slots=10` | 比旧的 7 路/45 slot 更保守 |
| 请求模型已支持并发参数 | `api_service/models.py:16-19`、`models.py:37-40` 支持 `batchMode`、`batchSize`、`parallelBatchWorkers`、`batchPartition` | 前端或压测脚本可逐次覆盖 |
| API runner 已透传参数 | `api_service/runner.py:68-95` 将 batch 与模型参数写入 `runner_request.json` | API 层与 runner 层参数链路已通 |
| ramp 分组已实现 | `qwen_ppt_runner.py:2364-2388` 支持 `2+3+4+5+6+7+8`，尾部 1 页并入前组 | 旧计划里的分组策略已不是待办 |
| SVG 文件 slot 已实现 | `qwen_ppt_runner.py:687-703` 读取 slot 目录与上限；`852-912` 用 `O_EXCL` 抢占并释放 slot | 能限制本机同阶段 qwen/direct turn 数 |
| fair-share 已实现 | `qwen_ppt_runner.py:755-803` 注册活跃 SVG job 并按 `svg_slots / active_jobs` 计算有效 worker | 已有保守公平窗口，但只在启动时计算 |
| anchor-first 已实现一版 | `qwen_ppt_runner.py:3942-4016` 默认先跑第一个 batch，再启动后续 batch | 能减少完全无锚点并行，但锚点上下文仍需增强 |
| SVG 阶段和 batch 错峰已实现 | `qwen_ppt_runner.py:3885-3896` 阶段错峰；`4018-4026` batch 提交错峰 | 可削平瞬时启动峰值 |
| SVG executor 上下文已压缩 | `qwen_ppt_runner.py:458-521` 写 `executor_skill_pack.md`，保留 cookbook 全文、压缩通用上下文 | 能降低重复静态 prompt 成本 |
| usage 汇总已存在 | `qwen_ppt_runner.py:1006-1102` 聚合 `usage_summary.json`；`1105-1132` 输出总量日志 | 有数据基础，但尚未反馈给调度器 |
| postprocess 有 slot | `qwen_ppt_runner.py:4442-4467` 对 `total_md_split.py`、`finalize_svg.py`、`svg_to_pptx.py` 串行后处理加 slot | 后处理不会无限并发 |
| 压测脚本参数化 | `stress_test.sh:17-23` 支持 batch、worker、模型、错峰；`109-114` 写入 payload | 首轮压测可以快速切配置 |
| rag-agent PPT 超时已调大 | `rag-agent/rag-agent/config.py:83` 默认为 2700 秒 | 缓解 15 分钟超时，但没有解决同步阻塞 |

### 1.2 旧计划需要修正的点

1. “实现 adaptive batch partition”不再是待办，当前代码已有 ramp 分组。
2. “实现 anchor-first parallel”也已有初版，但它现在主要通过 `prev_last_svg_path` 把第一个 batch 的最后一页路径传给后续 batch；尚未把 anchor 实际产物摘要回写进 `svg_anchor_context.json`。
3. “加全局 LLM slot”已有文件 slot 版本；它是临时止血层，不等于最终预算调度器。
4. “25 并发”必须拆成两个概念：25 个请求被接收，与 25 个 runner 同时执行。当前同步 API 把这两个概念绑在一起，容易误判压测结果。
5. “1500 万 TPM 下跑 50 并发”不能直接由 slot 数推导。必须先用实测 EWMA 算单 batch token 速率，再做 admission control。

---

## 2. 并发问题的真实模型

### 2.1 当前链路

```text
rag-agent
  -> engine.run(...) 得到 final_planbook
  -> PDF 生成 + 上传
  -> Word 生成 + 上传
  -> requests.post(/api/generate-ppt) 等 PPT 完成

ppt-master API
  -> FastAPI endpoint
  -> job_semaphore
  -> asyncio.to_thread(_process_request)
  -> subprocess.run(qwen_ppt_runner.py)
  -> spec
  -> SVG batches
  -> notes
  -> quality check / repair
  -> finalize / export
  -> upload zip
  -> callback
```

证据：`rag-agent/rag-agent/server_v2.py:321-356` 在 `final_planbook` 后串行做 PDF、Word，再调用 `send_plant_PPT`；`server_v2.py:566-582` 同步请求 PPT API。PPT API 侧在 `api_service/app.py:120-161` 内同步完成 runner、zip、COS 上传和回调。

### 2.2 并发放大的公式

在没有全局调度时，SVG 高峰近似为：

```text
active_svg_sessions = running_jobs * per_job_parallel_svg_batches
```

35 页上限下，ramp 分组最多 7 个 batch：

```text
25 jobs * 7 batches = 175 active SVG sessions
```

现有文件 slot 会把真正活跃的 qwen/direct turn 卡住，但 runner 线程、子进程、等待队列、HTTP 连接、日志文件、临时目录和后续修复回合仍会被大量创建。因此仅有 slot 不能替代 job queue。

### 2.3 四个必须拆开的并发平面

| 平面 | 负责什么 | 当前状态 | 目标状态 |
|---|---|---|---|
| Admission | 是否接收新请求、返回同步结果还是 job_id | 同步请求 + semaphore | API 快速返回 job_id，支持 ETA 与拒绝 |
| Job execution | 同时有多少 runner 在跑 | `PPT_API_MAX_CONCURRENT_JOBS` 粗控 | worker pool 按阶段容量取 job |
| SVG scheduling | 哪些 batch 现在能启动 | 每个 runner 自己计算窗口 | 中央预算调度器统一发放 batch lease |
| Callback aggregation | 什么时候通知业务方 | PPT 服务生成完就回调 | rag-agent 聚合 PDF/Word/PPT 后最终一次回调 |

只调 `parallelBatchWorkers` 只影响第三层的一小部分，而且还是 runner 局部决策。

---

## 3. 当前实现的主要风险

### R1. 同步 API 把“接收请求”和“执行任务”绑死

`api_service/app.py:93-107` 在请求生命周期内持有 semaphore，`api_service/runner.py:98-105` 又同步等待 runner 子进程。这样 25 个 HTTP 请求不是进入一个可观测队列，而是占住连接等待生成。

风险：

- 上游客户端超时仍可能发生，即使 `PPT_REQUEST_TIMEOUT_SECONDS` 已调到 2700。
- 无法返回排队位置、ETA、at_risk 状态。
- 服务重启后难以恢复未完成任务。
- 25 并发压测会混合测到“HTTP 等待能力”和“PPT 生成能力”，指标不干净。

### R2. 文件 slot 是本机限流，不是预算调度

`qwen_ppt_runner.py:852-912` 用 slot 文件限制同阶段 active turn 数。它的价值是低成本、可立即使用；边界也很明确：

- 只适合单机或可靠共享文件系统，不适合多 API 实例严格调度。
- stale 清理由 PID 和时间判断，容器/跨宿主机下可靠性有限。
- 它限制的是“同时发起的 turn”，不是“每分钟 token 预算”。
- 它不知道 deadline、queue age、job priority、历史 token 速率。

### R3. fair-share 是启动时快照，不是动态调度

`effective_svg_worker_count` 在进入并行 SVG 时计算一次 `active_svg_jobs`，之后该 job 的 `ThreadPoolExecutor(max_workers=...)` 固定。后续活跃 job 增减不会重新分配窗口。

这会带来两个方向的问题：

- 早进入的 job 可能在低活跃期拿到较大窗口，后进入的 job 只能排队等 slot。
- 如果大量 job 被阶段错峰 sleep，它们已经注册为 active SVG job，会压低其他 job 的 fair-share，但实际上还没有消耗 SVG slot。

这个策略保守，但不是最优。

### R4. anchor-first 的“产物锚点”还不够实

当前 anchor-first 会先执行 batch 1，再并行后续 batch。后续 prompt 可以拿到 `anchor_svg_path`，但 `svg_anchor_context.json` 在 SVG 之前由 `build_svg_anchor_context` 写出，内容主要来自 plan/spec/style，而不是 anchor 产物。

风险：

- 后续 batch 看到的是“路径提示”，不是稳定、结构化的实际视觉摘要。
- 如果 batch 1 产物里有具体 header/footer、卡片、图标节奏，调度器不会自动提炼进 anchor context。
- 质量回归时难以判断是 anchor 弱，还是并发窗口过大。

### R5. usage 数据没有进入控制回路

`usage_summary.json` 已聚合 per-stage usage，但当前只用于日志。调度仍依赖静态 slot 和 fair-share，无法回答：

- 当前 `worker_tpm` 是多少。
- `PPT_API_LLM_SVG_SLOTS=10` 对 500 万或 1500 万 TPM 是否过保守。
- 某个 job 是否因为预算限流已经无法满足 40 分钟 SLA。

### R6. rag-agent 链路串行浪费时间预算

`server_v2.py:331-356` 在 `final_planbook` 已经存在后，仍先生成/上传 PDF，再生成/上传 Word，最后才启动 PPT。旧计划对这个判断是正确的：PPT 内容只依赖 Markdown，不依赖 PDF/Word 文件本身。

但提前启动 PPT 的前提是不能让 PPT 服务提前回调最终业务方；否则回调缺 PDF/Word 链接。

---

## 4. 设计原则

1. 质量优先：不删除 cookbook，不跳过 `svg_quality_checker.py`、`svg_auto_repair.py`、`finalize_svg.py`、`svg_to_pptx.py`。
2. 调度集中：runner 负责执行 batch，不负责决定全局何时启动 batch。
3. 预算可解释：所有并发上限最终都能追溯到 TPM 预算、EWMA token 速率、机器资源上限和 SLA。
4. 请求可恢复：API 入口不应长期占住 HTTP 连接；job 状态必须可查询、可恢复、可超时处理。
5. 分阶段演进：保留当前文件 slot 作为 Phase 1 防线；Redis 调度器作为 Phase 3 目标，不在首轮引入大范围重构。
6. 观测先行：每一轮扩大并发前，必须能看到 active jobs、active slots、waiting slots、slot wait time、stage duration、usage 和质量结果。

---

## 5. 架构决策记录 ADR

### Decision

采用“两层治理”：

1. 近端保留当前本机文件 slot + fair-share + ramp + anchor-first，作为 15 运行任务和 25 接收请求的止血方案。
2. 终态新增 Redis job queue + SVG budget scheduler，把 SVG batch 变成中央队列里的可调度工作单元。

### Drivers

- 当前最大风险不是单个 PPT 慢，而是 `running_jobs * per_job_svg_batches` 的乘法失控。
- 40 分钟 SLA 同时受 rag-agent 串行等待、PPT 排队、SVG 预算和 postprocess 影响。
- 文件 slot 能快速控制本机峰值，但无法做跨实例预算、ETA 和 deadline 反馈。
- 质量链路已经比较完整，不能为了吞吐牺牲后处理和校验。

### Alternatives Considered

| 方案 | 结论 | 原因 |
|---|---|---|
| 继续只调 `parallelBatchWorkers` | 否决 | 无法控制全局乘法，也无法表达排队和预算 |
| 只保留文件 slot，不做 Redis | 阶段性接受 | 单机可用，但跨实例、ETA、TPM 预算、SLA 都不足 |
| SVG 直接切 direct API | 暂缓 | 质量一致性和工具约束风险较高，旧计划保留 CLI 的判断仍成立 |
| 降模型/跳质检换速度 | 否决 | 会破坏 PPT 质量边界，且失败修复可能反而放大 token |
| Redis 中央预算调度器 | 采纳为终态 | 能统一 admission、fairness、budget、deadline 和观测 |

### Consequences

- Phase 1 可以小步落地，不必立即引入 Redis。
- Phase 2 需要改 API 语义：同步结果不再是唯一模式。
- Phase 3 需要把 runner 内部 SVG 并行执行改造成“可执行单 batch”的 worker 接口。
- 压测指标必须从“请求是否返回”升级为“job 状态流、阶段耗时、预算使用、质量结果”。

---

## 6. 目标分层

### 6.1 近期目标：15 个运行中任务稳定

配置基线：

```env
PPT_API_MAX_CONCURRENT_JOBS=15
PPT_API_BATCH_MODE=parallel
PPT_API_BATCH_PARTITION=ramp_2_3_4_5_6_7_8
PPT_API_PARALLEL_BATCH_WORKERS=3
PPT_API_LLM_SVG_SLOTS=10
PPT_API_SVG_FAIR_SHARE=1
PPT_API_SVG_FAIR_SHARE_DELAY_SECONDS=8
PPT_API_SVG_STAGE_STAGGER_SECONDS=60
PPT_API_SVG_BATCH_STAGGER_SECONDS=5
```

解释：

- `parallelBatchWorkers=3` 是单 job 请求上限。
- `PPT_API_LLM_SVG_SLOTS=10` 是全局活跃 SVG turn 上限。
- 当 15 个 job 都活跃时，fair-share 会把每个 job 有效窗口压到 1，文件 slot 再把真正活跃 SVG turn 卡在 10 左右。
- 这不是最高吞吐配置，而是验证质量和稳定性的起点。

### 6.2 下一目标：25 个请求可接收、可排队、可完成

目标口径必须改为：

```text
25 accepted requests != 25 running runners
```

在没有 async job queue 前，不建议把 `PPT_API_MAX_CONCURRENT_JOBS` 直接拉到 25 作为正式目标。可以短时压测，但不能把它当生产配置。

正确目标：

- API 能接收 25 个请求并返回 `job_id`。
- 同时运行 runner 数仍按资源控制在 10-15。
- SVG active turn 仍受预算控制。
- 上游不因 HTTP 长连接超时丢任务。

---

## 7. 分阶段实施计划

### Phase 0：冻结基线与观测口径

目的：先确认当前未提交实现的真实行为，避免边改边压测。

工作项：

1. 固化当前默认值：
   - `api_service/config.py:59-85`
   - `qwen_ppt_runner.py:95-109`
   - `stress_test.sh:17-23`
2. 新增一份压测 runbook，明确每轮必须记录：
   - API active jobs / completed / failed。
   - active/waiting slot 数。
   - qwen 子进程峰值。
   - per-stage duration。
   - `usage_summary.json` stage totals。
   - SVG quality report。
   - PPTX 可打开性与页数一致性。
3. 对现有 `/metrics` 增强观测字段：
   - slot active count。
   - slot waiting count。
   - slot wait p50/p90/p99。
   - stage duration p50/p90。
   - recent failures by stage。

验收：

- 运行 3 并发 baseline，能复现旧数据口径。
- 每个 job 的 runner 目录里有 `usage_summary.json`、质量报告、stage session 信息。
- `/metrics` 可以看到 job、系统资源和 slot 状态。

### Phase 1：把当前止血层做扎实

目的：在不引入新依赖的前提下，让 15 running jobs 稳定，并为 25 accepted jobs 做准备。

工作项：

1. 增强 anchor-first：
   - batch 1 完成后读取其 SVG 文件。
   - 生成 `anchor_output_summary`：
     - `anchor_svg_paths`
     - `header_footer_rules`
     - `color_roles`
     - `card_patterns`
     - `icon_density_examples`
     - `layout_do_not_repeat`
   - 回写 `svg_anchor_context.json` 后再创建后续 batch prompt。
2. 将 fair-share 计算从“只在启动时一次”改为“提交 batch 前再确认”：
   - 当前 `ThreadPoolExecutor` 的 worker 数仍可保留。
   - 每个 batch 开始前必须重新读取 active jobs / slot 状态。
   - 如果当前 job 超出 fair-share，则延迟提交，而不是让线程长时间占住。
3. 给请求参数加硬上限：
   - `parallelBatchWorkers <= 7`。
   - fixed `batchSize <= 8`，避免单 turn 输出过长。
   - `batchPartition` 默认保持 ramp。
4. slot 观测增强：
   - 记录等待开始时间、获得 slot 时间、释放时间。
   - waiting slot 不仅写日志，也写 metrics snapshot。
5. 压测脚本输出完整元数据：
   - 写入本轮 env 配置。
   - 拉取 `/metrics` 快照。
   - 汇总每个 task 的 HTTP 状态、耗时、错误。

验收：

- 10 并发窗口 3：所有 job 进入 terminal 状态；SVG 质量报告无系统性新增错误。
- 15 并发窗口 3：`PPT_API_LLM_SVG_SLOTS=10` 下 active SVG turn 不超过 10。
- 每轮至少抽检 3 套 PPT：封面、第一页内容、中部页、尾页无明显跨 batch 风格漂移。

### Phase 2：改造 API 为异步 job 模式

目的：把“请求接收”和“任务执行”拆开。

新增 API 语义：

```text
POST /api/generate-ppt
  responseMode: "sync" | "async"
  callbackMode: "auto" | "defer" | "none"

GET /api/jobs/{job_id}
GET /api/jobs/{job_id}/artifacts
POST /api/jobs/{job_id}/cancel
```

状态模型：

```text
accepted
queued
running:spec
running:svg
running:notes
running:postprocess
uploading
succeeded
failed
cancelled
at_risk
```

工作项：

1. API 创建 job 后立即写入 job metadata。
2. 同步模式只作为兼容路径；生产链路使用 async。
3. worker pool 从本地队列取 job，`PPT_API_MAX_CONCURRENT_JOBS` 表示 runner pool 大小，不再表示 HTTP 同时连接数。
4. `notify_report_server` 只在 callbackMode 为 `auto` 时执行。
5. rag-agent 改成：
   - `final_planbook` 完成后立即 async 提交 PPT。
   - PDF、Word、PPT 三路并行。
   - 三个结果齐备后由 rag-agent 做最终聚合回调。

rag-agent 目标链路：

```text
final_planbook ready
  -> start PPT async job
  -> start PDF generation/upload
  -> start Word generation/upload
  -> poll or receive PPT result
  -> aggregate fileUrl + wordUrl + pptUrl
  -> final callback exactly once
```

验收：

- 25 个请求能在短时间内得到 `job_id`，不依赖 25 个长 HTTP 连接。
- PPT 服务提前完成时不会单独回调业务方导致缺少 PDF/Word。
- rag-agent 最终回调只发生一次，且包含 `fileUrl`、`wordUrl`、`pptUrl`。

### Phase 3：Redis SVG 预算调度器

目的：用中央调度替代 runner 局部并行决策。

核心数据结构：

```text
ppt:jobs:pending
ppt:jobs:running
ppt:jobs:{job_id}:meta

ppt:svg:jobs
ppt:svg:queue:{job_id}
ppt:svg:ready
ppt:svg:delayed
ppt:svg:running
ppt:svg:dead

llm:budget:{model}:tokens
llm:ewma:{stage}:{model}
llm:reservation:{batch_id}
```

调度公式：

```text
usable_tpm = tpm_budget * target_utilization
worker_tpm = EWMA(svg_batch_tokens / svg_batch_elapsed_minutes)
global_svg_concurrency = floor(usable_tpm / worker_tpm)
```

job 窗口：

```text
fair_share = max(1, floor(global_svg_concurrency / active_svg_jobs))
required_window = ceil(remaining_batches * avg_batch_duration / remaining_time)
urgent_bonus = max(0, required_window - fair_share) if budget_available else 0
job_window = min(single_job_cap, requested_parallel_workers, remaining_batches, fair_share + urgent_bonus)
```

worker 行为：

1. runner/spec 阶段产出 slide plan、design spec、batch descriptors。
2. runner 不直接开 SVG batch，而是把 batch 入队。
3. SVG scheduler 按 budget/fairness/deadline 选 batch。
4. SVG worker 执行单个 batch。
5. worker 写回 usage、耗时、质量结果。
6. scheduler 更新 EWMA、释放 reservation、继续调度。

验收：

- 同一时刻 active SVG batch 不超过 `global_svg_concurrency`。
- 50 个 active job 时不会出现 `50 * 1` 同时开跑；仍由全局 concurrency 决定总量。
- job 的 ETA 与 `at_risk` 可解释：能说明是预算不足、queue backlog、单 batch 慢还是失败重试导致。

### Phase 4：Admission control 与 SLA 治理

目的：系统在负载过高时给出明确承诺，而不是默默堆积到超时。

Admission 输入：

- 当前 pending jobs。
- 当前 running jobs。
- 当前 SVG queue。
- 近 N 个 job 的阶段耗时 EWMA。
- 近 N 个 SVG batch 的 token/elapsed EWMA。
- 目标 SLA：40 分钟。
- TPM 预算：例如 500 万、1500 万。

输出：

```text
accept: true/false
mode: run_now | queued | reject
estimated_start_at
estimated_finish_at
risk: normal | at_risk | impossible
reason
```

验收：

- 预算不足时返回 queue ETA 或 reject，不假装能满足 SLA。
- job 已经无法满足 40 分钟时尽早标记 `at_risk`。
- 扩大 `PPT_API_MAX_CONCURRENT_JOBS` 前必须先看到 admission control 的容量证明。

---

## 8. 压测矩阵

### 8.1 当前止血层矩阵

| 轮次 | 目标 | 请求数 | 同时运行 job | 请求窗口 | SVG slot | 分组 | 通过标准 |
|---|---|---:|---:|---:|---:|---|---|
| B0 | 复现基线 | 3 | 3 | 7 | 10 | fixed 或 ramp | 对齐历史 TPM 与耗时 |
| B1 | 分组质量 | 10 | 10 | 3 | 10 | ramp | 质量无明显漂移 |
| B2 | 15 running | 15 | 15 | 3 | 10 | ramp | active SVG turn <= 10 |
| B3 | 15 保守 | 15 | 15 | 2 | 10 | ramp | 完成率和质量优于 B2 |
| B4 | 25 同步短测 | 25 | 15 或 25 | 2 | 10 | ramp | 只作为风险测量，不作为生产承诺 |

### 8.2 async queue 后矩阵

| 轮次 | 目标 | accepted requests | runner pool | SVG budget | 通过标准 |
|---|---|---:|---:|---:|---|
| Q1 | 25 accepted | 25 | 10 | 10 slots | 全部有 job_id，无 HTTP 超时 |
| Q2 | 25 completed | 25 | 15 | 10 slots | 全部 terminal，成功率达标 |
| Q3 | SLA 观察 | 25 | 动态 | 10-15 slots | ETA 与实际完成误差可解释 |
| Q4 | 50 accepted | 50 | 15 | budget scheduler | 不要求全部 40 分钟内完成，但必须可排队和给 ETA |

### 8.3 每轮必须记录

- 成功率、失败 stage、失败原因。
- P50/P90/P99 job elapsed。
- P50/P90/P99 stage elapsed。
- active/waiting slots 与 slot wait time。
- qwen CLI 子进程峰值。
- CPU、RSS、系统内存。
- `usage_summary.json` 的 `stage_totals`。
- 1 分钟滑动 TPM 估计。
- SVG quality errors、repair count。
- final PPTX 是否可打开、页数是否正确、notes 是否完整。
- 抽检 PPT 的跨 batch 风格一致性。

---

## 9. 质量闸门

### 9.1 不可牺牲项

- 不删 `svg_design_cookbook.md`。
- 不跳过 `svg_quality_checker.py`。
- 不跳过 `svg_auto_repair.py`。
- 不跳过 `finalize_svg.py`。
- 不绕过 `svg_to_pptx.py -s final`。
- 不用 `cp` 替代 finalize。
- 不直接从 `svg_output/` 导出。

这些边界来自 `ppt-master/AGENTS.md:45-54` 与 `AGENTS.md:98-101`，也符合当前 runner 在 `qwen_ppt_runner.py:4396-4467` 的后处理顺序。

### 9.2 可调项

- API admission 是否立即接收。
- runner pool 大小。
- SVG 全局活跃 batch 数。
- 单 job 请求窗口。
- batch 分组。
- stage/batch 错峰。
- job priority / deadline bonus。
- 是否 async 返回 job_id。
- 是否由 rag-agent 聚合最终回调。

### 9.3 质量抽检标准

每轮至少抽检 3 个 PPT，每个 PPT 看 4 类页面：

- 封面。
- 第一张内容页。
- 中部内容页。
- 尾页。

检查项：

- header/footer 位置是否一致。
- 卡片半径、阴影、边距是否漂移。
- 图标来源是否真实、是否有 emoji 代替。
- 图表和信息密度是否符合 design spec。
- 跨 batch 配色和字体层级是否一致。
- PPTX 是否能打开，native 输出是否存在。

---

## 10. 代码改造清单

### 10.1 近期小改

| 文件 | 改造 |
|---|---|
| `skills/ppt-master/scripts/qwen_ppt_runner.py` | anchor batch 完成后回写真实产物摘要到 `svg_anchor_context.json` |
| `skills/ppt-master/scripts/qwen_ppt_runner.py` | batch 提交前二次确认 fair-share，不只在 `ThreadPoolExecutor` 创建时确认 |
| `skills/ppt-master/scripts/qwen_ppt_runner.py` | 对 `parallel_batch_workers`、fixed `batch_size` 加硬上限 |
| `api_service/metrics.py` | 增加 slot waiting、wait time、stage duration |
| `api_service/app.py` | 暴露更完整 `/metrics`，区分 accepted/running/terminal |
| `stress_test.sh` | 每轮保存 env、payload、metrics 快照、汇总表 |

### 10.2 async API 改造

| 文件/模块 | 改造 |
|---|---|
| `api_service/models.py` | 新增 `responseMode`、`callbackMode`、job status response model |
| `api_service/app.py` | 新增 job create/status/cancel/artifacts endpoint |
| `api_service/runner.py` | 支持 worker 异步执行，不再只从 endpoint 同步调用 |
| `api_service/storage.py` | callbackMode 控制是否自动回调 |
| `rag-agent/rag-agent/server_v2.py` | final_planbook 后并行启动 PPT/PDF/Word，最终聚合回调 |

### 10.3 Redis 终态改造

| 模块 | 改造 |
|---|---|
| `api_service/job_store.py` | Redis job metadata、状态机、heartbeat |
| `api_service/scheduler.py` | admission control、ETA、runner pool |
| `api_service/svg_scheduler.py` | budget token bucket、fair queue、deadline bonus |
| `qwen_ppt_runner.py` | 暴露“执行单 SVG batch”的 worker 入口 |
| `qwen_ppt_runner.py` | batch 完成后回写 usage、elapsed、quality result |

---

## 11. 测试计划

### Unit

- `split_plan_into_batches`：
  - N=1、2、3、10、18、25、30、35、36。
  - 尾部 1 页并入前组。
  - fixed mode 与 ramp mode 均覆盖。
- `effective_svg_worker_count`：
  - fair-share 开/关。
  - active jobs 为 1、5、10、25、50。
  - svg slots 为 1、10、32、45。
- slot lease：
  - 正常抢占/释放。
  - stale 文件清理。
  - wait timeout。
- anchor summary：
  - anchor batch SVG 存在时生成结构化摘要。
  - anchor batch 缺失时阻断后续并行。

### Integration

- fake qwen runner：
  - 用快速 stub 代替真实 qwen，模拟 batch 成功、失败、重试、超时。
  - 验证 active SVG slot 从不超过配置。
- API async：
  - 25 个请求快速返回 job_id。
  - job 状态从 queued 到 succeeded。
  - callbackMode=none 不回调。
  - callbackMode=auto 只回调一次。
- rag-agent 聚合：
  - PDF 慢、Word 快、PPT 快。
  - PPT 慢、PDF/Word 快。
  - 任一路失败时最终状态明确。

### E2E

- 真实 qwen 小样本：
  - 3 并发 baseline。
  - 10 并发 ramp。
  - 15 并发窗口 2/3。
- 质量回归：
  - 每轮抽 3 个 PPT。
  - 保留产物、日志、usage、metrics。

---

## 12. 验收标准

### Phase 1 验收

- 15 个运行中 job 能完成。
- active SVG turn 峰值不超过 `PPT_API_LLM_SVG_SLOTS`。
- 没有明显跨 batch 风格漂移。
- `usage_summary.json` 对每个 job 可读。
- `/metrics` 能显示 job、系统资源、slot active/waiting。
- PPTX 可打开，页数与 slide plan 一致，notes 完整。

### Phase 2 验收

- 25 个请求可以快速返回 job_id。
- 上游不需要等待 PPT 完成的 HTTP 长连接。
- rag-agent 最终回调包含 PDF、Word、PPT 三类链接。
- callback exactly once。
- job 重启后能从状态表判断 succeeded/failed/queued/running。

### Phase 3 验收

- Redis scheduler 是唯一决定 SVG batch 启动的组件。
- worker 不能绕过 scheduler 自行启动 batch。
- global SVG concurrency 来自预算公式，而不是手写固定值。
- ETA/at_risk 能被 API 查询。
- 25 accepted / 15 running / budget-controlled SVG 能稳定完成。

---

## 13. 当前推荐执行顺序

1. 不再继续扩 `parallelBatchWorkers`，先确认当前 3 并发和 10 并发 ramp 的质量。
2. 跑 15 并发，配置 `parallelBatchWorkers=3`、`llm_svg_slots=10`、stage stagger=60、batch stagger=5。
3. 增强 anchor 真实产物摘要。
4. 增强 `/metrics` 和压测汇总。
5. 做 async job API，先让 25 个请求可接收、可查询、可排队。
6. 改 rag-agent 为 PPT/PDF/Word 并行 + 最终聚合回调。
7. 再启动 Redis SVG scheduler 设计与实现。
8. Redis 版本稳定后，才讨论 50 accepted jobs 或更高 TPM 预算。

---

## 14. 禁止路径

- 禁止直接用 25 并发 * 7 SVG workers 作为下一轮验证。
- 禁止把 `PPT_API_LLM_SVG_SLOTS` 从 10 直接拍到 30/45，除非有 EWMA 与机器资源证据。
- 禁止在没有 async job queue 的情况下把“25 个请求可进入系统”解释成“25 个 runner 必须同时运行”。
- 禁止为了速度跳过质量检查、修复、finalize 或 export。
- 禁止让 PPT 提前生成后直接回调最终业务方，除非 PDF/Word 链接已经齐备或 callbackMode 明确为 defer/none。

---

## 15. 新旧计划差异摘要

| 主题 | 旧计划 | v2 修正 |
|---|---|---|
| ramp 分组 | 作为待实现步骤 | 已在代码中实现，后续只需测试和加边界 |
| anchor-first | 作为待实现步骤 | 已有初版，但需真实产物摘要 |
| 全局 slot | 作为待实现步骤 | 已有文件 slot，定位为止血层 |
| 25 并发 | 偏向直接调运行参数 | 拆成 accepted requests 与 running jobs |
| Redis scheduler | 放在最终架构 | 仍是终态，但前置 async API 和观测 |
| rag-agent | 建议并行 PDF/Word/PPT | 继续保留，但明确 callbackMode 与聚合回调 |
| 验收 | 偏压测配置 | 增加状态机、ETA、质量、usage、slot wait 证据 |

---

## 16. 最小下一步

如果只做一个最小闭环，顺序应是：

1. 跑 10 并发，确认当前 ramp + anchor-first + slot 的质量。
2. 跑 15 并发，确认 `llm_svg_slots=10` 真的限制住 active SVG turn。
3. 增强 anchor context，避免 batch 风格漂移。
4. 增强 metrics，拿到 slot wait 和 stage duration。
5. 再做 async job API。

这条路径小、稳、可回滚，也不会把系统过早推向 Redis 重构。
