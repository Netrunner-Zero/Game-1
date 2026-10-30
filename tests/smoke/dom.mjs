// Minimales DOM für den Rauchtest (nur was das Spiel benutzt).
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

class ClassList {
  constructor(el) { this.el = el; }
  get set() { return new Set((this.el.className || '').split(/\s+/).filter(Boolean)); }
  add(...c) { const s = this.set; c.forEach((x) => s.add(x)); this.el.className = [...s].join(' '); }
  remove(...c) { const s = this.set; c.forEach((x) => s.delete(x)); this.el.className = [...s].join(' '); }
  toggle(c, on) { const s = this.set; const want = on === undefined ? !s.has(c) : !!on; if (want) s.add(c); else s.delete(c); this.el.className = [...s].join(' '); return want; }
  contains(c) { return this.set.has(c); }
}

const ctx2d = new Proxy({ measureText: () => ({ width: 10 }), createLinearGradient: () => ({ addColorStop() {} }),
  createRadialGradient: () => ({ addColorStop() {} }), getImageData: () => ({ data: new Uint8ClampedArray(4) }) }, {
  get(t, p) { return p in t ? t[p] : () => {}; },
  set(t, p, v) { t[p] = v; return true; },
});

export class El {
  constructor(tag = 'div', id = '') {
    this.tagName = tag.toUpperCase(); this.id = id; this.children = []; this.className = '';
    this.style = { setProperty() {} }; this.dataset = {}; this.classList = new ClassList(this);
    this._l = {}; this._html = ''; this.open = false; this.value = ''; this.checked = false; this.textContent = '';
    this.width = 300; this.height = 150; this.disabled = false;
  }
  set innerHTML(h) {
    this._html = h; this.children = [];
    // data-tab / data-l Attribute als Kinder nachbilden (für querySelectorAll)
    const re = /<(\w+)[^>]*class="([^"]*)"[^>]*?(?:data-(\w+)="([^"]*)")?[^>]*>/g;
    let m;
    while ((m = re.exec(h))) { const e = new El(m[1]); e.className = m[2]; if (m[3]) e.dataset[m[3]] = m[4]; this.children.push(e); }
    const re2 = /<span data-l="(\w+)">/g;
    while ((m = re2.exec(h))) { const e = new El('span'); e.dataset.l = m[1]; e.className = 'lamp'; this.children.push(e); }
  }
  get innerHTML() { return this._html; }
  addEventListener(t, f) { (this._l[t] ||= []).push(f); }
  removeEventListener() {}
  dispatch(t, extra = {}) {
    const ev = { type: t, preventDefault() {}, stopPropagation() {}, target: this, pointerId: 1, clientX: 0, clientY: 0, ...extra };
    for (const f of this._l[t] || []) f(ev);
    if (t === 'click' && this.onclick) this.onclick(ev);
    if (t === 'change' && this.onchange) this.onchange(ev);
    if (t === 'input' && this.oninput) this.oninput(ev);
  }
  appendChild(c) { this.children.push(c); c.parentNode = this; return c; }
  _all() { const out = []; const walk = (e) => { for (const c of e.children) { out.push(c); walk(c); } }; walk(this); return out; }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || new El('div'); }
  querySelectorAll(sel) {
    if (sel === '.lamps span') return this._all().filter((e) => e.dataset.l);
    const last = sel.trim().split(/\s+/).pop();
    const cls = last.startsWith('.') ? last.slice(1).split('.')[0] : null;
    const tag = !cls && /^\w+$/.test(last) ? last.toUpperCase() : null;
    return this._all().filter((e) => (cls ? e.classList.contains(cls) : tag ? e.tagName === tag : false));
  }
  setPointerCapture() {} releasePointerCapture() {} focus() {}
  showModal() { this.open = true; }
  close() { this.open = false; this.dispatch('close'); }
  getContext() { return ctx2d; }
  getBoundingClientRect() { return { left: 0, top: 0, width: 100, height: 100 }; }
}

export function installDom(htmlPath, baseDir) {
  const html = readFileSync(htmlPath, 'utf8');
  const els = new Map();
  for (const m of html.matchAll(/<(\w+)[^>]*\sid="([^"]+)"([^>]*)>/g)) {
    const e = new El(m[1], m[2]);
    const cm = /class="([^"]*)"/.exec(m[0]);
    if (cm) e.className = cm[1];
    if (/\sdisabled/.test(m[0])) e.disabled = true;
    els.set(m[2], e);
  }
  const tabs = [...html.matchAll(/<button class="tab[^"]*" data-tab="(\w+)"/g)].map((m) => { const e = new El('button'); e.className = 'tab'; e.dataset.tab = m[1]; return e; });
  if (els.has('tabs')) els.get('tabs').children = tabs;
  const winL = {};
  const docL = {};
  const raf = [];
  const store = new Map();
  globalThis.window = globalThis;
  Object.assign(globalThis, {
    innerWidth: 1280, innerHeight: 720, devicePixelRatio: 2,
    addEventListener: (t, f) => (winL[t] ||= []).push(f),
    removeEventListener() {},
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    requestAnimationFrame: (f) => { raf.push(f); return raf.length; },
    localStorage: { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) },
    screen: { orientation: { angle: 0 } },
    document: {
      hidden: false,
      getElementById: (id) => { if (!els.has(id)) throw new Error('Element fehlt im HTML: #' + id); return els.get(id); },
      createElement: (t) => new El(t),
      querySelectorAll: (sel) => {
        if (sel === '#tabs .tab') return tabs;
        const cls = sel.startsWith('.') ? sel.slice(1) : null;
        const all = [];
        for (const e of els.values()) { all.push(e); all.push(...e._all()); }
        return cls ? all.filter((e) => e.classList.contains(cls)) : [];
      },
      querySelector: () => new El('div'),
      addEventListener: (t, f) => (docL[t] ||= []).push(f),
      documentElement: { style: { setProperty() {} } },
      body: new El('body'),
    },
    fetch: async (url) => {
      const p = path.resolve(baseDir, url);
      try {
        const buf = readFileSync(p);
        const txt = () => buf.toString('utf8');
        return { ok: true, status: 200, json: async () => JSON.parse(txt()), text: async () => txt(),
          arrayBuffer: async () => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) };
      } catch (e) { return { ok: false, status: 404, json: async () => ({}) }; }
    },
    __smokeResolve: (url) => path.resolve(baseDir, url),
    Image: class { set src(v) { this._src = v; setTimeout(() => this.onload && this.onload(), 0); } get src() { return this._src; } },
  });
  return {
    els, winL, raf, store,
    key(type, code) { for (const f of winL[type] || []) f({ code, repeat: false, preventDefault() {}, target: { tagName: 'BODY' } }); },
    async frames(n, dt = 1 / 60) {
      globalThis.__smokeDt = dt;
      for (let i = 0; i < n; i++) {
        const cbs = raf.splice(0);
        for (const f of cbs) f(performance.now());
        if (i % 30 === 0) await new Promise((r) => setTimeout(r, 0));
      }
    },
  };
}
