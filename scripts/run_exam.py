"""الـ orchestrator: تنزيل → ملاءمة → تشغيل → تصحيح → Excel + HTML.

مصمم لـ GitHub Actions (Linux CPU) لكن يشتغل محلياً كذلك.
- موديل واحد في المرة، وحذف ملفاته بعد الانتهاء لتوفير مساحة القرص.
- مفيش ملفات JSON وسيطة: كل النتائج في الذاكرة، والمخرجات النهائية فقط.
"""
from __future__ import annotations

import argparse
import logging
import os
import platform
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import (  # noqa: E402
    human_bytes,
    now_iso,
    repo_path,
    sha256_file,
    slugify,
)
from exam.grader import grade_exam  # noqa: E402
from exam_runner import run_exam  # noqa: E402
from excel_report import write_workbook  # noqa: E402
from fit_check import analyze as analyze_fit  # noqa: E402
from references import display_name, source_badge, target_gap, trust_flag_for  # noqa: E402
from hf_resolver import (  # noqa: E402
    HFError,
    cleanup_model,
    generation_config,
    resolve_and_download,
)
from html_report import write_report  # noqa: E402
from model_settings import load_overrides, resolve as resolve_model_settings  # noqa: E402


def _split_models(value: str) -> list[str]:
    parts = re.split(r"[,\n;]+", value or "")
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        item = part.strip()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _setup_logger(out_dir: Path) -> logging.Logger:
    out_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("exam")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")

    fh = logging.FileHandler(out_dir / "run.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    logger.propagate = False
    return logger


def _local_manifest(path: Path) -> dict:
    p = path.resolve()
    return {
        "repo": str(p),
        "revision": "local",
        "sha": sha256_file(p),
        "license": "local",
        "quant_pattern": "local",
        "files": [{"path": p.name, "local_path": str(p), "bytes": p.stat().st_size}],
        "primary_path": str(p),
        "total_bytes": p.stat().st_size,
        "url": "",
        "is_local": True,
    }


def _summary_md(results: list[dict], exam_cfg: dict, run_meta: dict) -> str:
    baseline = exam_cfg.get("baseline") or {}
    target = exam_cfg.get("target") or {}
    axes_cfg = exam_cfg.get("axes") or {}
    lines = [
        f"# نتائج امتحان المساعد المصري — {run_meta.get('run_id', '')}",
        "",
        f"- **البداية:** {run_meta.get('started_at', '—')}",
        f"- **النهاية:** {run_meta.get('finished_at', '—')}",
        f"- **عدد الموديلات:** {len(results)}",
        f"- **الإعدادات:** temp=0 · seed=20261106 · ctx={exam_cfg.get('settings', {}).get('ctx_size')} · "
        f"max_tokens={exam_cfg.get('settings', {}).get('max_tokens')}",
        f"- **سياسة التصحيح:** {run_meta.get('policy', 'paper')} · "
        f"الوضع: {run_meta.get('template_mode', 'auto')} · الكمية: {run_meta.get('quant_pattern', 'Q4_K_M')}",
        "",
        "| # | الموديل | الحالة | الدرجة /100 | درجة المقارنة (baseline) | الحكم | غير موثوق (②) | ① | ② | ③ | ④ | البوابات | Fit | ⚡ tok/s (مقيس) | الزمن | Δ الهدف | المسافة عن الهدف |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, result in enumerate(results, 1):
        exam = result.get("exam") or {}
        fit = result.get("fit") or {}
        rt = result.get("runtime") or {}
        axes = exam.get("axes") or {}
        axis_vals = " | ".join(
            f"{(axes.get(k) or {}).get('score', '—')}/{(axes.get(k) or {}).get('max', '—')}"
            for k in ("1", "2", "3", "4")
        )
        fired = "، ".join(g["code"] for g in exam.get("gates", []) if g.get("fired")) or "سليمة"
        status = "تم" if exam else "فشل"
        comparison = (exam.get("baseline") or {}).get("total", "—")
        perf = rt.get("perf") or {}
        tg_avg = (perf.get("tg_tps") or {}).get("avg")
        competing = (rt.get("gpu_contention") or {}).get("competing_processes") or []
        speed_cell = (
            f"{round(float(tg_avg), 1)} ⚠" if tg_avg is not None and competing
            else (round(float(tg_avg), 1) if tg_avg is not None else "—")
        )
        # وسم «غير موثوق» — على المحور ② فقط (مش حكم كلي)
        trust = str(exam.get("trust_flag") or "") or str((axes.get("2") or {}).get("trust_flag") or "")
        # المسافة عن شريط الهدف (Gemini 2.5 Pro)
        gap = target_gap(exam, target, axes_cfg) if target else {"total": None, "distance": None}
        gap_total = gap.get("total")
        gap_cell = "—" if gap_total is None else f"{gap_total:+.2f}"
        dist_cell = "—" if gap.get("distance") is None else f"{gap['distance']:.1f}"
        lines.append(
            f"| {i} | `{result.get('model', '')}` | {status} | {exam.get('total', '—')} | {comparison} | "
            f"{exam.get('verdict') or (result.get('error') or '—')} | {trust or '—'} | {axis_vals} | {fired} | "
            f"{fit.get('fit_class', '—')} | {speed_cell} | {round((rt.get('seconds_total') or 0) / 60, 1)} د | "
            f"{gap_cell} | {dist_cell} |"
        )

    # ── صفوف المراجع: خط الأساس (مقاس) + شريط الهدف (Gemini)
    if baseline:
        b_axes = baseline.get("axes") or {}
        b_cells = " | ".join(f"{b_axes.get(k, '—')}/{((axes_cfg.get(k) or {}).get('max'), '—')[0]}" for k in ("1", "2", "3", "4"))
        lines.append(
            f"| — | **{baseline.get('name', 'خط الأساس')}** | مرجع | {baseline.get('total', '—')} | "
            f"{baseline.get('total', '—')} | {baseline.get('verdict', '')} | "
            f"{trust_flag_for(baseline, axes_cfg) or '—'} | {b_cells} | "
            f"{'، '.join(baseline.get('gates') or []) or 'سليمة'} | — | — | — | — | — |"
        )
    if target:
        t_axes = target.get("axes") or {}
        t_cells = " | ".join(f"{t_axes.get(k, '—')}/{((axes_cfg.get(k) or {}).get('max'), '—')[0]}" for k in ("1", "2", "3", "4"))
        lines.append(
            f"| — | **🎯 {target.get('name', 'شريط الهدف')}** | هدف | {target.get('total', '—')} | "
            f"{target.get('total', '—')} | {target.get('verdict', '')} | — | {t_cells} | "
            f"{'، '.join(target.get('gates') or []) or 'سليمة'} | — | — | — | — | 0.00 | 0.0 |"
        )
        lines += [
            "",
            f"> **🎯 شريط الهدف ({target.get('name')}):** **{target.get('total')}/100** · "
            f"المصدر: **{target.get('note') or source_badge(target)}** · "
            "أرقامه **معايرة يدوية** (مش مقيسة آلياً) ⇒ بتظهر كـ«هدف» مش كـ«مقاس». "
            "**«المسافة عن الهدف»** = متوسط فرق النسبة على المحاور الأربعة (٠ = مطابق تماماً، الأقل = الأقرب).",
        ]
    if baseline:
        lines += [
            "",
            f"> **📏 خط الأساس للمقارنة ({baseline.get('name')}):** **{baseline.get('total')}/100** · "
            f"المصدر: **{baseline.get('note') or source_badge(baseline)}** · "
            "ده الموديل المرجعي **المقاس آلياً** بنفس المصحّح ⇒ المقارنة عليه صحيحة.",
        ]

    if any(
        (r.get("runtime") or {}).get("gpu_contention", {}).get("competing_processes")
        for r in results
    ):
        lines += [
            "",
            "> ⚠ **منافسة على الكارت:** وقت القياس كانت فيه عمليات استدلال تانية شغالة — "
            "السرعة المقيسة (tok/s) **أقل من الحقيقي**. أعد القياس بعد ما تقفل أي سيرفر تاني.",
        ]
    if any((r.get("exam") or {}).get("baseline") for r in results):
        lines += [
            "",
            "> **درجات المقارنة (baseline):** نفس الفحوص بدون عواقب البوابات وبدون عقوبة الطول — "
            "وهي المقياس اللي اتقاس بيه خط الأساس المنشور 61.6، فالمقارنة لازم تكون على العمود ده.",
        ]
    g5_scope = str(
        ((exam_cfg.get("settings") or {}).get("g5_reasoning_channel") or "visible")
    )
    lines += [
        "",
        f"> **سياسة G5:** `{g5_scope}` — "
        + (
            "وسوم <think> في الرد المرئي فقط (مطابق لورقة الامتحان §52). "
            "محتوى قناة reasoning_content المنفصلة يُسجَّل كملاحظة بدون عقوبة."
            if g5_scope == "visible"
            else "أي محتوى في قناة reasoning_content يُحتسب thinking (عقوبة −1/حالة)."
        ),
    ]
    reasoning_rows = [
        (r.get("model"), ((r.get("exam") or {}).get("reasoning_channel_questions") or []))
        for r in results
        if ((r.get("exam") or {}).get("reasoning_channel_questions"))
    ]
    if reasoning_rows:
        lines += [
            "",
            "### أسئلة استخدمت قناة تفكير منفصلة (لا تُحتسب ضمن G5)",
            "",
            "| الموديل | الأسئلة |",
            "|---|---|",
        ]
        for model, qids in reasoning_rows:
            lines.append(f"| `{model}` | {('، '.join(qids))} |")
    settings_rows = [
        (r.get("model"), r.get("settings") or {}) for r in results if r.get("settings")
    ]
    if settings_rows:
        lines += [
            "",
            "### الإعدادات الفعلية لكل موديل",
            "",
            "| الموديل | المصدر | القالب | KV | ngl | threads | device | flash-attn |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for model, st in settings_rows:
            rt = next((r.get("runtime") or {} for r in results if r.get("model") == model), {})
            lines.append(
                f"| `{model}` | {st.get('source') or '—'} | {st.get('chat_template') or '—'} | "
                f"{st.get('kv_cache_type') or rt.get('kv') or '—'} | "
                f"{st.get('n_gpu_layers') if st.get('n_gpu_layers') is not None else rt.get('ngl', '—')} | "
                f"{st.get('threads') if st.get('threads') is not None else rt.get('threads', '—')} | "
                f"{st.get('device') or rt.get('device') or '—'} | "
                f"{st.get('flash_attn') or rt.get('flash_attn') or '—'} |"
            )
    perf_rows = [
        (r.get("model"), (r.get("runtime") or {}).get("perf") or {}, r.get("fit") or {})
        for r in results
        if ((r.get("runtime") or {}).get("perf"))
    ]
    if perf_rows:
        lines += [
            "",
            "### الأداء المقيس فعلياً (مصدره llama.cpp timings — مش تقدير)",
            "",
            "| الموديل | توليد tok/s (متوسط) | معالجة prompt tok/s | أول استجابة ms | زمن الطلب s (متوسط) |",
            "|---|---|---|---|---|",
        ]
        for model, perf, fit in perf_rows:
            tg = perf.get("tg_tps") or {}
            pp = perf.get("pp_tps") or {}
            ttft = perf.get("ttft_ms") or {}
            req = perf.get("request_seconds") or {}
            lines.append(
                f"| `{model}` | {tg.get('avg', '—')} | {pp.get('avg', '—')} | "
                f"{ttft.get('avg', '—')} | {req.get('avg', '—')} |"
            )
    if baseline:
        lines += [
            "",
            f"**خط الأساس:** {baseline.get('name', '')} — **{baseline.get('total')}/100** · "
            f"{baseline.get('verdict', '')} · بوابات: {'، '.join(baseline.get('gates') or []) or 'سليمة'} · "
            f"المصدر: {baseline.get('note') or source_badge(baseline)}",
        ]
    if target:
        lines += [
            "",
            f"**🎯 شريط الهدف:** {target.get('name', '')} — **{target.get('total')}/100** · "
            f"{target.get('verdict', '')} · المصدر: {target.get('note') or source_badge(target)}",
        ]
    lines += [
        "",
        "> المخرجات: `exam-results.xlsx` (10 شيتات) · `exam-report.html` (تقرير مقارنة تفاعلي: كارت لكل موديل + رسم سداسي + رسوم مقارنة + جدول سرعة + سجل الإجابات) · `run.log`",
        "> التصحيح حتمي بالكامل — نفس الإجابات تعطي نفس الدرجات.",
    ]
    return "\n".join(lines) + "\n"


def _display_results(results: list[dict]) -> list[dict]:
    """نسخة **عرض** من النتائج: اسم الموديل مختصر + المسار الكامل محفوظ.

    الموديلات المحلية بتبقى مسارات طويلة (90+ حرف) ⇒ بتخنق جداول التقرير.
    هنا بنقصّرها لاسم الملف (`Qwen3.5-4B-IQ4_XS`) ونخزّن الأصل في `model_full`
    عشان يفضل متاح كـtooltip. **الأرقام ما تتغيّرش خالص.**
    """
    out: list[dict] = []
    for result in results or []:
        item = dict(result)
        full = str(item.get("model") or "")
        short = display_name(full)
        if short and short != full:
            item["model_full"] = full
            item["model"] = short
        out.append(item)
    return out


def _write_outputs(
    results: list[dict],
    exam_cfg: dict,
    run_meta: dict,
    out_dir: Path,
    logger: logging.Logger,
) -> None:
    display = _display_results(results)
    excel_path = write_workbook(display, out_dir / "exam-results.xlsx", exam_cfg, run_meta)
    html_path = write_report(display, out_dir / "exam-report.html", exam_cfg, run_meta)
    (out_dir / "summary.md").write_text(
        _summary_md(display, exam_cfg, run_meta), encoding="utf-8"
    )
    logger.info("checkpoint: %s · %s", excel_path.name, html_path.name)


def _result_ok(result: dict) -> bool:
    return result.get("status") == "ok" and bool(result.get("exam"))


def main() -> int:
    ap = argparse.ArgumentParser(description="تشغيل امتحان المساعد المصري على موديلات GGUF")
    ap.add_argument("--models", required=True, help="repo ids أو مسارات GGUF محلية، مفصولة بفاصلة")
    ap.add_argument("--quant", "--quant-pattern", dest="quant", default="Q4_K_M")
    ap.add_argument("--ctx", type=int, default=4096)
    ap.add_argument("--kv", default="", choices=["", "f16", "q8_0", "q4_0"], help="فاضي = من overrides/الافتراضي")
    ap.add_argument("--threads", type=int, default=0, help="0 = من overrides/الافتراضي")
    ap.add_argument("--ngl", type=int, default=None, help="مش محدد = القيمة المحسوبة من الملاءمة")
    ap.add_argument("--device-profile", default="config/device_profile.yaml")
    ap.add_argument("--server", default=".llama/bin/llama-server")
    ap.add_argument("--template", default="templates/qwen35_egyptian_nothink.jinja")
    ap.add_argument(
        "--template-mode",
        default="auto",
        choices=["auto", "exam", "model"],
        help="auto=قالب الامتحان (مقارنة عادلة) · exam=قالب الامتحان · model=القالب المدمج في GGUF",
    )
    ap.add_argument("--overrides", default="config/model_overrides.yaml", help="توصيات الموديلات")
    ap.add_argument(
        "--apply-recommended-sampling",
        action="store_true",
        help="يطبّق توصيات temperature/top_p/top_k من المطوّر (بيكسر الحتمية!)",
    )
    ap.add_argument(
        "--policy",
        default="paper",
        choices=["paper", "baseline"],
        help="paper=قواعد ورقة الامتحان كاملة · baseline=مطابق لخط الأساس المنشور 61.6",
    )
    ap.add_argument("--system-prompt", default="prompts/owner_system_prompt.txt")
    ap.add_argument("--exam", default="config/exam.yaml")
    ap.add_argument("--out", default="out")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--max-gib", type=float, default=10.0)
    ap.add_argument("--model-timeout", type=float, default=300.0, help="دقائق لكل موديل")
    ap.add_argument("--total-timeout", type=float, default=330.0, help="دقائق لكل التشغيل قبل الـ 6 ساعات")
    ap.add_argument("--request-timeout", type=float, default=900.0, help="ثواني لكل سؤال")
    ap.add_argument("--startup-timeout", type=float, default=900.0)
    ap.add_argument("--limit", type=int, default=0, help="حد أسئلة للتجربة السريعة (0 = الكل)")
    ap.add_argument("--device", default="", help="device للـ offload (مثال: Vulkan0، CUDA0)")
    ap.add_argument("--flash-attn", default="", choices=["", "on", "off", "auto"])
    ap.add_argument("--extra-server-args", default="", help="أعلام llama-server إضافية مفصولة بمسافات")
    ap.add_argument("--keep-models", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    out_dir = repo_path(args.out)
    logger = _setup_logger(out_dir)

    exam_cfg = load_exam_from(args.exam)
    settings = exam_cfg.get("settings") or {}
    fixed_ctx = int(settings.get("ctx_size", 4096))
    if args.ctx != fixed_ctx:
        logger.error(
            "ctx_size=%s مرفوض: ورقة الامتحان ثابتة على %s. "
            "أي قيمة مختلفة تلغي قابلية المقارنة بين الموديلات.",
            args.ctx,
            fixed_ctx,
        )
        return 2

    models = _split_models(args.models)
    if not models:
        logger.error("قائمة الموديلات فاضية.")
        return 2

    server_path = repo_path(args.server)
    template_path = repo_path(args.template)
    prompt_path = repo_path(args.system_prompt)
    if not args.dry_run:
        for path, label in (
            (server_path, "llama-server"),
            (template_path, "القالب"),
            (prompt_path, "الـ system prompt"),
        ):
            if not path.exists():
                logger.error("%s مش موجود: %s", label, path)
                return 2

    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S")
    extra_args = args.extra_server_args.split() if args.extra_server_args else []
    overrides = load_overrides(args.overrides)
    run_meta: dict[str, Any] = {
        "run_id": run_id,
        "started_at": now_iso(),
        "finished_at": "",
        "models_input": ", ".join(models),
        "quant_pattern": args.quant,
        "ctx": args.ctx,
        "kv": args.kv or "auto",
        "threads": args.threads or "auto",
        "ngl": args.ngl if args.ngl is not None else "auto",
        "device": args.device,
        "flash_attn": args.flash_attn,
        "extra_server_args": " ".join(extra_args),
        "device_profile": args.device_profile,
        "template": args.template,
        "template_mode": args.template_mode,
        "overrides": args.overrides,
        "policy": args.policy,
        "apply_recommended_sampling": bool(args.apply_recommended_sampling),
        "system_prompt": args.system_prompt,
        "mode": "llama-server /v1/chat/completions",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "exam_version": exam_cfg.get("version"),
        "out_dir": str(out_dir),
    }

    logger.info(
        "run_id=%s · models=%d · quant=%s · ctx=%s · policy=%s · template-mode=%s",
        run_id,
        len(models),
        args.quant,
        args.ctx,
        args.policy,
        args.template_mode,
    )
    logger.info("template=%s · prompt=%s", template_path, prompt_path)
    if args.dry_run:
        for model in models:
            logger.info("DRY · %s", model)
        return 0

    results: list[dict] = []
    overall_deadline = time.monotonic() + args.total_timeout * 60.0
    for index, model in enumerate(models, 1):
        logger.info("═" * 72)
        logger.info("[%d/%d] %s", index, len(models), model)
        remaining_min = (overall_deadline - time.monotonic()) / 60.0
        if remaining_min < 5:
            logger.error("انتهى وقت التشغيل الكلي (%.0f دقيقة) قبل الموديل ده.", args.total_timeout)
            results.append(
                {
                    "status": "failed",
                    "model": model,
                    "manifest": {},
                    "fit": {},
                    "runtime": {},
                    "exam": None,
                    "error": f"انتهى وقت التشغيل الكلي ({args.total_timeout:.0f} دقيقة)",
                    "started_at": now_iso(),
                    "finished_at": now_iso(),
                    "seconds": 0.0,
                }
            )
            continue
        model_timeout_min = min(args.model_timeout, max(1.0, remaining_min - 2.0))
        logger.info("مهلة الموديل: %.1f دقيقة (المتبقي من الكلي: %.1f)", model_timeout_min, remaining_min)
        manifest: dict = {}
        fit: dict = {}
        runtime: dict = {}
        ms = None
        started = now_iso()
        t0 = time.monotonic()
        try:
            local = Path(model)
            if local.exists() and local.is_file():
                manifest = _local_manifest(local)
                logger.info("موديل محلي: %s (%s)", local, human_bytes(manifest["total_bytes"]))
            else:
                manifest = resolve_and_download(
                    model,
                    args.quant,
                    revision="main",
                    token=os.environ.get("HF_TOKEN") or None,
                    out_dir=out_dir / "models",
                    max_gib=args.max_gib,
                )
                logger.info(
                    "نُزّل: %s · %s · %d ملف/ملفات",
                    Path(manifest["primary_path"]).name,
                    human_bytes(manifest["total_bytes"]),
                    len(manifest["files"]),
                )

            # ── الإعدادات الفعلية للموديل (overrides + توصيات تلقائية)
            gen_cfg: dict = {}
            if not (manifest.get("is_local")):
                try:
                    gen_cfg = generation_config(
                        model, "main", os.environ.get("HF_TOKEN") or None
                    )
                except Exception:
                    gen_cfg = {}
            ms = resolve_model_settings(
                model,
                overrides=overrides,
                exam_template=args.template,
                template_mode=args.template_mode,
                gguf_path=manifest["primary_path"],
                generation_config=gen_cfg,
                cli={
                    "kv": args.kv,
                    "threads": args.threads or None,
                    "ngl": args.ngl,
                    "device": args.device,
                    "flash_attn": args.flash_attn,
                    "extra_server_args": extra_args,
                },
                write_template_dir=out_dir / "templates",
            )
            eff_kv = ms.kv_cache_type or "f16"
            eff_threads = int(ms.threads or args.threads or 4)
            eff_device = ms.device
            eff_flash = ms.flash_attn
            eff_extra = list(ms.extra_server_args)
            eff_template = repo_path(ms.chat_template)
            if not eff_template.exists():
                eff_template = template_path
                logger.warning("قالب الموديل %s مش موجود — استُخدم قالب الامتحان.", ms.chat_template)

            fit = analyze_fit(
                manifest["primary_path"],
                profile_path=args.device_profile,
                ctx=args.ctx,
                kv=eff_kv,
            )
            eff_ngl = ms.n_gpu_layers
            if eff_ngl is None:
                eff_ngl = args.ngl if args.ngl is not None else int(fit.get("ngl") or 0)
            logger.info(
                "fit=%s · ngl=%s/%s · KV=%s GiB · tg=%s tok/s",
                fit.get("fit_class"),
                fit.get("ngl"),
                fit.get("n_layers"),
                fit.get("kv_total_gib"),
                fit.get("tg_tps"),
            )
            logger.info("الإعدادات المطبّقة [%s]: %s", ms.matched_key or ms.source, " · ".join(ms.applied))
            for warning in ms.warnings:
                logger.warning("تنبيه: %s", warning)

            # ── إعدادات التوليد: ثابتة للامتحان، إلا لو طلب المستخدم تطبيق التوصيات
            run_settings = dict(settings)
            if args.apply_recommended_sampling and ms.recommended_sampling:
                for key in ("temperature", "top_p", "top_k", "min_p", "repeat_penalty"):
                    value = ms.recommended_sampling.get(key)
                    if value is not None:
                        run_settings[key] = value
                logger.warning(
                    "تم تطبيق توصيات التوليد (%s) — التصحيح مش حتمي بعد كده!",
                    ", ".join(f"{k}={v}" for k, v in ms.recommended_sampling.items()),
                )

            run = run_exam(
                gguf_path=manifest["primary_path"],
                server_bin=server_path,
                template_path=eff_template,
                system_prompt_path=prompt_path,
                questions=exam_cfg["questions"],
                settings=run_settings,
                out_dir=out_dir,
                slug=slugify(model.replace("/", "__")),
                ctx=args.ctx,
                threads=eff_threads,
                kv=eff_kv,
                ngl=eff_ngl,
                startup_timeout=args.startup_timeout,
                request_timeout=args.request_timeout,
                model_timeout=model_timeout_min * 60.0,
                limit=args.limit,
                device=eff_device,
                flash_attn=eff_flash,
                extra_args=eff_extra,
            )
            runtime = run["runtime"]
            logger.info(
                "انتهى التشغيل: %ss · peak RSS %s MiB · %s",
                runtime.get("seconds_total"),
                runtime.get("peak_rss_mib"),
                runtime.get("fatal_error") or "سليم",
            )
            exam = grade_exam(
                run["answers"],
                exam_cfg,
                model_meta={**manifest, "run_id": run_id},
                policy=args.policy,
            )
            logger.info(
                "النتيجة: %s/100 · %s · بوابات: %s",
                exam.get("total"),
                exam.get("verdict"),
                "، ".join(g["code"] for g in exam.get("gates", []) if g.get("fired")) or "سليمة",
            )
            result = {
                "status": "ok",
                "model": model,
                "manifest": manifest,
                "fit": fit,
                "runtime": runtime,
                "exam": exam,
                "settings": ms.to_dict() if ms else {},
                "error": "",
                "started_at": started,
                "finished_at": now_iso(),
                "seconds": round(time.monotonic() - t0, 1),
            }
        except (HFError, FileNotFoundError, RuntimeError, ValueError) as exc:
            logger.error("فشل الموديل: %s: %s", type(exc).__name__, exc)
            result = {
                "status": "failed",
                "model": model,
                "manifest": manifest,
                "fit": fit,
                "runtime": runtime,
                "exam": None,
                "settings": ms.to_dict() if ms else {},
                "error": f"{type(exc).__name__}: {exc}",
                "started_at": started,
                "finished_at": now_iso(),
                "seconds": round(time.monotonic() - t0, 1),
            }
        except Exception as exc:  # pragma: no cover - أمان
            logger.error("خطأ غير متوقع: %s: %s", type(exc).__name__, exc)
            logger.error(traceback.format_exc())
            result = {
                "status": "failed",
                "model": model,
                "manifest": manifest,
                "fit": fit,
                "runtime": runtime,
                "exam": None,
                "error": f"{type(exc).__name__}: {exc}",
                "started_at": started,
                "finished_at": now_iso(),
                "seconds": round(time.monotonic() - t0, 1),
            }

        results.append(result)
        try:
            _write_outputs(results, exam_cfg, {**run_meta, "finished_at": now_iso()}, out_dir, logger)
        except Exception as exc:  # pragma: no cover
            logger.error("فشل كتابة التقارير المؤقتة: %s: %s", type(exc).__name__, exc)

        if not args.keep_models and not (manifest or {}).get("is_local"):
            cleanup_model(manifest)
            logger.info("تم حذف ملفات الموديل من الـ runner.")

    run_meta["finished_at"] = now_iso()
    _write_outputs(results, exam_cfg, run_meta, out_dir, logger)

    ok = [r for r in results if _result_ok(r)]
    logger.info("═" * 72)
    logger.info("الخلاصة: %d/%d موديل مكتمل · التقرير: %s", len(ok), len(results), out_dir / "exam-report.html")
    for result in ok:
        exam = result["exam"]
        logger.info(
            "  %-48s %6.2f/100  %s  (%s)",
            result["model"],
            exam["total"],
            exam["verdict"],
            "، ".join(g["code"] for g in exam["gates"] if g["fired"]) or "سليمة",
        )
    if not ok:
        logger.error("كل الموديلات فشلت — راجع run.log.")
        return 1
    return 0


def load_exam_from(path: str | Path) -> dict:
    from common import load_yaml

    return load_yaml(path)


if __name__ == "__main__":
    raise SystemExit(main())
