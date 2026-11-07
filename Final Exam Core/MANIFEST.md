# Final Exam Core — Manifest

- **تاريخ النسخة:** 2026-11-07 19:16 UTC
- **محتوى المجلد:** الامتحان + المصحّح + توزيع الدرجات + توثيق نقاط الضعف فقط.
- **مش محتوى المجلد:** الأداة (تنزيل · fit · تشغيل · تقارير · Kaggle).
- **عدد الملفات:** 16

| # | الملف | الحجم (بايت) | SHA-256 |
|---|---|---|---|
| 1 | `config/exam.yaml` | 8807 | `cfb435187d01dfab…` |
| 2 | `EXAM-PAPER-v1.md` | 57251 | `a0d8e9544732f3c1…` |
| 3 | `EXAM-WEAKNESSES-AND-FIXES.md` | 54625 | `3386ac63a4a295d7…` |
| 4 | `prompts/owner_system_prompt.txt` | 4296 | `0e885ad517ca9056…` |
| 5 | `README.md` | 7944 | `0518d936c6860b63…` |
| 6 | `scripts/common.py` | 5615 | `305070fdbcfaca91…` |
| 7 | `scripts/exam/__init__.py` | 87 | `dfca87523ccd5c11…` |
| 8 | `scripts/exam/axis1.py` | 12077 | `102fb487a4604441…` |
| 9 | `scripts/exam/axis2.py` | 11094 | `00b9607f8f247c30…` |
| 10 | `scripts/exam/axis34.py` | 15877 | `7f84755c57d0d5d0…` |
| 11 | `scripts/exam/grader.py` | 22989 | `7569b9e8ea5a2508…` |
| 12 | `scripts/exam/lib.py` | 10709 | `b11a42a60cf8f2a5…` |
| 13 | `scripts/references.py` | 8864 | `dba23ae6e9581857…` |
| 14 | `scripts/verify_manifest.py` | 1888 | `62b37c32a629b349…` |
| 15 | `templates/qwen35_egyptian_nothink.jinja` | 7585 | `22e67fd2f9b2fc41…` |
| 16 | `tests/test_smoke.py` | 37107 | `d52cc9f167381d32…` |

## التحقق

```bash
# تحقق إن كل ملف مطابق لبصمة SHA-256 في الـ MANIFEST
python scripts/verify_manifest.py
```
