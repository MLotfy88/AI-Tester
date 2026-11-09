"""فحوص الـ rubric — المحور BR (العصف الذهني والنقد) + TL (الأدوات والـ agent).

TL1/TL2 بيعتمدوا على **trace استدعاءات الأدوات** اللي بيجي في `ctx`:
    ctx = {"tool_calls": [{"name": ..., "arguments": {...}}, ...],
           "tool_results": {...}}
"""
from __future__ import annotations

import json
import re

from .rubric_lib import (
    bullet_count,
    contains_any,
    count_any,
    english_count,
    fail,
    header_count,
    non_empty_lines,
    numbers_in,
    ok,
    partial,
    repetition_ratio,
    sentence_count,
    word_count,
)

# --------------------------------------------------------------------------- BR
#: فئات الأفكار لـ BR1 (التنوع)
BR1_CATEGORIES = (
    ("عمليات", "تشغيل", "إجراء", "بروتوكول", "operation", "process", "تدريب", "جولة", "مراجعة"),
    ("بيانات", "قياس", "تحليل", "داشبورد", "تتبع", "data", "dashboard", "مرصد", "audit", "جودة البيانات"),
    ("موردين", "مورد", "supplier", "vendor", "موردين", "عروض", "مناقصة", "مقارنة"),
    ("سياسات", "سياسة", "policy", "لائحة", "قاعدة", "إجراء تنظيمي", "compliance", "التزام"),
    ("تقنية", "أتمتة", "أداة", "tool", "automation", "سENSOR", "حساسات", "tracking", "تتبع"),
    ("تحفيز", "تحفيز", "مكافأة", "incentive", "تقدير", "جائزة", "مسابقة"),
    ("تخطيط", "تخطيط", "forecast", "توقع", "جدولة", "buffer", "مخزون", "تنبيه"),
    ("تدريب", "تعليم", "training", "ورشة", "كبسولات", "onboarding"),
)


def _br1_ideas(text: str) -> tuple[float, str]:
    """R1: ٨ أفكار."""
    n = bullet_count(text)
    # بنتجاهل البنود الفارغة/اللي مفيهاش محتوى
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    real = [ln for ln in lines if len(ln) > 4]
    if n >= 8:
        return 2.0, f"{n} أفكار ✓"
    if n >= 5:
        return 1.0, f"{n} أفكار (المطلوب 8)"
    return 0.0, f"{n} أفكار — بعيد"


def _br1_diverse(text: str) -> tuple[float, str]:
    """R2: متنوعة (عمليات، بيانات، موردين، سياسات...)."""
    hits = sum(1 for group in BR1_CATEGORIES if contains_any(text, group))
    if hits >= 4:
        return 2.0, f"تنوع في {hits} فئات ✓"
    if hits >= 2:
        return 1.0, f"تنوع في {hits} فئات بس"
    return 0.0, f"تنوع ضعيف ({hits} فئات)"


def _br1_unconventional(text: str) -> tuple[float, str]:
    """R3: فيها فكرة غير تقليدية."""
    unconventional = (
        "مكافأة",
        "مسابقة",
        "سوق",
        "مزاد",
        "محلي",
        "أنشئ",
        "استأجر",
        "تبادل",
        "شراكة",
        "open source",
        "مفتوح المصدر",
        "هاش",
        "gamif",
        "لعبة",
        "Points",
        "نقاط",
        "تحدي",
        "تحدٍ",
        "hackathon",
        "مساحة مشتركة",
        "تظليل",
        "shadow",
        "تدوير",
        "عكس",
        "إلغاء",
        "stop",
        "ورشة",
        "Analog",
        "ورقي",
    )
    if contains_any(text, unconventional):
        return 2.0, "فيها فكرة غير تقليدية ✓"
    return 0.0, "مفيش فكرة غير تقليدية"


