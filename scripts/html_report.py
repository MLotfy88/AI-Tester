"""تقرير HTML عربي مستقل (RTL) — مقارنة مباشرة بين الموديلات.

- ملف واحد بدون أي CDN أو اعتماد خارجي.
- كل الجداول والإجابات مبنية من نتائج التشغيل في الذاكرة.
- JavaScript اختياري للفلترة والتبويب والوضع الفاتح؛ الصفحة مقروءة بدونه.
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from common import dump_json_for_html, fmt_num, human_bytes, now_iso
from html_charts import (
    GEM_CLASS,
    charts_section,
    model_cards_section,
    radar_section,
    settings_section,
    speed_table_section,
    transcripts_section,
)
from references import (
    category_short,
    gemini_gap,
    gemini_ranking,
    gemini_reference,
    gemini_total,
    gemini_values,
    infer_runner_meta,
    measured_on_gpu,
    runner_kind,
    runner_label,
    source_badge,
)

# --------------------------------------------------------------------------- أدوات
def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _pct(score: Any, maximum: Any) -> float | None:
    try:
        if maximum is None or float(maximum) == 0:
            return None
        return max(0.0, min(100.0, 100.0 * float(score) / float(maximum)))
    except (TypeError, ValueError):
        return None


def _heat_style(pct: float | None) -> str:
    if pct is None:
        return "background:rgba(148,163,184,.08);color:var(--dim)"
    hue = max(0.0, min(120.0, pct * 1.2))
    return f"background:hsla({hue:.0f},72%,38%,.82);color:#fff"


def _bar(pct: float | None, *, small: bool = False) -> str:
    width = 0.0 if pct is None else pct
    cls = "bar sm" if small else "bar"
    return f'<div class="{cls}"><i style="width:{width:.1f}%"></i></div>'


def _score_cell(score: Any, maximum: Any, *, bar: bool = True) -> str:
    pct = _pct(score, maximum)
    value = f'<b>{esc(fmt_num(score, 2))}</b><span class="mut">/{esc(fmt_num(maximum, 0))}</span>'
    if not bar:
        return f'<span class="num" dir="ltr">{value}</span>'
    return f'<div class="score-cell"><span class="num" dir="ltr">{value}</span>{_bar(pct, small=True)}</div>'


def _verdict_class(verdict: Any, status: Any = "") -> str:
    text = str(verdict or "")
    if status == "failed":
        return "v-fail"
    if "جاهز" in text:
        return "v-ready"
    if "ممتاز" in text:
        return "v-good"
    if "مقبول" in text:
        return "v-ok"
    if "ضعيف" in text:
        return "v-weak"
    if "مرفوض" in text or "خطير" in text or "غير موثوق" in text:
        return "v-bad"
    return "v-na"


def _fit_class(value: Any) -> str:
    text = str(value or "")
    if text == "Full GPU":
        return "v-good"
    if text in ("Partial", "Mostly CPU"):
        return "v-ok"
    if text in ("No fit", "Unknown"):
        return "v-bad"
    return "v-na"


def _safe_text(value: Any, limit: int = 0) -> str:
    text = "" if value is None else str(value)
    if limit and len(text) > limit:
        text = text[:limit] + "…"
    return esc(text)


def _short_name(name: Any, limit: int = 30) -> str:
    """اسم موديل مختصر: آخر جزء من المسار + قصّ."""
    text = str(name or "").replace("\\", "/").rsplit("/", 1)[-1]
    if len(text) > limit:
        text = text[:limit] + "…"
    return esc(text)


# --------------------------------------------------------------------------- أدوات
def _cat_short(exam_cfg: dict, key: str) -> str:
    """اسم المحور المختصر (للجداول والرسوم)."""
    return category_short(exam_cfg, key)


def _gate_badges(exam: dict | None) -> str:
    """شارات حدود الدنيا لكل محور — الحمراء = محور تحت الحد (فشل حرج)."""
    if not exam:
        return '<span class="pill muted">—</span>'
    chips = []
    for gate in exam.get("gates") or []:
        code = str(gate.get("code", ""))
        fired = bool(gate.get("fired"))
        title = f"{code} · {gate.get('title', '')} · {gate.get('detail', '')}"
        chips.append(
            f'<span class="gate {"on" if fired else "off"}" title="{esc(title)}">'
            f'{esc(code)}{" ●" if fired else ""}</span>'
        )
    return "".join(chips)


def _ok_models(results: list[dict]) -> list[dict]:
    return [r for r in results if r.get("status") == "ok" and r.get("exam")]


def _model_options(results: list[dict]) -> str:
    out = ['<option value="all">كل الموديلات</option>']
    for i, result in enumerate(results):
        if not result.get("exam"):
            continue
        out.append(f'<option value="m{i}">{esc(result.get("model") or i)}</option>')
    return "".join(out)


def _cat_options(exam_cfg: dict) -> str:
    out = ['<option value="all">كل المحاور</option>']
    for key in (exam_cfg.get("categories") or {}).keys():
        out.append(f'<option value="{esc(key)}">{esc(_cat_short(exam_cfg, key))}</option>')
    return "".join(out)


# --------------------------------------------------------------------------- أقسام
def _gemini_card(exam_cfg: dict) -> str:
    """كارت مرجع Gemini — **عرض فقط**، ويختفي بالكامل لما المستخدم يطفئ المرجع."""
    ref = gemini_reference(exam_cfg)
    if not ref:
        return ""
    values = gemini_values(exam_cfg)
    if not values:
        return ""
    avg = gemini_total(exam_cfg)
    bars = ""
    for key in (exam_cfg.get("categories") or {}).keys():
        value = values.get(key)
        if value is None:
            continue
        bars += (
            f'<div class="mc-axis"><span class="mc-axis-l">{esc(_cat_short(exam_cfg, key))}</span>'
            f'<span class="bar sm"><i style="width:{float(value):.1f}%"></i></span>'
            f'<span class="num mc-axis-v" dir="ltr">{float(value):.1f}%</span></div>'
        )
    src = ref.get("primary_source") or {}
    return f"""
<div class="ref-card src-manual {GEM_CLASS}" id="ref-gemini">
  <div class="ref-head">
    <span class="ref-icon">🎯</span>
    <span class="ref-title">مرجع عرض فقط ⛔</span>
  </div>
  <div class="ref-name">🎯 {esc(ref.get("name") or "Gemini 2.5 Pro")}</div>
  <div class="ref-score num" dir="ltr">{esc(fmt_num(avg, 1))}<span>/100</span></div>
  <div class="ref-axes">متوسط التقدير على المحاور الثمانية — <b>مش درجة rubric</b></div>
  <div class="mc-axes" style="margin-top:6px">{bars}</div>
  <div class="base-source target-src">
    <b>المصدر:</b> {esc(source_badge(ref))}
    <div class="mut small">{esc(str(src.get("title") or ""))}</div>
    <div class="mut small">{esc(str(src.get("url") or ""))}</div>
    <div class="mut small">⛔ <b>مالوش أي تأثير</b> في درجة أي نموذج ولا في الحكم ولا في حدود الدنيا.</div>
  </div>
</div>"""


def _hero(results: list[dict], exam_cfg: dict, run_meta: dict) -> str:
    ok = _ok_models(results)
    settings = exam_cfg.get("settings") or {}
    n_questions = len(exam_cfg.get("questions") or [])
    n_profile = len(exam_cfg.get("profile") or [])
    n_cats = len(exam_cfg.get("categories") or {})

    # ── السرعة المقيسة: بتاخد مكان مميز (أكبر رقم في التقرير بعد الدرجة)
    speeds: list[tuple[float, str]] = []
    for result in ok:
        perf = (result.get("runtime") or {}).get("perf") or {}
        avg = (perf.get("tg_tps") or {}).get("avg")
        if avg:
            speeds.append((float(avg), str(result.get("model") or "")))
    if speeds:
        best_speed, best_speed_model = max(speeds)
        avg_speed = sum(s for s, _ in speeds) / len(speeds)
        speed_block = f"""
<div class="speed-hero">
  <div class="speed-hero-head"><span class="speed-hero-icon">⚡</span><span>السرعة المقيسة فعلياً</span></div>
  <div class="speed-hero-value num" dir="ltr">{esc(fmt_num(best_speed, 1))}<span class="speed-hero-unit">tok/s</span></div>
  <div class="speed-hero-sub">أسرع موديل · متوسط {esc(fmt_num(avg_speed, 1))} tok/s</div>
  <div class="speed-hero-model">{esc(_short_name(best_speed_model, 34))}</div>
</div>"""
    else:
        speed_block = ""

    return f"""
<section class="hero" id="top">
  <div class="hero-main">
    <div class="eyebrow">AI Online Tester · تقرير تلقائي</div>
    <h1>امتحان المساعد المصري <span class="grad">v3</span></h1>
    <p class="lead">
      مقارنة موديلات GGUF على نفس الـ {n_questions} سؤالاً مصحّحاً (5 معايير × درجتين لكل سؤال)
      على {n_cats} محاور بأوزان وحدود دنيا، بتصحيح <b>حتمي بالكامل</b> (تعبيرات نمطية + أرقام + تنفيذ كود)
      — بدون LLM-judge. و{n_profile} سؤال استكشافي بلا درجة.
    </p>
    <div class="chips">
      <span class="chip">🤖 {len(ok)} موديل مكتمل من {len(results)}</span>
      <span class="chip">🖥 {esc(runner_label(run_meta))}</span>
      <span class="chip">🧪 temp {esc(settings.get("temperature", 0))} · top_p {esc(settings.get("top_p", 0))} · seed {esc(settings.get("seed", 0))}</span>
      <span class="chip">🧠 ctx {esc(settings.get("ctx_size", 8192))} · max {esc(settings.get("max_tokens", 4000))} توكن</span>
      <span class="chip">📄 {esc(exam_cfg.get("spec_path") or "exam/exam_questions_v2.json")}</span>
      <span class="chip">🕒 {esc(run_meta.get("finished_at") or now_iso())}</span>
    </div>
    {speed_block}
  </div>
  <aside class="hero-side">
    <div class="ref-controls" id="ref-controls">
      <label class="ref-check"><input type="checkbox" id="show-gemini" checked>
        🎯 إظهار مرجع Gemini 2.5 Pro <span class="mut">(عرض فقط ⛔)</span></label>
    </div>
    {_gemini_card(exam_cfg)}
  </aside>
