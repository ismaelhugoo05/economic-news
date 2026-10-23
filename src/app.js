// Topic filters, search modal, About drawer, reading progress and copy-link. Copied to public/ by build_site.py.
(() => {
  const root = document.body.dataset.root || "";

  // --- dialogs (search modal, About & Methodology drawer) ---
  const searchInput = document.getElementById("search-input");
  function openDialog(id, target) {
    const dialog = document.getElementById(id);
    if (!dialog) return;
    if (!dialog.open) dialog.showModal();
    if (id === "search") { searchInput.select(); loadIndex(); }
    if (target) document.getElementById(target)?.scrollIntoView({ block: "start" });
  }
  document.querySelectorAll("[data-open]").forEach((button) =>
    button.addEventListener("click", () => openDialog(button.dataset.open, button.dataset.target)));
  document.querySelectorAll("[data-close]").forEach((button) =>
    button.addEventListener("click", () => button.closest("dialog").close()));
  document.querySelectorAll("dialog").forEach((dialog) =>
    dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); })); // click on the backdrop
  addEventListener("keydown", (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName) || document.activeElement.isContentEditable;
    if (e.key === "/" && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      openDialog("search");
    }
  });

  // --- instant search over search.json ---
  const results = document.getElementById("search-results");
  let index = null;
  async function loadIndex() {
    if (index) return;
    try {
      index = await (await fetch(root + "search.json")).json();
    } catch {
      index = [];
      hint("Search is unavailable right now.");
      return;
    }
    render();
  }
  function hint(text) {
    results.replaceChildren();
    const li = document.createElement("li");
    li.className = "hint";
    li.textContent = text;
    results.append(li);
  }
  function highlight(el, text, terms) {
    // wrap matched terms in <mark>, building nodes so story text is never parsed as HTML
    const pattern = terms.length ? new RegExp(`(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi") : null;
    (pattern ? text.split(pattern) : [text]).forEach((part, i) => {
      if (i % 2) { const m = document.createElement("mark"); m.textContent = part; el.append(m); }
      else el.append(part);
    });
  }
  function render() {
    if (!index) return;
    const terms = searchInput.value.toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) return hint(`Type to search ${index.length} reports by headline, tag or summary.`);
    const matches = index.filter((r) => {
      const hay = `${r.t} ${r.g} ${r.s}`.toLowerCase();
      return terms.every((t) => hay.includes(t));
    }).slice(0, 25);
    if (!matches.length) return hint(`No reports match “${searchInput.value.trim()}”.`);
    results.replaceChildren(...matches.map((r) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = root + r.u;
      const title = document.createElement("strong");
      highlight(title, r.t, terms);
      const meta = document.createElement("span");
      meta.textContent = `${r.g} · ${r.d}`;
      const summary = document.createElement("span");
      highlight(summary, r.s, terms);
      a.append(title, meta, summary);
      li.append(a);
      return li;
    }));
  }
  searchInput?.addEventListener("input", render);
  searchInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") results.querySelector("a")?.click();
    if (e.key === "ArrowDown") { e.preventDefault(); results.querySelector("a")?.focus(); }
  });

  // --- topic filters (front page only; elsewhere the links open the front page with ?topic=) ---
  const grid = document.querySelector(".cards[data-filterable]");
  const links = document.querySelectorAll("[data-filter]");
  function applyFilter(filter) {
    links.forEach((a) => a.setAttribute("aria-current", String(a.dataset.filter === filter)));
    if (!grid) return;
    const active = filter !== "all";
    let shown = 0;
    grid.querySelectorAll(":scope > li").forEach((li) => {
      const match = active && li.dataset.filters.split(" ").includes(filter);
      li.classList.toggle("match", match);
      shown += match;
    });
    grid.classList.toggle("filtered", active);
    document.querySelector(".front").classList.toggle("filtering", active);
    document.querySelector(".empty").hidden = !active || shown > 0;
    const label = [...links].find((a) => a.dataset.filter === filter)?.textContent;
    document.getElementById("latest").textContent = active ? `${label} · ${shown} report${shown === 1 ? "" : "s"}` : "Latest reports";
  }
  const initial = new URLSearchParams(location.search).get("topic");
  const known = [...links].some((a) => a.dataset.filter === initial);
  applyFilter(grid && known ? initial : grid ? "all" : null);
  if (grid) {
    links.forEach((a) => a.addEventListener("click", (e) => {
      e.preventDefault();
      applyFilter(a.dataset.filter);
      history.replaceState(null, "", a.dataset.filter === "all" ? location.pathname : `?topic=${a.dataset.filter}`);
    }));
  }

  // --- reading progress bar (report pages) ---
  const bar = document.querySelector(".progress");
  const article = document.querySelector(".article");
  if (bar && article) {
    const update = () => {
      const rect = article.getBoundingClientRect();
      const total = rect.height - innerHeight;
      const progress = total > 0 ? Math.min(1, Math.max(0, -rect.top / total)) : 1;
      bar.style.transform = `scaleX(${progress})`;
    };
    addEventListener("scroll", update, { passive: true });
    addEventListener("resize", update);
    update();
  }

  // --- copy link ---
  function legacyCopy(text) { // for browsers or embedded views that block the async Clipboard API
    const box = Object.assign(document.createElement("textarea"), { value: text, readOnly: true });
    box.style.cssText = "position:fixed;opacity:0";
    document.body.append(box);
    box.select();
    const ok = document.execCommand("copy");
    box.remove();
    if (!ok) throw new Error("copy blocked");
  }
  document.querySelectorAll("[data-copy]").forEach((button) => button.addEventListener("click", async () => {
    try {
      try { await navigator.clipboard.writeText(location.href); } catch { legacyCopy(location.href); }
      button.textContent = "Copied!";
      button.classList.add("done");
    } catch {
      button.textContent = "Copy failed";
    }
    setTimeout(() => { button.textContent = "Copy link"; button.classList.remove("done"); }, 2000);
  }));
})();