def _br1_ranked(text: str) -> tuple[float, str]:
    """R4: ترتيب بمعيار صريح (أثر وسهولة)."""
    has_criterion = contains_any(
        text,
        (
            "الأثر",
            "أثر",
            "impact",
            "سهولة",
            "سهل",
            "ease",
            "التكلفة",
            "تكلفة",
            "الجهد",
            "جهد",
            "الأولوية",
            "ترتيب حسب",
        ),
    )
    has_order = contains_any(
        text,
        (
            "مرتّب",
            "مرتب",
            "الترتيب",
            "الأعلى",
            "أولوية",
            "1.",
            "الأول",
            "الثاني",
            "best first",
            "ranked",
        ),
    )
    if has_criterion and has_order:
        return 2.0, "ترتيب بمعيار صريح ✓"
    if has_criterion or has_order:
        return 1.0, "ترتيب ناقص المعيار"
    return 0.0, "مفيش ترتيب بمعيار"


def _br1_actionable(text: str) -> tuple[float, str]:
    """R5: كل فكرة قابلة للتنفيذ."""
    # الفعل في العادة أول كلمة في البادجت — بنفحص بداية كل بادجت
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    bullets = [
        re.sub(r"^(?:[-*•◄–—>]|\d{1,2}[\.\)])\s*", "", ln)
        for ln in lines
        if re.match(r"^\s*(?:[-*•◄–—>]|\d{1,2}[\.\)])", ln)
    ]
    if not bullets:
        bullets = lines
    action_verbs = (
        "اعمل", "عمل", "ابدأ", "شغّل", "شغل", "نفذ", "طبّق", "طبق", "اعتمد", "راجع",
        "أنشئ", "انشئ", "خصص", "أرسل", "ارسل", "قابل", "احسب", "سجل", "استخدم", "ضع",
        "ارفع", "أدر", "ادر", "خط", "خص", "اختبر", "جرّب", "جرب", "ابحث", "اسأل",
        "اتفق", "تعاقد", "اشتري", "درب", "حوّل", "حول", "رقمن", "أتمت", "اجهز", "جهز",
        "قارن", "نظم", "اتبع", "راقب", "تابع", "ادرس", "اعمل", "احصل",
        "تدريب", "مقارنة", "حصر", "مراجعة", "تتبع", "سياسة", "داشبورد", "قياس",
        "استبدال", "شراكة", "مسابقة", "متابعة", "فحص", "ورشة",
    )
    n_ok = 0
    for b in bullets:
        # الفكرة لازم تكون عربية ومبنية على فعل
        ar_chars = len(re.findall(r"[\u0600-\u06ff]", b))
        if ar_chars < 3:
            continue
        if contains_any(b[:40], action_verbs):
            n_ok += 1
    ratio = n_ok / max(1, len(bullets))
    if ratio >= 0.75:
        return 2.0, f"{n_ok}/{len(bullets)} أفكار قابلة للتنفيذ ✓"
    if ratio >= 0.4:
        return 1.0, f"{n_ok}/{len(bullets)} أفكار قابلة للتنفيذ"
    return 0.0, f"أفكار غير قابلة للتنفيذ ({n_ok}/{len(bullets)})"


# --------------------------------------------------------------------------- BR2
def _br2_five_causes(text: str) -> tuple[float, str]:
    """R1: ٥ أسباب واقعية."""
    n = bullet_count(text)
    if n >= 5:
        return 2.0, f"{n} أسباب ✓"
    if n >= 3:
        return 1.0, f"{n} أسباب (المطلوب 5)"
    return 0.0, f"{n} أسباب — بعيد"


def _br2_prevention_linked(text: str) -> tuple[float, str]:
    """R2: كل سبب مربوط بإجراء وقائي."""
    prevention = (
        "نعمل",
        "الحل",
        "الإجراء",
        "الوقاية",
        "نمنع",
        "نتجنب",
        "نخطط",
        "نجهز",
        "نحقق",
        "نتدرب",
        "نراجع",
        "نوثق",
        "نعد",
        "نخصص",
        "مفتاح",
        "حصر",
        "قائمة",
        "checklist",
        "buffer",
        "احتياطي",
        "نستخدم",
        "نأكد",
        "نتأكد",
        "بنجهز",
        "بنعمل",
        "بندرب",
        "بنراجع",
        "بنخصص",
        "مفيش",
        "منع",
        "ضمان",
        "تأمين",
        "نسخة",
        "أقراص",
        "مسار بديل",
        "مسارات بديلة",
    )
    n = count_any(text, prevention)
    if n >= 5:
        return 2.0, f"{n} إجراءات وقائية ✓"
    if n >= 2:
        return 1.0, f"{n} إجراءات وقائية"
    return 0.0, f"إجراءات وقائية قليلة ({n})"


