# AI Online Tester — امتحان المساعد المصري لموديلات GGUF (v3)

مشروع لتشغيل **امتحان ثابت v3** على موديلات GGUF من Hugging Face، ثم تصحيح الإجابات
**بشكل حتمي 100%** (165 فحص نصي/رقمي — **مفيش LLM-judge**) وإخراج:

- ملف Excel من **أحد عشر** شيتاً للمقارنة التفصيلية.
- تقرير HTML عربي مستقل (RTL) للمقارنة المباشرة بين الموديلات، فيه **كارت لكل موديل**
  و**الرسم السداسي** و**رسوم المقارنة** و**خريطة الدرجات** و**جدول السرعة لكل سؤال**
  و**سجل الإجابات الكامل**، مع **زر إظهار/إخفاء مرجع Gemini** بيشتغل على التقرير كله.
- ملخص Markdown يظهر في صفحة GitHub Actions.
- سجلات نصية للتشغيل.

> 📌 **المصدر الوحيد للحقيقة:** `exam/exam_questions_v2.json`.
> كل حاجة (الأسئلة · المحاور · الأوزان · الحدود الدنيا · الـ rubric · الإعدادات ·
> الأدوات · الـ system prompt) بتتقري من الملف ده. مفيش `config/exam.yaml` ولا ورقة
> امتحان تانية — الملف لو اتغير، الأداة كلها بتتغير معاه.
>
> 📌 **نسختان مرجعتان (مخرجات بناء، مش جزء من المستودع):** تتولّدا في مجلد `dist/`:
> `python scripts/build_final_reference.py` ⇒ `dist/Final AI Test/` (نسخة كاملة للاستخدام بأي أداة)
> و `python scripts/build_exam_core.py` ⇒ `dist/Final Exam Core/` (الامتحان + المصحّح فقط).
> كل واحدة مع `MANIFEST.md` بـ SHA-256.
>
> 📌 **سجل الأخطاء:** [`GRADING-ERRORS-AND-FIXES.md`](GRADING-ERRORS-AND-FIXES.md) — كل خطأ
> ظهر في التصحيح، سبب ظهوره، الكود قبل/بعد، والأثر بالأرقام.

التنفيذ الفعلي للامتحان بيحصل على **Kaggle GPU T4×2** (كارت T4 واحد فعلياً؛ ذاكرة
الكارتين مش بتتجمع). GitHub Actions دوره **لوحة تحكم فقط**. يعمل محلياً كمان.
لا يُستخدم أي LLM-judge، ولا تُكتب أي ملفات JSON وسيطة أو إجابات خام كملفات منفصلة.

---

## 1) قبل أن تبدأ — حدود يجب فهمها

| الحد | التفصيل |
|---|---|
| **GPU حقيقي على Kaggle** | GitHub runner دوره **المدخلات فقط**. التنفيذ الفعلي على **Kaggle GPU T4×2** (كارت واحد)، فالأرقام المقيسة حقيقية مش تقديرية. |
| **محاكاة السعة مش السرعة** | الـ kernel بيحجز VRAM/RAM زيادة علشان المتاح يبقى **3.4 GiB VRAM · 15.9 GiB RAM** زي جهازك. لكن **T4 أسرع من Quadro M4000M** — سرعة M4000M الفعلية تقديرية في قسم الملاءمة. |
| **fit وسرعة tg/pp تحليليان** | يُحسبان من metadata الـ GGUF وملف `config/device_profile.yaml` لجهازك المستهدف. ليسا قياساً فعلياً. |
| **السرعة الفعلية** | تظهر في تقرير Excel/HTML كـ `tok/s` مقاس فعلياً من زمن كل طلب **على T4**. للمقارنة مع جهازك استخدم قسم الملاءمة النظرية. |
| **`ngl` مش صامت** | لو حساب الـ fit فشل (مثلاً `gguf` مش متثبّت) ⇒ الأداة **توقف بخطأ واضح** بدل ما تشغّل على المعالج وتقول «GPU». |
| **منافسة الكارت** | الأداة **بتفحص** قبل كل موديل لو فيه سيرفر تاني شغّال (`llama-server` / `llama-cli` / `ollama`) — لو لقى واحد بتنوّهك في `run.log` وتعرض **بانر تحذير** في التقرير. **اقفل LM Studio** قبل أي قياس. |
| **مقارنة عادلة** | كل الموديلات تُشغَّل بنفس القالب، ونفس الـ system prompt (من ملف المواصفات)، ونفس الإعدادات، وعلى نفس بيئة التشغيل. |
| **ctx ثابت** | `ctx_size` لازم يكون **8192** بالضبط. أي قيمة أخرى تُرفض (`exit 2`) لأنها تكسر قابلية المقارنة. |
| **لا JSON وسيط** | مخرجات التشغيل: Excel + HTML + Markdown + سجلات نصية فقط. الـ HTML فيه payload JSON للعرض جوه الصفحة، لكنه مش ملف منفصل. |
| **إعادة الإنتاج** | التصحيح حتمي، لكن توليد الموديل نفسه قد يختلف قليلاً بين إصدارات llama.cpp والأجهزة. ثبّت `llama_tag` عند الحاجة. |

