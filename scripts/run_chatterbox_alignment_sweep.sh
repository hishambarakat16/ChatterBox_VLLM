#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="${LOG_DIR:-$ROOT_DIR/logs}"
RUN_NAME="${RUN_NAME:-alignment_sweep_$TIMESTAMP}"
LOG_FILE="${LOG_DIR}/${RUN_NAME}.log"
WAV_DIR="${WAV_DIR:-$ROOT_DIR/benchmark_wavs/${RUN_NAME}}"

DEVICE="${DEVICE:-cuda}"
LANGUAGE_ID="${LANGUAGE_ID:-ar}"
TEXT="${TEXT:-مرحبا، هذا اختبار للبنية الحالية.}"
PROMPT_AUDIO="${PROMPT_AUDIO:-$ROOT_DIR/SPK_17_000003.wav}"
CONCURRENCY_LEVELS="${CONCURRENCY_LEVELS:-1 2}"
PYTHON_BIN="${PYTHON_BIN:-python}"
TRACE_SHAPES="${TRACE_SHAPES:-0}"
TRACE_STEP_SHAPES="${TRACE_STEP_SHAPES:-0}"

mkdir -p "$LOG_DIR" "$WAV_DIR"

if [[ ! -f "$PROMPT_AUDIO" ]]; then
  echo "Missing PROMPT_AUDIO: $PROMPT_AUDIO" >&2
  exit 1
fi

COMMON_ARGS=(
  external/chatterbox/benchmark_multilingual_concurrency.py
  --impl scheduled
  --device "$DEVICE"
  --language-id "$LANGUAGE_ID"
  --audio-prompt-path "$PROMPT_AUDIO"
  --text "$TEXT"
  --output-dir "$WAV_DIR"
)

for level in $CONCURRENCY_LEVELS; do
  COMMON_ARGS+=(--concurrency-levels "$level")
done

if [[ "$TRACE_SHAPES" == "1" ]]; then
  COMMON_ARGS+=(--trace-shapes)
fi

if [[ "$TRACE_STEP_SHAPES" == "1" ]]; then
  COMMON_ARGS+=(--trace-step-shapes)
fi

run_case() {
  local label="$1"
  shift

  {
    echo
    echo "============================================================"
    echo "CASE: $label"
    echo "TIME: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "PWD: $ROOT_DIR"
    echo "WAV_DIR: $WAV_DIR"
    echo "COMMAND: PYTHONPATH=external/chatterbox/src $PYTHON_BIN ${COMMON_ARGS[*]} $*"
    echo "============================================================"
  } | tee -a "$LOG_FILE"

  PYTHONPATH=external/chatterbox/src "$PYTHON_BIN" "${COMMON_ARGS[@]}" "$@" 2>&1 | tee -a "$LOG_FILE"
}

{
  echo "RUN_NAME=$RUN_NAME"
  echo "LOG_FILE=$LOG_FILE"
  echo "WAV_DIR=$WAV_DIR"
  echo "DEVICE=$DEVICE"
  echo "LANGUAGE_ID=$LANGUAGE_ID"
  echo "CONCURRENCY_LEVELS=$CONCURRENCY_LEVELS"
  echo "TRACE_SHAPES=$TRACE_SHAPES"
  echo "TRACE_STEP_SHAPES=$TRACE_STEP_SHAPES"
  echo "TEXT=$TEXT"
  echo "PROMPT_AUDIO=$PROMPT_AUDIO"
} | tee "$LOG_FILE"

run_case "baseline_guard" \
  --scheduled-alignment on \
  --scheduled-inspect-every 1 \
  --scheduled-alignment-head-count 3

run_case "one_head" \
  --scheduled-alignment on \
  --scheduled-inspect-every 1 \
  --scheduled-alignment-head-count 1

run_case "two_heads" \
  --scheduled-alignment on \
  --scheduled-inspect-every 1 \
  --scheduled-alignment-head-count 2

run_case "alignment_off" \
  --scheduled-alignment off

run_case "block_eos_off" \
  --scheduled-alignment on \
  --scheduled-inspect-every 1 \
  --scheduled-alignment-head-count 3 \
  --scheduled-alignment-block-eos off

run_case "force_long_tail_off" \
  --scheduled-alignment on \
  --scheduled-inspect-every 1 \
  --scheduled-alignment-head-count 3 \
  --scheduled-alignment-force-long-tail off

run_case "force_alignment_repetition_off" \
  --scheduled-alignment on \
  --scheduled-inspect-every 1 \
  --scheduled-alignment-head-count 3 \
  --scheduled-alignment-force-alignment-repetition off

run_case "force_token_repetition_off" \
  --scheduled-alignment on \
  --scheduled-inspect-every 1 \
  --scheduled-alignment-head-count 3 \
  --scheduled-alignment-force-token-repetition off

echo
echo "Finished."
echo "Log: $LOG_FILE"
echo "WAVs: $WAV_DIR"
