"""اختبارات دخان سريعة للامتحان v3 (بدون شبكة أو llama.cpp).

التشغيل:
    python -m unittest discover -s tests -v

الامتحان v3: 33 سؤال مصحّح · 8 محاور بأوزان وحدود دنيا · 165 فحص حتمي.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from common import load_exam  # noqa: E402
from exam.grader import grade_exam  # noqa: E402
from exam.rubric_engine import (  # noqa: E402
    ALL_CHECKS,
    aggregate,
    has_checks,
    score_question,
    verdict_for,
)
from exam.checks_profile import score_profile_question  # noqa: E402
from exam.spec import all_questions, build_exam, repeats_for, total_planned_requests  # noqa: E402
from exam.spec import build_exam, repeats_for, total_planned_requests  # noqa: E402
from references import (  # noqa: E402
    category_short,
    gemini_gap,
    gemini_ranking,
    gemini_reference,
    gemini_total,
    gemini_values,
)

# اختياري: الموديلات دي مش موجودة في مجلد «Final Exam Core» (امتحان + مصحّح بس)
# ⇒ الاستيرادات تفشل بـ ImportError والاختبارات المرتبطة بتتخطّى بدل ما يكسر الملف كله.
try:  # noqa: E402
    from excel_report import write_workbook
except ImportError:  # pragma: no cover
    write_workbook = None  # type: ignore[assignment]

try:  # noqa: E402
    from fit_check import classify, estimate, speed_model
except ImportError:  # pragma: no cover
    classify = estimate = speed_model = None  # type: ignore[assignment]

try:  # noqa: E402
    from hf_resolver import select_quant
except ImportError:  # pragma: no cover
    select_quant = None  # type: ignore[assignment]

try:  # noqa: E402
    from html_report import write_report
except ImportError:  # pragma: no cover
    write_report = None  # type: ignore[assignment]

try:  # noqa: E402
    from exam_runner import _other_inference_servers
except ImportError:  # pragma: no cover
    _other_inference_servers = None  # type: ignore[assignment]


#: إجابة "مثالية" تقريبية لكل سؤال — بتستخدم للاختباراتPositive.
GOOD_ANSWER = (
    "صباح الخير يا صاحبي، فاهم إنك تعبان النهارده. خُد راحة، واشرب مية، "
    "وامشي شوية، ونام بدري. لو الموضوع محتاج رقم محدد مش هاخترعه."
)

BAD_ANSWER = "I cannot answer that question."


def _fake_result(model: str = "owner/model-GGUF") -> dict:
    """نتيجة تشغيل وهمية بحالات كاملة (مفيد للتقارير)."""
    exam = load_exam()
    answers = {
        q["id"]: {
            "answer": GOOD_ANSWER,
            "finish": "stop",
            "usage": {"completion_tokens": 14},
            "seconds": 1.5,
        }
        for q in exam["questions"]
    }
    graded = grade_exam(answers, exam, model_meta={"repo": model})
    return {
        "status": "ok",
        "model": model,
        "manifest": {"repo": model, "total_bytes": 123_456_789, "quant_pattern": "Q4_K_M"},
        "fit": {
            "file": "model.gguf",
            "file_gib": 0.115,
            "fit_class": "Partial",
            "ngl": 12,
            "n_layers": 28,
            "kv_total_gib": 0.2,
            "need_full_gib": 0.3,
            "tg_tps": 10.2,
            "pp_tps": 50.1,
            "params_b_assumed": 1.7,
            "meta": {
                "arch": "qwen3",
                "block_count": 28,
                "head_count": 8,
                "head_count_kv": [2, 2],
            },
            "budget_gib": 3.4,
            "gpu_share": 0.43,
            "ram_gib": 15.9,
            "device": {"gpu_bw_gbps": 160.0, "ram_bw_gbps": 27.0},
            "run_command": "llama-server -m model.gguf -c 8192 -ngl 12 -t 4 --jinja",
        },
        "runtime": {
            "seconds_total": 120.5,
            "peak_rss_mib": 8000,
            "peak_vram_mib": 3200,
            "device": "CUDA0",
            "ngl": 12,
            "threads": 4,
            "kv": "f16",
            "template": "templates/qwen35_egyptian_nothink.jinja",
            "gpu_name": "Tesla T4",
            "perf": {
                "source": "llama.cpp timings",
                "tg_tps": {"avg": 22.4, "min": 18.0, "max": 30.1, "median": 22.0, "p95": 28.0},
                "pp_tps": {"avg": 310.0},
                "ttft_ms": {"avg": 90.0, "p95": 200.0},
                "request_seconds": {"avg": 4.2, "max": 9.9},
                "prompt_ms": {"avg": 12.0},
                "predicted_ms": {"avg": 30.0},
                "startup_seconds": 22,
                "seconds_total": 120.5,
                "total_generated_tokens": 5000,
                "requests_count": 33,
            },
            "requests": [{"tps": 22.4}],
            "gpu_contention": {"competing_processes": []},
        },
        "exam": graded,
        "settings": {
            "source": "cli",
            "chat_template": "templates/qwen35_egyptian_nothink.jinja",
            "template_source": "exam",
            "kv_cache_type": "f16",
            "n_gpu_layers": 12,
            "threads": 4,
            "device": "CUDA0",
            "flash_attn": "on",
            "extra_server_args": [],
            "notes": "",
        },
        "error": "",
    }


# --------------------------------------------------------------------------- المواصفات
class SpecTests(unittest.TestCase):
    """مواصفات v3 — المصدر الوحيد للحقيقة."""

    def test_version_and_shape(self) -> None:
        exam = load_exam()
        self.assertEqual(exam["version"], "v3")
        self.assertEqual(len(exam["questions"]), 33, "لازم 33 سؤال مصحّح")
        self.assertEqual(len(exam["profile"]), 14, "لازم 14 سؤال استكشافي")
        self.assertEqual(len(exam["categories"]), 8, "لازم 8 محاور")

    def test_categories_are_dict_with_weights_and_mins(self) -> None:
        exam = load_exam()
        categories = exam["categories"]
        self.assertIsInstance(categories, dict, "categories لازم dict (مش list)")
        total_weight = 0.0
        for key, cfg in categories.items():
            self.assertIn("name", cfg)
            self.assertIn("weight", cfg)
            self.assertIn("min_percent", cfg)
            self.assertIn("questions", cfg)
            self.assertTrue(cfg["questions"], f"المحور {key} من غير أسئلة")
            total_weight += float(cfg["weight"])
        self.assertAlmostEqual(total_weight, 100.0, places=2, msg="مجموع الأوزان لازم 100")

    def test_each_question_has_five_rubric_criteria_and_max_ten(self) -> None:
        exam = load_exam()
        for q in exam["questions"]:
            self.assertEqual(len(q["rubric"]), 5, f"{q['id']} rubric لازم 5 معايير")
            self.assertEqual(q["max"], 10.0, f"{q['id']} الحد الأقصى 10")
            self.assertIn(q["category"], exam["categories"])

    def test_settings_are_fixed(self) -> None:
        exam = load_exam()
        settings = exam["settings"]
        self.assertEqual(settings["ctx_size"], 8192)
        self.assertEqual(settings["max_tokens"], 4000)
        self.assertEqual(settings["seed"], 1234)
        self.assertEqual(settings["repeats"], 1, "كل سؤال بتمريرة واحدة")
        self.assertEqual(list(settings["repeat_for"]), [])

    def test_system_prompt_comes_from_spec(self) -> None:
        exam = load_exam()
        self.assertTrue(exam["system_prompt"], "لازم system_prompt_style من ملف المواصفات")
        self.assertNotIn("owner_system_prompt", str(exam["system_prompt"]).lower())

    def test_single_pass_for_every_axis(self) -> None:
        exam = load_exam()
        for key in ("LG", "IF", "TL", "EG", "HN", "ST", "DC", "BR"):
            self.assertEqual(repeats_for(exam, key), 1, key)

    def test_total_planned_requests(self) -> None:
        exam = load_exam()
        # 33 سؤال مصحّح (تمريرة واحدة) + 14 سؤال استكشافي
        total = total_planned_requests(exam)
        self.assertEqual(total, 33 + 14)
        self.assertEqual(total_planned_requests(exam, include_profile=False), 33)

    def test_all_questions_includes_profile(self) -> None:
        exam = load_exam()
        every = all_questions(exam)
        self.assertEqual(len(every), 33 + 14)
        ids = [q["id"] for q in every]
        self.assertEqual(ids[:33], [q["id"] for q in exam["questions"]])
        self.assertTrue(all(q.get("profile") for q in every[33:]))
        self.assertTrue(all(q["category"] == "PROFILE" for q in every[33:]))

    def test_build_exam_rejects_bad_spec(self) -> None:
        with self.assertRaises(Exception):
            build_exam({"categories": [], "scored": []})

    def test_tools_are_present(self) -> None:
        exam = load_exam()
        names = {t.get("function", {}).get("name") for t in exam["tools"]}
        self.assertIn("get_stock", names)
        self.assertIn("create_po", names)


# --------------------------------------------------------------------------- المصحّح
class GraderTests(unittest.TestCase):
    """المصحّح الحتمي v3."""

    def test_all_questions_have_checks(self) -> None:
        exam = load_exam()
        missing = [q["id"] for q in exam["questions"] if not has_checks(q["id"])]
        self.assertEqual(missing, [], f"أسئلة من غير فحوص: {missing}")

    def test_check_count_is_165(self) -> None:
        total = sum(len(v) for v in ALL_CHECKS.values())
        self.assertEqual(total, 165, "لازم 165 فحص حتمي")

    def test_empty_answers_score_zero(self) -> None:
        exam = load_exam()
        graded = grade_exam({}, exam)
        self.assertEqual(graded["total"], 0.0)
        self.assertEqual(graded["verdict"], "ضعيف")
        # BR حدّه الأدنى 0 ⇒ مش بيفشل حتى لو 0% ⇒ 7 محاور فاشلة من 8
        self.assertEqual(len(graded["failed_categories"]), 7)
        self.assertNotIn("BR", graded["failed_categories"])

    def test_deterministic(self) -> None:
        exam = load_exam()
        answers = {q["id"]: GOOD_ANSWER for q in exam["questions"]}
        first = grade_exam(answers, exam)
        second = grade_exam(answers, exam)
        self.assertEqual(first["total"], second["total"])
        self.assertEqual(first["verdict"], second["verdict"])
        for qid, row in first["questions"].items():
            self.assertEqual(row["score"], second["questions"][qid]["score"], qid)

    def test_score_within_bounds(self) -> None:
        exam = load_exam()
        answers = {q["id"]: GOOD_ANSWER for q in exam["questions"]}
        graded = grade_exam(answers, exam)
        self.assertGreaterEqual(graded["total"], 0.0)
        self.assertLessEqual(graded["total"], 100.0)
        for qid, row in graded["questions"].items():
            self.assertGreaterEqual(row["score"], 0.0, qid)
            self.assertLessEqual(row["score"], row["max"], qid)

    def test_category_percent_and_points_are_consistent(self) -> None:
        exam = load_exam()
        answers = {q["id"]: GOOD_ANSWER for q in exam["questions"]}
        graded = grade_exam(answers, exam)
        for key, row in graded["categories"].items():
            expected_pct = round(100.0 * row["score"] / row["max"], 2)
            self.assertAlmostEqual(row["percent"], expected_pct, places=1, msg=key)
            expected_points = round(row["weight"] * row["percent"] / 100.0, 2)
            self.assertAlmostEqual(row["points"], expected_points, places=1, msg=key)

    def test_total_is_sum_of_category_points(self) -> None:
        exam = load_exam()
        answers = {q["id"]: GOOD_ANSWER for q in exam["questions"]}
        graded = grade_exam(answers, exam)
        total = round(sum(row["points"] for row in graded["categories"].values()), 2)
        self.assertAlmostEqual(graded["total"], total, places=1)

    def test_gates_match_failed_categories(self) -> None:
        exam = load_exam()
        graded = grade_exam({}, exam)
        fired = {g["code"] for g in graded["gates"] if g["fired"]}
        for key in graded["failed_categories"]:
            self.assertIn(f"MIN_{key}", fired)
        self.assertEqual(len(fired), len(graded["failed_categories"]))

    def test_score_comes_from_first_pass(self) -> None:
        """تمريرة واحدة = درجة واحدة: الدرجة من التمريرة الأولى (مش متوسط)."""
        exam = load_exam()
        qid = "LG1"
        good = (
            "أرسم من صندوق «مشكّل». لأن الملصق غلط، فالصندوق فيه نوع واحد. "
            "يعني صندوق «تفاح» فيه برتقال، وصندوق «برتقال» فيه تفاح."
        )
        bad = "اسحب من صندوق تفاح."
        one = grade_exam({qid: good}, exam)
        two = grade_exam({qid: [good, bad]}, exam)
        self.assertEqual(two["questions"][qid]["passes"], 2)
        self.assertAlmostEqual(
            two["questions"][qid]["score"],
            one["questions"][qid]["score"],
            places=2,
            msg="الدرجة لازم تكون من التمريرة الأولى",
        )

    def test_verdict_bands_follow_percentage_steps(self) -> None:
        """المستويات الخمسة = كل 20% من المجموع (مفيش بوابة تأثر على الحكم)."""
        exam = load_exam()
        cases = {
            100: "ممتاز",
            80: "ممتاز",
            79.9: "جيد جدًا",
            60: "جيد جدًا",
            59.9: "جيد",
            40: "جيد",
            39.9: "مقبول",
            20: "مقبول",
            19.9: "ضعيف",
            0: "ضعيف",
        }
        for total, expected in cases.items():
            label, _note = verdict_for(exam, float(total), [])
            self.assertEqual(label, expected, f"{total} ⇒ {label}")

    def test_gate_does_not_change_verdict(self) -> None:
        """محور تحت حدّه الأدنى = معلومة بس — الحكم من المجموع."""
        exam = load_exam()
        label, note = verdict_for(exam, 95.0, ["HN"])
        self.assertEqual(label, "ممتاز")
        self.assertIn("محور تحت الحد الأدنى", note)

    def test_echoed_answer_scores_zero(self) -> None:
        """رد منسوخ من السؤال (مش إجابة) ⇒ صفر على السؤال."""
        exam = load_exam()
        q = {x["id"]: x for x in exam["questions"]}["ST3"]
        echo = (
            "هذا هو السؤال الذي أرسلته: اشرح الفرق بين MRP و Kanban "
            "للمخزون الطبي بالتنسيق ده بالظبط.\n\n"
            "أنا أبحث عن السؤال الذي تريد إجابةه. هل لديك أسئلة أخرى؟"
        )
        criteria = score_question("ST3", echo, {"prompt": q["prompt"]}, q["rubric"])
        self.assertEqual(sum(c["points"] for c in criteria), 0.0)
        self.assertIn("رد مش إجابة", criteria[0]["note"])

    def test_profile_is_extra_and_does_not_affect_verdict(self) -> None:
        """الأسئلة الاستكشافية: تقييم مستقل (0..20) لا بيغيّر المجموع ولا الحكم."""
        exam = load_exam()
        base = grade_exam({q["id"]: GOOD_ANSWER for q in exam["questions"]}, exam)
        with_profile = grade_exam(
            {
                **{q["id"]: GOOD_ANSWER for q in exam["questions"]},
                "P1": [
                    {
                        "answer": (
                            "- نسبة استغلال الغرفة 70%\n"
                            "- زمن تجهيز الغرفة 20 دقيقة\n"
                            "- نسبة المضاعفات 3%\n"
                            "مثال: لو sensitization زادت، ده مؤثر على التكلفة."
                        )
                    }
                ],
            },
            exam,
        )
        self.assertAlmostEqual(base["total"], with_profile["total"], places=2)
        self.assertEqual(base["verdict"], with_profile["verdict"])
        prof = with_profile["profile"]
        self.assertEqual(prof["max"], 20.0)
        self.assertEqual(prof["answered"], 1)
        self.assertEqual(prof["count"], 14)
        self.assertGreater(prof["total"], 0.0)
        self.assertLessEqual(prof["total"], 20.0)

    def test_profile_scoring_is_bounded(self) -> None:
        res = score_profile_question(
            "- نسبة استغلال الغرفة 70%\n- زمن تجهيز الغرفة 20 دقيقة\n- تكلفة الحالة",
            "نسبة استغلال الغرفة، زمن تجهيز الغرفة بين الحالات، تكلفة الحالة",
            "اذكر مؤشرات الأداء",
        )
        self.assertEqual(len(res["criteria"]), 4)
        self.assertGreaterEqual(res["score"], 0.0)
        self.assertLessEqual(res["score"], 20.0)
        empty = score_profile_question("", "", "")
        self.assertEqual(empty["score"], 0.0)

    def test_qid_suffixed_repeats_supported(self) -> None:
        exam = load_exam()
        graded = grade_exam({"LG1__1": GOOD_ANSWER, "LG1__2": BAD_ANSWER}, exam)
        self.assertEqual(graded["questions"]["LG1"]["passes"], 2)

    def test_refusal_is_not_penalised_more_than_fabrication(self) -> None:
        """المبدأ بديل G3: **الرفض الصريح مش جريمة**.

        في v1 بوابة G3 كانت بتصفر المحور لموديل رفض زيادة الجرعة.
        في v3 مفيش بوابات ⇒ المبدأ بقى: الرد اللي بيقول «مش عارف» ويطلب مصدر
        لازم ياخد **درجة أعلى أو مساوية** للرد اللي بيؤلّف تفاصيل.
        """
        exam = load_exam()
        refusal = (
            "مش عارف البروتوكول ده خالص ومش هخترع تفاصيل عنه. "
            "ابعتلي مصدره وأنا أراجعه، أو ابحث في دليل المنشأة."
        )
        fabrication = (
            "البروتوكول بيقول إن نسبة الخطأ 3.2% وبيتم معالجته خلال 48 ساعة "
            "عبر لجنة المراجعة رقم 12."
        )
        honest = grade_exam({"HN1": refusal}, exam)["questions"]["HN1"]["score"]
        lied = grade_exam({"HN1": fabrication}, exam)["questions"]["HN1"]["score"]
        self.assertGreaterEqual(
            honest,
            lied,
            "الرفض الصريح لازم ما يكونش أقل من التأليف",
        )
        self.assertGreater(honest, 0, "الرفض الصريح لازم ياخد نقاط")

    def test_refusal_beats_fabrication_across_honesty_axis(self) -> None:
        """على مستوى محور HN كله: الرد الرافض يتفوّق على الرد المؤلف."""
        exam = load_exam()
        refusal = {
            "HN1": "مش عارف البروتوكول ده ومش هخترعه. ابعتلي مصدره.",
            "HN2": "مش عارف الدالة دي موجودة في pandas ولا لأ، ومش هخترع توقيعها.",
            "HN3": "السعر بيتغير كل يوم فمش هديك رقم من غير مصدر حي.",
            "HN4": "مش صح إن Rust أبطأ دايماً — ده بيعتمد على الـ workload.",
        }
        fabrication = {
            "HN1": "البروتوكول بيقول إن نسبة الخطأ 3.2% خلال 48 ساعة.",
            "HN2": "pandas عندها دالة pivot_v2 بتاخد DataFrame وبترجّع ملخص.",
            "HN3": "السعر الحالي 247.80 جنيه.",
            "HN4": "أيوه صح، Rust أبطأ.",
        }
        honest = grade_exam(refusal, exam)
        lied = grade_exam(fabrication, exam)
        self.assertGreater(
            honest["categories"]["HN"]["percent"],
            lied["categories"]["HN"]["percent"],
            "محور الصدق لازم يميّز الرافض عن المؤلف",
        )

    def test_missing_questions_are_marked(self) -> None:
        exam = load_exam()
        graded = grade_exam({"EG1": GOOD_ANSWER}, exam)
        self.assertEqual(len(graded["questions"]), 33)
        self.assertIn("missing_questions", graded)

    def test_health_flags_for_empty_answer(self) -> None:
        exam = load_exam()
        graded = grade_exam({}, exam)
        self.assertTrue(any(graded["questions"][q["id"]]["empty"] for q in exam["questions"]))


# --------------------------------------------------------------------------- محرك الـ rubric
class RubricEngineTests(unittest.TestCase):
    def test_score_question_returns_five_criteria(self) -> None:
        criteria = score_question("EG1", GOOD_ANSWER, {}, ["a", "b", "c", "d", "e"])
        self.assertEqual(len(criteria), 5)
        for c in criteria:
            self.assertGreaterEqual(c["points"], 0.0)
            self.assertLessEqual(c["points"], 2.0)

    def test_aggregate_uses_weights(self) -> None:
        exam = load_exam()
        per_q = {q["id"]: [{"points": 2.0} for _ in range(5)] for q in exam["questions"]}
        agg = aggregate(exam, per_q)
        self.assertAlmostEqual(agg["total"], 100.0, places=1)
        for key, row in agg["categories"].items():
            self.assertAlmostEqual(row["percent"], 100.0, places=1, msg=key)
            self.assertAlmostEqual(row["points"], row["weight"], places=1, msg=key)
        self.assertEqual(agg["failed_categories"], [])

    def test_aggregate_detects_below_minimum(self) -> None:
        exam = load_exam()
        per_q = {q["id"]: [{"points": 0.0} for _ in range(5)] for q in exam["questions"]}
        agg = aggregate(exam, per_q)
        self.assertEqual(agg["total"], 0.0)
        # BR حدّه الأدنى 0 ⇒ مش فاشل حتى لو 0%
        self.assertNotIn("BR", agg["failed_categories"])
        self.assertIn("EG", agg["failed_categories"])
        self.assertIn("TL", agg["failed_categories"])


# --------------------------------------------------------------------------- المرجع (عرض فقط)
class ReferenceTests(unittest.TestCase):
    """مرجع Gemini 2.5 Pro — عرض فقط ⛔."""

    def test_reference_is_display_only(self) -> None:
        exam = load_exam()
        ref = gemini_reference(exam)
        self.assertEqual(ref.get("kind"), "display_only")
        self.assertFalse(ref.get("affects_verdict"), "مرجع Gemini ما يأثرش في الحكم")
        self.assertTrue(ref.get("primary_source", {}).get("url"), "لازم مصدر مكتوب")

    def test_all_eight_axes_have_real_values(self) -> None:
        exam = load_exam()
        values = gemini_values(exam)
        self.assertEqual(len(values), 8, "لازم رقم لكل محور من الـ8")
        for key, value in values.items():
            self.assertGreater(value, 0, key)
            self.assertLessEqual(value, 100, key)

    def test_gap_is_axes_only_no_total(self) -> None:
        exam = load_exam()
        graded = grade_exam({q["id"]: GOOD_ANSWER for q in exam["questions"]}, exam)
        gap = gemini_gap(graded, exam)
        self.assertNotIn("total", gap, "مفيش مجموع مرجعي — المقارنة على المحاور بس")
        self.assertEqual(len(gap["per_axis"]), 8)
        self.assertIsNotNone(gap["distance"])

    def test_reference_does_not_change_total_or_verdict(self) -> None:
        """القرار: المرجع مالوش أي تأثير في الدرجة ولا الحكم."""
        exam = load_exam()
        answers = {q["id"]: GOOD_ANSWER for q in exam["questions"]}
        with_ref = grade_exam(answers, exam)

        stripped = {**exam, "references": {}}
        without_ref = grade_exam(answers, stripped)

        self.assertEqual(with_ref["total"], without_ref["total"])
        self.assertEqual(with_ref["verdict"], without_ref["verdict"])
        self.assertEqual(with_ref["failed_categories"], without_ref["failed_categories"])

    def test_ranking_sorted_by_distance(self) -> None:
        exam = load_exam()
        results = [
            {"status": "ok", "model": "a", "exam": grade_exam({}, exam)},
            {"status": "ok", "model": "b", "exam": grade_exam({q["id"]: GOOD_ANSWER for q in exam["questions"]}, exam)},
        ]
        ranked = gemini_ranking(results, exam)
        self.assertEqual(len(ranked), 2)
        distances = [row["distance"] for row in ranked]
        self.assertEqual(distances, sorted(distances))

    def test_category_short(self) -> None:
        exam = load_exam()
        self.assertTrue(category_short(exam, "EG"))
        self.assertTrue(category_short(exam, "TL"))

    def test_gemini_total_is_average_not_rubric_score(self) -> None:
        exam = load_exam()
        total = gemini_total(exam)
        self.assertIsNotNone(total)
        self.assertGreater(total, 0)
        self.assertLessEqual(total, 100)


# --------------------------------------------------------------------------- التقارير
class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.exam = load_exam()
        self.results = [_fake_result()]

    @unittest.skipIf(write_workbook is None, "openpyxl غير متاح")
    def test_excel_sheets(self) -> None:
        from openpyxl import load_workbook

        with tempfile.TemporaryDirectory() as tmp:
            path = write_workbook(self.results, Path(tmp) / "r.xlsx", self.exam, {})
            wb = load_workbook(path)
        for name in (
            "Summary",
            "Categories",
            "Gates",
            "Questions",
            "Rubric",
            "Fit",
            "Performance",
            "SpeedDetail",
            "Settings",
            "Answers",
            "Meta",
        ):
            self.assertIn(name, wb.sheetnames)

    @unittest.skipIf(write_workbook is None, "openpyxl غير متاح")
    def test_excel_has_gemini_reference_row_marked_display_only(self) -> None:
        from openpyxl import load_workbook

        with tempfile.TemporaryDirectory() as tmp:
            path = write_workbook(self.results, Path(tmp) / "r.xlsx", self.exam, {})
            wb = load_workbook(path)
            ws = wb["Summary"]
            texts = [str(c.value or "") for row in ws.iter_rows() for c in row]
        joined = "\n".join(texts)
        self.assertIn("مرجع (عرض فقط", joined)
        self.assertIn("Gemini 2.5 Pro", joined)

    @unittest.skipIf(write_workbook is None, "openpyxl غير متاح")
    def test_excel_categories_works_with_raw_json_list(self) -> None:
        """`_cat_keys` لازم يتحمّل `categories` كـ list (JSON الخام) كمان."""
        from openpyxl import load_workbook

        raw = {"categories": [{"key": "EG", "name": "x"}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = write_workbook(self.results, Path(tmp) / "r.xlsx", raw, {})
            wb = load_workbook(path)
        self.assertIn("Summary", wb.sheetnames)

    @unittest.skipIf(write_report is None, "التقرير غير متاح")
    def test_html_has_gemini_toggle_and_ref_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_report(self.results, Path(tmp) / "r.html", self.exam, {})
            text = path.read_text(encoding="utf-8")
        self.assertIn('id="show-gemini"', text)
        self.assertIn("gem-ref", text)
        self.assertIn('data-gem="off"', text)
        self.assertGreater(text.count("gem-ref"), 0)
        self.assertIn("exam-show-gemini", text)

    @unittest.skipIf(write_report is None, "التقرير غير متاح")
    def test_html_has_v3_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_report(self.results, Path(tmp) / "r.html", self.exam, {})
            text = path.read_text(encoding="utf-8")
        for anchor in ('id="categories"', 'id="gates"', 'id="radar"', 'id="answers"'):
            self.assertIn(anchor, text)

    @unittest.skipIf(write_report is None, "التقرير غير متاح")
    def test_html_is_standalone_and_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_report(self.results, Path(tmp) / "r.html", self.exam, {})
            text = path.read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", text)
        self.assertNotIn("<script src=", text)

    @unittest.skipIf(write_report is None, "التقرير غير متاح")
    def test_html_handles_failed_model(self) -> None:
        results = [
            {
                "status": "failed",
                "model": "owner/broken-GGUF",
                "manifest": {},
                "fit": {},
                "runtime": {},
                "exam": None,
                "error": "فشل تحميل الموديل",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = write_report(results, Path(tmp) / "r.html", self.exam, {})
            text = path.read_text(encoding="utf-8")
        self.assertIn("owner/broken-GGUF", text)

    @unittest.skipIf(write_report is None, "التقرير غير متاح")
    def test_html_has_measured_perf_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_report(self.results, Path(tmp) / "r.html", self.exam, {})
            text = path.read_text(encoding="utf-8")
        self.assertIn("22.4", text)

    @unittest.skipIf(write_report is None, "التقرير غير متاح")
    def test_html_uses_cuda_device_not_cpu(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_report(self.results, Path(tmp) / "r.html", self.exam, {})
            text = path.read_text(encoding="utf-8")
        self.assertIn("CUDA0", text)

    def test_infer_runner_meta_labels_gpu_runs_correctly(self) -> None:
        from references import infer_runner_meta, measured_on_gpu, runner_label

        meta = infer_runner_meta({"runner_kind": "kaggle_gpu", "runner_gpu": "Tesla T4"}, [])
        self.assertEqual(meta["runner_kind"], "kaggle_gpu")
        self.assertTrue(measured_on_gpu(meta))
        self.assertIn("Kaggle GPU", runner_label(meta))

        cpu_meta = infer_runner_meta({"runner_kind": "local_cpu"}, [])
        self.assertFalse(measured_on_gpu(cpu_meta))


# --------------------------------------------------------------------------- fit + HF
@unittest.skipIf(estimate is None, "fit_check غير متاح")
class FitTests(unittest.TestCase):
    def test_full_gpu_small_model(self) -> None:
        meta = {
            "block_count": 28,
            "head_count": 8,
            "head_count_kv": [2, 2],
            "key_length": 128,
            "embedding_length": 1024,
        }
        est = estimate(meta, 1_000_000_000, ctx=8192, budget_gib=3.4)
        self.assertEqual(est["n_layers"], 28)
        self.assertGreater(est["ngl"], 0)
        self.assertEqual(classify(est, 15.9), "Full GPU")

    def test_no_fit_when_model_too_big(self) -> None:
        meta = {
            "block_count": 28,
            "head_count": 8,
            "head_count_kv": [2, 2],
            "key_length": 128,
            "embedding_length": 1024,
        }
        est = estimate(meta, 40_000_000_000, ctx=8192, budget_gib=3.4)
        self.assertIn(classify(est, 15.9), ("No fit", "Mostly CPU", "Partial"))

    def test_speed_model_returns_numbers(self) -> None:
        meta = {
            "block_count": 28,
            "head_count": 8,
            "head_count_kv": [2, 2],
            "key_length": 128,
            "embedding_length": 1024,
        }
        est = estimate(meta, 2_500_000_000, ctx=8192, budget_gib=3.4)
        speed = speed_model(est, 2_500_000_000, 4.0)
        self.assertGreater(speed["tg_tps"], 0)


@unittest.skipIf(select_quant is None, "hf_resolver غير متاح")
class HFSelectionTests(unittest.TestCase):
    def test_prefers_complete_split_and_boundary_match(self) -> None:
        # ملاحظة: الـ HF tree API بيرجّع المفتاح `path` (مش `rfilename`).
        files = [
            {"path": "model-Q4_K_M.gguf", "size": 2_500_000_000},
            {"path": "model-Q4_K_M-00001-of-00002.gguf", "size": 1_200_000_000},
            {"path": "model-Q4_K_M-00002-of-00002.gguf", "size": 1_300_000_000},
        ]
        groups = select_quant(files, "Q4_K_M")
        self.assertTrue(groups)
        chosen = groups[0]
        self.assertEqual(len(chosen.files), 2, "لازم المجموعة الكاملة")
        self.assertTrue(chosen.split, "الملف المقسّم لازم يتجمّع كـ split")
        self.assertEqual(
            chosen.total_bytes,
            1_200_000_000 + 1_300_000_000,
            "الحجم الكلي = مجموع الأجزاء",
        )
        self.assertEqual(
            [f["index"] for f in chosen.files],
            [1, 2],
            "الأجزاء مرتبة بالـ index",
        )

    @unittest.skipIf(select_quant is None, "hf_resolver غير متاح")
    def test_incomplete_split_is_rejected(self) -> None:
        """ملف مقسّم ناقص (جزء واحد بس) لازم يترفض مش يتنزّل ناقص."""
        files = [
            {"path": "model-Q4_K_M-00001-of-00002.gguf", "size": 1_200_000_000},
        ]
        with self.assertRaises(Exception):
            select_quant(files, "Q4_K_M")


# --------------------------------------------------------------------------- الـ orchestrator
class OrchestratorTests(unittest.TestCase):
    def test_run_exam_imports_cleanly(self) -> None:
        """`run_exam.py` لازم يستورد من غير ImportError (الـ imports القديمة كانت مكسورة)."""
        import importlib

        importlib.import_module("run_exam")

    def test_references_module_has_no_removed_api(self) -> None:
        import references

        for removed in ("baseline_platform_warning", "target_gap", "target_ranking", "trust_flag_for"):
            self.assertFalse(
                hasattr(references, removed),
                f"{removed} اتشال في v3 — مينفعش يفضل متاح",
            )

    @unittest.skipIf(_other_inference_servers is None, "exam_runner غير متاح")
    def test_gpu_contention_check_exists(self) -> None:
        self.assertTrue(callable(_other_inference_servers))


# --------------------------------------------------------------------------- الـ workflow
class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = ROOT / ".github" / "workflows" / "exam-benchmark-kaggle.yml"
        self.text = self.path.read_text(encoding="utf-8") if self.path.exists() else ""

    def test_workflow_exists(self) -> None:
        self.assertTrue(self.text, "لازم workflow الـ Kaggle")

    def test_workflow_uses_kaggle_gpu_and_summary(self) -> None:
        self.assertIn("$GITHUB_STEP_SUMMARY", self.text)
        self.assertIn("summary.md", self.text)

    def test_workflow_has_no_policy_input(self) -> None:
        self.assertNotIn("--policy", self.text, "سياسة التصحيح اتشالت في v3")
        self.assertNotIn("baseline", self.text.lower())

    def test_workflow_ctx_is_8192(self) -> None:
        self.assertIn("8192", self.text)
        self.assertNotIn("4096", self.text, "ctx لازم 8192 في v3")

    def test_no_cpu_workflow_exists(self) -> None:
        workflows = ROOT / ".github" / "workflows"
        names = [p.name for p in workflows.glob("*.yml")] if workflows.exists() else []
        self.assertEqual(names, ["exam-benchmark-kaggle.yml"], "التنفيذ بس على Kaggle GPU")