</section>
"""


def _kpis(results: list[dict], exam_cfg: dict, run_meta: dict) -> str:
    ok = _ok_models(results)
    failed = len(results) - len(ok)
    hard = [r for r in ok if (r.get("exam") or {}).get("failed_categories")]
    if ok:
        best = max(ok, key=lambda r: float((r.get("exam") or {}).get("total") or 0))
        best_exam = best.get("exam") or {}
        best_total = float(best_exam.get("total") or 0)
        best_name = best.get("model") or ""
    else:
        best, best_exam, best_total, best_name = None, {}, 0.0, "—"

    runtimes = [float((r.get("runtime") or {}).get("seconds_total") or 0) for r in ok]
    avg_min = (sum(runtimes) / len(runtimes) / 60.0) if runtimes else 0.0
    answers = sum(len((r.get("exam") or {}).get("questions") or {}) for r in ok)
    n_questions = len(exam_cfg.get("questions") or [])

    # ── السرعة المقيسة: أسرع موديل بـ tok/s (رقم بارز زي الدرجة)
    speed_rows: list[tuple[float, str]] = []
    for r in ok:
        perf = (r.get("runtime") or {}).get("perf") or {}
        avg = (perf.get("tg_tps") or {}).get("avg")
        if avg:
            speed_rows.append((float(avg), str(r.get("model") or "")))
    if speed_rows:
        best_tps, best_tps_model = max(speed_rows)
        avg_tps_all = sum(t for t, _ in speed_rows) / len(speed_rows)
    else:
        best_tps, best_tps_model, avg_tps_all = None, "—", None

    # ── الأقرب لمرجع Gemini (عرض فقط)
    ref = gemini_reference(exam_cfg)
    ranked = gemini_ranking(ok, exam_cfg)
    if ranked:
        nearest = ranked[0]
        nearest_name = str(nearest["result"].get("model") or "—")
        nearest_dist = nearest["distance"]
        nearest_sub = f"المسافة {fmt_num(nearest_dist, 1)} عن {ref.get('name', 'المرجع')}"
    else:
        nearest_name, nearest_dist, nearest_sub = "—", None, "مفيش نتائج"

    cards = [
        ("أفضل موديل", esc(best_name or "—"), f"الدرجة {esc(fmt_num(best_total, 2))}/100", "kpi-best"),
        (
            "🎯 الأقرب لمرجع Gemini",
            esc(_short_name(nearest_name, 26)),
            nearest_sub,
            f"kpi-target {GEM_CLASS}",
        ),
        (
            "⚡ أسرع توليد",
            (
                f'<span class="kpi-tok num" dir="ltr">{esc(fmt_num(best_tps, 1))}'
                f'<span class="unit">tok/s</span></span>'
                if best_tps is not None
                else "—"
            ),
            (
                f"متوسط {esc(fmt_num(avg_tps_all, 1))} tok/s"
                if avg_tps_all is not None
                else "لا يوجد قياس"
            ),
            "kpi-speed",
        ),
        (
            "موديلات مكتملة",
            f"{len(ok)}<span class='mut'>/{len(results)}</span>",
            f"{failed} فشل تشغيل" if failed else "كل الموديلات اشتغلت",
            "kpi-count",
        ),
        (
            "فشل حرج ⛔",
            f"{len(hard)}",
            "موديل نزل فيه محور عن حدّه الأدنى",
            "kpi-gates",
        ),
        (
            "متوسط زمن الموديل",
            f"{avg_min:.1f}<span class='unit'>د</span>",
            f"على {esc(runner_label(run_meta))}",
            "kpi-time",
        ),
        (
            "ردود مصححة",
            f"{answers}",
            f"{len(ok) * n_questions} رد متوقع",
            "kpi-answers",
        ),
    ]
    cards_html = "".join(
        f'<article class="kpi {cls}"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div><div class="kpi-sub">{sub}</div></article>'
        for label, value, sub, cls in cards
    )
    return f'<section class="kpis" id="overview">{cards_html}</section>'


def _summary_table(results: list[dict], exam_cfg: dict) -> str:
    cat_keys = list((exam_cfg.get("categories") or {}).keys())
    ref = gemini_reference(exam_cfg)
    rows = []
    ranked = sorted(
        [r for r in results if r.get("exam")],
        key=lambda r: float((r.get("exam") or {}).get("total") or 0),
        reverse=True,
    )
    rank = {id(r): i for i, r in enumerate(ranked, 1)}
    for result in results:
        exam = result.get("exam") or {}
        fit = result.get("fit") or {}
        runtime = result.get("runtime") or {}
        manifest = result.get("manifest") or {}
        status = result.get("status") or ("ok" if exam else "failed")
        total = exam.get("total")
        requests = runtime.get("requests") or []
        tps = [float(r.get("tps")) for r in requests if r.get("tps")]
        avg_tps = sum(tps) / len(tps) if tps else None
        perf = runtime.get("perf") or {}
        tg_real = (perf.get("tg_tps") or {}).get("avg")
        ttft_real = (perf.get("ttft_ms") or {}).get("avg")
        perf_html = (
            f'<span class="tok-big num" dir="ltr">{esc(fmt_num(tg_real, 1))}'
            f'<span class="tok-unit">tok/s</span></span>'
            f'<div class="mut small">أول استجابة {esc(fmt_num(ttft_real, 0))} ms</div>'
            if tg_real
            else '<span class="mut">—</span>'
        )
        cats = exam.get("categories") or {}
        cat_cells = ""
        for key in cat_keys:
            row = cats.get(key) or {}
            pct = row.get("percent")
            under = bool(row.get("failed_min"))
            style = ' style="background:rgba(251,113,133,.16)"' if under else ""
            cat_cells += (
                f'<td{style}><span class="num" dir="ltr">'
                f'{esc(fmt_num(pct, 1))}%{" ⛔" if under else ""}</span></td>'
            )
        model = result.get("model") or ""
        gap = gemini_gap(exam, exam_cfg) if ref else {"distance": None}
        distance = gap.get("distance")
        distance_html = (
            f'<span class="num dist-val" dir="ltr">{fmt_num(distance, 1)}</span>'
            if distance is not None
            else "—"
        )
        rows.append(
            f"""
<tr class="{'failed-row' if status != 'ok' else ''}">
  <td class="rank num" dir="ltr">{rank.get(id(result), "—")}</td>
  <td class="model-cell">
    <div class="model-name" title="{esc(result.get('model_full') or model)}">{esc(model)}</div>
    <div class="mut small">{esc(manifest.get("quant_pattern") or manifest.get("quant_chosen") or "")}</div>
  </td>
  <td class="verdict-cell"><span class="verdict {_verdict_class(exam.get('verdict'), status)}">{esc(exam.get('verdict') or ("فشل التشغيل" if status != "ok" else "—"))}</span></td>
  <td class="score-total">{_score_cell(total, exam.get("max", 100), bar=False)}</td>
  {cat_cells}
  <td>{_gate_badges(exam) if exam else '<span class="pill muted">—</span>'}</td>
  <td><span class="pill {_fit_class(fit.get("fit_class"))}">{esc(fit.get("fit_class") or "—")}</span></td>
  <td class="num" dir="ltr">{esc(human_bytes((manifest.get("total_bytes") or (fit.get("file_bytes") if fit else 0))))}</td>
  <td class="num" dir="ltr">{esc(fmt_num(runtime.get("seconds_total"), 0))}s</td>
  <td class="num" dir="ltr">{esc(runtime.get("peak_rss_mib") or "—")} MiB</td>
  <td class="num" dir="ltr">{esc(fmt_num(avg_tps, 1) if avg_tps is not None else "—")}</td>
  <td class="perf-cell">{perf_html}</td>
  <td class="{GEM_CLASS}">{distance_html}</td>
</tr>"""
        )
    cat_heads = "".join(
        f'<th title="{esc((exam_cfg.get("categories") or {}).get(key, {}).get("name") or key)}">'
        f'{esc(_cat_short(exam_cfg, key))}</th>'
        for key in cat_keys
    )
    return f"""
<section class="section" id="results">
  <div class="section-head">
    <div><h2>🏁 المقارنة النهائية</h2><p class="sub">مرتبة بالدرجة من 100.
    كل محور بيعرض نسبته (0–100%) والـ ⛔ يعني المحور نزل عن حدّه الأدنى = <b>فشل حرج</b> حتى لو المجموع عالي.
    <span class="{GEM_CLASS}">والعمود الأخير (المسافة عن مرجع Gemini) بيختفي لما تطفئ المرجع.</span></p></div>
    <div class="legend"><span class="gate off">فوق الحد</span><span class="gate on">تحت الحد ●</span></div>
  </div>
  <div class="table-wrap">
    <table class="tbl summary-tbl">
      <thead><tr>
        <th>#</th><th>الموديل</th><th>الحكم</th><th>الدرجة</th>
        {cat_heads}
        <th>حدود الدنيا</th><th>Fit</th><th>الحجم</th><th>الزمن</th><th>Peak RSS</th><th>tok/s</th>
        <th>⚡ أداء مقيس</th><th class="{GEM_CLASS}">المسافة عن Gemini</th>
      </tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>
</section>
"""


def _categories_section(results: list[dict], exam_cfg: dict) -> str:
    """بطاقات المحاور الثمانية: الوزن + الحد الأدنى + درجات كل موديل."""
    categories = exam_cfg.get("categories") or {}
    ok = _ok_models(results)
    blocks = []
    for key, cfg in categories.items():
        rows = []
        for result in ok:
            row = ((result.get("exam") or {}).get("categories") or {}).get(key) or {}
            if not row:
                continue
            state = "⛔ تحت الحد" if row.get("failed_min") else "✅"
            rows.append(
                f"<tr><td>{esc(result.get('model'))}</td>"
                f"<td class='num' dir='ltr'>{esc(fmt_num(row.get('percent'), 1))}%</td>"
                f"<td class='num' dir='ltr'>{esc(fmt_num(row.get('points'), 2))}</td>"
                f"<td class='num' dir='ltr'>{esc(fmt_num(row.get('score'), 1))}/{esc(fmt_num(row.get('max'), 0))}</td>"
                f"<td>{state}</td></tr>"
            )
        blocks.append(
            f"""
<article class="card axis-card">
  <header class="axis-head">
    <div><h3>{esc(cfg.get("name") or key)}</h3>
      <div class="mut small">الوزن {esc(fmt_num(cfg.get("weight"), 0))} · الحد الأدنى {esc(fmt_num(cfg.get("min_percent"), 0))}%</div></div>
    <div class="axis-qcount">{len(cfg.get("questions") or [])} أسئلة</div>
  </header>
  <div class="table-wrap">
    <table class="tbl compact">
      <thead><tr><th>الموديل</th><th>النسبة</th><th>النقاط</th><th>الدرجة الخام</th><th>الحالة</th></tr></thead>
      <tbody>{''.join(rows) or '<tr><td colspan="5" class="mut">مفيش نتائج.</td></tr>'}</tbody>
    </table>
  </div>
</article>"""
        )
    return f"""
<section class="section" id="categories">
  <div class="section-head"><div><h2>📊 المحاور الثمانية</h2>
  <p class="sub">لكل محور: الوزن (كم نقطة من الـ 100) والحد الأدنى (النسبة اللي لو نزلت تحتها ⇒ فشل حرج).
  النقاط = النسبة × الوزن.</p></div></div>
  <div class="axis-grid">{''.join(blocks)}</div>
</section>
"""


def _gates_section(results: list[dict]) -> str:
    """حدود الدنيا لكل محور (بوابات الحد الأدنى في v3)."""
    rows = []
    for result in results:
        exam = result.get("exam")
        if not exam:
            rows.append(
                f"<tr><td>{esc(result.get('model'))}</td><td colspan='5' class='mut'>فشل التشغيل: {_safe_text(result.get('error'), 180)}</td></tr>"
            )
            continue
        for gate in exam.get("gates") or []:
            fired = bool(gate.get("fired"))
            rows.append(
                f"""
<tr class="{'gate-fired' if fired else ''}">
  <td class="model-cell">{esc(result.get('model'))}</td>
  <td>{esc(gate.get('title'))}</td>
  <td class="mut">{esc(gate.get('threshold'))}</td>
  <td>{'<b class="bad">فشل حرج ⛔</b>' if fired else '<span class="ok">فوق الحد ✓</span>'}</td>
  <td>{_safe_text(gate.get('detail'), 260)}</td>
  <td class="mut small">{esc('، '.join(gate.get('questions') or [])[:120])}</td>
</tr>"""
            )
    return f"""
