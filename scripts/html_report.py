"""تقرير HTML «مِحْيَر» — ملف واحد مستقل (RTL) لمقارنة موديلات GGUF.

التصميم الجديد بالكامل (ثيم بارد + خط Cairo + مرجع Gemini + رادار بتحكّم مستقل
+ ملف أسئلة بفلترة وترتيب وطيّ/فرد) بدل التصميم القديم.

- **ملف واحد بدون اعتماد خارجي**: CSS + JS + البيانات متضمّنة جوه الـ HTML.
  خط Cairo بيتحمّل من Google لو فيه إنترنت، والتقرير بيرجع لخط النظام لو مفيش.
- **كل الأرقام مقيسة**: مبنية من نتائج التشغيل في الذاكرة — مفيش أرقام تقديرية.
- **مرجع Gemini 2.5 Pro عرض فقط ⛔**: مالوش أي تأثير في الدرجة ولا في الحكم.
  درجته المحسوبة = مجموع(نسبة المحور × وزنه) — نفس طريقة المجموع الأساسي.
- **الحكم من المجموع النهائي فقط** (كل 20%): ممتاز ≥80 · جيد جدًا ≥60 · جيد ≥40 ·
  مقبول ≥20 · ضعيف <20. ومحور تحت الحد الأدنى = معلومة ⛔ بس (مش بيفرض مستوى).
- **الأسئلة الاستكشافية (P1..P14)**: تقييم مستقل من 20، بره المجموع والحكم.

ملاحظة: الملف ده **مولّد** — مصدر التصميم هو `design-preview/assets/`، و
`design-preview/sync_to_tool.py` بيحدّث `scripts/html_report.py` من Design.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common import dump_json_for_html, now_iso
from references import category_short, infer_runner_meta, runner_label

#: ألوان الموديلات في الرسوم (نفس ترتيب `design-preview/assets/js/01-core.js`).
COLORS = ["#5AA9FF", "#35D6C0", "#A78BFA", "#FF8FA3", "#6EE7B7", "#F5C45E", "#38BDF8", "#E879F9", "#94A3B8", "#FACC15"]

# ═════════════════════════════════════════════════════════ CSS / JS / HTML
# الثوابت دي (CSS/JS/TEMPLATE) بتتستبدل وقت التوليد — design-preview/sync_to_tool.py.
# أمّا `__CSS__`/`__JS__`/`__DATA__` جوه الـ TEMPLATE فدي تتستبدل وقت build_html.
CSS = r"""/* ═══════════════════════════════════════════════════════════════
   مِحْيَر — هوية بصرية جديدة لتقرير الامتحان
   داكنة دافية · أرقام monospace · خطوط رفيعة · إيقاع editorial
   ═══════════════════════════════════════════════════════════════ */

:root{
  --ink:#070A12;
  --ink-2:#0B0F19;
  --panel:rgba(150,180,255,.035);
  --panel-2:rgba(150,180,255,.06);
  --line:rgba(190,210,255,.11);
  --line-2:rgba(190,210,255,.20);
  --bone:#FFFFFF;
  --bone-dim:#E9EFFA;
  --muted:#D2DBEA;
  --faint:#BAC5D8;

  --primary:#5AA9FF;
  --aqua:#35D6C0;
  --danger:#FF6B81;
  --violet:#A78BFA;
  --sky:#8AB4FF;
  --ok:#4ADE80;

  --r-sm:8px; --r:14px; --r-lg:20px;
  --mono:"JetBrains Mono","SFMono-Regular",Consolas,monospace;
  --sans:"Cairo","Almarai","Segoe UI",Tahoma,system-ui,sans-serif;
  --maxw:1440px;
}

*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;background:var(--ink);color:var(--bone);
  font-family:var(--sans);font-size:15px;line-height:1.75;
  -webkit-font-smoothing:antialiased;
  background-image:
    radial-gradient(1200px 680px at 90% -10%,rgba(90,169,255,.13),transparent 62%),
    radial-gradient(950px 560px at 2% 14%,rgba(53,214,192,.07),transparent 62%);
  background-attachment:fixed;
}
::selection{background:rgba(242,166,90,.28)}

/* حبيبات ناعمة */
.grain{
  position:fixed;inset:0;pointer-events:none;z-index:1;opacity:.035;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='140' height='140'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3'/></filter><rect width='140' height='140' filter='url(%23n)'/></svg>");
}

/* ── util ───────────────────────────────────────────────── */
main{position:relative;z-index:2;max-width:var(--maxw);margin:0 auto;padding:0 clamp(16px,3vw,44px) 80px}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums;letter-spacing:-.02em}
b,strong{font-weight:600;color:#fff}
h1,h2,h3,h4{margin:0;font-weight:600;letter-spacing:-.01em}
p{margin:0}
button{font-family:inherit}

/* ══════════════ TOP BAR ══════════════ */
.topbar{
  position:sticky;top:0;z-index:50;
  display:flex;align-items:center;gap:24px;
  padding:12px clamp(16px,3vw,44px);
  background:rgba(11,10,9,.82);
  backdrop-filter:blur(18px) saturate(140%);
  border-bottom:1px solid var(--line);
}
.brand{display:flex;align-items:center;gap:12px;flex:0 0 auto}
.brand-mark{
  width:26px;height:26px;border-radius:8px;flex:0 0 auto;
  background:conic-gradient(from 210deg,var(--primary),var(--aqua),var(--violet),var(--sky),var(--primary));
  box-shadow:0 0 0 1px rgba(255,255,255,.14),0 6px 22px -8px rgba(90,169,255,.8);
}
.brand-name{font-weight:700;font-size:15px;line-height:1.2;letter-spacing:.02em}
.brand-sub{font-size:12px;color:var(--faint);line-height:1.3}
.topbar-meta{display:flex;gap:20px;flex-wrap:wrap;flex:1 1 auto;min-width:0}
.tm{display:flex;flex-direction:column;line-height:1.35;min-width:0}
.tm-k{font-size:11.5px;color:var(--faint);letter-spacing:.06em;text-transform:uppercase}
.tm-v{font-size:13.5px;color:var(--bone-dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.topbar-actions{display:flex;align-items:center;gap:12px;flex:0 0 auto}
.legend-chip{display:flex;align-items:center;gap:7px;font-size:12.5px;color:var(--muted)}
.sw{width:9px;height:9px;border-radius:3px;display:inline-block}
.sw-gate{background:var(--danger);box-shadow:0 0 10px -2px var(--danger)}
.sw-extra{background:transparent;border:1px dashed var(--violet)}
.btn-ghost{
  background:transparent;border:1px solid var(--line-2);color:var(--bone-dim);
  padding:7px 14px;border-radius:99px;font-size:12px;cursor:pointer;transition:.18s;
}
.btn-ghost:hover{border-color:var(--primary);color:var(--primary);background:rgba(242,166,90,.07)}

/* ══════════════ HERO ══════════════ */
.hero{
  display:grid;grid-template-columns:1.55fr .95fr;gap:clamp(24px,4vw,64px);
  align-items:end;padding:clamp(38px,6vw,78px) 0 clamp(26px,3.5vw,46px);
}
.eyebrow{
  font-family:var(--mono);font-size:12px;letter-spacing:.22em;text-transform:uppercase;
  color:var(--primary);margin-bottom:16px;
}
.hero-title{
  font-size:clamp(38px,6.4vw,76px);line-height:1.02;font-weight:700;letter-spacing:-.03em;
  margin-bottom:20px;
}
.hero-title em{
  font-style:normal;
  background:linear-gradient(105deg,var(--primary),var(--aqua) 52%,var(--violet));
  -webkit-background-clip:text;background-clip:text;color:transparent;
}
.hero-lede{max-width:58ch;color:var(--bone-dim);font-size:16px}
.hero-stats{display:flex;flex-wrap:wrap;gap:10px;margin-top:28px}
.stat{
  border:1px solid var(--line);border-radius:var(--r);padding:10px 16px;
  background:var(--panel);min-width:118px;
}
.stat-k{font-size:11.5px;color:var(--faint);letter-spacing:.05em}
.stat-v{font-family:var(--mono);font-size:21px;font-weight:500;line-height:1.35;color:var(--bone)}
.stat-v small{font-size:11px;color:var(--muted);font-family:var(--sans)}

.hero-note{
  border:1px solid var(--line);border-radius:var(--r-lg);padding:22px 24px;
  background:linear-gradient(180deg,rgba(255,255,255,.035),rgba(255,255,255,.008));
}
.note-label{
  font-family:var(--mono);font-size:11.5px;letter-spacing:.18em;text-transform:uppercase;
  color:var(--faint);margin-bottom:14px;
}
.note-list{margin:0;padding-inline-start:20px;color:var(--bone-dim);font-size:14.5px}
.note-list li{margin-bottom:9px}
.note-list li:last-child{margin-bottom:0}

/* ══════════════ PANEL ══════════════ */
.panel{
  border-top:1px solid var(--line);
  padding:clamp(30px,4vw,52px) 0;
}
.panel-head{display:flex;align-items:baseline;gap:18px;flex-wrap:wrap;margin-bottom:26px}
.panel-head h2{font-size:clamp(20px,2.3vw,28px);display:flex;align-items:baseline;gap:12px}
.pn{
  font-family:var(--mono);font-size:12px;color:var(--primary);
  border:1px solid rgba(242,166,90,.3);border-radius:6px;padding:2px 7px;letter-spacing:.1em;
}
.panel-sub{color:var(--muted);font-size:14px;flex:1 1 260px}
.panel-extra{
  position:relative;
  margin-inline:-1px;padding-inline:clamp(18px,2.4vw,30px);
  border:1px dashed rgba(179,155,232,.3);border-radius:var(--r-lg);
  background:
    radial-gradient(700px 260px at 90% 0%,rgba(179,155,232,.09),transparent 70%),
    rgba(179,155,232,.022);
  margin-top:8px;
}

/* ══════════════ 01 · SCALE ══════════════ */
.scale-wrap{position:relative;padding-top:54px}
.scale-stack{position:relative}
.scale-track{
  position:relative;height:78px;border-radius:12px;overflow:hidden;
  border:1px solid var(--line-2);
  display:flex;background:#080B14;
}
.scale-labels{position:absolute;inset:0;pointer-events:none;z-index:4}
.zone{
  position:relative;display:flex;align-items:flex-end;justify-content:center;
  padding-bottom:9px;font-size:11px;color:rgba(233,238,249,.55);
  border-inline-start:1px solid rgba(11,10,9,.55);
}
.zone:first-child{border-inline-start:0}
.zone b{display:block;font-family:var(--mono);font-size:11.5px;color:rgba(233,238,249,.72);font-weight:400}
.zone.z0{background:rgba(255,107,129,.16)}
.zone.z1{background:rgba(185,205,240,.06)}
.zone.z2{background:rgba(53,214,192,.14)}
.zone.z3{background:rgba(90,169,255,.17)}
.zone.z4{background:rgba(90,169,255,.34);color:var(--bone)}
.zone.z4 b{color:rgba(255,255,255,.88)}
.needle{
  position:absolute;top:0;bottom:0;width:2px;z-index:3;
  background:currentColor;box-shadow:0 0 14px 1px currentColor;
}
.needle::after{
  content:"";position:absolute;top:-5px;left:50%;transform:translateX(-50%) rotate(45deg);
  width:8px;height:8px;background:currentColor;border-radius:2px;
}
.needle.dim{opacity:.42;box-shadow:none}
.needle-label{
  position:absolute;z-index:4;transform:translateX(50%);
  display:flex;flex-direction:column;align-items:center;gap:2px;white-space:nowrap;
  font-size:12px;
}
.needle-label .nl-name{font-weight:600;max-width:150px;overflow:hidden;text-overflow:ellipsis}
.needle-label .nl-score{font-family:var(--mono);font-size:11.5px;opacity:.8}
.nl-up{bottom:calc(100% + 9px)}
.nl-dn{top:calc(100% + 9px)}
.scale-marks{display:flex;justify-content:space-between;margin-top:52px;font-family:var(--mono);font-size:12px;color:var(--faint)}
.scale-legend{display:flex;gap:22px;flex-wrap:wrap;margin-top:16px;font-size:12px;color:var(--muted)}

/* ══════════════ 02 · SPEC CARDS ══════════════ */
.spec-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:16px}
.spec-card{
  position:relative;border:1px solid var(--line);border-radius:var(--r-lg);
  padding:20px 20px 18px;background:var(--panel);cursor:pointer;
  transition:transform .22s cubic-bezier(.2,.7,.3,1),border-color .22s,background .22s;
  overflow:hidden;
}
.spec-card::before{
  content:"";position:absolute;inset-inline:0;top:0;height:2px;
  background:linear-gradient(90deg,transparent,var(--c),transparent);
  opacity:.55;transition:opacity .22s;
}
.spec-card:hover{transform:translateY(-3px);border-color:var(--line-2);background:var(--panel-2)}
.spec-card.focus{border-color:var(--c);background:rgba(150,180,255,.06)}
.spec-card.focus::before{opacity:1}
.spec-card.muted{opacity:.42;filter:saturate(.4)}
.sc-top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:16px}
.sc-top-right{display:flex;align-items:center;gap:8px;flex:0 0 auto}
.sc-eye{
  width:28px;height:28px;border-radius:50%;border:1px solid var(--line);
  background:transparent;color:var(--c);cursor:pointer;font-size:12px;line-height:1;
  display:inline-flex;align-items:center;justify-content:center;transition:.16s;padding:0;
}
.sc-eye:hover{border-color:var(--c);box-shadow:0 0 0 3px color-mix(in srgb,var(--c) 18%,transparent)}
.sc-eye.off{color:var(--faint);border-color:var(--line);opacity:.6}
.sc-name{font-weight:600;font-size:14.5px;line-height:1.35;word-break:break-word}
.sc-repo{font-size:12px;color:var(--faint);font-family:var(--mono);margin-top:3px}
.verdict{
  flex:0 0 auto;font-size:11px;font-weight:600;padding:4px 10px;border-radius:99px;
  border:1px solid var(--c);color:var(--c);background:color-mix(in srgb,var(--c) 12%,transparent);
  white-space:nowrap;
}
.sc-score{display:flex;align-items:baseline;gap:9px;margin-bottom:4px}
.sc-score .v{font-family:var(--mono);font-size:44px;font-weight:700;line-height:1;letter-spacing:-.04em}
.sc-score .u{font-family:var(--mono);font-size:13px;color:var(--faint)}
.sc-bar{height:5px;border-radius:99px;background:rgba(150,180,255,.09);overflow:hidden;margin:12px 0 8px}
.sc-bar i{display:block;height:100%;border-radius:99px;background:var(--c);box-shadow:0 0 14px -2px var(--c)}
.sc-fingerprint{display:flex;gap:1.5px;height:26px;margin:14px 0 12px;align-items:flex-end}
.sc-fingerprint i{flex:1;border-radius:1.5px;background:var(--c);opacity:.85;min-height:2px}
.sc-extra{
  display:inline-flex;align-items:center;gap:7px;font-size:11.5px;color:var(--violet);
  border:1px dashed rgba(179,155,232,.4);border-radius:99px;padding:3px 11px;margin-bottom:14px;
}
.sc-extra b{font-family:var(--mono);color:var(--bone)}
.sc-specs{display:grid;grid-template-columns:1fr 1fr;gap:7px 12px;border-top:1px solid var(--line);padding-top:13px}
.sc-spec{display:flex;justify-content:space-between;gap:8px;font-size:12.5px}
.sc-spec span{color:var(--faint)}
.sc-spec b{font-family:var(--mono);font-weight:500;color:var(--bone-dim)}

/* ══════════════ 03 · AXES ══════════════ */
.axes-layout{display:grid;grid-template-columns:minmax(320px,.85fr) 1.15fr;gap:20px;align-items:start}
.radar-wrap{border:1px solid var(--line);border-radius:var(--r-lg);padding:18px;background:var(--panel)}
.radar-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:8px;flex-wrap:wrap}
.radar-head>span{font-family:var(--mono);font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint)}
.radar-legend{display:flex;gap:7px;flex-wrap:wrap;font-size:11px;color:var(--muted)}
.rl-item{
  display:inline-flex;align-items:center;gap:7px;font-size:12px;color:var(--bone-dim);
  background:rgba(150,180,255,.05);border:1px solid var(--line);border-radius:99px;
  padding:4px 11px;cursor:pointer;transition:.16s;line-height:1.5;
}
.rl-item:hover{border-color:var(--line-2);color:var(--bone);background:rgba(150,180,255,.09)}
.rl-item i{width:8px;height:8px;border-radius:2px;display:inline-block;flex:0 0 auto}
.rl-item.off{opacity:.42;text-decoration:line-through}
.rl-item.off i{background:transparent!important;border:1px dashed currentColor}
.rl-item.ref{border-style:dashed}
.rl-item:focus-visible{outline:2px solid var(--primary);outline-offset:2px}
.radar-hint{font-size:11.5px;color:var(--faint);margin-top:10px;line-height:1.6}
.radar-hint b{color:var(--muted);font-weight:500}
.radar-host{display:flex;justify-content:center}
.axis-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}
.axis-card{border:1px solid var(--line);border-radius:var(--r);padding:14px 15px;background:var(--panel);transition:.2s}
.axis-card:hover{border-color:var(--line-2);background:var(--panel-2)}
.ax-top{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:3px}
.ax-key{font-family:var(--mono);font-size:12px;color:var(--primary);letter-spacing:.1em}
.ax-min{font-family:var(--mono);font-size:11px;color:var(--faint)}
.ax-name{font-size:13.5px;color:var(--bone-dim);margin-bottom:11px;min-height:2.4em}
.ax-bars{display:flex;flex-direction:column;gap:7px}
.ax-bar{position:relative;display:flex;align-items:center;gap:8px}
.ax-dot{width:7px;height:7px;border-radius:2px;flex:0 0 auto}
.ax-track{position:relative;flex:1;height:16px;background:rgba(150,180,255,.06);border-radius:4px;overflow:visible}
.ax-fill{position:absolute;inset-block:0;inset-inline-start:0;border-radius:4px;opacity:.9}
.ax-val{position:absolute;inset-inline-start:calc(var(--p) * 1%);transform:translateX(50%);font-family:var(--mono);font-size:11px;color:var(--bone-dim);white-space:nowrap}
.ax-thresh{position:absolute;inset-inline-start:calc(var(--m) * 1%);top:-3px;bottom:-3px;width:1px;background:var(--danger);opacity:.65}
.ax-thresh::after{content:"⛔";position:absolute;top:-11px;left:50%;transform:translateX(-50%);font-size:11.5px}
.ax-meta{display:flex;justify-content:space-between;margin-top:10px;font-size:11.5px;color:var(--faint);border-top:1px solid var(--line);padding-top:8px}
.ax-meta b{font-family:var(--mono);color:var(--muted)}