---

## 2) التشغيل من GitHub Actions (لوحة تحكم Kaggle)

1. ارفع المشروع إلى مستودع GitHub.
2. أضف السرّين في **Settings → Secrets and variables → Actions**:
   - `KAGGLE_USERNAME` و`KAGGLE_KEY` — من `kaggle.com → Settings → API` (مطلوبين دايماً).
   - `HF_TOKEN` اختياري، لكنه **مش بيتنقل جوه الـ kernel** (Kaggle Secrets بتتشال مع
     `kaggle kernels push` بالـ CLI) ⇒ النماذج لازم تكون **عامة**.
3. افتح **Actions → Exam Benchmark (Kaggle GPU) → Run workflow**.
4. املأ الحقول (القسم 4).
5. بعد الانتهاء نزّل الـ artifact باسم `exam-kaggle-<run_id>` من صفحة التشغيل.

خطوات الـ job بالترتيب:

1. `Checkout` للمستودع.
2. تجهيز Python 3.12 مع cache للـ pip.
3. تثبيت `requirements.txt` + `"kaggle>=1.6.17" six` (من غير `six` الـ CLI بيفشل).
4. `build_kernel.py` — يبني notebook الـ kernel و`kernel-metadata.json` محلياً بدون رفع.
5. `run_on_kaggle.py` — يرفع الـ kernel على Kaggle، ينتظر انتهاء التشغيل، وينزّل
   المخرجات إلى `out_kaggle/<run>/`.
6. داخل Kaggle: فحص كارت T4 · ballast VRAM/RAM · بناء llama.cpp بـ CUDA arch 75 ·
   تحميل النماذج · تشغيل الامتحان (33 سؤال مصحّح + 14 استكشافي) · توليد Excel/HTML/summary/logs.
7. كتابة `summary.md` في Job Summary (حتى عند الفشل).
8. رفع المخرجات كـ artifact لمدة 30 يوماً (حتى عند الفشل).

---

## 3) المخرجات

| الملف | الوصف |
|---|---|
| `exam-results.xlsx` | التقرير الرسمي: **11 شيت** (Summary / Categories / Gates / Questions / Rubric / Fit / Performance / SpeedDetail / Settings / Answers / Meta). |
| `exam-report.html` | تقرير مقارنة عربي مستقل، RTL، بدون CDN أو اعتماد خارجي. |
| `summary.md` | ملخص Markdown بجدول الموديلات والدرجات والبوابات. |
| `run.log` | سجل التشغيل الكامل (تنزيل، fit، تشغيل، تصحيح، أخطاء). |
| `logs/<slug>.server.log` | stdout/stderr الخاص بـ llama-server لكل موديل، وأول سطر فيه أمر التشغيل. |

### 3.1 شيتات Excel

| الشيت | المحتوى |
|---|---|
| **Summary** | صف لكل موديل: الحالة · الدرجة /100 · الحكم · المحاور تحت الحد الأدنى · نسبة كل محور · fit · ngl · السرعة المقيسة. وفيه **صف مرجع Gemini** (بنفسجي) مكتوب عليه «مرجع (عرض فقط ⛔)» + جدول **«🎯 ترتيب القرب من مرجع Gemini»** (المسافة = متوسط |فرق النسبة| على المحاور الثمانية · **الأقل = الأقرب**). |
| **Categories** | صف لكل (موديل × محور): الوزن · الحد الأدنى · الدرجة الخام · الحد الأقصى · النسبة % · النقاط · الحالة · الأسئلة. |
| **Gates** | بوابات الحد الأدنى لكل محور: Fired / التفاصيل / الأسئلة. |
| **Questions** | درجة كل سؤال: الموديل · السؤال · المحور · الدرجة · الحد · % · الحروف · التوكنز · الثواني · finish · المؤشرات · الملاحظات. |
| **Rubric** | تفصيل كل معيار rubric (5 لكل سؤال) بدرجته وملاحظته — المصحّح شفاف تماماً. |
| **Fit** | الملاءمة: الحجم · المعمارية · الطبقات · KV (GiB) · ngl · نسبة GPU · Fit class · **سقف tg/pp (نظري)** · أمر التشغيل المقترح · خطأ. |
| **Performance** | **الأداء المقيس فعلياً**: توليد tok/s (متوسط/أدنى/أعلى/وسيط/p95) · معالجة prompt · أول استجابة ms · زمن الطلب · تجهيز الموديل · RAM/VRAM مقيسة · اسم الكارت · **⚠ منافسة على الكارت**. |
| **SpeedDetail** | زمن كل سؤال × كل موديل (ثوانٍ · tok/s · توكنز · finish). |
| **Settings** | الإعدادات الفعلية لكل موديل: المصدر · القالب · KV · ngl · threads · device · flash-attn · flags إضافية · توصيات التوليد. |
| **Answers** | الإجابات الكاملة غير المقتطعة + نص السؤال + الملاحظات. |
| **Meta** | البيانات الوصفية: الأوقات · إصدار الامتحان · عدد الأسئلة · الإعدادات الثابتة · أرقام مرجع Gemini ومصدرها · بيئة التشغيل · الـ quant · بصمات SHA. |

