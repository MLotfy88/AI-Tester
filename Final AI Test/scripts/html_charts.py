"""الرسوم البيانية وسجل الإجابات الكامل لتقرير HTML.

كل الرسوم هنا **SVG خالص** مولّد من Python:
  · مفيش Chart.js ولا CDN ولا أي ملف خارجي — التقرير ملف واحد مستقل.
  · الرسم السداسي (Hexagon/Radar) لمقارنة الموديلات على 6 محاور.
  · جدول الفروق عن خط الأساس (بار تفاضلي) — أداة القرار السريعة.
  · سجل الإجابات: نص السؤال + نص التفكير + نص الإجابة لكل موديل.
"""
from __future__ import annotations

import html
import math
import re
from typing import Any

from common import human_bytes
from references import (
    TARGET_COLOR,
    source_badge,
    target_config,
    target_gap,
    target_radar_values,
    target_ranking,
)

# --------------------------------------------------------------------------- ثابت
CHART_COLORS = [
    "#22d3ee", "#60a5fa", "#34d399", "#fbbf24", "#fb7185",
    "#a78bfa", "#f472b6", "#2dd4bf", "#facc15", "#c084fc",
]

# أبعاد الرسم السداسي (6 محاور ⇒ سداسي حقيقي)
RADAR_DIMS: tuple[tuple[str, str], ...] = (
    ("1", "① اللهجة"),
    ("2", "② الأمانة"),
    ("3", "③ الشغل"),
    ("4", "④ المهارات"),
    ("total", "المجموع"),
    ("ar", "نسبة العامية"),
)

AXIS_LABELS = ("① اللهجة", "② الأمانة", "③ الشغل", "④ المهارات")


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


def _num(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


# --------------------------------------------------------------------------- الرسم السداسي
def _radar_coords(values: list[float], cx: float, cy: float, radius: float) -> list[tuple[float, float]]:
    n = len(values)
    coords: list[tuple[float, float]] = []
    for i, value in enumerate(values):
        angle = math.radians(-90 + i * 360.0 / n)
        r = radius * max(0.0, min(100.0, float(value))) / 100.0
        coords.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return coords


def _radar_polygon(values: list[float], cx: float, cy: float, radius: float) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in _radar_coords(values, cx, cy, radius))


def radar_values(exam: dict | None, axes_cfg: dict) -> list[float]:
    """قيم الموديل على أبعاد الرسم السداسي (كلها من 0 إلى 100)."""
    exam = exam or {}
    axes = exam.get("axes") or {}
    values: list[float] = []
    for key, _label in RADAR_DIMS:
        if key == "total":
            values.append(float(exam.get("total") or 0.0))
        elif key == "ar":
            values.append(float(exam.get("ar_ratio") or 0.0) * 100.0)
        else:
            axis = axes.get(key) or {}
            maxv = axis.get("max") or (axes_cfg.get(key) or {}).get("max")
            values.append(_pct(axis.get("score"), maxv) or 0.0)
    return values


def baseline_radar_values(base: dict | None, axes_cfg: dict, models: list[dict]) -> list[float]:
    """قيم خط الأساس — نسبة العامية بتجيبها من ناتج التصحيح لو موجودة."""
    base = base or {}
    base_axes = base.get("axes") or {}
    ar_ratio = base.get("ar_ratio")
    if ar_ratio is None:
        for result in models:
            exam = result.get("exam") or {}
            ar_ratio = (exam.get("baseline") or {}).get("ar_ratio")
            if ar_ratio is not None:
                break
    values: list[float] = []
    for key, _label in RADAR_DIMS:
        if key == "total":
            values.append(float(base.get("total") or 0.0))
        elif key == "ar":
            values.append(float(ar_ratio or 0.0) * 100.0)
        else:
            maxv = (axes_cfg.get(key) or {}).get("max")
            values.append(_pct(base_axes.get(key), maxv) or 0.0)
    return values


def _model_key(name: str) -> str:
    """مفتاح تطبيع لاسم الموديل — للمقارنة بدون ترقيم ولا مسار ولا لاحقة.

    شيل أي تعليق بين قوسين («خط الأساس» · «مقاس آلياً» · «baseline») عشان
    الاسم البسيط (اسم الملف) هو اللي بيتقارن.
    """
    text = Path_name(str(name or ""))
    text = re.sub(r"\.gguf$", "", text, flags=re.I)
    text = re.sub(r"\s*\([^)]*\)\s*", " ", text)
    text = re.sub(r"[^0-9A-Za-z\u0600-\u06FF]+", "_", text.strip().lower())
    return text.strip("_")


def measured_baseline_model(
    results: list[dict], exam_cfg: dict
) -> tuple[dict | None, str]:
    """يلاقي الموديل المرجعي **المقاس فعلاً في نفس التشغيل** (مش المنشور).

    لو الموديل الأساس (Qwen3.5-4B) موجود ضمن الموديلات اللي اتقست، نستخدم أرقامه
    المقاسة (بنفس السياسة ⇒ مقارنة صحيحة 100%). وإلا نرجع للمنشور ونقول إن كده.

    المطابقة بثلاث طرق (من الأقوى للأدق):
      1. الاسم فيه علامة «خط الأساس» صراحةً.
      2. **اسم الملف بعد التطبيع** (نفس الـ repo + نفس الـ quant) — ده اللي بيخلّي
         الموديل المحلي `...\\Qwen3.5-4B-IQ4_XS.gguf` يتعرّف عليه.
      3. الدرجة المنشورة (61.6) — fallback قديم.
    """
    base = _baseline(exam_cfg)
    base_name = str(base.get("name") or "")
    base_total = float(base.get("total") or 0.0)
    if not base_name:
        return None, ""
    base_key = _model_key(base_name)
    for result in results:
        if not result.get("exam"):
            continue
        name = str(result.get("model") or "")
        model_key = _model_key(name)
        is_baseline = "خط الأساس" in name or name.endswith("(baseline)")
        if not is_baseline and base_key and model_key and model_key == base_key:
            is_baseline = True
        if not is_baseline and base_total:
            total = float((result.get("exam") or {}).get("total") or 0.0)
            if abs(total - base_total) < 0.01:
                is_baseline = True
        if is_baseline:
            return result, "مقاس في هذا التشغيل"
    return None, "منشور في ورقة الامتحان §0.6"


def radar_svg(
    series: list[dict],
    baseline_values: list[float] | None,
    target_values: list[float] | None = None,
    target_label: str = "شريط الهدف",
) -> str:
    """رسم SVG سداسي: كل موديل مضلّع + خط الأساس المتقطّع + شريط الهدف.

    · خط الأساس (المقاس آلياً / المنشور) = متقطّع كهرماني.
    · شريط الهدف (Gemini 2.5 Pro)        = بنفسجي منقّط (مصدره معلن في الـlegend).
    """
    width, height = 560, 450
    cx, cy, radius = 280, 220, 155
    n = len(RADAR_DIMS)
    out = [
        '<svg class="radar-svg" viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" '
        'role="img" aria-label="مقارنة سداسية بين الموديلات">' % (width, height)
    ]
    for level in (20, 40, 60, 80, 100):
        pts = _radar_polygon([float(level)] * n, cx, cy, radius)
        cls = "radar-ring" + (" outer" if level == 100 else "")
        out.append(f'<polygon class="{cls}" points="{pts}"/>')
    for i, (_key, label) in enumerate(RADAR_DIMS):
        angle = math.radians(-90 + i * 360.0 / n)
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        out.append(f'<line class="radar-spoke" x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}"/>')
        lx = cx + (radius + 36) * math.cos(angle)
        ly = cy + (radius + 36) * math.sin(angle)
        anchor = "middle"
        if math.cos(angle) > 0.25:
            anchor = "start"
        elif math.cos(angle) < -0.25:
            anchor = "end"
        out.append(
            f'<text class="radar-label" x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="{anchor}">{esc(label)}</text>'
        )
    for level in (20, 40, 60, 80, 100):
        y = cy - radius * level / 100.0
        out.append(f'<text class="radar-tick" x="{cx + 5}" y="{y + 3:.1f}">{level}</text>')
    if baseline_values:
        pts = _radar_polygon(baseline_values, cx, cy, radius)
        out.append(
            '<polygon class="radar-baseline" points="%s"><title>خط الأساس (مصدره معلن في الأسفل)</title></polygon>'
            % pts
        )
    if target_values:
        pts = _radar_polygon(target_values, cx, cy, radius)
        dots = "".join(
            f'<circle class="radar-target-dot" cx="{x:.1f}" cy="{y:.1f}" r="3.2"/>'
            for x, y in _radar_coords(target_values, cx, cy, radius)
        )
        out.append(
            f'<g class="radar-target"><title>{esc(target_label)} — شريط الهدف (مصدره معلن في الأسفل)</title>'
            f'<polygon class="radar-target-poly" points="{pts}"/>{dots}</g>'
        )
    for idx, item in enumerate(series):
        pts = _radar_polygon(item["values"], cx, cy, radius)
        tip = item["model"] + " — " + " · ".join(
            f"{label}: {value:.1f}" for (_k, label), value in zip(RADAR_DIMS, item["values"])
        )
        dots = "".join(
            f'<circle class="radar-dot" cx="{x:.1f}" cy="{y:.1f}" r="3.6"/>'
            for x, y in _radar_coords(item["values"], cx, cy, radius)
        )
        out.append(
            f'<g class="radar-series" data-series="s{idx}" style="--c:{item["color"]}">'
            f"<title>{esc(tip)}</title>"
            f'<polygon class="radar-poly" points="{pts}"/>{dots}</g>'
        )
    out.append("</svg>")
    return "".join(out)