def _br2_human_operational(text: str) -> tuple[float, str]:
    """R3: أسباب بشرية وتشغيلية."""
    human = contains_any(
        text,
        (
            "تدريب",
            "موظف",
            "العامل",
            "الفريق",
            "الطاقمة",
            "سلوك",
            "تواصل",
            "إ communicated",
            "نctic",
            "مقاومة",
            "إرهاق",
            "ضغط",
            "خطأ بشري",
            "عدم committing",
            "غياب",
            "مغادرة",
        ),
    )
    operational = contains_any(
        text,
        (
            "معدات",
            "رافعة",
            "شاحنة",
            "نقل",
            "تأخير",
            "تاخير",
            "ازدحام",
            "طريق",
            "مسار",
            "مخزن",
            "تركيب",
            "فاتورة",
            "جمارك",
            "تالف",
            "أمان",
            "سلامة",
            " electricity",
            "كهرباء",
            "مرافق",
        ),
    )
    n = sum([bool(human), bool(operational)])
    if n == 2:
        return 2.0, "أسباب بشرية وتشغيلية ✓"
    if n == 1:
        return 1.0, "نوع واحد بس"
    return 0.0, "مفيش أسباب بشرية/تشغيلية"


def _br2_by_severity(text: str) -> tuple[float, str]:
    """R4: مرتبة حسب الخطورة."""
    has_marker = contains_any(
        text,
        (
            "الأخطر",
            "الخطورة",
            "الأعلى خطورة",
            "الأهم",
            "الأولوية",
            "مرتبة",
            "الترتيب",
            "الأعلى",
            "الأكبر",
            "critical",
            "highest",
            "مرتّبة",
            "مرتبة حسب",
            "بترتيب",
            "حسب الخطورة",
            "حسب الأهمية",
            "حسب الأولوية",
        ),
    )
    # تدرّج صريح: سبب مرتبط بحل، وسبب فيه تدرّج لفظي
    ordered = bool(
        re.search(
            r"(?m)^\s*(?:\d{1,2}[\.\)]|[-*•])\s*\**\s*(?:الأخطر|الأهم|الأول|الأعلى|حرج|مرتفع|عالي|"
            r"الأكبر|الأقل|منخفض|متوسط|الأخطر|الأعلى خطورة)",
            text,
        )
    )
    ranked_list = bool(
        re.search(r"(?m)^\s*(?:\d{1,2}[\.\)]|[-*•]).*$", text)
    ) and contains_any(text, ("مرتبة", "الترتيب", "حسب الخطورة", "حسب الأهمية", "مرتّبة"))
    if (has_marker and ordered) or ranked_list:
        return 2.0, "مرتبة حسب الخطورة ✓"
    if has_marker:
        return 1.0, "ذكر الترتيب بدون تدرج واضح"
    return 0.0, "مفيش ترتيب حسب الخطورة"


def _br2_specific(text: str) -> tuple[float, str]:
    """R5: من غير عموميات."""
    specific = contains_any(
        text,
        (
            "المستلزمات",
            "المخزن",
            "المبنى",
            "الطابق",
            "المصعد",
            "الحرارة",
            "التأمين",
            "الفاتورة",
            "التصاريح",
            "المورد",
            "شهر",
            "الجدول",
            "الفريق",
            "النقل",
        ),
    )
    vague = contains_any(
        text,
        (
            "الأشياء",
            "أمور",
            "حاجات",
            "بعض",
            "كثير",
            "نوع ما",
            "يمكن",
            "也许",
            "зависит",
            "أسباب عامة",
        ),
    )
    if specific and not vague:
        return 2.0, "أسباب محددة للمشروع ✓"
    if specific:
        return 1.0, "محدد بس فيه عموميات"
    return 0.0, "أسباب عامة"


