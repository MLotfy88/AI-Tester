"""بناء تقرير HTML بتصميم «مِحْيَر» من بيانات آخر نتيجة Kaggle.

المخرج: ملف HTML واحد مستقل (CSS + JS + data مدمجة) — بيشتغل Offline.
⚠ ما بيلمسش التصميم الحالي في scripts/ خالص — ده نموذج مستقل.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(r"F:\App-Projects\hermes-assistant\AI Online Tester")
DESIGN = ROOT / "design-preview"
TPL = DESIGN / "template.html"
CSS = DESIGN / "assets" / "style.css"
JS_DIR = DESIGN / "assets" / "js"
OUT = DESIGN / "exam-report-v2.html"

PAYLOAD = Path(
    r"C:\Users\MLotfy\AppData\Local\Temp\opencode\kaggle427_payload.json"
)

COLORS = ["#5AA9FF", "#35D6C0", "#A78BFA", "#FF8FA3", "#6EE7B7", "#F5C45E"]


# ═══════════════════════════════════════ trim
def trim_questions(rows: dict) -> dict:
    out = {}
    for qid, r in (rows or {}).items():
        out[qid] = {
            "id": qid,
            "title": r.get("title") or "",
            "prompt": r.get("prompt") or "",
            "why": r.get("why") or "",
            "category": r.get("category") or "",
            "category_name": r.get("category_name") or "",
            "score": r.get("score") or 0,
            "max": r.get("max") or 10,
            "percent": r.get("percent") or 0,
            "passes": r.get("passes") or 1,
            "answer": r.get("answer") or "",
            "chars": r.get("chars") or 0,
            "tokens": r.get("tokens") or 0,
            "seconds": r.get("seconds") or 0,
            "finish": r.get("finish") or "",
            "empty": bool(r.get("empty")),
            "health": r.get("health") or [],
            "criteria": [
                {
                    "label": c.get("label") or "",
                    "points": c.get("points") or 0,
                    "max": c.get("max") or 2,
                    "note": c.get("note") or "",
                }
                for c in (r.get("criteria") or [])
            ],
        }
    return out


def trim_profile(prof: dict) -> dict:
    prof = prof or {}
    return {
        "total": prof.get("total") or 0,
        "max": prof.get("max") or 20,
        "percent": prof.get("percent") or 0,
        "count": prof.get("count") or 0,
        "answered": prof.get("answered") or 0,
        "note": prof.get("note") or "",
        "questions": {
            pid: {
                "id": pid,
                "domain": q.get("domain") or "",
                "prompt": q.get("prompt") or "",
                "expected": q.get("expected") or "",
                "answer": q.get("answer") or "",
                "score": q.get("score") or 0,
                "max": q.get("max") or 20,
                "percent": q.get("percent") or 0,
                "answered": bool(q.get("answered")),
                "criteria": [
                    {
                        "label": c.get("label") or "",
                        "points": c.get("points") or 0,
                        "max": c.get("max") or 5,
                        "note": c.get("note") or "",
                    }
                    for c in (q.get("criteria") or [])
                ],
            }
            for pid, q in (prof.get("questions") or {}).items()
        },
    }


def build_data() -> dict:
    raw = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    run = raw.get("run") or {}
    cfg_raw = raw.get("exam") or {}

    categories = {}
    for k, c in (cfg_raw.get("categories") or {}).items():
        categories[k] = {
            "name": c.get("name") or k,
            "short": c.get("short") or c.get("name") or k,
            "weight": c.get("weight") or 0,
            "min_percent": c.get("min_percent") or 0,
            "questions": c.get("questions") or [],
        }

    gem = (cfg_raw.get("references") or {}).get("gemini") or {}

    # درجة المرجع = مجموع (نسبة المحور × وزنه) — نفس طريقة المجموع الأساسي
    ref_total = 0.0
    for k, v in (gem.get("axes") or {}).items():
        val = (v or {}).get("value") or 0
        w = (categories.get(k) or {}).get("weight") or 0
        ref_total += val * w
    ref_total = round(ref_total / 100.0, 2)

    gemini = {
        "name": gem.get("name") or "Gemini 2.5 Pro",
        "note": gem.get("note") or "",
        "source_model": gem.get("source_model") or "",
        "source_date": gem.get("source_date") or "",
        "axes": {
            k: {"value": (v or {}).get("value") or 0, "why": (v or {}).get("why") or ""}
            for k, v in (gem.get("axes") or {}).items()
        },
    }

    reference = {
        "name": gem.get("name") or "Gemini 2.5 Pro",
        "total": ref_total,
        "color": "#9BB0D4",
        "axes": {k: (v or {}).get("value") or 0 for k, v in (gem.get("axes") or {}).items()},
        "note": gem.get("note") or "",
        "source": gem.get("source_model") or "",
        "source_date": gem.get("source_date") or "",
        "kind": gem.get("kind") or "",
    }

    models = []
    for i, m in enumerate(raw.get("models") or []):
        ex = m.get("exam") or {}
        rt = m.get("runtime") or {}
        perf = rt.get("perf") or {}
        fit = m.get("fit") or {}
        manifest = m.get("manifest") or {}
        tg = perf.get("tg_tps") or {}
        pp = perf.get("pp_tps") or {}
        req = perf.get("request_seconds") or {}
        pms = perf.get("prompt_ms") or {}

        cats = {}
        for k, c in (ex.get("categories") or {}).items():
            cats[k] = {
                "percent": c.get("percent") or 0,
                "points": c.get("points") or 0,
                "score": c.get("score") or 0,
                "max": c.get("max") or 0,
                "failed_min": bool(c.get("failed_min")),
            }

        models.append(
            {
                "key": f"m{i}",
                "name": m.get("model") or "—",
                "full": m.get("model_full") or m.get("model") or "",
                "repo": manifest.get("repo") or "",
                "sha": (manifest.get("sha") or "")[:8],
                "license": manifest.get("license") or "",
                "quant": manifest.get("quant_chosen") or "",
                "bytes": manifest.get("total_bytes") or 0,
                "color": COLORS[i % len(COLORS)],
                "total": ex.get("total") or 0,
                "max": ex.get("max") or 100,
                "verdict": ex.get("verdict") or "",
                "verdict_note": ex.get("verdict_note") or "",
                "failed_categories": ex.get("failed_categories") or [],
                "cats": cats,
                "questions": trim_questions(ex.get("questions") or {}),
                "profile": trim_profile(ex.get("profile") or {}),
                "fit": {
                    "ngl": fit.get("ngl"),
                    "layers": fit.get("n_layers"),
                    "kv": fit.get("kv") or rt.get("kv"),
                    "ctx": fit.get("ctx") or rt.get("ctx"),
                    "threads": fit.get("threads") or rt.get("threads"),
                    "fit_class": fit.get("fit_class") or "",
                },
                "perf": {
                    "tg_avg": tg.get("avg"),
                    "tg_max": tg.get("max"),
                    "pp_avg": pp.get("avg"),
                    "req_avg": req.get("avg"),
                    "req_p95": req.get("p95"),
                    "prompt_ms_avg": pms.get("avg"),
                    "startup": perf.get("startup_seconds"),
                    "generated": perf.get("total_generated_tokens"),
                    "requests": perf.get("requests_count"),
                },
                "runtime": {
                    "seconds_total": rt.get("seconds_total"),
                    "peak_rss_mib": (rt.get("memory") or {}).get("peak_rss_mib"),
                    "peak_vram_mib": (rt.get("memory") or {}).get("peak_vram_mib"),
                    "gpu": rt.get("gpu_name") or "",
                    "llama_version": rt.get("llama_version") or "",
                },
            }
        )

    return {
        "run": {
            "run_id": run.get("run_id") or "",
            "started_at": run.get("started_at") or "",
            "finished_at": run.get("finished_at") or "",
            "runner_label": run.get("runner_label") or "",
            "runner_gpu": run.get("runner_gpu") or "",
            "runner_kind": run.get("runner_kind") or "",
            "platform": run.get("platform") or "",
            "llama_version": run.get("llama_version") or "",
            "temperature": run.get("temperature"),
            "top_p": run.get("top_p"),
            "seed": run.get("seed"),
            "ctx": run.get("ctx"),
            "quant": run.get("quant_pattern") or "",
            "requests_count": (models[0].get("perf") or {}).get("requests"),
            "seconds_total": sum((mm.get("runtime") or {}).get("seconds_total") or 0 for mm in models),
            "exam_version": run.get("exam_version") or "",
        },
        "cfg": {
            "version": cfg_raw.get("version") or "",
            "settings": cfg_raw.get("settings") or {},
            "categories": categories,
            "gemini": gemini,
            "profile_count": 14,
        },
        "models": models,
        "ref": reference,
    }


# ═══════════════════════════════════════ build
def main() -> int:
    data = build_data()

    css = CSS.read_text(encoding="utf-8")
    js_parts = sorted(JS_DIR.glob("*.js"))
    js = "\n\n".join(p.read_text(encoding="utf-8") for p in js_parts)

    tpl = TPL.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")

    html = (
        tpl.replace("__CSS__", css)
        .replace("__JS__", js)
        .replace("__DATA__", payload)
    )
    OUT.write_text(html, encoding="utf-8")

    print(f"✅ {OUT}")
    print(f"   الحجم: {OUT.stat().st_size:,} bytes")
    print(f"   CSS: {len(css):,} · JS: {len(js):,} ({len(js_parts)} ملفات) · DATA: {len(payload):,}")
    print(f"   الموديلات: {len(data['models'])} · الأسئلة: "
          f"{sum(len(m['questions']) for m in data['models'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
