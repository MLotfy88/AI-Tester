"""طبقة «الإعدادات الموصى بها لكل موديل».

الفكرة: كل موديل عنده توصيات من مطوّره (قالب محادثة، نوع KV cache، flash-attn،
عدد الطبقات على الـ GPU، sampling...). الأداة لازم:
  1) تحترم إعدادات الامتحان الثابتة (temp=0 · seed · ctx=4096 · max_tokens=1200
     · الـ system prompt · المصحّح) — لأنها أساس المقارنة.
  2) تطبّق توصيات المطوّر على كل إعدادات التشغيل اللي مش بتأثر على الدرجة.
  3) تعرض توصيات التوليد (temperature/top_p/...) في التقرير بدون تطبيقها،
     لأن تطبيقها بيكسر الحتمية.

المصدر: config/model_overrides.yaml (قابل للتعديل من المستخدم).
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from common import load_yaml, repo_path, sha256_text

DEFAULT_OVERRIDES = "config/model_overrides.yaml"

# إعدادات الامتحان الثابتة — أي overrides مشallowed يغيّرها
FIXED_EXAM_SETTINGS = ("temperature", "top_p", "seed", "ctx_size", "max_tokens", "system_prompt")


@dataclass
class ModelSettings:
    """الإعدادات الفعلية اللي هتتنطبّق على موديل واحد."""

    source: str = "defaults"
    matched_key: str = ""
    chat_template: str = ""
    template_source: str = "exam"  # exam | model | override
    kv_cache_type: str = "f16"
    flash_attn: str = ""
    n_gpu_layers: int | None = None
    threads: int | None = None
    device: str = ""
    extra_server_args: list[str] = field(default_factory=list)
    recommended_sampling: dict = field(default_factory=dict)
    sampling_source: str = "none"
    notes: str = ""
    warnings: list[str] = field(default_factory=list)
    applied: list[str] = field(default_factory=list)
    template_sha256: str = ""

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "matched_key": self.matched_key,
            "chat_template": self.chat_template,
            "template_source": self.template_source,
            "template_sha256": self.template_sha256,
            "kv_cache_type": self.kv_cache_type,
            "flash_attn": self.flash_attn,
            "n_gpu_layers": self.n_gpu_layers,
            "threads": self.threads,
            "device": self.device,
            "extra_server_args": list(self.extra_server_args),
            "recommended_sampling": dict(self.recommended_sampling),
            "sampling_source": self.sampling_source,
            "notes": self.notes,
            "warnings": list(self.warnings),
            "applied": list(self.applied),
        }


def load_overrides(path: str | Path | None = None) -> dict:
    """يقرأ ملف الـ overrides؛ لو مش موجود بيرجع {} بدون ما يكسر التشغيل."""
    target = Path(path or DEFAULT_OVERRIDES)
    if not target.is_absolute():
        target = repo_path(target)
    if not target.exists():
        return {}
    data = load_yaml(target)
    return data if isinstance(data, dict) else {}


def _slug_key(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def match_entry(model_key: str, overrides: dict) -> tuple[dict, str, str]:
    """يلاقي أنسب entry للموديل. يرجع (entry, source, matched_key)."""
    models = overrides.get("models") or {}
    key = _slug_key(model_key)

    for name, entry in models.items():
        if _slug_key(name) == key:
            return dict(entry or {}), "override", str(name)

    for name, entry in models.items():
        pattern = _slug_key(name)
        if any(ch in pattern for ch in "*?["):
            if fnmatch.fnmatch(key, pattern):
                return dict(entry or {}), "override", str(name)

    # مطابقة بالعائلة: Qwen3.5-4B → qwen35
    family = family_of(key)
    if family:
        for name, entry in models.items():
            if _slug_key(name) == family:
                return dict(entry or {}), "override", str(name)

    return dict(overrides.get("defaults") or {}), "defaults", "defaults"


def family_of(model_key: str) -> str:
    """اسم عائلة الموديل (qwen35 / qwen3 / llama / gemma / phi ...)."""
    key = _slug_key(model_key)
    if "qwen3.5" in key or "qwen35" in key:
        return "qwen35"
    if "qwen3" in key:
        return "qwen3"
    if "gemma-3" in key or "gemma3" in key:
        return "gemma3"
    if "gemma" in key:
        return "gemma"
    if "llama-3" in key or "llama3" in key:
        return "llama3"
    if "phi-3" in key or "phi3" in key:
        return "phi3"
    if "mistral" in key:
        return "mistral"
    return ""


def extract_embedded_template(gguf_path: str | Path | None) -> str:
    """قالب المحادثة المدمج داخل الـ GGUF (لو موجود)."""
    if not gguf_path:
        return ""
    try:
        from fit_check import read_chat_template

        return read_chat_template(gguf_path)
    except Exception:
        return ""


SAMPLING_KEYS = (
    ("temperature", "temperature"),
    ("top_p", "top_p"),
    ("top_k", "top_k"),
    ("min_p", "min_p"),
    ("repeat_penalty", "repetition_penalty"),
)


def sampling_from_generation_config(data: dict | None) -> dict:
    """توصيات Sampling الرسمية من generation_config.json (تلقائي)."""
    out: dict[str, Any] = {}
    data = data or {}
    for our_key, hf_key in SAMPLING_KEYS:
        value = data.get(hf_key)
        if value is None:
            continue
        try:
            out[our_key] = float(value) if our_key != "top_k" else int(value)
        except (TypeError, ValueError):
            continue
    return out


def resolve(
    model_key: str,
    *,
    overrides: dict | None = None,
    exam_template: str = "templates/qwen35_egyptian_nothink.jinja",
    template_mode: str = "exam",
    gguf_path: str | Path | None = None,
    cli: dict | None = None,
    generation_config: dict | None = None,
    write_template_dir: str | Path | None = None,
) -> ModelSettings:
    """يحسب الإعدادات الفعلية لموديل واحد.

    cli = {kv, threads, ngl, device, flash_attn, extra_server_args} — أولوية الـ CLI
    فوق الـ overrides، والـ overrides فوق الـ defaults.
    """
    overrides = overrides or {}
    cli = cli or {}
    entry, source, matched = match_entry(model_key, overrides)
    defaults = overrides.get("defaults") or {}

    ms = ModelSettings(source=source, matched_key=matched)
    ms.notes = str(entry.get("notes") or defaults.get("notes") or "")

    # توصيات التوليد: التلقائي (generation_config) ثم الـ overrides فوقه
    auto_sampling = sampling_from_generation_config(generation_config)
    manual_sampling = {
        key: value
        for key, value in dict(
            entry.get("recommended_sampling") or defaults.get("recommended_sampling") or {}
        ).items()
        if value is not None
    }
    ms.recommended_sampling = {**auto_sampling, **manual_sampling}
    ms.sampling_source = "generation_config" if auto_sampling else ""
    if manual_sampling:
        ms.sampling_source = (
            "overrides" if not auto_sampling else "overrides+generation_config"
        )
    if not ms.recommended_sampling:
        ms.sampling_source = "none"

    # ── قالب المحادثة
    template = str(entry.get("chat_template") or defaults.get("chat_template") or "")
    embedded = ""
    if template_mode == "model" or not template:
        embedded = extract_embedded_template(gguf_path)
    if template:
        ms.chat_template = template
        ms.template_source = "override"
    elif template_mode == "model" and embedded:
        target = Path(write_template_dir or ".") / f"{_safe_name(model_key)}.jinja"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(embedded, encoding="utf-8")
        ms.chat_template = str(target)
        ms.template_source = "model"
    else:
        ms.chat_template = exam_template
        ms.template_source = "exam"
        if template_mode == "model":
            ms.warnings.append(
                "وضع القالب 'model': الموديل مفيهوش قالب محادثة مدمج، "
                "فاستُخدم قالب الامتحان."
            )

    exam_template_path = repo_path(exam_template)
    if ms.template_source == "exam" and embedded:
        try:
            if sha256_text(embedded) != sha256_text(exam_template_path.read_text(encoding="utf-8")):
                ms.warnings.append(
                    "قالب الموديل المدمج مختلف عن قالب الامتحان — في وضع 'exam' "
                    "استُخدم قالب الامتحان للحفاظ على قابلية المقارنة."
                )
        except Exception:
            pass

    # ── إعدادات التشغيل
    def pick(cli_key: str, entry_key: str, default_key: str, fallback: Any = None) -> Any:
        if cli.get(cli_key) not in (None, ""):
            return cli[cli_key]
        value = entry.get(entry_key)
        if value in (None, ""):
            value = defaults.get(default_key)
        if value in (None, ""):
            return fallback
        return value

    ms.kv_cache_type = str(pick("kv", "kv_cache_type", "kv_cache_type", "f16"))
    ms.flash_attn = str(pick("flash_attn", "flash_attn", "flash_attn", "") or "")
    ms.device = str(pick("device", "device", "device", "") or "")

    ngl = pick("ngl", "n_gpu_layers", "n_gpu_layers", None)
    ms.n_gpu_layers = int(ngl) if ngl not in (None, "") else None

    threads = pick("threads", "threads", "threads", None)
    ms.threads = int(threads) if threads not in (None, "") else None

    extra = cli.get("extra_server_args")
    if extra in (None, []):
        extra = entry.get("extra_server_args")
    if extra in (None, []):
        extra = defaults.get("extra_server_args")
    ms.extra_server_args = [str(x) for x in (extra or []) if str(x).strip()]

    # ── تعارضات مع إعدادات الامتحان الثابتة
    for key, value in (entry.get("exam_overrides") or {}).items():
        ms.warnings.append(
            f"'{key}' مثبّت في ورقة الامتحان ({FIXED_EXAM_SETTINGS}) — "
            f"تم تجاهل التوصية '{value}' حفاظاً على قابلية المقارنة."
        )

    ms.applied = _describe(ms)
    if ms.template_source == "override":
        ms.applied.append(f"قالب المحادثة: {ms.chat_template} (من overrides)")
    elif ms.template_source == "model":
        ms.applied.append("قالب المحادثة: القالب المدمج في الـ GGUF")
    else:
        ms.applied.append("قالب المحادثة: قالب الامتحان (للمقارنة العادلة)")
    if ms.kv_cache_type:
        ms.applied.append(f"KV cache: {ms.kv_cache_type}")
    if ms.flash_attn:
        ms.applied.append(f"flash-attn: {ms.flash_attn}")
    if ms.n_gpu_layers is not None:
        ms.applied.append(f"ngl: {ms.n_gpu_layers}")
    if ms.threads is not None:
        ms.applied.append(f"threads: {ms.threads}")
    if ms.device:
        ms.applied.append(f"device: {ms.device}")
    if ms.extra_server_args:
        ms.applied.append("flags إضافية: " + " ".join(ms.extra_server_args))
    if ms.recommended_sampling:
        ms.applied.append(
            "توصيات التوليد (معروضة بس — لا تُطبَّق افتراضياً): "
            + " · ".join(f"{k}={v}" for k, v in ms.recommended_sampling.items())
            + f" [المصدر: {ms.sampling_source}]"
        )

    try:
        ms.template_sha256 = sha256_text(repo_path(ms.chat_template).read_text(encoding="utf-8"))
    except Exception:
        ms.template_sha256 = ""
    return ms


def _safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "__", str(value or "model")).strip("._-")
    return (name or "model")[:80]


def _describe(ms: ModelSettings) -> list[str]:
    out = []
    if ms.source == "override":
        out.append(f"مطابقة overrides: {ms.matched_key}")
    elif ms.source == "defaults":
        out.append("لا توجد توصيات خاصة — استُخدمت الإعدادات العامة")
    return out


__all__ = [
    "ModelSettings",
    "load_overrides",
    "match_entry",
    "resolve",
    "family_of",
    "extract_embedded_template",
    "sampling_from_generation_config",
    "FIXED_EXAM_SETTINGS",
]
