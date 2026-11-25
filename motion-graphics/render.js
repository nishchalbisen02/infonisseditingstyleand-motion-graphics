#!/usr/bin/env node
// Render an HTML motion-graphics template to a video file, frame by frame.
//
//   node motion-graphics/render.js <template.html> [options]
//
// Options:
//   --param key=value   Template text/colour, repeatable (-p name="Infoniss")
//   --size WxH          1920x1080, or a preset: hd, reel (1080x1920), square (1080x1080)
//   --fps N             Frames per second (default: template's mg-fps, else 30)
//   --duration S        Seconds (default: template's mg-duration, else 5)
//   --alpha             Transparent background -> ProRes 4444 .mov (Premiere, AE, Final Cut, DaVinci)
//   --green             Flat green background MP4 for chroma key (CapCut, KineMaster, VN on phone)
//   --still S           Save a single PNG frame at S seconds instead of a video
//   --out FILE          Output path (default: motion-graphics/output/<template>.mp4)
// Templates are animated with CSS animations (or a window.renderFrame(t) function).
// Every animation is paused and seeked to each frame's time, so output is smooth and exact.

const { chromium } = require('playwright');
const { spawn } = require('child_process');
const { once } = require('events');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const PRESETS = { hd: '1920x1080', reel: '1080x1920', square: '1080x1080' };

function parseArgs(argv) {
  const opts = { params: {} };
  const positional = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => {
      const v = argv[++i];
      if (v === undefined) throw new Error(`${a} needs a value`);
      return v;
    };
    switch (a) {
      case '-o': case '--out': opts.out = next(); break;
      case '--size': opts.size = next(); break;
      case '--fps': opts.fps = Number(next()); break;
      case '--duration': opts.duration = Number(next()); break;
      case '--alpha': opts.alpha = true; break;
      case '--green': opts.green = true; break;
      case '--still': opts.still = Number(next()); break;
      case '-p': case '--param': {
        const kv = next();
        const eq = kv.indexOf('=');
        if (eq < 1) throw new Error(`--param expects key=value, got "${kv}"`);
        opts.params[kv.slice(0, eq)] = kv.slice(eq + 1);
        break;
      }
      case '-h': case '--help': opts.help = true; break;
      default:
        if (a.startsWith('-')) throw new Error(`Unknown option ${a}`);
        positional.push(a);
    }
  }
  opts.input = positional[0];
  return opts;
}

function readMeta(html, name) {
  const m = html.match(new RegExp(`<meta\\s+name=["']${name}["']\\s+content=["']([^"']+)["']`, 'i'));
  return m ? m[1] : undefined;
}

function parseSize(s) {
  const m = String(PRESETS[s] || s).match(/^(\d+)x(\d+)$/);
  if (!m) throw new Error(`Bad --size "${s}" (use WxH, hd, reel or square)`);
  const [w, h] = [Number(m[1]), Number(m[2])];
  if (w % 2 || h % 2) throw new Error('Width and height must be even numbers');
  return { width: w, height: h };
}

function ffmpegArgs({ fps, alpha, out }) {
  const input = ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-'];
  if (alpha) {
    return [...input, '-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le', '-vendor', 'apl0', out];
  }
  return [...input, '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out];
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help || !opts.input) {
    console.log(fs.readFileSync(__filename, 'utf8').split('\n').slice(1, 17).map((l) => l.replace(/^\/\/ ?/, '')).join('\n'));
    process.exit(opts.input ? 0 : 1);
  }

  const input = path.resolve(opts.input);
  const html = fs.readFileSync(input, 'utf8');
  const name = path.basename(input, path.extname(input));
  const size = parseSize(opts.size || readMeta(html, 'mg-size') || 'hd');
  const fps = opts.fps || Number(readMeta(html, 'mg-fps')) || 30;
  const duration = opts.duration || Number(readMeta(html, 'mg-duration')) || 5;
  const still = Number.isFinite(opts.still);
  if (opts.alpha && opts.green) throw new Error('Use either --alpha or --green, not both');

  const ext = still ? '.png' : opts.alpha ? '.mov' : '.mp4';
  const suffix = (opts.alpha ? '-alpha' : opts.green ? '-green' : '') + (still ? '-still' : '');
  const out = path.resolve(opts.out || path.join(__dirname, 'output', `${name}${suffix}${ext}`));
  fs.mkdirSync(path.dirname(out), { recursive: true });

  const query = new URLSearchParams({
    ...opts.params,
    render: '1',
    ...(opts.alpha ? { alpha: '1' } : {}),
    ...(opts.green ? { green: '1' } : {}),
  });
  const url = `${pathToFileURL(input).href}?${query}`;

  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: size, deviceScaleFactor: 1 });
    page.on('pageerror', (e) => console.warn(`[page error] ${e.message}`));
    page.on('console', (m) => { if (m.type() === 'error') console.warn(`[page console] ${m.text()}`); });

    await page.goto(url, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    await page.evaluate(() => {
      window.__mgSeek = (ms) => {
        if (typeof window.renderFrame === 'function') window.renderFrame(ms / 1000);
        for (const a of document.getAnimations()) {
          a.pause();
          a.currentTime = ms;
        }
        return new Promise((r) => requestAnimationFrame(() => r()));
      };
    });

    const shot = () => page.screenshot({ type: 'png', omitBackground: !!opts.alpha });

    if (still) {
      await page.evaluate((ms) => window.__mgSeek(ms), opts.still * 1000);
      fs.writeFileSync(out, await shot());
      console.log(`Saved ${path.relative(process.cwd(), out)} (${size.width}x${size.height}, t=${opts.still}s)`);
      return;
    }

    const ff = spawn('ffmpeg', ffmpegArgs({ fps, alpha: opts.alpha, out }), { stdio: ['pipe', 'inherit', 'inherit'] });
    const ffDone = once(ff, 'close');
    const frames = Math.round(duration * fps);
    let lastPct = -1;

    for (let i = 0; i < frames; i++) {
      await page.evaluate((ms) => window.__mgSeek(ms), (i / fps) * 1000);
      if (!ff.stdin.write(await shot())) await once(ff.stdin, 'drain');
      const pct = Math.floor(((i + 1) / frames) * 10) * 10;
      if (pct !== lastPct) { lastPct = pct; process.stdout.write(`\rRendering ${name}: ${pct}%`); }
    }
    ff.stdin.end();
    const [code] = await ffDone;
    process.stdout.write('\n');
    if (code !== 0) throw new Error(`ffmpeg exited with code ${code}`);

    const mb = (fs.statSync(out).size / 1024 / 1024).toFixed(1);
    console.log(`Saved ${path.relative(process.cwd(), out)} (${size.width}x${size.height}, ${fps}fps, ${duration}s, ${mb} MB)`);
  } finally {
    await browser.close();
  }
}

main().catch((e) => {
  console.error(`Error: ${e.message}`);
  process.exit(1);
});
