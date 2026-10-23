---
name: frontend-design
description: Design rules for the static site in public/ (built by src/build_site.py and src/app.js) - calm editorial layout, light/dark toggle, honest data.
---
# Frontend Design Skill

When changing the site's HTML, CSS or JS (the templates and `CSS` string in `src/build_site.py`, and `src/app.js`, which the build copies to `public/`):
1. **Calm first**: Clear hierarchy and breathing room. No diagnostic readouts, fake terminal logs, scanlines, glows, blinking or flashing. Motion is limited to short color/background transitions.
2. **Dependencies**: Google Fonts `Inter` and nothing else. No frameworks, chart libraries or CDNs; the chart is vanilla Canvas in `app.js`. The site must stay readable if fonts or JS fail to load (the theme toggle only appears when JS runs).
3. **Semantic HTML5**: `main`, `article`, `aside`, `header`, `nav`, `time datetime=...`, one `h1` per page (visually hidden on the home page).
4. **Theme**: Light is the default: `#f4f5f7` page, `#fff` cards, `#1e293b` text, `#0f172a` headlines, `#e2e8f0` borders. Dark (`:root[data-theme="dark"]`): `#0b0f19` page, `#151d2e` cards, light grey text, muted amber/emerald accents, no pure black or neon. The toggle stores `theme` in `localStorage`; an inline head script applies a saved dark choice before first paint. Colors live only as custom properties in those two blocks, chart series use `--c1`..`--c4`.
5. **Layout**: Home page: one lead story card (headline, 2-sentence summary, generous padding), then the next 9 stories in a 2-column list with divider lines; the coverage chart is a compact card in the sidebar. Article pages are a 720px reading column.
6. **Honest data**: Ticker values are a build-time Yahoo Finance snapshot labelled "as of" its time (S&P 500, US 10Y, crude, gold, USD/EUR); the chart plots real story counts. Never show invented prices or metrics.
7. **Accessibility**: Text contrast at least 4.5:1 in both themes, visible focus outlines, whole cards clickable, transitions off under `prefers-reduced-motion`, no horizontal page scroll at 320px.
8. **Safety**: All article text goes through `html.escape`; links only allow `http(s)` URLs; JSON embedded in `<script>` escapes `</`.
