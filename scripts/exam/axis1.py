"""فحوص المحور ① — اللهجة والأسلوب (8 أسئلة × 4 نقاط = 32)."""
from __future__ import annotations

import re

from .lib import (
    BROKEN_AR,
    has_code,
    has_date,
    has_first_step,
    has_num,
    has_table,
    numbered_steps,
    norm_digits,
    score_d1,
    score_d2,
    score_d3,
)

MAX = 4.0


def _lang(t: str, info: dict) -> tuple[float, list[str]]:
    """D1/D2/D3/D4 = 1.0 نقطة بالمجموع."""
    notes: list[str] = []
    d1 = score_d1(info)
    d2 = score_d2(info)
    d3 = score_d3(info)
    d4 = 0.25 if len(t.strip()) >= 40 else 0.0
    if d1 < 0.25:
        notes.append("D1: كثافة عامية ضعيفة (%s/1000)" % info.get("eg_per_1k"))
    if d2 < 0.25:
        notes.append("D2: فصحى مسرّبة (%s/1000)" % info.get("msa_per_1k"))
    if d3 < 0.25:
        notes.append("D3: %s" % ("لهجة تانية" if info.get("other_hits") else "عربي مكسور"))
    if d4 == 0:
        notes.append("D4: الرد قصير جداً")
    return d1 + d2 + d3 + d4, notes