# --------------------------------------------------------------------------- فرق عن الأساس
def _delta_cell(delta: float, maximum: float) -> str:
    cls = "up" if delta > 0 else ("down" if delta < 0 else "mut")
    sign = "+" if delta > 0 else ""
    width = min(50.0, abs(delta) / maximum * 50.0) if maximum else 0.0
    bar_cls = "pos" if delta > 0 else ("neg" if delta < 0 else "")
    bar = f'<i class="{bar_cls}" style="width:{width:.1f}%"></i>' if bar_cls else ""
    return (
        f'<div class="delta-cell"><span class="dval {cls} num" dir="ltr">{sign}{delta:.2f}</span>'
        f'<span class="dtrack">{bar}</span></div>'
    )


def delta_matrix(results: list[dict], exam_cfg: dict) -> str:
    """جدول الفروق عن خط الأساس: سطر لكل موديل، عمود لكل محور.

    خط الأساس هنا = **الموديل المرجعي المقاس في نفس التشغيل** لو موجود
    (⇒ مقارنة على نفس السياسة وعلى نفس الجهاز ⇒ صحيحة 100%).
    وإلا = الأرقام المنشورة في ورقة الامتحان §0.6.
    """
    axes_cfg = exam_cfg.get("axes") or {}
    measured, base_source = measured_baseline_model(results, exam_cfg)
    if measured:
        base_exam = measured.get("exam") or {}
        base_total = float(base_exam.get("total") or 0.0)
        base_axes = {
            k: float((base_exam.get("axes") or {}).get(k, {}).get("score") or 0.0)
            for k in ("1", "2", "3", "4")
        }
        base_name = str(measured.get("model") or "خط الأساس")
    else:
        published = _baseline(exam_cfg)
        base_total = float(published.get("total") or 0.0)
        base_axes = {k: float(v) for k, v in (published.get("axes") or {}).items()}
        base_name = str(published.get("name") or "خط الأساس")

    rows: list[str] = []
    for result in _ok_models(results):
        if measured and result is measured:
            continue
        exam = result.get("exam") or {}
        axes = exam.get("axes") or {}
        cells: list[str] = []
        for key in ("1", "2", "3", "4"):
            maxv = float((axes_cfg.get(key) or {}).get("max") or 0.0)
            model_score = float((axes.get(key) or {}).get("score") or 0.0)
            base_score = float(base_axes.get(key) or 0.0)
            cells.append(_delta_cell(model_score - base_score, maxv))
        total = float(exam.get("total") or 0.0)
        cells.append(_delta_cell(total - base_total, 100.0))
        rows.append(
            f'<tr><td class="model-cell"><div class="model-name">{esc(result.get("model"))}</div>'
            f'<div class="mut small num" dir="ltr">{_num(total, 2)}/100</div></td>'
            + "".join(f"<td>{cell}</td>" for cell in cells)
            + "</tr>"
        )
    if base_total:
        zeros = "".join('<td><div class="delta-cell"><span class="dval mut num" dir="ltr">0.00</span>'
                        '<span class="dtrack"></span></div></td>' for _ in range(5))
        rows.append(
            f'<tr class="baseline-row"><td class="model-cell"><div class="model-name">{esc(base_name)}</div>'
            f'<div class="mut small">خط الأساس · {esc(base_source)}</div></td>{zeros}</tr>'
        )

    note = (
        "الفروق محسوبة **نفس الموديل المرجعي المقاس في نفس التشغيل** "
        "⇒ المقارنة على نفس السياسة ونفس الجهاز."
        if measured
        else "الفروق محسوبة مقابل الأرقام **المنشورة** في ورقة الامتحان §0.6 "
        "(مقياس baseline — اقرأ §مبدأ المقارنة)."
    )
    return f"""
<div class="table-wrap">
  <table class="tbl compact delta-tbl">
    <thead><tr><th>الموديل</th><th>Δ ① اللهجة</th><th>Δ ② الأمانة</th><th>Δ ③ الشغل</th>
      <th>Δ ④ المهارات</th><th>Δ المجموع</th></tr></thead>
    <tbody>{''.join(rows) or '<tr><td colspan="6" class="mut">مفيش نتائج.</td></tr>'}</tbody>
  </table>
</div>
<p class="mut small delta-note">{note}</p>
"""


def axis_winners(results: list[dict], exam_cfg: dict) -> str:
    """«الأفضل في كل محور» — أسرع طريقة للقرار."""
    axes_cfg = exam_cfg.get("axes") or {}
    chips: list[str] = []
    for key, label in (("1", "① اللهجة"), ("2", "② الأمانة"), ("3", "③ الشغل"), ("4", "④ المهارات")):
        best = None
        best_score = -1.0
        for result in _ok_models(results):
            axis = ((result.get("exam") or {}).get("axes") or {}).get(key) or {}
            score = float(axis.get("score") or 0.0)
            if score > best_score:
                best, best_score = result, score
        if best is None:
            continue
        maxv = float((axes_cfg.get(key) or {}).get("max") or 0.0)
        pct = _pct(best_score, maxv) or 0.0
        chips.append(
            f'<span class="winner"><b>{esc(label)}</b><span class="winner-model">{esc(best.get("model"))}</span>'
            f'<span class="num" dir="ltr">{_num(best_score, 1)}/{_num(maxv, 0)} ({_num(pct, 0)}%)</span></span>'
        )
    return "".join(chips)


