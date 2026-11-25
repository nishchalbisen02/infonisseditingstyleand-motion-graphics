// Shared helpers for motion-graphics templates.
// - Reads ?key=value params from the URL (render.js passes --param values this way).
// - Adds class "alpha" on <html> when rendering with a transparent background.
// - In a normal browser (preview), loops the animation so it can be watched on a phone.
(function () {
  const qs = new URLSearchParams(location.search);
  const meta = (name) => document.querySelector(`meta[name="${name}"]`)?.content;

  const mg = {
    isRender: qs.has('render'),
    alpha: qs.get('alpha') === '1',
    duration: Number(meta('mg-duration') || 5),

    // Template defaults overridden by URL params.
    params(defaults) {
      const out = { ...defaults };
      for (const [k, v] of qs) if (k in defaults) out[k] = v;
      return out;
    },

    // Accept "ff3d6e" or "#ff3d6e".
    color(v) {
      return /^[0-9a-f]{3,8}$/i.test(v) ? `#${v}` : v;
    },

    // Wrap each word of `el` in a mask so it can rise into view.
    // Splits on spaces only, so Hindi conjuncts and matras stay intact.
    splitWords(el, { start = 0, stagger = 0.08 } = {}) {
      const words = el.textContent.trim().split(/\s+/);
      el.textContent = '';
      words.forEach((word, i) => {
        const mask = document.createElement('span');
        mask.className = 'word';
        const inner = document.createElement('span');
        inner.textContent = word;
        inner.style.animationDelay = `${(start + i * stagger).toFixed(3)}s`;
        mask.appendChild(inner);
        el.appendChild(mask);
        if (i < words.length - 1) el.appendChild(document.createTextNode(' '));
      });
      return words.length;
    },
  };

  if (mg.alpha) document.documentElement.classList.add('alpha');

  // Flat chroma-key green background (?green=1) for phone editors that use chroma key.
  if (qs.get('green') === '1') {
    document.documentElement.classList.add('green');
    const s = document.createElement('style');
    s.textContent = 'html.green body{background:#00b140 !important} html.green .backdrop{display:none !important}';
    document.head.appendChild(s);
  }

  if (!mg.isRender) {
    window.addEventListener('load', () => {
      setInterval(() => {
        for (const a of document.getAnimations()) {
          a.currentTime = 0;
          a.play();
        }
      }, (mg.duration + 0.8) * 1000);
    });
  }

  window.mg = mg;
})();