# --------------------------------------------------------------------------- BR3
def _br3_strong_objections(text: str) -> tuple[float, str]:
    """R1: اعتراضات قوية ومحددة."""
    n = bullet_count(text)
    w = word_count(text)
    # اعتراض قوي = فيه سبب/مفهوم/رقم مش مجرد رأي
    strong = contains_any(
        text,
        (
            "لأن",
            "بسبب",
            "يعني",
            "خلاصة",
            "الخلاصة",
            "100 ألف",
            "100,000",
            "١٠٠ ألف",
            "تدرّب",
            "تدريب",
            "overfit",
            "نسيان",
            "التخصص",
            "فجوة",
            "مفيش ضمان",
            "مش هيعوّض",
            "التكلفة",
            "التعميم",
            "القدرات",
        ),
    )
    if n >= 3 and w >= 55 and strong:
        return 2.0, f"{n} اعتراضات مفصّلة ✓"
    if n >= 3:
        return 1.0, f"{n} اعتراضات"
    if n >= 2:
        return 1.0, f"{n} اعتراضات بس"
    return 0.0, "معتراضات قليلة"


def _br3_style_vs_ability(text: str) -> tuple[float, str]:
    """R2: بيفرق بين الأسلوب والقدرة."""
    style = contains_any(
        text,
        ("الأسلوب", "الشكل", "النبرة", "persona", "ح persona", "prompt", "البرومبت", "الصياغة", "tone", "ستايل"),
    )
    ability = contains_any(
        text,
        (
            "القدرة",
            "القدرات",
            "المعرفة",
            "المهارة",
            "reasoning",
            "الاستدلال",
            "المعمارية",
            "التعميم",
            "generalization",
            "capability",
        ),
    )
    contrast = contains_any(
        text,
        (
            "مش نفس",
            "مختلف",
            "بين",
            "خلاصة",
            "يعني",
            "مش يعني",
            "لا يعني",
            "not the same",
            "while",
            "في المقابل",
        ),
    )
    n = sum([bool(style), bool(ability), bool(contrast)])
    if n >= 2 and style and ability:
        return 2.0, "فرّق بين الأسلوب والقدرة ✓"
    if n >= 1:
        return 1.0, "لمس الفرق بس مش واضح"
    return 0.0, "مفيش تمييز بين الأسلوب والقدرة"


def _br3_overtraining(text: str) -> tuple[float, str]:
    """R3: بيذكر خطر الإفراط في التدريب ونسيان القدرات."""
    overtrain = contains_any(
        text,
        (
            "الإفراط",
            "فرط",
            "زيادة",
            "كتر",
            "أكثر",
            "overfit",
            "over-train",
            "catastrophic forgetting",
            "نسيان",
            "ينسى",
            "نسي",
            "التخصص المفرط",
            "ضياع",
            "فقد",
        ),
    )
    forget = contains_any(
        text,
        (
            "نسيان",
            "ينسى",
            "نسي",
            "نسيت",
            "فقدان",
            "ت forgetting",
            "catastrophic",
            "يتخصص",
            "يضيق",
            "regression",
            "تراجع",
        ),
    )
    overfit = contains_any(text, ("overfit", "overfitting", "ت memoriz", "حفظ", "يتذكر", "حفظTraining"))
    n = sum([bool(overtrain), bool(forget), bool(overfit)])
    if n >= 2:
        return 2.0, f"ذكر الإفراط/نسيان القدرات ({n}/3) ✓"
    if n == 1:
        return 1.0, "ذكر خطر واحد بس"
    return 0.0, "مفيش ذكر لخطر الإفراط في التدريب"


