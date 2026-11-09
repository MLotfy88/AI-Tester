"""فحص ملاءمة GGUF لجهازك (VRAM/RAM) وسقف السرعة النظري.

يعتمد على معادلات HF-Model-Selection-Workflow.md (القسم 9 والملحق B).
لا يشغّل النموذج؛ الحساب تحليلي من metadata الملف + device_profile.yaml.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
from pathlib import Path

from common import GIB, load_yaml, repo_path

KV_BYTES = {"f16": 2.0, "q8_0": 34 / 32, "q4_0": 18 / 32}

DEVICE_DEFAULT = {
    "gpu_bw_gbps": 160.0,
    "gpu_fp32_tflops": 2.496,
    "ram_bw_gbps": 27.0,
    "cpu_fp32_gflops": 435.2,
}
ETA_DEFAULT = {"gpu_tg": 1.0, "cpu_tg": 1.0, "gpu_pp": 1.0, "cpu_pp": 1.0}


def _as_int(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def total_size(path: str | Path) -> int:
    path = str(path)
    m = re.match(r"(.*)-\d{5}-of-(\d{5})\.gguf$", path)
    if not m:
        return os.path.getsize(path)
    return sum(os.path.getsize(p) for p in glob.glob(f"{m.group(1)}-*-of-{m.group(2)}.gguf"))


def _field_value(field):
    if field is None:
        return None
    if hasattr(field, "contents"):
        try:
            return field.contents()
        except Exception:
            pass
    parts = getattr(field, "parts", None)
    data = getattr(field, "data", None)
    if parts is not None and data is not None and len(data):
        part = parts[data[0]]
        try:
            if getattr(part, "size", 0) == 1:
                return part.tolist()[0]
        except Exception:
            pass
        try:
            return bytes(part).decode("utf-8", errors="replace")
        except Exception:
            pass
    try:
        return field.tolist()
    except Exception:
        return None


def read_meta(path: str | Path) -> dict:
    """يقرأ الحقول المطلوبة من GGUF. لو gguf غير متاح يرجع error بدل ما يرمي استثناء."""
    meta = {
        "arch": None,
        "block_count": None,
        "head_count": None,
        "head_count_kv": None,
        "embedding_length": None,
        "key_length": None,
        "has_chat_template": None,
        "parameter_count": None,
        "error": "",
    }
    try:
        from gguf import GGUFReader

        reader = GGUFReader(str(path))
        fields = reader.fields

        def val(key):
            return _field_value(fields.get(key))

        arch = val("general.architecture")
        arch = str(arch) if arch is not None else None
        meta["arch"] = arch
        if arch:
            meta["block_count"] = _as_int(val(f"{arch}.block_count"))
            meta["head_count"] = _as_int(val(f"{arch}.attention.head_count"))
            meta["embedding_length"] = _as_int(val(f"{arch}.embedding_length"))
            meta["key_length"] = _as_int(val(f"{arch}.attention.key_length"))
            kv = val(f"{arch}.attention.head_count_kv")
            if isinstance(kv, (list, tuple)):
                meta["head_count_kv"] = [_as_int(x) for x in kv]
            else:
                meta["head_count_kv"] = _as_int(kv)
        meta["has_chat_template"] = "tokenizer.chat_template" in fields
        pc = val("general.parameter_count")
        if pc is not None:
            try:
                meta["parameter_count"] = int(pc)
            except Exception:
                pass
    except Exception as exc:  # pragma: no cover - يعتمد على الملف
        meta["error"] = f"{type(exc).__name__}: {exc}"
    return meta


def read_chat_template(path: str | Path) -> str:
    """قالب المحادثة المدمج داخل الـ GGUF (tokenizer.chat_template) — نص صريح."""
    try:
        from gguf import GGUFReader

        reader = GGUFReader(str(path))
        value = _field_value(reader.fields.get("tokenizer.chat_template"))
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, list):
            return "\n".join(str(x) for x in value)
        return str(value or "")
    except Exception:
        return ""


def estimate(
    meta: dict,
    file_bytes: int,
    ctx: int = 8192,
    budget_gib: float = 3.4,
    compute_gib: float = 0.3,
    kv_type: str = "f16",
    gpu_bw: float = 160.0,
    ram_bw: float = 27.0,
    safety: float = 0.95,
) -> dict:
    n_layers = int(meta.get("block_count") or 0)
    n_head = int(meta.get("head_count") or 0)
    if n_layers <= 0 or n_head <= 0:
        raise ValueError("metadata ناقصة (block_count/head_count)؛ مش ممكن حساب الـ fit.")

    n_kv = meta.get("head_count_kv") or n_head
    head_dim = meta.get("key_length") or (int(meta.get("embedding_length") or 0) // n_head)
    if not head_dim:
        raise ValueError("head_dim غير معروف (embedding_length/head_count).")

    bpe = KV_BYTES[kv_type]
    kv_list = n_kv if isinstance(n_kv, list) else [n_kv] * n_layers
    kv_total = sum(2 * ctx * int(k) * int(head_dim) * bpe for k in kv_list) / GIB
    kv_layer = kv_total / n_layers
    file_gib = file_bytes / GIB
    w_layer = file_gib / n_layers
    need_full = file_gib + kv_total + compute_gib

    if need_full <= budget_gib:
        ngl = n_layers
    else:
        avail = max(0.0, budget_gib - compute_gib) * safety
        ngl = max(0, min(n_layers, math.floor(avail / (w_layer + kv_layer))))

    file_gb = file_bytes / 1e9
    gpu_gb = file_gb * ngl / n_layers
    cpu_gb = file_gb - gpu_gb
    t = gpu_gb / gpu_bw + (cpu_gb / ram_bw if cpu_gb > 0 else 0.0)

    return {
        "n_layers": n_layers,
        "n_head": n_head,
        "n_kv": n_kv,
        "head_dim": int(head_dim),
        "kv_total_gib": round(kv_total, 3),
        "kv_layer_mib": round(kv_layer * 1024, 2),
        "file_gib": round(file_gib, 3),
        "need_full_gib": round(need_full, 3),
        "ngl": int(ngl),
        "gpu_share": round(ngl / n_layers, 3),
        "tps_ceiling": round(1 / t, 1) if t > 0 else None,
    }


def classify(est: dict, ram_gib: float, ram_overhead_gib: float = 4.0) -> str:
    cpu_share = 1 - est["gpu_share"]
    cpu_gib = (est["file_gib"] + est["kv_total_gib"]) * cpu_share
    if cpu_gib + ram_overhead_gib > ram_gib:
        return "No fit"
    if est["ngl"] == est["n_layers"]:
        return "Full GPU"
    return "Partial" if est["gpu_share"] >= 0.5 else "Mostly CPU"


def params_from_file(file_bytes: int, bits_per_weight: float = 4.85) -> float:
    return file_bytes * 8 / (bits_per_weight * 1e9)


def speed_model(est: dict, file_bytes: int, params_b: float, dev: dict | None = None, eta: dict | None = None) -> dict:
    dev = {**DEVICE_DEFAULT, **(dev or {})}
    eta = {**ETA_DEFAULT, **(eta or {})}
    share = est["gpu_share"]
    file_gb = file_bytes / 1e9
    gpu_gb, cpu_gb = file_gb * share, file_gb * (1 - share)

    t_tg = gpu_gb / (dev["gpu_bw_gbps"] * eta["gpu_tg"]) if gpu_gb > 0 else 0.0
    if cpu_gb > 0:
        t_tg += cpu_gb / (dev["ram_bw_gbps"] * eta["cpu_tg"])

    flop_tok = 2 * params_b * 1e9
    t_pp = share * flop_tok / (dev["gpu_fp32_tflops"] * 1e12 * eta["gpu_pp"])
    if share < 1:
        t_pp += (1 - share) * flop_tok / (dev["cpu_fp32_gflops"] * 1e9 * eta["cpu_pp"])

    return {
        "tg_tps": round(1 / t_tg, 1) if t_tg > 0 else None,
        "pp_tps": round(1 / t_pp, 1) if t_pp > 0 else None,
    }


def load_cfg(profile_path: str | Path | None, cli: dict) -> dict:
    cfg = {
        # ctx ثابت = 8192 (ورقة الامتحان v3) — أي قيمة تانية مرفوضة من run_exam.py
        "ctx": 8192,
        "budget": 3.4,
        "compute": 0.3,
        "kv": "f16",
        "ram": 15.9,
        "dev": dict(DEVICE_DEFAULT),
        "eta": dict(ETA_DEFAULT),
    }
    if profile_path:
        p = load_yaml(repo_path(profile_path))
        cfg["budget"] = float((p.get("budgets") or {}).get("vram_budget_gib", cfg["budget"]))
        cfg["compute"] = float((p.get("budgets") or {}).get("compute_buffer_gib", cfg["compute"]))
        cfg["ram"] = float((p.get("ram") or {}).get("usable_gib", cfg["ram"]))
        gpu = p.get("gpu") or {}
        ram = p.get("ram") or {}
        cpu = p.get("cpu") or {}
        cfg["dev"].update(
            gpu_bw_gbps=float(gpu.get("bw_gbps", cfg["dev"]["gpu_bw_gbps"])),
            gpu_fp32_tflops=float(gpu.get("fp32_tflops", cfg["dev"]["gpu_fp32_tflops"])),
            ram_bw_gbps=float(ram.get("bw_effective_gbps", cfg["dev"]["ram_bw_gbps"])),
        )
        cores = float(cpu.get("cores", 4))
        ghz = float(cpu.get("turbo_all_core_ghz", 3.4))
        cfg["dev"]["cpu_fp32_gflops"] = round(cores * ghz * 32, 1)
        cal = p.get("calibration") or {}
        cfg["eta"].update({k: float(v) for k, v in cal.items() if v is not None})
    for k, v in cli.items():
        if v is not None:
            cfg[k] = v
    return cfg


def analyze(
    gguf_path: str | Path,
    *,
    profile_path: str | Path | None = "config/device_profile.yaml",
    ctx: int = 8192,
    kv: str = "f16",
    params_b: float | None = None,
    budget: float | None = None,
    ram: float | None = None,
) -> dict:
    cfg = load_cfg(profile_path, {"ctx": ctx, "kv": kv, "budget": budget, "ram": ram})
    meta = read_meta(gguf_path)
    size = total_size(gguf_path)
    out = {
        "file": str(gguf_path),
        "file_bytes": size,
        "file_gib": round(size / GIB, 3),
        "ctx": cfg["ctx"],
        "kv": cfg["kv"],
        "meta": meta,
        "device": cfg["dev"],
        "budget_gib": cfg["budget"],
        "ram_gib": cfg["ram"],
        "calibrated": any(v != 1.0 for v in cfg["eta"].values()),
        "error": "",
    }

    if meta.get("error") or not meta.get("block_count"):
        out["fit_class"] = "Unknown"
        out["error"] = meta.get("error") or "metadata ناقصة"
        return out

    try:
        est = estimate(
            meta,
            size,
            cfg["ctx"],
            cfg["budget"],
            cfg["compute"],
            cfg["kv"],
            cfg["dev"]["gpu_bw_gbps"],
            cfg["dev"]["ram_bw_gbps"],
        )
        est["fit_class"] = classify(est, cfg["ram"])
        pb = params_b or (meta.get("parameter_count") or 0) / 1e9
        if not pb:
            pb = params_from_file(size)
        est["params_b_assumed"] = round(float(pb), 2)
        est.update(speed_model(est, size, float(pb), cfg["dev"], cfg["eta"]))
        out.update(est)
        out["run_command"] = (
            f"llama-server -m \"{Path(gguf_path).name}\" "
            f"-c {cfg['ctx']} -ngl {est['ngl']} -t 4 --jinja"
        )
    except Exception as exc:
        out["fit_class"] = "Unknown"
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--profile", default="config/device_profile.yaml")
    ap.add_argument("--ctx", type=int, default=8192, help="لازم 8192 — ورقة الامتحان v3 ثابتة")
    ap.add_argument("--kv", choices=list(KV_BYTES), default="f16")
    ap.add_argument("--params-b", type=float, default=None)
    ap.add_argument("--budget", type=float, default=None)
    ap.add_argument("--ram", type=float, default=None)
    args = ap.parse_args()

    result = analyze(
        args.gguf,
        profile_path=args.profile,
        ctx=args.ctx,
        kv=args.kv,
        params_b=args.params_b,
        budget=args.budget,
        ram=args.ram,
    )
    # عرض فقط على الطرفية — السكربت لا يكتب أي ملف JSON.
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
