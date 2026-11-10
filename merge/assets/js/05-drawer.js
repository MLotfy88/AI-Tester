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
