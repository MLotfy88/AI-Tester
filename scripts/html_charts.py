"""الرسوم البيانية وسجل الإجابات الكامل لتقرير HTML (الامتحان v3).

كل الرسوم هنا **SVG خالص** مولّد من Python:
  · مفيش Chart.js ولا CDN ولا أي ملف خارجي — التقرير ملف واحد مستقل.
  · الرسم السداسي (Radar) لكل نموذج: 8 محاور + المجموع.
  · جدول الفروق عن **مرجع Gemini (عرض فقط)** — أداة مقارنة سريعة.
  · سجل الإجابات: نص السؤال + نص الإجابة + ملاحظات المصحح لكل موديل.

⚠ كل عنصر يخص مرجع Gemini بياخد class `gem-ref` ⇒ زر «إظهار/إخفاء المرجع»
بيتحكم فيه من الـ CSS (`html[data-gem="off"] .gem-ref{display:none}`)
فيختفي **من الجداول والرسوم والبطاقات والنصوص** معاً، والاختيار بيتحفظ في localStorage.
"""
from __future__ import annotations

import html
import json
import math
from typing import Any

from common import human_bytes
from references import (
    GEMINI_COLOR,
    category_short,
    gemini_gap,
    gemini_radar_values,
    gemini_ranking,
    gemini_reference,
    gemini_total,
    gemini_values,
    source_badge,
)

# --------------------------------------------------------------------------- ثابت
CHART_COLORS = [
    "#22d3ee", "#60a5fa", "#34d399", "#fbbf24", "#fb7185",
    "#a78bfa", "#f472b6", "#2dd4bf", "#facc15", "#c084fc",
]

#: class موحّد لكل عنصر يخص مرجع Gemini (عرض فقط)
GEM_CLASS = "gem-ref"


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


def Path_name(path: str) -> str:
    """اسم الملف من مسار (Windows/Posix)."""
    text = str(path).replace("\\", "/")
    return text.rsplit("/", 1)[-1] if "/" in text else text


def _ok_models(results: list[dict]) -> list[dict]:
    return [r for r in results if r.get("status") == "ok" and r.get("exam")]


def radar_dims(exam_cfg: dict) -> list[tuple[str, str]]:
    """أبعاد الرسم السداسي: 8 محاور + المجموع."""
    dims: list[tuple[str, str]] = [
        (str(key), category_short(exam_cfg, key))
        for key in (exam_cfg.get("categories") or {}).keys()
    ]
    dims.append(("total", "المجموع"))
    return dims


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


def radar_values(exam: dict | None, exam_cfg: dict) -> list[float]:
    """قيم الموديل على أبعاد الرسم السداسي (كلها من 0 إلى 100)."""
    exam = exam or {}
    categories = exam.get("categories") or {}
    values: list[float] = []
    for key, _label in radar_dims(exam_cfg):
        if key == "total":
            values.append(float(exam.get("total") or 0.0))
        else:
            row = categories.get(key) or {}
            values.append(float(row.get("percent") or 0.0))
    return values