<section class="section" id="gates">
  <div class="section-head"><div><h2>🚦 حدود الدنيا لكل محور</h2>
  <p class="sub">أي محور نزل عن حدّه الأدنى ⇒ <b>فشل حرج ⛔</b> حتى لو المجموع عالي.
  دي حدود الدنيا الثمانية في الامتحان v3 (محور لكل حد).</p></div></div>
  <div class="table-wrap">
    <table class="tbl compact">
      <thead><tr><th>الموديل</th><th>الحد الأدنى</th><th>العتبة</th><th>الحالة</th><th>التفاصيل</th><th>الأسئلة</th></tr></thead>
      <tbody>{''.join(rows) or '<tr><td colspan="6" class="mut">مفيش نتائج.</td></tr>'}</tbody>
    </table>
  </div>
</section>
"""


def _heatmap(results: list[dict], exam_cfg: dict) -> str:
    models = _ok_models(results)
    if not models:
        return ""
    questions = exam_cfg.get("questions") or []
    head = "".join(
        f"<th class='heat-model' title='{esc(r.get('model'))}'>{esc((r.get('model') or '')[:22])}</th>"
        for r in models
    )
    rows = []
    for q in questions:
        qid = q.get("id")
        cells = []
        for result in models:
            row = ((result.get("exam") or {}).get("questions") or {}).get(qid)
            if not row:
                cells.append("<td class='heat na'>—</td>")
                continue
            pct = _pct(row.get("score"), row.get("max"))
            tip = f"{qid} · {result.get('model')} · {row.get('score')}/{row.get('max')} · {'؛ '.join(row.get('notes') or [])[:400]}"
            cells.append(
                f"<td class='heat' style='{_heat_style(pct)}' title='{esc(tip)}'>"
                f"<b>{esc(fmt_num(row.get('score'), 1))}</b><small>{esc(fmt_num(pct, 0))}%</small></td>"
            )
        rows.append(
            f"<tr><th class='heat-q'><span class='qid'>{esc(qid)}</span> {esc(q.get('title'))}</th>{''.join(cells)}</tr>"
        )
    return f"""
<section class="section" id="heatmap">
  <div class="section-head">
    <div><h2>🔥 خريطة الدرجات</h2><p class="sub">كل خلية = درجة السؤال. مرّر الماوس على الخلية تشوف سبب الخصم.</p></div>
    <div class="heat-legend"><span>0%</span><i></i><span>50%</span><i></i><span>100%</span></div>
  </div>
  <div class="table-wrap heat-wrap">
    <table class="tbl heat-tbl">
      <thead><tr><th class="heat-q">السؤال</th>{head}</tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>
</section>
"""


def _perf_section(results: list[dict], run_meta: dict) -> str:
    """قسم الأداء **المقيس فعلياً** — أرقام حقيقية من تشغيل الموديل على الكارت.

    ده القسم المهم: السرعة الفعلية وزمن أول استجابة وحجم الـ RAM
    المقيس فعلياً أثناء التشغيل. التقديرات البحتة موجودة في قسم «الملاءمة» بس.
    """
    rows: list[str] = []
    measured_any = False
    contention_notes: list[str] = []
    for result in results:
        runtime = result.get("runtime") or {}
        perf = runtime.get("perf") or {}
        fit = result.get("fit") or {}
        if not perf:
            continue
        measured_any = True
        contention = runtime.get("gpu_contention") or {}
        competing = contention.get("competing_processes") or []
        if competing:
            names = "، ".join(str(c.get("name") or "?") for c in competing)
            contention_notes.append(f"{result.get('model')}: {names}")
        tg = perf.get("tg_tps") or {}
        pp = perf.get("pp_tps") or {}
        req = perf.get("request_seconds") or {}
        ttft = perf.get("ttft_ms") or {}
        prompt_ms = perf.get("prompt_ms") or {}

        # مقارنة: المقيس vs السقف النظري (النظري ثانوي — للمقارنة فقط)
        ceil_tg = fit.get("tg_tps")
        real_tg = tg.get("avg")
        ratio = None
        if real_tg and ceil_tg:
            ratio = round(float(real_tg) / float(ceil_tg) * 100, 1)
        ratio_html = (
            f'<span class="num" dir="ltr">{ratio}%</span>'
            if ratio is not None
            else '<span class="mut">—</span>'
        )

        rows.append(
            f"""
<tr>
  <td class="model-cell">{esc(result.get('model'))}
    <div class="mut small">{esc(runtime.get('device') or '—')} · ngl={esc(runtime.get('ngl') if runtime.get('ngl') is not None else '—')} · threads={esc(runtime.get('threads') or '—')}</div></td>
  <td class="num" dir="ltr"><b>{esc(fmt_num(real_tg, 1))}</b>
    <div class="mut small">min {esc(fmt_num(tg.get('min'), 1))} · max {esc(fmt_num(tg.get('max'), 1))}</div></td>
  <td class="num" dir="ltr"><b>{esc(fmt_num(pp.get('avg'), 1))}</b>
    <div class="mut small">min {esc(fmt_num(pp.get('min'), 1))} · max {esc(fmt_num(pp.get('max'), 1))}</div></td>
  <td class="num" dir="ltr">{esc(fmt_num(ttft.get('avg'), 0))}
    <div class="mut small">p95 {esc(fmt_num(ttft.get('p95'), 0))} ms</div></td>
  <td class="num" dir="ltr">{esc(fmt_num(req.get('avg'), 1))}
    <div class="mut small">max {esc(fmt_num(req.get('max'), 1))} s</div></td>
  <td class="num" dir="ltr">{esc(fmt_num(perf.get('startup_seconds'), 0))} s</td>
  <td class="num" dir="ltr">{esc(fmt_num(perf.get('seconds_total'), 0))} s</td>
  <td class="num" dir="ltr">{esc(runtime.get('peak_rss_mib') or '—')} MiB</td>
  <td class="num" dir="ltr">{esc(runtime.get('peak_vram_mib') or '—')} MiB</td>
  <td class="num" dir="ltr">{esc(fmt_num(perf.get('total_generated_tokens'), 0))}</td>
  <td class="num" dir="ltr">{esc(fmt_num(ceil_tg, 1))}</td>
  <td>{ratio_html}</td>
</tr>"""
        )
    if not measured_any:
        return ""
    if runner_kind(run_meta) == "kaggle_gpu":
        perf_context = (
            f"القياس تم على <b>{esc(runner_label(run_meta))}</b> — GPU حقيقي مع محاكاة "
            "ميزانية VRAM/RAM لجهازك. الأرقام دي **سرعة الكارت الفعلي** (T4)، وهي أسرع من "
            "Quadro M4000M بتاعك؛ للمقارنة مع جهازك استخدم قسم الملاءمة النظرية."
        )
    elif measured_on_gpu(run_meta):
        perf_context = (
            f"القياس تم على <b>{esc(runner_label(run_meta))}</b> — GPU حقيقي. "
            "الأرقام دي سرعة الكارت الفعلي المستخدم، مش تقدير رياضي."
        )
    else:
        perf_context = (
            f"القياس تم على <b>{esc(runner_label(run_meta))}</b> — من غير GPU (ngl=0)، "
            "فالأرقام دي سرعة المعالج مش سرعة كارت."
        )
    contention_banner = ""
    if contention_notes:
        contention_banner = (
            '<div class="card note warn-note"><b>⚠ تحذير على دقة القياس:</b> '
            " وقت القياس كانت فيه عمليات استدلال تانية شغالة على نفس الكارت "
            f"({esc('؛ '.join(contention_notes))}) — يعني الكارت كان بينقسم والسرعة "
            "المقيسة **أقل من الحقيقي**. أعِد القياس بعد ما تقفل أي سيرفر تاني.</div>"
        )
    return f"""
<section class="section" id="perf">
  <div class="section-head">
    <div><h2>⚡ الأداء الحقيقي المقيس</h2>
    <p class="sub">أرقام <b>مقيسة فعلياً</b> أثناء تشغيل كل موديل — من `timings` الخاص بـ llama.cpp
    ومن أوقات الطلبات الحقيقية. مفيش تقدير رياضي في هذا القسم.
    {perf_context}</p></div>
  </div>
  {contention_banner}
  <div class="table-wrap">
    <table class="tbl compact">
      <thead><tr>
        <th>الموديل</th><th>توليد tok/s (مقيس)</th><th>معالجة prompt tok/s (مقيس)</th>
        <th>أول استجابة ms (مقيس)</th><th>زمن الطلب s (مقيس)</th><th>تجهيز الموديل s</th>
        <th>إجمالي الامتحان s</th><th>ذاكرة RAM مقيسة MiB</th><th>ذاكرة VRAM مقيسة MiB</th>
        <th>توكنز مولّدة</th>
        <th>سقف tg نظري</th><th>المقيس/النظري</th>
      </tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>
  <div class="card note perf-note">
    <b>إزاي تقرأ الأرقام دي:</b>
    <ul>
      <li><b>توليد tok/s</b> = سرعة التوليد الفعلية — دي اللي بتحسّ بيها في الاستخدام اليومي.</li>
      <li><b>أول استجابة ms</b> = الزمن لحد ما الموديل يبدأ يرد — ده اللي بيحسّ بيه المستخدم إنه «علق».</li>
      <li><b>تجهيز الموديل s</b> = وقت تحميله على الكارت (كل مرة تفتح).</li>
      <li><b>سقف tg نظري</b> = تقدير رياضي من مواصفات جهازك — للمقارنة فقط. لو المقيس أقل منه، ده طبيعي
        (السقف يفترض أفضل حالات). <b>الرقم اللي بياخد قرارك هو المقيس.</b></li>
      <li><b>ذاكرة VRAM مقيسة</b> = ذروة الاستخدام الحقيقي من الكارت (nvidia-smi) — دي بتثبت إن
        الموديل دخل ميزانيتك فعلاً (لو exceed عرض ⇒ الموديل مش هيشتغل على جهازك).</li>
    </ul>
  </div>
</section>
"""


def _fit_section(results: list[dict], run_meta: dict) -> str:
    fit_context = (
        "الحساب على <b>ميزانية جهازك المستهدف</b> (VRAM 3.4 GiB · RAM 15.9 GiB) "
        "ومواصفات Quadro M4000M — عشان تعرف الموديل ده هيترتب إزاي على جهازك."
        if measured_on_gpu(run_meta)
        else "الحساب على مواصفات جهازك المستهدف من <code>config/device_profile.yaml</code>."
    )
    rows = []
    for result in results:
        fit = result.get("fit") or {}
        runtime = result.get("runtime") or {}
        meta = fit.get("meta") or {}
        kv_heads = meta.get("head_count_kv")
        if isinstance(kv_heads, (list, tuple)):
            kv_heads = "، ".join(str(x) for x in kv_heads)
        rows.append(
            f"""
<tr>
  <td class="model-cell">{esc(result.get('model'))}<div class="mut small">{esc(Path(str(fit.get('file') or '')).name)}</div></td>
  <td class="num" dir="ltr">{esc(fmt_num(fit.get('file_gib'), 3))} GiB</td>
  <td class="num" dir="ltr">{esc(meta.get('block_count') or fit.get('n_layers') or '—')}</td>
  <td class="num" dir="ltr">{esc(meta.get('head_count') or '—')} / {esc(kv_heads or '—')}</td>
  <td class="num" dir="ltr">{esc(fit.get('kv_total_gib') or '—')} GiB</td>
  <td class="num" dir="ltr">{esc(fit.get('need_full_gib') or '—')} GiB</td>
  <td class="num" dir="ltr">{esc(fit.get('ngl') if fit.get('ngl') is not None else '—')}/{esc(fit.get('n_layers') or '—')}</td>
  <td><span class="pill {_fit_class(fit.get('fit_class'))}">{esc(fit.get('fit_class') or '—')}</span></td>
  <td class="num" dir="ltr">{esc(fmt_num(fit.get('tg_tps'), 1) or '—')}</td>
  <td class="num" dir="ltr">{esc(fmt_num(fit.get('pp_tps'), 1) or '—')}</td>
  <td class="num" dir="ltr">{esc(runtime.get('ngl') if runtime else '—')}</td>
  <td class="num" dir="ltr">{esc(fmt_num(fit.get('params_b_assumed'), 2) or '—')}B</td>
  <td class="mut small">{_safe_text(fit.get('error'), 120) or _safe_text(fit.get('run_command'), 180)}</td>
