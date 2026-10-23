---
name: frontend-design
description: Design rules for the static site in public/ (built by src/build_site.py and src/app.js) - dark financial-intelligence terminal theme, semantic HTML5, honest data.
---
# Frontend Design Skill

When changing the site's HTML, CSS or JS (the templates and `CSS` string in `src/build_site.py`, and `src/app.js`, which the build copies to `public/`):
1. **Dependencies**: Google Fonts (`Share Tech Mono` for tickers, timestamps, badges and labels; `Inter` for reading text) and nothing else. No frameworks, chart libraries or CDNs; charts are vanilla Canvas in `app.js`. The site must stay readable if fonts or JS fail to load.
2. **Semantic HTML5**: `main`, `article`, `aside`, `header`, `nav`, `time datetime=...`, one `h1` per page (visually hidden on the home page). Every page sets `lang`, `charset`, `viewport`, and `<meta name="color-scheme" content="dark">`.
3. **Theme**: Dark terminal: `#070a13` background with faint gridlines and scanlines; neon blue `#00f0ff` (links, focus, panel corners), amber `#ffb703` (badges, log levels), red `#ff003c` (falling markets, NEW flags), green `#00ff9c` (rising markets, status). Colors live as custom properties on `:root`; never hard-code a color anywhere else (use `color-mix` for tints).
4. **Honest data**: Everything that looks live must be real. Ticker prices are a build-time Yahoo Finance snapshot labelled with its time; the chart plots real story counts per topic; the system log lists real story timestamps. Never show invented prices, latencies or sentiment.
5. **Layout**: Home page is a HUD grid: coverage chart, lead brief and 9 briefs on the left, a sticky sidebar (system log, key data) on the right; one column on phones. Article pages are a 720px reading column.
6. **Interaction & accessibility**: Whole briefs are clickable with a glow on hover and focus. The ticker pauses on hover. All motion (marquee, pulses, chart animation, cascading log) stops under `prefers-reduced-motion`. Text contrast at least 4.5:1; layout works at 320px with no horizontal page scroll.
7. **Safety**: All article text goes through `html.escape`; links only allow `http(s)` URLs; JSON embedded in `<script>` escapes `</`.
