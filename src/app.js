// Theme toggle (remembered in localStorage) and the coverage chart. Copied to public/ by build_site.py.
(() => {
  const root = document.documentElement;
  const toggle = document.querySelector(".theme-toggle");
  let redrawChart = () => {};

  function label() {
    const dark = root.dataset.theme === "dark";
    toggle.textContent = dark ? "☀ Light" : "☾ Dark";
    toggle.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
  }

  if (toggle) {
    label();
    toggle.hidden = false; // only offered when this script runs
    toggle.addEventListener("click", () => {
      const dark = root.dataset.theme !== "dark";
      if (dark) root.dataset.theme = "dark";
      else delete root.dataset.theme;
      try { localStorage.setItem("theme", dark ? "dark" : "light"); } catch (e) { /* private mode: choice lasts this page only */ }
      label();
      redrawChart();
    });
  }

  const canvas = document.getElementById("coverage-chart");
  const dataEl = document.getElementById("coverage-data");
  if (!canvas || !dataEl) return;
  const data = JSON.parse(dataEl.textContent);
  if (!data.series.length) return;

  const tip = document.getElementById("chart-tip");
  const ctx = canvas.getContext("2d");
  const pad = { l: 22, r: 8, t: 8, b: 20 };
  const n = data.days.length;
  const max = Math.max(1, ...data.series.flatMap((s) => s.values));
  const step = Math.max(1, Math.ceil(max / 3));
  let w = 0, h = 0, hover = -1;

  const x = (i) => pad.l + ((w - pad.l - pad.r) * i) / Math.max(1, n - 1);
  const y = (v) => h - pad.b - ((h - pad.t - pad.b) * v) / max;
  const cssVar = (name) => getComputedStyle(root).getPropertyValue(name).trim();

  function size() {
    const dpr = window.devicePixelRatio || 1;
    w = canvas.clientWidth;
    h = canvas.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function draw() {
    const colors = data.series.map((_, k) => cssVar(`--c${k + 1}`));
    const line = cssVar("--line");
    const muted = cssVar("--muted");
    ctx.clearRect(0, 0, w, h);
    ctx.font = "11px Inter, system-ui, sans-serif";
    ctx.lineWidth = 1;
    ctx.strokeStyle = line;
    ctx.fillStyle = muted;
    for (let v = 0; v <= max; v += step) {
      ctx.beginPath();
      ctx.moveTo(pad.l, y(v));
      ctx.lineTo(w - pad.r, y(v));
      ctx.stroke();
      ctx.fillText(String(v), 4, y(v) + 4);
    }
    ctx.fillText(data.days[0], pad.l, h - 4);
    const last = data.days[n - 1];
    ctx.fillText(last, w - pad.r - ctx.measureText(last).width, h - 4);

    if (hover >= 0) {
      ctx.strokeStyle = muted;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(x(hover), pad.t);
      ctx.lineTo(x(hover), h - pad.b);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    data.series.forEach((s, k) => {
      ctx.strokeStyle = colors[k];
      ctx.lineWidth = 1.75;
      ctx.beginPath();
      s.values.forEach((v, i) => (i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v))));
      ctx.stroke();
      if (hover >= 0) {
        ctx.fillStyle = colors[k];
        ctx.beginPath();
        ctx.arc(x(hover), y(s.values[hover]), 3.5, 0, Math.PI * 2);
        ctx.fill();
      }
    });
  }

  canvas.addEventListener("pointermove", (e) => {
    const rect = canvas.getBoundingClientRect();
    const i = Math.round(((e.clientX - rect.left - pad.l) / (w - pad.l - pad.r)) * (n - 1));
    hover = Math.min(n - 1, Math.max(0, i));
    tip.textContent = "";
    const head = document.createElement("strong");
    head.textContent = data.days[hover];
    tip.append(head);
    data.series.forEach((s) => {
      const row = document.createElement("div");
      row.textContent = `${s.name}: ${s.values[hover]}`;
      tip.append(row);
    });
    tip.hidden = false;
    tip.style.left = `${Math.max(0, Math.min(x(hover) + 10, w - tip.offsetWidth))}px`;
    tip.style.top = "0px";
    draw();
  });
  canvas.addEventListener("pointerleave", () => {
    hover = -1;
    tip.hidden = true;
    draw();
  });
  window.addEventListener("resize", () => { size(); draw(); });

  redrawChart = draw;
  size();
  draw();
  document.fonts?.ready.then(draw); // redraw once Inter has loaded so axis labels use it
})();