### 3.2 أقسام تقرير HTML

1. **Hero** — هوية التقرير · عدد الموديلات · الإعدادات · بيئة التشغيل · كارت مرجع Gemini.
2. **زر «إظهار مرجع Gemini»** (`#show-gemini`) — بيخفي **كل** عناصر المرجع في التقرير
   (كارت · جداول · رسوم SVG · نصوص) مرة واحدة، والاختيار بيتحفظ في `localStorage`
   تحت المفتاح `exam-show-gemini`.
3. **KPI cards** — أفضل درجة · **🎯 الأقرب لمرجع Gemini** · **⚡ أسرع توليد (tok/s)** · عدد الناجح · محاور تحت الحد الأدنى.
4. **المقارنة** — جدول نهائي مرتب بالدرجة + أعمدة المحاور الثمانية + البوابات + Fit + السرعة + المسافة عن المرجع.
5. **🏅 النتيجة لكل موديل** — كارت لكل موديل: مقياس دائري للدرجة + الحكم + شرائط المحاور الثمانية + البوابات + المسافة عن المرجع + السرعة المقيسة.
6. **⬡ البصمة السداسية** — مضلّع لكل موديل + مضلّع منقّط لمرجع Gemini + لوحة قرار فيها «الأفضل في كل محور» + جدول القرب.
7. **📊 رسوم المقارنة** — عمودين SVG: (أ) الدرجة على كل محور (ب) الجودة مقابل الزمن.
8. **المحاور** — جدول/بطاقات لكل محور من الثمانية (الوزن · الحد الأدنى · النسبة · النقاط · الحالة).
9. **البوابات** — بوابات الحد الأدنى لكل محور.
10. **خريطة الدرجات** — heatmap لكل سؤال × موديل.
11. **⚡ الأداء الحقيقي المقيس** — أرقام مقيسة فعلياً على الكارت.
12. **الملاءمة** — جدول Fit والسرعة النظرية (تقديرية، للمقارنة والتخطيط).
13. **⚙️ الإعدادات** — كارت لكل موديل.
14. **الإجابات** — كل الإجابات جنب بعض مع فلترة حسب الموديل/المحور/البحث.
15. **🗂 سجل الإجابات الكامل** — لكل موديل: نص السؤال + نص THINKING + نص الإجابة + ملاحظات المصحح.
16. **البيانات** — metadata وبصمات SHA.
17. **دليل القراءة** — شرح الدرجات والبوابات وحدود الحكم.

المزايا: RTL كامل · وضع داكن/فاتح (محفوظ) · زر طباعة/PDF · فلاتر JavaScript اختيارية
(الجداول والإجابات ظاهرة بدون JS) · الصفحة **مستقلة تماماً** (لا CDN ولا طلبات شبكة) ·
كل نص الموديل بيمر عبر `html.escape` و`<` داخل الـ payload بيتهرَّب لـ `\u003c`.

---

## 4) مدخلات لوحة التحكم (Kaggle GPU)

| # | الاسم | مطلوب | الافتراضي | النوع | الشرح |
|---|---|---|---|---|---|
| 1 | `models` | نعم | — | string | repo ids على Hugging Face مفصولة بفاصلة. نماذج **عامة** فقط. |
| 2 | `quant_pattern` | نعم | `Q4_K_M` | string | جزء اسم الـ quant، أو **`auto`** لاختيار أفضل quant متاح تلقائياً. |
| 3 | `ctx_size` | نعم | `8192` | string | لازم 8192 بالضبط؛ أي قيمة أخرى تُرفض. |
| 4 | `accelerator` | نعم | `t4x2` | choice: `t4x2` | الكارت على Kaggle — T4×2، وكارت واحد فعلياً. |
| 5 | `vram_budget_gib` | لا | `3.4` | string | ميزانية VRAM المحاكاة (جهازك = 3.4). |
| 6 | `ram_budget_gib` | لا | `15.9` | string | الرام المتاحة المحاكاة (جهازك = 15.9). |
| 7 | `threads` | لا | `8` | string | عدد threads. الـ kernel بيقصّها لعدد أنوية Kaggle الفعلي. |
| 8 | `max_minutes` | لا | `350` | string | أقصى انتظار للـ kernel بالدقائق. |

> ⚠ **مفيش `policy`** — سياسة التصحيح اتشالت في v3. التصحيح واحد وحتمي.

### صيغ المدخلات