def radar_svg(
    series: list[dict],
    dims: list[tuple[str, str]],
    gemini_values: list[float] | None = None,
    gemini_label: str = "مرجع Gemini 2.5 Pro",
) -> str:
    """رسم SVG: كل موديل مضلّع + مرجع Gemini (منقّط بنفسجي، عرض فقط).

    مرجع Gemini ملفوف في `<g class="gem-ref">` ⇒ اختفاؤه بيخفيه من الرسم كله.
    """
    width, height = 620, 500
    cx, cy, radius = 310, 245, 165
    n = len(dims)
    out = [
        '<svg class="radar-svg" viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" '
        'role="img" aria-label="مقارنة سداسية بين الموديلات">' % (width, height)
    ]
    for level in (20, 40, 60, 80, 100):
        pts = _radar_polygon([float(level)] * n, cx, cy, radius)
        cls = "radar-ring" + (" outer" if level == 100 else "")
        out.append(f'<polygon class="{cls}" points="{pts}"/>')
    for i, (_key, label) in enumerate(dims):
        angle = math.radians(-90 + i * 360.0 / n)
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        out.append(f'<line class="radar-spoke" x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}"/>')
        lx = cx + (radius + 38) * math.cos(angle)
        ly = cy + (radius + 38) * math.sin(angle)
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
    if gemini_values:
        pts = _radar_polygon(gemini_values, cx, cy, radius)
        dots = "".join(
            f'<circle class="radar-target-dot" cx="{x:.1f}" cy="{y:.1f}" r="3.2"/>'
            for x, y in _radar_coords(gemini_values, cx, cy, radius)
        )
        out.append(
            f'<g class="{GEM_CLASS} radar-target"><title>{esc(gemini_label)} — مرجع عرض فقط</title>'
            f'<polygon class="radar-target-poly" points="{pts}"/>{dots}</g>'
        )
    for idx, item in enumerate(series):
        pts = _radar_polygon(item["values"], cx, cy, radius)
        tip = item["model"] + " — " + " · ".join(
            f"{label}: {value:.1f}" for (_k, label), value in zip(dims, item["values"])
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


# --------------------------------------------------------------------------- أفضل محور
def category_winners(results: list[dict], exam_cfg: dict) -> str:
    """«الأفضل في كل محور» — أسرع طريقة للقرار."""
    chips: list[str] = []
    for key in (exam_cfg.get("categories") or {}).keys():
        label = category_short(exam_cfg, key)
        best = None
        best_pct = -1.0
        for result in _ok_models(results):
            row = ((result.get("exam") or {}).get("categories") or {}).get(key) or {}
            pct = row.get("percent")
            if isinstance(pct, (int, float)) and float(pct) > best_pct:
                best, best_pct = result, float(pct)
        if best is None:
            continue
        chips.append(
            f'<span class="winner"><b>{esc(label)}</b><span class="winner-model">{esc(best.get("model"))}</span>'
            f'<span class="num" dir="ltr">{_num(best_pct, 1)}%</span></span>'
        )
    return "".join(chips)


# --------------------------------------------------------------------------- فرق عن مرجع Gemini
def _delta_cell(delta: float, maximum: float = 100.0) -> str:
    cls = "up" if delta > 0 else ("down" if delta < 0 else "mut")
    sign = "+" if delta > 0 else ""
    width = min(50.0, abs(delta) / maximum * 50.0) if maximum else 0.0
    bar_cls = "pos" if delta > 0 else ("neg" if delta < 0 else "")
    bar = f'<i class="{bar_cls}" style="width:{width:.1f}%"></i>' if bar_cls else ""
    return (
        f'<div class="delta-cell"><span class="dval {cls} num" dir="ltr">{sign}{delta:.2f}</span>'
        f'<span class="dtrack">{bar}</span></div>'
    )


def gemini_delta_matrix(results: list[dict], exam_cfg: dict) -> str:
    """جدول فرق النسبة عن مرجع Gemini — لكل محور + المسافة.

    ⚠ كل الجدول `gem-ref` ⇒ بيختفي مع إطفاء المرجع.
    """
    keys = list((exam_cfg.get("categories") or {}).keys())
    reference = gemini_values(exam_cfg)
    rows: list[str] = []
    for result in _ok_models(results):
        exam = result.get("exam") or {}
        gap = gemini_gap(exam, exam_cfg)
        cells = "".join(
            f"<td>{_delta_cell(gap['per_axis'].get(key, 0.0))}</td>" for key in keys
        )
        distance = gap.get("distance")
        rows.append(
            f'<tr><td class="model-cell"><div class="model-name">{esc(result.get("model"))}</div>'
            f'<div class="mut small num" dir="ltr">{_num(exam.get("total"), 2)}/100</div></td>'
            + cells
            + f'<td><span class="num dist-val" dir="ltr">{_num(distance, 1)}</span></td></tr>'
        )
    if reference:
        zeros = "".join(
            '<td><div class="delta-cell"><span class="dval mut num" dir="ltr">0.00</span>'
            '<span class="dtrack"></span></div></td>'
            for _ in keys
        )
        rows.append(
            f'<tr class="target-row"><td class="model-cell"><div class="model-name">🎯 '
            f'{esc(gemini_reference(exam_cfg).get("name") or "مرجع Gemini")}</div>'
            f'<div class="mut small">مرجع عرض فقط — {esc(source_badge(gemini_reference(exam_cfg)))}</div></td>'
            f"{zeros}<td>—</td></tr>"
        )
    head = "".join(f"<th>Δ {esc(category_short(exam_cfg, key))}</th>" for key in keys)
    return f"""
<div class="table-wrap">
  <table class="tbl compact delta-tbl">
    <thead><tr><th>الموديل</th>{head}<th>المسافة</th></tr></thead>
    <tbody>{''.join(rows) or '<tr><td colspan="10" class="mut">مفيش نتائج.</td></tr>'}</tbody>
  </table>
</div>
<p class="mut small delta-note">Δ = فرق النسبة عن مرجع Gemini (بالنقاط %) — موجب = أعلى من المرجع.
  <b>المسافة</b> = متوسط |Δ| على المحاور الثمانية · <b>الأقل = الأقرب</b>.
  ⛔ المرجع **عرض فقط** — مالوش أي تأثير في الدرجة ولا الحكم.</p>
"""


def gemini_ranking_table(results: list[dict], exam_cfg: dict) -> str:
    """«🎯 الأقرب لمرجع Gemini» — ترتيب من الأقرب للأبعد."""
    ref = gemini_reference(exam_cfg)
    if not ref:
        return '<p class="mut small">مفيش مرجع معرّف في الإعدادات.</p>'
    ranked = gemini_ranking(results, exam_cfg)
    if not ranked:
        return '<p class="mut small">مفيش نتائج.</p>'
    keys = list((exam_cfg.get("categories") or {}).keys())
    rows: list[str] = []
    for i, row in enumerate(ranked, 1):
        result = row["result"]
        gap = row["gap"]
        exam = result.get("exam") or {}
        distance = float(row["distance"])
        near = max(0.0, min(1.0, 1.0 - distance / 100.0))
        cells = "".join(
            f'<td class="num" dir="ltr">{_num(gap["per_axis"].get(key), 1)}</td>' for key in keys
        )
        rows.append(
            f'<tr><td class="rank num" dir="ltr">{i}</td>'
            f'<td class="model-cell"><div class="model-name" title="{esc(result.get("model_full") or result.get("model"))}">{esc(result.get("model"))}</div></td>'
            f'<td class="num" dir="ltr">{_num(exam.get("total"), 1)}</td>'
            f"{cells}"
            f'<td><span class="dist-bar" title="المسافة {distance:.1f}">'
            f'<i style="width:{near * 100:.1f}%"></i></span>'
            f'<span class="num dist-val" dir="ltr">{_num(distance, 1)}</span></td></tr>'
        )
    head = "".join(f"<th>Δ {esc(category_short(exam_cfg, key))}</th>" for key in keys)
    return f"""
<div class="table-wrap">
  <table class="tbl compact target-tbl">
    <thead><tr><th>#</th><th>الموديل</th><th>المجموع</th>{head}<th>المسافة (قرب)</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</div>
<p class="mut small delta-note">Δ = فرق النسبة عن <b>{esc(str(ref.get("name") or ""))}</b>
  (<span class="pill target">{esc(source_badge(ref))}</span>) — موجب = أعلى من المرجع.
  <b>المسافة</b> = متوسط |Δ| على المحاور الثمانية · الأقل = الأقرب.
  ⛔ <b>عرض فقط</b> — لا يدخل في درجة أي نموذج ولا في الحكم.</p>
"""


# --------------------------------------------------------------------------- الرسم السداسي (القسم)
def radar_section(results: list[dict], exam_cfg: dict) -> str:
    """قسم الرسم السداسي + لوحة القرار."""
    models = _ok_models(results)
    if not models:
        return ""
    dims = radar_dims(exam_cfg)
    series: list[dict] = []
    for i, result in enumerate(models):
        exam = result.get("exam") or {}
        series.append(
            {
                "id": f"s{i}",
                "model": result.get("model") or f"موديل {i + 1}",
                "values": radar_values(exam, exam_cfg),
                "color": CHART_COLORS[i % len(CHART_COLORS)],
                "total": exam.get("total"),
                "verdict": exam.get("verdict"),
            }
        )

    ref = gemini_reference(exam_cfg)
    ref_values = gemini_radar_values(exam_cfg, [k for k, _ in dims if k != "total"])
    # المجموع مش رقم مرجعي (Gemini مش مقاس ب rubricنا) ⇒ بنخليه 0 في الرسم
    ref_values = list(ref_values) + [0.0] if ref_values else None
    svg = radar_svg(series, dims, ref_values, str(ref.get("name") or "مرجع Gemini"))

    legend = "".join(
        f'<button type="button" class="legend-chip" data-series="{item["id"]}" style="--c:{item["color"]}">'
        f'<i class="dot"></i><span class="lc-name">{esc(item["model"])}</span>'
        f'<span class="lc-total num" dir="ltr">{_num(item["total"], 1)}</span></button>'
        for item in series
    )
    gem_chip = ""
    if ref:
        gem_chip = (
            f'<span class="legend-chip target {GEM_CLASS}" title="{esc(str(ref.get("note") or ""))}">'
            f'<i class="dot"></i><span class="lc-name">{esc(ref.get("name") or "مرجع Gemini")}</span>'
            f'<span class="lc-badge">{esc(source_badge(ref))}</span></span>'
        )

    ref_total = gemini_total(exam_cfg)
    ref_note = (
        f'<div class="base-source target-src {GEM_CLASS}">'
        f'<b>المرجع في الرسم:</b> {esc(str(ref.get("name") or ""))} — '
        f'<span class="pill target">{esc(source_badge(ref))}</span>'
        f'<div class="mut small">متوسط التقدير المرجعي: {_num(ref_total, 1)}/100 '
        f'(متوسط بسيط على المحاور الثمانية — <b>مش درجة rubric</b>).</div>'
        f'<div class="mut small">{esc(str(ref.get("note") or ""))}</div></div>'
        if ref
        else ""
    )

    return f"""
<section class="section" id="radar">
  <div class="section-head">
    <div><h2>⬡ البصمة السداسية للموديلات</h2>
      <p class="sub">كل مضلّع = موديل واحد على 8 محاور + المجموع (كلها 0–100).
      مرّر الماوس على أي مضلّع لتشوف أرقامه.
      <span class="{GEM_CLASS}">والمنقّط البنفسجي = مرجع Gemini 2.5 Pro (عرض فقط ⛔ — مالوش تأثير في الدرجة ولا الحكم).</span></p></div>
  </div>
  <div class="radar-layout">
    <div class="card radar-card">
      {svg}
      <div class="legend-chips">{legend}{gem_chip}</div>
      {ref_note}
    </div>
    <div class="decision-panel">
      <div class="card">
        <h3 class="panel-title">🏅 الأفضل في كل محور</h3>
        <div class="winners">{category_winners(results, exam_cfg) or '<span class="mut">مفيش نتائج.</span>'}</div>
      </div>
      <div class="card {GEM_CLASS}">
        <h3 class="panel-title">🎯 الفرق عن مرجع Gemini (نقاط %)</h3>
        <p class="mut small">الأخضر = أعلى من المرجع · الأحمر = أقل. النص = الفرق بالنقاط من 100.</p>
        {gemini_delta_matrix(results, exam_cfg)}
      </div>
      <div class="card {GEM_CLASS}">
        <h3 class="panel-title">🎯 الأقرب لمرجع Gemini ({esc(str(ref.get("name") or "مرجع Gemini"))})</h3>
        <p class="mut small">المسافة = متوسط فرق النسبة على المحاور الثمانية (٠ = مطابق تماماً). <b>الأقل = الأقرب.</b></p>
        {gemini_ranking_table(results, exam_cfg)}
      </div>
      <div class="card note">
        <b>طريقة القراءة:</b> لو المضلّع <b>مش متساوي</b> ⇒ فيه محور ضعيف حتى لو المجموع عالي —
        وده بالظبط اللي بيفرق في القرار. وكل محور نزل عن حدّه الأدنى = <b>فشل حرج ⛔</b>
        حتى لو المجموع عالي.
      </div>
    </div>
  </div>
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
    width: int = 900,
    height: int = 350,
    y_max: float = 100.0,
    y_suffix: str = "%",
) -> str:
    """أعمدة مجمّعة: كل مجموعة = محور، وكل لون = موديل.

    series = [{"label", "color", "values", "css_class"}]
    كل سلسلة ملفوفة في `<g>` ⇒ لو السلسلة مرجع Gemini بنحطها `gem-ref` فتختفى مع الإطفاء.
    """
    if not categories or not series:
        return ""
    pad_l, pad_r, pad_t, pad_b = 52, 14, 16, 60
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    out = [
        f'<svg class="chart-svg" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="مقارنة الأعمدة">'
    ]
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
            css = str(item.get("css_class") or "").strip()
            out.append(
                f'<g class="{esc(css)}">' if css else "<g>"
            )
            out.append(
                f'<rect class="ch-bar" x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                f'rx="3" fill="{esc(item.get("color"))}"><title>{esc(tip)}</title></rect>'
            )
            if bar_w >= 26:
                out.append(
                    f'<text class="ch-val" x="{x + bar_w / 2:.1f}" y="{max(pad_t + 9, y - 4):.1f}" '
                    f'text-anchor="middle">{v:.0f}</text>'
                )
            out.append("</g>")
        out.append(
            f'<text class="ch-label" x="{pad_l + group_w * gi + group_w / 2:.1f}" y="{height - pad_b + 20:.1f}" '
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
    gemini_y: float | None = None,
    gemini_label: str = "مرجع Gemini",
) -> str:
    """مخطط انتشار: الدرجة (y) ضد زمن التشغيل (x).

    خط أفقي بنفسجي = مرجع Gemini (عرض فقط) — ملفوف في `<g class="gem-ref">`.
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

    if gemini_y is not None:
        ty = sy(float(gemini_y))
        out.append(f'<g class="{GEM_CLASS}">')
        out.append(
            f'<line class="ch-target" x1="{pad_l}" y1="{ty:.1f}" x2="{width - pad_r}" y2="{ty:.1f}">'
            f"<title>{esc(gemini_label)}: {float(gemini_y):.1f}</title></line>"
        )
        out.append(
            f'<text class="ch-target-label" x="{pad_l + 4}" y="{ty - 6:.1f}" text-anchor="start">'
            f"{esc(gemini_label)}</text>"
        )
        out.append("</g>")

    placed: list[tuple[float, float, float]] = []
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


def _short_model(name: str, limit: int = 26) -> str:
    """اسم موديل مختصر للعرض في الرسوم والجداول."""
    text = Path_name(str(name or ""))
    text = text.replace(".gguf", "")
    text = text.strip()
    return text[:limit] if text else "—"


def _verdict_class(verdict: Any) -> str:
    """تصنيف CSS للحكم — نفس منطق html_report (مفيش استيراد دائري)."""
    text = str(verdict or "")
    if "فشل حرج" in text:
        return "v-bad"
    if "قريب جدًا" in text:
        return "v-good"
    if "قريب مع فجوات" in text:
        return "v-ok"
    if "متوسط" in text:
        return "v-weak"
    if "بعيد" in text:
        return "v-bad"
    return "v-na"


# --------------------------------------------------------------------------- النتائج لكل موديل
def _gemini_reference_card(exam_cfg: dict) -> str:
    """كارت **مرجع Gemini** (عرض فقط) — بنفس شكل كارت الموديل."""
    ref = gemini_reference(exam_cfg)
    if not ref:
        return ""
    values = gemini_values(exam_cfg)
    if not values:
        return ""
    avg = gemini_total(exam_cfg)
    bars = ""
    for key in (exam_cfg.get("categories") or {}).keys():
        label = category_short(exam_cfg, key)
        value = values.get(key)
        if value is None:
            continue
        bars += (
            f'<div class="mc-axis"><span class="mc-axis-l">{esc(label)}</span>'
            f'<span class="bar sm"><i style="width:{float(value):.1f}%"></i></span>'
            f'<span class="num mc-axis-v" dir="ltr">{_num(value, 1)}%</span></div>'
        )
    return f"""
<article class="card mc-card target-card {GEM_CLASS}">
  <header class="mc-head">
    <div class="mc-gauge">{_gauge_svg(avg)}
      <div class="mc-score"><b class="num" dir="ltr">{_num(avg, 1)}</b><small>/100</small></div>
    </div>
    <div class="mc-title">
      <div class="model-name">🎯 {esc(ref.get("name") or "مرجع Gemini")}</div>
      <div class="mut small">مرجع عرض فقط ⛔ — مش موديل مُشغّل ولا مشغّل بامتحاننا</div>
      <div class="mc-verdict"><span class="pill target">{esc(source_badge(ref))}</span></div>
    </div>
  </header>
  <div class="mc-axes">{bars}</div>
  <div class="mc-stats">
    <div class="mc-stat"><span class="mc-k">الرقم أعلاه</span><span class="mc-v">متوسط التقدير على المحاور — مش درجة rubric</span></div>
    <div class="mc-stat"><span class="mc-k">المصدر</span><span class="mc-v">{esc(source_badge(ref))}</span></div>
  </div>
  <div class="base-source target-src"><b>ملاحظة:</b> {esc(str(ref.get("note") or ""))}</div>
</article>"""


def model_cards_section(results: list[dict], exam_cfg: dict) -> str:
    """«النتيجة لكل موديل» — كارت واحد لكل موديل بالدرجة والمحاور والسرعة."""
    models = _ok_models(results)
    if not models:
        return ""
    ref = gemini_reference(exam_cfg)

    cards: list[str] = []
    for index, result in enumerate(models):
        exam = result.get("exam") or {}
        runtime = result.get("runtime") or {}
        perf = runtime.get("perf") or {}
        fit = result.get("fit") or {}
        manifest = result.get("manifest") or {}
        total = float(exam.get("total") or 0.0)
        verdict = str(exam.get("verdict") or "—")
        tg = (perf.get("tg_tps") or {}).get("avg")
        ttft = (perf.get("ttft_ms") or {}).get("avg")
        req = (perf.get("request_seconds") or {}).get("avg")
        categories = exam.get("categories") or {}

        # شرائط المحاور الثمانية + علامة «تحت الحد الأدنى»
        axis_bars = ""
        for key in (exam_cfg.get("categories") or {}).keys():
            label = category_short(exam_cfg, key)
            row = categories.get(key) or {}
            pct = float(row.get("percent") or 0.0)
            under = bool(row.get("failed_min"))
            under_html = (
                '<span class="trust-flag" title="تحت الحد الأدنى — فشل حرج">⛔</span>' if under else ""
            )
            axis_bars += (
                f'<div class="mc-axis"><span class="mc-axis-l">{esc(label)}</span>'
                f'<span class="bar sm"><i style="width:{pct:.1f}%"></i></span>'
                f'<span class="num mc-axis-v" dir="ltr">{_num(pct, 1)}%{under_html}</span></div>'
            )

        failed = list(exam.get("failed_categories") or [])
        failed_html = (
            "".join(
                f'<span class="gate on" title="محور تحت الحد الأدنى">{esc(str((exam_cfg.get("categories") or {}).get(k, {}).get("short") or k))}</span>'
                for k in failed
            )
            or '<span class="gate off">كل المحاور فوق الحد</span>'
        )

        quant = str(manifest.get("quant_pattern") or "")
        file_name = Path_name(str(manifest.get("primary_path") or fit.get("file") or ""))
        subtitle_parts = []
        if quant and quant.lower() != "local":
            subtitle_parts.append(esc(quant))
        elif file_name:
            subtitle_parts.append(esc(file_name))
        subtitle = " · ".join(subtitle_parts) or "—"

        # المسافة عن مرجع Gemini (عرض فقط)
        gap = gemini_gap(exam, exam_cfg) if ref else {"distance": None, "per_axis": {}}
        distance = gap.get("distance")

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
      <div class="mc-gates">{failed_html}</div>
    </div>
  </header>
  <div class="mc-axes">{axis_bars}</div>
  <div class="mc-stats">
    <div class="mc-stat"><span class="mc-k {GEM_CLASS}">المسافة عن مرجع Gemini</span><span class="mc-v num {GEM_CLASS}" dir="ltr">{_num(distance, 1)}</span></div>
    <div class="mc-stat"><span class="mc-k">⚡ توليد tok/s (مقيس)</span><span class="mc-v tok-v num" dir="ltr">{_num(tg, 1)}</span></div>
    <div class="mc-stat"><span class="mc-k">أول استجابة ms</span><span class="mc-v num" dir="ltr">{_num(ttft, 0)}</span></div>
    <div class="mc-stat"><span class="mc-k">زمن الطلب s</span><span class="mc-v num" dir="ltr">{_num(req, 1)}</span></div>
    <div class="mc-stat"><span class="mc-k">حجم الموديل</span><span class="mc-v num" dir="ltr">{esc(human_bytes(manifest.get("total_bytes") or 0))}</span></div>
  </div>
</article>"""
        )

    gem_card = _gemini_reference_card(exam_cfg)
    if gem_card:
        cards.insert(0, gem_card)

    ref_note = (
        f'<span class="{GEM_CLASS}">🎯 <b>مرجع {esc(str(ref.get("name") or ""))}</b> '
        f'(<span class="pill target">{esc(source_badge(ref))}</span>) — أرقامه <b>بنشماركات عامة منشورة</b> '
        "مش مقاسة على أسئلة امتحاننا، و<b>مالوش أي تأثير</b> في درجة أي نموذج ولا في الحكم.</span>"
        if ref
        else ""
    )
    return f"""
<section class="section" id="cards">
  <div class="section-head">
    <div><h2>🏅 النتيجة لكل موديل</h2>
      <p class="sub">كارت لكل موديل: الدرجة والحكم ونسب المحاور الثمانية والمحاور تحت الحد الأدنى والأداء المقيس.
      {ref_note}</p></div>
  </div>
  <div class="mc-grid">{''.join(cards)}</div>
</section>
"""


# --------------------------------------------------------------------------- رسوم المقارنة (القسم)
def charts_section(results: list[dict], exam_cfg: dict) -> str:
    """رسوم المقارنة: أعمدة المحاور الثمانية + انتشار الدرجة مقابل الزمن."""
    models = _ok_models(results)
    if not models:
        return ""
    keys = list((exam_cfg.get("categories") or {}).keys())
    labels = [category_short(exam_cfg, key) for key in keys]
    labels.append("المجموع")

    series: list[dict] = []
    scatter_points: list[dict] = []
    for index, result in enumerate(models):
        exam = result.get("exam") or {}
        color = CHART_COLORS[index % len(CHART_COLORS)]
        categories = exam.get("categories") or {}
        values = [float((categories.get(key) or {}).get("percent") or 0.0) for key in keys]
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

    # ── مرجع Gemini: عمود بنفسجي + خط أفقي (عرض فقط — كله gem-ref)
    ref = gemini_reference(exam_cfg)
    ref_values_map = gemini_values(exam_cfg)
    gem_y = gemini_total(exam_cfg)
    if ref and ref_values_map:
        ref_series = [float(ref_values_map.get(key, 0.0)) for key in keys]
        ref_series.append(float(gem_y or 0.0))
        series.append(
            {
                "label": str(ref.get("name") or "مرجع Gemini"),
                "color": GEMINI_COLOR,
                "values": ref_series,
                "css_class": GEM_CLASS,
                "is_gemini": True,
            }
        )

    bar_svg = grouped_bar_svg(labels, series)
    xs = [float(p["x"]) for p in scatter_points if p.get("x") is not None]
    scatter_html = scatter_svg(
        scatter_points,
        x_label="إجمالي زمن تشغيل الامتحان (ثانية)",
        y_label="الدرجة /100",
        x_max=(max(xs) * 1.2) if xs else None,
        gemini_y=gem_y if ref else None,
        gemini_label=str(ref.get("name") or "مرجع Gemini"),
    )
    legend = "".join(
        f'<span class="legend-chip{" " + GEM_CLASS if item.get("is_gemini") else ""}" style="--c:{item["color"]}">'
        f'<i class="dot"></i>'
        f'<span class="lc-name">{esc(_short_model(item["label"], 24))}</span>'
        + ('<span class="lc-badge">مرجع</span>' if item.get("is_gemini") else "")
        + "</span>"
        for item in series
    )
    gem_legend = ""
    if ref:
        gem_legend = (
            f'<p class="mut small {GEM_CLASS}">الخط الأفقي البنفسجي = {esc(str(ref.get("name") or ""))} '
            f"({esc(source_badge(ref))}) — <b>عرض فقط ⛔</b>، مالوش تأثير في الدرجة ولا الحكم.</p>"
        )
    return f"""
<section class="section" id="charts">
  <div class="section-head">
    <div><h2>📊 رسوم المقارنة</h2>
      <p class="sub">الأعمدة = النسبة على كل محور (0–100%) لكل موديل.
      والنقطة = الموديل: كلما كانت أعلى كلما أفضل، وكلما كانت على الشمال (أقل زمن) كلما أسرع.</p></div>
    <div class="legend-chips">{legend}</div>
  </div>
  <div class="grid2">
    <div class="card chart-card">
      <h3 class="panel-title">الدرجة على كل محور</h3>
      {bar_svg}
    </div>
    <div class="card chart-card">
      <h3 class="panel-title">الجودة مقابل الزمن</h3>
      {scatter_html}
      {gem_legend}
      <p class="mut small">الموديل فوق الخط وبـ x صغير = أحسن اختيار.</p>
    </div>
  </div>
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
    <div class="ans-model">{esc(result.get('model'))}</div>
    <span class="pill muted">{esc(st.get('source') or '—')}</span>
  </header>
  <div class="set-grid">
    <div class="set-k">القالب</div><div class="set-v" dir="ltr">{esc(Path_name(template))}</div>
    <div class="set-k">مصدر القالب</div><div class="set-v">{esc(st.get('template_source') or runtime.get('template_mode') or '—')}</div>
    <div class="set-k">KV cache</div><div class="set-v" dir="ltr">{esc(st.get('kv_cache_type') or runtime.get('kv') or '—')}</div>
    <div class="set-k">flash-attn</div><div class="set-v" dir="ltr">{esc(st.get('flash_attn') or runtime.get('flash_attn') or '—')}</div>
    <div class="set-k">ngl (offload)</div><div class="set-v num" dir="ltr">{esc(st.get('n_gpu_layers') if st.get('n_gpu_layers') is not None else runtime.get('ngl', '—'))}</div>
    <div class="set-k">threads</div><div class="set-v num" dir="ltr">{esc(st.get('threads') if st.get('threads') is not None else runtime.get('threads', '—'))}</div>
    <div class="set-k">device</div><div class="set-v" dir="ltr">{esc(st.get('device') or runtime.get('device') or '—')}</div>
    <div class="set-k">Sampling مطبّق</div>
    <div class="set-v num" dir="ltr">temp={esc(runtime.get('temperature', '—'))} · top_p={esc(runtime.get('top_p', '—'))} · seed={esc(runtime.get('seed', '—'))}</div>
    <div class="set-k">توصيات المطوّر</div>
    <div class="set-v">{" · ".join(f"{k}={v}" for k, v in rec.items()) or "—"}
      <span class="mut small">[{esc(st.get('sampling_source') or 'none')}]</span></div>
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
            "للمقارنة المطلقة ثبّت نفس القالب لكل الموديلات.</div>"
        )
    return f"""
<section class="section" id="settings">
  <div class="section-head">
    <div><h2>⚙️ الإعدادات الفعلية لكل موديل</h2>
      <p class="sub">اللي اتشغّل بيه فعلياً: قالب المحادثة، KV، offload، threads، device.
      إعدادات الامتحان الثابتة (temp/top_p/seed/ctx) واحدة للجميع.</p></div>
  </div>
  {banner}
  <div class="set-grid-cards">{''.join(rows)}</div>
</section>
"""


