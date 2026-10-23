// Live UTC clock in the status bar and the interactive coverage chart. Copied to public/ by build_site.py.
(() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

  const clock = document.getElementById("clock");
  if (clock) {
    const tick = () => { clock.textContent = new Date().toISOString().slice(11, 19); };
    tick();
    setInterval(tick, 1000);
  }

  const canvas = document.getElementById("coverage-chart");
  const dataEl = document.getElementById("coverage-data");
  if (!canvas || !dataEl) return;
  const data = JSON.parse(dataEl.textContent);
  if (!data.series.length) return;

  const css = getComputedStyle(document.documentElement);
  const color = (name) => css.getPropertyValue(name).trim();
  const colors = ["--blue", "--amber", "--red", "--green"].map(color);
  const grid = color("--line");
  const muted = color("--muted");
  const tip = document.getElementById("chart-tip");
  const ctx = canvas.getContext("2d");
  const pad = { l: 30, r: 14, t: 14, b: 24 };
  const n = data.days.length;
  const max = Math.max(1, ...data.series.flatMap((s) => s.values));
  const step = Math.max(1, Math.ceil(max / 4));
  const start = performance.now();
  let w = 0, h = 0, hover = -1;

  const x = (i) => pad.l + ((w - pad.l - pad.r) * i) / Math.max(1, n - 1);
  const y = (v) => h - pad.b - ((h - pad.t - pad.b) * v) / max;

  function size() {
    const dpr = window.devicePixelRatio || 1;
    w = canvas.clientWidth;
    h = canvas.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function draw(now) {
    const t = (now - start) / 1000;
    const reveal = reduce ? n - 1 : Math.min(1, t / 1.4) * (n - 1);
    ctx.clearRect(0, 0, w, h);

    ctx.font = '11px "Share Tech Mono", monospace';
    ctx.lineWidth = 1;
    ctx.strokeStyle = grid;
    ctx.fillStyle = muted;
    for (let v = 0; v <= max; v += step) {
      ctx.beginPath();
      ctx.moveTo(pad.l, y(v));
      ctx.lineTo(w - pad.r, y(v));
      ctx.stroke();
      ctx.fillText(String(v), 6, y(v) + 4);
    }
    const every = Math.ceil(n / Math.max(2, Math.floor(w / 70)));
    // every `every`-th day plus the last one, skipping a regular label that would collide with the last
    data.days.forEach((d, i) => { if ((i % every === 0 && n - 1 - i >= every) || i === n - 1) ctx.fillText(d, x(i) - 14, h - 6); });

    if (!reduce) { // scanning sweep line
      const sx = pad.l + ((t * 70) % (w - pad.l - pad.r));
      ctx.globalAlpha = 0.18;
      ctx.strokeStyle = colors[0];
      ctx.beginPath();
      ctx.moveTo(sx, pad.t);
      ctx.lineTo(sx, h - pad.b);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    if (hover >= 0) {
      ctx.setLineDash([3, 4]);
      ctx.strokeStyle = muted;
      ctx.beginPath();
      ctx.moveTo(x(hover), pad.t);
      ctx.lineTo(x(hover), h - pad.b);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    data.series.forEach((s, k) => {
      const c = colors[k];
      ctx.strokeStyle = c;
      ctx.lineWidth = 2;
      ctx.shadowColor = c;
      ctx.shadowBlur = 10;
      ctx.beginPath();
      for (let i = 0; i <= Math.floor(reveal); i++) (i ? ctx.lineTo : ctx.moveTo).call(ctx, x(i), y(s.values[i]));
      const frac = reveal - Math.floor(reveal);
      const i = Math.floor(reveal);
      if (frac > 0 && i + 1 < n) {
        ctx.lineTo(x(i) + (x(i + 1) - x(i)) * frac, y(s.values[i]) + (y(s.values[i + 1]) - y(s.values[i])) * frac);
      }
      ctx.stroke();

      const pulse = reduce ? 0 : (Math.sin(t * 3 + k) + 1) / 2;
      for (let j = 0; j <= Math.floor(reveal); j++) {
        if (!s.values[j] && j !== hover) continue; // only mark days with stories
        const r = j === hover ? 5 : j === n - 1 ? 3 + pulse * 2.5 : 2.5;
        ctx.fillStyle = c;
        ctx.beginPath();
        ctx.arc(x(j), y(s.values[j]), r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0;
    });

    if (!reduce) requestAnimationFrame(draw);
  }

  function showTip(e) {
    const rect = canvas.getBoundingClientRect();
    const i = Math.round(((e.clientX - rect.left - pad.l) / (w - pad.l - pad.r)) * (n - 1));
    hover = Math.min(n - 1, Math.max(0, i));
    tip.textContent = "";
    const head = document.createElement("div");
    head.textContent = data.days[hover];
    tip.append(head);
    data.series.forEach((s, k) => {
      const row = document.createElement("div");
      row.style.color = colors[k];
      row.textContent = `${s.name}: ${s.values[hover]}`;
      tip.append(row);
    });
    tip.hidden = false;
    const left = Math.min(x(hover) + 12, w - tip.offsetWidth - 4);
    tip.style.left = `${Math.max(4, left)}px`;
    tip.style.top = `${pad.t}px`;
    if (reduce) draw(performance.now());
  }

  canvas.addEventListener("pointermove", showTip);
  canvas.addEventListener("pointerleave", () => {
    hover = -1;
    tip.hidden = true;
    if (reduce) draw(performance.now());
  });
  window.addEventListener("resize", () => { size(); if (reduce) draw(performance.now()); });
  size();
  requestAnimationFrame(draw);
})();
