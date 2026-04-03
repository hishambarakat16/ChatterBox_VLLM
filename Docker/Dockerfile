# syntax=docker/dockerfile:1.7

FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04

ARG MINIFORGE_VERSION=24.11.3-0

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_TORCH_BACKEND=cu128 \
    CONDA_DIR=/opt/conda \
    PATH=/opt/conda/bin:$PATH \
    MODEL_ROOT=/models \
    HF_HOME=/models/.hf_home \
    CHECKPOINT_DIR=/models/chatterbox_base \
    BASE_CHECKPOINT_DIR=/models/chatterbox_base \
    TURBO_S3_CHECKPOINT_DIR=/models/chatterbox_turbo \
    VLLM_MODEL_DIR=/models/t3_vllm_export \
    DEFAULT_AUDIO_PROMPT_PATH=/app/SPK_17_000003.wav \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    API_DEVICE=cuda \
    API_BATCH_WINDOW_MS=5 \
    API_MAX_BATCH_SIZE=8 \
    VLLM_WORKER_MULTIPROC_METHOD=spawn \
    VLLM_ENABLE_PREFIX_CACHING=false \
    VLLM_ENFORCE_EAGER=false \
    VLLM_GPU_MEMORY_UTILIZATION=0.5 \
    VLLM_MAX_MODEL_LEN=2048 \
    VLLM_DTYPE=auto \
    VLLM_EXPORT_COPY=1 \
    AUTO_DOWNLOAD_BASE_CHECKPOINT=0 \
    AUTO_DOWNLOAD_TURBO_S3=0 \
    AUTO_EXPORT_VLLM_MODEL=0

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    ca-certificates \
    curl \
    ffmpeg \
    git \
    git-lfs \
    libsndfile1 \
    pkg-config \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Keep Python pinned to the same 3.11 family used in the working manual setup.
RUN wget -qO /tmp/miniforge.sh \
      "https://github.com/conda-forge/miniforge/releases/download/${MINIFORGE_VERSION}/Miniforge3-Linux-x86_64.sh" \
    && bash /tmp/miniforge.sh -b -p "${CONDA_DIR}" \
    && rm -f /tmp/miniforge.sh \
    && conda install -y python=3.11 pip \
    && conda clean -afy

WORKDIR /app

COPY . /app

# Install vLLM first so its torch wheel owns the environment, then install the
# Chatterbox runtime dependencies explicitly without letting editable install
# pull a second torch build.
RUN chmod +x /app/Docker/entrypoint.sh \
    && python -m pip install --upgrade pip uv \
    && uv pip install --system vllm --torch-backend=auto \
    && python -m pip install --no-cache-dir \
         "numpy>=1.24.0,<1.26.0" \
         "librosa==0.11.0" \
         "s3tokenizer" \
         "torchaudio==2.6.0" \
         "transformers==4.46.3" \
         "diffusers==0.29.0" \
         "resemble-perth==1.0.1" \
         "conformer==0.3.2" \
         "safetensors==0.5.3" \
         "spacy-pkuseg" \
         "pykakasi==2.3.0" \
         "pyloudnorm" \
         "omegaconf" \
         "huggingface_hub" \
         "soundfile" \
         "sentencepiece" \
         "fastapi" \
         "uvicorn" \
         "psutil" \
    && python -m pip install --no-deps -e /app/external/chatterbox

RUN mkdir -p /models /models/.hf_home

EXPOSE 8000

ENTRYPOINT ["/app/Docker/entrypoint.sh"]
CMD ["serve"]
