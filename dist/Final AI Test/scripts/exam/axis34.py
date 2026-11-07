"""فحوص المحور ③ (شغل Mahmoud: 4×6=24) والمحور ④ (مهارات: 16)."""
from __future__ import annotations

import re

from .lib import (
    code_blocks,
    has_code,
    has_date,
    has_first_step,
    has_num,
    has_table,
    norm_digits,
    numbered_steps,
    run_python,
)

MAX3 = 6.0


def _shape_rows(t: str, notes: list[str]) -> float:
    """أول خطوة + موعد (1.0)."""
    if has_first_step(t) and has_date(t):
        return 1.0
    notes.append("مفيش أول خطوة + موعد")
    return 0.0


def d1(t: str, info: dict):
    s, notes = 0.0, []
    if has_num(t, 576):
        s += 1.0
    else:
        notes.append("مفيش 576 (18% من 3200)")

    if has_table(t):
        s += 1.0
    else:
        notes.append("مفيش جدول")

    if has_num(t, 2624):
        s += 1.0
    elif has_num(t, 2224):
        s -= 1.0
        notes.append("رقم السليم غلط (2224 بدل 2624)")
    else:
        s += 0.5
        notes.append("رقم السليم مش ظاهر")

    steps = numbered_steps(t)
    if steps >= 3:
        s += 1.0
    elif steps >= 1:
        s += 0.5
        notes.append("إجراءات أقل من 3")
    else:
        notes.append("مفيش إجراءات")

    s += _shape_rows(t, notes)

    slips = len(
        re.findall(
            r"نظركه|بتتحمل|بيحمل|شريك\s+عملك|أنت\s+شغال\s+بذكاء|"
            r"أنت\s+مش\s+\"مشتري\"",
            t,
        )
    )
    if slips:
        s -= 0.5 * slips
        notes.append("ضمير الغريب ×%d" % slips)
    else:
        s += 1.0

    if info.get("msa_hits", 0) >= 3:
        s -= 0.5
        notes.append("فصحى تقيلة")
    return dict(score=round(max(0.0, s), 2), max=MAX3, notes=notes)


def d2(t: str, info: dict):
    s, notes = 0.0, []
    if re.search(
        r"(?:21\s*%)\s*من\s*24|24\s*(?:منها|موظف).{0,12}5|"
        r"(?:5|خمس|خمسة)\s*(?:موظف|موظفين)",
        t,
    ):
        s += 1.0
    else:
        notes.append("مفيش حساب 21% من 24 (≈5)")

    if re.search(r"8\s*(?:موظف|موظفين|لكل\s+وردية)|24\s*(?:على|÷|/)\s*3", t):
        s += 1.0
    else:
        notes.append("مفيش 8 لكل وردية")

    if numbered_steps(t) >= 3 or has_table(t):
        s += 1.0
    elif numbered_steps(t) >= 1:
        s += 0.5
        notes.append("إجراءات أقل من 3")
    else:
        notes.append("مفيش إجراءات")

    if re.search(r"مؤشر|نسبة\s+البوظ|إنتاجية|تتبع|متابعة|قياس\s+قبل", t):
        s += 1.0
    else:
        notes.append("مفيش مؤشر متابعة")

    s += _shape_rows(t, notes)

    invented = re.findall(
        r"(?:الفلوس\s+ناقصة|نقص\s+الفلوس|مش\s+مرتبين|زعلان|" r"مش\s+محترمين)", t
    )
    if invented:
        s -= 0.5 * len(invented)
        notes.append("افتراض بلا أساس: %s" % list(invented[:2]))
    else:
        s += 1.0

    if info.get("msa_hits", 0) >= 3:
        s -= 0.5
        notes.append("فصحى تقيلة")
    return dict(score=round(max(0.0, s), 2), max=MAX3, notes=notes)


