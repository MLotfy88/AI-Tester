/* ══════════ 01 · CORE — البيانات والـhelpers ══════════ */
"use strict";

const DATA = JSON.parse(document.getElementById("payload").textContent);
const MODELS = DATA.models;
const CFG = DATA.cfg;

const COLORS = ["#5AA9FF", "#35D6C0", "#A78BFA", "#FF8FA3", "#6EE7B7", "#F5C45E", "#38BDF8", "#E879F9", "#94A3B8", "#FACC15"];
/* حالة المرجع كـ attribute (مرجع عرض فقط — مش بيشارك في الدرجة ولا الحكم) */
const GEM_ATTR = { on: 'data-gem="on"', off: 'data-gem="off"' };
const VERDICT_BANDS = [
  { min: 80, label: "ممتاز",    cls: "v4" },
  { min: 60, label: "جيد جدًا", cls: "v3" },
  { min: 40, label: "جيد",      cls: "v2" },
  { min: 20, label: "مقبول",    cls: "v1" },
  { min: 0,  label: "ضعيف",     cls: "v0" },
];

const state = {
  visible: new Set(MODELS.map(m => m.key)),
  focus: MODELS[0].key,
  extraFocus: MODELS[0].key,
  cat: null,
  q: "",
  refVisible: true,
  /* موديلات الرسم السداسي (تحكّم مستقل عن باقي التقرير) */
  radar: new Set(MODELS.map(m => m.key)),
  /* ملف الأسئلة: فلترة الحالة · الترتيب · المحاور المطوية · الأسئلة المفتوحة */
  flag: "all",
  sort: "axis",
  collapsed: new Set(),
  expanded: new Set(),
};

/* المرجع: Gemini 2.5 Pro — عرض فقط، مش بيشارك في أي حكم */
const REF = DATA.ref ? {
  key: "__ref__",
  name: DATA.ref.name,
  total: DATA.ref.total,
  color: DATA.ref.color || "#9BB0D4",
  isRef: true,
  verdict: "مرجع",
  repo: DATA.ref.source || "",
  cats: Object.fromEntries(
    Object.entries(DATA.ref.axes || {}).map(([k, v]) => [k, { percent: v, failed_min: false, points: 0 }])
  ),
  questions: {},
  profile: { answered: 0, count: 0, total: 0, max: 20, percent: 0, questions: {} },
  perf: null,
  fit: {},
  runtime: {},
} : null;

/* كل ما يظهر في المقارنات: الموديلات + المرجع (لو ظاهر) */
const SHOWN = () => (REF && state.refVisible ? MODELS.concat([REF]) : MODELS);

/* ── helpers ─────────────────────────────── */
const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const ESC_MAP = {};
ESC_MAP[38] = "&amp;";
ESC_MAP[60] = "&lt;";
ESC_MAP[62] = "&gt;";
ESC_MAP[34] = "&quot;";
ESC_MAP[39] = "&#39;";
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ESC_MAP[c.charCodeAt(0)]);
const num = (v, d = 1) => (v === null || v === undefined || Number.isNaN(Number(v)))
  ? "—" : Number(v).toFixed(d).replace(/\.0+$/, "");
const pct = (v, d = 1) => (v === null || v === undefined) ? "—" : num(v, d) + "%";
const byId = k => MODELS.find(m => m.key === k) || MODELS[0];
const colorOf = k => byId(k).color;
const modelByKey = k => MODELS.find(m => m.key === k);