def _br3_cheaper_alternatives(text: str) -> tuple[float, str]:
    """R4: بيقترح بدائل أرخص (system prompt، RAG، اختيار نموذج أقرب)."""
    alternatives = (
        ("system prompt", "البرومبت", "system", "تعليمات", "instructions", "الشخصية", "persona"),
        ("RAG", "استرجاع", "retrieval", "قاعدة معرفة", "knowledge base", "مستندات"),
        ("نموذج أقرب", "نموذج أكبر", "model", "أقوى", "أذكى", "Gemini", "الفرق", "مقارنة"),
        ("few-shot", "أمثلة", "examples", "تعلم من", "imitation"),
        ("أخف", "أرخص", "cheaper", "أقل تكلفة", "cost", "ميزانية", "budget"),
    )
    hits = sum(1 for group in alternatives if contains_any(text, group))
    if hits >= 3:
        return 2.0, f"{hits} بدائل أرخص ✓"
    if hits >= 1:
        return 1.0, f"{hits} بديل"
    return 0.0, "مفيش بدائل أرخص"


def _br3_not_rude(text: str) -> tuple[float, str]:
    """R5: من غير مجاملة ولا قسوة زايدة."""
    harsh = (
        "غبي",
        "أحمق",
        "تافه",
        "سخيف",
        "مقرف",
        "بليد",
        "حماقة",
        "فاشل",
        " cari",
        "sucks",
        "stupid",
    )
    soft = contains_any(text, ("أنصح", "بصراحة", "رأيي", "من تجربتي", "أقترح", "تحذير", "نصيحة", "بالحرف"))
    if contains_any(text, harsh):
        return 0.0, "فيه قسوة زايدة"
    if soft:
        return 2.0, "نقد حازم بدون قسوة ✓"
    return 1.0, "مفيش قسوة بس كمان مفيش ليونة"


# --------------------------------------------------------------------------- TL
def _tool_calls(ctx: dict) -> list[dict]:
    calls = ctx.get("tool_calls") if isinstance(ctx, dict) else None
    return list(calls or [])


def _call_args(call: dict) -> dict:
    args = call.get("arguments") or call.get("args") or call.get("parameters") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, TypeError):
            args = {}
    return args if isinstance(args, dict) else {}


def _call_name(call: dict) -> str:
    return str(call.get("name") or call.get("function") or call.get("tool") or "").strip().lower()


# ------------------------------------------------------------------ TL1
def _tl1_get_stock_first(text: str, ctx: dict) -> tuple[float, str]:
    """R1: بيستدعي get_stock الأول لوحده."""
    calls = _tool_calls(ctx)
    if not calls:
        return 0.0, "مفيش استدعاءات أدوات"
    first = _call_name(calls[0])
    if first != "get_stock":
        return 0.0, f"أول استدعاء كان «{first or '؟'}» مش get_stock"
    args = _call_args(calls[0])
    item = str(args.get("item_id") or args.get("item") or "").strip()
    if item and item.upper() != "SUT-45":
        return 1.0, f"استدعى get_stock بس بـ item_id={item}"
    return 2.0, "get_stock أول استدعاء ✓"


def _tl1_no_fabrication(text: str, ctx: dict) -> tuple[float, str]:
    """R2: مبيألفش نتيجة المخزون."""
    calls = _tool_calls(ctx)
    results = (ctx.get("tool_results") or {}) if isinstance(ctx, dict) else {}
    stock = results.get("get_stock", results.get("stock"))
    calls_before = [c for c in calls if _call_name(c) == "get_stock"]
    # لو فيه نص قبل أول استدعاء بذكر كمية مخزون ⇒ تأليف
    first_call_text = ""
    if isinstance(ctx, dict):
        first_call_text = str(ctx.get("text_before_first_call") or "")
    nums = [n for n in numbers_in(first_call_text) if n >= 1]
    if nums:
        return 0.0, f"ذكر أرقام قبل النتيجة: {nums[:3]}"
    if calls_before and stock is None:
        return 1.0, "استدعى الأداة بس مفيش نتيجة مرجعة"
    return 2.0, "مبيألفش نتيجة المخزون ✓"


