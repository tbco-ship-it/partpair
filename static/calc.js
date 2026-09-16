(async function () {
  const base = document.querySelector('link[href$="static/style.css"]').getAttribute('href').replace('static/style.css', '');
  const data = await (await fetch(base + 'static/parts.json')).json();
  const RES = { '1080p': [45, 0.62], '1440p': [40, 0.60], '4k': [30, 0.50] };
  const TIERS = [450, 550, 650, 750, 850, 1000, 1200, 1600];
  const cpuSel = document.getElementById('cpu'), gpuSel = document.getElementById('gpu');
  const out = document.getElementById('result'), psuOut = document.getElementById('psu-result');
  const find = (arr, slug) => arr.find(x => x.slug === slug);
  const short = n => n.replace(/^(NVIDIA GeForce|AMD Radeon|AMD|Intel)\s+/, '');

  function bottleneck(cpu, gpu, res) {
    const [a, b] = RES[res], needed = a + b * gpu.s1440, ratio = cpu.game / needed;
    const side = ratio < 1 ? 'CPU' : 'GPU';
    const pct = Math.round((ratio < 1 ? 1 - ratio : 1 - 1 / ratio) * 100);
    const verdict = side === 'CPU' ? (pct <= 10 ? 'balanced' : pct <= 25 ? 'mild' : pct <= 40 ? 'moderate' : 'severe')
                                   : (pct <= 20 ? 'balanced' : pct <= 40 ? 'gpu-bound' : 'overkill');
    const LABELS = { balanced: 'balanced', mild: 'mild CPU bottleneck', moderate: 'moderate CPU bottleneck', severe: 'severe CPU bottleneck', 'gpu-bound': 'GPU-bound (normal)', overkill: 'CPU overkill' };
    return { side, pct, verdict, label: LABELS[verdict] };
  }
  function psu(cpu, gpu) {
    const load = cpu.tdp + gpu.tdp + 100;
    return { load, rec: TIERS.find(t => t >= load * 1.3) || 1600 };
  }
  function render() {
    const cpu = find(data.cpus, cpuSel.value), gpu = find(data.gpus, gpuSel.value);
    if (!cpu || !gpu) return;
    const href = base + 'bottleneck/' + cpu.slug + '-vs-' + gpu.slug + '/';
    if (out) {
      const res = (document.querySelector('input[name=res]:checked') || {}).value || '1440p';
      const r = bottleneck(cpu, gpu, res), p = psu(cpu, gpu);
      const msg = r.side === 'CPU'
        ? `The ${short(cpu.name)} holds the ${short(gpu.name)} back by about ${r.pct}% at ${res}.`
        : `The ${short(gpu.name)} is the limiting part at ${res}, which is the healthy direction. The CPU keeps ${r.pct}% in reserve.`;
      const dot = r.side === 'CPU' ? 50 - r.pct / 2 : 50 + r.pct / 2;
      out.innerHTML = `<section class="sheet ${r.verdict}"><div class="sheet-num"><span class="num">${r.pct}</span><span class="pct">%</span></div><p class="sheet-title">${r.side}-limited at ${res}. ${r.label.charAt(0).toUpperCase() + r.label.slice(1)}.</p><div class="beam" aria-hidden="true"><span class="beam-label">CPU</span><span class="beam-track"><span class="beam-dot" style="left:${dot}%"></span></span><span class="beam-label">GPU</span></div><p class="sheet-text">${msg} Suggested power supply: ${p.rec} W. <a href="${href}">See the full breakdown</a></p></section>`;
    }
    if (psuOut) {
      const p = psu(cpu, gpu);
      psuOut.innerHTML = `<section class="sheet balanced"><div class="sheet-num"><span class="num">${p.rec}</span><span class="pct">W</span></div><p class="sheet-title">Recommended power supply</p><p class="sheet-text">Estimated peak load ${p.load} W: CPU ${cpu.tdp} W, graphics card ${gpu.tdp} W, about 100 W for the rest. <a href="${href}">Bottleneck check for this pair</a></p></section>`;
    }
  }
  [cpuSel, gpuSel, ...document.querySelectorAll('input[name=res]')].forEach(el => el && el.addEventListener('change', render));
  render();
})();