function bandFor(score) {
  return VERDICT_BANDS.find(b => score >= b.min) || VERDICT_BANDS[VERDICT_BANDS.length - 1];
}
function scoreColor(p) {           /* 0..100 → تدرّج بارد */
  if (p >= 80) return "#5AA9FF";
  if (p >= 60) return "#79B6FF";
  if (p >= 40) return "#8FB6D8";
  if (p >= 20) return "#8FA3C8";
  return "#FF6B81";
}
function fmtBytes(b) {
  if (!b) return "—";
  const u = ["B", "KiB", "MiB", "GiB", "TiB"];
  let i = 0, v = b;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v < 10 && i > 1 ? 2 : 1)} ${u[i]}`;
}
function fmtDur(s) {
  if (s === null || s === undefined) return "—";
  if (s < 90) return `${num(s, 0)} ث`;
  return `${num(s / 60, 1)} د`;
}
function shortModel(name) {
  return String(name || "").replace(/-(GGUF|gguf)$/, "").replace(/__/g, " · ");
}

/* ══════════ TOP BAR ══════════ */
function renderTop() {
  const r = DATA.run;
  const items = [
    ["run", r.run_id],
    ["البيئة", r.runner_label || "—"],
    ["الإعدادات", `temp ${r.temperature} · top_p ${r.top_p} · seed ${r.seed} · ctx ${r.ctx}`],
    ["المدة", fmtDur(r.seconds_total || 0)],
    ["عدد الطلبات", r.requests_count || "—"],
  ];
  $("#topMeta").innerHTML = items.map(([k, v]) =>
    `<div class="tm"><div class="tm-k">${esc(k)}</div><div class="tm-v" title="${esc(v)}">${esc(v)}</div></div>`
  ).join("");

  const btn = $("#show-gemini");
  if (btn && REF) {
    btn.textContent = state.refVisible ? "🎯 المرجع ظاهر" : "🎯 المرجع مخفي";
    btn.classList.toggle("off", !state.refVisible);
    btn.setAttribute("data-gem", state.refVisible ? "on" : "off");
    btn.title = `Gemini 2.5 Pro — ${num(REF.total, 2)}/100 (عرض فقط، مش بيشارك في الحكم)`;
  }
}

/* ══════════ HERO ══════════ */
function renderHero() {
  const r = DATA.run;
  const eb = $("#heroEyebrow");
  if (eb) eb.textContent = `امتحان المساعد المصري${r.exam_version ? " · " + r.exam_version : ""}`;
  const best = MODELS[0];
  const answered = MODELS.reduce((s, m) => s + (m.profile?.answered || 0), 0);
  const totalQ = MODELS.reduce((s, m) => s + (m.questions ? Object.keys(m.questions).length : 0), 0);

  const stats = [
    ["الموديلات", MODELS.length, "نموذج"],
    ["أسئلة مصحَّحة", Object.keys(best.questions || {}).length, "سؤال"],
    ["محاور", Object.keys(CFG.categories || {}).length, "محور بأوزان"],
    ["أسئلة استكشافية", CFG.profile_count || 14, "ميزة إضافية"],
    ["طلبات", r.requests_count || "—", "نداء للموديل"],
    ["أعلى نتيجة", num(best.total, 2), best.verdict],
  ];
  $("#heroStats").innerHTML = stats.map(([k, v, sub]) =>
    `<div class="stat"><div class="stat-k">${esc(k)}</div>
       <div class="stat-v">${esc(v)} <small>${esc(sub)}</small></div></div>`
  ).join("");
}

/* ══════════ 01 · مقياس الحكم ══════════ */
/* الشرائح بترتيب تصاعدي: 0 على اليمين (بداية القراءة) ⇒ 100 على اليسار */
const SCALE_BANDS = [
  { min: 0,  max: 20,  label: "ضعيف",    cls: "v0" },
  { min: 20, max: 40,  label: "مقبول",   cls: "v1" },
  { min: 40, max: 60,  label: "جيد",     cls: "v2" },
  { min: 60, max: 80,  label: "جيد جدًا", cls: "v3" },
  { min: 80, max: 100, label: "ممتاز",   cls: "v4" },
];

function renderScale() {
  const host = $("#scaleWrap");
  const zones = SCALE_BANDS.map(b =>
    `<div class="zone ${b.cls}" style="width:${b.max - b.min}%">
       <span>${esc(b.label)}</span><b>${b.min}–${b.max}</b>
     </div>`
  ).join("");

  let needles = MODELS.map((m, i) => {
    const up = i % 2 === 0;
    const dim = state.visible.has(m.key) ? "" : " dim";
    const nm = shortModel(m.name);
    const label = nm.length > 20 ? nm.slice(0, 19) + "…" : nm;
    return `
      <div class="needle${dim}" style="inset-inline-start:${m.total}%;color:${m.color}"></div>
      <div class="needle-label ${up ? "nl-up" : "nl-dn"}" style="inset-inline-start:${m.total}%;color:${m.color};${dim ? "opacity:.42" : ""}">
        <span class="nl-name">${esc(label)}</span>
        <span class="nl-score">${num(m.total, 2)}</span>
      </div>`;
  }).join("");

  if (REF && state.refVisible) {
    needles += `
      <div class="needle ref" style="inset-inline-start:${REF.total}%;color:${REF.color}"></div>
      <div class="needle-label nl-dn" style="inset-inline-start:${REF.total}%;color:${REF.color}">
        <span class="nl-name">${esc(REF.name)}</span>
        <span class="nl-score">${num(REF.total, 2)}</span>
      </div>`;
  }

  const marks = [0, 20, 40, 60, 80, 100].map(v =>
    `<span>${v}</span>`).join("");

  host.innerHTML = `
    <div class="scale-stack">
      <div class="scale-track">${zones}</div>
      <div class="scale-labels">${needles}</div>
    </div>
    <div class="scale-marks">${marks}</div>
    <div class="scale-legend">
      <span>الحكم من <b class="mono">المجموع النهائي /100</b> فقط</span>
      <span>⛔ محور تحت حدّه الأدنى = معلومة، مش بيغيّر الحكم</span>
      <span>مرجع Gemini = عرض فقط</span>
    </div>`;
}