def _tl1_create_po(text: str, ctx: dict) -> tuple[float, str]:
    """R3: بعد النتيجة (٦٠) بيستدعي create_po بالقيم الصح."""
    calls = _tool_calls(ctx)
    po_calls = [c for c in calls if _call_name(c) == "create_po"]
    if not po_calls:
        return 0.0, "مفيش استدعاء create_po"
    args = _call_args(po_calls[0])
    item = str(args.get("item_id") or args.get("item") or "").strip()
    qty = args.get("qty") or args.get("quantity") or args.get("amount")
    vendor = str(args.get("vendor") or args.get("supplier") or args.get("مورد") or "").strip()
    problems = []
    if item.upper() != "SUT-45":
        problems.append(f"item_id={item}")
    try:
        if int(qty) != 300:
            problems.append(f"qty={qty}")
    except (TypeError, ValueError):
        problems.append(f"qty={qty}")
    if "نيل" not in vendor and vendor.upper() != "NILE":
        problems.append(f"vendor={vendor}")
    if not problems:
        return 2.0, "create_po بالقيم الصحيحة (SUT-45 · 300 · النيل) ✓"
    return 0.0, "قيم create_po غلط: " + " · ".join(problems)


def _tl1_call_format(text: str, ctx: dict) -> tuple[float, str]:
    """R4: صيغة الاستدعاء سليمة."""
    calls = _tool_calls(ctx)
    if not calls:
        return 0.0, "مفيش استدعاءات"
    ok_calls = 0
    for c in calls:
        name = _call_name(c)
        args = _call_args(c)
        if name == "get_stock" and "item_id" in args:
            ok_calls += 1
        elif name == "create_po" and {"item_id", "qty", "vendor"} <= set(args.keys()):
            ok_calls += 1
    if ok_calls == len(calls):
        return 2.0, f"كل الـ {len(calls)} استدعاءات بصيغة سليمة ✓"
    if ok_calls > 0:
        return 1.0, f"{ok_calls}/{len(calls)} صيغة سليمة"
    return 0.0, "كل الاستدعاءات بصيغة غلط"


def _tl1_final_summary(text: str, ctx: dict) -> tuple[float, str]:
    """R5: رد نهائي يلخص اللي حصل."""
    w = word_count(text)
    mentions_stock = contains_any(text, ("المخزون", "المخزن", "الكمية", "stock", "SUT-45", "sut-45", "60", "٦٠"))
    mentions_po = contains_any(
        text, ("أمر الشراء", "أمر شراء", "الطلب", "PO", "أنشأ", "تم إنشاء", "عملت", "تم")
    )
    if mentions_stock and mentions_po and w >= 15:
        return 2.0, "ملخص نهائي واضح ✓"
    if mentions_stock or mentions_po:
        return 1.0, "ملخص ناقص"
    return 0.0, "مفيش ملخص نهائي"


# ------------------------------------------------------------------ TL2
def _tl2_no_guessed_po(text: str, ctx: dict) -> tuple[float, str]:
    """R1: مبيستدعيش create_po بقيم متخمنة."""
    calls = _tool_calls(ctx)
    po_calls = [c for c in calls if _call_name(c) == "create_po"]
    if not po_calls:
        return 2.0, "مبيستدعيش create_po ✓"
    args = _call_args(po_calls[0])
    item = str(args.get("item_id") or args.get("item") or "").strip()
    qty = args.get("qty")
    vendor = str(args.get("vendor") or "").strip()
    guessed = []
    if item:
        guessed.append(f"item={item}")
    if qty not in (None, ""):
        guessed.append(f"qty={qty}")
    if vendor:
        guessed.append(f"vendor={vendor}")
    if guessed:
        return 0.0, "استدعى create_po بقيم متخمنة: " + " · ".join(guessed)
    return 1.0, "استدعى create_po بس من غير قيم"