</tr>"""
        )
    return f"""
<section class="section" id="fit">
  <div class="section-head">
    <div><h2>🧮 الملاءمة والسرعة النظرية</h2>
    <p class="sub"><b>تقديرات رياضية</b> — {fit_context}
    للمقارنة والتخطيط، <b>مش قياس</b>. الأرقام المقيسة فعلياً في قسم
    <a href="#perf">⚡ الأداء الحقيقي المقيس</a>، وهي اللي بتاخد قرارك.</p></div>
  </div>
  <div class="table-wrap">
    <table class="tbl compact">
      <thead><tr>
        <th>الموديل</th><th>الحجم</th><th>Layers</th><th>Heads / KV</th><th>KV</th><th>الاحتياج</th>
        <th>ngl (محاكاة جهازك)</th><th>Fit</th><th>سقف tg</th><th>سقف pp</th><th>ngl التشغيل</th><th>Params</th><th>ملاحظة</th>
      </tr></thead>
      <tbody>{''.join(rows) or '<tr><td colspan="13" class="mut">مفيش نتائج.</td></tr>'}</tbody>
    </table>
  </div>
</section>
"""


def _answers_section(results: list[dict], exam_cfg: dict) -> str:
    ok = _ok_models(results)
    if not ok:
        return """
<section class="section" id="answers"><div class="section-head"><h2>💬 الإجابات</h2></div>
<div class="card mut">مفيش إجابات مكتملة.</div></section>"""
    questions = exam_cfg.get("questions") or []
    blocks = []
    for q_index, q in enumerate(questions):
        qid = str(q.get("id"))
        cards = []
        for m_index, result in enumerate(results):
            if not result.get("exam"):
                continue
            row = ((result.get("exam") or {}).get("questions") or {}).get(qid)
            if not row:
                continue
            notes = "؛ ".join(row.get("notes") or [])
            health = "، ".join(row.get("health") or [])
            search_blob = " ".join(
                [
                    str(result.get("model") or ""),
                    qid,
                    str(q.get("title") or ""),
                    str(q.get("prompt") or ""),
                    str(row.get("answer") or ""),
                    notes,
                ]
            ).lower()
            cards.append(
                f"""
<article class="answer-card" data-model="m{m_index}" data-cat="{esc(row.get('category'))}" data-search="{esc(search_blob)}">
  <header>
    <div class="ans-model">{esc(result.get('model'))}</div>
    <div class="ans-score">{_score_cell(row.get('score'), row.get('max'), bar=False)}</div>
  </header>
  <div class="ans-meta">
    <span>{esc(row.get('chars') or 0)} حرف</span>
    <span>{esc(row.get('tokens') if row.get('tokens') is not None else '—')} توكن</span>
    <span>{esc(fmt_num(row.get('seconds'), 1))} ث</span>
    <span>{esc(row.get('finish') or '—')}</span>
    {f'<span class="bad small">⚠ {esc(health)}</span>' if health else ''}
  </div>
  <pre class="answer-text">{esc(row.get('answer') or '')}</pre>
  {f'<details class="reason"><summary>reasoning ({len(str(row.get("reasoning") or ""))} حرف)</summary><pre>{esc(row.get("reasoning") or "")}</pre></details>' if row.get('reasoning') else ''}
  {f'<div class="notes"><b>ملاحظات المصحح:</b> {esc(notes)}</div>' if notes else ''}
  {f'<div class="notes bad">خطأ تشغيل: {esc(row.get("error"))}</div>' if row.get('error') else ''}
</article>"""
            )
        chips = "".join(
            f"<span class='chip sm'>{esc(r.get('model'))}: <b>{esc(fmt_num(((r.get('exam') or {}).get('questions') or {}).get(qid, {}).get('score'), 1))}</b></span>"
            for r in ok
        )
        blocks.append(
            f"""
<details class="qblock" {'open' if q_index == 0 else ''} data-qid="{esc(qid)}">
  <summary>
    <span class="qid">{esc(qid)}</span>
    <span class="qtitle">{esc(q.get('title'))}</span>
    <span class="qprompt">{esc(q.get('prompt'))}</span>
    <span class="qchips">{chips}</span>
  </summary>
  <div class="answers-grid">{''.join(cards)}</div>
</details>"""
        )
    return f"""
<section class="section" id="answers">
  <div class="section-head"><div><h2>💬 الإجابات جنب بعض</h2><p class="sub">نفس السؤال لكل الموديلات. افتح السؤال وشوف الإجابة وملاحظات المصحح.</p></div></div>
  <div class="filters card">
    <label>الموديل <select id="f-model">{_model_options(results)}</select></label>
    <label>المحور <select id="f-cat">{_cat_options(exam_cfg)}</select></label>
    <label class="grow">بحث <input id="f-search" type="search" placeholder="كلمة في السؤال أو الإجابة أو الملاحظات…"></label>
    <span id="f-count" class="mut small"></span>
    <button type="button" class="btn" id="f-clear">مسح</button>
  </div>
  <div id="qblocks">{''.join(blocks)}</div>
</section>
"""


def _meta_section(results: list[dict], exam_cfg: dict, run_meta: dict) -> str:
    settings = exam_cfg.get("settings") or {}
    runtime = exam_cfg.get("runtime") or {}
    categories = exam_cfg.get("categories") or {}
    items = [
        ("رقم التشغيل", run_meta.get("run_id") or "—"),
        ("بداية التشغيل", run_meta.get("started_at") or "—"),
        ("نهاية التشغيل", run_meta.get("finished_at") or "—"),
        ("عدد الموديلات", len(results)),
        ("الموديلات المدخلة", run_meta.get("models_input") or "—"),
        ("إصدار الامتحان", exam_cfg.get("version") or "—"),
        ("ملف المواصفات", exam_cfg.get("spec_path") or "—"),
        ("عدد الأسئلة المصحّحة", len(exam_cfg.get("questions") or [])),
        ("عدد الأسئلة الاستكشافية", len(exam_cfg.get("profile") or [])),
        ("عدد المحاور", len(categories)),
        ("quant_pattern", run_meta.get("quant_pattern") or "—"),
        ("ctx_size", settings.get("ctx_size")),
        ("kv_cache_type", run_meta.get("kv") or "—"),
        ("threads", run_meta.get("threads")),
        ("temperature", settings.get("temperature")),
        ("top_p", settings.get("top_p")),
        ("seed", settings.get("seed")),
        ("max_tokens", settings.get("max_tokens")),
        ("max_answer_chars", settings.get("max_answer_chars")),
        ("تكرار الأسئلة", settings.get("repeats")),
        ("المحاور المتكررة", "، ".join(settings.get("repeat_for") or []) or "—"),
        ("القالب", runtime.get("template") or run_meta.get("template") or "—"),
        ("system prompt", run_meta.get("system_prompt") or "—"),
        ("ملف الجهاز", run_meta.get("device_profile") or "—"),
        ("وضع التشغيل", run_meta.get("mode") or "llama-server /v1/chat/completions"),
        ("بيئة التشغيل", runner_label(run_meta)),
        ("GPU الفعلي", run_meta.get("runner_gpu") or "—"),
        ("نظام التشغيل", run_meta.get("platform") or "—"),
        ("Python", run_meta.get("python") or "—"),
        ("آخر تحديث", run_meta.get("finished_at") or now_iso()),
    ]
    grid = "".join(
        f'<div class="meta-item"><div class="meta-key">{esc(k)}</div><div class="meta-val">{esc(v)}</div></div>'
        for k, v in items
    )
    # ── جدول أوزان المحاور وحدود الدنيا
    cat_rows = "".join(
        f"<tr><td>{esc(cfg.get('name') or key)}</td>"
        f"<td class='num' dir='ltr'>{esc(fmt_num(cfg.get('weight'), 0))}</td>"
        f"<td class='num' dir='ltr'>{esc(fmt_num(cfg.get('min_percent'), 0))}%</td>"
        f"<td>{esc(len(cfg.get('questions') or []))}</td></tr>"
        for key, cfg in categories.items()
    )
    versions = []
    seen = set()
    for result in results:
        rt = result.get("runtime") or {}
        ver = rt.get("llama_version")
        if ver and ver not in seen:
            seen.add(ver)
            versions.append(
                f'<div class="meta-item wide"><div class="meta-key">llama.cpp — {esc(result.get("model"))}</div>'
                f'<div class="meta-val small" dir="ltr">{esc(ver)}</div></div>'
            )
    per_model = []
    for result in results:
        rt = result.get("runtime") or {}
        if not rt:
            continue
        manifest = result.get("manifest") or {}
        per_model.append(
            f'<div class="meta-item wide"><div class="meta-key">بصمات — {esc(result.get("model"))}</div>'
            f'<div class="meta-val small" dir="ltr">quant: {esc(manifest.get("quant_chosen") or manifest.get("quant_pattern") or "—")} · '
            f'template: {esc(str(rt.get("template_sha256", "—"))[:16])} · '
            f'prompt: {esc(str(rt.get("system_prompt_sha256", "—"))[:16])} · log: {esc(rt.get("server_log", "—"))}</div></div>'
        )
    return f"""
<section class="section" id="meta">
  <div class="section-head"><div><h2>🗂 البيانات الوصفية</h2><p class="sub">كل ما يلزم لإعادة نفس التشغيل ومقارنة النتائج.</p></div></div>
  <div class="meta-grid">{grid}{''.join(versions)}{''.join(per_model)}</div>
  <div class="card note">
    <b>ملاحظة منهجية:</b> التصحيح حتمي 100% — نفس الإجابات تعطي نفس الدرجات.
    قسم <a href="#perf">⚡ الأداء الحقيقي المقيس</a> أرقامه **مقيسة فعلاً** على الكارت أثناء التشغيل
    (من <code>timings</code> الخاص بـ llama.cpp ومن أوقات الطلبات) — دي الأرقام اللي بتاخد قرارك.
    قسم <a href="#fit">الملاءمة</a> أرقامه **تحليلية/نظرية** لجهازك المستهدف — للمقارنة والتخطيط فقط.
    المقارنة بين الموديلات صحيحة لأنها بنفس البيئة والإعدادات.
  </div>
  <div class="card note">
    <b>مواصفات الامتحان v3:</b> 33 سؤال مصحّح (5 معايير × درجتين = 10 درجات/سؤال) ·
    14 سؤال استكشافي بلا درجة · 8 محاور بأوزان وحدود دنيا.
  </div>
  <div class="table-wrap">
    <table class="tbl compact">
      <thead><tr><th>المحور</th><th>الوزن</th><th>الحد الأدنى %</th><th>عدد الأسئلة</th></tr></thead>
      <tbody>{cat_rows}</tbody>
    </table>
  </div>