def a1(t: str, info: dict):
    s, notes = 0.0, []
    eg_hits = len(
        re.findall(
            r"\b(?:إزيك|إيه|كده|دلوقتي|قاعد|عامل|أهو|تمام|ماشي|النهاردة|إزاي)\b", t
        )
    )
    if eg_hits >= 3:
        s += 1.0
    elif eg_hits == 2:
        s += 0.5
        notes.append("علامات عامية قليلة (%d)" % eg_hits)
    else:
        notes.append("مفيش علامات عامية صريحة")

    msa = info.get("msa_hits", 0)
    if msa == 0:
        s += 1.0
    else:
        s += max(0.0, 1.0 - 0.5 * (msa // 3))
        notes.append("فصحى مسرّبة (%d)" % msa)

    defects = info.get("other_hits", 0) + info.get("broken_hits", 0)
    if defects == 0:
        s += 1.0
    else:
        s += max(0.0, 1.0 - 0.5 * defects)
        notes.append("عيب لغة ×%d" % defects)

    if re.search(
        r"إزيك|سلام|عامل إيه|أهو|تمام|مرحبا|أهلاً|أهلا|وعليكم|صباح|مساء|"
        r"يا محمود|جاهز|طيب|ماشي|النهاردة قاعد|قاعد على",
        t,
    ):
        s += 1.0
    else:
        notes.append("ما ردّش على سؤال الترحيب")

    # عقوبة الطول (>1200 حرف) تُطبّق مركزياً في grader.py لكل الأسئلة.
    return dict(score=round(max(0.0, s), 2), max=MAX, notes=notes)


def a2(t: str, info: dict):
    s, notes = 0.0, []
    head = t[:600]
    if re.search(r"الخلاصة|باختصار|مختصر|أولاً|أولا|الخلاصة في|الحاجة في سطر", head):
        s += 0.75
    else:
        notes.append("مفيش خلاصة في الأول")

    if has_table(t):
        s += 0.75
    elif numbered_steps(t) >= 4:
        s += 0.75
    elif numbered_steps(t) >= 1:
        s += 0.5
        notes.append("خطوات أقل من 4")
    else:
        notes.append("مفيش جدول ولا خطوات")

    if has_first_step(t) and has_date(t):
        s += 0.75
    elif has_first_step(t):
        s += 0.4
        notes.append("أول خطوة من غير موعد")
    else:
        notes.append("مفيش أول خطوة + موعد")

    if re.search(r"مهندس|مبرمج", t):
        notes.append("قال إنه مهندس/مبرمج")
    else:
        s += 0.5

    if "KDP" in t:
        notes.append("ذكر KDP في سياق تصوير")
    else:
        s += 0.25

    ls, ln = _lang(t, info)
    return dict(score=round(max(0.0, s + ls), 2), max=MAX, notes=notes + ln)


def a3(t: str, info: dict):
    s, notes = 0.0, []
    quoted = len(re.findall(r"^\s*>", t, re.M))
    quoted_text = " ".join(re.findall(r"^\s*>\s*(.+)$", t, re.M))
    long_lines = len([ln for ln in t.splitlines() if len(ln.strip()) > 25])
    if (quoted >= 1 and len(quoted_text.strip()) > 60) or (
        long_lines >= 3 and "رسالة" in t
    ):
        s += 0.75
    elif "رسالة" in t or quoted >= 1:
        s += 0.4
        notes.append("مفيش نص رسالة جاهز")
    else:
        notes.append("مفيش نص رسالة")

    hard = re.search(r"قوي|صارم|حازم|بكل وضوح|مش هقبل|لازم|بنتكلم|جد", t)
    soft = re.search(r"محترم|احترام|مهذب|بكل أدب|ممكن|لو سمحت|أرسل|رسالتك", t)
    if hard and soft:
        s += 0.75
    elif hard or soft:
        s += 0.375
        notes.append("النبرة ناقصة طرف")
    else:
        notes.append("مفيش تصنيف نبرة")

    bad = len(re.findall(r"نظركه|بتتحمل|بيحمل|شريك عملك|أنت شغال بذكاء", t))
    if bad:
        s -= 0.5 * bad
        notes.append("كلام عن Mahmoud بضمير الغريب ×%d" % bad)
    else:
        s += 0.75

    if has_date(t) and re.search(r"خلال|رد|مهلة|موعد|أيام|أسبوع", t):
        s += 0.5
    else:
        notes.append("مفيش مهلة أو خطوة تالية")

    invented = re.findall(r"(?:السيد|الستاذ|أ\.\s*)\s*[ء-ي]{3,}\s+[ء-ي]{3,}", t)
    if invented:
        s -= 0.25
        notes.append("اسم مخترع: %s" % invented[0])
    else:
        s += 0.25

    ls, ln = _lang(t, info)
    return dict(score=round(max(0.0, s + ls), 2), max=MAX, notes=notes + ln)


def a4(t: str, info: dict):
    s, notes = 0.0, []
    if "429" in t and re.search(r"too many requests|طلبات كثيرة|طلبات كتير", t, re.I):
        s += 0.75
    elif "429" in t:
        s += 0.4
        notes.append("ذكر 429 من غير الاسم")
    else:
        notes.append("مفيش 429")

    if re.search(r"retry-after|exponential backoff|backoff|rate limit|throttl", t, re.I):
        s += 0.75
    elif re.search(r"حاول تاني|التأخير|تقليل الطلبات|انتظر", t):
        s += 0.4
        notes.append("الحل عام")
    else:
        notes.append("مفيش حل عملي")

    terms = len(
        re.findall(r"retry-after|rate limit|backoff|429|api|header|timeout|throttl", t, re.I)
    )
    if terms >= 3:
        s += 0.75
    elif terms >= 2:
        s += 0.5
    else:
        s += 0.25
        notes.append("مصطلحات تقنية قليلة")

    if has_code(t) or "مثال" in t:
        s += 0.5
    else:
        notes.append("مفيش مثال ولا كود")

    broken = len(BROKEN_AR.findall(t))
    if broken:
        s -= 0.25 * broken
        notes.append("تركيب مكسور ×%d" % broken)
    else:
        s += 0.25

    ls, ln = _lang(t, info)
    return dict(score=round(max(0.0, s + ls), 2), max=MAX, notes=notes + ln)


def b1(t: str, info: dict):
    s, notes = 0.0, []
    if re.search(r"COGS", t) and re.search(
        r"تكلفة البضاعة المباعة|تكلفة المبيعات|بضاعة مباعة|"
        r"تكلفة السلعة المباعة|ما اشتريناه|ثمن البضاعة",
        t,
    ):
        s += 0.75
    elif "COGS" in t:
        s += 0.4
        notes.append("تعريف COGS غامض")
    else:
        notes.append("مفيش تعريف COGS")

    nums = [x for x in re.findall(r"\d+(?:\.\d+)?", norm_digits(t))]
    if len(nums) >= 2 and re.search(r"[=+×*]|جمع|مجموع|يجمع|\+", t):
        s += 0.75
    elif nums:
        s += 0.4
        notes.append("مفيش حساب بأرقام")
    else:
        notes.append("مفيش أرقام")

    if numbered_steps(t) >= 3 or has_table(t):
        s += 0.75
    else:
        notes.append("مفيش خطوات للحساب")

    if (
        "KDP" in t
        and re.search(r"متجر|electron|التجارة", t)
        and not re.search(r"KDP\s*(?:=|:)?\s*(?:متجر|electron)", t, re.I)
    ):
        s -= 0.5
        notes.append("نسب KDP لمتجر إلكتروني")
    else:
        s += 0.5

    if re.search(r"متجر|electron|محل|ماركت|Amazon|KDP|شغلك|بند", t):
        s += 0.25
    else:
        notes.append("مفيش ربط بواقع Mahmoud")

    ls, ln = _lang(t, info)
    return dict(score=round(max(0.0, s + ls), 2), max=MAX, notes=notes + ln)


def b2(t: str, info: dict):
    s, notes = 0.0, []
    if numbered_steps(t) >= 4 or has_table(t):
        s += 0.75
    elif numbered_steps(t) >= 1:
        s += 0.5
        notes.append("مراحل أقل من 4")
    else:
        notes.append("مفيش خطة")

    if has_table(t) or re.search(
        r"timeline|جدول زمني|خط زمني|أسبوع \d|شهر \d|الأسبوع", t, re.I
    ):
        s += 0.75
    else:
        notes.append("مفيش جدول أو خط زمني")

    if re.search(r"\d+\s*(?:كلمة|ريال|جنيه|دولار|كتاب|إصدار|عنوان|نسخة|أسوأ|يوم)", t):
        s += 0.5
    else:
        notes.append("مفيش رقم قابل للقياس")

    if has_first_step(t) and has_date(t):
        s += 0.5
    else:
        notes.append("مفيش أول خطوة + موعد")

    msa = info.get("msa_hits", 0)
    if msa == 0:
        s += 0.5
    else:
        s += max(0.0, 0.5 - 0.25 * (msa // 3))
        notes.append("فصحى مسرّبة (%d)" % msa)

    ls, ln = _lang(t, info)
    return dict(score=round(max(0.0, s + ls), 2), max=MAX, notes=notes + ln)


def b3(t: str, info: dict):
    s, notes = 0.0, []
    eg = info.get("eg_per_1k", 0)
    if eg >= 8:
        s += 0.75
    elif eg >= 4:
        s += 0.375
        notes.append("كثافة عامية متوسطة (%s/1000)" % eg)
    else:
        notes.append("كثافة عامية ضعيفة (%s/1000)" % eg)

    density = info.get("msa_per_1k", 0)
    if density <= 6:
        s += 0.75
    else:
        s += max(0.0, 0.75 - 0.4 * (int(density - 6) // 4))
        notes.append("فصحى عالية (%s/1000)" % density)

    if info.get("other_hits"):
        s -= 0.5
        notes.append("لهجة تانية")
    else:
        s += 0.5

    if re.search(r"انت|أنت|بتاعك|شغلك|عمليات|المستودع|الورديات|بوظ", t):
        s += 1.0
    else:
        s += 0.5
        notes.append("نصيحة عامة مش مخصوصة")

    if has_table(t) or numbered_steps(t) >= 3:
        s += 1.0
    else:
        s += 0.5
        notes.append("مفيش شكل أو خطوات")
    return dict(score=round(max(0.0, s), 2), max=MAX, notes=notes)


def e3(t: str, info: dict):
    s, notes = 0.0, []
    if has_num(t, 6500):
        s += 0.75
    else:
        notes.append("مفيش 6500")

    tot_ok = False
    tbl_nums: list[int] = []
    for ln in t.splitlines():
        if not ln.strip().startswith("|"):
            continue
        if re.match(r"^\s*\|[\s\-:|]+\|\s*$", ln):
            continue
        tbl_nums += [int(x) for x in re.findall(r"\d[\d,]*", norm_digits(ln))]
    if not tbl_nums:
        tbl_nums = [int(x) for x in re.findall(r"\d+", norm_digits(t))]
    for k in range(3, 9):
        for i in range(0, max(0, len(tbl_nums) - k + 1)):
            if sum(tbl_nums[i : i + k]) == 9000:
                tot_ok = True
                break
        if tot_ok:
            break
    if tot_ok:
        s += 0.75
    elif has_num(t, 9000):
        s += 0.375
        notes.append("مجموع التوزيع مش 9000")
    else:
        notes.append("مفيش 9000")

    eg = info.get("eg_per_1k", 0)
    if eg >= 8:
        s += 0.75
    elif eg >= 4:
        s += 0.375
        notes.append("كثافة عامية متوسطة")
    else:
        notes.append("كثافة عامية ضعيفة (%s/1000)" % eg)

    msa = info.get("msa_hits", 0)
    if msa == 0:
        s += 0.25
    else:
        s += max(0.0, 0.25 - 0.25 * (msa // 3))
        notes.append("فصحى مسرّبة (%d)" % msa)

    if has_first_step(t) and has_date(t):
        s += 0.5
    else:
        notes.append("مفيش أول خطوة + موعد")

    ls, ln = _lang(t, info)
    return dict(score=round(max(0.0, s + ls), 2), max=MAX, notes=notes + ln)


CHECKS = {"A1": a1, "A2": a2, "A3": a3, "A4": a4, "B1": b1, "B2": b2, "B3": b3, "E3": e3}
