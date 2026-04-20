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
BATCH_MODE=${BATCH_MODE:-parallel}
BATCH_SIZE=${BATCH_SIZE:-5}
PARALLEL_BATCH_WORKERS=${PARALLEL_BATCH_WORKERS:-3}
BATCH_PARTITION=${BATCH_PARTITION:-ramp_2_3_4_5_6_7_8}
SPEC_MODEL=${SPEC_MODEL:-qwen3.6-plus}
NOTES_MODEL=${NOTES_MODEL:-qwen3.5-flash}
STAGGER_SECONDS=${STAGGER_SECONDS:-0}
RESPONSE_MODE=${RESPONSE_MODE:-sync}
CALLBACK_MODE=${CALLBACK_MODE:-auto}

echo "╔══════════════════════════════════════════════════╗"
echo "║       PPT Master 并发压力测试                     ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  并发数:  $CONCURRENCY"
echo "║  API:     $API"
echo "║  监控台:  $DASHBOARD"
echo "║  SVG窗口: $PARALLEL_BATCH_WORKERS | 分组: $BATCH_PARTITION"
echo "║  响应:    $RESPONSE_MODE | 回调: $CALLBACK_MODE"
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

# 预生成 payload 模板到临时文件（避免 shell 变量传递大 JSON 出错）
LOG_DIR="/tmp/ppt_stress_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"

python3 -c "
import json, sys
with open('$POSTPPT_JSON', 'r', encoding='utf-8') as f:
    data = json.load(f)
content = data.get('content', '')
print(f'📝 内容长度: {len(content)} 字符', file=sys.stderr)
# 保存为模板，report_id 和 title 用占位符
template = {
    'report_id': '__REPORT_ID__',
    'title': '__TITLE__',
    'content': content
}
with open('$LOG_DIR/_payload_template.json', 'w', encoding='utf-8') as out:
    json.dump(template, out, ensure_ascii=False)
" 2>&1 | head -1
echo ""

# ── 发起并发请求 ──
echo "[2/3] 发起 $CONCURRENCY 个并发请求..."
echo ""

PIDS=()

for i in $(seq 1 "$CONCURRENCY"); do
    REPORT_ID="stress_test_$(date +%s)_$i"
    
    # 从模板生成每个任务的 payload 文件
    PAYLOAD_FILE="$LOG_DIR/payload_${i}.json"
    python3 -c "
import json
with open('$LOG_DIR/_payload_template.json', 'r', encoding='utf-8') as f:
    payload = json.load(f)
payload['report_id'] = '$REPORT_ID'
payload['title'] = '压测任务 $i'
payload['batchMode'] = '$BATCH_MODE'
payload['batchSize'] = int('$BATCH_SIZE')
payload['parallelBatchWorkers'] = int('$PARALLEL_BATCH_WORKERS')
payload['batchPartition'] = '$BATCH_PARTITION'
payload['specModel'] = '$SPEC_MODEL'
payload['notesModel'] = '$NOTES_MODEL'
payload['responseMode'] = '$RESPONSE_MODE'
payload['callbackMode'] = '$CALLBACK_MODE'
with open('$PAYLOAD_FILE', 'w', encoding='utf-8') as out:
    json.dump(payload, out, ensure_ascii=False)
"
    
    LOG_FILE="$LOG_DIR/task_${i}.log"
    
    # 后台发起请求
    (
        echo "[Task $i] 开始 @ $(date '+%H:%M:%S')" | tee "$LOG_FILE"
        echo "[Task $i] report_id: $REPORT_ID" | tee -a "$LOG_FILE"
        
        START_TS=$(date +%s)
        
        HTTP_RESPONSE=$(curl -s -w "\n%{http_code}\n%{time_total}" \
            -X POST "$API" \
            -H "Content-Type: application/json" \
            -d @"$PAYLOAD_FILE" \
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
    if [ "$STAGGER_SECONDS" != "0" ] && [ "$i" -lt "$CONCURRENCY" ]; then
        sleep "$STAGGER_SECONDS"
    fi
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
