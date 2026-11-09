"""يبني مجلد «Final Exam Core» — الامتحان نفسه فقط (مش الأداة كاملة).

المحتوى (v3):
  · **ملف المواصفات** `exam/exam_questions_v2.json` — المصدر الوحيد للحقيقة
    (33 سؤال مصحّح · 14 استكشافي · 8 محاور بأوزان وحدود دنيا).
  · المصحّح الحتمي (scripts/exam/*) — كل كود التصحيح.
  · أدوات مساعدة مطلوبة للتصحيح فقط (scripts/common.py · scripts/references.py).
  · القالب الثابت (شرط صحّة الامتحان).
  · README.md (طريقة الاستخدام) + MANIFEST.md (SHA-256).

**مش** بتنسخ: الأداة (التنزيل · fit · Kaggle · التقارير · التشغيل).
"""
from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "dist" / "Final Exam Core"

# ── ملفات التوثيق الأصلية (كما هي)
# ⚠ مفيش README.md هنا — الـ README بتاع النسخة بيتولّد من README_TEXT تحت.
DOCS: list[str] = []

# ── ملفات الكود: فقط ما يلزم لتشغيل **التصحيح** على إجابات أي موديل
CODE = [
    "exam/exam_questions_v2.json",
    "exam/منهج الامتحان الجديد.md",
    "config/references.yaml",
    "templates/qwen35_egyptian_nothink.jinja",
    "scripts/common.py",
    "scripts/references.py",
    "scripts/verify_manifest.py",
    "scripts/exam/__init__.py",
    "scripts/exam/lib.py",
    "scripts/exam/spec.py",
    "scripts/exam/grader.py",
    "scripts/exam/rubric_engine.py",
    "scripts/exam/rubric_lib.py",
    "scripts/exam/checks_eg_st.py",
    "scripts/exam/checks_lg_hn.py",
    "scripts/exam/checks_if_dc.py",
    "scripts/exam/checks_br_tl.py",
    "tests/test_smoke.py",
]

SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache"}
SKIP_SUFFIX = {".pyc", ".pyo", ".log"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


README_TEXT = """# Final Exam Core — الامتحان والمصحّح فقط (v3)

مجلد مرجعي مستقل فيه **الامتحان نفسه** (مش الأداة):

| المسار | المحتوى |
|---|---|
| `exam/exam_questions_v2.json` | **المصدر الوحيد للحقيقة**: 33 سؤال مصحّح + 14 سؤال استكشافي + 8 محاور (أوزان + حدود دنيا) + الإعدادات + الأدوات + `system_prompt_style`. |
| `exam/منهج الامتحان الجديد.md` | منهج الامتحان الجديد مكتوب بالعربي. |
| `scripts/exam/` | **المصحّح الحتمي**: `spec.py` (تحميل المواصفات) · `grader.py` (التجميع + الحكم + التقييم الاستكشافي) · `rubric_engine.py` (نسب المحاور + بوابات الحد الأدنى) · `rubric_lib.py` + `checks_*.py` (165 فحص نصي/رقمي) · `lib.py` (أدوات النص). |
| `scripts/common.py` | أدوات مشتركة (مسارات · YAML · SHA). |
| `scripts/references.py` | مرجع Gemini 2.5 Pro (**عرض فقط ⛔**) + حساب المسافة على المحاور الثمانية. |
| `config/references.yaml` | مراجع العرض + حدود الحكم (80/60/40/20) — كل رقم مرجعي مكتوب مصدره. |
| `templates/qwen35_egyptian_nothink.jinja` | قالب المحادثة الثابت (مع منع thinking). |
| `scripts/verify_manifest.py` | يتحقق إن كل ملف في المجلد مطابق لبصمة SHA-256 في `MANIFEST.md`. |
| `tests/test_smoke.py` | اختبارات المصحّح (تقدر تتأكد بيها إن التصحيح سليم). |
| `MANIFEST.md` | كل الملفات + SHA-256 + تاريخ النسخة. |

> **مش موجود هنا:** التنزيل · fit · التشغيل · التقارير (Excel/HTML) · مسار Kaggle.
> دي **الأداة**، وهي في مجلد `AI Online Tester` الأصلي.

---

## 1) شروط صحّة الامتحان (من غيرها النتيجة مش comparable)

| الشرط | القيمة |
|---|---|
| system prompt | `system_prompt_style` **من ملف المواصفات** (ثابت، بيتسلّم مع كل سؤال) |
| chat template | `templates/qwen35_egyptian_nothink.jinja` + `enable_thinking=false` |
| temperature | `0.6` |
| top_p | `0.95` |
| seed | `1234` |
| ctx_size | `8192` |
| max_tokens | `4000` |
| تكرار الأسئلة | **1** · تمريرة واحدة لكل سؤال (درجة واحدة + ملاحظة واحدة) |
| الأسئلة الاستكشافية | 14 سؤال · **ميزة إضافية** بتتقيم من 20 (مش بتأثر على الحكم) |
| المصحّح | نفس النسخة دي بالظبط (تصحيح حتمي — مفيش LLM-judge) |

> ⚠ تغيير أي واحد من دول بيكسر المقارنة بين الموديلات.

## 2) إزاي تصحّح إجابات أي موديل (بأي أداة)

```python
import sys; sys.path.insert(0, "scripts")
from common import load_exam
from exam.grader import grade_exam

exam = load_exam()   # مبني من exam/exam_questions_v2.json

# الشكل المقبول: {id: نص} أو {id: {...}} (أو {id: [{...}, ...]} للتمريرات القديمة)
answers = {
    "EG1": "صباح الخير يا صاحبي، خُد راحة واشرب مية...",
    "HN1": {"answer": "...", "reasoning": "...", "finish": "stop"},
    "P1": {"answer": "..."},                        # سؤال استكشافي (ميزة إضافية)
}

graded = grade_exam(answers, exam)
print(graded["total"], "/100 —", graded["verdict"])
for qid, row in graded["questions"].items():
    print(qid, row["score"], "/", row["max"], "|", "؛ ".join(row["notes"]))
```

## 3) توزيع الدرجات (100 نقطة)

كل سؤال = **5 معايير rubric × درجتين** ⇒ **10 درجات** كحد أقصى للسؤال.
المجموع 33 سؤال × 10 = 330 خام ⇒ بيتنقّص بالوزن لكل محور ⇒ **0..100**.

| المحور | الوزن | الحد الأدنى % | الاختصار |
|---|---:|---:|---|
| العامية المصرية والشخصية | 15 | 60 | EG |
| أسلوب Gemini (تنظيم ودقة وعملية) | 15 | 50 | ST |
| المنطق والتفكير الخوارزمي | 20 | 60 | LG |
| الصدق ومنع التأليف | 10 | 60 | HN |
| اتباع التعليمات | 10 | 60 | IF |
| التوثيق وتقسيم المهام | 10 | 50 | DC |
| العصف الذهني والنقد | 10 | 0 | BR |
| الأدوات والـ agent (Hermes) | 10 | 50 | TL |

**نسبة المحور** = (مجموع نقاط المحور ÷ الحد الأقصى) × 100
**نقاط المحور** = النسبة × الوزن

**حدود الدنيا (معلومة):** لو نسبة المحور نزلت عن `min_percent` ⇒ بتظهر ⛔ للمراجعة،
بس **مش بتغيّر الحكم**.

**مستويات الحكم الخمسة** — من **المجموع النهائي /100** بس (كل 20% مستوى):
`≥80` ⇒ «ممتاز» · `≥60` ⇒ «جيد جدًا» · `≥40` ⇒ «جيد» · `≥20` ⇒ «مقبول» · أقل ⇒ «ضعيف».
> ⚠ المستوى بيتحدَّد من **مجموع درجاتك أنت** — مش من أي مرجع خارجي.

**الأسئلة الاستكشافية (14 سؤال):** تقييم مستقل من **20** (= متوسط أداء الأسئلة)
ظاهر بجوار التقييم الأساسي — **ميزة إضافية** مش بتأثر على المجموع ولا على الحكم.

## 3.1 المرجع (عرض فقط ⛔)

| المرجع | الاسم | المصدر | دوره |
|---|---|---|---|
| **🎯 مرجع** | **Gemini 2.5 Pro** | **بنشماركات عامة منشورة** (مش مقاسة على أسئلة امتحاننا) | **مقارنة بصرية فقط** |

> ⚠ **مش** يدخل في حساب درجة أي نموذج، ولا في الحكم، ولا في بوابات الحد الأدنى.
> مفيش «مجموع مرجعي» — لأن متوسط التقدير **مش درجة rubric**.
> **المسافة** = متوسط |الفرق| على المحاور الثمانية (٠ = مطابق تماماً · الأقل = الأقرب).
> كل رقم مرجعي ومصدره مكتوب في `config/references.yaml`.

## 4) التحقق

```bash
python -m unittest discover -s tests     # اختبارات المصحّح
```

## 5) ملاحظات

- التصحيح **حتمي 100%**: نفس الإجابات ⇒ نفس الدرجات دائماً.
- **مفيش LLM-judge**: 165 فحص نصي/رقمي في `scripts/exam/checks_*.py`.
- كل سؤال بتمريرة **واحدة**: درجة واحدة + ملاحظة واحدة من نفس الرد.
- الأسئلة الاستكشافية (14) ليها **تقييم مستقل من 20** — ميزة إضافية مش بتأثر على الحكم.
"""


def main() -> int:
    if DEST.exists():
        shutil.rmtree(DEST, ignore_errors=True)
    DEST.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []

    # 1) ملفات التوثيق
    for name in DOCS:
        src = ROOT / name
        if not src.exists():
            print(f"⚠ ناقص: {name}")
            continue
        copy_file(src, DEST / name)
        copied.append(DEST / name)

    # 2) كود التصحيح + ملف المواصفات
    for rel in CODE:
        src = ROOT / rel
        if not src.exists():
            print(f"⚠ ناقص: {rel}")
            continue
        dst = DEST / rel
        copy_file(src, dst)
        copied.append(dst)

    # 3) README
    (DEST / "README.md").write_text(README_TEXT, encoding="utf-8")
    copied.append(DEST / "README.md")

    # 4) MANIFEST
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Final Exam Core — Manifest",
        "",
        f"- **تاريخ النسخة:** {stamp}",
        "- **محتوى المجلد:** الامتحان (ملف المواصفات) + المصحّح + مراجع العرض + توثيق فقط.",
        "- **مش محتوى المجلد:** الأداة (تنزيل · fit · تشغيل · تقارير · Kaggle).",
        f"- **عدد الملفات:** {len(copied)}",
        "",
        "| # | الملف | الحجم (بايت) | SHA-256 |",
        "|---|---|---|---|",
    ]
    for i, path in enumerate(sorted(copied, key=lambda p: str(p).lower()), 1):
        rel = path.relative_to(DEST).as_posix()
        lines.append(f"| {i} | `{rel}` | {path.stat().st_size} | `{sha256(path)[:16]}…` |")
    lines += [
        "",
        "## التحقق",
        "",
        "```bash",
        "# تحقق إن كل ملف مطابق لبصمة SHA-256 في الـ MANIFEST",
        "python scripts/verify_manifest.py .",
        "```",
        "",
        "(أو من جذر المشروع: `python scripts/verify_manifest.py \"dist/Final Exam Core\"`)",
        "",
    ]
    (DEST / "MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"✅ Final Exam Core: {len(copied)} ملف + MANIFEST.md")
    for path in sorted(copied, key=lambda p: str(p).lower()):
        print(f"   {path.relative_to(DEST).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
