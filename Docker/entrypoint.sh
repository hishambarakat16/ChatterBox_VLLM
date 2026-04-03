#!/usr/bin/env bash
set -euo pipefail

cd /app

export MODEL_ROOT="${MODEL_ROOT:-/models}"
export HF_HOME="${HF_HOME:-${MODEL_ROOT}/.hf_home}"
export CHECKPOINT_DIR="${CHECKPOINT_DIR:-${BASE_CHECKPOINT_DIR:-${MODEL_ROOT}/chatterbox_base}}"
export BASE_CHECKPOINT_DIR="${BASE_CHECKPOINT_DIR:-${CHECKPOINT_DIR}}"
export TURBO_S3_CHECKPOINT_DIR="${TURBO_S3_CHECKPOINT_DIR:-${MODEL_ROOT}/chatterbox_turbo}"
export VLLM_MODEL_DIR="${VLLM_MODEL_DIR:-${MODEL_ROOT}/t3_vllm_export}"
export DEFAULT_AUDIO_PROMPT_PATH="${DEFAULT_AUDIO_PROMPT_PATH:-/app/SPK_17_000003.wav}"
export LD_LIBRARY_PATH="/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
export PYTHONPATH="/app/external/chatterbox/src${PYTHONPATH:+:${PYTHONPATH}}"
export VLLM_WORKER_MULTIPROC_METHOD="${VLLM_WORKER_MULTIPROC_METHOD:-spawn}"
export VLLM_ENABLE_PREFIX_CACHING="${VLLM_ENABLE_PREFIX_CACHING:-false}"
export VLLM_ENFORCE_EAGER="${VLLM_ENFORCE_EAGER:-false}"
export API_HOST="${API_HOST:-0.0.0.0}"
export API_PORT="${API_PORT:-8000}"

mkdir -p "${MODEL_ROOT}" "${HF_HOME}"

case "${1:-serve}" in
  serve)
    shift || true
    python /app/Docker/prepare_models.py
    exec python /app/external/chatterbox/fastapi_vllm_tts_service.py "$@"
    ;;
  prepare-models)
    shift || true
    exec python /app/Docker/prepare_models.py "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