# --------------------------------------------------------------------------- الأقسام
def target_ranking_table(results: list[dict], exam_cfg: dict) -> str:
    """«🎯 الأقرب لشريط الهدف» — ترتيب الموديلات من الأقرب للهدف للأبعد.

    **المسافة** = متوسط فرق النسبة على المحاور الأربعة (٠ = مطابق تماماً).
    الأرقام المقروءة من `config/exam.yaml → target` (معايرة يدوية).
    """
    target = target_config(exam_cfg)
    if not target:
        return '<p class="mut small">مفيش شريط هدف معرّف في الإعدادات.</p>'
    ranked = target_ranking(results, exam_cfg)
    if not ranked:
        return '<p class="mut small">مفيش نتائج.</p>'
    rows: list[str] = []
    for i, row in enumerate(ranked, 1):
        result = row["result"]
        gap = row["gap"]
        exam = result.get("exam") or {}
        distance = float(row["distance"])
        # كل ما المسافة قلّت ⇒ الشريط يمتلئ أكتر (قرب أعلى)
        near = max(0.0, min(1.0, 1.0 - distance / 100.0))
        cells = "".join(
            f'<td class="num" dir="ltr">{_num(gap["axis_pct"].get(k), 1)}</td>'
            for k in ("1", "2", "3", "4")
        )
        rows.append(
            f'<tr><td class="rank num" dir="ltr">{i}</td>'
            f'<td class="model-cell"><div class="model-name" title="{esc(result.get("model_full") or result.get("model"))}">{esc(result.get("model"))}</div></td>'
            f'<td class="num" dir="ltr">{_num(exam.get("total"), 1)}</td>'
            f"{cells}"
            f'<td class="num" dir="ltr">{_num(gap["total"], 1)}</td>'
            f'<td><span class="dist-bar" title="المسافة {distance:.1f}">'
            f'<i style="width:{near * 100:.1f}%"></i></span>'
            f'<span class="num dist-val" dir="ltr">{_num(distance, 1)}</span></td></tr>'
        )
    return f"""
<div class="table-wrap">
  <table class="tbl compact target-tbl">
    <thead><tr><th>#</th><th>الموديل</th><th>المجموع</th>
      <th>Δ ① %</th><th>Δ ② %</th><th>Δ ③ %</th><th>Δ ④ %</th>
      <th>Δ المجموع</th><th>المسافة (قرب)</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</div>
<p class="mut small delta-note">Δ = فرق النسبة عن شريط الهدف <b>{esc(str(target.get("name") or ""))}</b>
  (<span class="pill target">{esc(source_badge(target))}</span>) — موجب = أعلى من الهدف.
  <b>المسافة</b> = متوسط |Δ| على المحاور الأربعة · الأقل = الأقرب.</p>
"""


def radar_section(results: list[dict], exam_cfg: dict) -> str:
    """قسم الرسم السداسي + لوحة القرار."""
    models = _ok_models(results)
    if not models:
        return ""
    axes_cfg = exam_cfg.get("axes") or {}
    series: list[dict] = []
    for i, result in enumerate(models):
        exam = result.get("exam") or {}
        series.append(
            {
                "id": f"s{i}",
                "model": result.get("model") or f"موديل {i + 1}",
                "values": radar_values(exam, axes_cfg),
                "color": CHART_COLORS[i % len(CHART_COLORS)],
                "total": exam.get("total"),
                "verdict": exam.get("verdict"),
            }
        )

    # ── خط الأساس: الموديل المرجعي **المقاس في نفس التشغيل** لو موجود،
    #    وإلا الأرقام المنشورة. المهم: نعرف المستخدم مصدر الخط ده.
    published = _baseline(exam_cfg)
    measured, base_source = measured_baseline_model(results, exam_cfg)
    if measured:
        base_values = radar_values(measured.get("exam") or {}, axes_cfg)
        base_label = str(measured.get("model") or "خط الأساس")
        base_total = (measured.get("exam") or {}).get("total")
    else:
        base_values = baseline_radar_values(published, axes_cfg, models)
        base_label = str(published.get("name") or "خط الأساس")
        base_total = published.get("total")

    # ── شريط الهدف (Gemini 2.5 Pro): مرجع «معايرة يدوية» — بيبان في كل رسم
    target = target_config(exam_cfg)
    target_values = target_radar_values(target, axes_cfg) if target else None
    target_total = target.get("total")
    svg = radar_svg(series, base_values, target_values, str(target.get("name") or "شريط الهدف"))

    legend = "".join(
        f'<button type="button" class="legend-chip" data-series="{item["id"]}" style="--c:{item["color"]}">'
        f'<i class="dot"></i><span class="lc-name">{esc(item["model"])}</span>'
        f'<span class="lc-total num" dir="ltr">{_num(item["total"], 1)}</span></button>'
        for item in series
    )
    base_badge = "مقاس في هذا التشغيل" if measured else "منشور (§0.6)"

    # ── شرائح المراجع في الـlegend: خط الأساس + شريط الهدف
    target_chip = ""
    if target:
        target_chip = (
            f'<span class="legend-chip target" title="{esc(str(target.get("note") or ""))}">'
            f'<i class="dot"></i><span class="lc-name">{esc(target.get("name") or "شريط الهدف")}</span>'
            f'<span class="lc-total num" dir="ltr">{_num(target_total, 1)}</span>'
            f'<span class="lc-badge">{esc(source_badge(target))}</span></span>'
        )

    return f"""
<section class="section" id="radar">
  <div class="section-head">
    <div><h2>⬡ البصمة السداسية للموديلات</h2>
      <p class="sub">كل مضلّع = موديل واحد على 6 محاور (اللهجة، الأمانة، الشغل، المهارات، المجموع، نسبة العامية).
      مرّر الماوس على أي مضلّع لتشوف أرقامه. المتقطّع الكهرماني = خط الأساس، والمنقّط البنفسجي = شريط الهدف (Gemini 2.5 Pro).</p></div>
  </div>
  <div class="radar-layout">
    <div class="card radar-card">
      {svg}
      <div class="legend-chips">{legend}
        <span class="legend-chip base" title="خط الأساس: {esc(base_source)}"><i class="dot"></i>
          <span class="lc-name">خط الأساس</span>
          <span class="lc-total num" dir="ltr">{_num(base_total, 1)}</span></span>
        {target_chip}
      </div>
      <div class="base-source">
        <b>خط الأساس في الرسم:</b> {esc(base_label)} — <span class="pill muted">{esc(base_badge)}</span>
        <div class="mut small">{esc(base_source)}</div>
      </div>
      {f'<div class="base-source target-src"><b>شريط الهدف في الرسم:</b> {esc(str(target.get("name") or ""))} — <span class="pill target">{esc(source_badge(target))}</span><div class="mut small">{esc(str(target.get("note") or ""))}</div></div>' if target else ''}
    </div>
    <div class="decision-panel">
      <div class="card">
        <h3 class="panel-title">🏅 الأفضل في كل محور</h3>
        <div class="winners">{axis_winners(results, exam_cfg) or '<span class="mut">مفيش نتائج.</span>'}</div>
      </div>
      <div class="card">
        <h3 class="panel-title">📏 الفرق عن خط الأساس (نقاط)</h3>
        <p class="mut small">الأخضر = أعلى من الأساس · الأحمر = أقل. النص = الفرق بالنقاط من 100.</p>
        {delta_matrix(results, exam_cfg)}
      </div>
      <div class="card">
        <h3 class="panel-title">🎯 الأقرب لشريط الهدف ({esc(str(target.get("name") or "الهدف"))})</h3>
        <p class="mut small">المسافة = متوسط فرق النسبة على المحاور الأربعة (٠ = مطابق تماماً). **الأقل = الأقرب للهدف.**</p>
        {target_ranking_table(results, exam_cfg)}
      </div>
      <div class="card note">
        <b>طريقة القراءة:</b> لو المضلّع <b>داخلي</b> خط الأساس ⇒ أضعف. لو خارجي ومساحة أكبر ⇒ أفضل.
        ولو المضلّع مش متساوي ⇒ فيه محور ضعيف حتى لو المجموع عالي — وده بالظبط اللي بيفرق في القرار.
        وقارن المضلّع بالمنقّط البنفسجي (الهدف) عشان تعرف قد إيه بقيت من الفجوة.
      </div>
    </div>
  </div>
</section>
"""