</section>
"""


def _guide(run_meta: dict) -> str:
    if runner_kind(run_meta) == "kaggle_gpu":
        fit_text = (
            "حساب تحليلي من metadata الـ GGUF وميزانية جهازك المستهدف، <b>مش قياس فعلي</b>. "
            "القياس الفعلي في قسم <a href=\"#perf\">⚡ الأداء الحقيقي المقيس</a> — بس خُد بالك: "
            "الكارت اللي اتقاس عليه (T4 على Kaggle) أسرع من Quadro M4000M بتاعك، "
            "فالسرعة الحقيقية على جهازك أقل. قسم الملاءمة هو اللي بيحاكي جهازك."
        )
    elif measured_on_gpu(run_meta):
        fit_text = (
            "حساب تحليلي من metadata الـ GGUF ومواصفات جهازك، <b>مش قياس فعلي</b>. "
            "القياس الفعلي في قسم <a href=\"#perf\">⚡ الأداء الحقيقي المقيس</a>."
        )
    else:
        fit_text = (
            "حساب تحليلي من metadata الـ GGUF ومواصفات جهازك، <b>مش قياس فعلي</b> — "
            "وده السبب إن لازم تبص على قسم <a href=\"#perf\">⚡ الأداء الحقيقي المقيس</a> "
            "قبل ما تقرر. التشغيل الحالي على CPU (ngl=0) مش على كارت."
        )
    return f"""
<section class="section" id="guide">
  <details class="card guide">
    <summary><span class="guide-h">📖 إزاي تقرأ التقرير</span></summary>
    <div class="guide-grid">
      <div><h4>الدرجة الكلية</h4><p>من 100 = مجموع نقاط المحاور الثمانية (كل محور: نسبته × وزنه).
      حدود الحكم: <b>≥85</b> «قريب جدًا من Gemini 2.5 Pro في المقاييس دي» · <b>≥70</b> «قريب مع فجوات» ·
      <b>≥55</b> «متوسط» · أقل من كده «بعيد».
      <br><span class="mut">الدرجة وحدها مش كفاية: لو أي محور نزل عن حدّه الأدنى ⇒ <b>فشل حرج ⛔</b> حتى لو المجموع عالي.</span></p></div>
      <div><h4>حدود الدنيا</h4><p>العامية 60% · أسلوب Gemini 50% · المنطق 60% · الصدق 60% · الالتزام 60% ·
      التوثيق 50% · النقد 0% · الأدوات 50%.
      <br><span class="mut">الحد الأدنى = أقل نسبة مقبولة في المحور؛ النزول تحته بطل المحور كله.</span></p></div>
      <div class="{GEM_CLASS}"><h4>🎯 مرجع Gemini 2.5 Pro (عرض فقط ⛔)</h4>
      <p>أرقامه <b>بنشماركات عامة منشورة</b> لنفس النموذج (مش مقاسة على أسئلة امتحاننا)،
      اتحوّلت لتقدير لكل محور على سعة 0..100. «المسافة عن المرجع» = متوسط |فرق النسبة| على المحاور الثمانية
      (٠ = مطابق تماماً، الأقل = الأقرب).
      <br><span class="mut">⛔ <b>مالوش أي تأثير</b> في درجة أي نموذج ولا في الحكم ولا في حدود الدنيا.
      ومفيش «مجموع مرجعي» — لأن متوسط تقدير Gemini <b>مش درجة rubric</b>، فالمقارنة بالمجموع كانت هتبقى مقارنة بين قياسين مختلفين.
      وتقدر تطفئه كله من زر «إظهار مرجع Gemini» في أعلى التقرير، والاختيار بيتحفظ.</span></p></div>
      <div><h4>Fit والسرعة</h4><p>{fit_text}</p></div>
      <div><h4>فين تقارن الموديلات؟</h4><p><b>①</b> <a href="#cards">كارت لكل موديل</a> (الدرجة والحكم والمحاور) —
      <b>②</b> <a href="#radar">البصمة السداسية</a> (الشكل العام) —
      <b>③</b> <a href="#charts">رسوم المقارنة</a> (النسبة على كل محور + الجودة مقابل الزمن) —
      <b>④</b> <a href="#categories">المحاور الثمانية</a> (الوزن والحد الأدنى ونقطة كل موديل) —
      <b>⑤</b> <a href="#gates">حدود الدنيا</a> (مين نزل تحت الحد) —
      <b>⑥</b> <a href="#speed">جدول السرعة</a> (زمن كل سؤال × كل موديل) —
      <b>⑦</b> <a href="#answers">الإجابات جنب بعض</a> للمراجعة اللغوية.</p></div>
    </div>
  </details>
