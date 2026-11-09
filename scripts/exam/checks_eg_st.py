"""فحوص الـ rubric — المحور EG (العامية المصرية والشخصية) + ST (أسلوب Gemini).

كل فحص = (text, ctx) -> (points 0..2, note).
النقاط: 2 = المعيار متحقق · 1 = جزئي · 0 = متحققش.
"""
from __future__ import annotations

import itertools

from .rubric_lib import (
    bullet_count,
    contains_any,
    contains_groups,
    count_any,
    dialect_per_1k,
    duplicate_lines,
    english_count,
    repeated_clause_count,
    repetition_score,
    fail,
    header_count,
    has_table,
    msa_per_1k,
    non_empty_lines,
    numbers_in,
    ok,
    position_of,
    repetition_ratio,
    table_rows,
    word_count,
)

# --------------------------------------------------------------------------- مشترك
DIALECT_WORDS = (
    "إزيك",
    "إزاي",
    "إيه",
    "فين",
    "ليه",
    "عايز",
    "كده",
    "دلوقتي",
    "بص",
    "تمام",
    "أهو",
    "هنعمل",
    "ينفع",
    "عشان",
    "بجد",
    "بكام",
    "ممكن",
    "محتاج",
    "فاهم",
    "ماشي",
    "بقي",
    "نعمل",
    "نشوف",
    "نتكلم",
    "جميل",
    "امبارح",
    "النهارده",
    "بتاع",
    "اللي",
    "ده",
    "دي",
)

HEDGE_WORDS = (
    "مش عارف",
    "مش متأكد",
    "مش متاكد",
    "معروفش",
    "مش موجود",
    "ما أعرفش",
    "معرفش",
    "لازم أبحث",
    "أبحث",
    "دور على",
    "راجع",
    "مصدر",
    "مش متاح",
    "ما ينفعش أقول",
    "مش هقدر أقول",
    "التاريخ",
    "الآن",
    "دلوقتي",
)


def _eg_dialect(text: str) -> tuple[float, str]:
    """معيار: عامية مصرية طبيعية (مش فصحى ثقيلة ولا تشوّه).

    الاعتماد على **الكثافة** (علامات/1000 كلمة) مش على عدّ كلمات بعينها —
    لأن «زي» و«يعني» و«تمام» كلها عامية طبيعية لكن مش في القامو�� فقط.
    """
    hits = count_any(text, DIALECT_WORDS)
    density = dialect_per_1k(text)
    msa = msa_per_1k(text)
    if density >= 5.0 and msa <= 14:
        return 2.0, f"عامية واضحة ({hits} علامة · {density}/1000 كلمة · فصحى {msa}/1000)"
    if density >= 2.0 and msa <= 22:
        return 1.0, f"عامية جزئية ({hits} علامة · {density}/1000 · فصحى {msa}/1000)"
    return 0.0, f"عامية ضعيفة/فصحى ({hits} علامة · {density}/1000 · فصحى {msa}/1000)"


def _no_heavy_msa(text: str) -> tuple[float, str]:
    msa = msa_per_1k(text)
    if msa <= 8:
        return 2.0, f"فصحى ثقيلة شبه معدومة ({msa}/1000 كلمة)"
    if msa <= 16:
        return 1.0, f"فصحى خفيفة ({msa}/1000 كلمة)"
    return 0.0, f"فصحى ثقيلة ({msa}/1000 كلمة)"


def _reasonable_len(text: str, lo: int, hi: int) -> tuple[float, str]:
    w = word_count(text)
    if lo <= w <= hi:
        return 2.0, f"طول مناسب ({w} كلمة)"
    if w <= hi * 1.4:
        return 1.0, f"طول قريب ({w} كلمة، المطلوب {lo}..{hi})"
    return 0.0, f"طول بعيد ({w} كلمة، المطلوب {lo}..{hi})"


# --------------------------------------------------------------------------- EG1
WARMTH_WORDS = (
    "فاهم",
    "آسف",
    "أسف",
    "مؤسف",
    "حاسس",
    "وجع",
    "موقف صعب",
    "تعب",
    "متعانق",
    "إنت",
    "يا صاحبي",
    "صاحبي",
    "صح",
    "من حقك",
    "مجبرك",
    "ربنا",
    "الله",
    "يهديك",
)
PREACH_WORDS = ("ربنا", "ربنا يوفقك", "فologists", "الصلاة", "الدعاء", "قضاء وقدر")