def transcripts_section(results: list[dict], exam_cfg: dict) -> str:
    """سجل الإجابات الكامل: نص السؤال + نص التفكير + نص الإجابة لكل موديل."""
    models = _ok_models(results)
    if not models:
        return ""
    questions = exam_cfg.get("questions") or []

    blocks: list[str] = []
    for m_index, result in enumerate(models):
        exam = result.get("exam") or {}
        qrows = exam.get("questions") or {}
        items: list[str] = []
        for q in questions:
            qid = str(q.get("id"))
            row = qrows.get(qid) or {}
            prompt = str(row.get("prompt") or q.get("prompt") or "")
            reasoning = str(row.get("reasoning") or "")
            answer = str(row.get("answer") or "")
            notes = "؛ ".join(row.get("notes") or [])
            health = "، ".join(row.get("health") or [])
            blob = " ".join(
                [qid, str(q.get("title") or ""), prompt, reasoning, answer, notes, str(result.get("model") or "")]
            ).lower()
            think_block = (
                f'<div class="tr-text think">{esc(reasoning)}</div>'
                if reasoning
                else '<div class="tr-text think muted">— لا يوجد نص تفكير: التشغيل بوضع بلا تفكير '
                '(enable_thinking=false) حسب ورقة الامتحان §0.1 —</div>'
            )
            if reasoning and not row.get("think_visible"):
                think_block += (
                    '<div class="tr-note">↳ النص ده رجع في قناة reasoning_content منفصلة '
                    "(مش ظاهر للمستخدم) — مش محتسب ضمن G5 حسب ورقة الامتحان §52.</div>"
                )
            answer_block = (
                f'<div class="tr-text answer">{esc(answer)}</div>'
                if answer
                else '<div class="tr-text answer bad">— رد فاضي (G6) —</div>'
            )
            items.append(
                f"""
<article class="tr-item" data-search="{esc(blob)}">
  <header class="tr-head">
    <span class="qid">{esc(qid)}</span>
    <span class="tr-title">{esc(q.get("title"))}</span>
    <span class="tr-axis">محور {esc(row.get("axis") or "—")}</span>
    <span class="tr-score num" dir="ltr">{_num(row.get("score"), 1)}/{_num(row.get("max"), 0)}</span>
  </header>
  <div class="tr-meta">
    <span>{esc(row.get("chars") or 0)} حرف</span>
    <span>{esc(row.get("tokens") if row.get("tokens") is not None else "—")} توكن</span>
    <span>{_num(row.get("seconds"), 1)} ث</span>
    <span>{esc(row.get("finish") or "—")}</span>
    {f'<span class="bad small">⚠ {esc(health)}</span>' if health else ""}
  </div>
  <div class="tr-part"><div class="tr-label">📝 نص السؤال</div><div class="tr-text q">{esc(prompt)}</div></div>
  <div class="tr-part"><div class="tr-label">🧠 نص التفكير</div>{think_block}</div>
  <div class="tr-part"><div class="tr-label">💬 نص الإجابة</div>{answer_block}</div>
  {f'<div class="notes"><b>ملاحظات المصحح:</b> {esc(notes)}</div>' if notes else ""}
  {f'<div class="notes bad">خطأ تشغيل: {esc(row.get("error"))}</div>' if row.get("error") else ""}
</article>"""
            )
        total = exam.get("total")
        blocks.append(
            f"""
<details class="card model-tr" data-model="m{m_index}" {'open' if m_index == 0 else ''}>
  <summary>
    <span class="ans-model">{esc(result.get("model"))}</span>
    <span class="tr-total num" dir="ltr">{_num(total, 1)}/100</span>
    <span class="verdict-mut mut small">{esc(exam.get("verdict") or "")}</span>
    <span class="mut small">{len(items)} سؤال</span>
  </summary>
  <div class="tr-list">{''.join(items)}</div>
</details>"""
        )

    return f"""
<section class="section" id="transcripts">
  <div class="section-head">
    <div><h2>🗂 سجل الإجابات الكامل</h2>
      <p class="sub">كل موديل: نص السؤال + نص التفكير + نص الإجابة كما وصل من الخادم —
      عشان تراجع بنفسك العامية المصرية والجودة اللغوية قبل ما تقرر.</p></div>
    <div class="tr-tools">
      <input id="tr-search" type="search" placeholder="بحث في الأسئلة والتفكير والإجابات…">
      <button type="button" class="btn" id="tr-expand">فتح الكل</button>
      <button type="button" class="btn" id="tr-collapse">طي الكل</button>
    </div>
  </div>
  <div class="tr-models">{''.join(blocks)}</div>
</section>
"""


# --------------------------------------------------------------------------- إعدادات الموديلات
def settings_section(results: list[dict], exam_cfg: dict) -> str:
    """الإعدادات الفعلية لكل موديل + تحذير لو اختلفت القوالب بين الموديلات."""
    models = _ok_models(results)
    if not models:
        return ""
    rows: list[str] = []
    templates: dict[str, str] = {}
    for result in models:
        st = result.get("settings") or {}
        runtime = result.get("runtime") or {}
        template = str(st.get("chat_template") or runtime.get("template") or "—")
        templates[template] = template
        rec = st.get("recommended_sampling") or {}
        applied = st.get("applied") or []
        warnings = st.get("warnings") or []
        rows.append(
            f"""
<article class="card set-card">
  <header class="set-head">
    <div class="ans-model">{esc(result.get("model"))}</div>
    <span class="pill muted">{esc(st.get("source") or "—")}</span>
  </header>
  <div class="set-grid">
    <div class="set-k">القالب</div><div class="set-v" dir="ltr">{esc(Path_name(template))}</div>
    <div class="set-k">مصدر القالب</div><div class="set-v">{esc(st.get("template_source") or runtime.get("template_mode") or "—")}</div>
    <div class="set-k">KV cache</div><div class="set-v" dir="ltr">{esc(st.get("kv_cache_type") or runtime.get("kv") or "—")}</div>
    <div class="set-k">flash-attn</div><div class="set-v" dir="ltr">{esc(st.get("flash_attn") or runtime.get("flash_attn") or "—")}</div>
    <div class="set-k">ngl (offload)</div><div class="set-v num" dir="ltr">{esc(st.get("n_gpu_layers") if st.get("n_gpu_layers") is not None else runtime.get("ngl", "—"))}</div>
    <div class="set-k">threads</div><div class="set-v num" dir="ltr">{esc(st.get("threads") if st.get("threads") is not None else runtime.get("threads", "—"))}</div>
    <div class="set-k">device</div><div class="set-v" dir="ltr">{esc(st.get("device") or runtime.get("device") or "—")}</div>
    <div class="set-k">Sampling مطبّق</div>
    <div class="set-v num" dir="ltr">temp={esc(runtime.get("temperature", "—"))} · top_p={esc(runtime.get("top_p", "—"))} · seed={esc(runtime.get("seed", "—"))}</div>
    <div class="set-k">توصيات المطوّر</div>
    <div class="set-v">{" · ".join(f"{k}={v}" for k, v in rec.items()) or "—"}
      <span class="mut small">[{esc(st.get("sampling_source") or "none")}]</span></div>
  </div>
  {f'<div class="notes"><b>مطبّق:</b> {esc(" · ".join(applied))}</div>' if applied else ""}
  {f'<div class="notes bad"><b>تنبيهات:</b> {esc(" · ".join(warnings))}</div>' if warnings else ""}
</article>"""
        )
    banner = ""
    if len(templates) > 1:
        banner = (
            '<div class="card note warn-note"><b>⚠ تحذير قابلية المقارنة:</b> الموديلات استخدمت قوالب مختلفة '
            f'({esc(" ، ".join(sorted(templates)))}). المقارنة بين الموديلات في هذه الحالة تقريبية — '
            "للمقارنة المطلقة ثبّت <code>--template-mode exam</code> لكل الموديلات.</div>"
        )
    return f"""
<section class="section" id="settings">
  <div class="section-head">
    <div><h2>⚙️ الإعدادات الفعلية لكل موديل</h2>
      <p class="sub">اللي اتشغّل بيه فعلياً: قالب المحادثة، KV، offload، threads، device، وخلاصة الـ flags.
      إعدادات الامتحان الثابتة (temp/seed/ctx) واحدة للجميع؛ الباقي ممكن يتغيّر حسب الموديل.</p></div>
  </div>
  {banner}
  <div class="set-grid-cards">{''.join(rows)}</div>
</section>
"""