- **`models`**: يُقسم على `,` أو `;` أو سطر جديد، مع إزالة الفراغات والتكرار.
  ```text
  owner/model-a-GGUF, owner/model-b-GGUF, owner/model-c-GGUF
  ```
  محلياً يمكن تمرير مسار ملف GGUF مباشرة؛ لا يُحذف الملف المحلي بعد التشغيل.

  > **المقارنة بين أكثر من موديل:** الموديلات الممرَّرة بتشتغل **متسلسلة** على نفس الكارت
  > وبنفس الإعدادات الثابتة (temp=0.6 · top_p=0.95 · seed=1234 · ctx=8192 ·
  > max_tokens=4000 · نفس الـ system prompt · نفس القالب)، وبعدين **كل أقسام التقرير
  > والـ Excel** بتغطي كل الموديلات جنب بعض. الحد العملي هو **ميزانية وقت الـ kernel**.

- **`quant_pattern`**: مثال `Q4_K_M` أو `IQ4_XS` أو **`auto`**.
  1. يقرأ شجرة الريبو من HF API بدون تنزيل الريبو كله.
  2. يجمع الملفات المطابقة في مجموعات single/split.
  3. يرفض أي split ناقص الأجزاء.
  4. يستبعد `mmproj` / `projector` / `vision` / `image` / `embed` / `clip`.
  5. عند تساوي الدرجة يفضّل الـ split المكتمل، ثم الأصغر حجماً، ثم المسار (ترتيب حتمي).
  6. ينزّل **كل أجزاء** الـ split، وllama.cpp يقرأ من الجزء الأول.

- **`ctx_size`**: `8192` فقط. القيمة تُمرَّر إلى `llama-server -c` وإلى حساب KV cache.

- **`accelerator`**: `t4x2` فقط. الـ kernel بيفحص إن الكارت T4 فعلاً، وإلا يوقف فوراً.

- **`vram_budget_gib` / `ram_budget_gib`**: الـ kernel بيحجز ballast علشان المتاح يساوي الميزانية دي بالظبط.

- **`threads`**: الـ kernel بيستخدم `min(threads, cpu_count)` علشان ما يحصلش oversubscription.

### متغيرات بيئة اختيارية

| المتغير | الاستخدام |
|---|---|
| `HF_TOKEN` | توكن Hugging Face للريبوهات المقيّدة/الخاصة **عند التشغيل المحلي**. في مسار Kaggle لازم النماذج تكون عامة. |
| `LLAMA_SERVER_BIN` | مسار llama-server جاهز؛ يتخطى التنزيل/البناء في `install_llamacpp.py`. |
| `GITHUB_TOKEN` / `GH_TOKEN` | يستخدمهما سكربت التثبيت لرفع حد GitHub API. |
| `HF_HUB_DISABLE_PROGRESS_BARS` | يقلل ضجيج التحميل (مضبوط في الـ workflow). |

---

## 5) خط سير التشغيل خطوة بخطوة

### 5.1 داخل `run_exam.py` (لكل موديل)

1. **تحقق من `ctx`** يساوي 8192، وإلا يخرج بكود `2`.
2. **حلّل المصدر**: مسار GGUF محلي، أو repo id من Hugging Face.
3. **نزّل الملف/الأجزاء** مع فحص الحجم والقرص.
4. **اقرأ metadata** من GGUF واحسب fit و`ngl` وسقف tg/pp.
   - لو الـ fit فشل ⇒ **خطأ صريح** (مش `ngl=0` صامت).
5. **شغّل llama-server** على منفذ حر مع:
   - `--jinja`
   - `--chat-template-file templates/qwen35_egyptian_nothink.jinja`
   - `--chat-template-kwargs '{"enable_thinking": false}'`
   - `-ngl <المحسوب>` · `-c 8192` · `-t <threads>` · `--device <CUDA0|Vulkan0>`
   - KV cache type عند اختياره
6. **انتظر `/health`** حتى يصبح جاهزاً.
7. **أرسل الأسئلة بالتسلسل** على `/v1/chat/completions` بنفس الـ system prompt لكلهم.
8. **قِس** زمن كل سؤال، التوكنز، `tok/s`، وpeak RSS.
9. **أوقف السيرفر** ونظّف العمليات دائماً (`finally`).
10. **صحّح الإجابات** في الذاكرة عبر `exam.grader.grade_exam`.
11. **اكتب checkpoint** من Excel + HTML + summary بعد كل موديل.

### 5.2 معالجة الأخطاء

- فشل تنزيل/تحميل موديل → يُسجَّل `status=failed` مع السبب، ويستمر باقي الموديلات.
- فشل `/health` أو خروج السيرفر → الموديل يفشل، وتُنظّف العملية.
- 3 أخطاء طلبات متتالية → يتوقف الموديل ويعتبر fatal.
- تجاوز وقت الموديل → بقية الأسئلة `TIMEOUT` وفارغة.
- انتهاء الوقت الكلي → الموديلات المتبقى تُسجَّل failed بدون تشغيل.
- **كود الخروج**: `0` لو موديل واحد على الأقل اكتمل · `1` لو كل الموديلات فشلت · `2` لخطأ إعداد.

