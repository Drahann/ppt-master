#!/usr/bin/env bash
# =========================================================
# PPT Master 并发压测脚本
# 用法:
#   bash stress_test.sh               # 默认 3 并发，短内容
#   bash stress_test.sh 5             # 5 个并发
#   bash stress_test.sh 15 http://localhost:3001 /path/to/postppt.json
#                                     # 15 并发 + 从 JSON 读长内容（30+页）
# =========================================================

set -euo pipefail

CONCURRENCY=${1:-3}
BASE_URL=${2:-"http://localhost:3001"}
CONTENT_JSON=${3:-""}
API="${BASE_URL}/api/generate-ppt"
METRICS="${BASE_URL}/metrics"
DASHBOARD="${BASE_URL}/dashboard"

# 如果提供了 JSON 模板，提取 content 字段
LONG_CONTENT=""
if [ -n "$CONTENT_JSON" ] && [ -f "$CONTENT_JSON" ]; then
    LONG_CONTENT=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1],'r',encoding='utf-8')); print(d['content'])" "$CONTENT_JSON" 2>/dev/null || echo "")
    if [ -n "$LONG_CONTENT" ]; then
        echo "📄 使用外部内容: $CONTENT_JSON"
    fi
fi

echo "╔══════════════════════════════════════════════════╗"
echo "║       PPT Master 并发压力测试                     ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  并发数:  $CONCURRENCY"
echo "║  API:     $API"
echo "║  监控台:  $DASHBOARD"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 检查服务是否在线 ──
echo "[1/3] 检查服务状态..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/healthz" || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
    echo "❌ 服务不可用 (HTTP $HTTP_CODE)，请确认容器已启动"
    exit 1
fi
echo "✅ 服务在线"
echo ""

# ── 测试内容（不同长度的 markdown，模拟真实场景） ──
CONTENTS=(
"# 人工智能教育应用

## 项目背景
人工智能技术正在深刻改变教育领域。从个性化学习到智能评估,AI正在重新定义教学方式。

## 技术方案
我们采用大语言模型驱动的自适应学习系统,根据学生的学习行为和知识掌握程度,动态调整教学内容和难度。

### 核心算法
- 知识图谱构建: 自动从教材中提取知识点及其关联关系
- 学习路径规划: 基于强化学习的个性化推荐
- 智能批改: 结合NLP的作文和简答题自动评分

## 市场分析
K12在线教育市场规模预计2025年达到5000亿元,年复合增长率18%。

## 商业模式
SaaS订阅制,按学校/机构收费,同时提供API服务给第三方平台。

## 团队介绍
核心团队来自清华大学计算机系和北师大教育学部,兼具技术深度和教育理解。"

"# 智慧物流配送系统

## 背景与痛点
最后一公里配送成本占整体物流成本的50%以上,传统模式效率低下。

## 解决方案
基于实时交通数据和订单聚合算法,实现配送路径动态优化和智能调度。

### 技术架构
- 路径优化引擎: 改进的遗传算法+模拟退火
- 实时调度系统: 基于事件驱动的微服务架构  
- 需求预测: LSTM时序预测模型

## 竞争优势
1. 算法精度领先竞品15%
2. 系统响应时间<200ms
3. 支持10万级并发订单处理

## 融资计划
首轮融资1000万元,用于技术研发和市场拓展。"

"# 新能源储能技术

## 行业现状
随着光伏和风电装机快速增长,储能需求爆发式增长。2024年全球储能市场规模突破200GWh。

## 技术创新
我们研发的新型固态电池,能量密度达到400Wh/kg,循环寿命超过5000次,成本较现有方案降低30%。

### 核心专利
- 固态电解质配方 (已授权)
- 正极材料制备工艺 (已授权)
- 电池管理系统算法 (申请中)

## 产品规划
- Phase 1: 户用储能 (5-20kWh)
- Phase 2: 工商业储能 (100kWh-1MWh)
- Phase 3: 电网级储能 (10MWh+)

## 团队
首席科学家为中科院院士,团队成员15人均具有电化学或材料学博士学位。"

"# 数字健康管理平台

## 项目概述
构建基于AI的慢病管理平台,通过可穿戴设备数据和生活方式分析,为用户提供个性化健康干预建议。

## 技术方案
融合多模态生理数据(心率、血氧、睡眠、运动),结合电子健康档案,构建个人健康数字孪生。

## 市场机会
- 中国慢病患者超过3亿
- 健康管理市场年增长25%
- 政策支持: 健康中国2030规划

## 盈利模式
B2B2C: 与保险公司和企业合作,提供健康管理服务。保险端降低赔付率,企业端降低员工缺勤率。

## 数据安全
严格遵循《个人信息保护法》和《数据安全法》,采用联邦学习实现数据可用不可见。"

"# 碳中和科技解决方案

## 背景
双碳目标下,企业面临巨大的碳排放管理压力。现有碳核算方法复杂且成本高。

## 产品
一站式碳管理SaaS平台: 碳盘查 → 碳核算 → 碳交易 → 碳中和全链路数字化。

### 功能模块
1. 自动化碳盘查: 对接企业ERP/MES系统
2. 智能碳核算: 覆盖Scope 1/2/3全范围
3. 减排路径规划: AI优化能源结构
4. 碳资产管理: 配额交易与CCER开发

## 客户
已签约30家上市公司,ARR突破2000万元。

## 竞争壁垒
- 行业know-how: 团队来自生态环境部核算中心
- 数据优势: 接入全国碳排放因子数据库
- 先发优势: 国内首批获得碳核算资质的科技公司"
)

