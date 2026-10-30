// Live-Displays im Cockpit: Kombiinstrument, Mittel-Display, Fond-Bildschirme.
//
// Die GLB enthält für jedes Display ein Standardbild. Hier werden die
// Bilder durch Canvas-Texturen ersetzt, die echte Werte zeigen
// (Geschwindigkeit, Drehzahl, Gang, Uhrzeit, Blinker, Licht …).
// Die Helligkeit regelt Vehicle über die Emission der Materialien.

import * as THREE from 'three';

const SIZES = { cluster: [1024, 410], center: [1024, 640], rear: [1024, 640], retro: [512, 170] };

function hex(c) {
  return '#' + new THREE.Color(c).getHexString();
}

export class Displays {
  constructor(vehicle) {
    this.v = vehicle;
    this.items = [];
    this.accent = hex(vehicle.meta.defaultAccent || '#00e5ff');
    this.lastDraw = -1;
    const kind = vehicle.meta.gauges || {};
    for (const mat of vehicle.materialList) {
      const which = mat.userData && mat.userData.canvas;
      if (!which) continue;
      let type = which;
      if (which === 'cluster' && kind.cluster === 'analog') continue; // analoge Uhren: Zeiger sind 3D
      if (which === 'center' && kind.center === 'retro') type = 'retro';
      const [w, h] = SIZES[type];
      const canvas = document.createElement('canvas');
      canvas.width = w;
      canvas.height = h;
      const tex = new THREE.CanvasTexture(canvas);
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.flipY = false; // glTF-UVs
      tex.anisotropy = 4;
      mat.map = tex;            // Standardbild der GLB bleibt im Zwischenspeicher erhalten
      mat.emissiveMap = tex;
      mat.needsUpdate = true;
      this.items.push({ type, canvas, ctx: canvas.getContext('2d'), tex, mat });
    }
  }

  update(time, force = false) {
    if (!this.items.length) return;
    if (!force && time - this.lastDraw < 1 / 15) return; // 15 Hz reicht
    this.lastDraw = time;
    const s = this.v.state;
    for (const it of this.items) {
      const fn = this['draw_' + it.type];
      if (fn) fn.call(this, it.ctx, it.canvas.width, it.canvas.height, s, time);
      it.tex.needsUpdate = true;
    }
  }

  dispose() {
    for (const it of this.items) it.tex.dispose();
    this.items = [];
  }