/* ══════════════ 04 · EXTRA ══════════════ */
.extra-layout{display:grid;grid-template-columns:300px 1fr;gap:24px;align-items:start}
.extra-dials{display:flex;flex-direction:column;gap:10px}
.dial{
  border:1px solid rgba(179,155,232,.22);border-radius:var(--r);padding:13px 15px;
  background:rgba(179,155,232,.05);cursor:pointer;transition:.2s;
}
.dial:hover{border-color:rgba(179,155,232,.45)}
.dial.active{border-color:var(--violet);background:rgba(179,155,232,.11)}
.dial-top{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:8px}
.dial-name{font-size:12.5px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dial-score{font-family:var(--mono);font-size:16px;color:var(--violet);font-weight:600}
.dial-track{position:relative;height:6px;border-radius:99px;background:rgba(150,180,255,.09);overflow:hidden}
.dial-track i{display:block;height:100%;background:linear-gradient(90deg,var(--violet),var(--sky));border-radius:99px}
.dial-sub{margin-top:7px;font-size:11.5px;color:var(--faint);font-family:var(--mono)}
.extra-detail{display:flex;flex-direction:column;gap:14px}
.extra-tabs{display:flex;gap:8px;flex-wrap:wrap}
.etab{
  font-size:12px;padding:6px 13px;border-radius:99px;border:1px solid var(--line);
  color:var(--bone-dim);cursor:pointer;background:transparent;transition:.18s;
}
.etab.on{border-color:var(--violet);color:var(--bone);background:rgba(179,155,232,.14)}
.extra-domains{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}
.dom{border:1px solid var(--line);border-radius:var(--r-sm);padding:11px 13px;background:rgba(0,0,0,.18)}
.dom-name{font-size:12.5px;color:var(--bone-dim);margin-bottom:8px;line-height:1.4}
.dom-bar{height:4px;border-radius:99px;background:rgba(150,180,255,.09);overflow:hidden;margin-bottom:5px}
.dom-bar i{display:block;height:100%;background:var(--violet);opacity:.8}
.dom-val{font-family:var(--mono);font-size:12px;color:var(--muted)}
.extra-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}
.pcard{
  border:1px solid var(--line);border-radius:var(--r-sm);padding:12px 13px;
  background:rgba(0,0,0,.2);cursor:pointer;transition:.18s;
}
.pcard:hover{border-color:rgba(179,155,232,.4);transform:translateY(-2px)}
.pc-top{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px}
.pc-id{font-family:var(--mono);font-size:12px;color:var(--violet)}
.pc-score{font-family:var(--mono);font-size:13px;font-weight:600}
.pc-dom{font-size:11.5px;color:var(--faint);margin-bottom:8px}
.pc-crit{display:flex;gap:3px;margin-bottom:7px}
.pc-crit i{flex:1;height:3px;border-radius:99px;background:rgba(150,180,255,.11);position:relative;overflow:hidden}
.pc-crit i b{position:absolute;inset-block:0;inset-inline-start:0;background:var(--violet)}
.pc-prompt{font-size:12px;color:var(--muted);line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}

