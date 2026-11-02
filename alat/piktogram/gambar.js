// Set piktogram buatan proyek (CC0) untuk kartu Tutor ASD. Gaya: garis tebal hitam, warna datar, latar putih.
const { chromium } = require('playwright');
const fs = require('fs');
const K = '#1f1f1f', KULIT = '#f2c9a0', BIRU = '#4a8fd8', ORANYE = '#e9a23b', HIJAU = '#6fae8b', ABU = '#cfd8dc',
      AIR = '#7cc3f0', MERAH = '#d9534f', KUNING = '#f3d36b', COKLAT = '#b07a4f', UNGU = '#9b7fd1';
const sw = 'stroke="' + K + '" stroke-width="7" stroke-linejoin="round" stroke-linecap="round"';

// Tangan terbuka, jari ke atas. (x,y) pusat telapak.
function tangan(x, y, s = 1, r = 0, cermin = false, lengan = BIRU) {
  const jari = [[-42, 66], [-20, 78], [2, 76], [24, 62]].map(([fx, h]) =>
    `<rect x="${fx}" y="${-40 - h + 14}" width="19" height="${h}" rx="9.5" fill="${KULIT}" ${sw}/>`).join('');
  return `<g transform="translate(${x} ${y}) rotate(${r}) scale(${cermin ? -s : s} ${s})">
    <rect x="-36" y="40" width="72" height="70" fill="${lengan}" ${sw}/>
    ${jari}
    <rect x="-76" y="-24" width="26" height="64" rx="13" fill="${KULIT}" ${sw} transform="rotate(-32 -63 8)"/>
    <rect x="-46" y="-42" width="92" height="98" rx="26" fill="${KULIT}" ${sw}/></g>`;
}
// Tangan menunjuk dengan telunjuk ke kanan.
function tunjuk(x, y, s = 1, r = 0) {
  return `<g transform="translate(${x} ${y}) rotate(${r}) scale(${s})">
    <rect x="-150" y="-30" width="70" height="66" fill="${BIRU}" ${sw}/>
    <rect x="-10" y="-30" width="120" height="22" rx="11" fill="${KULIT}" ${sw}/>
    <rect x="-90" y="-38" width="100" height="84" rx="26" fill="${KULIT}" ${sw}/>
    <path d="M-40 0 h40 M-40 18 h36 M-40 34 h30" fill="none" ${sw} stroke-width="5"/></g>`;
}
function orang(x, y, s = 1, baju = BIRU, opsi = {}) {
  const lambai = opsi.lambai;
  const rambut = opsi.dewasa
    ? `<path d="M-40 -158 q0 -46 40 -46 q40 0 40 46 q-20 -18 -40 -18 q-20 0 -40 18z" fill="#5a3b2a" ${sw}/><circle cx="0" cy="-214" r="16" fill="#5a3b2a" ${sw}/>`
    : `<path d="M-38 -160 q2 -40 38 -40 q36 0 38 40 q-18 -14 -38 -14 q-20 0 -38 14z" fill="#3b2a20" ${sw}/>`;
  const lenganKanan = lambai
    ? `<path d="M52 -88 L105 -170" fill="none" stroke="${K}" stroke-width="30" stroke-linecap="round"/><path d="M52 -88 L105 -170" fill="none" stroke="${baju}" stroke-width="18" stroke-linecap="round"/><circle cx="110" cy="-182" r="20" fill="${KULIT}" ${sw}/>`
    : `<path d="M55 -88 L72 -10" fill="none" stroke="${K}" stroke-width="30" stroke-linecap="round"/><path d="M55 -88 L72 -10" fill="none" stroke="${baju}" stroke-width="18" stroke-linecap="round"/><circle cx="74" cy="4" r="18" fill="${KULIT}" ${sw}/>`;
  return `<g transform="translate(${x} ${y}) scale(${s})">
    <rect x="-40" y="30" width="30" height="90" rx="10" fill="#3d4a5c" ${sw}/><rect x="10" y="30" width="30" height="90" rx="10" fill="#3d4a5c" ${sw}/>
    <path d="M-55 -110 h110 q12 0 14 12 l12 140 h-162 l12 -140 q2 -12 14 -12z" fill="${baju}" ${sw}/>
    <path d="M-55 -88 L-72 -10" fill="none" stroke="${K}" stroke-width="30" stroke-linecap="round"/><path d="M-55 -88 L-72 -10" fill="none" stroke="${baju}" stroke-width="18" stroke-linecap="round"/><circle cx="-74" cy="4" r="18" fill="${KULIT}" ${sw}/>
    ${lenganKanan}
    <circle cx="0" cy="-152" r="42" fill="${KULIT}" ${sw}/>${rambut}
    <circle cx="-14" cy="-152" r="5" fill="${K}"/><circle cx="14" cy="-152" r="5" fill="${K}"/>
    <path d="M-14 -132 q14 12 28 0" fill="none" ${sw} stroke-width="5"/></g>`;
}
const gerak = (x, y) => `<path d="M${x} ${y} q18 -22 0 -44 M${x + 22} ${y + 8} q26 -30 0 -60" fill="none" ${sw} stroke-width="6"/>`;
const panah = (x1, y1, x2, y2) => {
  const a = Math.atan2(y2 - y1, x2 - x1), u = 26;
  const p1 = [x2 - u * Math.cos(a - 0.5), y2 - u * Math.sin(a - 0.5)], p2 = [x2 - u * Math.cos(a + 0.5), y2 - u * Math.sin(a + 0.5)];
  return `<path d="M${x1} ${y1} L${x2} ${y2} M${p1} L${x2} ${y2} L${p2}" fill="none" stroke="${MERAH}" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>`;
};
const gelembung = (pts) => pts.map(([x, y, r]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="#ffffff" stroke="${AIR}" stroke-width="5"/>`).join('');
const tas = (x, y, s = 1, terbuka = false) => `<g transform="translate(${x} ${y}) scale(${s})">
  <path d="M-60 -95 q0 -40 60 -40 q60 0 60 40" fill="none" ${sw} stroke-width="12"/>
  <rect x="-95" y="-100" width="190" height="210" rx="40" fill="${BIRU}" ${sw}/>
  ${terbuka ? `<path d="M-95 -60 q95 -60 190 0" fill="#2f6aa8" ${sw}/>` : `<path d="M-95 -40 q95 50 190 0" fill="none" ${sw}/>`}
  <rect x="-55" y="20" width="110" height="60" rx="14" fill="#6aa6e6" ${sw}/></g>`;
const bekal = (x, y, s = 1) => `<g transform="translate(${x} ${y}) scale(${s})">
  <rect x="-80" y="-45" width="160" height="90" rx="16" fill="${HIJAU}" ${sw}/><path d="M-80 -15 h160" ${sw}/>
  <rect x="-16" y="-24" width="32" height="18" rx="5" fill="${KUNING}" ${sw}/></g>`;
const stiker = (x, y, r = 22) => `<path d="${Array.from({length: 10}, (_, i) => { const a = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? r * 0.45 : r; return (i ? 'L' : 'M') + (x + rr * Math.cos(a)).toFixed(1) + ' ' + (y + rr * Math.sin(a)).toFixed(1); }).join(' ')}z" fill="${KUNING}" ${sw} stroke-width="5"/>`;
const loker = (x, y, isi = '', buka = false) => `<g transform="translate(${x} ${y})">
  <rect x="-110" y="-200" width="220" height="400" rx="10" fill="${ABU}" ${sw}/>
  ${buka ? `<rect x="-92" y="-182" width="184" height="364" fill="#eef2f4" ${sw}/>${isi}<path d="M92 -182 L170 -150 L170 160 L92 182z" fill="#b8c4ca" ${sw}/>`
         : `<path d="M-80 -165 h160 M-80 -150 h160 M-80 -135 h160" ${sw} stroke-width="5"/><rect x="70" y="-10" width="14" height="50" rx="6" fill="${K}"/>${stiker(0, -60, 34)}`}</g>`;
const balok = (x, y, w, warna) => `<rect x="${x}" y="${y}" width="${w}" height="${w}" rx="8" fill="${warna}" ${sw}/>`;
const pensil = (x, y, r = 0, s = 1) => `<g transform="translate(${x} ${y}) rotate(${r}) scale(${s})">
  <rect x="-110" y="-16" width="180" height="32" fill="${KUNING}" ${sw}/><path d="M70 -16 L120 0 L70 16z" fill="#f4e1c1" ${sw}/>
  <path d="M104 -5 L120 0 L104 5z" fill="${K}"/><rect x="-130" y="-16" width="22" height="32" rx="6" fill="#f29bb0" ${sw}/></g>`;
const keran = (x, y) => `<g transform="translate(${x} ${y})"><rect x="-150" y="-30" width="140" height="44" rx="12" fill="${ABU}" ${sw}/>
  <path d="M-20 -8 h40 q20 0 20 20 v30" fill="none" stroke="${K}" stroke-width="40" stroke-linecap="round"/><path d="M-20 -8 h40 q20 0 20 20 v30" fill="none" stroke="${ABU}" stroke-width="26" stroke-linecap="round"/>
  <rect x="-100" y="-62" width="40" height="34" rx="8" fill="${ABU}" ${sw}/></g>`;

const kartu = {
  'guru-melambai': orang(220, 330, 1.05, UNGU, {lambai: true, dewasa: true}) + gerak(370, 110),
  'tangan-melambai': tangan(240, 280, 1.5, -12) + gerak(340, 120),
  'jari-saling-menyilang': (() => {
    // dua tangan bertemu dari kiri dan kanan, jari bergantian (saling menyilang)
    const jariKiri = [0, 1, 2, 3].map(i => `<rect x="${200}" y="${170 + i * 34}" width="120" height="24" rx="12" fill="${KULIT}" ${sw}/>`).join('');
    const jariKanan = [0, 1, 2, 3].map(i => `<rect x="${180}" y="${187 + i * 34}" width="120" height="24" rx="12" fill="#e8b98c" ${sw}/>`).join('');
    return `<rect x="20" y="190" width="70" height="110" fill="${BIRU}" ${sw}/><rect x="410" y="190" width="70" height="110" fill="${BIRU}" ${sw}/>` +
      `<rect x="80" y="150" width="140" height="190" rx="40" fill="${KULIT}" ${sw}/>` + jariKiri + jariKanan +
      `<rect x="290" y="150" width="130" height="190" rx="40" fill="#e8b98c" ${sw}/>` +
      gelembung([[150, 110, 22], [250, 90, 16], [340, 115, 20], [250, 395, 18], [170, 400, 13]]);
  })(),
  'telapak-bergesekan': `<rect x="50" y="310" width="70" height="100" fill="${BIRU}" ${sw} transform="rotate(-20 85 360)"/><rect x="380" y="310" width="70" height="100" fill="${BIRU}" ${sw} transform="rotate(20 415 360)"/>` +
    tangan(200, 250, 1.35, 12) + tangan(300, 250, 1.35, -12, true) + gelembung([[250, 80, 20], [165, 95, 14], [340, 98, 16], [250, 440, 15]]) +
    panah(140, 455, 210, 455) + panah(360, 455, 290, 455),
  'telapak-menggosok-punggung-tangan': tangan(250, 330, 1.25, 90, false, BIRU) +
    `<g transform="translate(270 255) rotate(-90) scale(1.15 1.15)"><rect x="-36" y="40" width="72" height="70" fill="#6aa6e6" ${sw}/>${[[-42, 66], [-20, 78], [2, 76], [24, 62]].map(([fx, h]) => `<rect x="${fx}" y="${-40 - h + 14}" width="19" height="${h}" rx="9.5" fill="#e8b98c" ${sw}/>`).join('')}<rect x="-46" y="-42" width="92" height="98" rx="26" fill="#e8b98c" ${sw}/></g>` +
    gelembung([[110, 150, 18], [400, 170, 16], [420, 420, 14], [90, 420, 12]]) + panah(200, 120, 120, 120) + panah(300, 120, 380, 120),
  'tangan-di-bawah-air': keran(250, 70) + `<path d="M262 120 v170" stroke="${AIR}" stroke-width="44" stroke-linecap="round"/>` +
    gelembung([[230, 180, 8], [292, 220, 7]]) + tangan(180, 360, 1.05, 30) + tangan(330, 360, 1.05, -30, true),
  'tangan-di-pengering': `<rect x="60" y="70" width="380" height="16" rx="8" fill="${COKLAT}" ${sw}/>` +
    `<path d="M150 86 h200 v230 h-200z" fill="${HIJAU}" ${sw}/><path d="M150 260 h200 M150 285 h200" ${sw} stroke-width="5"/>` +
    tangan(140, 250, 1.0, 25) + tangan(360, 250, 1.0, -25, true),
  'kotak-bekal-di-tas': tas(250, 330, 1.05, true) + bekal(250, 180, 0.95) + panah(410, 300, 410, 160),
  'kotak-masuk-tas': tas(250, 350, 1.0, true) + bekal(250, 120, 0.9) + panah(410, 110, 410, 260),
  'loker-dengan-foto-anak': loker(250, 255),
  'tas-di-dalam-loker': `<g transform="translate(-20 0)">${loker(250, 255, tas(250, 290, 0.7) + '', true)}</g>`.replace(tas(250, 290, 0.7), `<g transform="translate(0 40)">${tas(0, 0, 0.7)}</g>`),
  'kursi-dengan-foto-anak': `<rect x="150" y="70" width="200" height="190" rx="18" fill="${COKLAT}" ${sw}/>${stiker(250, 165, 46)}` +
    `<rect x="120" y="260" width="260" height="46" rx="10" fill="${COKLAT}" ${sw}/><path d="M145 306 v140 M355 306 v140 M175 306 v110 M325 306 v110" ${sw} stroke-width="14"/>`,
  'papan-jadwal': `<rect x="80" y="40" width="340" height="420" rx="16" fill="#f7f3e8" ${sw}/>` +
    [0, 1, 2].map(i => `<rect x="115" y="${80 + i * 125}" width="100" height="100" rx="10" fill="${[HIJAU, BIRU, ORANYE][i]}" ${sw}/>` +
      `<path d="M240 ${130 + i * 125} h140" ${sw} stroke-width="10"/>` + (i === 0 ? `<path d="M135 ${130} l20 22 l45 -50" fill="none" stroke="#ffffff" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>` : '')).join(''),
  'pensil-masuk-kotak': `<rect x="90" y="300" width="320" height="120" rx="18" fill="${ORANYE}" ${sw}/><path d="M90 330 h320" ${sw}/>` +
    pensil(250, 150, 0, 0.95) + panah(250, 190, 250, 290),
  'tangan-menaruh-balok': balok(150, 380, 100, BIRU) + balok(250, 380, 100, HIJAU) + balok(200, 280, 100, ORANYE) +
    tangan(250, 70, 1.0, 180) + `<rect x="205" y="150" width="90" height="90" rx="8" fill="${MERAH}" ${sw}/>` + panah(370, 150, 370, 260),
  'kartu-istirahat': `<rect x="70" y="60" width="360" height="380" rx="26" fill="#eaf4ee" ${sw}/>` +
    `<path d="M130 380 q-20 -120 120 -130 q140 10 120 130 z" fill="${UNGU}" ${sw}/><path d="M170 330 q80 -40 160 0" fill="none" ${sw} stroke-width="5"/>` +
    `<circle cx="250" cy="160" r="70" fill="#ffffff" ${sw}/><rect x="218" y="122" width="22" height="76" rx="6" fill="${K}"/><rect x="260" y="122" width="22" height="76" rx="6" fill="${K}"/>`,
  'kartu-menunjuk-teman': orang(370, 330, 0.85, ORANYE) + tunjuk(150, 220, 1.1, 0) + panah(175, 290, 265, 290).replace(MERAH, MERAH),
};
(async () => {
  fs.mkdirSync('png', {recursive: true});
  const b = await chromium.launch(); const p = await b.newPage({viewport: {width: 500, height: 500}});
  for (const [nama, isi] of Object.entries(kartu)) {
    await p.setContent(`<html><body style="margin:0;background:#fff"><svg xmlns="http://www.w3.org/2000/svg" width="500" height="500" viewBox="0 0 500 500">${isi}</svg></body></html>`);
    await p.screenshot({path: `png/${nama}.png`});
  }
  // lembar kontak untuk diperiksa
  const sel = Object.keys(kartu).map(n => `<figure style="margin:6px;width:220px;text-align:center;font:13px sans-serif"><img src="file://${process.cwd()}/png/${n}.png" width="210" style="border:1px solid #ccc"><figcaption>${n}</figcaption></figure>`).join('');
  await p.setViewportSize({width: 1200, height: 1000});
  await p.setContent(`<div style="display:flex;flex-wrap:wrap">${sel}</div>`);
  await p.screenshot({path: 'lembar.png', fullPage: true});
  await b.close();
})();