  // ------------------------------------------------------------------
  draw_cluster(c, w, h, s, t) {
    const acc = this.accent;
    const g = this.v.meta.gauges || {};
    const rpmMax = (g.rpmMaxThousand || 9) * 1000;
    const red = (this.v.meta.physics && this.v.meta.physics.redlineRpm) || rpmMax * 0.88;
    c.fillStyle = '#040508';
    c.fillRect(0, 0, w, h);
    const grd = c.createRadialGradient(w / 2, h, 40, w / 2, h, h * 1.2);
    grd.addColorStop(0, 'rgba(40,60,90,0.35)');
    grd.addColorStop(1, 'rgba(0,0,0,0)');
    c.fillStyle = grd;
    c.fillRect(0, 0, w, h);
    // Drehzahlbogen
    const cx = w / 2, cy = h * 0.98, r = h * 0.9;
    const a0 = Math.PI * (200 / 180), a1 = Math.PI * (340 / 180);
    c.lineCap = 'butt';
    c.lineWidth = 22;
    c.strokeStyle = '#1c1f28';
    c.beginPath(); c.arc(cx, cy, r, a0, a1); c.stroke();
    const f = Math.min(1, s.rpm / rpmMax);
    const fr = Math.min(1, red / rpmMax);
    c.strokeStyle = acc;
    c.beginPath(); c.arc(cx, cy, r, a0, a0 + (a1 - a0) * Math.min(f, fr)); c.stroke();
    if (f > fr) {
      c.strokeStyle = '#ff2a2a';
      c.beginPath(); c.arc(cx, cy, r, a0 + (a1 - a0) * fr, a0 + (a1 - a0) * f); c.stroke();
    }
    c.fillStyle = '#8c92a4';
    c.font = 'bold 26px monospace';
    c.textAlign = 'center';
    c.textBaseline = 'middle';
    const steps = Math.round(rpmMax / 1000);
    for (let k = 0; k <= steps; k++) {
      const a = a0 + (a1 - a0) * (k / steps);
      c.fillText(String(k), cx + (r - 40) * Math.cos(a), cy + (r - 40) * Math.sin(a) + 4);
    }
    // Geschwindigkeit + Gang
    c.fillStyle = '#f1f3f8';
    c.font = 'bold 150px sans-serif';
    c.fillText(String(Math.round(Math.abs(s.speedKmh))), cx, h * 0.5);
    c.fillStyle = '#828aa0';
    c.font = '30px sans-serif';
    c.fillText('km/h', cx, h * 0.72);
    c.strokeStyle = acc;
    c.lineWidth = 4;
    roundRect(c, cx - 40, h * 0.78, 80, h * 0.15, 10);
    c.stroke();
    c.fillStyle = acc;
    c.font = 'bold 48px sans-serif';
    c.fillText(s.gear, cx, h * 0.855);
    // Seitenfelder
    c.textAlign = 'left';
    c.fillStyle = '#c8ccd8';
    c.font = 'bold 30px sans-serif';
    c.fillText(this.v.meta.name.toUpperCase(), 40, 52);
    c.fillStyle = '#7a8094';
    c.font = 'bold 26px monospace';
    c.fillText(clock() + '   18°C', 40, 96);
    c.textAlign = 'right';
    c.fillText('RANGE ' + Math.round(412 - s.odo * 0.2) + ' km', w - 40, 52);
    c.fillText('ODO ' + (77777 + Math.floor(s.odo)).toLocaleString('de-DE') + ' km', w - 40, 96);
    // Blinker und Licht
    const blink = Math.floor(t * 2.6) % 2 === 0;
    if (s.indicator !== 0 && blink) {
      c.fillStyle = '#29e05a';
      arrow(c, s.indicator < 0 ? 300 : w - 300, 60, s.indicator < 0 ? -1 : 1);
    }
    if (s.lights) {
      c.fillStyle = '#2f8bff';
      c.font = 'bold 34px sans-serif';
      c.textAlign = 'center';
      c.fillText('◖≡', 150, h - 60);
    }
    // Balken Kraftstoff/Temperatur
    c.textAlign = 'left';
    c.font = 'bold 22px monospace';
    ['FUEL', 'TEMP'].forEach((lab, i) => {
      const y = h - 110 + i * 46;
      c.fillStyle = '#6e7486';
      c.fillText(lab, 40, y + 12);
      c.fillStyle = '#1c1f28';
      c.fillRect(130, y + 4, 200, 14);
      c.fillStyle = i === 0 ? acc : '#5aa8ff';
      c.fillRect(130, y + 4, i === 0 ? 150 : 90 + 30 * Math.min(1, s.rpm / rpmMax), 14);
    });
  }

  draw_center(c, w, h, s, t) {
    const acc = this.accent;
    c.fillStyle = '#05060c';
    c.fillRect(0, 0, w, h);
    // Karte mit Straßen
    c.save();
    c.beginPath();
    c.rect(0, 86, 640, h - 86);
    c.clip();
    const off = (s.odo * 40) % 64;
    c.strokeStyle = '#121828';
    c.lineWidth = 2;
    for (let i = -2; i < 14; i++) {
      c.beginPath(); c.moveTo(i * 64 + off, 90); c.lineTo(i * 64 + off - 220, h); c.stroke();
    }
    for (let j = 110; j < h; j += 56) {
      c.beginPath(); c.moveTo(0, j); c.lineTo(640, j + 30); c.stroke();
    }
    c.strokeStyle = acc;
    c.lineWidth = 10;
    c.lineJoin = 'round';
    c.beginPath();
    const pts = [[80, 600], [180, 470], [330, 430], [420, 300], [560, 260], [610, 140]];
    c.moveTo(pts[0][0], pts[0][1]);
    for (const p of pts) c.lineTo(p[0], p[1]);
    c.stroke();
    c.fillStyle = '#ffffff';
    c.beginPath(); c.moveTo(70, 590); c.lineTo(95, 560); c.lineTo(100, 610); c.closePath(); c.fill();
    c.beginPath(); c.arc(610, 140, 12, 0, Math.PI * 2); c.fill();
    c.restore();
    // Kopfzeile
    c.fillStyle = '#0a0c14';
    c.fillRect(0, 0, w, 86);
    c.fillStyle = acc;
    c.font = 'bold 38px sans-serif';
    c.textAlign = 'left';
    c.textBaseline = 'middle';
    c.fillText('NEON HAVEN OS', 28, 44);
    c.fillStyle = '#dce0ec';
    c.font = 'bold 32px monospace';
    c.textAlign = 'right';
    c.fillText(clock() + '  18°C', w - 28, 44);
    // Infokarte
    c.fillStyle = '#0c0e18';
    c.fillRect(660, 110, w - 684, h - 134);
    c.strokeStyle = 'rgba(255,255,255,0.08)';
    c.lineWidth = 2;
    c.strokeRect(660, 110, w - 684, h - 134);
    c.textAlign = 'left';
    c.fillStyle = '#f0f2fa';
    c.font = 'bold 44px sans-serif';
    c.fillText('Hallo Zero!', 690, 160);
    c.fillStyle = '#969cb0';
    c.font = '30px sans-serif';
    c.fillText(this.v.meta.name, 690, 210);
    c.fillStyle = acc;
    c.font = '22px sans-serif';
    c.fillText('JETZT LÄUFT', 690, 275);
    c.fillStyle = '#eceef6';
    c.font = 'bold 30px sans-serif';
    c.fillText('Midnight Overdrive', 690, 312);
    c.fillStyle = '#969cb0';
    c.font = '26px sans-serif';
    c.fillText('The Synth Rats', 690, 350);
    const prog = (t * 0.01) % 1;
    c.fillStyle = '#262a3a';
    c.fillRect(690, 392, w - 744, 8);
    c.fillStyle = acc;
    c.fillRect(690, 392, (w - 744) * prog, 8);
    const st = this.v.settingsView || {};
    c.fillStyle = '#c8ccdc';
    c.font = '26px sans-serif';
    c.fillText('Innenlicht  ' + Math.round((st.interiorLight ?? 0.25) * 100) + ' %', 690, 450);
    c.fillText('Display      ' + Math.round((st.displayBrightness ?? 0.7) * 100) + ' %', 690, 490);
    c.fillStyle = '#5a6078';
    c.font = '22px sans-serif';
    c.fillText('Tipp: Hupe 3x drücken …', 690, 570);
  }