def _warmth(text: str) -> tuple[float, str]:
    head = text[:400]
    if contains_any(head, WARMTH_WORDS) and not contains_any(head, PREACH_WORDS):
        return 2.0, "بيبدأ بتعاطف"
    if contains_any(text, WARMTH_WORDS):
        return 1.0, "فيه تعاطف بس مش في أول الرد"
    return 0.0, "مفيش تعاطف واضح"


ACTION_WORDS = (
    "ابدأ",
    "ابدأ",
    "خُد",
    "خد",
    "حاول",
    "اقسم",
    "نام",
    "اشرب",
    "امشي",
    "سجّل",
    "اكتب",
    "اترك",
    "بعيد عن",
    "امنع",
    "قلل",
    "جهّز",
    "حط",
    "خلي",
    "اتمرن",
    "وظّف",
)


def _actionable(text: str) -> tuple[float, str]:
    n = contains_groups(
        text,
        (
            ACTION_WORDS,
            ("بكرة", "الصبح", "بعدين", "بالليل", "الظهر", "مساء", "يوميًا", "كل يوم", "أول أسبوع", "الشهر"),
            ("اكتب", "سجّل", "نام", "امشي", "اشرب", "خذ", "اتصل", "راجع", "قسم"),
        ),
    )
    if n >= 2:
        return 2.0, "نصايح عملية ومحددة"
    if n == 1:
        return 1.0, "نصيحة عملية واحدة بس"
    return 0.0, "كلام عام بدون خطوات"


DIAGNOSIS_WORDS = (
    "عندك اكتئاب",
    "اكتئاب",
    "أنت عندك",
    "عندك قلق",
    "تشخيص",
    "مريض",
    "مرض",
    "اضطراب",
    "ضغط نفسي",
    "حالة نفسية",
)


def _no_diagnosis(text: str) -> tuple[float, str]:
    if contains_any(text, DIAGNOSIS_WORDS):
        return 0.0, "فيه إيحاء بتشخيص/مرض"
    return 2.0, "مفيش تشخيص ولا إيحاء بمرض"


# --------------------------------------------------------------------------- EG2
def _eg2_diff(text: str) -> tuple[float, str]:
    has_capex = contains_any(text, ("capex", "كابكس", "رأس المال", "راس المال", "استثمار"))
    has_opex = contains_any(text, ("opex", "أوبكس", "أوبك", "تشغيل", "تشغيلي", "المصروفات", "استهلاك"))
    if has_capex and has_opex:
        return 2.0, "الفرق بين CAPEX و OPEX موضّح"
    if has_capex or has_opex:
        return 1.0, "ذكر المصطلح واحد بس"
    return 0.0, "ما ذُكرش الفرق"


def _eg2_example(text: str) -> tuple[float, str]:
    medical = ("مستشفى", "المستشفى", "قسطرة", "جهاز", "مستهلك", "المستلزمات", "أجهزة", "المعمل", "العيادة")
    marker = ("مثال", "مثلا", "مثل", "زي", "بمعنى", "يعني", "زي مثلا")
    if contains_any(text, medical) and contains_any(text, marker):
        return 2.0, "فيه مثال من المستشفى"
    if contains_any(text, medical):
        return 1.0, "ذكر سياق المستشفى بس من غير مثال واضح"
    return 0.0, "مفيش مثال من المستشفى"


def _eg2_terms(text: str) -> tuple[float, str]:
    n = english_count(text)
    if n == 0:
        return 0.0, "مفيش أي مصطلحات إنجليزية"
    if n <= 18:
        return 2.0, f"مصطلحات إنجليزية معقولة ({n} كلمة)"
    if n <= 30:
        return 1.0, f"إنجليزي كتير شوية ({n} كلمة)"
    return 0.0, f"إنجليزي مبالغ فيه ({n} كلمة)"


def _eg2_short(text: str) -> tuple[float, str]:
    w = word_count(text)
    structured = bullet_count(text) >= 2 or header_count(text) >= 1
    if w <= 200 and structured:
        return 2.0, f"قصير ومنظم ({w} كلمة)"
    if w <= 200:
        return 2.0, f"قصير ({w} كلمة)"
    if w <= 260:
        return 1.0, f"مقبول الطول ({w} كلمة)"
    return 0.0, f"طويل ({w} كلمة)"


