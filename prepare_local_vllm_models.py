#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from huggingface_hub import snapshot_download


REPO_ROOT = Path(__file__).resolve().parent

BASE_REPO_ID = "ResembleAI/chatterbox"
TURBO_REPO_ID = "ResembleAI/chatterbox-turbo"

BASE_FILES = (
    "ve.pt",
    "t3_mtl23ls_v2.safetensors",
    "grapheme_mtl_merged_expanded_v1.json",
    "conds.pt",
    "Cangjie5_TC.json",
)
TURBO_FILES = ("s3gen_meanflow.safetensors",)
EXPORT_FILES = (
    "config.json",
    "generation_config.json",
    "model.safetensors",
    "chatterbox_vllm_export.json",
)


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


def ensure_base_checkpoint(base_dir: Path) -> None:
    missing = require_files(base_dir, BASE_FILES)
    if not missing:
        return
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
            f"Base checkpoint download finished but {base_dir} is still missing: {', '.join(missing)}"
        )


def ensure_turbo_checkpoint(turbo_dir: Path) -> None:
    missing = require_files(turbo_dir, TURBO_FILES)
    if not missing:
        return
    turbo_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=TURBO_REPO_ID,
        repo_type="model",
        revision="main",
        allow_patterns=list(TURBO_FILES),
        local_dir=str(turbo_dir),
        local_dir_use_symlinks=False,
        token=os.getenv("HF_TOKEN") or True,
    )
    missing = require_files(turbo_dir, TURBO_FILES)
    if missing:
        raise SystemExit(
            f"Turbo checkpoint download finished but {turbo_dir} is still missing: {', '.join(missing)}"
        )


def ensure_vllm_export(base_dir: Path, export_dir: Path, use_copy: bool) -> None:
    if export_ready(export_dir):
        return
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
    if use_copy:
        cmd.append("--copy")
    subprocess.run(cmd, check=True, env=env)
    if not export_ready(export_dir):
        raise SystemExit(f"Export finished but {export_dir} is still incomplete.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download local Chatterbox vLLM artifacts and export the vLLM T3 package."
    )
    parser.add_argument(
        "--model-root",
        default=os.getenv("MODEL_ROOT", str(REPO_ROOT / "runs" / "models")),
        help="Root directory that will contain chatterbox_base, chatterbox_turbo, and t3_vllm_export.",
    )
    parser.add_argument(
        "--base-dir",
        default=None,
        help="Override the base checkpoint directory. Defaults to <model-root>/chatterbox_base.",
    )
    parser.add_argument(
        "--turbo-dir",
        default=None,
        help="Override the turbo S3 checkpoint directory. Defaults to <model-root>/chatterbox_turbo.",
    )
    parser.add_argument(
        "--export-dir",
        default=None,
        help="Override the exported vLLM model directory. Defaults to <model-root>/t3_vllm_export.",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy export weights instead of creating symlinks. Recommended for portability.",
    )
    parser.add_argument(
        "--skip-base-download",
        action="store_true",
        help="Do not download the base checkpoint; assume it already exists.",
    )
    parser.add_argument(
        "--skip-turbo-download",
        action="store_true",
        help="Do not download the turbo checkpoint; assume it already exists.",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Do not export the vLLM package; assume it already exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_root = Path(args.model_root).expanduser().resolve()
    base_dir = Path(args.base_dir).expanduser().resolve() if args.base_dir else model_root / "chatterbox_base"
    turbo_dir = Path(args.turbo_dir).expanduser().resolve() if args.turbo_dir else model_root / "chatterbox_turbo"
    export_dir = Path(args.export_dir).expanduser().resolve() if args.export_dir else model_root / "t3_vllm_export"

    if not args.skip_base_download:
        ensure_base_checkpoint(base_dir)
    if not args.skip_turbo_download:
        ensure_turbo_checkpoint(turbo_dir)
    if not args.skip_export:
        ensure_vllm_export(base_dir, export_dir, use_copy=args.copy)

    summary = {
        "model_root": str(model_root),
        "base_checkpoint_dir": str(base_dir),
        "turbo_s3_checkpoint_dir": str(turbo_dir),
        "vllm_model_dir": str(export_dir),
        "base_ready": not require_files(base_dir, BASE_FILES),
        "turbo_ready": not require_files(turbo_dir, TURBO_FILES),
        "export_ready": export_ready(export_dir),
        "default_audio_prompt_path": str(REPO_ROOT / "SPK_17_000003.wav"),
        "hf_token_present": bool(os.getenv("HF_TOKEN")),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
