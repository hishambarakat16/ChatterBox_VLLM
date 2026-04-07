#!/usr/bin/env bash
set -euo pipefail

cd /app

add_ld_path_front() {
  local path="$1"
  if [[ ! -d "$path" ]]; then
    return
  fi
  case ":${LD_LIBRARY_PATH:-}:" in
    *":${path}:"*) ;;
    *)
      LD_LIBRARY_PATH="${path}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
      ;;
  esac
}

check_vllm_cuda_runtime() {
  python - <<'PY'
import vllm._C  # noqa: F401
PY
}

export MODEL_ROOT="${MODEL_ROOT:-/models}"
export HF_HOME="${HF_HOME:-${MODEL_ROOT}/.hf_home}"
export CHECKPOINT_DIR="${CHECKPOINT_DIR:-${BASE_CHECKPOINT_DIR:-${MODEL_ROOT}/chatterbox_base}}"
export BASE_CHECKPOINT_DIR="${BASE_CHECKPOINT_DIR:-${CHECKPOINT_DIR}}"
export TURBO_S3_CHECKPOINT_DIR="${TURBO_S3_CHECKPOINT_DIR:-${MODEL_ROOT}/chatterbox_turbo}"
export VLLM_MODEL_DIR="${VLLM_MODEL_DIR:-${MODEL_ROOT}/t3_vllm_export}"
export DEFAULT_AUDIO_PROMPT_PATH="${DEFAULT_AUDIO_PROMPT_PATH:-/app/SPK_17_000003.wav}"
# Prefer the Conda runtime first so Python extension modules do not bind against
# older system libstdc++ / ICU copies.
add_ld_path_front "/opt/conda/lib"
# Build a robust CUDA 12 loader path for both system CUDA and pip/conda CUDA runtimes.
add_ld_path_front "/opt/conda/lib/python3.11/site-packages/torch/lib"
add_ld_path_front "/opt/conda/lib/python3.11/site-packages/nvidia/cuda_runtime/lib"
add_ld_path_front "/opt/conda/lib/python3.11/site-packages/nvidia/cu12/lib"
add_ld_path_front "/usr/local/cuda/lib64"
add_ld_path_front "/usr/local/cuda-12.8/targets/x86_64-linux/lib"
export LD_LIBRARY_PATH
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
    if ! check_vllm_cuda_runtime; then
      echo "vLLM CUDA extension import failed. Check CUDA 12 runtime paths and LD_LIBRARY_PATH." >&2
      echo "LD_LIBRARY_PATH=${LD_LIBRARY_PATH}" >&2
      exit 1
    fi
    python /app/Docker/prepare_models.py
    exec python /app/external/chatterbox/fastapi_vllm_tts_service.py "$@"
    ;;
  prepare-models)
    shift || true
    if ! check_vllm_cuda_runtime; then
      echo "vLLM CUDA extension import failed. Check CUDA 12 runtime paths and LD_LIBRARY_PATH." >&2
      echo "LD_LIBRARY_PATH=${LD_LIBRARY_PATH}" >&2
      exit 1
    fi
    exec python /app/Docker/prepare_models.py "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