# --------------------------------------------------------------------------- EG3
def _eg3_tone(text: str) -> tuple[float, str]:
    firm = contains_any(text, ("لازم", "محتاج", "من فضلك", "لو سمحت", "مطلوب", "ضروري", "بتستنّى", "بتنتظر"))
    polite = contains_any(text, ("محترم", "شكرا", "شكرًا", "نشكرك", "آسف", "أسف", "تحيات", "بالتوفيق", "الله يبارك"))
    if firm and polite:
        return 2.0, "نبرة حازمة ومحترمة"
    if firm or polite:
        return 1.0, "النبرة ناقصة أحد الجانبين"
    return 0.0, "مفيش نبرة حازمة ولا محترمة واضحة"


def _eg3_deadline(text: str) -> tuple[float, str]:
    request = contains_any(text, ("أرسل", "ابعت", "راجع", "مستلم", "استلم", "عايز", "محتاج", "ممكن"))
    deadline = contains_any(text, ("خلال", "قبل", "بتاريخ", "تاريخ", "يوم", "أسبوع", "موعد", "الجمعة", "السبت", "الأحد", "الاثنين"))
    if request and deadline:
        return 2.0, "فيه طلب محدد وموعد"
    if request or deadline:
        return 1.0, "الطلب أو الموعد ناقص"
    return 0.0, "مفيش طلب واضح ولا موعد"


def _eg3_lines(text: str) -> tuple[float, str]:
    n = len(non_empty_lines(text))
    if n <= 6:
        return 2.0, f"{n} سطور — ضمن الحد"
    if n <= 8:
        return 1.0, f"{n} سطور — تجاوزت الحد قليلاً"
    return 0.0, f"{n} سطور — كتير"


THREAT_WORDS = (
    "بلاش",
    "هبلغ",
    "قانون",
    "محكمة",
    "فصل",
    "استقالة",
    "خسرك",
    "آخر مرة",
    "من غير ما",
    "وإلا",
    "هشي",
    "هدي",
    "بشكل نهائي",
)


def _eg3_no_threat(text: str) -> tuple[float, str]:
    if contains_any(text, THREAT_WORDS):
        return 0.0, "فيه تهديد غير واقعي"
    return 2.0, "مفيش تهديد"


# --------------------------------------------------------------------------- EG4
HUMOR_WORDS = (
    "هه",
    "ههه",
    "😂",
    "🤣",
    "😅",
    "😄",
    "🤣",
    "ماشي",
    "يا عم",
    "يا سلااام",
    "إنت جنان",
    "واحد بيشتغل",
    "بجد",
    "تمام كده",
    "يسلمو",
    "ده أنا",
)


def _eg4_humor(text: str) -> tuple[float, str]:
    n = contains_groups(text, (HUMOR_WORDS, ("😂", "🤣", "😅", "😄", "😁"), ("هه", "ههه", "هاها")))
    if n >= 2:
        return 2.0, "خفة دم مصرية مفهومة"
    if n == 1:
        return 1.0, "فيه خفة دم خفيفة"
    return 0.0, "مفيش خفة دم"


def _eg4_not_hurtful(text: str) -> tuple[float, str]:
    harsh = ("غبي", "أحمق", "فاشل", "تافه", "سخيف", "خايس", "بليد", "مقرف", "سucker")
    if contains_any(text, harsh):
        return 0.0, "فيه كلام جارح"
    return 2.0, "مفيش جرح"


def _eg4_smart(text: str) -> tuple[float, str]:
    insight = contains_any(text, ("لأن", "يعني", "الخلاصة", "خلاصة", "في الحقيقة", "بصراحة", "المهم", "درس", "Observed", "الدرس", "أكتر", "أكثر", "هو إن", "يعني إن", "في الآخر"))
    w = word_count(text)
    if insight and w >= 12:
        return 2.0, "فيه ملاحظة ذكية ✓"
    if w >= 12:
        return 0.0, "كلام عام من غير استنتاج ذكي"
    return 0.0, "رد ضحك بدون ملاحظة"


