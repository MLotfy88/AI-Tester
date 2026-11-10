# أداة الدمج — `merge/`

أداة **مستقلة تماماً** بتدمج أكتر من تشغيل للامتحان في **تقرير HTML واحد** +
**ملف Excel واحد** — عشان تقدر تقارن بين 8 موديلات لما تقسّمهم على تشغيلين
(cause Kaggle limited disk space / model size).

> ⚠️ **مجلد `merge/` مستقل تماماً**: مالهوش أي تأثير على الأداة الأصلية.
> بيستورد **ولا سطر واحد** من `scripts/` — كل الأصول (CSS/JS/القالب) نسخة
> محلية في `merge/assets/`.

---

## 1. الاستخدام السريع

```powershell
python merge/merge_reports.py run1/exam-report.html run2/exam-report.html -o merged/
```

بيطلع في `merged/`:

| الملف | المحتوى |
|---|---|
| `exam-report-merged.html` | تقرير واحد فيه كل الموديلات (تصميم «مِحْيَر») |
| `exam-results-merged.xlsx` | الـExcel ده (11 شيت) بكل الموديلات مدموجة |

### خيارات

| الخيار | الوظيفة |
|---|---|
| `-o/--out DIR` | مجلد الخرج (افتراضياً `merged/`) |
| `--no-excel` | HTML بس — من غير Excel |
| `--xlsx FILE...` | ملفات Excel صراحة (افتراضياً: البحث عن `exam-results.xlsx` بجانب كل تقرير) |

---

## 2. البيانات المطلوبة بالظبط

الأداة بتاخد **تقرير HTML** لكل تشغيل + (اختياري) **ملف Excel** المرافق.

### 📄 الـHTML (إجباري)

كل ملف `exam-report.html` لسوق تشغيل مستقل. الأداة بتقرأ الـpayload
المدمج جواه (`<script id="payload">`) — **مش محتاج أي حاجة تانية**.

### 📊 الـExcel (اختياري بس مهم)

`exam-results.xlsx` **بجانب** كل تقرير HTML (نفس المجلد ونفس الاسم).
ليه مهم؟ لأن الـHTML الجديد فيه **بيانات مقلّمة** (HTML كامل — Excel ناقص):
الـfit والـsettings والـgatesAnswers الكاملة **مش** في الـpayload.

> الصيغة القديمة (`<script id="exam-data">` بالنتائج الكاملة) **مدعومة** —
> الأداة بتحوّلها لوحدها.

**لو شغّلت بـ `--no-excel`** هتاخد HTML كامل بس، والـExcel مش هيتعمل.

---

## 3. خطوات Kaggle (8 موديلات على تشغيلين)

### الخطوة 1 — التشغيل الأول (4 موديلات)

في الـkernel:

```bash
python scripts/exam_runner.py --models model-a model-b model-c model-d
```

### الخطوة 2 — نزّل الملفين

من **Output** في Kaggle نزّل:
- `exam-report.html`
- `exam-results.xlsx`

سمّيهم: `run1.html` + `run1.xlsx` (ومسار مجلد `run1/`).

### الخطوة 3 — التشغيل التاني (4 موديلات تانية)

```bash
python scripts/exam_runner.py --models model-e model-f model-g model-h
```

ونزّل: `run2.html` + `run2.xlsx`.

### الخطوة 4 — الدمج محلياً

```powershell
python merge/merge_reports.py run1/exam-report.html run2/exam-report.html -o merged/
```

افتح `merged/exam-report-merged.html` في المتصفح ✅

---

## 4. إيه اللي بيحصل في الدمج

### الـHTML
- كل الموديلات من كل التشغيلات في **payload واحد** (8 موديلات).
- **ألوان مميزة** لكل موديل (10 ألوان في البPalette).
- **درجات مرجعية Gemini** واحدة (عرض فقط ⛔ — مالوش أي تأثير في الدرجة ولا الحكم).
- الأرقام الثابتة (المحاور · الأوزان · الحدود الدنيا · الـsettings) بتتأكد إنها **واحدة** في كل التشغيلات.

### الـExcel
- **Categories / Gates / Questions / Profile / Rubric / Answers / Settings**:
  صفوف كل موديل بتتضاف تحت بعض.
- **Summary**: جدول الموديلات + صف المرجع + **جدول ترتيب القرب** (مرتّب من الأقرب للأبعد).
- **SpeedDetail**: الأعمدة بتتمدد — 4 أعمدة لكل موديل (ثوانٍ · tok/s · توكنز · finish).
- **Meta**: الصفوف العامة مرة واحدة + صف لكل موديل (quant · SHA · server log).

---

## 5. حل المشاكل

| العلامة | السبب | الحل |
|---|---|---|
| `❌ مفيش payload في التقرير` | الملف مش تقرير امتحان | اتأكد它是 `exam-report.html` من تشغيل حقيقي |
| `⚠️ مفيش Excel لكل تقرير` | `exam-results.xlsx` مش موجود جنب التقرير | نزّله من Kaggle أو استخدم `--xlsx` |
| `⚠️ موديل مكرر اتجاهل` | نفس الموديل في تشغيلين | مقصود — مفيش تكرار |
| الـHTML مفتوحش | المتصفح قديم | افتحه من جديد (Ctrl+F5) |

---

## 6. الملفات

```
merge/
├── merge_reports.py      ← الـCLI (نقطة الدخول)
├── excel_merge.py        ← منطق دمج الـExcel
├── assets/
│   ├── style.css         ← ثيم بارد + خط Cairo
│   ├── template.html     ← هيكل الصفحة
│   └── js/01..05.js      ← سكربتات التقرير
└── README.md
```

**التبعية الوحيدة:** `openpyxl` (اختيارية — لو محتاج Excel بس).
