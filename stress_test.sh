#!/usr/bin/env bash
# =========================================================
# PPT Master 并发压测脚本
# 用法:
#   bash stress_test.sh               # 默认 3 个并发任务
#   bash stress_test.sh 5             # 5 个并发任务
#   bash stress_test.sh 3 http://1.2.3.4:3001  # 指定服务器地址
# =========================================================

set -euo pipefail

CONCURRENCY=${1:-3}
BASE_URL=${2:-"http://localhost:3001"}
API="${BASE_URL}/api/generate-ppt"
METRICS="${BASE_URL}/metrics"
DASHBOARD="${BASE_URL}/dashboard"

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

# ── 测试内容：从 postppt.json 读取真实内容 ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
POSTPPT_JSON="${3:-}"

# 自动查找 postppt.json
if [ -z "$POSTPPT_JSON" ]; then
    for candidate in \
        "$SCRIPT_DIR/postppt.json" \
        "$SCRIPT_DIR/../postppt.json" \
        "$HOME/AIPPT_CLI/ppt-master/postppt.json" \
        "$HOME/AIPPT_CLI/rag-agent/rag-agent/postppt.json"; do
        if [ -f "$candidate" ]; then
            POSTPPT_JSON="$candidate"
            break
        fi
    done
fi

if [ -z "$POSTPPT_JSON" ] || [ ! -f "$POSTPPT_JSON" ]; then
    echo "❌ 找不到 postppt.json"
    echo "   用法: bash stress_test.sh [并发数] [服务器地址] [postppt.json路径]"
    exit 1
fi

echo "📄 内容来源: $POSTPPT_JSON"
# 提取 content 字段并 JSON 编码
CONTENT_JSON=$(python3 -c "
import json, sys
with open('$POSTPPT_JSON', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(json.dumps(data.get('content', '')))
")
CONTENT_LEN=$(python3 -c "
import json
print(len(json.loads($CONTENT_JSON)))
")
echo "📝 内容长度: ${CONTENT_LEN} 字符"
echo ""

# ── 发起并发请求 ──
echo "[2/3] 发起 $CONCURRENCY 个并发请求..."
echo ""

PIDS=()
LOG_DIR="/tmp/ppt_stress_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"

for i in $(seq 1 "$CONCURRENCY"); do
    REPORT_ID="stress_test_$(date +%s)_$i"
    
    # 构造 JSON payload（每个任务用相同内容，不同 report_id）
    PAYLOAD=$(python3 -c "
import json
content = json.loads($CONTENT_JSON)
payload = {
    'report_id': '$REPORT_ID',
    'title': '压测任务 $i',
    'content': content
}
print(json.dumps(payload, ensure_ascii=False))
")
    
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