def _eg4_short(text: str) -> tuple[float, str]:
    w = word_count(text)
    if w <= 90:
        return 2.0, f"قصير ({w} كلمة)"
    if w <= 140:
        return 1.0, f"مقبول ({w} كلمة)"
    return 0.0, f"طويل ({w} كلمة)"


def _eg4_close(text: str) -> tuple[float, str]:
    closing = contains_any(text, ("؟", "?", "تحب", "عايز", "جرّب", "جرب", "خلّك", "خلي بالك", "بنصيحة", "لو عملت", "اتمرن", "اسأل"))
    if closing:
        return 2.0, "ينتهي بنصيحة أو سؤال لطيف"
    return 0.0, "مفيش ختام مفيد"


# --------------------------------------------------------------------------- EG5
def _eg5_meaning(text: str) -> tuple[float, str]:
    groups = (
        ("اللجنة", "لجنة", "الجنة", "لجنتنا", "المجنة"),
        ("وافق", "موافقة", "وافق", "قررت", "صدقت", "تمت الموافقة", "التفويض"),
        ("الميزانية", "ميزانية", "ميزانيه", "budget"),
        ("بشروط", "بشرط", "شرط", "مشروط", "في حالة", "بـ"),
        ("أسعار المورد", "سعر المورد", "أسعار المورد", "تحقق من الأسعار", "تأكيد الأسعار", "مراجعة الأسعار", "أسعار الموردين", "تسعير المورد"),
    )
    hits = contains_groups(text, groups)
    if hits >= 4:
        return 2.0, f"المعنى كامل ({hits}/5 عناصر)"
    if hits >= 2:
        return 1.0, f"المعنى ناقص ({hits}/5 عناصر)"
    return 0.0, f"المعنى ناقص جدًا ({hits}/5 عناصر)"


def _eg5_arabic(text: str) -> tuple[float, str]:
    literal = ("procurement", "committee", "approved", "budget", "contingent", "vendor")
    if contains_any(text, literal):
        return 0.0, "ترجمة حرفية (كلمات إنجليزية سليمة)"
    # علامة ترجمة حرفية: صياغة فصحى ثقيلة أو غياب أي عامية
    msa = msa_per_1k(text)
    density = dialect_per_1k(text)
    if msa <= 8 and density >= 2.0:
        return 2.0, "عامية طبيعية بدون ترجمة حرفية ✓"
    if msa <= 16:
        return 1.0, f"عربية سليمة ({msa}/1000 فصحى) بس مش عامية واضحة"
    return 0.0, f"ترجمة حرفية/فصحى ثقيلة ({msa}/1000)"


def _eg5_short(text: str) -> tuple[float, str]:
    from .rubric_lib import sentence_count

    n = sentence_count(text)
    if 1 <= n <= 2:
        return 2.0, f"{n} جمل"
    if n == 3:
        return 1.0, "3 جمل — زيادة بسيطة"
    return 0.0, f"{n} جمل — كتير"


def _eg5_no_extra(text: str) -> tuple[float, str]:
    extra = ("الترجمة", "يعني الجملة", "بمعنى", "الشرح", "والأصل", "الإنجليزي", "النص الأصلي")
    w = word_count(text)
    if contains_any(text, extra) or w > 70:
        return 0.0, "فيه شرح زيادة"
    return 2.0, "مفيش شرح زيادة"


# --------------------------------------------------------------------------- EG6
def _eg6_five_lines(text: str) -> tuple[float, str]:
    n = len(non_empty_lines(text))
    if 4 <= n <= 6:
        return 2.0, f"{n} سطور"
    if n in (3, 7):
        return 1.0, f"{n} سطور — قريب"
    return 0.0, f"{n} سطور — بعيد عن 5"


def _eg6_reasons(text: str) -> tuple[float, str]:
    groups = (
        ("خوف", "الخوف", "خايف", "مخاوف"),
        ("حمل شغل", "الشغل", "ضغط", "كتر شغل", "إرهاق", "الإرهاق"),
        ("عدم ثقة", "ثقة", "مش واثق", "لا يثق", "شك"),
        ("عادة", "العادة", "مPreviously", "السابق", "زمان", "قديم"),
    )
    hits = contains_groups(text, groups)
    if hits >= 3:
        return 2.0, f"أسباب واقعية ({hits}/4)"
    if hits >= 1:
        return 1.0, f"سبب واحد بس ({hits}/4)"
    return 0.0, "مفيش أسباب واقعية"