---

## 6) الامتحان والتصحيح (v3)

### 6.1 المواصفات الثابتة (لا تُغيَّر للمقارنة)

| الإعداد | القيمة | المصدر |
|---|---|---|
| `temperature` | `0.6` | `run_settings` |
| `top_p` | `0.95` | `run_settings` |
| `seed` | `1234` | `run_settings` |
| `ctx_size` | `8192` | `run_settings` (و`run_exam.py` بيقفل أي قيمة تانية) |
| `max_tokens` | `4000` | `run_settings` |
| نظام التكرار | 2 مرة لكل سؤال في `LG`/`IF`/`TL` | `run_settings.repeat_for` |
| القالب | `templates/qwen35_egyptian_nothink.jinja` | مسار المشروع |
| system prompt | `system_prompt_style` | **من ملف المواصفات** |
| thinking | مغلق (`enable_thinking: false`) | `--chat-template-kwargs` |

### 6.2 الأسئلة — 33 مصحّح + 14 استكشافي

| المحور | الاختصار | عدد الأسئلة | الوزن | الحد الأدنى % |
|---|---|---:|---:|---:|
| العامية المصرية والشخصية | **EG** | 6 | 15 | 60 |
| أسلوب Gemini (تنظيم ودقة وعملية) | **ST** | 4 | 15 | 50 |
| المنطق والتفكير الخوارزمي | **LG** | 6 | 20 | 60 |
| الصدق ومنع التأليف | **HN** | 4 | 10 | 60 |
| اتباع التعليمات | **IF** | 4 | 10 | 60 |
| التوثيق وتقسيم المهام | **DC** | 3 | 10 | 50 |
| العصف الذهني والنقد | **BR** | 3 | 10 | 0 |
| الأدوات والـ agent (Hermes) | **TL** | 3 | 10 | 50 |

- **33 سؤال مصحّح** = 33 × (5 معايير × 2 درجة) = **330 درجة خام** ⇒ بعد التوزيع بالأوزان = **0..100**.
- **14 سؤال استكشافي** (بلا درجة) — للاطلاع وتوثيق سلوك الموديل.
- **إجمالي الطلبات**: 33 + 13 (تمريرة ثانية لكل سؤال في LG/IF/TL) + 14 = **60**.

### 6.3 كيف تُحسب الدرجة

| الخطوة | الصيغة |
|---|---|
| درجة السؤال | مجموع نقاط معاييره الخمسة (كل معيار 0 / 1 / 2) ⇒ **0..10** |
| نسبة المحور | (مجموع درجات أسئلته ÷ (10 × عدد أسئلته)) × **100** |
| نقاط المحور | النسبة × **الوزن** |
| المجموع | مجموع نقاط المحاور الثمانية ⇒ **0..100** |

- **محاور LG و IF و TL بتتكرر مرتين** و**المتوسط** هو المعتمد (مفتاح `LG1__1`/`LG1__2` أو قائمة تحت `LG1`).
- **بوابة الحد الأدنى:** لو نسبة المحور نزلت عن `min_percent` ⇒ **«فشل حرج ⛔»**،
  حتى لو المجموع النهائي عالي. (BR حدّه 0 ⇒ مش بيتفعّل.)

### 6.4 حدود الحكم

| المجموع | الحكم |
|---|---|
| `≥ 85` | **قريب جدًا من Gemini 2.5 Pro في المقاييس دي 🟢** |
| `≥ 70` | **قريب مع فجوات 🟡** |
| `≥ 55` | **متوسط 🟠** |
| `< 55` | **أقل من الحد الأخير — بعيد 🔴** |

> ⚠ لو أي محور تحت حدّه الأدنى ⇒ الحكم **«فشل حرج ⛔»** (الأعلى من حدود المجموع).

### 6.5 المصحّح — حتمي بالكامل

- **165 فحص** نصي/رقمي في 4 ملفات: `checks_eg_st.py` · `checks_lg_hn.py` ·
  `checks_if_dc.py` · `checks_br_tl.py`.
- كل معيار rubric بيتحوّل لفحص واحد أو أكتر ⇒ نفس الإجابة دايماً بتدي نفس الدرجة.
- **مفيش LLM-judge** ⇒ الحتمية مكسورةش.
- **حارس الرد الفاضي:** نص فارغ **من غير استدعاء أدوات** ⇒ **صفر على السؤال**.
  (من غير الحارس ده كان الرد الفاضي بياخد 18.21/100 — إيجابية كاذبة.)
- **الرفض الصريح مش جريمة:** الرد اللي بيقول «مش عارف» ويطلب مصدر **بياخد نقاط
  أعلى** من الرد اللي بيؤلّف تفاصيل (محور HN: الرفض ≈ 70% · التأليف ≈ 40%).

