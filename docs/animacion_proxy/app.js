/* Motor de la animacion: dibuja el diagrama SVG, mueve los paquetes y sincroniza
   narracion, inspector de paquete, linea de tiempo, registro y configuracion. */
(function () {
  'use strict';

  const { scenes, COMPARE } = window.PROXY_DATA;
  const NS = 'http://www.w3.org/2000/svg';
  const $ = (s, r = document) => r.querySelector(s);
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const esc = t => String(t).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  const svgEl = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };
  const ease = t => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

  /* ------------------------------------------------------------------ */
  /* Estado global                                                      */
  /* ------------------------------------------------------------------ */
  const st = {
    scene: scenes[0], scenarioIdx: 0, steps: [], opts: {},
    playing: true, inStep: false, stepReq: false, speed: 1, loop: false,
    runId: 0, t0: performance.now(),
  };
  st.frozen = () => !st.playing && !st.inStep;

  /* ------------------------------------------------------------------ */
  /* Escenario SVG                                                      */
  /* ------------------------------------------------------------------ */
  class Stage {
    constructor(svg) { this.svg = svg; this.nodes = {}; this.links = {}; }

    load(scene) {
      this.svg.innerHTML = '';
      this.nodes = {}; this.links = {};
      this.gLinks = svgEl('g', {}, this.svg);
      this.gPk = svgEl('g', {}, this.svg);      // los paquetes van DETRAS de los nodos: salen "de dentro"
      this.gNodes = svgEl('g', {}, this.svg);
      this.gBub = svgEl('g', {}, this.svg);
      scene.nodes.forEach(n => this.addNode(n));
      scene.links.forEach(([a, b]) => {
        const A = this.nodes[a], B = this.nodes[b];
        this.links[a + '|' + b] = this.links[b + '|' + a] =
          svgEl('line', { class: 'link', x1: A.x, y1: A.y, x2: B.x, y2: B.y }, this.gLinks);
      });
    }

    addNode(n) {
      const g = svgEl('g', { class: 'node ' + n.kind }, this.gNodes);
      svgEl('rect', { x: n.x - n.w / 2, y: n.y - n.h / 2, width: n.w, height: n.h, rx: 11 }, g);
      const ix = n.x - n.w / 2 + 19;
      const ico = svgEl('text', { class: 'ico', x: ix, y: n.y + 7, 'text-anchor': 'middle' }, g); ico.textContent = n.icon;
      const tx = n.x - n.w / 2 + 38;
      const l = svgEl('text', { class: 'lbl', x: tx, y: n.y - 2 }, g); l.textContent = n.label;
      const s = svgEl('text', { class: 'sub', x: tx, y: n.y + 13 }, g); s.textContent = n.sub;
      const b = svgEl('text', { class: 'badge', x: n.x, y: n.y + n.h / 2 + 15 }, this.gNodes);
      this.nodes[n.id] = { ...n, g, badgeEl: b, sub: s, subText: n.sub };
    }

    badge(id, text, cls) { const n = this.nodes[id]; if (!n) return; n.badgeEl.textContent = text || ''; n.badgeEl.setAttribute('class', 'badge ' + (cls || '')); }

    down(id, isDown, text) {
      const n = this.nodes[id]; if (!n) return;
      n.g.classList.toggle('down', isDown);
      if (isDown) this.badge(id, text || 'DOWN', 'err'); else this.badge(id, text || '', 'ok');
    }

    fx(id, kind) {
      const n = this.nodes[id]; if (!n) return;
      const c = 'fx-' + kind; n.g.classList.add(c);
      setTimeout(() => n.g.classList.remove(c), 1400);
    }

    active(id, on) { const n = this.nodes[id]; if (n) n.g.classList.toggle('active', on); }

    link(a, b, cls) {
      const l = this.links[a + '|' + b]; if (!l) return;
      l.setAttribute('class', 'link' + (cls ? ' ' + cls : ''));
    }
    linkOn(a, b, on) { const l = this.links[a + '|' + b]; if (l) l.classList.toggle('on', on); }

    clearPackets() { this.gPk.innerHTML = ''; this.gBub.innerHTML = ''; }

    /* animacion con tiempo propio: respeta pausa, velocidad y reinicios */
    animate(ms, fn, token) {
      return new Promise(res => {
        let acc = 0, last = performance.now();
        const tick = now => {
          if (token !== st.runId) return res();
          const dt = now - last; last = now;
          if (!st.frozen()) acc += dt * st.speed;
          fn(Math.min(1, acc / ms));
          if (acc >= ms) return res();
          requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });
    }

    async move(a, b, o, token) {
      const A = this.nodes[a], B = this.nodes[b];
      const dx = B.x - A.x, dy = B.y - A.y, len = Math.hypot(dx, dy) || 1;
      const px = (-dy / len) * 11, py = (dx / len) * 11;       // carril lateral: ida y vuelta no se superponen
      const g = svgEl('g', { class: 'pk ' + o.kind }, this.gPk);
      const r = svgEl('rect', { rx: 7, height: 22 }, g);
      const t = svgEl('text', {}, g); t.textContent = o.label;
      const w = t.getComputedTextLength() + 18;
      r.setAttribute('width', w); r.setAttribute('x', -w / 2); r.setAttribute('y', -11);
      const dur = o.dur || 1500;
      await this.animate(dur, p => {
        const e = ease(p);
        g.setAttribute('transform', `translate(${A.x + dx * e + px},${A.y + dy * e + py})`);
      }, token);
      g.remove();
    }

    bubble(id, text, kind) {
      const n = this.nodes[id];
      const lines = String(text).split('\n');
      const g = svgEl('g', { class: 'bub ' + (kind || 'ctl') }, this.gBub);
      const r = svgEl('rect', { rx: 9 }, g);
      const texts = lines.map(line => { const t = svgEl('text', {}, g); t.textContent = line; return t; });
      let w = 0; texts.forEach(t => { w = Math.max(w, t.getComputedTextLength()); });
      w += 20; const h = lines.length * 15 + 10;
      const cx = Math.max(w / 2 + 6, Math.min(1000 - w / 2 - 6, n.x));
      const below = n.y < 90;
      const top = below ? n.y + n.h / 2 + 24 : n.y - n.h / 2 - 8 - h;
      r.setAttribute('x', cx - w / 2); r.setAttribute('y', top); r.setAttribute('width', w); r.setAttribute('height', h);
      texts.forEach((t, i) => { t.setAttribute('x', cx); t.setAttribute('y', top + 17 + i * 15); });
      return () => g.remove();
    }
  }

  const stage = new Stage($('#stage'));

  /* ------------------------------------------------------------------ */
  /* Paneles                                                            */
  /* ------------------------------------------------------------------ */
  function renderIntro() {
    const s = st.scene;
    $('#intro').innerHTML = `<h2>${esc(s.title)}</h2><p>${esc(s.summary)}</p>` +
      `<div class="tags">${s.tags.map(t => `<span class="tag">${esc(t)}</span>`).join('')}</div>`;
  }

  function renderTabs() {
    $('#tabs').innerHTML = scenes.map(s =>
      `<button class="tab" role="tab" data-id="${s.id}" aria-selected="${s === st.scene}">${esc(s.tab)}</button>`).join('');
  }

  function renderScenarioChips() {
    $('#scenarios').innerHTML = st.scene.scenarios.map((c, i) =>
      `<button class="chip" data-i="${i}" aria-pressed="${i === st.scenarioIdx}">${esc(c.name)}</button>`).join('');
  }

  function renderOptions() {
    const box = $('#options'); box.innerHTML = '';
    const opts = st.scene.options || [];
    const isLb = st.scene.scenarios[st.scenarioIdx].name === 'Repartir peticiones';
    if (!opts.length || !isLb) return;
    const cur = st.opts[st.scene.id] || (st.opts[st.scene.id] = {});
    opts.forEach(o => {
      if (cur[o.id] === undefined) cur[o.id] = o.def;
      if (o.type === 'select') {
        const l = document.createElement('label'); l.textContent = o.label + ' ';
        const sel = document.createElement('select');
        o.values.forEach(([v, t]) => { const op = new Option(t, v); op.selected = cur[o.id] === v; sel.add(op); });
        sel.onchange = () => { cur[o.id] = sel.value; loadScenario(st.scenarioIdx); };
        l.appendChild(sel); box.appendChild(l);
      } else {
        const wrap = document.createElement('span'); wrap.textContent = o.label + ': ';
        o.values.forEach(([v, t]) => {
          const l = document.createElement('label');
          const cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = cur[o.id].includes(v);
          cb.onchange = () => { cur[o.id] = cb.checked ? [...cur[o.id], v] : cur[o.id].filter(x => x !== v); loadScenario(st.scenarioIdx); };
          l.append(cb, ' ' + t); wrap.appendChild(l);
        });
        box.appendChild(wrap);
      }
    });
  }

  function renderCode(hl) {
    const s = st.scene;
    $('#codeTitle').textContent = s.codeTitle;
    const marks = hl || [];
    $('#code').innerHTML = s.code.map(line => {
      const on = marks.some(m => line.includes(m));
      const cm = line.trim().startsWith('#');
      return `<span class="${on ? 'hl' : ''}${cm ? ' cm' : ''}">${esc(line) || ' '}</span>`;
    }).join('');
    const first = $('#code .hl'); if (first) first.scrollIntoView({ block: 'nearest' });
  }

  function renderConcepts() {
    $('#concepts').innerHTML = st.scene.concepts.map(c =>
      `<div class="concept"><b>${esc(c.t)}</b><span>${esc(c.d)}</span></div>`).join('');
  }

  function renderCompare() {
    const idx = st.scene.cmp;
    $('#cmp').innerHTML = '<thead><tr>' + COMPARE.head.map(h => `<th>${esc(h)}</th>`).join('') + '</tr></thead><tbody>' +
      COMPARE.rows.map((r, i) => `<tr class="${i === idx ? 'cur' : ''}">${r.map(c => `<td>${esc(c)}</td>`).join('')}</tr>`).join('') + '</tbody>';
  }

  function renderTimeline() {
    $('#timeline').innerHTML = st.steps.map((s, i) => {
      const txt = s.from ? `${stage.nodes[s.from].label} → ${stage.nodes[s.to].label}: ${s.label}` : `${stage.nodes[s.at].label}: ${s.bubble.replace(/\n/g, ' · ')}`;
      return `<li data-i="${i}">${esc(txt)}</li>`;
    }).join('');
  }

  function mark(i) {
    document.querySelectorAll('#timeline li').forEach((li, k) => {
      li.classList.toggle('done', k < i); li.classList.toggle('now', k === i);
    });
    const now = $('#timeline li.now'); if (now) now.scrollIntoView({ block: 'nearest' });
  }

  function narrate(s, i) {
    const who = s.from ? `${stage.nodes[s.from].label} → ${stage.nodes[s.to].label}` : stage.nodes[s.at].label + ' decide';
    $('#narr').innerHTML = `<span class="from">Paso ${i + 1} de ${st.steps.length} · ${esc(who)}</span><span class="n">${esc(s.from ? s.label : s.bubble.replace(/\n/g, ' · '))}</span><br>${esc(s.text)}`;
    $('#inspector').textContent = s.h && s.h.length ? s.h.join('\n') : s.from ? '(sin contenido relevante en este paso)' : '(decisión interna: no viaja ningún paquete)';
  }

  function logLine(s) {
    const t = ((performance.now() - st.t0) / 1000).toFixed(1).padStart(5, '0');
    const where = s.from ? `${stage.nodes[s.from].label} → ${stage.nodes[s.to].label}` : stage.nodes[s.at].label;
    const msg = s.from ? s.label : s.bubble.replace(/\n/g, ' · ');
    const d = document.createElement('div');
    d.innerHTML = `<span class="t">${t}s</span> <span class="k-${s.kind}">${esc(where)}  ${esc(msg)}</span>`;
    const box = $('#log'); box.appendChild(d); box.scrollTop = box.scrollHeight;
  }

  /* ------------------------------------------------------------------ */
  /* Ejecucion                                                          */
  /* ------------------------------------------------------------------ */
  async function playStep(s, i, token) {
    mark(i); narrate(s, i); renderCode(s.hl); logLine(s);
    if (s.pre) s.pre(stage);
    if (s.from) {
      stage.linkOn(s.from, s.to, true); stage.active(s.from, true);
      await stage.move(s.from, s.to, { kind: s.kind, label: s.label, dur: s.dur || 1500 }, token);
      stage.linkOn(s.from, s.to, false); stage.active(s.from, false);
      if (token !== st.runId) return;
      stage.active(s.to, true); setTimeout(() => stage.active(s.to, false), 450);
    } else {
      stage.active(s.at, true);
      const off = stage.bubble(s.at, s.bubble, s.kind);
      await stage.animate(s.dur || 2300, () => {}, token);
      off(); stage.active(s.at, false);
      if (token !== st.runId) return;
    }
    if (s.post) s.post(stage);
    await stage.animate(180, () => {}, token);
  }

  async function runLoop(token, from) {
    for (let i = from; i < st.steps.length; i++) {
      while (token === st.runId && !st.playing && !st.stepReq) await sleep(40);
      if (token !== st.runId) return;
      st.stepReq = false; st.inStep = true;
      await playStep(st.steps[i], i, token);
      st.inStep = false;
      if (token !== st.runId) return;
    }
    mark(st.steps.length);
    $('#narr').insertAdjacentHTML('beforeend', '<br><br><span class="from">✔ Escenario completo. Elige otro o pulsa Reiniciar.</span>');
    if (st.loop) { await sleep(1200); if (token === st.runId) loadScenario(st.scenarioIdx); return; }
    st.playing = false; syncPlay();
  }

  function syncPlay() { $('#btnPlay').textContent = st.playing ? '⏸ Pausar' : '▶ Reproducir'; }

  function loadScenario(i) {
    st.runId++; st.inStep = false; st.stepReq = false; st.scenarioIdx = i; st.t0 = performance.now();
    const sc = st.scene.scenarios[i];
    stage.load(st.scene);
    const built = sc.build(st.opts[st.scene.id] || {});
    st.steps = built.steps;
    if (built.setup) built.setup(stage);
    renderScenarioChips(); renderOptions(); renderTimeline(); renderCode([]);
    $('#log').innerHTML = ''; $('#inspector').textContent = ''; $('#narr').innerHTML = '';
    st.playing = true; syncPlay();
    runLoop(st.runId, 0);
  }

  function loadScene(id) {
    st.scene = scenes.find(s => s.id === id);
    renderTabs(); renderIntro(); renderConcepts(); renderCompare();
    loadScenario(0);
  }

  /* ------------------------------------------------------------------ */
  /* Eventos                                                            */
  /* ------------------------------------------------------------------ */
  $('#tabs').addEventListener('click', e => { const b = e.target.closest('.tab'); if (b) loadScene(b.dataset.id); });
  $('#scenarios').addEventListener('click', e => { const b = e.target.closest('.chip'); if (b) loadScenario(+b.dataset.i); });
  $('#btnPlay').onclick = () => { st.playing = !st.playing; syncPlay(); };
  $('#btnStep').onclick = () => { st.playing = false; syncPlay(); st.stepReq = true; };
  $('#btnReset').onclick = () => loadScenario(st.scenarioIdx);
  $('#speed').oninput = e => { st.speed = +e.target.value; $('#speedOut').textContent = st.speed + '×'; };
  $('#loop').onchange = e => { st.loop = e.target.checked; };
  document.addEventListener('keydown', e => {
    if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName)) return;
    if (e.code === 'Space') { e.preventDefault(); $('#btnPlay').click(); }
    if (e.key === 'ArrowRight') $('#btnStep').click();
    if (e.key === 'r') $('#btnReset').click();
  });

  loadScene(scenes[0].id);
})();
