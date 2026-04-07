#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from huggingface_hub import snapshot_download


REPO_ROOT = Path(__file__).resolve().parents[1]


BASE_T3_FILENAME = "t3_mtl23ls_v2.safetensors"
BASE_REPO_ID = "ResembleAI/chatterbox"
TURBO_REPO_ID = "ResembleAI/chatterbox-turbo"
TURBO_FILENAME = "s3gen_meanflow.safetensors"

BASE_FILES = (
    "ve.pt",
    BASE_T3_FILENAME,
    "grapheme_mtl_merged_expanded_v1.json",
    "conds.pt",
    "Cangjie5_TC.json",
)
EXPORT_FILES = (
    "config.json",
    "generation_config.json",
    "model.safetensors",
    "chatterbox_vllm_export.json",
)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def require_files(root: Path, names: tuple[str, ...]) -> list[str]:
    missing: list[str] = []
    for name in names:
        target = root / name
        if not target.exists():
            missing.append(name)
    return missing


def export_ready(export_dir: Path) -> bool:
    missing = require_files(export_dir, EXPORT_FILES)
    if missing:
        return False
    weights = export_dir / "model.safetensors"
    if weights.is_symlink() and not weights.exists():
        return False
    return True


def ensure_base_checkpoint(base_dir: Path, auto_download: bool) -> None:
    missing = require_files(base_dir, BASE_FILES)
    if not missing:
        return
    if not auto_download:
        raise SystemExit(
            "Base checkpoint is incomplete at "
            f"{base_dir}. Missing: {', '.join(missing)}. "
            "Either mount the files there or set AUTO_DOWNLOAD_BASE_CHECKPOINT=1."
        )
    base_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=BASE_REPO_ID,
        repo_type="model",
        revision="main",
        allow_patterns=list(BASE_FILES),
        local_dir=str(base_dir),
        local_dir_use_symlinks=False,
        token=os.getenv("HF_TOKEN"),
    )
    missing = require_files(base_dir, BASE_FILES)
    if missing:
        raise SystemExit(
            f"Base checkpoint download finished but files are still missing in {base_dir}: {', '.join(missing)}"
        )


def ensure_turbo_checkpoint(turbo_dir: Path, auto_download: bool) -> None:
    missing = require_files(turbo_dir, (TURBO_FILENAME,))
    if not missing:
        return
    if not auto_download:
        raise SystemExit(
            "Turbo S3 checkpoint is incomplete at "
            f"{turbo_dir}. Missing: {', '.join(missing)}. "
            "Either mount the file there or set AUTO_DOWNLOAD_TURBO_S3=1."
        )
    turbo_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=TURBO_REPO_ID,
        allow_patterns=[TURBO_FILENAME],
        local_dir=str(turbo_dir),
        local_dir_use_symlinks=False,
        token=os.getenv("HF_TOKEN") or True,
    )
    missing = require_files(turbo_dir, (TURBO_FILENAME,))
    if missing:
        raise SystemExit(
            f"Turbo S3 download finished but files are still missing in {turbo_dir}: {', '.join(missing)}"
        )


def ensure_vllm_export(base_dir: Path, export_dir: Path, auto_export: bool, export_copy: bool) -> None:
    if export_ready(export_dir):
        return
    if not auto_export:
        raise SystemExit(
            "vLLM export is incomplete at "
            f"{export_dir}. Either mount a self-contained export there or set AUTO_EXPORT_VLLM_MODEL=1. "
            "For Docker, using a copied export (`--copy` / VLLM_EXPORT_COPY=1) is recommended."
        )
    export_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    src_path = str(REPO_ROOT / "external" / "chatterbox" / "src")
    env["PYTHONPATH"] = src_path if not env.get("PYTHONPATH") else f"{src_path}:{env['PYTHONPATH']}"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "external" / "chatterbox" / "export_vllm_t3_model.py"),
        "--base-checkpoint-dir",
        str(base_dir),
        "--output-dir",
        str(export_dir),
    ]
    if export_copy:
        cmd.append("--copy")
    subprocess.run(cmd, check=True, env=env)
    if not export_ready(export_dir):
        raise SystemExit(f"Export finished but {export_dir} is still incomplete.")


def describe(path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
    }


def main() -> None:
    model_root = Path(os.getenv("MODEL_ROOT", "/models"))
    base_dir = Path(os.getenv("BASE_CHECKPOINT_DIR", str(model_root / "chatterbox_base")))
    checkpoint_dir = Path(os.getenv("CHECKPOINT_DIR", str(base_dir)))
    turbo_dir = Path(os.getenv("TURBO_S3_CHECKPOINT_DIR", str(model_root / "chatterbox_turbo")))
    export_dir = Path(os.getenv("VLLM_MODEL_DIR", str(model_root / "t3_vllm_export")))
    prompt_path = Path(os.getenv("DEFAULT_AUDIO_PROMPT_PATH", "/app/SPK_17_000003.wav"))

    auto_download_base = env_bool("AUTO_DOWNLOAD_BASE_CHECKPOINT", False)
    auto_download_turbo = env_bool("AUTO_DOWNLOAD_TURBO_S3", False)
    auto_export = env_bool("AUTO_EXPORT_VLLM_MODEL", False)
    export_copy = env_bool("VLLM_EXPORT_COPY", True)

    ensure_base_checkpoint(base_dir, auto_download=auto_download_base)
    ensure_turbo_checkpoint(turbo_dir, auto_download=auto_download_turbo)
    ensure_vllm_export(base_dir, export_dir, auto_export=auto_export, export_copy=export_copy)

    summary = {
        "model_root": str(model_root),
        "checkpoint_dir": str(checkpoint_dir),
        "base_checkpoint_dir": str(base_dir),
        "turbo_s3_checkpoint_dir": str(turbo_dir),
        "vllm_model_dir": str(export_dir),
        "default_audio_prompt_path": str(prompt_path),
        "default_audio_prompt_exists": prompt_path.exists(),
        "auto_download_base_checkpoint": auto_download_base,
        "auto_download_turbo_s3": auto_download_turbo,
        "auto_export_vllm_model": auto_export,
        "vllm_export_copy": export_copy,
        "artifacts": {
            "base": describe(base_dir),
            "turbo": describe(turbo_dir),
            "vllm_export": describe(export_dir),
        },
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
