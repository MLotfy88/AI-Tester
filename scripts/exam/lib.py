"""أدوات مساعدة للمصحّح: نص، لغة، أرقام، بنية الرد، وتشغيل كود آمن.

منقولة من qwen35-egyptian-assistant/tools/exam_lib.py مع إزالة الاعتماد
على مسارات المشروع الأصلية، وإضافة كشف اللهجات الشامية/الليبية.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

# ─────────────────────────── الأرقام
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# التشكيل والتطويل — بيتجاهَل في عدّ علامات اللغة (الكلمة واحدة مهما اتشكت)
TASHKEEL = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640]")


def strip_tashkeel(t: str) -> str:
    """يشيل التشكيل والتطويل — «زوّد» تبقى «زود»."""
    return TASHKEEL.sub("", t or "")


def norm_digits(t: str) -> str:
    t = t.translate(_AR_DIGITS)
    t = re.sub(r"(?<=\d)[,\u066c\u060c](?=\d)", "", t)
    return t


def has_num(t: str, *nums) -> bool:
    n = norm_digits(t)
    for x in nums:
        s = str(x).replace(",", "")
        if re.search(r"(?<!\d)%s(?!\d)" % re.escape(s), n):
            return True
    return False


def all_numbers(t: str) -> list[int]:
    n = norm_digits(t)
    out = []
    for x in re.findall(r"\d[\d,\.]*", n):
        x = x.replace(",", "").rstrip(".")
        try:
            out.append(int(float(x)))
        except ValueError:
            continue
    return out


# ─────────────────────────── بنية الرد
def code_blocks(t: str, lang: str = "") -> list[str]:
    out = []
    for m in re.finditer(r"```([A-Za-z0-9_+-]*)\n(.*?)```", t, re.S):
        if lang and m.group(1).lower() != lang.lower():
            continue
        out.append(m.group(2))
    return out


def has_code(t: str) -> bool:
    return bool(code_blocks(t)) or bool(re.search(r"^\s{4}\S.*\n.*=", t, re.M))


def has_table(t: str) -> bool:
    if re.search(r"^\s*\|.*\|\s*$", t, re.M) and re.search(
        r"^\s*\|[\s\-:|]+\|\s*$", t, re.M
    ):
        return True
    return bool(re.search(r"جدول", t))


def strip_code(t: str) -> str:
    return re.sub(r"```.*?```", " ", t, flags=re.S)


def numbered_steps(t: str) -> int:
    t = strip_code(t)
    n = len(
        re.findall(
            r"(?:^|[\n:؛،])\s*(?:\d{1,2}[\.\)]|أولًا|أولاً|أول|ثانيًا|ثانيا|ثاني|"
            r"ثالثًا|ثالثا|ثالث|رابع|خامس)\s*[:.\-]",
            t,
            re.M,
        )
    )
    if n == 0:
        n = len(
            re.findall(
                r"(?:^|\n)\s*(?:#{1,6}\s*|\*\*)?\s*(?:الخطوة|خطوت)\s*[:.]?\s*\d", t
            )
        )
    if n == 0:
        n = len(re.findall(r"(?:^|[\s:؛،])(?:[1-9]|1[0-2])[\.\)]\s+\S", t))
    return n


DATE_WORDS = (
    "النهاردة",
    "النهارده",
    "اليوم",
    "بكرة",
    "خلال",
    "موعد",
    "تاريخ",
    "الأحد",
    "الإثنين",
    "الثلاثاء",
    "الأربعاء",
    "الخميس",
    "الجمعة",
    "السبت",
    "week",
    "day",
    "يوم",
    "أيام",
    "أسبوع",
    "أسابيع",
    "شهر",
    "ساعة",
)


def has_date(t: str) -> bool:
    if re.search(
        r"\d+\s*(?:يوم|أيام|أسبوع|أسابيع|شهر|ساعة|weeks?|days?)",
        norm_digits(t),
        re.I,
    ):
        return True
    return any(w in t for w in DATE_WORDS)


def has_first_step(t: str) -> bool:
    return bool(
        re.search(
            r"(أول\s*خطوة|الخطوة\s*الأولى|أول\s*إجراء|أبدا\s*بـ|ابدأ\s*بـ|ابدأ|نبدأ|"
            r"الأولوية|First\s*Step|خُطّة\s*الأولى|أول\s*مهمة|ابدأي|نبدا)",
            t,
            re.I,
        )
    )


def first_step_with_date(t: str) -> bool:
    return has_first_step(t) and has_date(t)


# ─────────────────────────── اللغة
AR = re.compile(r"[\u0600-\u06ff]")
LAT = re.compile(r"[A-Za-z]")
MSA = re.compile(
    r"\b(إليك|حيث|يجب عليك|إجراء|طريقة|يُعد|يمكن|سيتم|الإرشادات|نصائح|أولًا|ثانيًا|"
    r"أخيرًا|علاوة على|بشكل عام|من خلال|الخلاصة|التفاصيل والأسباب|الهدف|السبب|"
    r"الإجراء|الخطوة|الخيار|بما إنك|بالتالي|قيمة|إذاً|لذلك|"
    r"المحاور|الاستراتيجية|الخطوط\s+الحمراء|الاحتياطي\s+الصارم|الإنفاق\s+الاستراتيجي|"
    r"المبدأ|المرتكزات|الأسس|المنهج)\b"
)
EG = re.compile(
    r"\b(إزيك|إزاي|إيه|فين|ليه|عايز|عاوز|كده|دلوقتي|بص|تمام|أهو|هنعمل|ينفع|"
    r"عشان|بسبب|بجد|قوي|عادي|بكام|جربت|ممكن|محتاج|فاهم|ماشي|بقي|نعمل|نشوف|"
    r"نتكلم|جميل|شغال|امبارح|النهارده|النهاردة|ناخد|نجيب|هنشوف|بpopulate|بنتكلم|"
    r"تعال|يلا|يلا بينا|يلا نعمل|هيشتغل|هنعملها|أنا عايز|أنا فاهم|شغل كويس|"
    r"عشان كده|بجد كده|تمام كده|خلي بالك|ماشي نعمل|نبدأ نعمل)\b"
)

OTHER_DIALECT = re.compile(
    r"ديالنا|كيفاش|\bبش\b|شوية بزاف|\bبزاف\b|بالزاف|إهنا|دروك|واش|بنتعلمو|نتمنى|يا ريت|"
    r"كيما راك|\bدابا\b|بحال|\bهلق\b|\bهلأ\b|\bمنيح\b|\bشو\b|"
    r"\bلسا\b|عم\s+بت|ما\s+في\s+حد|مش\s+هيك|بصح|يا\s+زين|شنو|كي\s+داير|"
    r"ما\s+نحبش",
    re.I,
)
BROKEN_AR = re.compile(
    r"بيقايي|نو منو|عزائلك|بpopulate|بنتكلم بي|في في|هو هو|الي الي|كي اعملين|"
    r"هبقاوم|ماكس|بِنِي"
)

# حروف من لغات غريبة (صيني · ياباني · روسي · fullwidth) — معيار «مفيش حروف غريبة»
# في معايير الـ rubric (v3).
FOREIGN_SCRIPT = re.compile(
    r"[\u3000-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
    r"\u0400-\u04ff\u0500-\u052f\uff01-\uff60\uffe0-\uffe6]"
)

# علامات عامية مصرية إضافية
EG_EXTRA = re.compile(
    r"\b(?:إزيك|إزاي|إيه|فين|ليه|عايز|عاوز|كده|دلوقتي|بص|تمام|أهو|هنعمل|ينفع|"
    r"عشان|علشان|بسبب|بجد|بكام|جربت|جرب|ممكن|محتاج|فاهم|ماشي|بقي|نعمل|نشوف|نتكلم|"
    r"جميل|شغال|امبارح|النهاردة|النهارده|خلاص|خلينا|يلا|تعال|خلي|ابدأ|ابدئي|نبدأ|"
    r"معاها|بتاع|بتاعك|خالص|شوية|شوي|علطول|ياريت|تاني|بكرة|يعني|يبقى|عندك|عندنا|"
    r"نقدر|هعمل|هنعمله|بنعمل|طبعا|أكيد|صحيح|زي|قاعد|واقع|فعلا|أهو|حلو|كويس|"
    r"مش قادر|قادر|كتير|خايف|زمان|الجنة|نتأكد|نتناقش|بنتأكد|بشوف|بجيب|مبحبش|"
    r"مش عارف|معروفش|ما أعرفش|ليش|فين|إزاي|kam،|مرات|بصي|بصراحة|علي العموم|"
    r"ما ينفعش|مينفعش|هينفع|ينفع|بتوع|بتوعنا|ours|بقي|كله|بس)\b",
    re.I,
)


def dialect_stats(text: str) -> dict:
    norm = strip_tashkeel(text)
    ar = len(AR.findall(text))
    lat = len(LAT.findall(text))
    words = len(re.findall(r"[\w\u0600-\u06ff]+", text))
    msa = len(MSA.findall(norm))
    eg = len(EG.findall(norm))
    return {
        "ar_chars": ar,
        "lat_chars": lat,
        "ar_ratio": round(ar / max(1, ar + lat), 3),
        "words": words,
        "msa_hits": msa,
        "eg_hits": eg,
        "eg_per_1k": round(1000 * eg / max(1, words), 1),
        "msa_per_1k": round(1000 * msa / max(1, words), 1),
        "has_think": bool(re.search(r"<think>|</think>", text, re.I)),
    }


def lang_info(text: str) -> dict:
    norm = strip_tashkeel(text)
    st = dialect_stats(text)
    st["other_hits"] = len(OTHER_DIALECT.findall(norm))
    st["broken_hits"] = len(BROKEN_AR.findall(norm))
    st["foreign_hits"] = len(FOREIGN_SCRIPT.findall(text))
    st["chars"] = len(text)
    st["words"] = st.get("words") or 0
    st["eg_hits"] = len(EG_EXTRA.findall(norm))
    st["eg_per_1k"] = round(1000 * st["eg_hits"] / max(1, st["words"]), 1)
    return st


def score_d1(info: dict) -> float:
    """D1 — كثافة العامية: ≥ 8 علامات/1000 كلمة (ورقة الامتحان §المحور ①)."""
    eg = info.get("eg_per_1k", 0)
    if eg >= 8:
        return 0.25
    if eg >= 4:
        return 0.125
    return 0.0


def score_d2(info: dict) -> float:
    """D2 — انعدام الفصحى: ≤ 6 علامات فصحى/1000 كلمة (ورقة الامتحان §المحور ①).

    الكثافة بالكلمة مش بالعدد المجرد — لأن الردود الطويلة فيها فصحى أقل كثافة.
    """
    density = info.get("msa_per_1k", 0)
    if density <= 6:
        return 0.25
    if density <= 10:
        return 0.15
    return 0.0


def score_d3(info: dict) -> float:
    if info.get("other_hits"):
        return 0.0
    if info.get("broken_hits"):
        return 0.15
    return 0.25


def score_d4(t: str) -> float:
    return 0.25 if len(t.strip()) >= 40 else 0.0


# ─────────────────────────── تشغيل الكود (منفصل ومؤمّن)
UNSAFE = re.compile(
    r"(?:\bos\s*\.\s*system|\bsubprocess\b|\bshutil\s*\.\s*rmtree|\bsocket\b|\brequests\b|"
    r"\burllib\b|\bhttpx\b|\bpickle\b|__import__|\beval\s*\(|\bexec\s*\(|"
    r"\bopen\s*\([^)]*['\"][wax]|\bos\s*\.\s*remove\s*\(|\bPath\s*\.\s*remove\s*\(|"
    r"\brmdir\b|\bunlink\s*\(|\bchmod\b|shutil\.move)",
    re.I,
)


def is_safe_code(code: str) -> bool:
    return not bool(UNSAFE.search(code))


def run_python(code: str, test_body: str, timeout: int = 25):
    """يشغّل كود الموديل في مجلد مؤقت. يرجع (ok, stdout, stderr)."""
    if not is_safe_code(code):
        return False, "", "SKIPPED_UNSAFE"
    with tempfile.TemporaryDirectory(prefix="exam_gr_") as td:
        f = Path(td) / "snippet.py"
        f.write_text(code + "\n\n" + test_body, encoding="utf-8")
        try:
            p = subprocess.run(
                [sys.executable, "-I", str(f)],
                cwd=td,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return False, "", "TIMEOUT"
        except Exception as exc:  # pragma: no cover
            return False, "", type(exc).__name__
        return p.returncode == 0, (p.stdout or "")[-4000:], (p.stderr or "")[-2000:]