# --------------------------------------------------------------------------- رسوم المقارنة
def _gauge_svg(pct: float | None, size: int = 92) -> str:
    """مقياس دائري (donut) لنسبة 0–100 — SVG خالص."""
    try:
        value = max(0.0, min(100.0, float(pct or 0.0)))
    except (TypeError, ValueError):
        value = 0.0
    half = size / 2.0
    radius = half - 7
    circumference = 2 * math.pi * radius
    dash = circumference * value / 100.0
    return (
        f'<svg class="gauge" viewBox="0 0 {size} {size}" width="{size}" height="{size}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{value:.0f}%">'
        f'<circle class="g-track" cx="{half}" cy="{half}" r="{radius:.1f}" fill="none" stroke-width="7"/>'
        f'<circle class="g-fill" cx="{half}" cy="{half}" r="{radius:.1f}" fill="none" stroke-width="7" '
        f'stroke-linecap="round" stroke-dasharray="{dash:.1f} {circumference:.1f}" '
        f'transform="rotate(-90 {half} {half})"/></svg>'
    )


def grouped_bar_svg(
    categories: list[str],
    series: list[dict],
    *,
    width: int = 780,
    height: int = 330,
    y_max: float = 100.0,
    y_suffix: str = "%",
) -> str:
    """أعمدة مجمّعة: كل مجموعة = محور، وكل لون = موديل.

    series = [{"label": str, "color": str, "values": [float|None]}]
    """
    if not categories or not series:
        return ""
    pad_l, pad_r, pad_t, pad_b = 52, 14, 16, 54
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    out = [
        f'<svg class="chart-svg" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="مقارنة الأعمدة">'
    ]
    # المحور Y + الشبكة
    for level in range(0, 5):
        value = y_max * level / 4.0
        y = pad_t + plot_h - plot_h * (value / y_max if y_max else 0)
        out.append(f'<line class="ch-grid" x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}"/>')
        out.append(
            f'<text class="ch-tick" x="{pad_l - 7}" y="{y + 4:.1f}" text-anchor="end">{value:.0f}{esc(y_suffix)}</text>'
        )
    out.append(f'<line class="ch-axis" x1="{pad_l}" y1="{pad_t + plot_h}" x2="{width - pad_r}" y2="{pad_t + plot_h}"/>')

    group_w = plot_w / max(1, len(categories))
    n_series = len(series)
    bar_gap = 2.0
    bar_w = max(3.0, (group_w * 0.74) / max(1, n_series) - bar_gap)
    for gi, category in enumerate(categories):
        gx = pad_l + group_w * gi + group_w * 0.13
        for si, item in enumerate(series):
            values = item.get("values") or []
            value = values[gi] if gi < len(values) else None
            if value is None:
                continue
            try:
                v = float(value)
            except (TypeError, ValueError):
                continue
            bar_h = plot_h * max(0.0, min(v / y_max if y_max else 0, 1.0))
            x = gx + si * (bar_w + bar_gap)
            y = pad_t + plot_h - bar_h
            tip = f"{item.get('label')} · {category}: {v:.1f}{y_suffix}"
            out.append(
                f'<rect class="ch-bar" x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                f'rx="3" fill="{esc(item.get("color"))}"><title>{esc(tip)}</title></rect>'
            )
            if bar_w >= 26:
                out.append(
                    f'<text class="ch-val" x="{x + bar_w / 2:.1f}" y="{max(pad_t + 9, y - 4):.1f}" '
                    f'text-anchor="middle">{v:.0f}</text>'
                )
        out.append(
            f'<text class="ch-label" x="{pad_l + group_w * gi + group_w / 2:.1f}" y="{height - pad_b + 18:.1f}" '
            f'text-anchor="middle">{esc(category)}</text>'
        )
    out.append("</svg>")
    return "".join(out)


def scatter_svg(
    points: list[dict],
    *,
    width: int = 620,
    height: int = 380,
    x_label: str = "",
    y_label: str = "",
    x_max: float | None = None,
    y_max: float = 100.0,
    baseline_y: float | None = None,
    target_y: float | None = None,
    target_label: str = "شريط الهدف",
) -> str:
    """مخطط انتشار: الجودة (y) ضد الزمن/السرعة (x) — أداة القرار للمقارنة.

    خطان أفقيان مرجعيان:
      · خط الأساس (كهرماني متقطّع).
      · شريط الهدف — Gemini 2.5 Pro (بنفسجي منقّط).
    """
    if not points:
        return ""
    pad_l, pad_r, pad_t, pad_b = 58, 20, 18, 52
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    xs = [float(p["x"]) for p in points if p.get("x") is not None]
    ys = [float(p["y"]) for p in points if p.get("y") is not None]
    if not xs or not ys:
        return ""
    x_hi = float(x_max) if x_max else max(xs) * 1.15
    if x_hi <= 0:
        x_hi = 1.0
    y_hi = float(y_max) if y_max else max(ys) * 1.1

    def sx(v: float) -> float:
        return pad_l + plot_w * (max(0.0, min(v, x_hi)) / x_hi)

    def sy(v: float) -> float:
        return pad_t + plot_h - plot_h * (max(0.0, min(v, y_hi)) / y_hi)

    out = [
        f'<svg class="chart-svg" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="الجودة مقابل الزمن">'
    ]
    for level in range(0, 5):
        value = y_hi * level / 4.0
        y = sy(value)
        out.append(f'<line class="ch-grid" x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}"/>')
        out.append(
            f'<text class="ch-tick" x="{pad_l - 7}" y="{y + 4:.1f}" text-anchor="end">{value:.0f}</text>'
        )
    for level in range(0, 5):
        value = x_hi * level / 4.0
        x = sx(value)
        out.append(f'<text class="ch-tick" x="{x:.1f}" y="{pad_t + plot_h + 16:.1f}" text-anchor="middle">{value:.0f}</text>')
    out.append(f'<line class="ch-axis" x1="{pad_l}" y1="{pad_t + plot_h}" x2="{width - pad_r}" y2="{pad_t + plot_h}"/>')
    out.append(f'<line class="ch-axis" x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + plot_h}"/>')

    if baseline_y is not None:
        by = sy(float(baseline_y))
        out.append(
            f'<line class="ch-baseline" x1="{pad_l}" y1="{by:.1f}" x2="{width - pad_r}" y2="{by:.1f}">'
            f"<title>خط الأساس: {float(baseline_y):.1f}</title></line>"
        )
        out.append(
            f'<text class="ch-base-label" x="{width - pad_r - 4}" y="{by - 6:.1f}" text-anchor="end">خط الأساس</text>'
        )

    if target_y is not None:
        ty = sy(float(target_y))
        out.append(
            f'<line class="ch-target" x1="{pad_l}" y1="{ty:.1f}" x2="{width - pad_r}" y2="{ty:.1f}">'
            f"<title>{esc(target_label)}: {float(target_y):.1f}</title></line>"
        )
        out.append(
            f'<text class="ch-target-label" x="{pad_l + 4}" y="{ty - 6:.1f}" text-anchor="start">'
            f"{esc(target_label)}</text>"
        )

    placed: list[tuple[float, float, float]] = []  # (x_center, y, half_width)
    for p in points:
        if p.get("x") is None or p.get("y") is None:
            continue
        x, y = sx(float(p["x"])), sy(float(p["y"]))
        color = p.get("color") or "#22d3ee"
        tip = str(p.get("tip") or p.get("label") or "")
        label = str(p.get("short") or "")
        out.append(
            f'<circle class="ch-dot" cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{esc(color)}" '
            f'fill-opacity=".26" stroke="{esc(color)}" stroke-width="2.4"><title>{esc(tip)}</title></circle>'
        )
        if not label:
            continue
        # ── تفادي تداخل التسميات: لو-label فوقي قريبة ⇒ انزلها تحت النقطة
        half = max(24.0, len(label) * 3.2)
        lx = min(max(x, pad_l + half * 0.4), width - pad_r - half * 0.4)
        ly = y - 15
        for (px, py, phalf) in placed:
            if abs(lx - px) < (half + phalf) * 0.85 and abs(ly - py) < 13:
                ly = y + 24
                break
        placed.append((lx, ly, half))
        out.append(
            f'<text class="ch-point-label" x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle">{esc(label)}</text>'
        )
    if x_label:
        out.append(
            f'<text class="ch-axis-title" x="{pad_l + plot_w / 2:.1f}" y="{height - 10}" text-anchor="middle">{esc(x_label)}</text>'
        )
    if y_label:
        out.append(
            f'<text class="ch-axis-title" x="14" y="{pad_t + plot_h / 2:.1f}" text-anchor="middle" '
            f'transform="rotate(-90 14 {pad_t + plot_h / 2:.1f})">{esc(y_label)}</text>'
        )
    out.append("</svg>")
    return "".join(out)