# --------------------------------------------------------------------------- سجل الإجابات الكامل
def transcripts_section(results: list[dict], exam_cfg: dict) -> str:
    """سجل الإجابات الكامل: نص السؤال + نص الإجابة + ملاحظات المصحح لكل موديل."""
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
                else '<div class="tr-text think muted">— لا يوجد نص تفكير (التشغيل بوضع بلا تفكير '
                "حسب إعدادات الامتحان) —</div>"
            )
            answer_block = (
                f'<div class="tr-text answer">{esc(answer)}</div>'
                if answer
                else '<div class="tr-text answer bad">— رد فاضي —</div>'
            )
            tool_calls = row.get("tool_calls") or []
            tool_block = ""
            if tool_calls:
                calls_txt = " · ".join(
                    f"{c.get('name')}({json.dumps(c.get('arguments') or {}, ensure_ascii=False)})"
                    for c in tool_calls
                )
                tool_block = (
                    f'<div class="tr-part"><div class="tr-label">🛠 استدعاءات الأدوات</div>'
                    f'<div class="tr-text q" dir="ltr">{esc(calls_txt)}</div></div>'
                )
            items.append(
                f"""
<article class="tr-item" data-search="{esc(blob)}">
  <header class="tr-head">
    <span class="qid">{esc(qid)}</span>
    <span class="tr-title">{esc(q.get("title"))}</span>
    <span class="tr-axis">{esc(str(row.get("category") or q.get("category") or "—"))}</span>
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
  {tool_block}
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
    <span class="ans-model">{esc(result.get('model'))}</span>
    <span class="tr-total num" dir="ltr">{_num(total, 1)}/100</span>
    <span class="verdict-mut mut small">{esc(exam.get('verdict') or "")}</span>
    <span class="mut small">{len(items)} سؤال</span>
  </summary>
  <div class="tr-list">{''.join(items)}</div>
</details>"""
        )

    return f"""
<section class="section" id="transcripts">
  <div class="section-head">
    <div><h2>🗂 سجل الإجابات الكامل</h2>
      <p class="sub">كل موديل: نص السؤال + نص الإجابة كما وصل من الخادم +
      ملاحظات المصحح — عشان تراجع بنفسك العامية المصرية والجودة اللغوية قبل ما تقرر.</p></div>
    <div class="tr-tools">
      <input id="tr-search" type="search" placeholder="بحث في الأسئلة والتفكير والإجابات…">
      <button type="button" class="btn" id="tr-expand">فتح الكل</button>
      <button type="button" class="btn" id="tr-collapse">طي الكل</button>
    </div>
  </div>
  <div class="tr-models">{''.join(blocks)}</div>
</section>
"""


# --------------------------------------------------------------------------- جدول السرعة
def speed_table_section(results: list[dict], exam_cfg: dict) -> str:
    """«⚡ جدول السرعة» — زمن كل سؤال + سرعة التوليد لكل موديل جنب بعض."""
    models = _ok_models(results)
    if not models:
        return ""
    questions = exam_cfg.get("questions") or []

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


__all__ = [
    "CHART_COLORS",
    "GEM_CLASS",
    "category_winners",
    "charts_section",
    "gemini_delta_matrix",
    "gemini_ranking_table",
    "grouped_bar_svg",
    "model_cards_section",
    "radar_dims",
    "radar_section",
    "radar_svg",
    "radar_values",
    "scatter_svg",
    "settings_section",
    "speed_table_section",
    "transcripts_section",
]
