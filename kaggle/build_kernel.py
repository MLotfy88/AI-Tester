"""يبني مجلد الـ Kaggle kernel من مشروع الامتحان (بدون أي رفع).

اللي بيحصل:
  1. المشروع (scripts/config/prompts/templates) بيتضغط zip ويتحوّل base64.
  2. القيم بتتحقن في قالب `kaggle/kernel_main.py` (المكان placeholder).
  3. القالب بيتقسّم لخلايا notebook بشكل `# %%` ويتكتب `exam-runner.ipynb`.
  4. بيتكتب `kernel-metadata.json` (GPU + Internet + private).

الاستخدام:
    python kaggle/build_kernel.py --models Qwen/Qwen3-4B-GGUF --owner myuser
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import re
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = Path(__file__).resolve().parent / "kernel_main.py"
INCLUDE = ("scripts", "config", "prompts", "templates")

# ملاحظة: أسماء الـ accelerator بتتغير من نسخة للتانية في Kaggle CLI.
# بنكتبها في الميتاداتا + بنتحقق جوه الـ notebook إن الكارت هو المتوقع (Cell 2).
# Kaggle حالياً بيدي T4×2 (كارت واحد فعلياً) — P100 اتشال من المنصة.
ACCELERATORS = {
    "t4x2": "nvidiaTeslaT4",
}


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return text or "exam-kernel"


def project_zip_b64() -> tuple[str, int]:
    """يضغط ملفات المشروع المطلوبة للامتحان ويرجع (base64, عدد_الملفات)."""
    buf = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for top in INCLUDE:
            base = REPO / top
            if not base.exists():
                continue
            for path in sorted(base.rglob("*")):
                if not path.is_file():
                    continue
                if "__pycache__" in path.parts:
                    continue
                if path.suffix in (".pyc", ".pyo"):
                    continue
                zf.write(path, path.relative_to(REPO).as_posix())
                count += 1
    return base64.b64encode(buf.getvalue()).decode("ascii"), count


def split_cells(source: str) -> list[dict]:
    """يبني خلايا notebook من قالب فيه فواصل `# %%`."""
    cells: list[dict] = []
    parts = re.split(r"^# %%( \[markdown\])?\s*$", source, flags=re.MULTILINE)
    # parts = [قبل أي فاصل, نوع الفاصل, نص الخلية, نوع الفاصل, نص الخلية, ...]
    index = 1
    while index < len(parts) - 1:
        kind = parts[index]
        body = parts[index + 1].strip("\n")
        index += 2
        if not body.strip():
            continue
        if kind:  # خلية markdown
            cells.append(
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [line + "\n" for line in body.split("\n")],
                }
            )
        else:
            cells.append(
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [line + "\n" for line in body.split("\n")],
                }
            )
    return cells


def build(
    *,
    owner: str,
    kernel_name: str,
    models: str,
    quant: str = "Q4_K_M",
    ctx: int = 4096,
    policy: str = "paper",
    accelerator: str = "t4x2",
    vram_gib: float = 3.4,
    ram_gib: float = 15.9,
    threads: int = 8,
    llama_tag: str = "latest",
    kv: str = "f16",
    template_mode: str = "auto",
    max_gib: float = 20.0,
    model_timeout: int = 300,
    total_timeout: int = 600,
    out_dir: str | Path | None = None,
) -> dict:
    """يبني مجلد الـ kernel ويرجع dict بالمسارات والقيم."""
    slug = slugify(kernel_name)
    out = Path(out_dir) if out_dir else REPO / "kaggle" / "_build" / slug
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    params = {
        "models": models,
        "quant": quant,
        "ctx": ctx,
        "policy": policy,
        "vram_gib": vram_gib,
        "ram_gib": ram_gib,
        "threads": threads,
        "llama_tag": llama_tag,
        "kv": kv,
        "template_mode": template_mode,
        "max_gib": max_gib,
        "model_timeout": model_timeout,
        "total_timeout": total_timeout,
        "gpu_expect": ["T4"] if accelerator in ACCELERATORS else [],
        "accelerator": ACCELERATORS.get(accelerator, ""),
    }

    project_b64, files_count = project_zip_b64()
    template = TEMPLATE.read_text(encoding="utf-8")
    source = template.replace("__PARAMS_JSON__", json.dumps(params, ensure_ascii=False))
    source = source.replace("__PROJECT_B64__", project_b64)
    cells = split_cells(source)

    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.11"},
            "kaggle": {
                "accelerator": params["accelerator"] or "nvidiaTeslaT4",
                "dataSources": [],
                "isGpuEnabled": True,
                "isInternetEnabled": True,
                "language": "python",
                "sourceType": "notebook",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    notebook_path = out / f"{slug}.ipynb"
    notebook_path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")

    metadata = {
        "id": f"{owner}/{slug}" if owner else slug,
        "title": slug,
        "code_file": notebook_path.name,
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,
        "enable_tpu": False,
        "dataset_sources": [],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }
    (out / "kernel-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    info = {
        "dir": str(out),
        "notebook": str(notebook_path),
        "metadata": str(out / "kernel-metadata.json"),
        "kernel_id": metadata["id"],
        "slug": slug,
        "params": params,
        "project_files": files_count,
        "project_b64_chars": len(project_b64),
        "cells": len(cells),
    }
    (out / "build_info.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description="بناء مجلد Kaggle kernel للامتحان (بدون رفع)")
    ap.add_argument("--models", required=True, help="repo ids على HF مفصولة بفاصلة")
    ap.add_argument("--owner", default="", help="اسم حساب Kaggle (لازم للـ id)")
    ap.add_argument("--kernel-name", default="", help="اسم الـ kernel (افتراضي: exam-<تاريخ>)")
    ap.add_argument("--quant", default="Q4_K_M")
    ap.add_argument("--ctx", type=int, default=4096)
    ap.add_argument("--policy", default="paper", choices=["paper", "baseline"])
    ap.add_argument("--accelerator", default="t4x2", choices=sorted(ACCELERATORS))
    ap.add_argument("--vram-gib", type=float, default=3.4)
    ap.add_argument("--ram-gib", type=float, default=15.9)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--llama-tag", default="latest")
    ap.add_argument("--kv", default="f16")
    ap.add_argument("--template-mode", default="auto", choices=["auto", "exam", "model"])
    ap.add_argument("--max-gib", type=float, default=20.0)
    ap.add_argument("--model-timeout", type=int, default=300)
    ap.add_argument("--total-timeout", type=int, default=600)
    ap.add_argument("--out", default="", help="مجلد البناء (افتراضي kaggle/_build/<slug>)")
    args = ap.parse_args()

    import time as _time

    info = build(
        owner=args.owner,
        kernel_name=args.kernel_name or f"exam-{_time.strftime('%Y%m%d-%H%M')}",
        models=args.models,
        quant=args.quant,
        ctx=args.ctx,
        policy=args.policy,
        accelerator=args.accelerator,
        vram_gib=args.vram_gib,
        ram_gib=args.ram_gib,
        threads=args.threads,
        llama_tag=args.llama_tag,
        kv=args.kv,
        template_mode=args.template_mode,
        max_gib=args.max_gib,
        model_timeout=args.model_timeout,
        total_timeout=args.total_timeout,
        out_dir=args.out or None,
    )
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