def d3(t: str, info: dict):
    s, notes = 0.0, []
    n = norm_digits(t)
    if re.search(r"150[,\.]?000|١٥٠\s*ألف|150\s*ألف", n):
        s += 1.5
    elif re.search(r"(?:1[،,\.]35|1\.35)\s*(?:مليون|م)", n) and re.search(
        r"(?:1[،,\.]2|1\.2)\s*(?:مليون|م)", n
    ):
        s += 0.75
        notes.append("ذكر inflow/outflow من غير فجوة 150 ألف")
    else:
        notes.append("مفيش فجوة 150 ألف")

    if re.search(r"400\s*(?:ألف|الف)", n) and re.search(
        r"مستحق|تحصيل|دورة|سيولة|أجل", t
    ):
        s += 1.0
    else:
        notes.append("مفيش فصل المستحقات 400 ألف")

    prio = len(
        re.findall(r"تحصيل|مؤجّل|تأجيل|تمويل|تقليل\s+صرف|تأخّر|تقسيط|خط\s+سحب", t)
    )
    if prio >= 2:
        s += 1.0
    elif prio == 1:
        s += 0.5
        notes.append("أولويات قليلة")
    else:
        notes.append("مفيش ترتيب أولويات")

    if re.search(
        r"غير\s+مؤكد|مضمون|مضمونة|100\s*%|نقدها|تحصل\s+منها|متأكد\s+منها", t
    ):
        s += 0.5
    else:
        notes.append("مفيش تحذير من المستحقات غير المؤكدة")

    s += _shape_rows(t, notes)

    over = re.findall(
        r"(?:هنتعادل|رح\s+نتعادل|خلال\s+(?:يوم|أسبوع|شهر)\s*(?:هن|رح)?\s*"
        r"(?:نحل|نعادل|تتعادل))",
        t,
    )
    if over:
        s -= 0.5 * len(over)
        notes.append("مبالغة: %s" % list(over[:2]))
    else:
        s += 1.0

    if info.get("msa_hits", 0) >= 3:
        s -= 0.5
        notes.append("فصحى تقيلة")
    return dict(score=round(max(0.0, s), 2), max=MAX3, notes=notes)


def d4(t: str, info: dict):
    s, notes = 0.0, []
    named = set(
        re.findall(
            r"(?:المبيعات|الإيراد|Revenue|هامش\s*الربح|Margin|"
            r"التحويل|Conversion|رجوع|Repeat|CAC|LTV|العملاء|متوسط\s+السلة|"
            r"متوسط\s+قيمة\s+الطلب)",
            t,
            re.I,
        )
    )
    if len(named) >= 5:
        s += 1.0
    elif len(named) >= 4:
        s += 0.5
        notes.append("أقل من 5 مؤشرات (%d)" % len(named))
    else:
        notes.append("مؤشرات قليلة (%d)" % len(named))

    formulas = 0
    for pat in (
        r"=\s*[^\n]{0,40}[÷/]\s*[^\n]{0,30}",
        r"=\s*\w+\s*[-×*]\s*\w+",
        r"\(\s*[^\n)]{0,30}\)\s*÷",
        r"×\s*100",
    ):
        formulas += len(re.findall(pat, t))
    if formulas >= 2:
        s += 1.5
    elif formulas == 1:
        s += 0.75
        notes.append("صيغ قليلة")
    else:
        notes.append("مفيش صيغ حساب")

    need = ["المبيعات", "هامش", "التحويل", "رجوع"]
    need_any = {"رجوع": ("رجوع", "عودات", "العودة", "Return")}
    hit = 0
    for w in need:
        alts = need_any.get(w, (w,))
        if any(a in t for a in alts):
            hit += 1
    if hit >= 4:
        s += 1.0
    else:
        s += 0.5 * hit
        notes.append("مؤشرات السؤال ناقصة (%d/4)" % hit)

    if re.search(
        r"CAC|LTV|متوسط\s+قيمة\s+الطلب|متوسط\s+السلة|تكلفة\s+الاكتساب|"
        r"قيمة\s+العميل",
        t,
        re.I,
    ):
        s += 0.5
    else:
        notes.append("المؤشر الخامس مش واضح")

    if has_table(t) or has_code(t):
        s += 1.0
    else:
        s += 0.5
        notes.append("مفيش جدول عرض")

    if has_first_step(t) and has_date(t):
        s += 1.0
    else:
        notes.append("مفيش أول خطوة + موعد")

    if info.get("msa_hits", 0) >= 3:
        s -= 0.5
        notes.append("فصحى تقيلة")
    return dict(score=round(max(0.0, s), 2), max=MAX3, notes=notes)