  draw_rear(c, w, h, s, t) {
    // kleiner "Film": Sonnenuntergang über der Skyline
    for (let y = 0; y < h; y += 4) {
      const k = y / h;
      c.fillStyle = `rgb(${20 + 60 * k | 0},${14 + 26 * k | 0},${40 + 70 * (1 - k) | 0})`;
      c.fillRect(0, y, w, 4);
    }
    const sunY = 220 + Math.sin(t * 0.1) * 30;
    c.fillStyle = '#ffbe78';
    c.beginPath(); c.arc(760, sunY, 130, 0, Math.PI * 2); c.fill();
    for (let k = 0; k < 13; k++) {
      const x = ((k * 82 - t * 12) % (w + 100) + w + 100) % (w + 100) - 60;
      const hh = 120 + ((k * 37) % 180);
      c.fillStyle = '#0c0a16';
      c.fillRect(x, h - hh, 60, hh);
      c.fillStyle = this.accent;
      for (let wy = h - hh + 12; wy < h - 10; wy += 22) {
        if ((wy + k) % 3) c.fillRect(x + 10, wy, 8, 8);
      }
    }
    c.fillStyle = '#000';
    c.fillRect(0, h - 70, w, 70);
    c.fillStyle = '#dcdce6';
    c.font = 'bold 28px monospace';
    c.textAlign = 'left';
    c.textBaseline = 'middle';
    const m = Math.floor(t / 60) % 48, sec = Math.floor(t) % 60;
    c.fillText(`▶  NEON HAVEN – DOKU   ${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')} / 48:00`, 30, h - 35);
  }

  draw_retro(c, w, h, s, t) {
    c.fillStyle = '#140c04';
    c.fillRect(0, 0, w, h);
    c.fillStyle = '#ff9628';
    c.font = 'bold 60px monospace';
    c.textAlign = 'left';
    c.textBaseline = 'top';
    c.fillText('FM 77.7', 24, 12);
    const msg = "MIXTAPE '77 – SIDE A – NEON NIGHTS –  ";
    const off = Math.floor(t * 6) % msg.length;
    c.fillStyle = '#c86e1e';
    c.font = 'bold 30px monospace';
    c.fillText((msg + msg).substr(off, 22), 24, 104);
  }
}

function roundRect(c, x, y, w, h, r) {
  c.beginPath();
  c.moveTo(x + r, y);
  c.arcTo(x + w, y, x + w, y + h, r);
  c.arcTo(x + w, y + h, x, y + h, r);
  c.arcTo(x, y + h, x, y, r);
  c.arcTo(x, y, x + w, y, r);
  c.closePath();
}

function arrow(c, x, y, dir) {
  c.beginPath();
  c.moveTo(x + dir * 30, y);
  c.lineTo(x - dir * 5, y - 24);
  c.lineTo(x - dir * 5, y - 10);
  c.lineTo(x - dir * 30, y - 10);
  c.lineTo(x - dir * 30, y + 10);
  c.lineTo(x - dir * 5, y + 10);
  c.lineTo(x - dir * 5, y + 24);
  c.closePath();
  c.fill();
}

function clock() {
  const d = new Date();
  return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
}
