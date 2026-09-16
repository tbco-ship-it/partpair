(async function () {
  const cssHref = document.querySelector('link[href*="static/style.css"]').getAttribute('href');
  const v = (cssHref.match(/\?v=([^&]+)/) || [])[1] || '';
  const base = cssHref.replace(/static\/style\.css.*$/, '');
  const data = await (await fetch(base + 'static/parts.json?v=' + v)).json();
  const RES = { '1080p': [45, 0.62], '1440p': [40, 0.60], '4k': [30, 0.50] };
  const TIERS = [450, 550, 650, 750, 850, 1000, 1200, 1600];
  const LABELS = { balanced: 'balanced', mild: 'mild CPU bottleneck', moderate: 'moderate CPU bottleneck', severe: 'severe CPU bottleneck', 'gpu-bound': 'GPU-bound (normal)', overkill: 'CPU overkill' };
  const out = document.getElementById('result'), psuOut = document.getElementById('psu-result');
  const short = n => n.replace(/^(NVIDIA GeForce|AMD Radeon|AMD|Intel)\s+/, '');
  const norm = s => s.toLowerCase().replace(/[^a-z0-9]/g, '');
  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);

  // Typeahead pickers. Each keeps its chosen part on the input element.
  const picked = {};
  function picker(input) {
    const kind = input.dataset.kind, list = data[kind], menu = document.getElementById(input.id + '-menu');
    let items = [], active = -1;
    const remembered = localStorage.getItem('pcpairs.' + kind);
    const initial = list.find(x => x.slug === remembered) || list[Math.min(6, list.length - 1)];
    choose(initial, false);

    function choose(part, fire = true) {
      picked[kind] = part; input.value = part.name; input.dataset.slug = part.slug;
      localStorage.setItem('pcpairs.' + kind, part.slug);
      close(); if (fire) render();
    }
    function open(q) {
      const nq = norm(q);
      const tokens = x => x.name.toLowerCase().split(/[\s-]+/).map(norm);
      items = (nq ? list.filter(x => norm(x.name).includes(nq))
                      .sort((a, b) => rank(a) - rank(b)) : list).slice(0, 8);
      function rank(x) { const t = tokens(x); if (t.includes(nq)) return 0; if (t.some(k => k.startsWith(nq))) return 1; return 2; }
      menu.innerHTML = items.length
        ? items.map((x, i) => `<li role="option" data-i="${i}" ${i === active ? 'aria-selected="true"' : ''}>${x.name}</li>`).join('')
        : '<li class="empty">No match. Try a model number like 5600 or 4070.</li>';
      menu.hidden = false; input.setAttribute('aria-expanded', 'true');
    }
    function close() { menu.hidden = true; active = -1; input.setAttribute('aria-expanded', 'false'); }

    // Typing replaces the current pick: select everything on focus/click so the user never edits inside the old name.
    input.addEventListener('focus', () => { setTimeout(() => input.select(), 0); open(''); });
    input.addEventListener('click', () => { if (picked[kind] && input.value === picked[kind].name) input.select(); });
    input.addEventListener('input', () => { active = -1; open(input.value); });
    input.addEventListener('keydown', e => {
      if (menu.hidden) return;
      if (e.key === 'ArrowDown') { active = Math.min(active + 1, items.length - 1); open(input.value); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { active = Math.max(active - 1, 0); open(input.value); e.preventDefault(); }
      else if (e.key === 'Enter') { if (items[active >= 0 ? active : 0]) choose(items[active >= 0 ? active : 0]); e.preventDefault(); }
      else if (e.key === 'Escape') { close(); input.value = picked[kind].name; }
    });
    menu.addEventListener('mousedown', e => { const li = e.target.closest('li[data-i]'); if (li) { choose(items[+li.dataset.i]); e.preventDefault(); } });
    input.addEventListener('blur', () => setTimeout(() => { close(); if (picked[kind]) input.value = picked[kind].name; }, 120));
  }

  function bottleneck(cpu, gpu, res) {
    const [a, b] = RES[res], needed = a + b * gpu.s1440, ratio = cpu.game / needed;
    const side = ratio < 1 ? 'CPU' : 'GPU';
    const pct = Math.round((ratio < 1 ? 1 - ratio : 1 - 1 / ratio) * 100);
    const verdict = side === 'CPU' ? (pct <= 10 ? 'balanced' : pct <= 25 ? 'mild' : pct <= 40 ? 'moderate' : 'severe')
                                   : (pct <= 20 ? 'balanced' : pct <= 40 ? 'gpu-bound' : 'overkill');
    return { side, pct, verdict, label: LABELS[verdict] };
  }
  function psu(cpu, gpu) { const load = cpu.tdp + gpu.tdp + 100; return { load, rec: TIERS.find(t => t >= load * 1.3) || 1600 }; }


  // Count-up on the headline number (skipped when the user prefers reduced motion).
  function countUp(el) {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const target = parseFloat(el.textContent.replace(/[^0-9.]/g, '')); if (!isFinite(target)) return;
    const fmt = el.textContent.includes(',') ? n => Math.round(n).toLocaleString('ko-KR') : n => String(Math.round(n));
    const t0 = performance.now(), dur = 420;
    (function step(t) { const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3); el.textContent = fmt(target * e); if (k < 1) requestAnimationFrame(step); })(t0);
  }

  function render() {
    const cpu = picked.cpus, gpu = picked.gpus;
    if (!cpu || !gpu) return;
    const href = base + 'bottleneck/' + cpu.slug + '-vs-' + gpu.slug + '/';
    if (out) {
      const res = (document.querySelector('input[name=res]:checked') || {}).value || '1440p';
      const r = bottleneck(cpu, gpu, res), p = psu(cpu, gpu);
      const even = r.pct < 3;
      const title = even ? `Evenly matched at ${res}.` : r.verdict === 'balanced' ? `Balanced at ${res}.` : `${r.side}-limited at ${res}. ${cap(r.label)}.`;
      const msg = even ? `Neither part waits on the other at ${res}.`
        : r.verdict === 'balanced' ? `Well matched at ${res}. The ${r.side === 'CPU' ? short(cpu.name) : short(gpu.name)} is the slightly busier part, by about ${r.pct}%.`
        : r.side === 'CPU' ? `The ${short(cpu.name)} holds the ${short(gpu.name)} back by about ${r.pct}% at ${res}.`
        : `The ${short(gpu.name)} is the limiting part at ${res}, which is the healthy direction. The CPU keeps ${r.pct}% in reserve.`;
      let next = '';
      if (r.side === 'CPU' && r.pct > 10) next = `<a class="next" href="${base}best-cpu-for/${gpu.slug}/">See processors that fix this</a>`;
      else if (r.side === 'GPU' && r.pct > 25) next = `<a class="next" href="${base}best-gpu-for/${cpu.slug}/">See cards that use this CPU fully</a>`;
      out.innerHTML = `<section class="sheet ${r.verdict}"><p class="sheet-label">Bottleneck at ${res}</p><div class="sheet-num"><span class="num">${r.pct}</span><span class="pct">%</span></div><p class="sheet-title">${title}</p><div class="beam ${r.side.toLowerCase()}" role="img" aria-label="${r.side} is the limiting part by ${r.pct} percent"><span class="beam-label">CPU</span><span class="beam-track"><span class="beam-fill" style="width:${r.pct / 2}%"></span></span><span class="beam-label">GPU</span></div><p class="sheet-text">${msg} Suggested power supply: ${p.rec} W.</p><p class="sheet-actions">${next}<a class="next" href="${href}">Full breakdown for this pair</a></p></section>`;
    }
    if (psuOut) {
      const p = psu(cpu, gpu);
      psuOut.innerHTML = `<section class="sheet balanced"><p class="sheet-label">Recommended power supply</p><div class="sheet-num"><span class="num">${p.rec}</span><span class="pct">W</span></div><p class="sheet-title">Recommended power supply</p><p class="sheet-text">Estimated peak load ${p.load} W: CPU ${cpu.tdp} W, graphics card ${gpu.tdp} W, about 100 W for the rest.</p><p class="sheet-actions"><a class="next" href="${href}">Bottleneck check for this pair</a></p></section>`;
    }
    document.querySelectorAll('.sheet-num .num').forEach(countUp);
  }

  document.addEventListener('click', e => {
    const a = e.target.closest('a.next'); if (!a) return;
    if (typeof gtag === 'function') gtag('event', 'next_action', { label: a.textContent.trim(), href: a.getAttribute('href') });
  });
  document.querySelectorAll('input.pick').forEach(picker);
  document.querySelectorAll('input[name=res]').forEach(el => el.addEventListener('change', render));
  render();
})();