# --------------------------------------------------------------------------- النتائج لكل موديل
def _short_model(name: str, limit: int = 26) -> str:
    """اسم موديل مختصر للعرض في الرسوم والجداول."""
    text = Path_name(str(name or ""))
    text = text.replace(".gguf", "")
    # شيل علامات مثل «(خط الأساس)» — بتخلي الاسم أطول من اللازم
    text = re.sub(r"\s*\(\s*(?:خط\s*الأساس|baseline)\s*\)\s*", " ", text, flags=re.I)
    text = text.strip()
    return text[:limit] if text else "—"


def _verdict_class(verdict: Any) -> str:
    """تصنيف CSS للحكم — نفس منطق html_report (مفيش استيراد دائري)."""
    text = str(verdict or "")
    if "غير موثوق" in text or "مرفوض" in text or "خطير" in text:
        return "v-bad"
    if "جاهز" in text:
        return "v-ready"
    if "ممتاز" in text:
        return "v-good"
    if "مقبول" in text:
        return "v-ok"
    if "ضعيف" in text:
        return "v-weak"
    return "v-na"


def _target_reference_card(exam_cfg: dict) -> str:
    """كارت **شريط الهدف** (Gemini 2.5 Pro) — مرجع مكتمل زي كارت الموديل.

    بيظهر جنب كروت الموديلات عشان المقارنة تكون مباشرة: نفس الشكل، ونفس
    المحاور الأربعة، بس عليه وسم «هدف» ومصدر معلن (معايرة يدوية).
    """
    target = target_config(exam_cfg)
    if not target:
        return ""
    axes_cfg = exam_cfg.get("axes") or {}
    total = float(target.get("total") or 0.0)
    t_axes = target.get("axes") or {}

    axis_bars = ""
    for key, label in (
        ("1", "① اللهجة"),
        ("2", "② الأمانة"),
        ("3", "③ الشغل"),
        ("4", "④ المهارات"),
    ):
        maxv = float((axes_cfg.get(key) or {}).get("max") or 0.0)
        score = float(t_axes.get(key) or 0.0)
        pct = _pct(score, maxv) or 0.0
        axis_bars += (
            f'<div class="mc-axis"><span class="mc-axis-l">{esc(label)}</span>'
            f'<span class="bar sm"><i style="width:{pct:.1f}%"></i></span>'
            f'<span class="num mc-axis-v" dir="ltr">{_num(score, 1)}/{_num(maxv, 0)}</span></div>'
        )

    try:
        ar = float(target.get("ar_ratio") or 0.0) * 100.0
    except (TypeError, ValueError):
        ar = 0.0

    return f"""
<article class="card mc-card target-card">
  <header class="mc-head">
    <div class="mc-gauge">{_gauge_svg(total)}
      <div class="mc-score"><b class="num" dir="ltr">{_num(total, 1)}</b><small>/100</small></div>
    </div>
    <div class="mc-title">
      <div class="model-name">🎯 {esc(target.get("name") or "شريط الهدف")}</div>
      <div class="mut small">شريط الهدف — ليس موديلاً مُشغّلاً</div>
      <div class="mc-verdict"><span class="verdict {_verdict_class(target.get("verdict"))}">{esc(str(target.get("verdict") or "—"))}</span></div>
      <div class="mc-gates"><span class="pill target">{esc(source_badge(target))}</span></div>
    </div>
  </header>
  <div class="mc-axes">{axis_bars}</div>
  <div class="mc-stats">
    <div class="mc-stat"><span class="mc-k">نسبة العامية</span><span class="mc-v num" dir="ltr">{_num(ar, 1)}%</span></div>
    <div class="mc-stat"><span class="mc-k">المصدر</span><span class="mc-v">{esc(source_badge(target))}</span></div>
  </div>
  <div class="base-source target-src"><b>ملاحظة:</b> {esc(str(target.get("note") or ""))}</div>
</article>"""