### 6.6 مرجع Gemini 2.5 Pro — عرض فقط ⛔

| البند | التفصيل |
|---|---|
| **الاسم** | Gemini 2.5 Pro |
| **الدور** | **عرض فقط (display-only)** — `affects_verdict: false` |
| **المصدر** | **بنشماركات عامة منشورة** (مش مقاسة على أسئلة امتحاننا) — كل رقم ومصدره مكتوب في `config/references.yaml` |
| **لا يدخل في** | حساب درجة أي نموذج · الحكم (verdict) · بوابات الحد الأدنى |
| **المسافة** | متوسط |فرق النسبة| على **المحاور الثمانية** (٠ = مطابق تماماً · **الأقل = الأقرب**) |

- **مفيش «مجموع مرجعي»** — لأن متوسط التقدير **مش درجة rubric** ⇒ أي مقارنة بالمجموع
  كانت هتبقى مقارنة بين قياسين مختلفين. رقم `gemini_total` بيظهر كمتوسط تقديري
  **مكتوب جنبه إنه مش درجة rubric**.
- **الأرقام المرجعية:** EG 70.7 · ST 82.5 · LG 82.9 · HN 73.5 · IF 71.6 · DC 82.2 ·
  BR 79.0 · TL 57.2 — ومعاها `extra_indicators` (LMArena 1457 Elo، HLE 21.6%…).
- **زر الإخفاء في HTML** بيخفي كل عناصر المرجع (class `gem-ref`) عبر
  `html[data-gem="off"] .gem-ref{display:none!important}`، والاختيار محفوظ في
  `localStorage` (`exam-show-gemini`).

---

## 7) شرح كل ملف في المشروع

### 7.1 المصدر والمواصفات

| الملف | الوظيفة |
|---|---|
| `exam/exam_questions_v2.json` | **المصدر الوحيد للحقيقة**: 33 سؤال مصحّح (rubric من 5 معايير) + 14 استكشافي + 8 محاور (أوزان + حدود دنيا) + `run_settings` + `tools` + `system_prompt_style`. |
| `exam/منهج الامتحان الجديد.md` | منهج الامتحان الجديد مكتوب بالعربي. |
| `config/references.yaml` | مراجع **العرض فقط** + حدود الحكم (85/70/55). كل رقم مرجعي مكتوب مصدره. |
| `config/device_profile.yaml` | مواصفات جهازك المستهدف: CPU/RAM/GPU، ميزانية VRAM، ومعاملات المعايرة. |
| `config/model_overrides.yaml` | توصيات per-model (قالب، KV، ngl، threads، device، flags، sampling موصى به). |
| `templates/qwen35_egyptian_nothink.jinja` | قالب المحادثة الثابت مع منع thinking. |
| `HF-Model-Selection-Workflow.md` | مرجع اختيار موديل GGUF: fit، حدود VRAM/RAM، السرعة، وأمثلة. |
| `GRADING-ERRORS-AND-FIXES.md` | **سجل أخطاء التصحيح**: كل خطأ ظهر، سبب ظهوره، الكود قبل/بعد، والأثر بالأرقام. |
| `README.md` | هذا الملف. |
| `requirements.txt` | `gguf`, `huggingface_hub`, `openpyxl`, `psutil`, `PyYAML`. |

### 7.2 المصحّح

| الملف | الوظيفة |
|---|---|
| `scripts/exam/spec.py` | تحميل ملف المواصفات وبناء المواصفات الموحّدة (`build_exam`) + حساب التكرارات + إجمالي الطلبات. |
| `scripts/exam/grader.py` | تصحيح إجابات موديل واحد: تطبيع الشكل (نص / dict / قائمة تكرار / `qid__N`) + التجميع + الحكم. |
| `scripts/exam/rubric_engine.py` | محرك الـ rubric: `score_question` (5 معايير) · `aggregate` (النسب والأوزان والحدود الدنيا) · `verdict_for`. |
| `scripts/exam/rubric_lib.py` | أدوات النص: تطبيع الأرقام، كشف الجداول/الخطوات/الكود، تشغيل Python في sandbox. |
| `scripts/exam/checks_eg_st.py` | فحوص محوري EG و ST. |
| `scripts/exam/checks_lg_hn.py` | فحوص محوري LG و HN. |
| `scripts/exam/checks_if_dc.py` | فحوص محوري IF و DC. |
| `scripts/exam/checks_br_tl.py` | فحوص محوري BR و TL (منها trace الأدوات). |
| `scripts/exam/lib.py` | أدوات النص العربية (نسبة العامية · الفصحى · الحروف الغريبة · كشف الكود). |

### 7.3 التشغيل والتقارير

