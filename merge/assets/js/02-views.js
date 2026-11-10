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
