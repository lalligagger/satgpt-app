/* SatGPT demo replayer: replays a recorded conversation (data/transcript.json) and lets the
   visitor explore the recorded Sentinel-2 rasters (data/rasters/*.png + sidecar JSON) client-side.
   Only its own files and the Leaflet/CartoDB CDN assets are ever fetched. */
(() => {
  'use strict';

  const DATA = 'data/';
  const REPO_URL = 'https://github.com/lalligagger/satgpt-app';
  // Shown when a typed message matches none of the recorded steps. {prompts} becomes the list of recorded
  // prompts and {repo} the repository link. Edit freely.
  const DEMO_REPLY = "This is a recorded demo, so I can only replay the conversation that was captured: no live " +
    "model or STAC search is behind this page. Try one of the recorded prompts, or just name what you want to see " +
    "(search, footprints, cloud cover, images, or an index like NDVI):\n{prompts}\n" +
    "To run SatGPT live with your own OpenAI key, clone the repository: {repo}";
  const $ = (id) => document.getElementById(id);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // ------------------------------------------------------------------ colormaps
  const CMAPS = {
    viridis: ['#440154', '#482475', '#414487', '#355f8d', '#2a788e', '#21918c', '#22a884', '#44bf70', '#7ad151', '#bddf26', '#fde725'],
    magma: ['#000004', '#140e36', '#3b0f70', '#641a80', '#8c2981', '#b73779', '#de4968', '#f7705c', '#fe9f6d', '#fecf92', '#fcfdbf'],
    inferno: ['#000004', '#160b39', '#420a68', '#6a176e', '#932667', '#bc3754', '#dd513a', '#f37819', '#fca50a', '#f6d746', '#fcffa4'],
    plasma: ['#0d0887', '#41049d', '#6a00a8', '#8f0da4', '#b12a90', '#cc4778', '#e16462', '#f2844b', '#fca636', '#fcce25', '#f0f921'],
    cividis: ['#00224e', '#123570', '#3b496c', '#575d6d', '#707173', '#8a8678', '#a59c74', '#c3b369', '#e1cc55', '#fee838'],
    gray: ['#000000', '#ffffff'],
    RdYlGn: ['#a50026', '#d73027', '#f46d43', '#fdae61', '#fee08b', '#ffffbf', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'],
    RdBu: ['#67001f', '#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#f7f7f7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac', '#053061'],
    Spectral: ['#9e0142', '#d53e4f', '#f46d43', '#fdae61', '#fee08b', '#ffffbf', '#e6f598', '#abdda4', '#66c2a5', '#3288bd', '#5e4fa2'],
    BrBG: ['#543005', '#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#f5f5f5', '#c7eae5', '#80cdc1', '#35978f', '#01665e', '#003c30'],
  };
  const DEFAULT_CMAP = { NDVI: 'RdYlGn', SAVI: 'RdYlGn', EVI: 'RdYlGn', NDMI: 'RdYlGn', NBR: 'RdYlGn', GNDVI: 'RdYlGn',
    NDWI: 'RdBu', MNDWI: 'RdBu', NDBI: 'magma', NBRSWIR: 'inferno' };
  const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const lutCache = new Map();
  function buildLut(name, reverse) {
    const key = name + (reverse ? '-r' : '');
    if (lutCache.has(key)) return lutCache.get(key);
    let stops = (CMAPS[name] || CMAPS.viridis).map(hex);
    if (reverse) stops = stops.slice().reverse();
    const lut = new Uint8Array(256 * 3);
    for (let i = 0; i < 256; i++) {
      const t = (i / 255) * (stops.length - 1);
      const k = Math.min(Math.floor(t), stops.length - 2);
      const f = t - k;
      for (let c = 0; c < 3; c++) lut[i * 3 + c] = Math.round(stops[k][c] * (1 - f) + stops[k + 1][c] * f);
    }
    lutCache.set(key, lut);
    return lut;
  }

  // ------------------------------------------------------------------ state
  const S = {
    transcript: null, meta: null, items: null,
    map: null, tiles: null, bboxRect: null, footprints: null, overlay: null,
    turn: 0, playing: false, skip: false,
    imagery: false, date: null, layer: 'RGB', cmap: 'RdYlGn', reverse: false, lo: 2, hi: 98, opacity: 1,
    maskClouds: false, scl: new Map(), currentScl: null,
    rasters: new Map(), current: null, charts: [],
  };

  // ------------------------------------------------------------------ boot
  async function boot() {
    const [transcript, meta, items] = await Promise.all([
      fetch(DATA + 'transcript.json').then((r) => r.json()),
      fetch(DATA + 'metadata.json').then((r) => r.json()),
      fetch(DATA + 'items.geojson').then((r) => r.json()),
    ]);
    S.transcript = transcript; S.meta = meta; S.items = items;
    S.date = meta.recorded_dates[0];

    const badge = $('mode-badge');
    if (transcript.mode === 'llm') { badge.textContent = `recorded with ${transcript.model || 'an LLM'}`; badge.classList.add('llm'); }
    else badge.textContent = 'recorded without an LLM · replies canned';
    badge.title = transcript.note || '';
    $('recorded-at').textContent = ` Recorded ${String(transcript.recorded_at).slice(0, 10)} (${transcript.mode} mode).`;

    initMap();
    initSteps();
    initChatForm();
    initImagery();
    $('chart-panel').hidden = true;
    S.charts.push($('chart'));
    renderCharts();
  }

  // ------------------------------------------------------------------ map
  function initMap() {
    S.map = L.map('map', { zoomControl: true, attributionControl: true }).setView([47.6, -122.34], 10);
    // CartoDB's basemaps.cartocdn.com tiles now watermark "API KEY REQUIRED" without a key (2026), so this
    // uses the OpenStreetMap tiles the original app's viewer used (hv.element.tiles.OSM / MapManager.tile_url).
    S.tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(S.map);
    // Rasters sit above the footprint polygons (overlayPane is z 400) and the bbox outline above both.
    S.map.createPane('imagery').style.zIndex = 410;
    S.map.createPane('outline').style.zIndex = 420;
    // The map's box changes between the two-column and stacked layouts; keep Leaflet's size in sync.
    if (window.ResizeObserver) new ResizeObserver(() => S.map.invalidateSize()).observe($('map'));
    S.map.on('mousemove', onMouseMove);
    S.map.on('mouseout', () => { $('cursor-readout').textContent = 'hover the map for a value'; });
  }

  function showBbox(b) {
    if (S.bboxRect) S.bboxRect.remove();
    const bounds = [[b.south, b.west], [b.north, b.east]];
    S.bboxRect = L.rectangle(bounds, { color: '#2563eb', weight: 2, fill: false, className: 'bbox-rect', pane: 'outline' }).addTo(S.map);
    S.map.fitBounds(bounds, { padding: [20, 20] });
  }

  function showFootprints() {
    if (S.footprints) S.footprints.remove();
    S.footprints = L.geoJSON(S.items, {
      style: () => ({ color: '#d97706', weight: 1.5, fillColor: '#f59e0b', fillOpacity: 0.05 }),
      onEachFeature: (f, l) => {
        const p = f.properties;
        l.bindPopup(`<b>${p.id}</b><br>${String(p.datetime).slice(0, 19).replace('T', ' ')} UTC<br>` +
          `cloud cover ${Number(p['eo:cloud_cover']).toFixed(1)} % · ${p.platform || ''}<br>${p['grid:code'] || ''}`);
      },
    }).addTo(S.map);
  }

  function clearMap() {
    for (const k of ['bboxRect', 'footprints', 'overlay']) { if (S[k]) { S[k].remove(); S[k] = null; } }
    S.map.setView([47.6, -122.34], 10);
  }

  // ------------------------------------------------------------------ chat
  const chat = () => $('chat');
  function scrollChat() { const c = chat(); c.scrollTop = c.scrollHeight; }
  function bubble(cls, who, text, note) {
    const d = document.createElement('div');
    d.className = 'msg ' + cls;
    const w = document.createElement('span'); w.className = 'who'; w.textContent = who;
    const t = document.createElement('span'); t.className = 'txt'; t.textContent = text || '';
    d.append(w, t);
    if (note) { const n = document.createElement('span'); n.className = 'note'; n.textContent = note; d.append(n); }
    chat().append(d); scrollChat();
    return t;
  }
  function fmtArgs(args) {
    if (!args || typeof args !== 'object' || !Object.keys(args).length) return '';
    return Object.entries(args).map(([k, v]) => `${k}=${typeof v === 'string' ? JSON.stringify(v) : v}`).join(', ');
  }
  function addToolBlock(call) {
    const det = document.createElement('details');
    det.className = 'tool'; det.open = true;
    const sum = document.createElement('summary');
    const name = document.createElement('span');
    let sig = `${call.name}(${fmtArgs(call.arguments)})`;
    if (sig.length > 64) sig = sig.slice(0, 61) + '…)';
    name.textContent = '⚙ ' + sig;
    const state = document.createElement('span'); state.className = 'state'; state.textContent = 'running…';
    sum.append(name, state);
    const body = document.createElement('div'); body.className = 'body';
    const la = document.createElement('span'); la.className = 'lbl'; la.textContent = 'arguments';
    const pa = document.createElement('pre'); pa.textContent = JSON.stringify(call.arguments || {}, null, 1);
    body.append(la, pa);
    if (call.log) { const ll = document.createElement('span'); ll.className = 'lbl'; ll.textContent = 'agent log'; const pl = document.createElement('pre'); pl.textContent = call.log; body.append(ll, pl); }
    const lr = document.createElement('span'); lr.className = 'lbl'; lr.textContent = 'result';
    const pr = document.createElement('pre'); pr.innerHTML = '<span class="dots"><span></span><span></span><span></span></span>';
    body.append(lr, pr);
    det.append(sum, body); chat().append(det); scrollChat();
    return {
      setResult(txt) { pr.textContent = txt == null ? '(no result)' : String(txt); state.textContent = 'done'; state.classList.add('done'); det.open = false; scrollChat(); },
    };
  }
  function addMediaCard(text, extra) {
    const d = document.createElement('div'); d.className = 'media' + (extra ? ' chart-card' : '');
    d.textContent = text;
    if (extra) d.append(extra);
    chat().append(d); scrollChat();
    return d;
  }
  async function typeBot(text, fast) {
    const el = bubble('bot', 'SatGPT', '');
    el.classList.add('typing');
    S.skip = !!fast;
    let i = 0;
    while (i < text.length) {
      if (S.skip) { el.textContent = text; break; }
      const ch = text[i++];
      el.textContent += ch;
      if (i % 3 === 0) scrollChat();
      await sleep('.!?'.includes(ch) ? 140 : ch === ',' ? 60 : 14);
    }
    el.classList.remove('typing');
    linkify(el);
    scrollChat();
  }
  function linkify(el) {
    const parts = el.textContent.split(/(https?:\/\/[^\s)]+)/g);
    if (parts.length < 2) return;
    el.textContent = '';
    for (const p of parts) {
      if (/^https?:\/\//.test(p)) { const a = document.createElement('a'); a.href = p; a.textContent = p; a.target = '_blank'; a.rel = 'noopener'; el.append(a); }
      else el.append(p);
    }
  }
  chat().addEventListener('click', () => { S.skip = true; });

  async function applyEffect(call) {
    const a = call.arguments || {};
    switch (call.name) {
      case 'stac_search': {
        const b = ['west', 'south', 'east', 'north'].every((k) => a[k] != null)
          ? { west: +a.west, south: +a.south, east: +a.east, north: +a.north }
          : { west: S.meta.bbox[0], south: S.meta.bbox[1], east: S.meta.bbox[2], north: S.meta.bbox[3] };
        showBbox(b);
        break;
      }
      case 'view_footprints':
        showFootprints();
        addMediaCard('🗺 Footprint map · drawn on the map →');
        break;
      case 'plot_metadata': {
        const wrap = document.createElement('div'); wrap.className = 'chart-wrap';
        S.charts.push(wrap);
        addMediaCard(`📈 ${a.field || 'eo:cloud_cover'} by date`, wrap);
        $('chart-panel').hidden = false;
        renderCharts();
        break;
      }
      case 'show_datacube':
        if (!/can't be loaded|cannot|ERROR/i.test(String(call.result || ''))) {
          addMediaCard('🖼 Image viewer · use the Imagery panel →');
          await enableImagery();
        }
        break;
      default: break;
    }
  }

  async function playTurn(i, opts) {
    const { fast = false, typed = null } = opts || {};
    const t = S.transcript.turns[i];
    const replay = i < S.turn;
    S.playing = true; renderSteps();
    $('chat-status').textContent = replay ? `replaying turn ${i + 1}` : `turn ${i + 1} of ${S.transcript.turns.length}`;
    if (typed) bubble('user', 'You', typed, `↳ matched recorded step ${i + 1}: "${t.user}"`);
    else bubble('user', 'You', t.user);
    const pause = (ms) => sleep(fast ? Math.min(ms, 80) : ms);
    await pause(400);
    for (const call of t.tool_calls || []) {
      const blk = addToolBlock(call);
      await pause(700 + Math.random() * 500);
      blk.setResult(call.result);
      await applyEffect(call);
      await pause(250);
    }
    await typeBot(t.assistant || '', fast);
    S.turn = Math.max(S.turn, i + 1); S.playing = false; renderSteps();
    if (S.turn >= S.transcript.turns.length) $('chat-status').textContent = 'end of the recording';
  }

  // ------------------------------------------------------------------ steps menu
  function initSteps() {
    $('play-all').addEventListener('click', async () => {
      if (S.playing) return;
      while (S.turn < S.transcript.turns.length) { await playTurn(S.turn); await sleep(500); }
    });
    $('restart').addEventListener('click', restart);
    renderSteps();
  }
  function renderSteps() {
    const ol = $('steps'); ol.innerHTML = '';
    S.transcript.turns.forEach((t, i) => {
      const li = document.createElement('li');
      const b = document.createElement('button'); b.type = 'button';
      const n = document.createElement('span'); n.className = 'n'; n.textContent = i < S.turn ? '✓' : String(i + 1);
      const txt = document.createElement('span'); txt.textContent = t.user;
      b.append(n, txt);
      if (i < S.turn) b.classList.add('done');
      if (i === S.turn && !S.playing) b.classList.add('next');
      b.disabled = S.playing;
      b.title = i < S.turn ? 'replay this step' : i > S.turn ? 'plays the earlier steps first' : 'play this step';
      b.addEventListener('click', () => { if (!S.playing) playUpTo(i); });
      li.append(b); ol.append(li);
    });
    $('play-all').disabled = S.playing || S.turn >= S.transcript.turns.length;
  }
  async function playUpTo(i, typed) {
    for (let k = S.turn; k < i; k++) await playTurn(k, { fast: true });
    await playTurn(i, { typed });
  }

  // ---------------------------------------------------------------- free-typed chat
  // Keyword rules, first match wins. Each maps to the recorded tool whose step should play.
  // Only domain nouns count: bare verbs ("find", "show", "see", "where", "map") would send every
  // off-script question to a recorded step instead of the DEMO_REPLY above.
  const INTENTS = [
    { tool: 'stac_search', re: /\b(search|scenes?|sentinel|landsat|stac|catalog|seattle)\b/i },
    { tool: 'view_footprints', re: /\b(footprints?|outlines?|coverage|on (a|the) map)\b/i },
    { tool: 'plot_metadata', re: /\b(cloud ?cover|clouds?|plot|chart|graph|metadata|over time)\b/i },
    { tool: 'show_datacube', re: /\b(images?|imagery|pictures?|photos?|datacube|viewer|rgb|true colou?r)\b/i },
  ];
  function stepForTool(tool) {
    return S.transcript.turns.findIndex((t) => (t.tool_calls || []).some((c) => c.name === tool));
  }
  function matchIntent(text) {
    const index = S.meta.indices.find((ix) => new RegExp(`\\b${ix}\\b`, 'i').test(text));
    if (index) return { step: stepForTool('show_datacube'), index };
    for (const it of INTENTS) {
      if (it.re.test(text)) { const step = stepForTool(it.tool); if (step >= 0) return { step }; }
    }
    return null;
  }
  function initChatForm() {
    const form = $('chat-form'), input = $('chat-input');
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const text = input.value.trim();
      if (!text || S.playing) return;
      input.value = '';
      const m = matchIntent(text);
      if (!m) {
        bubble('user', 'You', text);
        const prompts = S.transcript.turns.map((t, i) => `  ${i + 1}. ${t.user}`).join('\n');
        await typeBot(DEMO_REPLY.replace('{prompts}', prompts).replace('{repo}', REPO_URL));
        return;
      }
      const alreadyShown = m.index && S.imagery;
      if (alreadyShown) {
        bubble('user', 'You', text);
        setLayer(m.index);
        await typeBot(`Switched the viewer to ${m.index}. Use the Imagery panel to change the date, stretch or colormap.`);
        return;
      }
      await playUpTo(m.step, text);
      if (m.index && S.imagery) setLayer(m.index);
    });
  }
  function setLayer(layer) {
    const ls = $('layer-select');
    if (![...ls.options].some((o) => o.value === layer)) return;
    ls.value = layer; ls.dispatchEvent(new Event('change'));
  }

  function restart() {
    if (S.playing) { S.skip = true; }
    chat().innerHTML = '';
    S.turn = 0; S.playing = false;
    S.charts = [$('chart')]; $('chart-panel').hidden = true;
    clearMap();
    S.imagery = false; S.current = null;
    $('imagery-panel').classList.add('inactive'); $('imagery-hint').textContent = 'appears once the agent loads the images';
    $('chat-status').textContent = 'press a prompt to start';
    renderSteps();
  }

  // ------------------------------------------------------------------ imagery
  function initImagery() {
    const ds = $('date-select');
    const dates = [...new Set(S.meta.items.map((it) => it.date))].sort();
    for (const d of dates) {
      const it = S.meta.items.find((x) => x.date === d);
      const o = document.createElement('option');
      const rec = S.meta.recorded_dates.includes(d);
      o.value = d; o.disabled = !rec;
      o.textContent = `${d} · ${Number(it['eo:cloud_cover']).toFixed(1)} % cloud${rec ? '' : ' (not recorded)'}`;
      ds.append(o);
    }
    ds.value = S.date;
    const ls = $('layer-select');
    for (const l of ['RGB', ...S.meta.indices]) { const o = document.createElement('option'); o.value = l; o.textContent = l; ls.append(o); }
    const cs = $('cmap-select');
    for (const c of Object.keys(CMAPS)) { const o = document.createElement('option'); o.value = c; o.textContent = c; cs.append(o); }
    cs.value = S.cmap;

    ds.addEventListener('change', () => { S.date = ds.value; refresh(); });
    ls.addEventListener('change', () => {
      S.layer = ls.value;
      if (S.layer !== 'RGB') { S.cmap = DEFAULT_CMAP[S.layer] || 'viridis'; cs.value = S.cmap; S.reverse = false; $('cmap-reverse').checked = false; }
      refresh();
    });
    cs.addEventListener('change', () => { S.cmap = cs.value; render(); });
    $('cmap-reverse').addEventListener('change', (e) => { S.reverse = e.target.checked; render(); });
    $('mask-clouds').addEventListener('change', async (e) => { S.maskClouds = e.target.checked; await refreshMask(); render(); renderMeta(); });
    $('opacity').addEventListener('input', (e) => { S.opacity = +e.target.value; if (S.overlay) S.overlay.setOpacity(S.opacity); });
    const lo = $('stretch-lo'), hi = $('stretch-hi');
    const onStretch = () => {
      S.lo = Math.min(+lo.value, +hi.value - 1); S.hi = Math.max(+hi.value, +lo.value + 1);
      lo.value = S.lo; hi.value = S.hi;
      $('stretch-label').textContent = `${S.lo} – ${S.hi} %`;
      render();
    };
    lo.addEventListener('input', onStretch); hi.addEventListener('input', onStretch);
    $('imagery-panel').classList.add('inactive');
  }

  async function enableImagery() {
    S.imagery = true;
    $('imagery-panel').classList.remove('inactive');
    $('imagery-hint').textContent = `${S.meta.recorded_dates.length} recorded dates · ${S.meta.indices.length} indices · ${S.meta.export_resolution_m} m pixels`;
    await refresh();
  }

  async function loadScl(date) {
    if (S.scl.has(date)) return S.scl.get(date);
    const p = (async () => {
      const entry = (S.meta.masks || []).find((m) => m.date === date);
      if (!entry) return null;
      const [meta, img] = await Promise.all([
        fetch(DATA + entry.json).then((r) => r.json()),
        new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = DATA + entry.png; }),
      ]);
      const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight;
      const ctx = c.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(img, 0, 0);
      const px = ctx.getImageData(0, 0, c.width, c.height).data;
      const n = c.width * c.height; const classes = new Uint8Array(n); const cloud = new Uint8Array(n);
      const cloudSet = new Set(meta.cloud_classes || [8, 9]);
      let count = 0;
      for (let i = 0; i < n; i++) { classes[i] = px[i * 4]; if (cloudSet.has(classes[i])) { cloud[i] = 1; count++; } }
      return { meta, classes, cloud, fraction: count / n, w: c.width, h: c.height };
    })();
    S.scl.set(date, p);
    return p;
  }
  async function refreshMask() {
    S.currentScl = null;
    if (!S.maskClouds || !S.imagery) return;
    try { S.currentScl = await loadScl(S.date); } catch (e) { console.warn('no SCL mask', e); }
  }

  function rasterEntry(date, layer) {
    return S.meta.rasters.find((r) => r.date === date && r.layer === layer);
  }
  async function loadRaster(date, layer) {
    const key = date + '|' + layer;
    if (S.rasters.has(key)) return S.rasters.get(key);
    const p = (async () => {
      const entry = rasterEntry(date, layer);
      if (!entry) throw new Error(`no raster for ${date} ${layer}`);
      const [meta, img] = await Promise.all([
        fetch(DATA + entry.json).then((r) => r.json()),
        new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = DATA + entry.png; }),
      ]);
      const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight;
      const ctx = c.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(img, 0, 0);
      const px = ctx.getImageData(0, 0, c.width, c.height).data;
      const n = c.width * c.height;
      const hist = new Uint32Array(256);
      let values = null;
      if (meta.kind === 'index') {
        values = new Uint8Array(n);
        for (let i = 0; i < n; i++) { const v = px[i * 4]; values[i] = v; if (v) hist[v]++; }
      } else {
        values = px;
        for (let i = 0; i < n; i++) if (px[i * 4 + 3]) { hist[px[i * 4]]++; hist[px[i * 4 + 1]]++; hist[px[i * 4 + 2]]++; }
      }
      hist[0] = 0;
      return { meta, entry, w: c.width, h: c.height, values, hist };
    })();
    S.rasters.set(key, p);
    return p;
  }
  function percentile(hist, p) {
    let total = 0; for (let i = 1; i < 256; i++) total += hist[i];
    const target = (p / 100) * total; let acc = 0;
    for (let i = 1; i < 256; i++) { acc += hist[i]; if (acc >= target) return i; }
    return 255;
  }
  const decode = (m, v) => m.scale.vmin + ((v - 1) / 254) * (m.scale.vmax - m.scale.vmin);

  async function refresh() {
    if (!S.imagery) return;
    const isRGB = S.layer === 'RGB';
    $('cmap-select').disabled = isRGB; $('cmap-reverse').disabled = isRGB;
    try {
      S.current = await loadRaster(S.date, S.layer);
      await refreshMask();
    } catch (e) {
      $('layer-meta').textContent = String(e.message || e); return;
    }
    render();
    renderMeta();
    renderCharts();
  }

  const outCanvas = document.createElement('canvas');
  function render() {
    const r = S.current; if (!r) return;
    const { w, h, values, hist, meta } = r;
    const loV = percentile(hist, S.lo), hiV = Math.max(percentile(hist, S.hi), loV + 1);
    const span = hiV - loV;
    outCanvas.width = w; outCanvas.height = h;
    const ctx = outCanvas.getContext('2d');
    const out = ctx.createImageData(w, h); const o = out.data;
    const n = w * h;
    const cloud = (S.maskClouds && S.currentScl && S.currentScl.w === w && S.currentScl.h === h) ? S.currentScl.cloud : null;
    if (meta.kind === 'index') {
      const lut = buildLut(S.cmap, S.reverse);
      for (let i = 0; i < n; i++) {
        const v = values[i];
        if (!v || (cloud && cloud[i])) { o[i * 4 + 3] = 0; continue; }
        let t = (v - loV) / span; t = t < 0 ? 0 : t > 1 ? 1 : t;
        const k = Math.round(t * 255) * 3;
        o[i * 4] = lut[k]; o[i * 4 + 1] = lut[k + 1]; o[i * 4 + 2] = lut[k + 2]; o[i * 4 + 3] = 255;
      }
    } else {
      for (let i = 0; i < n; i++) {
        const a = values[i * 4 + 3];
        if (!a || (cloud && cloud[i])) { o[i * 4 + 3] = 0; continue; }
        for (let c = 0; c < 3; c++) {
          let t = (values[i * 4 + c] - loV) / span; t = t < 0 ? 0 : t > 1 ? 1 : t;
          o[i * 4 + c] = Math.round(t * 255);
        }
        o[i * 4 + 3] = 255;
      }
    }
    ctx.putImageData(out, 0, 0);
    const url = outCanvas.toDataURL('image/png');
    const b = meta.bounds_lonlat; const bounds = [[b[1], b[0]], [b[3], b[2]]];
    if (S.overlay) { S.overlay.setUrl(url); S.overlay.setBounds(bounds); }
    else S.overlay = L.imageOverlay(url, bounds, { opacity: S.opacity, interactive: false, pane: 'imagery' }).addTo(S.map);
    renderLegend(loV, hiV);
  }

  function renderLegend(loV, hiV) {
    const r = S.current; const m = r.meta;
    const c = $('legend-bar'); const ctx = c.getContext('2d');
    const img = ctx.createImageData(256, 1);
    const lut = m.kind === 'index' ? buildLut(S.cmap, S.reverse) : buildLut('gray', false);
    for (let i = 0; i < 256; i++) { img.data[i * 4] = lut[i * 3]; img.data[i * 4 + 1] = lut[i * 3 + 1]; img.data[i * 4 + 2] = lut[i * 3 + 2]; img.data[i * 4 + 3] = 255; }
    ctx.putImageData(img, 0, 0);
    ctx.drawImage(c, 0, 0, 256, 1, 0, 0, 256, 12);
    const f = (v) => decode(m, v).toFixed(m.kind === 'index' ? 2 : 3);
    $('legend-min').textContent = f(loV); $('legend-mid').textContent = f((loV + hiV) / 2); $('legend-max').textContent = f(hiV);
  }

  function renderMeta() {
    const m = S.current.meta; const e = S.current.entry;
    const el = $('layer-meta');
    const mk = (S.meta.masks || []).find((x) => x.date === S.date);
    const maskTxt = mk ? ` · SCL cloud ${(mk.cloud_fraction * 100).toFixed(1)} % of the bbox${S.maskClouds ? ' (masked)' : ''}` : '';
    if (m.kind === 'index') {
      el.innerHTML = `<b>${m.index}</b> · ${esc(m.long_name)} (${esc(m.application_domain)})<br>` +
        `formula <span class="mono">${esc(m.formula)}</span> · bands ${m.bands.join(', ')}<br>` +
        `p2/p98 ${m.percentiles.p2.toFixed(3)} / ${m.percentiles.p98.toFixed(3)} · range ${m.scale.vmin.toFixed(3)} … ${m.scale.vmax.toFixed(3)} · ${m.width}×${m.height} px @ ${m.resolution_m} m<br>` +
        `item ${e.item_ids.join(', ')}${esc(maskTxt)}`;
    } else {
      el.innerHTML = `<b>True colour</b> · bands ${m.bands.join(', ')} · ${esc(m.units)}<br>` +
        `p2/p98 ${m.percentiles.p2.toFixed(3)} / ${m.percentiles.p98.toFixed(3)} · ${m.width}×${m.height} px @ ${m.resolution_m} m<br>item ${e.item_ids.join(', ')}${esc(maskTxt)}`;
    }
  }
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  function onMouseMove(ev) {
    const r = S.current; if (!r || !S.imagery) return;
    const m = r.meta; const b = m.bounds_3857;
    const p = L.CRS.EPSG3857.project(ev.latlng);
    const col = Math.floor((p.x - b[0]) / m.resolution_m), row = Math.floor((b[3] - p.y) / m.resolution_m);
    const el = $('cursor-readout');
    if (col < 0 || row < 0 || col >= r.w || row >= r.h) { el.textContent = 'outside the raster'; return; }
    const i = row * r.w + col;
    const ll = `${ev.latlng.lat.toFixed(4)}, ${ev.latlng.lng.toFixed(4)}`;
    const sclTxt = (S.currentScl && S.currentScl.classes.length === r.w * r.h) ? ` · SCL ${S.currentScl.meta.classes[String(S.currentScl.classes[i])] || S.currentScl.classes[i]}` : '';
    if (m.kind === 'index') {
      const v = r.values[i];
      el.textContent = (v ? `${m.index} = ${decode(m, v).toFixed(3)} at ${ll}` : `nodata at ${ll}`) + sclTxt;
    } else {
      const a = r.values[i * 4 + 3];
      el.textContent = (a ? `R/G/B reflectance ${[0, 1, 2].map((c) => decode(m, r.values[i * 4 + c]).toFixed(3)).join(' / ')} at ${ll}` : `nodata at ${ll}`) + sclTxt;
    }
  }

  // ------------------------------------------------------------------ cloud-cover chart (inline SVG)
  function renderCharts() { for (const c of S.charts) renderChart(c); }
  function renderChart(container) {
    const items = S.meta.items.slice().sort((a, b) => a.datetime.localeCompare(b.datetime));
    const W = 360, H = 130, L = 30, R = 10, T = 10, B = 24;
    const [y0, y1] = S.meta.datetime.split('/').map((d) => new Date(d + 'T00:00:00Z').getTime());
    const x = (d) => L + ((new Date(d + 'T00:00:00Z').getTime() - y0) / (y1 - y0)) * (W - L - R);
    const y = (v) => T + (1 - v / 100) * (H - T - B);
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Cloud cover percentage of each scene by date');
    const mk = (tag, attrs, text) => { const e = document.createElementNS(ns, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (text != null) e.textContent = text; return e; };
    for (const v of [0, 50, 100]) {
      svg.append(mk('line', { x1: L, x2: W - R, y1: y(v), y2: y(v), class: 'cc-axis' }));
      svg.append(mk('text', { x: L - 4, y: y(v) + 3, 'text-anchor': 'end', class: 'cc-txt' }, v + '%'));
    }
    const first = new Date(y0);
    for (let d = 1; d <= 31; d += 7) {
      const ds = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth(), d)).toISOString().slice(0, 10);
      svg.append(mk('text', { x: x(ds), y: H - 8, 'text-anchor': 'middle', class: 'cc-txt' }, ds.slice(5)));
    }
    svg.append(mk('path', { d: items.map((it, i) => `${i ? 'L' : 'M'}${x(it.date).toFixed(1)},${y(it['eo:cloud_cover']).toFixed(1)}`).join(' '), class: 'cc-line' }));
    const tip = document.createElement('div'); tip.className = 'cc-tip';
    for (const it of items) {
      const rec = S.meta.recorded_dates.includes(it.date);
      const cx = x(it.date), cy = y(it['eo:cloud_cover']);
      const c = mk('circle', { cx, cy, r: 4.5, class: 'cc-dot' + (rec ? ' rec' : '') + (S.imagery && it.date === S.date ? ' sel' : '') });
      const hit = mk('circle', { cx, cy, r: 11, class: 'cc-hit' });
      const bboxCloud = it.scl_cloud_fraction_bbox == null ? '' : ` · ${(it.scl_cloud_fraction_bbox * 100).toFixed(1)} % SCL cloud in bbox`;
      const label = `${it.date} · ${Number(it['eo:cloud_cover']).toFixed(2)} % cloud (scene)${bboxCloud}${rec ? ' · recorded, click to view' : ''}`;
      hit.append(mk('title', {}, label));
      const show = () => { tip.textContent = label; tip.style.display = 'block'; tip.style.left = `${(cx / W) * 100}%`; tip.style.top = `${(cy / H) * 100}%`; c.setAttribute('r', 6); };
      const hide = () => { tip.style.display = 'none'; c.setAttribute('r', 4.5); };
      hit.addEventListener('mouseenter', show); hit.addEventListener('mouseleave', hide);
      if (rec) hit.addEventListener('click', () => { if (!S.imagery) return; S.date = it.date; $('date-select').value = it.date; refresh(); });
      svg.append(c, hit);
    }
    container.innerHTML = ''; container.append(svg, tip);
  }

  boot().catch((e) => { $('chat-status').textContent = 'failed to load the recording: ' + e; console.error(e); });
})();
