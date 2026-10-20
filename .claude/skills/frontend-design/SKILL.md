---
name: frontend-design
description: Design rules for the static site in public/ (built by src/build_site.py) - semantic HTML5, serif headlines on an FT-style salmon newsprint theme, zero dependencies.
---
# Frontend Design Skill

When changing the site's HTML or CSS (the templates and `CSS` string in `src/build_site.py`):
1. **Zero dependencies**: No frameworks, CDNs, web fonts, or JavaScript. One hand-written stylesheet, `public/style.css`.
2. **Semantic HTML5**: `main`, `article`, `header`, `nav`, `time datetime=...`, real heading order (one `h1` per page). Every page sets `lang`, `charset`, `viewport`, and `<meta name="color-scheme" content="light">`.
3. **Typography**: Editorial serif headings (Georgia/Merriweather stack, no web fonts), system sans-serif body, `text-wrap: balance` on headings. Article text column max 720px.
4. **Theme**: Light only, Financial Times newsprint: salmon `#fff1e5` page, `#fff8f2` card surfaces, `#ead8cb` warm hairline rules, `#141414` headline ink, `#333` body, claret `#990f3d` for badges, links and buttons, navy `#0f2537` for hover states. Colors live as custom properties on `:root`; never hard-code a color anywhere else.
5. **Interaction & accessibility**: Whole cards are clickable (2px lift, accent border, title turns claret on hover) with a visible focus outline; all motion is off under `prefers-reduced-motion`. Text contrast at least 4.5:1, layout works at 320px wide with no horizontal scroll.
6. **Safety**: All article text goes through `html.escape`; links only allow `http(s)` URLs.