/* ══════════════ 05 · DOSSIER ══════════════ */
.filters{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-bottom:18px}
.chips{display:flex;gap:7px;flex-wrap:wrap}
.chip{
  font-size:12.5px;padding:5px 12px;border-radius:99px;cursor:pointer;
  border:1px solid var(--line);background:transparent;color:var(--muted);transition:.16s;
  display:inline-flex;align-items:center;gap:7px;
}
.chip:hover{color:var(--bone-dim);border-color:var(--line-2)}
.chip.on{color:var(--bone);background:rgba(150,180,255,.08);border-color:var(--line-2)}
.chip i{width:7px;height:7px;border-radius:2px;background:currentColor;opacity:.85}
.chip.gate{border-color:rgba(226,117,123,.3);color:var(--danger)}
.chip.gate.on{background:rgba(226,117,123,.14)}
.search-box{
  flex:1 1 240px;min-width:200px;display:flex;align-items:center;gap:9px;
  border:1px solid var(--line);border-radius:99px;padding:7px 15px;color:var(--faint);
  transition:.2s;
}
.search-box:focus-within{border-color:var(--primary);color:var(--primary)}
.search-box input{
  flex:1;background:transparent;border:0;outline:0;color:var(--bone);
  font-family:inherit;font-size:13.5px;
}
.search-box input::placeholder{color:var(--faint)}
.dossier{display:flex;flex-direction:column;gap:6px}
.qrow{
  display:grid;grid-template-columns:66px 1fr 132px 88px 24px;
  align-items:center;gap:14px;padding:11px 14px;border-radius:var(--r-sm);
  border:1px solid transparent;cursor:pointer;transition:.15s;
}
.qrow:hover{background:var(--panel);border-color:var(--line)}
.qrow-head{
  cursor:default;border-bottom:1px solid var(--line);border-radius:0;
  font-family:var(--mono);font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--faint);padding-bottom:9px;
}
.qrow-head:hover{background:none;border-color:transparent}
.qid{font-family:var(--mono);font-size:13px;color:var(--primary);font-weight:500}
.qtitle{font-size:14px;color:var(--bone-dim);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.qtitle small{display:block;font-size:11.5px;color:var(--faint);font-family:var(--mono);letter-spacing:.04em}
.qbar{position:relative;height:6px;border-radius:99px;background:rgba(150,180,255,.08);overflow:hidden}
.qbar i{display:block;height:100%;border-radius:99px}
.qscore{font-family:var(--mono);font-size:13px;text-align:end;color:var(--bone-dim)}
.qflags{display:flex;gap:5px;justify-content:flex-end}
.flag{font-size:11.5px;padding:2px 7px;border-radius:99px;border:1px solid;white-space:nowrap}
.flag.gate{color:var(--danger);border-color:rgba(226,117,123,.4)}
.flag.empty{color:var(--faint);border-color:var(--line-2)}
.flag.copy{color:var(--primary);border-color:rgba(242,166,90,.4)}
.flag.ok{color:var(--ok);border-color:rgba(143,203,155,.35)}
.qchev{color:var(--faint);font-size:13px;text-align:center}
.empty-state{padding:40px;text-align:center;color:var(--faint);font-size:13px;border:1px dashed var(--line);border-radius:var(--r)}

/* ══════════════ 06 · PERF ══════════════ */
.perf-layout{display:grid;grid-template-columns:1.5fr .8fr;gap:20px;align-items:start}
.perf-table-wrap{border:1px solid var(--line);border-radius:var(--r-lg);overflow:auto;background:var(--panel)}
.perf-table{width:100%;border-collapse:collapse;font-size:13.5px}
.perf-table th{
  text-align:start;padding:11px 14px;font-family:var(--mono);font-size:11px;
  letter-spacing:.12em;text-transform:uppercase;color:var(--faint);
  border-bottom:1px solid var(--line);white-space:nowrap;position:sticky;top:0;background:#0A0E17;
}
.perf-table td{padding:10px 14px;border-bottom:1px solid rgba(233,238,249,.055);color:var(--bone-dim)}
.perf-table tr:last-child td{border-bottom:0}
.perf-table td.num{font-family:var(--mono);text-align:end;white-space:nowrap}
.perf-table .mname{display:flex;align-items:center;gap:8px;color:var(--bone);font-weight:500}
.perf-table .mname i{width:8px;height:8px;border-radius:2px;flex:0 0 auto}
.best{color:var(--ok)!important}
.gemini-card{border:1px solid var(--line);border-radius:var(--r-lg);padding:18px;background:var(--panel)}
.gc-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:6px}
.gc-name{font-weight:600;font-size:14px}
.gc-badge{font-family:var(--mono);font-size:11px;border:1px solid var(--line-2);border-radius:99px;padding:2px 9px;color:var(--faint)}
.gc-note{font-size:12.5px;color:var(--muted);line-height:1.6;margin-bottom:14px}
.gc-rows{display:flex;flex-direction:column;gap:7px}
.gc-row{display:flex;align-items:center;gap:9px;font-size:12.5px}
.gc-name-s{width:28px;font-family:var(--mono);font-size:11.5px;color:var(--primary)}
.gc-track{flex:1;height:5px;border-radius:99px;background:rgba(150,180,255,.08);position:relative;overflow:hidden}
.gc-track i{position:absolute;inset-block:0;inset-inline-start:0;border-radius:99px;background:rgba(233,238,249,.35)}
.gc-val{font-family:var(--mono);font-size:11.5px;color:var(--muted);width:46px;text-align:end}