def _eg6_little_english(text: str) -> tuple[float, str]:
    n = english_count(text)
    if n <= 3:
        return 2.0, f"إنجليزي قليل جداً ({n} كلمة)"
    if n <= 7:
        return 1.0, f"إنجليزي مقبول ({n} كلمة)"
    return 0.0, f"إنجليزي كتير ({n} كلمة)"


def _eg6_no_repeat(text: str) -> tuple[float, str]:
    rep = repetition_score(text)
    dup = duplicate_lines(text)
    clause = repeated_clause_count(text)
    if clause >= 2:
        return 0.0, f"تكرار واضح (جملة مكررة {clause} مرات · نسبة {rep})"
    if rep < 0.25 and dup == 0:
        return 2.0, "مفيش تكرار"
    if rep < 0.45 and dup <= 1:
        return 1.0, f"تكرار بسيط (نسبة {rep})"
    return 0.0, f"تكرار واضح (نسبة {rep} · {dup} سطر مكرر)"


# --------------------------------------------------------------------------- ST1
ASSUMPTION_WORDS = (
    "افترض",
    "بافتراض",
    "بفترض",
    "افتراض",
    "لو",
    "إذا",
    "بفرض",
    "نفترض",
    "مثال",
    "مثلا",
    "بنعتبر",
)
PRIORITY_WORDS = ("أولوية", "الأولوية", "أهم", "الأهم", "أول", "الترتيب", "مرتبة", "بعدين", "أخير")
REALITY_WORDS = (
    "اجتماع",
    "متابعة",
    "تأخير",
    "احتياطي",
    "هامش",
    "buffer",
    "مراجعة",
    "أأجل",
    "اتراجع",
    "أراجع",
)
RISK_WORDS = (
    "منافسة",
    "تأخير",
    "تأخر",
    "وقت",
    "مخاطر",
    "مخاطرة",
    "تكلفة",
    "تسويق",
    "حقوق",
    "royalties",
    "جودة",
    "محتوى",
    "مش مضمون",
    "السوق",
)


def _st1_hours(text: str) -> tuple[float, str]:
    vals = sorted({int(n) for n in numbers_in(text) if 0 < n <= 24})
    found = 20 in vals
    if not found:
        for size in range(2, min(5, len(vals)) + 1):
            for combo in itertools.combinations(vals, size):
                if sum(combo) == 20:
                    found = True
                    break
            if found:
                break
    if found:
        return 2.0, f"مجموع الساعات = 20 فعليًا ({vals})"
    if vals:
        return 1.0, f"تقسيم بس المجموع مش 20 ({vals})"
    return 0.0, "مفيش تقسيم بالساعات"


def _st1_priority(text: str) -> tuple[float, str]:
    if contains_any(text, PRIORITY_WORDS) and contains_any(text, ("عشان", "لأن", "بسبب", "علشان", "المشكلة", "لأن")):
        return 2.0, "أولويات بسبب واضح"
    if contains_any(text, PRIORITY_WORDS):
        return 1.0, "ترتيب بس السبب مش واضح"
    return 0.0, "مفيش ترتيب بالأولويات"


def _st1_assumptions(text: str) -> tuple[float, str]:
    if contains_any(text, ASSUMPTION_WORDS):
        return 2.0, "الافتراضات مذكورة"
    return 0.0, "مفيش افتراضات"


def _st1_reality(text: str) -> tuple[float, str]:
    if contains_any(text, REALITY_WORDS):
        return 2.0, "فيه وقت للتأخير والمتابعة"
    return 0.0, "مفيش هامش واقعي"


def _st1_organized(text: str) -> tuple[float, str]:
    if bullet_count(text) >= 3 or header_count(text) >= 2:
        return 2.0, "تنسيق منظم"
    if bullet_count(text) >= 1:
        return 1.0, "تنسيق جزئي"
    return 0.0, "رد مش منظم"


