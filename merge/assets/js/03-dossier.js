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