def model_cards_section(results: list[dict], exam_cfg: dict) -> str:
    """«النتيجة لكل موديل» — كارت واحد لكل موديل بالدرجة والمحاور والسرعة.

    ده المقابل لـ «النتيجة لكل موديل × وضع» في التقرير المرجعي:
    عندنا «الوضع» = الموديل نفسه (كل موديل بيشتغل بإعداداته)،
    فالكارت يعرض كل التفاصيل اللي محتاجها قبل ما تقرر.
    """
    models = _ok_models(results)
    if not models:
        return ""
    axes_cfg = exam_cfg.get("axes") or {}
    published = _baseline(exam_cfg)
    base_total = float(published.get("total") or 0.0)
    measured, _base_source = measured_baseline_model(results, exam_cfg)
    if measured:
        base_total = float((measured.get("exam") or {}).get("total") or 0.0)

    # ── شريط الهدف (Gemini 2.5 Pro): مرجع «معايرة يدوية» — بتظهر معاه المسافة
    target = target_config(exam_cfg)
    target_total = float(target.get("total") or 0.0) if target else 0.0

    cards: list[str] = []
    for index, result in enumerate(models):
        exam = result.get("exam") or {}
        runtime = result.get("runtime") or {}
        perf = runtime.get("perf") or {}
        fit = result.get("fit") or {}
        manifest = result.get("manifest") or {}
        total = float(exam.get("total") or 0.0)
        verdict = str(exam.get("verdict") or "—")
        delta = total - base_total if base_total else None
        tg = (perf.get("tg_tps") or {}).get("avg")
        ttft = (perf.get("ttft_ms") or {}).get("avg")
        req = (perf.get("request_seconds") or {}).get("avg")
        ar = float(exam.get("ar_ratio") or 0.0) * 100.0
        # المسافة عن شريط الهدف (Gemini) — أقل = أقرب
        gap = target_gap(exam, target, axes_cfg) if target else {"total": None, "distance": None}
        gap_total = gap.get("total")
        distance = gap.get("distance")

        # شرائط المحاور الأربعة
        axis_bars = ""
        for key, label in (
            ("1", "① اللهجة"),
            ("2", "② الأمانة"),
            ("3", "③ الشغل"),
            ("4", "④ المهارات"),
        ):
            axis = (exam.get("axes") or {}).get(key) or {}
            score = float(axis.get("score") or 0.0)
            maxv = float(axis.get("max") or (axes_cfg.get(key) or {}).get("max") or 0.0)
            pct = _pct(score, maxv) or 0.0
            trust = str(axis.get("trust_flag") or "")
            trust_html = (
                f'<span class="trust-flag" title="{esc(str(axis.get("trust_note") or ""))}">{esc(trust)}</span>'
                if trust
                else ""
            )
            axis_bars += (
                f'<div class="mc-axis"><span class="mc-axis-l">{esc(label)}</span>'
                f'<span class="bar sm"><i style="width:{pct:.1f}%"></i></span>'
                f'<span class="num mc-axis-v" dir="ltr">{_num(score, 1)}/{_num(maxv, 0)}{trust_html}</span></div>'
            )

        fired = [g.get("code") for g in (exam.get("gates") or []) if g.get("fired")]
        gates_html = (
            "".join(f'<span class="gate on">{esc(g)}</span>' for g in fired)
            or '<span class="gate off">سليمة</span>'
        )
        delta_html = (
            f'<span class="{"up" if delta >= 0 else "down"}" dir="ltr">{"+" if delta >= 0 else ""}{delta:.2f}</span>'
            if delta is not None
            else "—"
        )
        # سطر تحت الاسم: الكمية + حجم الملف
        quant = str(manifest.get("quant_pattern") or "")
        file_name = Path_name(str(manifest.get("primary_path") or fit.get("file") or ""))
        subtitle_parts = []
        if quant and quant.lower() != "local":
            subtitle_parts.append(esc(quant))
        elif file_name:
            subtitle_parts.append(esc(file_name))
        subtitle = " · ".join(subtitle_parts) or "—"

        cards.append(
            f"""
<article class="card mc-card" data-model="m{index}">
  <header class="mc-head">
    <div class="mc-gauge">{_gauge_svg(total)}
      <div class="mc-score"><b class="num" dir="ltr">{_num(total, 1)}</b><small>/100</small></div>
    </div>
    <div class="mc-title">
      <div class="model-name" title="{esc(result.get('model_full') or result.get('model'))}">{esc(result.get('model'))}</div>
      <div class="mut small">{subtitle}</div>
      <div class="mc-verdict"><span class="verdict {_verdict_class(verdict)}">{esc(verdict)}</span></div>
      <div class="mc-gates">{gates_html}</div>
    </div>
  </header>
  <div class="mc-axes">{axis_bars}</div>
  <div class="mc-stats">
    <div class="mc-stat"><span class="mc-k">Δ عن الأساس</span><span class="mc-v">{delta_html}</span></div>
    <div class="mc-stat"><span class="mc-k">Δ عن الهدف (Gemini)</span><span class="mc-v {"" if gap_total is None else ("up" if gap_total >= 0 else "down")}" dir="ltr">{"" if gap_total is None else ("+" if gap_total >= 0 else "") + format(gap_total, ".2f")}</span></div>
    <div class="mc-stat"><span class="mc-k">المسافة عن الهدف</span><span class="mc-v num" dir="ltr">{_num(distance, 1)}</span></div>
    <div class="mc-stat"><span class="mc-k">نسبة العامية</span><span class="mc-v num" dir="ltr">{_num(ar, 1)}%</span></div>
    <div class="mc-stat"><span class="mc-k">⚡ توليد tok/s (مقيس)</span><span class="mc-v tok-v num" dir="ltr">{_num(tg, 1)}</span></div>
    <div class="mc-stat"><span class="mc-k">أول استجابة ms</span><span class="mc-v num" dir="ltr">{_num(ttft, 0)}</span></div>
    <div class="mc-stat"><span class="mc-k">زمن الطلب s</span><span class="mc-v num" dir="ltr">{_num(req, 1)}</span></div>
    <div class="mc-stat"><span class="mc-k">حجم الموديل</span><span class="mc-v num" dir="ltr">{esc(human_bytes(manifest.get("total_bytes") or 0))}</span></div>
  </div>
</article>"""
        )

    # ── كارت شريط الهدف أول الكروت (مرجع واضح + مصدر معلن)
    target_card = _target_reference_card(exam_cfg)
    if target_card:
        cards.insert(0, target_card)

    base_note = (
        "خط الأساس = الموديل المرجعي **المقاس في نفس التشغيل** (المقارنة على نفس السياسة ونفس الجهاز)."
        if measured
        else "خط الأساس = الأرقام **المنشورة** في ورقة الامتحان §0.6."
    )
    target_note = (
        f"🎯 **شريط الهدف** = {esc(str(target.get('name') or ''))} "
        f"(<span class=\"pill target\">{esc(source_badge(target))}</span>) — "
        "أرقامه **معايرة يدوية** مش مقيسة، و«المسافة عن الهدف» = متوسط فرق النسبة "
        "على المحاور الأربعة (٠ = مطابق تماماً، **الأقل = الأقرب**)."
        if target
        else ""
    )
    return f"""
<section class="section" id="cards">
  <div class="section-head">
    <div><h2>🏅 النتيجة لكل موديل</h2>
      <p class="sub">كارت لكل موديل: الدرجة والحكم والمحاور الأربعة والبوابات المفعّلة والأداء المقيس.
      {base_note} {target_note}</p></div>
  </div>
  <div class="mc-grid">{''.join(cards)}</div>
</section>
"""


def speed_table_section(results: list[dict], exam_cfg: dict) -> str:
    """«⚡ جدول السرعة» — زمن كل سؤال + سرعة التوليد لكل موديل جنب بعض.

    الأرقام **مقيسة فعلياً** (من `timings` الخاص بـ llama.cpp ومن أوقات الطلبات).
    """
    models = _ok_models(results)
    if not models:
        return ""
    questions = exam_cfg.get("questions") or []

    # ── الجدول الأول: ملخص لكل موديل
    summary_rows: list[str] = []
    for result in models:
        runtime = result.get("runtime") or {}
        perf = runtime.get("perf") or {}
        tg = perf.get("tg_tps") or {}
        pp = perf.get("pp_tps") or {}
        req = perf.get("request_seconds") or {}
        ttft = perf.get("ttft_ms") or {}
        pm = perf.get("prompt_ms") or {}
        pred = perf.get("predicted_ms") or {}
        summary_rows.append(
            f"""
<tr>
  <td class="model-cell"><div class="model-name" title="{esc(result.get('model_full') or result.get('model'))}">{esc(result.get('model'))}</div></td>
  <td class="num" dir="ltr">{_num((ttft.get('avg')), 0)}</td>
  <td class="num" dir="ltr">{_num((pm.get('avg')), 0)}</td>
  <td class="num" dir="ltr">{_num((pred.get('avg')), 0)}</td>
  <td class="num" dir="ltr">{_num((req.get('avg')), 1)}</td>
  <td class="num tok-cell" dir="ltr"><b>{_num((tg.get('avg')), 1)}</b></td>
  <td class="num" dir="ltr">{_num((tg.get('min')), 1)}</td>
  <td class="num" dir="ltr">{_num((tg.get('max')), 1)}</td>
  <td class="num" dir="ltr">{_num((pp.get('avg')), 1)}</td>
  <td class="num" dir="ltr">{_num((perf.get('total_generated_tokens')), 0)}</td>
  <td class="num" dir="ltr">{_num((perf.get('seconds_total')), 0)}</td>
  <td class="num" dir="ltr">{_num((perf.get('startup_seconds')), 0)}</td>
  <td class="num" dir="ltr">{esc(runtime.get('peak_rss_mib') or '—')}</td>
  <td class="num" dir="ltr">{esc(runtime.get('peak_vram_mib') or '—')}</td>
</tr>"""
        )

    # ── صف مرجعي: شريط الهدف (Gemini 2.5 Pro) — مش مُشغّل محلياً ⇒ السرعة غير مقيسة
    target = target_config(exam_cfg)
    if target:
        dashes = "".join('<td class="num" dir="ltr">—</td>' for _ in range(13))
        summary_rows.append(
            f"""
<tr class="target-row">
  <td class="model-cell"><div class="model-name">🎯 {esc(target.get('name') or 'شريط الهدف')}</div>
    <div class="mut small">{esc(source_badge(target))} — شريط هدف، مش موديل مُشغّل على الجهاز</div></td>
  {dashes}
</tr>"""
        )

    # ── الجدول الثاني: زمن كل سؤال × كل موديل
    detail_head = "".join(
        f"<th class='sp-model' title='{esc(r.get('model'))}'>{esc(_short_model(r.get('model') or '', 24))}</th>"
        for r in models
    )
    detail_rows: list[str] = []
    for q in questions:
        qid = str(q.get("id"))
        cells: list[str] = []
        for result in models:
            row = ((result.get("exam") or {}).get("questions") or {}).get(qid) or {}
            seconds = row.get("seconds")
            tokens = row.get("tokens")
            tps = None
            try:
                if seconds and tokens:
                    tps = float(tokens) / float(seconds)
            except (TypeError, ValueError, ZeroDivisionError):
                tps = None
            finish = str(row.get("finish") or "")
            tip = f"{qid} · {result.get('model')} · {seconds if seconds is not None else '—'}s · {tokens or '—'} tok"
            flag = ""
            if finish == "length":
                flag = ' <span class="bad" title="بلغ الحد الأقصى">⚠</span>'
            cells.append(
                f'<td class="num" dir="ltr" title="{esc(tip)}">{_num(seconds, 1)}'
                f'<small>{_num(tps, 1)} tok/s</small>{flag}</td>'
            )
        detail_rows.append(
            f"<tr><th class='heat-q'><span class='qid'>{esc(qid)}</span> {esc(q.get('title'))}</th>"
            f"{''.join(cells)}</tr>"
        )

    return f"""
<section class="section" id="speed">
  <div class="section-head">
    <div><h2>⚡ جدول السرعة</h2>
      <p class="sub">كل الأرقام هنا **مقيسة فعلياً** أثناء التشغيل — من `timings` الخاص بـ llama.cpp
      ومن أوقات الطلبات الحقيقية. مفيش تقدير رياضي. كل الموديلات اشتغلت على نفس الجهاز ⇒ المقارنة عدلانة.</p></div>
  </div>
  <div class="table-wrap">
    <table class="tbl compact speed-tbl">
      <thead><tr>
        <th>الموديل</th><th>أول استجابة ms</th><th>معالجة prompt ms</th><th>توليد ms</th>
        <th>زمن الطلب s</th><th>توليد tok/s</th><th>أدنى tok/s</th><th>أعلى tok/s</th>
        <th>prompt tok/s</th><th>توكنز مولّدة</th><th>إجمالي s</th><th>تجهيز s</th>
        <th>RAM MiB</th><th>VRAM MiB</th>
      </tr></thead>
      <tbody>{''.join(summary_rows)}</tbody>
    </table>
  </div>
  <div class="subhead">⏱ زمن كل سؤال (ثانية) وسرعة التوليد — مقارنة جنب بعض</div>
  <div class="table-wrap heat-wrap">
    <table class="tbl heat-tbl speed-detail">
      <thead><tr><th class="heat-q">السؤال</th>{detail_head}</tr></thead>
      <tbody>{''.join(detail_rows)}</tbody>
    </table>
  </div>
  <p class="mut small">⚠ = الرد بلغ حد التوكنات (finish=length) — الرد ممكن يكون ناقص.</p>
</section>
"""


