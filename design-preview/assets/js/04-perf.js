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