| الملف | الوظيفة |
|---|---|
| `scripts/common.py` | أدوات مشتركة: YAML، مسارات المشروع، SHA-256، تنسيق الأحجام، تشغيل أوامر، تضمين JSON آمن. |
| `scripts/hf_resolver.py` | شجرة HF، اختيار الـ quant، دعم split الكامل، فحص الحجم/القرص، التنزيل. |
| `scripts/install_llamacpp.py` | بناء/تنزيل llama.cpp (CPU/CUDA) + نسخ كل الـ `.so` + RPATH `$ORIGIN` + **فحص `--version` بيفشل صريحاً**. |
| `scripts/fit_check.py` | metadata الـ GGUF، KV/ngl/fit class، سقف tg/pp النظري. |
| `scripts/model_settings.py` | overrides لكل موديل + توصيات Sampling من `generation_config.json`. |
| `scripts/exam_runner.py` | تشغيل llama-server (مع `-ngl`/`--device`/`--chat-template-file` **دايماً**) · health · إرسال الأسئلة · قياس · تنظيف. |
| `scripts/run_exam.py` | المنسّق الكامل: تنزيل → fit → إعدادات → تشغيل → تصحيح → Excel/HTML/summary → تنظيف. |
| `scripts/references.py` | الطبقة المشتركة للمراجع: مرجع Gemini (عرض فقط) · `gemini_gap` · `gemini_ranking` · وسم المصدر · بيئة التشغيل. |
| `scripts/excel_report.py` | تقرير Excel (11 شيت). |
| `scripts/html_report.py` | تقرير HTML العربي المستقل + زر إخفاء مرجع Gemini. |
| `scripts/html_charts.py` | الرسوم SVG: الرادار · كارت لكل موديل · رسوم المقارنة · heatmap · جدول السرعة. |
| `scripts/verify_manifest.py` | يتحقق إن كل ملف في مجلد المرجع مطابق لبصمة SHA-256. |
| `scripts/build_final_reference.py` | يبني `dist/Final AI Test/`. |
| `scripts/build_exam_core.py` | يبني `dist/Final Exam Core/`. |

### 7.4 Kaggle

| الملف | الوظيفة |
|---|---|
| `kaggle/kernel_main.py` | الـ notebook: تثبيت `gguf`/`huggingface_hub`/`psutil` · فحص الكارت · ballast · بناء CUDA · تشغيل · **تنظيف Output**. |
| `kaggle/build_kernel.py` | يولّد `kernel-metadata.json` + notebook (المشروع مضغوط base64) بدون رفع. |
| `kaggle/run_on_kaggle.py` | رفع الـ kernel، انتظار، وتنزيل المخرجات. |

### 7.5 الاختبارات

`tests/test_smoke.py` — **55 اختبار** بدون شبكة أو llama.cpp: المواصفات · المصحّح ·
حتمية الدرجات · التكرار · حارس الرد الفاضي · بوابات الحد الأدنى · المرجع (عرض فقط)
· شيتات Excel · toggle مرجع Gemini في HTML · fit · اختيار HF · الـ workflow ·
استيراد `run_exam.py` · ومساحة الأسماء بعد حذف واجهات v1.

```bash
python -m unittest discover -s tests -v
```

---

## 8) التشغيل المحلي

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt

# Linux: تثبيت/بناء llama.cpp
python scripts/install_llamacpp.py --dir .llama --tag master --jobs 4 --backend cuda --cuda-arch 75

# المنسّق الكامل
python scripts/run_exam.py \
  --models "owner/model-GGUF,owner/other-GGUF" \
  --quant Q4_K_M \
  --ctx 8192 \
  --server .llama/bin/llama-server \
  --threads 4 \
  --device CUDA0 \
  --out out
