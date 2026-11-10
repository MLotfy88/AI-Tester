"""أداة دمج تقارير الامتحان — **مستقلة تماماً** عن الأداة الأصلية.

بتاخد أكتر من تقرير HTML (كل واحد ناتج عن تشغيل مستقل) وتدمجهم في:
  - تقرير HTML واحد فيه كل الموديلات (بتصميم «مِحْيَر»).
  - ملف Excel واحد فيه كل الموديلات.

الاستخدام:
    python merge/merge_reports.py run1/exam-report.html run2/exam-report.html -o merged/

مجلد `merge/` مستقل: **مش بيعدّل** ولا بيستورد أي حاجة من `scripts/`.
كل الأصول (CSS/JS/القالب) نسخة محلية في `merge/assets/`.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # استيراد الموديولات المحلية (excel_merge)
ASSETS = HERE / "assets"
TEMPLATE = ASSETS / "template.html"
CSS_FILE = ASSETS / "style.css"
JS_DIR = ASSETS / "js"

#: ألوان الموديلات (نفس `assets/js/01-core.js`) — 8 ألوان مميزة + احتياطي.
COLORS = [
    "#5AA9FF", "#35D6C0", "#A78BFA", "#FF8FA3",
    "#6EE7B7", "#F5C45E", "#38BDF8", "#E879F9",
    "#94A3B8", "#FACC15",
]

#: regexpPulling the payload out of the report HTML (the new and old formats).
PAYLOAD_RE = re.compile(
    r'<script[^>]*id="(payload|exam-data)"[^>]*>(.*?)</script>', re.S
)


# ═════════════════════════════════════════════════════════ helpers
def esc(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def extract_payload(path: pathlib.Path) -> tuple[dict, str]:
    """بيستخرج الـ payload من تقرير HTML — بيدعم الصيغة الجديدة والقديمة."""
    text = path.read_text(encoding="utf-8")
    m = PAYLOAD_RE.search(text)
    if not m:
        raise SystemExit(f"❌ مفيش payload في التقرير: {path}")
    fmt = "new" if m.group(1) == "payload" else "old"
    return json.loads(m.group(2)), fmt


def _trim_questions(rows: dict | None) -> dict:
    out: dict[str, dict] = {}
    for qid, r in (rows or {}).items():
        r = r or {}
        out[str(qid)] = {
            "id": str(qid),
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


def _trim_profile(prof: dict | None) -> dict:
    prof = prof or {}
    return {
        "total": prof.get("total") or 0,
        "max": prof.get("max") or 20,
        "percent": prof.get("percent") or 0,
        "count": prof.get("count") or 0,
        "answered": prof.get("answered") or 0,
        "note": prof.get("note") or "",
        "questions": {
            str(pid): {
                "id": str(pid),
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


def model_from_old(raw: dict) -> dict:
    """يحوّل موديل من الصيغة القديمة (كاملة) للصيغة الجديدة (مقلّمة)."""
    ex = raw.get("exam") or {}
    rt = raw.get("runtime") or {}
    perf = rt.get("perf") or {}
    fit = raw.get("fit") or {}
    manifest = raw.get("manifest") or {}
    status = str(raw.get("status") or "ok")

    cats: dict[str, dict] = {}
    for key, c in (ex.get("categories") or {}).items():
        c = c or {}
        cats[str(key)] = {
            "percent": c.get("percent") or 0,
            "points": c.get("points") or 0,
            "score": c.get("score") or 0,
            "max": c.get("max") or 0,
            "failed_min": bool(c.get("failed_min")),
        }

    tg = perf.get("tg_tps") or {}
    pp = perf.get("pp_tps") or {}
    req = perf.get("request_seconds") or {}
    pms = perf.get("prompt_ms") or {}

    return {
        "key": "",
        "name": raw.get("model") or "—",
        "full": raw.get("model_full") or raw.get("model") or "",
        "repo": manifest.get("repo") or "",
        "sha": (manifest.get("sha") or "")[:8],
        "license": manifest.get("license") or "",
        "quant": manifest.get("quant_chosen") or "",
        "bytes": manifest.get("total_bytes") or 0,
        "color": "",
        "status": status,
        "error": str(raw.get("error") or "") if status != "ok" else "",
        "total": ex.get("total") or 0,
        "max": ex.get("max") or 100,
        "verdict": ex.get("verdict") or ("" if status == "ok" else "فشل"),
        "verdict_note": ex.get("verdict_note") or "",
        "failed_categories": ex.get("failed_categories") or [],
        "cats": cats,
        "questions": _trim_questions(ex.get("questions") or {}),
        "profile": _trim_profile(ex.get("profile") or {}),
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
            "device": rt.get("device") or "",
            "gpu": rt.get("gpu_name") or "",
            "llama_version": rt.get("llama_version") or "",
        },
    }


def _cfg_from_old(data: dict) -> dict:
    """يبني `cfg` من تقرير بالصيغة القديمة."""
    exam = data.get("exam") or {}
    cats = {}
    for k, c in (exam.get("categories") or {}).items():
        c = c or {}
        cats[str(k)] = {
            "name": str(c.get("name") or k),
            "short": str(c.get("short") or c.get("name") or k),
            "weight": c.get("weight") or 0,
            "min_percent": c.get("min_percent") or 0,
            "questions": c.get("questions") or [],
        }
    gem = (exam.get("references") or {}).get("gemini") or {}
    axes = {}
    total = 0.0
    for k, row in (gem.get("axes") or {}).items():
        row = row or {}
        value = row.get("value") or 0
        axes[str(k)] = {"value": value, "why": row.get("why") or ""}
        total += float(value or 0) * float((cats.get(str(k)) or {}).get("weight") or 0)
    return {
        "version": exam.get("version") or "",
        "settings": exam.get("settings") or {},
        "categories": cats,
        "gemini": {
            "name": gem.get("name") or "Gemini 2.5 Pro",
            "note": gem.get("note") or "",
            "source_model": gem.get("source_model") or "",
            "source_date": gem.get("source_date") or "",
            "axes": axes,
        },
        "profile_count": 14,
    }


def _ref_from_old(data: dict, cfg: dict) -> dict:
    gem = (data.get("exam") or {}).get("references", {}).get("gemini") or {}
    axes = {k: v["value"] for k, v in (cfg.get("gemini", {}).get("axes") or {}).items()}
    total = sum(
        float(v or 0) * float((cfg["categories"].get(k) or {}).get("weight") or 0)
        for k, v in axes.items()
    )
    return {
        "name": gem.get("name") or "Gemini 2.5 Pro",
        "total": round(total / 100.0, 2),
        "color": "#9BB0D4",
        "axes": axes,
        "note": gem.get("note") or "",
        "source": gem.get("source_model") or "",
        "source_date": gem.get("source_date") or "",
        "kind": gem.get("kind") or "display_only",
    }


# ═════════════════════════════════════════════════════════ merge payload
def merge_payloads(inputs: list[tuple[dict, str]]) -> dict:
    """يدمج الـ payloads في payload واحد بصيغة التصميم."""
    models: list[dict] = []
    seen: set[str] = set()
    for data, fmt in inputs:
        for raw in data.get("models") or []:
            m = dict(raw) if fmt == "new" else model_from_old(raw)
            name = str(m.get("name") or "")
            if name and name in seen:
                print(f"   ⚠️ موديل مكرر اتجاهل: {name}")
                continue
            seen.add(name)
            m["key"] = f"m{len(models)}"
            m["color"] = COLORS[len(models) % len(COLORS)]
            models.append(m)

    first = inputs[0][0]
    cfg = first.get("cfg") or _cfg_from_old(first)
    ref = first.get("ref") or _ref_from_old(first, cfg)

    runs = [d.get("run") or {} for d, _ in inputs]
    settings = cfg.get("settings") or {}
    ids, starts, ends = [], [], []
    for r in runs:
        rid = str(r.get("run_id") or "")
        if rid and rid not in ids:
            ids.append(rid)
        if r.get("started_at"):
            starts.append(str(r["started_at"]))
        if r.get("finished_at"):
            ends.append(str(r["finished_at"]))

    def _sum(key: str) -> float:
        total = 0.0
        for r in runs:
            value = r.get(key)
            if isinstance(value, (int, float)):
                total += float(value)
        return round(total, 2)

    run = {
        "run_id": " + ".join(ids) or "—",
        "started_at": min(starts) if starts else "",
        "finished_at": max(ends) if ends else "",
        "runner_label": first.get("runner_label") or "",
        "runner_gpu": first.get("runner_gpu") or "",
        "runner_kind": first.get("runner_kind") or "",
        "platform": first.get("platform") or "—",
        "llama_version": first.get("llama_version") or "",
        "temperature": settings.get("temperature"),
        "top_p": settings.get("top_p"),
        "seed": settings.get("seed"),
        "ctx": first.get("ctx") or settings.get("ctx_size"),
        "quant": first.get("quant") or first.get("quant_pattern") or "",
        "exam_version": first.get("exam_version") or cfg.get("version") or "",
        "device": first.get("device") or "",
        "gpu": first.get("gpu") or first.get("runner_gpu") or "",
        "requests_count": int(_sum("requests_count")),
        "seconds_total": _sum("seconds_total"),
    }

    return {"run": run, "cfg": cfg, "models": models, "ref": ref}


def build_html(data: dict, out_path: pathlib.Path) -> pathlib.Path:
    """يبني التقرير المدمج (HTML واحد مستقل) من الأصول المحلية."""
    css = CSS_FILE.read_text(encoding="utf-8")
    js = "\n\n".join(p.read_text(encoding="utf-8") for p in sorted(JS_DIR.glob("*.js")))
    tpl = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    html = (
        tpl.replace("__CSS__", css)
        .replace("__JS__", js)
        .replace("__DATA__", payload)
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


# ═════════════════════════════════════════════════════════ merge Excel
#: منطق الدمج lives in ``merge/excel_merge.py`` — مستقل تماماً عن الأداة الأصلية.
from excel_merge import merge_workbooks  # noqa: E402


# ═════════════════════════════════════════════════════════ CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="دمج أكتر من تقرير امتحان في تقرير HTML + Excel واحد."
    )
    ap.add_argument("reports", nargs="+", type=pathlib.Path, help="تقارير HTML")
    ap.add_argument("-o", "--out", type=pathlib.Path, default=pathlib.Path("merged"))
    ap.add_argument("--no-excel", action="store_true", help="متعملش Excel")
    ap.add_argument(
        "--xlsx", nargs="*", type=pathlib.Path, default=None,
        help="ملفات Excel (بالافتراضي: البحث بجانب كل تقرير)",
    )
    args = ap.parse_args(argv)

    inputs = []
    for path in args.reports:
        if not path.exists():
            print(f"❌ الملف مش موجود: {path}")
            return 1
        data, fmt = extract_payload(path)
        inputs.append((data, fmt))
        print(f"📄 {path.name} — {len(data.get('models') or [])} موديل ({fmt})")

    merged = merge_payloads(inputs)
    print(f"\n✅ بعد الدمج: {len(merged['models'])} موديل")

    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "exam-report-merged.html"
    build_html(merged, html_path)
    print(f"📄 HTML -> {html_path} ({html_path.stat().st_size:,} bytes)")

    if not args.no_excel:
        xlsx_paths = args.xlsx or [
            p.parent / "exam-results.xlsx" for p in args.reports
        ]
        xlsx_paths = [p for p in xlsx_paths if p.exists()]
        if len(xlsx_paths) < len(args.reports):
            print("⚠️ مفيش Excel لكل تقرير — هندمج الموجود بس")
        if xlsx_paths:
            xlsx_out = out_dir / "exam-results-merged.xlsx"
            merge_workbooks(
                xlsx_paths,
                xlsx_out,
                ref_total=merged.get("ref", {}).get("total"),
                model_count=len(merged["models"]),
            )
            print(f"📊 Excel -> {xlsx_out}")

    print("\n🎉 خلص — افتح الـ HTML في المتصفح")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