def _tl2_asks_qty(text: str, ctx: dict) -> tuple[float, str]:
    """R2: بيسأل عن الكمية."""
    # لازم يكون **سؤال** (فيه علامة استفهام أو صيغة سؤال) مش مجرد ذكر
    has_qmark = "؟" in text or "?" in text
    asks = contains_any(
        text,
        (
            "الكمية",
            "كمية",
            "كام",
            "بكام",
            "عدد",
            "qty",
            "quantity",
            "الجرعة",
            "كم",
        ),
    )
    asks_pattern = bool(
        re.search(
            r"(?:إيه|ايه|ما\s*هي|ماهي|كام|كم|قد\s*إيه|قد إيه|أو\s*كام)\s*(?:ال)?(?:كمية|عدد)",
            text,
        )
    )
    if asks and (has_qmark or asks_pattern):
        return 2.0, "سأل عن الكمية ✓"
    if asks:
        return 1.0, "ذكر الكمية بس من غير ما يسأل"
    return 0.0, "مفيش سؤال عن الكمية"


def _tl2_asks_vendor_or_code(text: str, ctx: dict) -> tuple[float, str]:
    """R3: بيسأل عن المورد أو كود الصنف."""
    has_qmark = "؟" in text or "?" in text
    vendor = contains_any(text, ("المورد", "مورد", "vendor", "supplier", "المورّد"))
    code = contains_any(text, ("كود", "code", "الصنف", "صنف", "item", "رقم الصنف", "المنتج", "product"))
    if not (vendor or code):
        return 0.0, "مفيش سؤال عن المورد أو الكود"
    if has_qmark:
        return 2.0, "سأل عن المورد/كود الصنف ✓"
    return 1.0, "ذكر المورد/الكود بس من غير ما يسأل"


def _tl2_one_question(text: str, ctx: dict) -> tuple[float, str]:
    """R4: سؤال واحد مرتب مش حوار طويل."""
    n_q = text.count("؟") + text.count("?")
    w = word_count(text)
    # لو الرد بيعلن إنشاء أمر شراء ⇒ مش سؤال أصلاً
    claims_done = contains_any(
        text,
        ("تم إنشاء", "عملت أمر", "أمر شراء تم", "تم عمل", "أنشأت", "تم reserv", "حجزت"),
    )
    if claims_done:
        return 0.0, "علن تنفيذ الأمر بدل ما يسأل"
    if n_q == 1 and w <= 90:
        return 2.0, "سؤال واحد مختصر ✓"
    if n_q == 1:
        return 1.0, "سؤال واحد بس طويل شوية"
    if n_q == 0:
        return 0.0, "مفيش سؤال"
    return 0.0, f"{n_q} أسئلة — حوار طويل"


def _tl2_stock_optional(text: str, ctx: dict) -> tuple[float, str]:
    """R5: بيعرض يتأكد من المخزون الأول (اختياري)."""
    if contains_any(
        text,
        ("المخزون", "المخزن", "أتحقق", "نتأكد", "أراجع", "الكمية المتاحة", "stock", "المتاح"),
    ):
        return 2.0, "عرض التأكد من المخزون ✓"
    return 1.0, "مفيش عرض للتأكد من المخزون (اختياري)"


# ------------------------------------------------------------------ TL3
def _tl3_three_tasks(text: str) -> tuple[float, str]:
    """R1: ٣ مهام واضحة."""
    n = bullet_count(text)
    roles = (
        ("جامع", "جمع", "collector", "data collector", "الجمع"),
        ("محلل", "تحليل", "analyst", "المحلل"),
        ("كاتب", "كتابة", "writer", "الكاتب", "صياغة"),
    )
    found = sum(1 for r in roles if contains_any(text, r))
    if n >= 3 and found >= 2:
        return 2.0, f"٣ مهام بـ {found} أدوار ✓"
    if n >= 3 or found >= 2:
        return 1.0, "مهام/أدوار جزئية"
    return 0.0, "مفيش ٣ مهام واضحة"