# ─────────────────────────────── المحور ④
def e1(t: str, info: dict):
    s, notes = 0.0, []
    ideas = len(re.findall(r"^\s*(?:[1-٩1-9][\.\)]|[-•*])\s+", t, re.M))
    if ideas >= 4:
        s += 1.0
    elif ideas >= 2:
        s += 0.5
        notes.append("أفكار أقل من 4 (%d)" % ideas)
    else:
        notes.append("مفيش أفكار مرقمة")

    if re.search(r"تطبيق|موبايل|فوتون|أندرويد|آيفون|تطبيق\s+موبايل|تطبيق الجوال", t):
        s += 0.75
    else:
        s -= 0.5
        notes.append("الأفكار مش مربوطة بتطبيق موبايل")

    if has_table(t) or numbered_steps(t) >= 3:
        s += 0.5
    else:
        notes.append("مفيش جدول ولا خطوات")

    if re.search(
        r"معايير|أو\s+معنى|نختار|اختار|أفضل\s+فكرة|إيه\s+الأنسب|"
        r"priorit|اختيار|يعتمد|رتّب",
        t,
        re.I,
    ):
        s += 0.5
    else:
        notes.append("مفيش معيار اختيار")

    if has_first_step(t) and has_date(t):
        s += 0.5
    else:
        notes.append("مفيش أول خطوة + موعد")

    if info.get("msa_hits", 0) == 0:
        s += 0.25
    else:
        notes.append("فصحى مسرّبة (%d)" % info["msa_hits"])
    return dict(score=round(max(0.0, s), 2), max=3.5, notes=notes)


def e2(t: str, info: dict):
    """كود Python — بيتشغّل فعلاً (G7)."""
    s, notes = 0.0, []
    blocks = [b for b in code_blocks(t) if "def " in b] or code_blocks(t)
    if not blocks:
        notes.append("مفيش كود")
        return dict(score=0.0, max=3.5, notes=notes, gates=dict(g7=True))
    code = max(blocks, key=len)
    s += 1.0

    fn = re.search(r"def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)", code)
    harness = """
_fn = globals().get(%r)
_out = None
_err = None
for _args in ((100.0, 60.0), (150.0, 100.0), (200.0, 100.0)):
    try:
        _out = _fn(*_args)
        break
    except TypeError:
        try:
            _out = _fn(_args[0], _args[1])
            break
        except Exception as _e:
            _err = _e
    except Exception as _e:
        _err = _e
        break
if _err is not None:
    print('ERROR', type(_err).__name__, str(_err)[:200])
print('RESULT', repr(_out))
""" % (fn.group(1) if fn else "")
    ok, out, err = run_python(code, harness)
    if "ERROR" in out:
        err_line = [ln for ln in out.splitlines() if ln.startswith("ERROR")][0]
        notes.append("الكود رماه error: %s" % err_line[:120])
        return dict(score=round(s, 2), max=3.5, notes=notes, gates=dict(g7=True))
    if ok and "RESULT" in out:
        s += 1.0
        val = out.split("RESULT", 1)[1].strip()
        try:
            v = eval(val, {"__builtins__": {}}, {})  # noqa: S307
        except Exception:
            v = None
        if isinstance(v, (int, float)):
            if abs(v - 40.0) < 1e-6 or abs(v - 0.4) < 1e-6:
                s += 1.0
            else:
                s += 0.5
                notes.append("النتيجة مش 40%% (طلعت %s)" % v)
        else:
            s += 0.5
            notes.append("مفيش رقم مرجعي (%s)" % val[:40])
    else:
        notes.append("الكود ما اشتغلش: %s" % (err or "error")[-120:].replace("\n", " "))
        return dict(score=round(s, 2), max=3.5, notes=notes, gates=dict(g7=True))

    if re.search(r'docstring|"""|\'\'\'', code) or re.search(r"مثال|example|شرح", t):
        s += 0.5
    else:
        notes.append("مفيش شرح أو docstring")
    return dict(score=round(max(0.0, s), 2), max=3.5, notes=notes, gates=dict(g7=False))


def f1(t: str, info: dict):
    s, notes = 0.0, []
    sql = " ".join(code_blocks(t, "sql")) or t
    if re.search(r"\bSELECT\b", sql, re.I):
        s += 0.5
    else:
        notes.append("مفيش SELECT")
    if re.search(r"\bFROM\b", sql, re.I):
        s += 0.5
    else:
        notes.append("مفيش FROM")
    if re.search(r"\bJOIN\b", sql, re.I):
        s += 0.5
    else:
        notes.append("مفيش JOIN")

    if re.search(r"orders", sql, re.I) and re.search(r"products?", sql, re.I):
        s += 0.5
    else:
        notes.append("مش رابط orders و products")

    if re.search(
        r"ORDER\s+BY[^;\n]*(?:total|quantity|qty|amount|price|sum)[^;\n]*DESC",
        sql,
        re.I,
    ):
        s += 0.75
    elif re.search(r"ORDER\s+BY[^;\n]*DESC", sql, re.I):
        s += 0.5
        notes.append("ORDER BY مش على قيمة المبيعات")
    else:
        notes.append("مفيش ORDER BY ... DESC")

    if re.search(r"LIMIT\s+10\b", sql, re.I):
        s += 0.5
    else:
        notes.append("مفيش LIMIT 10")

    if re.search(r"SUM\s*\(|COUNT\s*\(|GROUP\s+BY", sql, re.I) or "المبيعات" in t:
        s += 0.25
    else:
        notes.append("مفيش شرح ولا حساب إجمالي")
    return dict(score=round(max(0.0, s), 2), max=3.0, notes=notes)


