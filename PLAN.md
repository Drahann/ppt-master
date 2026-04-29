# PPT Master API Automation v1 Plan

## Summary
把现有交互式 PPT Master 改造成同步 API：接收 Markdown，按每个 `##` 二级标题生成一页，不使用任何页面模板，用 DeepSeek V4 Pro 生成 `design_spec.md` / `spec_lock.md` / `notes/total.md`，用 Claude Code CLI 逐页生成 SVG，最后复用现有后处理脚本导出 PPTX。v1 不做质量失败重试，只生成质量报告并继续导出。

## Key Interfaces
- 新增入口：`python skills/ppt-master/scripts/api_ppt.py serve --host 127.0.0.1 --port 8765`。
- 本地调试：`python skills/ppt-master/scripts/api_ppt.py generate input.md --project-name demo`。
- API endpoint：`POST /api/v1/presentations`。
- Request JSON:
  ```json
  {
    "markdown": "# 标题\n\n## 第一页\n内容",
    "project_name": "demo",
    "format": "ppt169",
    "style": "general",
    "deepseek_api_key": "optional; env fallback",
    "quality_check": true
  }
  ```
- Response JSON:
  ```json
  {
    "ok": true,
    "project_path": "projects/demo_ppt169_YYYYMMDD_HHMMSS",
    "pptx_path": "projects/.../exports/name_timestamp.pptx",
    "svg_pptx_path": "projects/.../exports/name_timestamp_svg.pptx",
    "quality_report_path": "projects/.../svg_quality_report.txt",
    "quality": {"errors": 0, "warnings": 0},
    "slides": 3
  }
  ```
- Markdown 规则固定：第一个 `#` 是整套 PPT 标题；每个 `##` 是一页；`##` 到下一个 `##` 之间的内容是该页素材；没有 `##` 时返回校验错误。

## Implementation Changes
- 新增 API 编排层，复用现有脚本，不重写核心导出链路：
  - 创建项目目录并写入 `sources/input.md`。
  - 生成确定性的 `slide_manifest.md`，包含页码、标题、slug、SVG 文件名、原始 Markdown。
  - 明确跳过模板流程：不读取 `templates/layouts/layouts_index.json`，不复制任何 layout template 到项目 `templates/`。
  - 通过 DeepSeek Anthropic 兼容接口生成 `design_spec.md` 和 `spec_lock.md`，模型固定为 `deepseek-v4-pro`。
  - 用 Claude Code CLI 逐页生成 `svg_output/<slide>.svg`，每次只允许写当前页 SVG。
  - 通过 DeepSeek `deepseek-v4-pro` 生成 notes，再写成 `notes/total.md`。
  - 运行 `svg_quality_checker.py` 生成质量报告，但 v1 不因质量错误中断、不自动重试。
  - 顺序运行 `total_md_split.py`、`finalize_svg.py`、`svg_to_pptx.py -s final`。

- Claude Code / DeepSeek 配置：
  - 直接 API 调用模型：`deepseek-v4-pro`。
  - Claude Code 环境变量：
    - `ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`
    - `ANTHROPIC_AUTH_TOKEN=<DeepSeek key>`
    - `ANTHROPIC_MODEL=deepseek-v4-pro[1m]`
    - `ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-v4-pro[1m]`
    - `ANTHROPIC_DEFAULT_SONNET_MODEL=deepseek-v4-pro[1m]`
    - `ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-v4-flash`
    - `CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-flash`
    - `CLAUDE_CODE_EFFORT_LEVEL=max`
  - 预检 `claude --version`；若缺失或过旧，在错误信息中提示 `npm install -g @anthropic-ai/claude-code@latest`。

- 缓存优化：
  - SVG 生成 prompt 使用稳定前缀：固定规则、SVG/PPT 约束摘要、项目 `design_spec.md`、`spec_lock.md`、完整 slide manifest。
  - 当前页内容放在最后，避免破坏可复用前缀。
  - 不在可缓存前缀里放时间戳、随机路径、当前页编号、日志。
  - DeepSeek API 响应中如有 `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`，记录到项目日志。

- 文档同步：
  - 新增 `workflows/api-automation.md`。
  - 在 `SKILL.md` 增加 “API Automation Mode”：无八项确认、不使用模板、`##` 固定一页、质量检查仅报告。
  - 在 Strategist 文档说明自动模式下确认项来自默认配置/API 参数。
  - 在 Executor 文档说明 Claude Code CLI 逐页生成和缓存前缀要求。
  - 更新 scripts README，加入 API 服务、本地生成命令、DeepSeek/Claude Code 环境变量和 v1 限制。

## Test Plan
- Parser:
  - 3 个 `##` 生成 3 页。
  - 无 `##` 返回校验错误。
  - `###` 及更深标题保留在当前页内容中。
- Dry run:
  - 增加 `--dry-run`，只生成项目结构、`sources/input.md`、`slide_manifest.md`、prompts，不调用 DeepSeek 或 Claude Code。
- Live smoke:
  - 用 2 页 Markdown 跑通 API。
  - 验证 `design_spec.md`、`spec_lock.md`、`svg_output/*.svg`、`notes/total.md`、拆分 notes、`svg_final/`、导出 PPTX 都存在。
  - 验证质量报告生成，即使存在 warnings/errors 也继续导出。
- Manual verification:
  - 单独运行 `svg_quality_checker.py <project_path>`，确认 API 返回的质量摘要和脚本输出一致。

## Assumptions And Defaults
- v1 同步执行，请求会等待 PPTX 导出完成。
- 不引入 FastAPI/Flask，使用 Python 标准库 `ThreadingHTTPServer`。
- 默认 `format=ppt169`，`style=general`。
- 默认不使用模板，且 v1 不开放模板参数。
- 默认不生成 AI 图片。
- 不做 SVG 自动重试、图表坐标自动校准、质量阻断。
- DeepSeek key 可来自请求或环境变量，但不得写入被跟踪文档或项目产物。