/* ══════════════ DRAWER ══════════════ */
.drawer-scrim{position:fixed;inset:0;background:rgba(6,5,4,.62);backdrop-filter:blur(3px);z-index:80}
.drawer{
  position:fixed;inset-block:0;inset-inline-end:0;width:min(660px,94vw);z-index:90;
  background:#0A0E17;border-inline-start:1px solid var(--line-2);
  box-shadow:-30px 0 80px -30px rgba(0,0,0,.9);
  overflow-y:auto;animation:slideIn .3s cubic-bezier(.2,.8,.25,1);
}
@keyframes slideIn{from{transform:translateX(-24px);opacity:0}to{transform:none;opacity:1}}
.drawer-close{
  position:sticky;top:14px;float:inline-end;margin:14px 16px 0 0;
  width:32px;height:32px;border-radius:50%;border:1px solid var(--line-2);
  background:rgba(20,18,16,.92);color:var(--bone-dim);cursor:pointer;font-size:13px;z-index:2;
}
.drawer-close:hover{color:var(--primary);border-color:var(--primary)}
.drawer-body{padding:0 26px 40px}
.dr-head{border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:18px}
.dr-kicker{display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-wrap:wrap}
.dr-qid{font-family:var(--mono);font-size:13px;color:var(--primary);font-weight:600}
.dr-cat{font-family:var(--mono);font-size:11.5px;color:var(--faint);border:1px solid var(--line);border-radius:99px;padding:2px 9px}
.dr-title{font-size:19px;font-weight:600;line-height:1.4}
.dr-why{font-size:13.5px;color:var(--muted);margin-top:6px}
.dr-score{display:flex;align-items:baseline;gap:10px;margin:16px 0 4px}
.dr-score b{font-family:var(--mono);font-size:34px;font-weight:700;line-height:1}
.dr-score span{font-family:var(--mono);font-size:12px;color:var(--faint)}
.dr-meta{display:flex;gap:16px;flex-wrap:wrap;font-family:var(--mono);font-size:11.5px;color:var(--faint);margin-top:10px}
.dr-meta i{font-style:normal;color:var(--muted)}
.dr-sec{margin-bottom:22px}
.dr-sec-h{
  font-family:var(--mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;
  color:var(--faint);margin-bottom:9px;padding-bottom:7px;border-bottom:1px solid var(--line);
}
.dr-prompt{font-size:14.5px;color:var(--bone-dim);line-height:1.8;white-space:pre-wrap}
.dr-answer{
  font-size:14px;line-height:1.85;white-space:pre-wrap;max-height:340px;overflow-y:auto;
  padding:14px 16px;border-radius:var(--r);background:rgba(0,0,0,.3);border:1px solid var(--line);
  color:var(--bone-dim);
}
.dr-answer.empty{color:var(--faint);font-style:italic}
.crit{display:grid;grid-template-columns:1fr 62px;gap:12px;padding:11px 0;border-bottom:1px solid rgba(233,238,249,.055)}
.crit:last-child{border-bottom:0}
.crit-label{font-size:13.5px;color:var(--bone-dim);margin-bottom:3px}
.crit-note{font-size:12.5px;color:var(--muted);line-height:1.6}
.crit-pts{font-family:var(--mono);font-size:13px;text-align:end}
.crit-bar{grid-column:1/-1;height:3px;border-radius:99px;background:rgba(150,180,255,.09);overflow:hidden;margin-top:7px}
.crit-bar i{display:block;height:100%;border-radius:99px}
.pill{display:inline-block;font-size:11px;padding:2px 8px;border-radius:99px;border:1px solid}

/* ══════════════ FOOT ══════════════ */
.foot{
  border-top:1px solid var(--line);margin-top:30px;padding-top:22px;
  display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;
  font-size:12.5px;color:var(--faint);font-family:var(--mono);
}

/* ══════════════ RESPONSIVE ══════════════ */
@media (max-width:1080px){
  .hero,.axes-layout,.perf-layout,.extra-layout{grid-template-columns:1fr}
  .hero{align-items:start}
  .qrow{grid-template-columns:56px 1fr 90px 24px}
  .qrow .qflags{display:none}
}
@media (max-width:720px){
  .topbar-meta{display:none}
  .spec-grid{grid-template-columns:1fr}
  .qrow{grid-template-columns:48px 1fr 62px;gap:9px}
  .qrow .qchev{display:none}
}
@media print{
  .topbar,.drawer,.drawer-scrim,.filters,.grain{display:none!important}
  body{background:#fff;color:#111}
  .panel{border-color:#ddd}
}

/* ══════════ مرجع Gemini (عرض فقط) ══════════ */
.spec-card.ref{border-style:dashed;background:rgba(150,180,255,.025)}
.spec-card.ref::before{background:repeating-linear-gradient(90deg,transparent,var(--c),transparent);opacity:.8}
.ref-badge{
  font-family:var(--mono);font-size:11.5px;border:1px dashed var(--c);color:var(--c);
  border-radius:99px;padding:2px 9px;letter-spacing:.06em;
}
.ref-note{font-size:12px;color:var(--faint);line-height:1.6;margin-bottom:12px}
.needle.ref{
  width:0;background:transparent;box-shadow:none;
  border-inline-start:2px dashed currentColor;
}
.needle.ref::after{
  background:transparent;border:2px solid currentColor;border-radius:50%;
  width:9px;height:9px;top:-4px;
}
.ax-bar.ref .ax-fill{
  background:repeating-linear-gradient(90deg,var(--c) 0 5px,transparent 5px 10px);
  opacity:.8;
}
.ref-toggle{
  display:inline-flex;align-items:center;gap:7px;font-size:11.5px;
  border:1px dashed rgba(155,176,212,.5);color:#9BB0D4;background:transparent;
  border-radius:99px;padding:6px 13px;cursor:pointer;transition:.18s;
}
.ref-toggle:hover{border-color:#9BB0D4;background:rgba(155,176,212,.08)}
.ref-toggle.off{opacity:.5}

/* ══════════ قسم الأسئلة — عرض مجمّع + طيّ/فرد ══════════ */
.dossier-bar{
  display:flex;align-items:center;gap:14px;flex-wrap:wrap;
  padding:12px 16px;border:1px solid var(--line);border-radius:var(--r);
  background:var(--panel);margin-bottom:14px;
}
.dossier-count{font-family:var(--mono);font-size:12px;color:var(--bone-dim)}
.dossier-count b{color:var(--bone)}
.dossier-bar .spacer{flex:1}
.sort-select{
  background:#0C1424;border:1px solid var(--line-2);color:var(--bone);
  border-radius:99px;padding:6px 13px;font-family:inherit;font-size:12.5px;cursor:pointer;
}
.sort-select:focus{outline:none;border-color:var(--primary)}
.btn-mini{
  background:transparent;border:1px solid var(--line-2);color:var(--bone-dim);
  border-radius:99px;padding:6px 13px;font-size:12.5px;cursor:pointer;transition:.16s;
}
.btn-mini:hover{border-color:var(--primary);color:var(--bone)}

.qgroup{border:1px solid var(--line);border-radius:var(--r);margin-bottom:10px;overflow:hidden;background:rgba(150,180,255,.018)}
.qgroup-head{
  display:grid;grid-template-columns:26px 120px 1fr 180px 110px 26px;
  align-items:center;gap:12px;padding:12px 16px;cursor:pointer;
  background:rgba(150,180,255,.05);transition:background .16s;
}
.qgroup-head:hover{background:rgba(150,180,255,.09)}
.qgroup-key{font-family:var(--mono);font-size:13px;color:var(--primary);font-weight:600}
.qgroup-name{font-size:14px;color:var(--bone)}
.qgroup-meta{font-size:12px;color:var(--muted);display:flex;gap:16px;flex-wrap:wrap}
.qgroup-meta b{font-family:var(--mono);color:var(--bone-dim)}
.qgroup-bar{position:relative;height:7px;border-radius:99px;background:rgba(150,180,255,.1);overflow:hidden}
.qgroup-bar i{display:block;height:100%;border-radius:99px}
.qgroup-bar .thr{position:absolute;inset-block:-3px;width:2px;background:var(--danger);opacity:.8}
.qgroup-arrow{color:var(--muted);text-align:center;transition:transform .2s;font-size:12px}
.qgroup.closed .qgroup-arrow{transform:rotate(-90deg)}
.qgroup-body{border-top:1px solid var(--line)}

.qrow{
  display:grid;grid-template-columns:26px 66px 1fr 150px 92px 120px 26px;
  align-items:center;gap:12px;padding:11px 16px;border-bottom:1px solid rgba(190,210,255,.06);
  cursor:pointer;transition:background .14s;
}
.qrow:hover{background:rgba(150,180,255,.06)}
.qrow.open{background:rgba(150,180,255,.08)}
.qrow:last-child{border-bottom:0}
.qcaret{color:var(--muted);font-size:11px;text-align:center;transition:transform .2s}
.qrow.open .qcaret{transform:rotate(90deg);color:var(--primary)}
.qchev{color:var(--muted);font-size:12px;text-align:center}

.qexpanded{
  padding:4px 16px 20px 54px;border-bottom:1px solid rgba(190,210,255,.06);
  background:rgba(8,12,22,.45);
}
.qexp-grid{display:grid;grid-template-columns:1.15fr .85fr;gap:22px}
.qexp-h{
  font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--faint);margin:0 0 9px;padding-bottom:6px;border-bottom:1px solid var(--line);
}
.qexp-prompt{font-size:14px;color:var(--bone-dim);line-height:1.85;white-space:pre-wrap}
.qexp-answer{
  font-size:13.5px;line-height:1.85;color:var(--bone-dim);white-space:pre-wrap;
  max-height:260px;overflow-y:auto;padding:13px 15px;border-radius:var(--r-sm);
  background:rgba(0,0,0,.28);border:1px solid var(--line);
}
.qexp-answer.empty{color:var(--faint);font-style:italic}
.qexp-crit{display:grid;grid-template-columns:1fr 64px;gap:10px;padding:9px 0;border-bottom:1px solid rgba(190,210,255,.05)}
.qexp-crit:last-child{border-bottom:0}
.qexp-crit .crit-label{font-size:13px}
.qexp-crit .crit-note{font-size:12px}
.qexp-crit .crit-pts{font-family:var(--mono);font-size:13px;text-align:end}
.qexp-crit .crit-bar{grid-column:1/-1;height:3px;margin-top:6px}
.qexp-meta{display:flex;gap:16px;flex-wrap:wrap;font-family:var(--mono);font-size:11.5px;color:var(--faint);margin-top:12px}
.qexp-meta i{font-style:normal;color:var(--bone-dim)}
@media (max-width:1080px){
  .qexp-grid{grid-template-columns:1fr}
  .qrow{grid-template-columns:22px 56px 1fr 90px 24px}
  .qrow .qflags,.qrow .qbar{display:none}
  .qgroup-head{grid-template-columns:22px 90px 1fr 90px 22px}
  .qgroup-head .qgroup-bar{display:none}
}

/* موديل فشل: رسالة الخطأ على الكارت */
.sc-error{
  font-size:11.5px;color:var(--danger);line-height:1.6;
  border:1px solid rgba(255,107,129,.35);background:rgba(255,107,129,.08);
  border-radius:8px;padding:6px 9px;margin-top:8px;
}
"""

JS = r"""/* ══════════ 01 · CORE — البيانات والـhelpers ══════════ */
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


/* ══════════ 02 · VIEWS — البطاقات · الرادار · المحاور ══════════ */

/* ══════════ 03 · بطاقات الموديلات ══════════ */
function renderSpecCards() {
  const host = $("#specGrid");
  host.innerHTML = MODELS.map(m => {
    const on = state.visible.has(m.key);
    const focus = state.focus === m.key;
    const cls = ["spec-card", on ? "" : "muted", focus ? "focus" : ""].join(" ").trim();

    /* بصمة الدرجات: 33 عمود صغير */
    const qs = Object.values(m.questions || {});
    const fp = qs.map(q => {
      const p = (q.score / (q.max || 10)) * 100;
      const h = Math.max(8, p);
      const c = scoreColor(p);
      return `<i style="height:${h}%;background:${c};opacity:${0.35 + p / 160}"></i>`;
    }).join("");

    const full = qs.filter(q => q.score >= (q.max || 10) - 0.01).length;
    const empty = qs.filter(q => q.empty).length;

    const prof = m.profile || {};
    const profChip = (prof.answered || 0) > 0
      ? `<div class="sc-extra">◆ الميزة الإضافية <b>${num(prof.total, 2)}/20</b> · ${prof.answered}/${prof.count}</div>`
      : `<div class="sc-extra" style="color:var(--faint);border-color:var(--line)">◆ الميزة الإضافية — لم يُجب</div>`;

    return `
    <article class="${cls}" style="--c:${m.color}" data-model="${esc(m.key)}" tabindex="0">
      <div class="sc-top">
        <div>
          <div class="sc-name">${esc(m.name)}</div>
          <div class="sc-repo">${esc(m.repo || "")}</div>
          ${m.error ? `<div class="sc-error">⛔ ${esc(m.error)}</div>` : ""}
        </div>
        <div class="sc-top-right">
          <button class="sc-eye ${on ? "" : "off"}" data-eye="${esc(m.key)}"
            title="${on ? "إخفاء من المقارنة" : "إظهار في المقارنة"}">${on ? "●" : "○"}</button>
          <span class="verdict">${esc(m.verdict)}</span>
        </div>
      </div>
      <div class="sc-score"><span class="v">${num(m.total, 2)}</span><span class="u">/100</span></div>
      <div class="sc-bar"><i style="width:${m.total}%"></i></div>
      <div class="sc-fingerprint" title="بصمة الدرجات: ${qs.length} سؤال">${fp}</div>
      ${profChip}
      <div class="sc-specs">
        <div class="sc-spec"><span>أسئلة كاملة</span><b>${full}/${qs.length}</b></div>
        <div class="sc-spec"><span>ردود فاضية</span><b>${empty}</b></div>
        <div class="sc-spec"><span>الوزن</span><b>${fmtBytes(m.bytes)}</b></div>
        <div class="sc-spec"><span>tok/s</span><b>${num(m.perf?.tg_avg, 1)}</b></div>
        <div class="sc-spec"><span>زمن الطلب</span><b>${fmtDur(m.perf?.req_avg)}</b></div>
        <div class="sc-spec"><span>GPU</span><b>${esc(m.fit?.ngl ?? "—")}/${esc(m.fit?.layers ?? "—")}</b></div>
      </div>
    </article>`;
  }).join("");

  /* بطاقة المرجع — شكل مميّز (منقّط) ومش بتدخل في ملف الأسئلة */
  if (REF) {
    host.innerHTML += `
    <article class="spec-card gem-ref ref ${state.refVisible ? "" : "muted"}" style="--c:${REF.color}"
      ${state.refVisible ? GEM_ATTR.on : GEM_ATTR.off} data-refcard>
      <div class="sc-top">
        <div>
          <div class="sc-name">${esc(REF.name)}</div>
          <div class="sc-repo">${esc(REF.repo || "مرجع خارجي")}</div>
        </div>
        <div class="sc-top-right">
          <button class="sc-eye ${state.refVisible ? "" : "off"}" data-ref-eye
            title="${state.refVisible ? "إخفاء المرجع" : "إظهار المرجع"}">${state.refVisible ? "●" : "○"}</button>
          <span class="ref-badge">مرجع · عرض فقط</span>
        </div>
      </div>
      <div class="sc-score"><span class="v">${num(REF.total, 2)}</span><span class="u">/100</span></div>
      <div class="sc-bar"><i style="width:${REF.total}%"></i></div>
      <div class="ref-note">أرقام مرجعية من بنشماركات عامة — <b>مش</b> مقاسة على أسئلة امتحاننا،
        وبالذات <b>مش</b> بتشارك في درجة ولا حكم أي موديل.</div>
      <div class="sc-specs">
        <div class="sc-spec"><span>محاور مقارنة</span><b>${Object.keys(REF.cats).length}</b></div>
        <div class="sc-spec"><span>أسئلة امتحاننا</span><b>—</b></div>
      </div>
    </article>`;
    const eye = $("[data-ref-eye]", host);
    if (eye) eye.addEventListener("click", ev => {
      ev.stopPropagation();
      state.refVisible = !state.refVisible;
      refresh();
    });
  }

  /* كليك البطاقة = تبعيد (focus) — مش إخفاء */
  $$(".spec-card", host).forEach(card => {
    const k = card.dataset.model;
    card.addEventListener("click", () => {
      state.focus = k;
      state.visible.add(k);
      refresh();
    });
  });

  /* زر الـeye = إظهار/إخفاء من المقارنات */
  $$("[data-eye]", host).forEach(btn => {
    btn.addEventListener("click", ev => {
      ev.stopPropagation();
      const k = btn.dataset.eye;
      if (state.visible.has(k) && state.visible.size > 1) state.visible.delete(k);
      else state.visible.add(k);
      refresh();
    });
  });
}

/* ══════════ 04 · الرادار (SVG مرسوم يدوياً) ══════════ */
function renderRadar() {
  const cats = Object.entries(CFG.categories || {});
  const N = cats.length;
  const size = 380, cx = size / 2, cy = size / 2 + 6, R = 138;
  /* الرسم بيعرض الموديلات المختارة في الرسم فقط (تحكّم مستقل) */
  const active = MODELS
    .filter(m => state.radar.has(m.key) && state.visible.has(m.key))
    .concat(REF && state.refVisible ? [REF] : []);

  const pt = (i, r) => {
    const a = (-Math.PI / 2) + (i * 2 * Math.PI) / N;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  };
  const poly = m => cats.map(([k], i) => {
    const pctv = m.cats?.[k]?.percent ?? 0;
    const r = (Math.max(0, Math.min(100, pctv)) / 100) * R;
    return pt(i, r).map(v => v.toFixed(1)).join(",");
  }).join(" ");

  const rings = [0.25, 0.5, 0.75, 1].map(f =>
    `<polygon points="${cats.map((_, i) => pt(i, R * f).map(v => v.toFixed(1)).join(",")).join(" ")}"
       fill="none" stroke="rgba(237,231,220,.09)" stroke-width="1"/>`
  ).join("");

  const spokes = cats.map((_, i) => {
    const [x, y] = pt(i, R);
    return `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}"
             stroke="rgba(237,231,220,.09)" stroke-width="1"/>`;
  }).join("");

  const labels = cats.map(([k, c], i) => {
    const [x, y] = pt(i, R + 30);
    const anchor = Math.abs(x - cx) < 12 ? "middle" : (x > cx ? "start" : "end");
    const under = y > cy + 6;
    return `<text x="${x.toFixed(1)}" y="${under ? (y + 14).toFixed(1) : (y - 4).toFixed(1)}"
              text-anchor="${anchor}" fill="#8C857A" font-size="11"
              font-family="Cairo, sans-serif">${esc(c.short || k)}</text>`;
  }).join("");

  const shapes = active.map(m => m.isRef
    ? `<polygon points="${poly(m)}" fill="none" stroke="${m.color}" stroke-width="1.8"
       stroke-dasharray="5 4" stroke-linejoin="round" opacity=".85"/>`
    : `<polygon points="${poly(m)}" fill="${m.color}" fill-opacity="${active.length > 1 ? 0.07 : 0.13}"
       stroke="${m.color}" stroke-width="${state.focus === m.key ? 2.4 : 1.4}"
       stroke-linejoin="round" opacity="${state.focus === m.key ? 1 : 0.55}"/>`
  ).join("");

  const dots = active.filter(m => !m.isRef).map(m => cats.map(([k], i) => {
    const pctv = m.cats?.[k]?.percent ?? 0;
    const r = (Math.max(0, Math.min(100, pctv)) / 100) * R;
    const [x, y] = pt(i, r);
    return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${state.focus === m.key ? 3.4 : 2.2}"
             fill="${m.color}" opacity="${state.focus === m.key ? 1 : 0.6}"/>`;
  }).join("")).join("");

  $("#radarHost").innerHTML =
    `<svg viewBox="0 0 ${size} ${size + 18}" width="100%" style="max-width:400px">
       ${rings}${spokes}${shapes}${dots}${labels}
     </svg>`;

  /* ── الليجند = أزرار إظهار/إخفاء لكل موديل داخل الرسم ── */
  const legendModels = MODELS.concat(REF ? [REF] : []);
  $("#radarLegend").innerHTML = legendModels.map(m => {
    const on = m.isRef
      ? state.refVisible
      : (state.radar.has(m.key) && state.visible.has(m.key));
    const nm = shortModel(m.name);
    const label = nm.length > 18 ? nm.slice(0, 17) + "…" : nm;
    return `<button type="button" class="rl-item ${m.isRef ? "ref" : ""} ${on ? "" : "off"}"
      data-rl="${esc(m.key)}" title="${on ? "اضغط للإخفاء من الرسم" : "اضغط للإظهار في الرسم"}">
      <i style="background:${m.color}"></i>${esc(label)}</button>`;
  }).join("");

  $$("[data-rl]").forEach(b => b.addEventListener("click", () => {
    const k = b.dataset.rl;
    if (k === "__ref__") {
      state.refVisible = !state.refVisible;
      renderTop();
      refresh();
      return;
    }
    if (state.radar.has(k)) {
      if (state.radar.size > 1) state.radar.delete(k);   /* لازم واحد على الأقل */
    } else {
      state.radar.add(k);
    }
    refresh();
  }));
}

/* ══════════ 05 · بطاقات المقارنة على المحاور ══════════ */
function renderAxisCards() {
  const cats = Object.entries(CFG.categories || {});
  const host = $("#categories");

  host.innerHTML = cats.map(([key, c]) => {
    const active = SHOWN().filter(m => state.visible.has(m.key) || m.isRef);
    const bars = active.map(m => {
      const row = m.cats?.[key] || {};
      const p = row.percent ?? 0;
      const failed = row.failed_min;
      return `
        <div class="ax-bar ${m.isRef ? "ref" : ""}" title="${esc(m.name)} — ${pct(p)}${failed ? " (تحت الحد)" : ""}">
          <i class="ax-dot" style="background:${m.color}"></i>
          <div class="ax-track">
            <div class="ax-fill" style="width:${Math.max(1.5, p)}%;background:${m.color}"></div>
            <div class="ax-val" style="--p:${Math.min(97, p)}">${num(p, 1)}%</div>
            ${c.min_percent > 0 ? `<div class="ax-thresh" style="--m:${c.min_percent}"></div>` : ""}
          </div>
        </div>`;
    }).join("");

    const vals = active.map(m => m.cats?.[key]?.percent ?? 0);
    const best = Math.max(...vals, 0);
    const worst = Math.min(...vals, 100);
    const spread = best - worst;

    return `
    <article class="axis-card">
      <div class="ax-top">
        <span class="ax-key">${esc(key)}</span>
        <span class="ax-min">${c.min_percent > 0 ? "الحد الأدنى " + c.min_percent + "%" : "بلا حد أدنى"}</span>
      </div>
      <div class="ax-name">${esc(c.name)}</div>
      <div class="ax-bars">${bars}</div>
      <div class="ax-meta">
        <span>الوزن <b>${c.weight}%</b></span>
        <span>الفارق <b>${num(spread, 1)}</b> نقطة</span>
        <span>أسئلة <b>${(c.questions || []).length}</b></span>
      </div>
    </article>`;
  }).join("");
}


/* ══════════ 07 · ملف الأسئلة — عرض مجمّع + طيّ/فرد + فلترة + ترتيب ══════════ */

const STATE_CHIPS = [
  { k: "all",   label: "الكل" },
  { k: "gate",  label: "تحت حد المحور" },
  { k: "empty", label: "رد فاضي" },
  { k: "copy",  label: "نسخ السؤال" },
  { k: "full",  label: "سؤال كامل" },
  { k: "zero",  label: "صفر" },
];

const SORTS = [
  { k: "axis",   label: "ترتيب: المحور" },
  { k: "desc",   label: "ترتيب: الدرجة (تنازلي)" },
  { k: "asc",    label: "ترتيب: الدرجة (تصاعلي)" },
  { k: "model",  label: "ترتيب: الموديل" },
  { k: "time",   label: "ترتيب: زمن الطلب" },
];

function renderFilters() {
  /* ── الموديلات ── */
  $("#fModels").innerHTML = MODELS.map(m =>
    `<button class="chip ${state.visible.has(m.key) ? "on" : ""}" data-fm="${esc(m.key)}">
       <i style="background:${m.color}"></i>${esc(shortModel(m.name))}</button>`).join("");

  /* ── المحاور ── */
  const cats = Object.entries(CFG.categories || {});
  $("#fCats").innerHTML =
    `<button class="chip ${state.cat === null ? "on" : ""}" data-fc="">كل المحاور</button>` +
    cats.map(([k, c]) =>
      `<button class="chip ${state.cat === k ? "on" : ""}" data-fc="${esc(k)}">${esc(k)} · ${esc(c.short || c.name)}</button>`
    ).join("");

  $$("[data-fm]").forEach(b => b.addEventListener("click", () => {
    const k = b.dataset.fm;
    if (state.visible.has(k) && state.visible.size > 1) state.visible.delete(k);
    else state.visible.add(k);
    state.focus = k;
    refresh();
  }));
  $$("[data-fc]").forEach(b => b.addEventListener("click", () => {
    state.cat = b.dataset.fc || null;
    renderFilters(); renderDossier();
  }));
}

/* ── شريط الحالة (كل / تحت حد / فاضي / منسوخ / كامل / صفر) ── */
function renderStateChips() {
  const host = $("#fStates");
  if (!host) return;
  host.innerHTML = STATE_CHIPS.map(c =>
    `<button class="chip ${state.flag === c.k ? "on" : ""} ${c.k === "gate" ? "gate" : ""}"
      data-fs="${c.k}">${esc(c.label)}</button>`).join("");
  $$("[data-fs]").forEach(b => b.addEventListener("click", () => {
    state.flag = b.dataset.fs;
    renderStateChips();
    renderDossier();
  }));
}

function rowFlags(m, row) {
  const flags = [];
  const p = (row.score / (row.max || 10)) * 100;
  const ax = (m.cats || {})[row.category] || {};
  if (row.empty) flags.push(`<span class="flag empty">رد فاضي</span>`);
  if (ax.failed_min) flags.push(`<span class="flag gate">تحت حد المحور</span>`);
  if ((row.criteria || []).some(c => /رد مش إجابة/.test(c.note || "")))
    flags.push(`<span class="flag copy">نسخ السؤال</span>`);
  if (!flags.length && p >= 100) flags.push(`<span class="flag ok">كامل</span>`);
  else if (!flags.length && p === 0) flags.push(`<span class="flag empty">صفر</span>`);
  return flags.join("");
}

function matchFlag(m, row) {
  const p = (row.score / (row.max || 10)) * 100;
  const ax = (m.cats || {})[row.category] || {};
  switch (state.flag) {
    case "gate":  return !!ax.failed_min;
    case "empty": return !!row.empty;
    case "copy":  return (row.criteria || []).some(c => /رد مش إجابة/.test(c.note || ""));
    case "full":  return p >= 100;
    case "zero":  return p === 0;
    default:      return true;
  }
}

/* ══════════ الرسم ══════════ */
function renderDossier() {
  const host = $("#answers");
  const q = state.q.trim().toLowerCase();

  /* ── 1) جمع الصفوف ── */
  const rows = [];
  MODELS.filter(m => state.visible.has(m.key)).forEach(m => {
    Object.entries(m.questions || {}).forEach(([qid, row]) => {
      if (state.cat && row.category !== state.cat) return;
      if (!matchFlag(m, row)) return;
      if (q) {
        const hay = `${qid} ${row.title || ""} ${row.answer || ""} ${row.prompt || ""}`.toLowerCase();
        if (!hay.includes(q)) return;
      }
      rows.push({ m, qid, row });
    });
  });

  /* ── 2) الترتيب ── */
  const sort = state.sort || "axis";
  if (sort === "desc") rows.sort((a, b) => b.row.score - a.row.score || a.qid.localeCompare(b.qid));
  else if (sort === "asc") rows.sort((a, b) => a.row.score - b.row.score || a.qid.localeCompare(b.qid));
  else if (sort === "model") rows.sort((a, b) => a.m.name.localeCompare(b.m.name) || a.qid.localeCompare(b.qid));
  else if (sort === "time") rows.sort((a, b) => (b.row.seconds || 0) - (a.row.seconds || 0));
  else rows.sort((a, b) => a.qid.localeCompare(b.qid) || a.m.key.localeCompare(b.m.key));

  /* ── 3) شريط التحكم ── */
  const groups = [...new Set(rows.map(r => r.row.category || "—"))];
  const openCount = rows.filter(r => state.expanded.has(r.m.key + "|" + r.qid)).length;
  $("#dossierBar").innerHTML = `
    <span class="dossier-count"><b>${rows.length}</b> صف · <b>${groups.length}</b> محور · <b>${openCount}</b> مفتوح</span>
    <span class="spacer"></span>
    <select class="sort-select" id="sortSelect" aria-label="ترتيب الأسئلة">
      ${SORTS.map(s => `<option value="${s.k}" ${s.k === (state.sort || "axis") ? "selected" : ""}>${esc(s.label)}</option>`).join("")}
    </select>
    <button class="btn-mini" data-toggle-all>${openCount ? "طي الكل" : "فرد الكل"}</button>`;

  /* ── 4) تجميع حسب المحور (مع الترتيب) ── */
  const byGroup = new Map();
  rows.forEach(r => {
    const k = r.row.category || "—";
    if (!byGroup.has(k)) byGroup.set(k, []);
    byGroup.get(k).push(r);
  });

  let gk = [...byGroup.keys()];
  if (sort === "axis") gk.sort((a, b) => a.localeCompare(b));

  if (!rows.length) {
    host.innerHTML = `<div class="empty-state">لا توجد أسئلة مطابقة — جرّب توسّع الفلترة</div>`;
    return;
  }

  host.innerHTML = gk.map(key => {
    const list = byGroup.get(key);
    const cfg = (CFG.categories || {})[key] || {};
    const closed = state.collapsed.has(key);
    const pcts = list.map(r => (r.row.score / (r.row.max || 10)) * 100);
    const avg = pcts.reduce((a, b) => a + b, 0) / pcts.length;
    const minP = cfg.min_percent || 0;
    const overMin = minP > 0 && avg < minP;

    const body = list.map(({ m, qid, row }) => {
      const key2 = m.key + "|" + qid;
      const open = state.expanded.has(key2);
      const p = (row.score / (row.max || 10)) * 100;
      return `
      <div class="qrow ${open ? "open" : ""}" data-q="${esc(m.key)}|${esc(qid)}">
        <span class="qcaret">▶</span>
        <span class="qid">${esc(qid)}</span>
        <span class="qtitle">${esc(row.title || "")}
          <small>${esc(m.name)} · ${esc(row.category_name || "")}</small></span>
        <span class="qbar"><i style="width:${Math.max(1.5, p)}%;background:${scoreColor(p)}"></i></span>
        <span class="qscore">${num(row.score, 1)}/${num(row.max, 1)}</span>
        <span class="qflags">${rowFlags(m, row)}</span>
        <span class="qchev">›</span>
      </div>
      ${open ? expandedHtml(m, row) : ""}`;
    }).join("");

    return `
    <section class="qgroup ${closed ? "closed" : ""}" data-group="${esc(key)}">
      <header class="qgroup-head">
        <span class="qgroup-arrow">▼</span>
        <span class="qgroup-key">${esc(key)}</span>
        <span class="qgroup-name">${esc(cfg.name || key)}
          <span class="qgroup-meta">
            <span>الوزن <b>${cfg.weight ?? "—"}%</b></span>
            <span>الحد الأدنى <b>${minP ? minP + "%" : "—"}</b></span>
            <span>متوسط الصفوف <b>${num(avg, 1)}%</b></span>
            <span>${list.length} صف</span>
          </span>
        </span>
        <span class="qgroup-bar">
          <i style="width:${Math.max(1.5, avg)}%;background:${scoreColor(avg)}"></i>
          ${minP > 0 ? `<span class="thr" style="inset-inline-start:${minP}%"></span>` : ""}
        </span>
        <span class="qscore">${overMin ? "⛔ تحت الحد" : "✅"}</span>
        <span></span>
      </header>
      <div class="qgroup-body" ${closed ? "hidden" : ""}>${body}</div>
    </section>`;
  }).join("");

  /* ── 5) الأحداث ── */
  $$(".qgroup-head", host).forEach(h =>
    h.addEventListener("click", () => {
      const key = h.parentElement.dataset.group;
      if (state.collapsed.has(key)) state.collapsed.delete(key);
      else state.collapsed.add(key);
      renderDossier();
    }));

  $$(".qrow[data-q]", host).forEach(r =>
    r.addEventListener("click", () => {
      const [mk, qid] = r.dataset.q.split("|");
      const k = mk + "|" + qid;
      if (state.expanded.has(k)) state.expanded.delete(k);
      else state.expanded.add(k);
      renderDossier();
    }));

  const sortSel = $("#sortSelect");
  if (sortSel) sortSel.addEventListener("change", e => {
    state.sort = e.target.value;
    renderDossier();
  });

  const all = $("#dossierBar [data-toggle-all]");
  if (all) all.addEventListener("click", () => {
    if (state.expanded.size) state.expanded.clear();
    else rows.forEach(r => state.expanded.add(r.m.key + "|" + r.qid));
    renderDossier();
  });
}

/* ── المحتوى الموسّع (تحت الصف) ── */
function expandedHtml(m, row) {
  const p = (row.score / (row.max || 10)) * 100;
  const crits = (row.criteria || []).map(c => {
    const cm = c.max || 2;
    const cp = (c.points / cm) * 100;
    const col = c.points >= cm ? "var(--ok)" : c.points > 0 ? "var(--primary)" : "var(--danger)";
    return `
      <div class="qexp-crit">
        <div>
          <div class="crit-label">${esc(c.label)}</div>
          <div class="crit-note">${esc(c.note || "")}</div>
        </div>
        <div class="crit-pts" style="color:${col}">${num(c.points, 1)}/${cm}</div>
        <div class="crit-bar"><i style="width:${cp}%;background:${col}"></i></div>
      </div>`;
  }).join("");

  const ans = (row.answer || "").trim();
  return `
  <div class="qexpanded">
    <div class="qexp-grid">
      <div>
        <div class="qexp-h">السؤال</div>
        <div class="qexp-prompt">${esc(row.prompt || "—")}</div>
        <div class="qexp-h" style="margin-top:18px">رد الموديل</div>
        <div class="qexp-answer ${ans ? "" : "empty"}">${ans ? esc(ans) : "— لم يُرجع الموديل أي نص —"}</div>
      </div>
      <div>
        <div class="qexp-h">المعايير الخمسة</div>
        ${crits}
        <div class="qexp-meta">
          <span>الدرجة <i>${num(row.score, 1)}/${num(row.max, 1)}</i></span>
          <span>النسبة <i>${pct(p, 0)}</i></span>
          <span>حروف <i>${row.chars ?? "—"}</i></span>
          <span>توكن <i>${row.tokens ?? "—"}</i></span>
          <span>ثانية <i>${num(row.seconds, 1)}</i></span>
        </div>
      </div>
    </div>
  </div>`;
}


/* ══════════ 09 · الأداء والبيئة ══════════ */
function renderPerf() {
  const rows = MODELS.map(m => {
    const p = m.perf || {};
    return { m, p };
  });

  const bestOf = key => {
    const vals = rows.map(r => r.p[key]).filter(v => typeof v === "number");
    return vals.length ? Math.max(...vals) : null;
  };
  const bTg = bestOf("tg_avg"), bReq = bestOf("req_avg"), bUp = bestOf("prompt_ms_avg");

  $("#perfTable").innerHTML = `
    <thead><tr>
      <th>الموديل</th><th>الوزن</th><th>طبقات GPU</th><th>توليد tok/s</th>
      <th>معالجة prompt tok/s</th><th>زمن الطلب (متوسط)</th><th>أول استجابة ms</th>
      <th>زمن التجهيز</th><th>ذاكرة العملية</th><th>ذروة VRAM</th><th>المدة الكلية</th>
    </tr></thead>
    <tbody>
      ${rows.map(({ m, p }) => `
        <tr>
          <td><span class="mname"><i style="background:${m.color}"></i>${esc(shortModel(m.name))}</span></td>
          <td class="num">${fmtBytes(m.bytes)}</td>
          <td class="num">${esc(m.fit?.ngl ?? "—")}/${esc(m.fit?.layers ?? "—")}</td>
          <td class="num ${p.tg_avg === bTg ? "best" : ""}">${num(p.tg_avg, 1)}</td>
          <td class="num">${num(p.pp_avg, 0)}</td>
          <td class="num ${p.req_avg === bReq ? "best" : ""}">${num(p.req_avg, 2)} ث</td>
          <td class="num ${p.prompt_ms_avg === bUp ? "best" : ""}">${num(p.prompt_ms_avg, 0)}</td>
          <td class="num">${num(p.startup, 1)} ث</td>
          <td class="num">${num(m.runtime?.peak_rss_mib, 0)} MiB</td>
          <td class="num">${num(m.runtime?.peak_vram_mib, 0)} MiB</td>
          <td class="num">${fmtDur(m.runtime?.seconds_total)}</td>
        </tr>`).join("")}
    </tbody>`;

  /* ── مرجع Gemini (عرض فقط) ── */
  const g = CFG.gemini || {};
  const axes = Object.entries(g.axes || {});
  $("#geminiCard").innerHTML = `
    <div class="gc-head">
      <span class="gc-name">🎯 ${esc(g.name || "Gemini 2.5 Pro")}</span>
      <span class="gc-badge">عرض فقط — لا يدخل في الحكم</span>
    </div>
    <div class="gc-note">${esc(g.note || "أرقام مرجعية من بنشماركات عامة، مش مقاسة على أسئلة امتحاننا.")}</div>
    <div class="gc-rows">
      ${axes.map(([k, a]) => {
        const v = a?.value ?? 0;
        const ours = MODELS.map(m => m.cats?.[k]?.percent ?? 0);
        const best = Math.max(...ours, v);
        return `
        <div class="gc-row" title="${esc(a?.why || "")}">
          <span class="gc-name-s">${esc(k)}</span>
          <div class="gc-track">
            <i style="width:${v}%;background:${best === v ? "rgba(242,166,90,.7)" : "rgba(237,231,220,.32)"}"></i>
          </div>
          <span class="gc-val">${num(v, 1)}%</span>
        </div>`;
      }).join("")}
    </div>
    <div class="gc-note" style="margin:14px 0 0;font-size:11px">
      المصدر: ${esc(g.source_model || "—")} · ${esc(g.source_date || "")}
    </div>`;

  /* ── الفوتر ── */
  const r = DATA.run;
  $("#foot").innerHTML = `
    <span>run ${esc(r.run_id)} · ${esc(r.exam_version)} · ${esc(r.platform || "")}</span>
    <span>${esc(r.device || "")} ${esc(r.runner_kind || "")} · ${esc(r.gpu || r.runner_gpu || "")} · ${esc(r.llama_version || "")}</span>`;
}

/* ══════════ 10 · INIT ══════════ */
function refresh() {
  renderScale();
  renderSpecCards();
  renderRadar();
  renderAxisCards();
  renderFilters();
  renderDossier();
}

function init() {
  renderTop();
  renderHero();
  renderPerf();
  renderExtra();
  renderStateChips();

  refresh();

  $("#fSearch").addEventListener("input", e => {
    state.q = e.target.value;
    renderDossier();
  });
  $("#drawerClose").addEventListener("click", closeDrawer);
  $("#scrim").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeDrawer();
  });
  $("#btnPrint").addEventListener("click", () => window.print());
  const refBtn = $("#show-gemini");
  if (refBtn) refBtn.addEventListener("click", () => {
    state.refVisible = !state.refVisible;
    renderTop();
    refresh();
  });
}

document.addEventListener("DOMContentLoaded", init);


/* ══════════ 05 · الميزة الإضافية + الـDrawer ══════════ */

/* ══════════ الميزة الإضافية (الاستكشافي) ══════════ */
function renderExtra() {
  /* ── الأقراص (كل موديل) ── */
  $("#extraDials").innerHTML = MODELS.map(m => {
    const p = m.profile || {};
    const on = state.extraFocus === m.key;
    const has = (p.answered || 0) > 0;
    return `
    <div class="dial ${on ? "active" : ""}" data-extra="${esc(m.key)}">
      <div class="dial-top">
        <span class="dial-name">${esc(shortModel(m.name))}</span>
        <span class="dial-score">${has ? num(p.total, 2) : "—"}</span>
      </div>
      <div class="dial-track"><i style="width:${has ? (p.total / p.max * 100) : 0}%"></i></div>
      <div class="dial-sub">${has ? `${p.answered}/${p.count} سؤال · ${pct(p.percent, 0)}` : "لم يُجب على الأسئلة الاستكشافية"}</div>
    </div>`;
  }).join("");

  $$(".dial", $("#extraDials")).forEach(d =>
    d.addEventListener("click", () => { state.extraFocus = d.dataset.extra; renderExtra(); }));

  const m = byId(state.extraFocus);
  const prof = m.profile || {};
  const qs = Object.values(prof.questions || {});

  /* ── المتوسطات حسب المجال ── */
  const doms = {};
  qs.forEach(q => {
    if (!q.answered) return;
    (doms[q.domain] = doms[q.domain] || []).push(q.score);
  });
  $("#extraDomains").innerHTML = Object.entries(doms).map(([d, arr]) => {
    const avg = arr.reduce((a, b) => a + b, 0) / arr.length;
    return `
      <div class="dom">
        <div class="dom-name">${esc(d)}</div>
        <div class="dom-bar"><i style="width:${avg / 20 * 100}%"></i></div>
        <div class="dom-val">${num(avg, 1)}/20 · ${arr.length} سؤال</div>
      </div>`;
  }).join("") || `<div class="empty-state">لا توجد إجابات استكشافية لهذا الموديل</div>`;

  /* ── بطاقات الأسئلة P1..P14 ── */
  $("#extraGrid").innerHTML = qs.map(q => {
    const crits = q.criteria || [];
    const bars = crits.map(c => {
      const p = (c.points / (c.max || 5)) * 100;
      return `<i title="${esc(c.label)} — ${num(c.points, 1)}/${c.max || 5}"><b style="width:${p}%"></b></i>`;
    }).join("");
    return `
    <article class="pcard" data-pq="${esc(q.id)}">
      <div class="pc-top">
        <span class="pc-id">${esc(q.id)}</span>
        <span class="pc-score">${num(q.score, 1)}<span style="font-size:11px;color:var(--faint)">/20</span></span>
      </div>
      <div class="pc-dom">${esc(q.domain || "")}</div>
      <div class="pc-crit">${bars}</div>
      <div class="pc-prompt">${esc(q.prompt || "")}</div>
    </article>`;
  }).join("") || `<div class="empty-state">لا توجد أسئلة استكشافية</div>`;

  $$(".pcard", $("#extraGrid")).forEach(c =>
    c.addEventListener("click", () => openProfileQuestion(c.dataset.pq)));
}

/* ══════════ الـDrawer ══════════ */
function openDrawer(html) {
  $("#drawerBody").innerHTML = html;
  $("#drawer").hidden = false;
  $("#scrim").hidden = false;
  document.body.style.overflow = "hidden";
}
function closeDrawer() {
  $("#drawer").hidden = true;
  $("#scrim").hidden = true;
  document.body.style.overflow = "";
}

function critHtml(c) {
  const cm = c.max || 2;
  const cp = (c.points / cm) * 100;
  const col = c.points >= cm ? "var(--ok)" : c.points > 0 ? "var(--primary)" : "var(--danger)";
  return `
    <div class="crit">
      <div>
        <div class="crit-label">${esc(c.label)}</div>
        <div class="crit-note">${esc(c.note || "")}</div>
      </div>
      <div class="crit-pts" style="color:${col}">${num(c.points, 1)}/${cm}</div>
      <div class="crit-bar"><i style="width:${cp}%;background:${col}"></i></div>
    </div>`;
}

function openQuestion(mk, qid) {
  const m = byId(mk);
  const row = (m.questions || {})[qid];
  if (!row) return;
  const p = (row.score / (row.max || 10)) * 100;
  const crits = (row.criteria || []).map(critHtml).join("");
  const ans = (row.answer || "").trim();

  openDrawer(`
    <div class="dr-head">
      <div class="dr-kicker">
        <span class="dr-qid">${esc(qid)}</span>
        <span class="dr-cat">${esc(row.category || "")}</span>
        <span class="dr-cat">${esc(m.name)}</span>
        ${row.empty ? `<span class="pill" style="color:var(--faint);border-color:var(--line-2)">رد فاضي</span>` : ""}
        ${row.finish ? `<span class="pill" style="color:var(--muted);border-color:var(--line)">finish: ${esc(row.finish)}</span>` : ""}
      </div>
      <div class="dr-title">${esc(row.title || "")}</div>
      ${row.why ? `<div class="dr-why">${esc(row.why)}</div>` : ""}
      <div class="dr-score">
        <b style="color:${scoreColor(p)}">${num(row.score, 1)}</b>
        <span>/ ${num(row.max, 1)} · ${pct(p, 0)}</span>
      </div>
      <div class="dr-meta">
        <span><i>${row.chars ?? "—"}</i> حرف</span>
        <span><i>${row.tokens ?? "—"}</i> توكن</span>
        <span><i>${num(row.seconds, 1)}</i> ثانية</span>
        <span><i>${row.passes ?? 1}</i> تمريرة</span>
      </div>
    </div>
    <div class="dr-sec">
      <div class="dr-sec-h">السؤال</div>
      <div class="dr-prompt">${esc(row.prompt || "—")}</div>
    </div>
    <div class="dr-sec">
      <div class="dr-sec-h">معايير التقييم (٥)</div>
      ${crits}
    </div>
    <div class="dr-sec">
      <div class="dr-sec-h">رد الموديل</div>
      <div class="dr-answer ${ans ? "" : "empty"}">${ans ? esc(ans) : "— لم يُرجع الموديل أي نص —"}</div>
    </div>
  `);
}

function openProfileQuestion(pid) {
  const m = byId(state.extraFocus);
  const q = (m.profile?.questions || {})[pid];
  if (!q) return;
  const crits = (q.criteria || []).map(critHtml).join("");

  openDrawer(`
    <div class="dr-head">
      <div class="dr-kicker">
        <span class="dr-qid">${esc(q.id)}</span>
        <span class="dr-cat">${esc(q.domain || "")}</span>
        <span class="dr-cat">${esc(m.name)}</span>
      </div>
      <div class="dr-title">${num(q.score, 1)} / ${num(q.max, 1)} · ${pct(q.percent, 0)}</div>
      <div class="dr-why">ميزة إضافية — لا تدخل في المجموع الأساسي ولا في الحكم</div>
    </div>
    <div class="dr-sec">
      <div class="dr-sec-h">السؤال</div>
      <div class="dr-prompt">${esc(q.prompt || "—")}</div>
    </div>
    <div class="dr-sec">
      <div class="dr-sec-h">النقاط المتوقعة</div>
      <div class="dr-prompt" style="font-size:13px;color:var(--muted)">${esc(q.expected || "—")}</div>
    </div>
    <div class="dr-sec">
      <div class="dr-sec-h">المعايير (٤)</div>
      ${crits}
    </div>
    <div class="dr-sec">
      <div class="dr-sec-h">رد الموديل</div>
      <div class="dr-answer">${esc(q.answer || "— لم يُجب —")}</div>
    </div>
  `);
}
"""

TEMPLATE = r"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>تقرير امتحان المساعد المصري — «مِحْيَر»</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;500;600;700;800&family=Almarai:wght@400;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>__CSS__</style>
</head>
<body>

<div class="grain" aria-hidden="true"></div>

<!-- ══════════════ TOP BAR ══════════════ -->
<header class="topbar">
  <div class="brand">
    <span class="brand-mark"></span>
    <div>
      <div class="brand-name">مِحْيَر</div>
      <div class="brand-sub">تقرير قياس النماذج · امتحان المساعد المصري</div>
    </div>
  </div>
  <div class="topbar-meta" id="topMeta"></div>
  <div class="topbar-actions">
    <div class="legend-chip" id="gates"><i class="sw sw-gate"></i>محور تحت حدّه الأدنى</div>
    <div class="legend-chip"><i class="sw sw-extra"></i>ميزة إضافية</div>
    <button class="ref-toggle exam-show-gemini" id="show-gemini" type="button" data-gem="on">🎯 المرجع</button>
    <button class="btn-ghost" id="btnPrint" type="button">طباعة / PDF</button>
  </div>
</header>

<main>

  <!-- ══════════════ HERO ══════════════ -->
  <section class="hero">
    <div class="hero-left">
      <div class="eyebrow" id="heroEyebrow">امتحان المساعد المصري</div>
      <h1 class="hero-title">من 100 نقطة، إلى <em>قرار</em>.</h1>
      <p class="hero-lede">
        ٣٣ سؤال مصحَّح حتمياً في ٨ محاور بأوزان، و١٤ سؤال استكشافي <b>بره</b> الحساب.
        كل رقم هنا <b>مقيس</b> — مفيش تقدير، مفيش مرجع بيشارك في الحكم.
      </p>
      <div class="hero-stats" id="heroStats"></div>
    </div>
    <aside class="hero-note">
      <div class="note-label">كيف بتقرأ التقرير</div>
      <ol class="note-list">
        <li><b>مقياس الحكم</b> — الدرجة الأساسية فقط (٠–١٠٠) هي اللي بتحدّد المستوى.</li>
        <li><b>⛔ محور تحت الحد</b> — معلومة للمراجعة، <b>مش</b> بتفرض مستوى تاني.</li>
        <li><b>🔎 الميزة الإضافية</b> — تقييم مستقل من ٢٠ (زي الماجستير: وجودها ميزة، غيابها ما بيخصمش).</li>
      </ol>
    </aside>
  </section>

  <!-- ══════════════ VERDICT SCALE ══════════════ -->
  <section class="panel" id="sec-scale">
    <div class="panel-head">
      <h2><span class="pn">01</span> مقياس الحكم</h2>
      <p class="panel-sub">الدرجة الأساسية /100 · الشرائح الخمسة كل ٢٠٪</p>
    </div>
    <div class="scale-wrap" id="scaleWrap"></div>
  </section>

  <!-- ══════════════ MODEL SPEC SHEETS ══════════════ -->
  <section class="panel" id="sec-models">
    <div class="panel-head">
      <h2><span class="pn">02</span> بطاقات الموديلات</h2>
      <p class="panel-sub">اضغط على أي بطاقة عشان تبعّدها في باقي الأقسام</p>
    </div>
    <div class="spec-grid" id="specGrid"></div>
  </section>

  <!-- ══════════════ AXIS COMPARISON ══════════════ -->
  <section class="panel" id="sec-axes">
    <div class="panel-head">
      <h2><span class="pn">03</span> المقارنة على المحاور</h2>
      <p class="panel-sub">٨ محاور · كل شريط = نسبة موديل · العلامة العمودية = الحد الأدنى</p>
    </div>
    <div class="axes-layout">
      <div class="radar-wrap panel-sub-panel" id="radar">
        <div class="radar-head">
          <span>شكل الأداء</span>
          <div class="radar-legend" id="radarLegend"></div>
        </div>
        <div id="radarHost" class="radar-host"></div>
        <div class="radar-hint">اضغط على <b>اسم أي موديل</b> في القائمة فوق عشان تخفيه من الرسم
          أو تظهره تاني — عشان تقارن بين اتنين بس.</div>
      </div>
      <div class="axis-cards" id="categories"></div>
    </div>
  </section>

  <!-- ══════════════ EXPLORATORY ══════════════ -->
  <section class="panel panel-extra" id="sec-extra">
    <div class="panel-head">
      <h2><span class="pn">04</span> الميزة الإضافية — الأسئلة الاستكشافية</h2>
      <p class="panel-sub">١٤ سؤال · تقييم من ٢٠ · <b>لا يدخل في المجموع ولا في الحكم</b></p>
    </div>
    <div class="extra-layout">
      <div class="extra-dials" id="extraDials"></div>
      <div class="extra-detail">
        <div class="extra-tabs" id="extraTabs"></div>
        <div class="extra-domains" id="extraDomains"></div>
        <div class="extra-grid" id="extraGrid"></div>
      </div>
    </div>
  </section>

  <!-- ══════════════ DOSSIER ══════════════ -->
  <section class="panel" id="sec-dossier">
    <div class="panel-head">
      <h2><span class="pn">05</span> ملف الأسئلة</h2>
      <p class="panel-sub">كل سؤال · درجته من ١٠ · المعايير الخمسة وأسبابها · اضغط للتفاصيل</p>
    </div>
    <div class="filters">
      <div class="chips" id="fModels"></div>
      <div class="chips" id="fCats"></div>
      <div class="chips" id="fStates"></div>
      <div class="search-box">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
        <input id="fSearch" type="search" placeholder="ابحث في السؤال أو الإجابة…" autocomplete="off">
      </div>
    </div>
    <div class="dossier-bar" id="dossierBar"></div>
    <div class="dossier" id="answers"></div>
  </section>

  <!-- ══════════════ PERF & ENV ══════════════ -->
  <section class="panel" id="sec-perf">
    <div class="panel-head">
      <h2><span class="pn">06</span> الأداء والبيئة</h2>
      <p class="panel-sub">كل الأرقام مقيسة فعلياً على GPU</p>
    </div>
    <div class="perf-layout">
      <div class="perf-table-wrap"><table class="perf-table" id="perfTable"></table></div>
      <div class="gemini-card" id="geminiCard"></div>
    </div>
  </section>

  <footer class="foot" id="foot"></footer>
</main>

<!-- ══════════════ DRAWER ══════════════ -->
<div class="drawer-scrim" id="scrim" hidden></div>
<aside class="drawer" id="drawer" hidden aria-label="تفاصيل السؤال">
  <button class="drawer-close" id="drawerClose" type="button" aria-label="إغلاق">✕</button>
  <div class="drawer-body" id="drawerBody"></div>
</aside>

<script id="payload" type="application/json">__DATA__</script>
<script>__JS__</script>
</body>
</html>
"""


# ═════════════════════════════════════════════════════════ Trim data
def _trim_questions(rows: dict | None) -> dict:
    """يقلّم صفوف الأسئلة للبيانات اللي التقرير محتاجها بس."""
    out: dict[str, dict] = {}
    for qid, r in (rows or {}).items():
        r = r or {}
        out[str(qid)] = {
            "id": str(qid),
            "title": r.get("title") or "",
            "prompt": r.get("prompt") or "",
            "why": r.get("why") or "",
            "category": r.get("category") or "",
            "category_name": r.get("category_name") or "",
            "score": r.get("score") or 0,
            "max": r.get("max") or 10,
            "percent": r.get("percent") or 0,
            "passes": r.get("passes") or 1,
            "answer": r.get("answer") or "",
            "chars": r.get("chars") or 0,
            "tokens": r.get("tokens") or 0,
            "seconds": r.get("seconds") or 0,
            "finish": r.get("finish") or "",
            "empty": bool(r.get("empty")),
            "health": r.get("health") or [],
            "criteria": [
                {
                    "label": c.get("label") or "",
                    "points": c.get("points") or 0,
                    "max": c.get("max") or 2,
                    "note": c.get("note") or "",
                }
                for c in (r.get("criteria") or [])
            ],
        }
    return out


def _trim_profile(prof: dict | None) -> dict:
    """يقلّم الأسئلة الاستكشافية (P1..P14) — تقييم مستقل من 20."""
    prof = prof or {}
    return {
        "total": prof.get("total") or 0,
        "max": prof.get("max") or 20,
        "percent": prof.get("percent") or 0,
        "count": prof.get("count") or 0,
        "answered": prof.get("answered") or 0,
        "note": prof.get("note") or "",
        "questions": {
            str(pid): {
                "id": str(pid),
                "domain": q.get("domain") or "",
                "prompt": q.get("prompt") or "",
                "expected": q.get("expected") or "",
                "answer": q.get("answer") or "",
                "score": q.get("score") or 0,
                "max": q.get("max") or 20,
                "percent": q.get("percent") or 0,
                "answered": bool(q.get("answered")),
                "criteria": [
                    {
                        "label": c.get("label") or "",
                        "points": c.get("points") or 0,
                        "max": c.get("max") or 5,
                        "note": c.get("note") or "",
                    }
                    for c in (q.get("criteria") or [])
                ],
            }
            for pid, q in (prof.get("questions") or {}).items()
        },
    }


def _categories(exam_cfg: dict | None) -> dict:
    """مواصفات المحاور الثمانية (اسم · اختصار · وزن · حد أدنى · أسئلة)."""
    raw = (exam_cfg or {}).get("categories") or {}
    if isinstance(raw, dict):
        items = list(raw.items())
    else:  # JSON الخام: categories=list
        items = [
            (str(r.get("key") or r.get("name") or ""), r)
            for r in raw
            if isinstance(r, dict)
        ]
    out: dict[str, dict] = {}
    for key, c in items:
        c = c or {}
        out[str(key)] = {
            "name": str(c.get("name") or key),
            "short": category_short(exam_cfg, str(key)) or str(c.get("name") or key),
            "weight": c.get("weight") or 0,
            "min_percent": c.get("min_percent") or 0,
            "questions": c.get("questions") or [],
        }
    return out


def _reference(exam_cfg: dict | None, categories: dict) -> dict:
    """مرجع Gemini 2.5 Pro — **عرض فقط**.

    الدرجة المحسوبة = مجموع(نسبة المحور × وزنه) / 100 — نفس طريقة المجموع
    الأساسي، عشان المقارنة تكون منصفة. بس ما بتدخلش في درجة ولا حكم أي موديل.
    """
    gem = ((exam_cfg or {}).get("references") or {}).get("gemini") or {}
    detail: dict[str, dict] = {}
    total = 0.0
    for key, row in (gem.get("axes") or {}).items():
        row = row or {}
        value = row.get("value") or 0
        detail[str(key)] = {"value": value, "why": row.get("why") or ""}
        total += float(value or 0) * float((categories.get(str(key)) or {}).get("weight") or 0)
    return {
        "name": gem.get("name") or "Gemini 2.5 Pro",
        "total": round(total / 100.0, 2),
        "color": "#9BB0D4",
        "axes": {k: v["value"] for k, v in detail.items()},
        "axes_detail": detail,
        "note": gem.get("note") or "",
        "source": gem.get("source_model") or "",
        "source_date": gem.get("source_date") or "",
        "kind": gem.get("kind") or "display_only",
    }


# ═════════════════════════════════════════════════════════ Build data
def build_data(
    results: list[dict] | None,
    exam_cfg: dict | None,
    run_meta: dict | None = None,
) -> dict:
    """يبني الـ payload اللي الـ JS بيقرأه (كل الأرقام من نتائج التشغيل)."""
    run = dict(run_meta or {})
    categories = _categories(exam_cfg)
    reference = _reference(exam_cfg, categories)
    settings = (exam_cfg or {}).get("settings") or {}

    models: list[dict] = []
    for i, m in enumerate(results or []):
        m = m or {}
        ex = m.get("exam") or {}
        rt = m.get("runtime") or {}
        perf = rt.get("perf") or {}
        fit = m.get("fit") or {}
        manifest = m.get("manifest") or {}
        status = str(m.get("status") or "ok")

        cats: dict[str, dict] = {}
        for key, c in (ex.get("categories") or {}).items():
            c = c or {}
            cats[str(key)] = {
                "percent": c.get("percent") or 0,
                "points": c.get("points") or 0,
                "score": c.get("score") or 0,
                "max": c.get("max") or 0,
                "failed_min": bool(c.get("failed_min")),
            }

        tg = perf.get("tg_tps") or {}
        pp = perf.get("pp_tps") or {}
        req = perf.get("request_seconds") or {}
        pms = perf.get("prompt_ms") or {}

        models.append(
            {
                "key": f"m{i}",
                "name": m.get("model") or "—",
                "full": m.get("model_full") or m.get("model") or "",
                "repo": manifest.get("repo") or "",
                "sha": (manifest.get("sha") or "")[:8],
                "license": manifest.get("license") or "",
                "quant": manifest.get("quant_chosen") or "",
                "bytes": manifest.get("total_bytes") or 0,
                "color": COLORS[i % len(COLORS)],
                "status": status,
                "error": str(m.get("error") or "") if status != "ok" else "",
                "total": ex.get("total") or 0,
                "max": ex.get("max") or 100,
                "verdict": ex.get("verdict") or ("" if status == "ok" else "فشل"),
                "verdict_note": ex.get("verdict_note") or "",
                "failed_categories": ex.get("failed_categories") or [],
                "cats": cats,
                "questions": _trim_questions(ex.get("questions") or {}),
                "profile": _trim_profile(ex.get("profile") or {}),
                "fit": {
                    "ngl": fit.get("ngl"),
                    "layers": fit.get("n_layers"),
                    "kv": fit.get("kv") or rt.get("kv"),
                    "ctx": fit.get("ctx") or rt.get("ctx"),
                    "threads": fit.get("threads") or rt.get("threads"),
                    "fit_class": fit.get("fit_class") or "",
                },
                "perf": {
                    "tg_avg": tg.get("avg"),
                    "tg_max": tg.get("max"),
                    "pp_avg": pp.get("avg"),
                    "req_avg": req.get("avg"),
                    "req_p95": req.get("p95"),
                    "prompt_ms_avg": pms.get("avg"),
                    "startup": perf.get("startup_seconds"),
                    "generated": perf.get("total_generated_tokens"),
                    "requests": perf.get("requests_count"),
                },
                "runtime": {
                    "seconds_total": rt.get("seconds_total"),
                    "peak_rss_mib": (rt.get("memory") or {}).get("peak_rss_mib"),
                    "peak_vram_mib": (rt.get("memory") or {}).get("peak_vram_mib"),
                    "device": rt.get("device") or "",
                    "gpu": rt.get("gpu_name") or "",
                    "llama_version": rt.get("llama_version") or "",
                },
            }
        )

    first_rt = ((results or [{}])[0] or {}).get("runtime") or {}
    requests = 0
    for m in models:
        value = (m.get("perf") or {}).get("requests")
        if isinstance(value, (int, float)):
            requests = max(requests, int(value))
    seconds = 0.0
    for m in models:
        value = (m.get("runtime") or {}).get("seconds_total")
        if isinstance(value, (int, float)):
            seconds += float(value)

    run_block = {
        "run_id": run.get("run_id") or "",
        "started_at": run.get("started_at") or "",
        "finished_at": run.get("finished_at") or now_iso(),
        "runner_label": runner_label(run),
        "runner_gpu": run.get("runner_gpu") or "",
        "runner_kind": run.get("runner_kind") or "",
        "platform": run.get("platform") or "—",
        "llama_version": run.get("llama_version") or first_rt.get("llama_version") or "",
        "temperature": settings.get("temperature"),
        "top_p": settings.get("top_p"),
        "seed": settings.get("seed"),
        "ctx": run.get("ctx") or settings.get("ctx_size"),
        "quant": run.get("quant_pattern") or "",
        "exam_version": run.get("exam_version") or (exam_cfg or {}).get("version") or "",
        "device": run.get("device") or first_rt.get("device") or "",
        "gpu": first_rt.get("gpu_name") or run.get("runner_gpu") or "",
        "requests_count": requests,
        "seconds_total": round(seconds, 2),
    }

    profile_count = 14
    prof = (exam_cfg or {}).get("profile")
    if isinstance(prof, list):
        profile_count = len(prof) or profile_count

    return {
        "run": run_block,
        "cfg": {
            "version": (exam_cfg or {}).get("version") or "",
            "settings": settings,
            "categories": categories,
            "gemini": {
                "name": reference["name"],
                "note": reference["note"],
                "source_model": reference["source"],
                "source_date": reference["source_date"],
                "axes": reference["axes_detail"],
            },
            "profile_count": profile_count,
        },
        "models": models,
        "ref": reference,
    }


# ═════════════════════════════════════════════════════════ Build HTML
def build_html(
    results: list[dict],
    exam_cfg: dict,
    run_meta: dict | None = None,
) -> str:
    """يبني صفحة HTML كاملة (ملف واحد مستقل)."""
    meta = infer_runner_meta(run_meta, results)
    meta.setdefault("finished_at", now_iso())
    if not meta.get("platform"):
        meta["platform"] = "—"

    data = build_data(results, exam_cfg, meta)
    payload = dump_json_for_html(data)

    return (
        TEMPLATE.replace("__CSS__", CSS)
        .replace("__JS__", JS)
        .replace("__DATA__", payload)
    )


def write_report(
    results: list[dict],
    path: str | Path,
    exam_cfg: dict,
    run_meta: dict | None = None,
) -> Path:
    """يكتب التقرير على القرص ويرجع المسار."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_html(results, exam_cfg, run_meta), encoding="utf-8")
    return p


__all__ = ["build_data", "build_html", "write_report"]