def f2(t: str, info: dict):
    s, notes = 0.0, []
    if re.search(r"pivot\s*table|pivot|جدول\s+محوري|الجدول\s+المحوري", t, re.I):
        s += 0.75
    else:
        notes.append("مفيش PivotTable")

    rows_ok = re.search(
        r"(?:rows|rows\s*=|صفوف|الصفوف).{0,30}(?:product|منتج|المنتج|item)", t, re.I
    )
    cols_ok = re.search(
        r"(?:columns|cols|أعمدة|الأعمدة).{0,30}(?:month|شهر|الشهر|monthly)", t, re.I
    )
    if rows_ok and cols_ok:
        s += 0.75
    elif rows_ok or cols_ok:
        s += 0.375
        notes.append("Rows/Columns ناقص واحد")
    else:
        notes.append("مفيش تحديد Rows/Columns")

    if re.search(r"values|القيمة|القيم|مجموع\s+المبيعات|sum\s+of\s+sales", t, re.I):
        s += 0.5
    else:
        notes.append("مفيش تحديد القيمة")

    if re.search(r"insert|إدراج|بيانات\s+المصدر|source\s+data|تحديث|refresh", t, re.I):
        s += 0.5
    else:
        notes.append("مفيش خطوات تنفيذ")

    if re.search(r"قرار|تحليل|أعرف|هعرف|تشوف|نقارن|مقارنة|شغلك|بوظ|ورديات", t):
        s += 0.5
    else:
        notes.append("مفيش ربط بواقع Mahmoud")
    return dict(score=round(max(0.0, s), 2), max=3.0, notes=notes)


def f3(t: str, info: dict):
    s, notes = 0.0, []
    blocks = code_blocks(t)
    if not blocks:
        notes.append("مفيش كود")
        return dict(score=0.0, max=3.0, notes=notes)
    code = max(blocks, key=len)
    fn = re.search(r"def\s+([A-Za-z_][A-Za-z0-9_]*)", code)
    if fn:
        s += 0.5
    else:
        notes.append("مفيش def")

    forms = 0
    if re.search(r"0?1\d{9}", code) or re.search(r"r['\"]?\(?0?1", code, re.I):
        forms += 1
    if re.search(r"\+?20", code):
        forms += 1
    if re.search(r"0020|0{2}20", code, re.I):
        forms += 1
    if re.search(r"re\.(?:sub|match|fullmatch|search)|replace\(|strip\(|lstrip\(", code):
        forms += 1
    if forms >= 3:
        s += 1.0
    elif forms >= 2:
        s += 0.5
        notes.append("أشكال الأرقام مش مغطّاة كلها")
    else:
        notes.append("أشكال الأرقام ناقصة")

    if re.search(r"\+20", code):
        s += 0.75
    else:
        notes.append("مش بيرجّع +20")

    harness = """
_f = globals().get(%r)
if _f is None:
    raise SystemExit(2)
for _inp in ('01012345678', '01234567878', '+201012345678', '00201012345678'):
    try:
        _v = _f(_inp)
    except Exception as _e:
        print('ERR', _inp, type(_e).__name__)
        continue
    print('RES', _inp, repr(_v))
""" % (fn.group(1) if fn else "")
    ok, out, err = run_python(code, harness)
    if ok and out.count("RES") >= 2:
        vals = [ln.split(None, 2)[2] for ln in out.splitlines() if ln.startswith("RES")]
        okv = sum(1 for v in vals if "+20" in v)
        if okv >= len(vals) and okv >= 2:
            s += 0.5
        else:
            s += 0.25
            notes.append("مش كل الأرقام رجعت +20")
    else:
        notes.append("الكود ما اشتغلش: %s" % (err or "error")[-100:].replace("\n", " "))

    if re.search(r"raise|ValueError|return\s+None|if\s+not\s+.*return", code):
        s += 0.25
    else:
        notes.append("مفيش validation")
    return dict(score=round(max(0.0, s), 2), max=3.0, notes=notes)


CHECKS3 = {"D1": d1, "D2": d2, "D3": d3, "D4": d4}
CHECKS4 = {"E1": e1, "E2": e2, "F1": f1, "F2": f2, "F3": f3}