def _tl3_inputs_outputs(text: str) -> tuple[float, str]:
    """R2: مدخلات ومخرجات كل وكيل متسقة."""
    has_in = contains_any(text, ("المدخلات", "مدخلات", "input", "يستهلك", "يأخذ من", "المصدر", "بيانات"))
    has_out = contains_any(text, ("المخرجات", "مخرجات", "output", "ينتج", "يسلم", "يُسلّم", "المخرج"))
    both = bool(has_in and has_out)
    n_pairs = count_any(text, ("المدخلات", "المخرجات", "input", "output"))
    if both and n_pairs >= 2:
        return 2.0, "مدخلات/مخرجات لكل وكيل ✓"
    if both:
        return 1.0, "ذكر المدخلات/المخرجات بس مش لكل وكيل"
    return 0.0, "مفيش تحديد للمدخلات/المخرجات"


def _tl3_handoff(text: str) -> tuple[float, str]:
    """R3: صيغة تسليم بين الوكلاء (ملف أو جدول)."""
    handoff = contains_any(
        text,
        (
            "ملف",
            "جدول",
            "CSV",
            "csv",
            "JSON",
            "json",
            "XML",
            "Markdown",
            "markdown",
            "MD",
            "ملف نصي",
            "تقرير",
            "ملخص",
            "Spreadsheet",
            "ورقة",
            "XLSX",
        ),
    )
    if handoff:
        return 2.0, "صيغة تسليم محددة ✓"
    return 0.0, "مفيش صيغة تسليم"


def _tl3_quality_checks(text: str) -> tuple[float, str]:
    """R4: شروط جودة وتحقق."""
    quality = contains_any(
        text,
        (
            "تحقق",
            "مراجعة",
            "دقة",
            "مطابقة",
            "مطابق",
            "اختبار",
            "جودة",
            "معايير",
            "معيار",
            "checksum",
            "validation",
            "ضمان",
            "cross-check",
        ),
    )
    if quality:
        return 2.0, "شروط جودة/تحقق موجودة ✓"
    return 0.0, "مفيش شروط جودة"


def _tl3_small_model(text: str) -> tuple[float, str]:
    """R5: مناسبة لنموذج صغير."""
    w = word_count(text)
    tasks = max(1, bullet_count(text))
    per_task = w / tasks
    complex_words = count_any(text, ("صUTO", "معقد", "معقدة", "متقدم", "متقدمة", "تحليل متعمق", "باحث"))
    if per_task <= 60 and complex_words <= 1:
        return 2.0, f"مهمة واحدة بسيطة لكل وكيل (~{int(per_task)} كلمة) ✓"
    if per_task <= 90:
        return 1.0, f"متوسط (~{int(per_task)} كلمة/مهمة)"
    return 0.0, f"مهام كبيرة لنموذج صغير (~{int(per_task)} كلمة/مهمة)"


CHECKS_BR = {
    "BR1": [_br1_ideas, _br1_diverse, _br1_unconventional, _br1_ranked, _br1_actionable],
    "BR2": [_br2_five_causes, _br2_prevention_linked, _br2_human_operational, _br2_by_severity, _br2_specific],
    "BR3": [
        _br3_strong_objections,
        _br3_style_vs_ability,
        _br3_overtraining,
        _br3_cheaper_alternatives,
        _br3_not_rude,
    ],
}

CHECKS_TL = {
    "TL1": [
        _tl1_get_stock_first,
        _tl1_no_fabrication,
        _tl1_create_po,
        _tl1_call_format,
        _tl1_final_summary,
    ],
    "TL2": [
        _tl2_no_guessed_po,
        _tl2_asks_qty,
        _tl2_asks_vendor_or_code,
        _tl2_one_question,
        _tl2_stock_optional,
    ],
    "TL3": [
        _tl3_three_tasks,
        _tl3_inputs_outputs,
        _tl3_handoff,
        _tl3_quality_checks,
        _tl3_small_model,
    ],
}

#: كل فحوص BR + TL
CHECKS_BR_TL: dict[str, list] = {**CHECKS_BR, **CHECKS_TL}