# ── 发起并发请求 ──
echo "[2/3] 发起 $CONCURRENCY 个并发请求..."
echo ""

PIDS=()
LOG_DIR="/tmp/ppt_stress_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"

for i in $(seq 1 "$CONCURRENCY"); do
    REPORT_ID="stress_test_$(date +%s)_$i"
    
    # 构造 JSON payload
    if [ -n "$LONG_CONTENT" ]; then
        # 使用外部长内容（30+页）
        PAYLOAD=$(python3 -c "
import json,sys
content = open(sys.argv[1],'r',encoding='utf-8').read()
d = json.loads(content)
d['report_id'] = sys.argv[2]
d['title'] = '压测任务 ' + sys.argv[3]
print(json.dumps(d, ensure_ascii=False))
" "$CONTENT_JSON" "$REPORT_ID" "$i")
    else
        # 使用内嵌短内容
        CONTENT_IDX=$(( (i - 1) % ${#CONTENTS[@]} ))
        PAYLOAD=$(cat <<ENDJSON
{
    "report_id": "$REPORT_ID",
    "title": "压测任务 $i",
    "content": $(echo "${CONTENTS[$CONTENT_IDX]}" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")
}
ENDJSON
)
    fi
    
    LOG_FILE="$LOG_DIR/task_${i}.log"
    
    # 后台发起请求
    (
        echo "[Task $i] 开始 @ $(date '+%H:%M:%S')" | tee "$LOG_FILE"
        echo "[Task $i] report_id: $REPORT_ID" | tee -a "$LOG_FILE"
        
        START_TS=$(date +%s)
        
        HTTP_RESPONSE=$(curl -s -w "\n%{http_code}\n%{time_total}" \
            -X POST "$API" \
            -H "Content-Type: application/json" \
            -d "$PAYLOAD" \
            2>&1)
        
        END_TS=$(date +%s)
        ELAPSED=$((END_TS - START_TS))
        
        # 解析响应
        BODY=$(echo "$HTTP_RESPONSE" | head -n -2)
        HTTP_CODE=$(echo "$HTTP_RESPONSE" | tail -2 | head -1)
        
        if [ "$HTTP_CODE" = "200" ]; then
            SLIDES=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('slideCount','?'))" 2>/dev/null || echo "?")
            echo "[Task $i] ✅ 成功 | ${ELAPSED}s | ${SLIDES}页 | HTTP $HTTP_CODE" | tee -a "$LOG_FILE"
        else
            echo "[Task $i] ❌ 失败 | ${ELAPSED}s | HTTP $HTTP_CODE" | tee -a "$LOG_FILE"
            echo "$BODY" >> "$LOG_FILE"
        fi
    ) &
    
    PIDS+=($!)
    echo "  → Task $i 已启动 (PID: ${PIDS[-1]}, report_id: $REPORT_ID)"
done

echo ""
echo "所有任务已启动！日志目录: $LOG_DIR"
echo ""
echo "═══════════════════════════════════════════════════"
echo "📊 实时监控: $DASHBOARD"
echo "📡 JSON API:  $METRICS"
echo "═══════════════════════════════════════════════════"
echo ""

# ── 轮询等待 + 打印状态 ──
echo "[3/3] 等待所有任务完成..."
echo ""

while true; do
    RUNNING=0
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            RUNNING=$((RUNNING + 1))
        fi
    done
    
    if [ "$RUNNING" -eq 0 ]; then
        break
    fi
    
    # 打印 metrics 摘要
    METRICS_JSON=$(curl -s "$METRICS" 2>/dev/null || echo "{}")
    ACTIVE=$(echo "$METRICS_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('jobs',{}).get('active_count','?'))" 2>/dev/null || echo "?")
    CPU=$(echo "$METRICS_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('system',{}).get('cpu_percent','?'))" 2>/dev/null || echo "?")
    MEM=$(echo "$METRICS_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); s=d.get('system',{}); m=s.get('mem_rss_mb',0); print(f'{m/1024:.1f}GB' if m>=1024 else f'{m}MB')" 2>/dev/null || echo "?")
    CHILDREN=$(echo "$METRICS_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('system',{}).get('child_processes','?'))" 2>/dev/null || echo "?")
    SYS_MEM=$(echo "$METRICS_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('system',{}).get('mem_percent','?'))" 2>/dev/null || echo "?")
    
    echo "  $(date '+%H:%M:%S') | 活跃: $ACTIVE | CPU: ${CPU}% | 进程树: ${MEM} (${CHILDREN}子进程) | 系统内存: ${SYS_MEM}% | 等待中: $RUNNING"
    
    sleep 30
done

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║              压测完成                             ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 汇总结果 ──
echo "结果汇总:"
echo "────────────────────────────────────────────────────"
for f in "$LOG_DIR"/task_*.log; do
    tail -1 "$f"
done
echo "────────────────────────────────────────────────────"
echo "详细日志: $LOG_DIR/"
