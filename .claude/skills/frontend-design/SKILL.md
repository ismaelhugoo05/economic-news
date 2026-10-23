---
name: frontend-design
description: Design rules for the static site in public/ (built by src/build_site.py and src/app.js) - World Economy Watch, a digital editorial magazine with a navy masthead, cards, and honest data.
---
# Frontend Design Skill

When changing the site's HTML, CSS or JS (the templates and `CSS` string in `src/build_site.py`, and `src/app.js`, which the build copies to `public/`):
1. **Look**: Digital editorial magazine. `#f8fafc` canvas, white cards with soft borders, 10px corners, `0 8px 24px rgba(15,23,42,.06)` shadows and a small hover lift. Deep navy (`#0b132b`) sticky header with `backdrop-filter: blur(12px)` and an amber edition badge. Colors live only as custom properties on `:root`.
2. **Typography**: Google Fonts `Newsreader` (bold) for headlines, the wordmark and article body; `Plus Jakarta Sans` for navigation, labels and summaries. No other fonts or libraries.
3. **Front page**: Lead card with the decorative SVG wave graphic (seeded per story), then "Latest reports" cards in two columns; the sidebar holds the Market stance dial. Topic tags are tinted pills (`#POLICY`, `#MARKETS`, ...). Header filters (Markets, Policy, Commodities, Global Trade) filter cards client-side and set `?topic=`.
4. **Report pages**: 48rem card with tag, headline, meta, primary-source button, Copy link, an Executive summary of the first 3 key-data bullets, and a 2px amber reading-progress bar.
5. **Shared chrome**: Market ribbon with 1-month sparklines; search modal (button or `/`) over `search.json`; About & Methodology drawer; 4-column footer (brand and cadence, coverage, platform links incl. `feed.xml`, legal and AI disclosure).
6. **Honest data and claims**: Ribbon, sparklines and dial are a build-time Yahoo Finance snapshot labelled with its time; the dial is a plain count of benchmarks up over a month. Never call the site live or claim fact-checking it does not do: reports are written by Gemini with automated structure checks and no human fact-check, and every report links its primary source.
7. **Accessibility**: Native `<dialog>` for modals, visible focus outlines, text contrast at least 4.5:1, all motion off under `prefers-reduced-motion`, no horizontal page scroll at 320px. The site must stay readable without JS (filters fall back to showing the latest 9).
8. **Safety**: All article text goes through `html.escape`; search results are built with DOM nodes, never innerHTML; links only allow `http(s)` URLs.
