---
name: frontend-design
description: Design rules for the static site in public/ (built by src/build_site.py) - semantic HTML5, system-font typography, zero dependencies, automatic dark mode.
---
# Frontend Design Skill

When changing the site's HTML or CSS (the templates and `CSS` string in `src/build_site.py`):
1. **Zero dependencies**: No frameworks, CDNs, web fonts, or JavaScript. One hand-written stylesheet, `public/style.css`.
2. **Semantic HTML5**: `main`, `article`, `header`, `nav`, `time datetime=...`, real heading order (one `h1` per page). Every page sets `lang`, `charset`, `viewport`, and `<meta name="color-scheme" content="light dark">`.
3. **Typography**: System font stack, ~17px base, line-height ~1.6, measure capped at ~42rem, `text-wrap: balance` on headings.
4. **Dark mode**: Colors live as custom properties on `:root` and are redefined under `@media (prefers-color-scheme: dark)`. Never hard-code a color outside those two blocks.
5. **Accessibility**: Text contrast at least 4.5:1 in both themes, visible link styling, layout works at 320px wide with no horizontal scroll.
6. **Safety**: All article text goes through `html.escape`; links only allow `http(s)` URLs.