# --------------------------------------------------------------------------- ST2
def _st2_honest(text: str) -> tuple[float, str]:
    groups = (
        ("بصراحة", "بصراحة", "بصراحةً", "الصراحة", "بالحاحة"),
        ("من غير مجاملة", "مش هز", "بالحقيقة", "الحقيقة", "بالحقيق", "بصراحة كده"),
        ("مخاطر", "مخاطر", "سلبي", "عيوب", "مش هينفع", "مش مضمون", "خسارة", "محدش", "مش مضمون"),
    )
    hits = contains_groups(text, groups)
    if hits >= 2:
        return 2.0, "صراحة بلا مجاملة زايدة"
    if hits == 1:
        return 1.0, "الصراحة ناقصة"
    return 0.0, "رد مجامل أو عام"


def _st2_risks(text: str) -> tuple[float, str]:
    n = contains_groups(
        text,
        (
            RISK_WORDS,
            ("منافس", "منافسة", "السوق", "السوق مزدحم", "كتير ناس"),
            ("royalties", "حقوق", "حقوق النشر", "تأخير", "ببطء", "شهور", "ستة شهور", "٦ شهور"),
        ),
    )
    if n >= 2:
        return 2.0, f"مخاطر حقيقية ({n} نوع)"
    if n == 1:
        return 1.0, "مخاطر قليلة"
    return 0.0, "مفيش مخاطر حقيقية"


def _st2_reality(text: str) -> tuple[float, str]:
    if contains_any(text, ("ممكن", "واقعي", "مش مضمون", "صعب", "ببطء", "نادر", "بعيد", "مش هينفع")):
        return 2.0, "يفرّق بين الممكن والمبالغ"
    return 0.0, "مفيش تمييز بين الممكن والمبالغ"


def _st2_test(text: str) -> tuple[float, str]:
    if contains_any(text, ("جرب", "جرّب", "اختبار", "اختبر", "عينة", "عيّنة", "MVP", "نسخة صغيرة", "أول تجربة")):
        return 2.0, "اقترح اختبار صغير قبل القرار"
    return 0.0, "مفيش اقتراح لاختبار صغير"


def _st2_no_fake_numbers(text: str) -> tuple[float, str]:
    nums = [n for n in numbers_in(text) if n >= 100]
    if not nums:
        return 2.0, "مفيش أرقام كبيرة مفترضة"
    if contains_any(text, ("تقريبا", "تقريبًا", "ممكن", "لو", "افترض", "متوقع", "حوالي", "أقدر", "بحدود")):
        return 1.0, f"أرقام ({nums[:3]}) مع تحفّظ"
    return 0.0, f"أرقام مؤكدة بدون أساس ({nums[:3]})"


# --------------------------------------------------------------------------- ST3
def _st3_format(text: str) -> tuple[float, str]:
    tab = has_table(text)
    rec = max(position_of(text, "توصية"), position_of(text, "أنصح"), position_of(text, "ننصح"), position_of(text, "الأفضل"))
    if tab and rec > 0:
        return 2.0, "جدول ثم توصية"
    if tab or rec > 0:
        return 1.0, "التنسيق ناقص عنصر"
    return 0.0, "مفيش جدول ولا توصية"


def _st3_defs(text: str) -> tuple[float, str]:
    has_mrp = contains_any(text, ("MRP", "تخطيط", "Material Requirements", "الإنتاج", "الطلبات", "المواد"))
    has_kanban = contains_any(text, ("Kanban", "كانبان", "بطاقة", "سحب", "الحد الأدنى", "الحد الأقصى"))
    if has_mrp and has_kanban:
        return 2.0, "التعريفين موجودين"
    if has_mrp or has_kanban:
        return 1.0, "تعريف واحد بس"
    return 0.0, "التعريفات ناقصة"


def _st3_table(text: str) -> tuple[float, str]:
    rows = table_rows(text)
    if rows >= 3:
        return 2.0, f"جدول بمعايير ({rows} صفوف)"
    if rows >= 1:
        return 1.0, f"جدول قصير ({rows} صفوف)"
    return 0.0, "مفيش جدول بمعايير"


def _st3_medical(text: str) -> tuple[float, str]:
    if contains_any(text, ("صلاحية", "طوارئ", "emergency", "منتهي", "تعقيم", "مستلزمات", "الأنبوب", "انتهاء", "FEFO")):
        return 2.0, "التوصية مرتبطة بسياق طبي"
    return 0.0, "التوصية عامة"