```

> على Windows: `install_llamacpp.py` مخصص Linux — نزّل `llama-server.exe` أو ابنِه
> بـ CMake، ومرّر مساره بـ `--server`.

### خيارات `run_exam.py`

| الخيار | الافتراضي | الشرح |
|---|---|---|
| `--models` | مطلوب | repo ids أو مسارات GGUF، مفصولة بفاصلة/فاصلة منقوطة/سطر. |
| `--quant`, `--quant-pattern` | `Q4_K_M` | نمط اسم الـ quant، أو `auto`. |
| `--ctx` | `0` (= من المواصفات) | لازم `8192`؛ أي قيمة تانية ⇒ `exit 2`. |
| `--kv` | من الإعدادات | `f16` / `q8_0` / `q4_0`. |
| `--threads` | من الإعدادات | threads. |
| `--ngl` | محسوب من الملاءمة | طبقات GPU؛ **لو الـ fit فشل ⇒ خطأ صريح**. |
| `--device` | — | device للـ offload (`CUDA0` · `Vulkan0`). |
| `--device-profile` | `config/device_profile.yaml` | ملف جهازك المستهدف. |
| `--runner-kind` | حسب `--device` | `kaggle_gpu` / `local_gpu` / `local_cpu` / `github_cpu` / `custom`. |
| `--runner-label` / `--runner-gpu` | — | وسم بيئة التشغيل واسم الكارت. |
| `--server` | `.llama/bin/llama-server` | مسار llama-server. |
| `--template` | `templates/qwen35_egyptian_nothink.jinja` | قالب المحادثة. |
| `--template-mode` | `auto` | `auto` · `exam` · `model`. |
| `--overrides` | `config/model_overrides.yaml` | توصيات الموديلات. |
| `--apply-recommended-sampling` | false | يطبّق توصيات temperature/top_p/top_k (بيكسر الحتمية!). |
| `--exam` | `exam/exam_questions_v2.json` | **ملف مواصفات الامتحان v3**. |
| `--out` | `out` | مجلد المخرجات. |
| `--run-id` | timestamp | معرف التشغيل في التقارير. |
| `--max-gib` | `10` | حد التنزيل. |
| `--model-timeout` | `300` | دقائق لكل موديل. |
| `--total-timeout` | `330` | دقائق لكل التشغيل. |
| `--request-timeout` | `1800` | ثواني لكل سؤال. |
| `--startup-timeout` | `900` | ثواني انتظار health. |
| `--limit` | `0` | عدد أسئلة للتجربة السريعة (0 = الكل). |
| `--flash-attn` | — | `on` / `off` / `auto`. |
| `--extra-server-args` | — | أعلام llama-server إضافية. |
| `--keep-models` | false | عدم حذف ملفات الموديل. |
| `--dry-run` | false | طباعة الموديلات فقط بدون تنزيل/تشغيل. |

---

## 9) صيغ البيانات

### 9.1 نتيجة الموديل في الذاكرة (لا تُكتب كـ JSON)

```python
{
  "status": "ok" | "failed",
  "model": "owner/model-GGUF",
  "manifest": {
    "repo", "revision", "sha", "license", "quant_pattern",
    "files": [{"path", "local_path", "bytes"}],
    "primary_path", "total_bytes", "local_dir", "url", "is_local"
  },
  "fit": {
    "file", "file_bytes", "file_gib", "ctx", "kv",
    "meta": {"arch", "block_count", "head_count", "head_count_kv", "error"},
    "n_layers", "n_head", "n_kv", "head_dim", "kv_total_gib", "need_full_gib",
    "ngl", "gpu_share", "fit_class", "tg_tps", "pp_tps",
    "budget_gib", "ram_gib", "run_command", "error"
  },
  "runtime": {
    "started_at", "finished_at", "seconds_total", "peak_rss_mib", "peak_vram_mib",
    "device", "ngl", "threads", "kv", "template", "gpu_name",
    "perf": {
      "tg_tps": {"avg", "min", "max", "median", "p95"},
      "pp_tps": {"avg"},
      "ttft_ms": {"avg", "p95"},
      "request_seconds": {"avg", "max"},
      "startup_seconds", "seconds_total", "total_generated_tokens", "requests_count"
    },
    "requests": [{"id", "index", "seconds", "tokens", "tps", "finish", "chars"}],
    "gpu_contention": {"competing_processes": [...]}
  },
  "exam": {
    "total", "max", "verdict", "verdict_reason",
    "categories": {"EG": {"score", "max", "percent", "points", "weight",
                           "min_percent", "failed", "questions"}, ...},
    "questions": {"EG1": {"id", "title", "prompt", "category", "category_name",
                          "rubric", "criteria", "score", "max", "percent",
                          "passes", "pass_details", "answer", "reasoning",
                          "chars", "tokens", "seconds", "finish", "notes", "empty"}, ...},
    "gates": [{"code", "title", "threshold", "fired", "detail", "questions"}],
    "failed_categories": ["ST", "LG", ...],
    "missing_questions": [...],
    "references": {...}
  },
  "settings": {"source", "chat_template", "kv_cache_type", "n_gpu_layers",
               "threads", "device", "flash_attn", "extra_server_args", "notes"},
  "error": ""
}
```

### 9.2 شكل الإجابات المقبولة للمصحّح

```python
answers = {
    "EG1": "نص الإجابة",
    "HN1": {"answer": "...", "reasoning": "...", "finish": "stop"},
    "LG1": [{"answer": "..."}, {"answer": "..."}],      # تمريرتين ⇒ المتوسط
    "TL1__1": "...", "TL1__2": "...",                   # نفس المعنى بصيغة مفتاح
}
```

---

## 10) بناء النسخ المرجعية

```bash
python scripts/build_exam_core.py      # ⇒ dist/Final Exam Core/  (امتحان + مصحّح)
python scripts/build_final_reference.py # ⇒ dist/Final AI Test/    (نسخة كاملة)
```

كل نسخة مع `MANIFEST.md` فيه SHA-256 لكل ملف — للتأكد إن النسخة سليمة:

```bash
python scripts/verify_manifest.py "dist/Final Exam Core"
python scripts/verify_manifest.py "dist/Final AI Test"
```