def charts_section(results: list[dict], exam_cfg: dict) -> str:
    """رسوم المقارنة: أعمدة المحاور + انتشار الجودة مقابل الزمن."""
    models = _ok_models(results)
    if len(models) < 1:
        return ""
    axes_cfg = exam_cfg.get("axes") or {}
    categories = ["① اللهجة", "② الأمانة", "③ الشغل", "④ المهارات", "المجموع"]
    series: list[dict] = []
    scatter_points: list[dict] = []
    for index, result in enumerate(models):
        exam = result.get("exam") or {}
        color = CHART_COLORS[index % len(CHART_COLORS)]
        values: list[float] = []
        for key in ("1", "2", "3", "4"):
            axis = (exam.get("axes") or {}).get(key) or {}
            maxv = axis.get("max") or (axes_cfg.get(key) or {}).get("max")
            values.append(_pct(axis.get("score"), maxv) or 0.0)
        values.append(float(exam.get("total") or 0.0))
        series.append({"label": str(result.get("model") or ""), "color": color, "values": values})

        runtime = result.get("runtime") or {}
        perf = runtime.get("perf") or {}
        seconds = perf.get("seconds_total") or runtime.get("seconds_total")
        try:
            x = float(seconds) if seconds else None
        except (TypeError, ValueError):
            x = None
        scatter_points.append(
            {
                "x": x,
                "y": float(exam.get("total") or 0.0),
                "color": color,
                "short": _short_model(result.get("model") or "", 16),
                "label": result.get("model"),
                "tip": (
                    f"{result.get('model')} — الدرجة {float(exam.get('total') or 0):.2f}/100 · "
                    f"إجمالي {x:.0f}s" if x is not None else str(result.get("model"))
                ),
            }
        )

    published = _baseline(exam_cfg)
    measured, _src = measured_baseline_model(results, exam_cfg)
    base_y = (
        float((measured.get("exam") or {}).get("total") or 0.0)
        if measured
        else float(published.get("total") or 0.0)
    )

    # ── شريط الهدف (Gemini 2.5 Pro): خط أفقي في الانتشار + عمود في الأعمدة
    target = target_config(exam_cfg)
    target_y = float(target.get("total") or 0.0) if target else None
    if target:
        t_axes = target.get("axes") or {}
        target_values = [
            _pct(t_axes.get(k), (axes_cfg.get(k) or {}).get("max")) or 0.0
            for k in ("1", "2", "3", "4")
        ]
        target_values.append(float(target.get("total") or 0.0))
        series.append(
            {
                "label": str(target.get("name") or "شريط الهدف"),
                "color": TARGET_COLOR,
                "values": target_values,
                "is_target": True,
            }
        )

    bar_svg = grouped_bar_svg(categories, series)
    xs = [float(p["x"]) for p in scatter_points if p.get("x") is not None]
    scatter_svg_html = scatter_svg(
        scatter_points,
        x_label="إجمالي زمن تشغيل الامتحان (ثانية)",
        y_label="الدرجة /100",
        x_max=(max(xs) * 1.2) if xs else None,
        baseline_y=base_y or None,
        target_y=target_y or None,
        target_label=str(target.get("name") or "شريط الهدف"),
    )
    legend = "".join(
        f'<span class="legend-chip" style="--c:{item["color"]}"><i class="dot"></i>'
        f'<span class="lc-name">{esc(_short_model(item["label"], 24))}</span>'
        + ('<span class="lc-badge">هدف</span>' if item.get("is_target") else "")
        + "</span>"
        for item in series
    )
    return f"""
<section class="section" id="charts">
  <div class="section-head">
    <div><h2>📊 رسوم المقارنة</h2>
      <p class="sub">الأعمدة = الدرجة النسبية على كل محور (0–100%) لكل موديل.
      والنقطة = الموديل: كلما كانت أعلى كلما أفضل، وكلما كانت على الشمال (أقل زمن) كلما أسرع.
      <b>شريط الهدف (Gemini 2.5 Pro)</b> موجود في الرسمين: عمود بنفسجي في الأعمدة، وخط أفقي في الانتشار.</p></div>
    <div class="legend-chips">{legend}</div>
  </div>
  <div class="grid2">
    <div class="card chart-card">
      <h3 class="panel-title">الدرجة على كل محور</h3>
      {bar_svg}
    </div>
    <div class="card chart-card">
      <h3 class="panel-title">الجودة مقابل الزمن</h3>
      {scatter_svg_html}
      <p class="mut small">الخط الأفقي الكهرماني = خط الأساس، والبنفسجي = شريط الهدف ({esc(str(target.get("name") or "الهدف"))} · {esc(source_badge(target))}).
      الموديل فوق الخطوط وبـ x صغير = أحسن اختيار.</p>
    </div>
  </div>
</section>
"""


def Path_name(path: str) -> str:
    """اسم الملف من مسار (Windows/Posix)."""
    text = str(path).replace("\\", "/")
    return text.rsplit("/", 1)[-1] if "/" in text else text


# --------------------------------------------------------------------------- مساعدات داخلية
def _baseline(exam_cfg: dict) -> dict:
    return exam_cfg.get("baseline") or {}


def _ok_models(results: list[dict]) -> list[dict]:
    return [r for r in results if r.get("status") == "ok" and r.get("exam")]


__all__ = [
    "CHART_COLORS",
    "RADAR_DIMS",
    "radar_section",
    "radar_svg",
    "radar_values",
    "baseline_radar_values",
    "delta_matrix",
    "axis_winners",
    "settings_section",
    "transcripts_section",
    "model_cards_section",
    "speed_table_section",
    "charts_section",
    "grouped_bar_svg",
    "scatter_svg",
]