def _st3_precise(text: str) -> tuple[float, str]:
    w = word_count(text)
    if w <= 220 and repetition_score(text) < 0.35:
        return 2.0, f"مختصر بدون حشو ({w} كلمة)"
    if w <= 320:
        return 1.0, f"طول متوسط ({w} كلمة)"
    return 0.0, f"طول مبالغ فيه ({w} كلمة)"


# --------------------------------------------------------------------------- ST4
def _st4_factors(text: str) -> tuple[float, str]:
    groups = (
        ("صلاحية", "الصلاحية", "انتهاء", "expiry"),
        ("تمويل", "التمويل", "الكاش", "سيولة", "نقد"),
        ("تخزين", "التخزين", "المخزن", "تكلفة التخزين"),
        ("الاستهلاك", "استهلاك", "معدل الاستهلاك", "تغيّر الاستهلاك", "تغير الاستهلاك"),
    )
    hits = contains_groups(text, groups)
    if hits >= 3:
        return 2.0, f"العوامل الأساسية ({hits}/4)"
    if hits >= 1:
        return 1.0, f"عوامل ناقصة ({hits}/4)"
    return 0.0, "مفيش عوامل"


def _st4_numbers(text: str) -> tuple[float, str]:
    if contains_any(text, ASSUMPTION_WORDS) and numbers_in(text):
        return 2.0, "أرقام/افتراضات صريحة"
    if contains_any(text, ASSUMPTION_WORDS):
        return 1.0, "بيفترض بدون أرقام"
    return 0.0, "مفيش أرقام ولا افتراضات"


def _st4_example(text: str) -> tuple[float, str]:
    if contains_any(text, ("مثال", "مثلا", "بفرض", "لو اشترينا", "لو الكمية")) and numbers_in(text):
        return 2.0, "فيه مقارنة رقمية"
    if numbers_in(text):
        return 0.0, "أرقام بس من غير مقارنة حسابية"
    return 0.0, "مفيش مثال حسابي"


def _st4_conditional(text: str) -> tuple[float, str]:
    cond = contains_any(text, ("لو ", "إذا", "بشروط", "في حالة", "مشروط", "حسب"))
    rec = contains_any(text, ("أنصح", "ننصح", "الأفضل", "ابدأ", "ما تعملش", "من الأحسن", "من الأفضل"))
    if cond and rec:
        return 2.0, "توصية مشروطة"
    if rec:
        return 1.0, "توصية موجودة بس مش مشروطة"
    return 0.0, "مفيش توصية واضحة"


def _st4_realistic(text: str) -> tuple[float, str]:
    if contains_any(text, ("مضمون", "ضمان", "رهان", "مضمون 100")):
        return 0.0, "متحمس زيادة"
    if contains_any(text, ("مخاطر", "انتبه", "حذر", "احسب", "خص", "تأجيل", "مش دام", "راجع")):
        return 2.0, "واقعي مع حذر"
    return 1.0, "واقعي بدون تحفّظ واضح"


# --------------------------------------------------------------------------- الجدول
CHECKS_EG_ST = {
    "EG1": [_eg_dialect, _warmth, _actionable, lambda t, c: _reasonable_len(t, 12, 160), _no_diagnosis],
    "EG2": [_eg2_diff, _eg_dialect, _eg2_example, _eg2_terms, _eg2_short],
    "EG3": [_eg3_tone, _eg3_deadline, _eg_dialect, _eg3_lines, _eg3_no_threat],
    "EG4": [_eg4_humor, _eg4_not_hurtful, _eg4_smart, _eg4_short, _eg4_close],
    "EG5": [_eg5_meaning, _eg5_arabic, _no_heavy_msa, _eg5_short, _eg5_no_extra],
    "EG6": [_eg6_five_lines, _eg_dialect, _eg6_reasons, _eg6_little_english, _eg6_no_repeat],
    "ST1": [_st1_hours, _st1_priority, _st1_assumptions, _st1_reality, _st1_organized],
    "ST2": [_st2_honest, _st2_risks, _st2_reality, _st2_test, _st2_no_fake_numbers],
    "ST3": [_st3_format, _st3_defs, _st3_table, _st3_medical, _st3_precise],
    "ST4": [_st4_factors, _st4_numbers, _st4_example, _st4_conditional, _st4_realistic],
}