</section>
"""


# --------------------------------------------------------------------------- القالب
CSS = r"""
:root{
  --font:"Segoe UI",Tahoma,"Noto Kufi Arabic","Cairo",system-ui,-apple-system,sans-serif,"Segoe UI Emoji","Noto Color Emoji";
  --mono:ui-monospace,"Cascadia Mono","JetBrains Mono",Consolas,monospace;
  --bg:#060912; --fg:#e9eefc; --mut:#93a1bd; --dim:#64748b;
  --panel:rgba(17,25,42,.66); --panel2:rgba(11,17,30,.62); --inset:rgba(5,8,15,.55);
  --bd:rgba(148,163,184,.16); --bd2:rgba(148,163,184,.30); --hdr:rgba(6,9,18,.78);
  --cy:#22d3ee; --vi:#38bdf8; --bl:#60a5fa; --gr:#34d399; --am:#fbbf24; --rd:#fb7185;
  --grad:linear-gradient(135deg,#22d3ee 0%,#0ea5e9 50%,#14b8a6 100%);
  --ok:#34d399; --bad:#fb7185; --warn:#fbbf24;
  --okfg:#6ee7b7; --badfg:#fda4af; --warnfg:#fcd34d;
  --shadow:0 22px 60px -26px rgba(0,0,0,.95); --r:18px;
}
html[data-theme=light]{
  --bg:#eef2f9; --fg:#131a2a; --mut:#5b6883; --dim:#7b879f;
  --panel:rgba(255,255,255,.88); --panel2:rgba(255,255,255,.72); --inset:rgba(233,238,247,.92);
  --bd:rgba(15,23,42,.14); --bd2:rgba(15,23,42,.26); --hdr:rgba(240,244,251,.88);
  --shadow:0 16px 40px -24px rgba(15,23,42,.5); --okfg:#047857; --badfg:#be123c; --warnfg:#a16207;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;font:14px/1.7 var(--font);color:var(--fg);background:var(--bg);overflow-x:hidden;-webkit-font-smoothing:antialiased}
a{color:var(--cy);text-decoration:none}
b,strong{font-weight:750}
code{font:12px var(--mono);background:var(--inset);padding:1px 6px;border-radius:6px;color:var(--cy)}
.mut{color:var(--mut)} .small{font-size:12px} .num{font-family:var(--mono);font-variant-numeric:tabular-nums}
.bad{color:var(--bad)} .ok{color:var(--ok)} .up{color:var(--ok);font-weight:700} .down{color:var(--bad);font-weight:700}
.bg{position:fixed;inset:0;z-index:-3;background:
  radial-gradient(1100px 640px at 88% -12%,rgba(14,165,233,.30),transparent 62%),
  radial-gradient(880px 560px at 2% 6%,rgba(34,211,238,.22),transparent 60%),
  radial-gradient(1000px 760px at 46% 116%,rgba(20,184,166,.20),transparent 62%),
  linear-gradient(180deg,#050810,#070c17 45%,#050810)}
html[data-theme=light] .bg{background:
  radial-gradient(1000px 600px at 88% -12%,rgba(14,165,233,.16),transparent 62%),
  radial-gradient(820px 520px at 2% 6%,rgba(34,211,238,.16),transparent 60%),
  radial-gradient(900px 700px at 46% 116%,rgba(20,184,166,.12),transparent 62%),
  linear-gradient(180deg,#f4f7fd,#e9eef8)}
.bg::after{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(148,163,184,.055) 1px,transparent 1px),linear-gradient(90deg,rgba(148,163,184,.055) 1px,transparent 1px);background-size:46px 46px;-webkit-mask-image:radial-gradient(ellipse 90% 60% at 50% 0%,#000 12%,transparent 78%);mask-image:radial-gradient(ellipse 90% 60% at 50% 0%,#000 12%,transparent 78%)}
.orb{position:fixed;border-radius:50%;filter:blur(96px);opacity:.35;z-index:-2;pointer-events:none;animation:float 22s ease-in-out infinite}
.orb.a{width:420px;height:420px;top:-120px;inset-inline-end:-90px;background:#22d3ee}
.orb.b{width:380px;height:380px;bottom:-140px;inset-inline-start:-80px;background:#0d9488;animation-delay:-8s}
@keyframes float{0%,100%{transform:translate3d(0,0,0) scale(1)}50%{transform:translate3d(0,34px,0) scale(1.07)}}
header{position:sticky;top:0;z-index:40;display:flex;gap:14px;align-items:center;flex-wrap:wrap;padding:10px 22px;background:var(--hdr);backdrop-filter:blur(20px) saturate(1.5);-webkit-backdrop-filter:blur(20px) saturate(1.5);border-bottom:1px solid var(--bd)}
.brand{display:flex;align-items:center;gap:11px}
.logo{width:36px;height:36px;border-radius:12px;background:var(--grad);display:grid;place-items:center;box-shadow:0 8px 24px -8px rgba(14,165,233,.95);font-weight:800;color:#fff}
.brand h1{margin:0;font-size:15px;line-height:1.2} .brand small{display:block;color:var(--mut);font-size:11px}
nav{display:flex;gap:4px;flex-wrap:wrap;margin-inline-start:auto}
nav a{color:var(--mut);padding:6px 9px;border-radius:9px;font-size:12px;border:1px solid transparent}
nav a:hover{color:var(--fg);background:var(--inset);border-color:var(--bd)}
.btn{cursor:pointer;font:inherit;color:var(--fg);background:var(--inset);border:1px solid var(--bd2);padding:7px 12px;border-radius:10px}
.btn:hover{border-color:var(--cy);color:var(--cy)}
main{max-width:1320px;margin:0 auto;padding:26px 20px 60px}
.hero{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:stretch;margin-bottom:18px}
.hero-main{background:var(--panel);border:1px solid var(--bd);border-radius:var(--r);padding:26px;box-shadow:var(--shadow);position:relative;overflow:hidden}
.hero-main::after{content:"";position:absolute;inset:0;background:radial-gradient(600px 200px at 90% 0%,rgba(34,211,238,.14),transparent 70%);pointer-events:none}
.eyebrow{color:var(--cy);font-weight:700;font-size:12px;letter-spacing:.4px}
.hero h1{margin:6px 0 8px;font-size:clamp(24px,3.8vw,40px);line-height:1.2}
.grad{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.lead{color:var(--mut);max-width:70ch;margin:0 0 16px}
.chips{display:flex;gap:7px;flex-wrap:wrap}
.chip{display:inline-flex;gap:5px;align-items:center;background:var(--inset);border:1px solid var(--bd);border-radius:999px;padding:4px 10px;font-size:12px;color:var(--mut)}
.chip.sm{font-size:11px;padding:2px 8px}
.hero-side{display:flex;flex-direction:column;gap:12px;min-width:0}
/* أدوات التحكم في ظهور المراجع */
.ref-controls{display:flex;gap:14px;margin-bottom:4px;flex-wrap:wrap}
.ref-check{display:inline-flex;align-items:center;gap:6px;cursor:pointer;font-size:12.5px;color:var(--fg);padding:6px 10px;border-radius:8px;background:var(--panel);border:1px solid var(--bd);transition:background .15s}
.ref-check:hover{background:var(--inset)}
.ref-check input{accent-color:var(--cy);width:14px;height:14px}
/* ⛔ مرجع Gemini (عرض فقط): إطفاؤه يخفيه من الجداول والرسوم والبطاقات والنصوص معاً */
html[data-gem="off"] .gem-ref{display:none!important}
html[data-gem="off"] .ref-controls .ref-check{opacity:.65}
/* كروت المرجع: الهدف + المرجع الإضافي — كل واحد بيقول مصدره */
.ref-card{flex:1;display:flex;flex-direction:column;gap:6px;justify-content:center;
  background:var(--panel);border:1px solid var(--bd);border-radius:var(--r);padding:17px 18px;box-shadow:var(--shadow);min-width:0}
.ref-card.src-manual{border-color:rgba(167,139,250,.45);background:linear-gradient(160deg,rgba(167,139,250,.14),var(--panel))}
.ref-card.src-measured{border-color:rgba(251,191,36,.4);background:linear-gradient(160deg,rgba(251,191,36,.12),var(--panel))}
.ref-head{display:flex;align-items:center;gap:7px;color:var(--mut);font-size:11.5px;font-weight:700}
.ref-icon{font-size:14px}
.ref-name{font-weight:700;font-size:14.5px;overflow-wrap:anywhere}
.ref-score{font-size:30px;font-weight:800;line-height:1.1}
.ref-card.src-manual .ref-score{color:#c4b5fd}
.ref-card.src-measured .ref-score{color:var(--warn)}
.ref-score span{font-size:13px;color:var(--mut);font-weight:500}
.ref-axes{font-size:11px;color:var(--mut)}
/* ── السرعة المقيسة: أكبر رقم بارز في التقرير */
.speed-hero{margin-top:14px;padding:13px 16px;border-radius:14px;
  background:linear-gradient(135deg,rgba(34,211,238,.16),rgba(52,211,153,.10));
  border:1px solid rgba(34,211,238,.4);display:grid;gap:2px}
.speed-hero-head{display:flex;align-items:center;gap:7px;font-size:11.5px;font-weight:700;color:var(--cy)}
.speed-hero-icon{font-size:15px}
.speed-hero-value{font-size:40px;font-weight:800;line-height:1.05;color:var(--cy);
  text-shadow:0 0 22px rgba(34,211,238,.35)}
.speed-hero-unit{font-size:14px;font-weight:600;color:var(--mut);margin-inline-start:6px}
.speed-hero-sub{font-size:11.5px;color:var(--mut)}
.speed-hero-model{font-size:11px;color:var(--dim);direction:ltr;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* ── وسم «غير موثوق» على المحور ② */
.trust-flag{display:inline-flex;align-items:center;gap:3px;border-radius:999px;padding:1px 7px;
  font-size:10px;font-weight:800;background:rgba(251,113,133,.16);color:var(--badfg);border:1px solid rgba(251,113,133,.45);white-space:nowrap}
.axis-trust{display:inline-flex;align-items:center;gap:5px}
.mc-axis-v{display:flex;align-items:center;gap:4px}
.base-name{font-weight:700;font-size:15px}
.base-score{font-size:34px;font-weight:800;color:var(--warn)} .base-score span{font-size:14px;color:var(--mut);font-weight:500}
.base-gates{display:flex;gap:5px;flex-wrap:wrap}
.ref-verdict{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:0 0 26px}
.kpi{background:var(--panel);border:1px solid var(--bd);border-radius:14px;padding:14px 15px;position:relative;overflow:hidden;box-shadow:var(--shadow)}
.kpi::before{content:"";position:absolute;inset-inline:0;top:0;height:3px;background:var(--grad)}
.kpi-label{color:var(--mut);font-size:11px;font-weight:700;letter-spacing:.3px}
.kpi-value{font-size:19px;font-weight:800;margin-top:2px;line-height:1.35;word-break:break-word}
.kpi-value .unit{font-size:12px;color:var(--mut);margin-inline-start:2px}
.kpi-sub{color:var(--dim);font-size:11px;margin-top:3px}
.kpi-best .kpi-value{font-size:15px}
.kpi-delta::before{background:linear-gradient(90deg,var(--gr),var(--cy))}
.kpi-gates::before{background:linear-gradient(90deg,var(--rd),var(--am))}
.kpi-target::before{background:linear-gradient(90deg,#a78bfa,#c084fc)}
.kpi-target .kpi-value{font-size:15px}
.kpi-speed::before{background:linear-gradient(90deg,var(--cy),var(--gr))}
.kpi-speed .kpi-value{font-size:24px;color:var(--cy)}
.kpi-tok{font-weight:800}
.section{margin:0 0 30px;scroll-margin-top:70px}
.section-head{display:flex;justify-content:space-between;align-items:end;gap:14px;flex-wrap:wrap;margin:0 0 12px}
.section-head h2{margin:0;font-size:20px}
.sub{color:var(--mut);font-size:12px;margin:4px 0 0;max-width:95ch}
.card{background:var(--panel);border:1px solid var(--bd);border-radius:var(--r);box-shadow:var(--shadow)}
.table-wrap{overflow:auto;border:1px solid var(--bd);border-radius:14px;background:var(--panel2);box-shadow:var(--shadow)}
.tbl{width:100%;border-collapse:collapse;font-size:12.5px;min-width:760px}
.tbl th,.tbl td{padding:9px 10px;border-bottom:1px solid var(--bd);text-align:right;vertical-align:middle}
.tbl thead th{position:sticky;top:0;z-index:2;background:rgba(15,23,42,.94);color:#cbd5e1;font-size:11px;letter-spacing:.2px;white-space:nowrap}
html[data-theme=light] .tbl thead th{background:rgba(226,232,240,.98);color:#334155}
.tbl tbody tr:hover{background:rgba(34,211,238,.055)}
.tbl tbody tr:last-child td{border-bottom:0}
.tbl.compact th,.tbl.compact td{padding:7px 9px}
.model-cell{min-width:210px}
.model-name{font-weight:700;direction:ltr;text-align:right;unicode-bidi:plaintext;overflow-wrap:anywhere}
.rank{color:var(--mut);font-weight:700}
.score-cell{display:flex;align-items:center;gap:7px;min-width:100px}
.score-total{font-size:15px;font-weight:800}
.bar{height:9px;border-radius:999px;background:var(--inset);overflow:hidden;border:1px solid var(--bd);min-width:70px;flex:1}
.bar.sm{height:5px;min-width:42px}
.bar i{display:block;height:100%;background:var(--grad);border-radius:999px}
.verdict,.pill{display:inline-flex;align-items:center;gap:4px;border-radius:999px;padding:3px 9px;font-size:11px;font-weight:700;border:1px solid var(--bd);white-space:nowrap}
.verdict.v-ready,.verdict.v-good{background:rgba(52,211,153,.14);color:var(--okfg);border-color:rgba(52,211,153,.4)}
.verdict.v-ok{background:rgba(251,191,36,.14);color:var(--warnfg);border-color:rgba(251,191,36,.4)}
.verdict.v-weak{background:rgba(251,146,60,.15);color:#fdba74;border-color:rgba(251,146,60,.42)}
.verdict.v-bad,.verdict.v-fail{background:rgba(251,113,133,.15);color:var(--badfg);border-color:rgba(251,113,133,.42)}
.verdict.v-na,.pill.muted{background:var(--inset);color:var(--mut)}
.pill.v-good{color:var(--okfg);border-color:rgba(52,211,153,.4)} .pill.v-ok{color:var(--warnfg);border-color:rgba(251,191,36,.4)} .pill.v-bad{color:var(--badfg);border-color:rgba(251,113,133,.4)}
.gate{display:inline-flex;align-items:center;justify-content:center;min-width:34px;border-radius:7px;padding:2px 6px;font-size:10.5px;font-weight:800;border:1px solid var(--bd);margin:1px}
.gate.off{background:rgba(52,211,153,.10);color:var(--okfg);border-color:rgba(52,211,153,.35)}
.gate.on{background:rgba(251,113,133,.18);color:var(--badfg);border-color:rgba(251,113,133,.5)}
.legend{display:flex;gap:5px;align-items:center}
.failed-row{background:rgba(251,113,133,.055)}
.gate-fired{background:rgba(251,113,133,.055)}
.axis-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(430px,1fr));gap:14px}
.axis-card{padding:14px;overflow:hidden}
.axis-head{display:flex;justify-content:space-between;align-items:start;gap:10px;margin-bottom:8px;padding:10px 0}
.axis-head h3{margin:0;font-size:14px}
.axis-qcount{font-size:11px;color:var(--mut);background:var(--inset);border:1px solid var(--bd);border-radius:999px;padding:2px 8px;white-space:nowrap}
.heat-wrap{max-height:70vh}
.heat-tbl{min-width:680px}
.heat-tbl thead th.heat-q{text-align:right}
.heat-model{max-width:110px;overflow:hidden;text-overflow:ellipsis;direction:ltr;text-align:right}
.heat-q{max-width:310px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.heat{text-align:center!important;min-width:74px;font-family:var(--mono);transition:filter .15s}
.heat b{display:block;font-size:13px;line-height:1.2}
.heat small{display:block;font-size:10px;opacity:.85}
.heat:hover{filter:brightness(1.14)}
.heat.na{background:rgba(148,163,184,.06)!important;color:var(--dim)}
.heat-legend{display:flex;align-items:center;gap:6px;font-size:10px;color:var(--mut)}
.heat-legend i{display:block;width:34px;height:7px;border-radius:99px;background:linear-gradient(90deg,hsl(0,72%,38%),hsl(60,72%,38%),hsl(120,72%,38%))}
.qid{display:inline-flex;align-items:center;justify-content:center;min-width:30px;padding:1px 6px;border-radius:7px;background:var(--inset);border:1px solid var(--bd);color:var(--cy);font:700 11px var(--mono)}
.filters{display:flex;gap:10px;align-items:end;flex-wrap:wrap;padding:12px 13px;margin-bottom:12px;position:sticky;top:59px;z-index:20;backdrop-filter:blur(16px)}
.filters label{display:flex;flex-direction:column;gap:3px;font-size:11px;color:var(--mut);font-weight:700}
.filters .grow{flex:1;min-width:220px}
.filters select,.filters input{font:inherit;color:var(--fg);background:var(--inset);border:1px solid var(--bd2);border-radius:9px;padding:7px 9px;outline:none}
.filters input{width:100%}
.filters select:focus,.filters input:focus{border-color:var(--cy)}
.qblock{background:var(--panel);border:1px solid var(--bd);border-radius:14px;margin-bottom:9px;box-shadow:var(--shadow);overflow:hidden}
.qblock>summary{cursor:pointer;padding:11px 13px;display:flex;gap:9px;align-items:center;flex-wrap:wrap;list-style:none}
.qblock>summary::-webkit-details-marker{display:none}
.qblock>summary::after{content:"▾";margin-inline-start:auto;color:var(--mut);transition:transform .15s}
.qblock[open]>summary::after{transform:rotate(180deg)}
.qblock[open]>summary{border-bottom:1px solid var(--bd);background:var(--inset)}
.qtitle{font-weight:700}
.qprompt{color:var(--mut);font-size:12px;flex:1;min-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.qchips{display:flex;gap:4px;flex-wrap:wrap}
.answers-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:10px;padding:10px}
.answer-card{background:var(--panel2);border:1px solid var(--bd);border-radius:12px;padding:10px 11px;min-width:0}
.answer-card>header{display:flex;justify-content:space-between;gap:8px;align-items:start;margin-bottom:6px}
.ans-model{font-weight:700;font-size:12px;direction:ltr;text-align:right;unicode-bidi:plaintext;overflow-wrap:anywhere}
.ans-score{font-size:13px;white-space:nowrap}
.ans-meta{display:flex;gap:9px;flex-wrap:wrap;color:var(--dim);font-size:10.5px;margin-bottom:7px}
.answer-text{white-space:pre-wrap;word-break:break-word;background:var(--inset);border:1px solid var(--bd);border-radius:9px;padding:9px 10px;margin:0;font:12.5px/1.7 var(--font);max-height:420px;overflow:auto}
.reason{margin-top:7px;font-size:11px;color:var(--mut)}
.reason summary{cursor:pointer}
.reason pre{white-space:pre-wrap;background:var(--inset);border:1px solid var(--bd);border-radius:8px;padding:8px;max-height:220px;overflow:auto;font-size:11px}
.notes{margin-top:7px;font-size:11px;color:var(--mut);border-top:1px dashed var(--bd);padding-top:6px}
.notes.bad{color:var(--bad)}
/* ---------------------------------------------- الرسم السداسي + لوحة القرار */
.radar-layout{display:grid;grid-template-columns:minmax(360px,.95fr) minmax(360px,1.05fr);gap:14px;align-items:start}
/* الأعمدة لازم تقدر تصغر — من غير كده الجداول العريضة (min-width) بتمدّ الصفحة أفقياً */
.radar-layout>*{min-width:0}
.decision-panel>*{min-width:0}
.mc-grid>*{min-width:0}
.grid2>*{min-width:0}
.axis-grid>*{min-width:0}
.radar-card{padding:12px}
.radar-svg{width:100%;height:auto;max-height:520px;display:block}
.radar-ring{fill:none;stroke:rgba(148,163,184,.16);stroke-width:1}
.radar-ring.outer{stroke:rgba(148,163,184,.34);stroke-width:1.4}
.radar-spoke{stroke:rgba(148,163,184,.16);stroke-width:1}
.radar-label{fill:var(--mut);font:600 11.5px var(--font)}
.radar-tick{fill:var(--dim);font:10px var(--mono)}
.radar-target-poly{fill:rgba(192,132,252,.10);stroke:#c084fc;stroke-width:2.4;stroke-dasharray:3 4;stroke-linejoin:round}
.radar-target-dot{fill:#c084fc;stroke:#0b1120;stroke-width:1.4}
.radar-series .radar-poly{fill:color-mix(in srgb,var(--c) 18%,transparent);stroke:var(--c);stroke-width:2.2;stroke-linejoin:round;transition:fill-opacity .15s,opacity .15s}
.radar-series .radar-dot{fill:var(--c);stroke:#0b1120;stroke-width:1.6}
.radar-series.dim{opacity:.16}
.radar-series.hi .radar-poly{fill:color-mix(in srgb,var(--c) 34%,transparent);stroke-width:3}
.legend-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.legend-chip{display:inline-flex;align-items:center;gap:6px;font:inherit;font-size:11.5px;color:var(--fg);
  background:var(--inset);border:1px solid var(--bd);border-radius:999px;padding:3px 10px;cursor:pointer;max-width:100%}
.legend-chip:hover{border-color:var(--c,var(--cy))}
.legend-chip .dot{width:10px;height:10px;border-radius:50%;background:var(--c,var(--am));flex:none}
.legend-chip.base .dot{background:transparent;border:2px dashed var(--am)}
.legend-chip.target .dot{background:transparent;border:2px dotted #c084fc}
.legend-chip.target{border-color:rgba(192,132,252,.45);background:rgba(192,132,252,.10)}
.legend-chip .lc-badge{font-size:9.5px;font-weight:700;color:var(--mut);border:1px solid var(--bd);
  border-radius:999px;padding:0 6px;margin-inline-start:2px}
.legend-chip .lc-name{max-width:190px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;direction:ltr}
.legend-chip .lc-total{color:var(--mut)}
.base-source{margin-top:9px;padding:7px 10px;background:var(--inset);border:1px solid var(--bd);
  border-radius:10px;font-size:11.5px;line-height:1.7}
.base-source b{color:var(--am)}
.base-source.target-src b{color:#c084fc}
.base-source.target-src{border-color:rgba(192,132,252,.32);background:rgba(192,132,252,.08)}
.pill.target{border-color:rgba(192,132,252,.5);color:#d8b4fe;background:rgba(192,132,252,.12)}
/* ── كارت شريط الهدف (Gemini) — شكل زي كارت الموديل بس لون مميز */
.mc-card.target-card{border-color:rgba(192,132,252,.42);background:linear-gradient(160deg,rgba(192,132,252,.10),var(--panel))}
.mc-card.target-card .gauge .g-fill{stroke:#c084fc}
/* ── جدول الترتيب حسب القرب من الهدف */
.dist-bar{display:inline-block;width:70px;height:6px;border-radius:999px;background:var(--inset);
  overflow:hidden;vertical-align:middle;margin-inline-end:6px}
.dist-bar>i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--gr),#c084fc)}
.dist-val{font-weight:700}
/* ── سرعة التوليد: بارزة في الكروت والجداول */
.mc-v.tok-v{font-size:15px;font-weight:800;color:var(--cy)}
.tok-cell b{font-size:15px;font-weight:800;color:var(--cy)}
.tok-big{font-size:15px;font-weight:800;color:var(--cy)}
.tok-unit{font-size:10px;font-weight:600;color:var(--mut);margin-inline-start:3px}
.target-row{background:rgba(192,132,252,.08)}
.target-row td{border-top:1px solid rgba(192,132,252,.35)}
.delta-note{margin:7px 0 0;font-size:10.5px;line-height:1.6}
.perf-note{margin-top:12px}
.perf-note ul{margin:6px 0 0;padding-inline-start:18px}
.perf-note li{margin:3px 0;font-size:12px;line-height:1.75}
.decision-panel{display:grid;gap:12px}
/* ---------------------------------------------- كروت الموديلات + رسوم المقارنة */
.mc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:12px}
.mc-card{padding:13px 14px;display:flex;flex-direction:column;gap:10px}
.mc-head{display:flex;gap:12px;align-items:center}
.mc-gauge{position:relative;width:92px;height:92px;flex:none}
.mc-gauge .gauge{position:absolute;inset:0}
.gauge .g-track{stroke:var(--inset)}
.gauge .g-fill{stroke:url(#gradStroke);stroke:var(--cy)}
.mc-score{position:absolute;inset:0;display:grid;place-content:center;text-align:center;line-height:1.1}
.mc-score b{font-size:22px;font-weight:800;display:block}
.mc-score small{font-size:10px;color:var(--mut)}
.mc-title{min-width:0;flex:1}
.mc-title .model-name{font-size:13px}
.mc-verdict{margin-top:4px}
.mc-gates{margin-top:5px;display:flex;gap:3px;flex-wrap:wrap}
.mc-axes{display:flex;flex-direction:column;gap:5px}
.mc-axis{display:grid;grid-template-columns:78px 1fr 54px;gap:7px;align-items:center}
.mc-axis-l{font-size:11px;color:var(--mut)}
.mc-axis-v{font-size:10.5px;color:var(--dim);text-align:left}
.mc-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(96px,1fr));gap:7px;
  border-top:1px dashed var(--bd);padding-top:9px}
.mc-stat{display:flex;flex-direction:column;gap:1px;min-width:0}
.mc-k{font-size:10px;color:var(--dim)}
.mc-v{font-size:13px;font-weight:700;overflow-wrap:anywhere}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:12px}
.chart-card{padding:13px 14px;overflow:hidden}
.chart-svg{width:100%;height:auto;display:block}
.ch-grid{stroke:var(--bd);stroke-width:1;stroke-dasharray:3 4}
.ch-axis{stroke:var(--bd2);stroke-width:1.4}
.ch-tick{fill:var(--dim);font:10px var(--mono);direction:ltr}
.ch-label{fill:var(--mut);font:11px var(--font)}
.ch-val{fill:var(--fg);font:9.5px var(--mono)}
.ch-axis-title{fill:var(--mut);font:11px var(--font)}
.ch-base-label{fill:var(--am);font:10px var(--font)}
.ch-target{stroke:#c084fc;stroke-width:1.8;stroke-dasharray:3 4}
.ch-target-label{fill:#d8b4fe;font:700 10px var(--font)}
.ch-point-label{fill:var(--fg);font:10px var(--font);paint-order:stroke;stroke:var(--panel);stroke-width:3px}
.ch-dot{cursor:help}
.subhead{margin:16px 0 8px;font-weight:700;font-size:13px;color:var(--cy)}
.speed-tbl{min-width:1100px}
.speed-detail td small{display:block;font-size:9.5px;color:var(--dim);margin-top:1px}
.speed-detail td{min-width:88px;text-align:center!important}
.speed-detail .bad{font-size:11px}
.speed-detail .sp-model{max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;direction:ltr;text-align:center}
.decision-panel .card{padding:12px 14px}
.panel-title{margin:0 0 8px;font-size:14px}
.winners{display:flex;flex-wrap:wrap;gap:7px}
.winner{display:inline-flex;align-items:center;gap:7px;background:var(--inset);border:1px solid var(--bd);
  border-radius:10px;padding:5px 10px;font-size:11.5px}
.winner b{color:var(--cy)}
.winner-model{max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;direction:ltr;color:var(--mut)}
.delta-tbl td,.delta-tbl th{white-space:nowrap}
.delta-cell{display:flex;flex-direction:column;gap:2px;min-width:92px}
.dval{font-size:12px;font-weight:700}
.dtrack{position:relative;display:block;height:7px;background:var(--inset);border:1px solid var(--bd);border-radius:99px}
.dtrack::before{content:"";position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:var(--bd2)}
.dtrack i{position:absolute;top:0;bottom:0;border-radius:99px}
.dtrack i.pos{left:50%;background:linear-gradient(90deg,var(--gr),rgba(52,211,153,.35))}
.dtrack i.neg{right:50%;background:linear-gradient(270deg,var(--rd),rgba(251,113,133,.35))}
/* ---------------------------------------------- سجل الإجابات الكامل */
.tr-tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.tr-tools input{font:inherit;color:var(--fg);background:var(--inset);border:1px solid var(--bd2);border-radius:9px;padding:7px 10px;min-width:240px;outline:none}
.tr-tools input:focus{border-color:var(--cy)}
.tr-models{display:grid;gap:10px}
.model-tr>summary{cursor:pointer;display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:12px 14px;list-style:none}
.model-tr>summary::-webkit-details-marker{display:none}
.model-tr>summary::after{content:"▾";margin-inline-start:auto;color:var(--mut)}
.model-tr[open]>summary::after{transform:rotate(180deg)}
.model-tr[open]>summary{border-bottom:1px solid var(--bd)}
.tr-total{font-weight:800;font-size:14px;color:var(--warn)}
.tr-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:10px;padding:10px}
.tr-item{background:var(--panel2);border:1px solid var(--bd);border-radius:12px;padding:10px 12px;min-width:0}
.tr-head{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:5px}
.tr-title{font-weight:700}
.tr-axis{font-size:10.5px;color:var(--mut);background:var(--inset);border:1px solid var(--bd);border-radius:999px;padding:1px 8px}
.tr-score{margin-inline-start:auto;font-weight:700}
.tr-meta{display:flex;gap:9px;flex-wrap:wrap;color:var(--dim);font-size:10.5px;margin-bottom:7px}
.tr-part{margin-top:6px}
.tr-label{font-size:10.5px;font-weight:700;color:var(--cy);margin-bottom:3px}
.tr-text{white-space:pre-wrap;word-break:break-word;background:var(--inset);border:1px solid var(--bd);
  border-radius:9px;padding:8px 10px;font:12.5px/1.75 var(--font);max-height:340px;overflow:auto}
.tr-text.q{border-inline-start:3px solid var(--cy)}
.tr-text.think{border-inline-start:3px solid var(--vi);font-size:12px}
.tr-text.answer{border-inline-start:3px solid var(--gr)}
.tr-note{margin-top:4px;padding:5px 9px;border-inline-start:3px solid var(--vi);background:rgba(139,92,246,.07);
  border-radius:0 8px 8px 0;color:var(--dim);font-size:11px;line-height:1.6}
@media (max-width:1100px){.radar-layout{grid-template-columns:1fr}.tr-list{grid-template-columns:1fr}}
/* ---------------------------------------------- إعدادات الموديلات */
.set-grid-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(430px,1fr));gap:12px}
.set-card{padding:12px 14px}
.set-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px;padding:10px 0}
.set-grid{display:grid;grid-template-columns:auto 1fr;gap:4px 10px;font-size:11.5px}
.set-k{color:var(--mut);font-weight:700;white-space:nowrap}
.set-v{color:var(--fg);overflow-wrap:anywhere}
.warn-note{border-inline-start-color:var(--warn);background:rgba(251,191,36,.07)}
.meta-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px}
.meta-item{background:var(--panel);border:1px solid var(--bd);border-radius:11px;padding:9px 11px;min-width:0}
.meta-item.wide{grid-column:1/-1}
.meta-key{font-size:10.5px;color:var(--mut);font-weight:700}
.meta-val{margin-top:2px;font-size:12.5px;overflow-wrap:anywhere;unicode-bidi:plaintext}
.note{margin-top:12px;padding:13px 15px;font-size:12px;color:var(--mut);border-inline-start:3px solid var(--cy)}
.guide{padding:12px 15px}
.guide summary{cursor:pointer;list-style:none}
.guide summary::-webkit-details-marker{display:none}
.guide-h{font-size:20px;font-weight:800}
.guide-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-top:10px}
.guide h4{margin:0 0 3px;font-size:13px;color:var(--cy)}
.guide p{margin:0;color:var(--mut);font-size:12px}
footer{max-width:1320px;margin:0 auto;padding:0 20px 40px;color:var(--dim);font-size:11px;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
@media (max-width:900px){
  .hero{grid-template-columns:1fr}
  nav{display:none}
  main{padding:16px 12px 50px}
  .filters{position:static}
  .axis-grid{grid-template-columns:1fr}
  .kpis{grid-template-columns:repeat(auto-fit,minmax(140px,1fr))}
}
@media print{
  .bg,.orb,header nav,.filters,.btn{display:none!important}
  body{background:#fff;color:#111}
  .card,.table-wrap,.kpi,.hero-main{box-shadow:none;background:#fff;border-color:#ccc}
  .tbl thead th{background:#eee!important;color:#111!important}
  .section{break-inside:avoid}
  .answer-text{max-height:none}
}
"""

JS = r"""
(function(){
  const root=document.documentElement;
  const saved=localStorage.getItem("exam-theme");
  if(saved) root.setAttribute("data-theme",saved);
  const btn=document.getElementById("theme");
  if(btn) btn.addEventListener("click",()=>{
    const next=root.getAttribute("data-theme")==="light"?"dark":"light";
    root.setAttribute("data-theme",next); localStorage.setItem("exam-theme",next);
  });
  const printBtn=document.getElementById("print");
  if(printBtn) printBtn.addEventListener("click",()=>window.print());

  // ── إظهار/إخفاء مرجع Gemini (عرض فقط) مع حفظ الاختيار في localStorage
  //    كل عناصر المرجع عليها class="gem-ref" ⇒ CSS يخفيها كلها مرة واحدة
  //    (جداول + رسوم SVG + بطاقات + نصوص) من غير ما نلمس أي عنصر يدوي.
  function initGeminiToggle(){
    const check=document.getElementById("show-gemini");
    const root=document.documentElement;
    if(!check) return;
    const KEY="exam-show-gemini";
    const saved=localStorage.getItem(KEY);
    if(saved===null||saved==="true"||saved==="false"){
      check.checked=(saved!=="false");
    }else{
      check.checked=true;
    }
    function apply(){
      root.setAttribute("data-gem",check.checked?"on":"off");
      localStorage.setItem(KEY,check.checked?"true":"false");
    }
    apply();
    check.addEventListener("change",apply);
  }
  initGeminiToggle();

  // قبل الطباعة: افتح كل الأسئلة المقفولة عشان الـ PDF يحتوي كل الإجابات،
  // وبعد الطباعة رجّع الحالة الأصلية.
  window.addEventListener("beforeprint",()=>{
    document.querySelectorAll("details").forEach(d=>{
      d.dataset.prevOpen=d.open?"1":"0"; d.open=true;
    });
  });
  window.addEventListener("afterprint",()=>{
    document.querySelectorAll("details").forEach(d=>{
      if(d.dataset.prevOpen==="0") d.open=false;
    });
  });

  const selModel=document.getElementById("f-model");
  const selCat=document.getElementById("f-cat");
  const search=document.getElementById("f-search");
  const count=document.getElementById("f-count");
  const clear=document.getElementById("f-clear");
  function apply(){
    if(!selModel||!selCat||!search) return;
    const m=selModel.value, a=selCat.value, q=(search.value||"").trim().toLowerCase();
    let visible=0;
    document.querySelectorAll(".qblock").forEach(block=>{
      let any=false;
      block.querySelectorAll(".answer-card").forEach(card=>{
        const okModel=(m==="all"||card.dataset.model===m);
        const okCat=(a==="all"||card.dataset.cat===a);
        const okSearch=(!q||(card.dataset.search||"").includes(q));
        const show=okModel&&okCat&&okSearch;
        card.style.display=show?"":"none";
        if(show){any=true;visible++;}
      });
      block.style.display=any?"":"none";
      if(any&&q) block.open=true;
    });
    if(count) count.textContent=visible+" إجابة ظاهرة";
  }
  [selModel,selCat,search].forEach(el=>{if(el){el.addEventListener("input",apply);el.addEventListener("change",apply);}});
  if(clear) clear.addEventListener("click",()=>{if(selModel)selModel.value="all";if(selCat)selCat.value="all";if(search)search.value="";apply();});
  apply();

  // ── الرسم السداسي: تمرير الماوس على وسيلة الإيضاح ⇒ إبراز المضلّع
  const radar=document.querySelector(".radar-svg");
  document.querySelectorAll(".legend-chip[data-series]").forEach(chip=>{
    const target=chip.dataset.series;
    const hi=()=>{
      if(!radar) return;
      radar.querySelectorAll(".radar-series").forEach(g=>{
        g.classList.toggle("dim",g.dataset.series!==target);
        g.classList.toggle("hi",g.dataset.series===target);
      });
    };
    const off=()=>{
      if(!radar) return;
      radar.querySelectorAll(".radar-series").forEach(g=>g.classList.remove("dim","hi"));
    };
    chip.addEventListener("mouseenter",hi);
    chip.addEventListener("mouseleave",off);
    chip.addEventListener("focus",hi);
    chip.addEventListener("blur",off);
  });

  // ── سجل الإجابات الكامل: بحث + فتح/طي الكل
  const trSearch=document.getElementById("tr-search");
  function applyTr(){
    if(!trSearch) return;
    const q=(trSearch.value||"").trim().toLowerCase();
    document.querySelectorAll(".tr-item").forEach(it=>{
      it.style.display=(!q||(it.dataset.search||"").includes(q))?"":"none";
    });
  }
  if(trSearch){trSearch.addEventListener("input",applyTr);trSearch.addEventListener("change",applyTr);applyTr();}
  const trExpand=document.getElementById("tr-expand");
  const trCollapse=document.getElementById("tr-collapse");
  if(trExpand) trExpand.addEventListener("click",()=>document.querySelectorAll("details.model-tr").forEach(d=>{d.open=true;}));
  if(trCollapse) trCollapse.addEventListener("click",()=>document.querySelectorAll("details.model-tr").forEach(d=>{d.open=false;}));
})();
"""


def build_html(results: list[dict], exam_cfg: dict, run_meta: dict | None = None) -> str:
    run_meta = infer_runner_meta(run_meta, results)
    run_meta.setdefault("finished_at", now_iso())
    if not run_meta.get("platform"):
        run_meta["platform"] = "—"
    data = {
        "run": run_meta,
        "exam": {
            "version": exam_cfg.get("version"),
            "settings": exam_cfg.get("settings"),
            "categories": exam_cfg.get("categories"),
            "references": exam_cfg.get("references"),
        },
        "models": results,
    }
    payload = dump_json_for_html(data)
    title = "تقرير امتحان المساعد المصري — مقارنة موديلات GGUF"
    body = "".join(
        [
            _hero(results, exam_cfg, run_meta),
            _kpis(results, exam_cfg, run_meta),
            _summary_table(results, exam_cfg),
            model_cards_section(results, exam_cfg),
            radar_section(results, exam_cfg),
            charts_section(results, exam_cfg),
            _categories_section(results, exam_cfg),
            _heatmap(results, exam_cfg),
            _gates_section(results),
            _perf_section(results, run_meta),
            speed_table_section(results, exam_cfg),
            _fit_section(results, run_meta),
            settings_section(results, exam_cfg),
            _answers_section(results, exam_cfg),
            transcripts_section(results, exam_cfg),
            _meta_section(results, exam_cfg, run_meta),
            _guide(run_meta),
        ]
    )
    return f"""<!doctype html>
<html lang="ar" dir="rtl" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light">
<title>{esc(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="bg"></div><div class="orb a"></div><div class="orb b"></div>
<header>
  <div class="brand"><div class="logo">AI</div><div><h1>AI Online Tester</h1><small>امتحان المساعد المصري · تقرير حتمي</small></div></div>
  <nav>
    <a href="#overview">نظرة عامة</a><a href="#results">المقارنة</a><a href="#cards">النتيجة لكل موديل</a>
    <a href="#radar">الرسم السداسي</a><a href="#charts">رسوم المقارنة</a>
    <a href="#categories">المحاور</a>
    <a href="#heatmap">خريطة الدرجات</a><a href="#gates">حدود الدنيا</a>
    <a href="#perf">الأداء المقيس</a><a href="#speed">جدول السرعة</a><a href="#fit">الملاءمة</a>
    <a href="#settings">الإعدادات</a>
    <a href="#answers">الإجابات</a><a href="#transcripts">سجل الإجابات</a><a href="#meta">البيانات</a>
    <a href="#guide">دليل القراءة</a>
  </nav>
  <button class="btn" id="theme" type="button" title="تبديل الوضع">🌓</button>
  <button class="btn" id="print" type="button">🖨 طباعة / PDF</button>
</header>
<main>{body}</main>
<footer>
  <span>تم التوليد تلقائياً بواسطة <b>scripts/html_report.py</b> — بدون ملفات JSON وسيطة.</span>
  <span>{esc(run_meta.get("run_id") or "")} · {esc(run_meta.get("finished_at") or "")}</span>
</footer>
<noscript><div style="padding:10px 22px;color:#fbbf24">JavaScript متعطل — الجداول والإجابات كلها ظاهرة، الفلاتر فقط مش هتشتغل.</div></noscript>
<script type="application/json" id="exam-data">{payload}</script>
<script>{JS}</script>
</body>
</html>
"""


def write_report(
    results: list[dict],
    path: str | Path,
    exam_cfg: dict,
    run_meta: dict | None = None,
) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_html(results, exam_cfg, run_meta), encoding="utf-8")
    return p


__all__ = ["build_html", "write_report"]
