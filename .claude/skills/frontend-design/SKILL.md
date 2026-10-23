---
name: frontend-design
description: Design rules for the static site in public/ (built by src/build_site.py) - World Economy Watch, a print-style financial broadsheet on newsprint cream.
---
# Frontend Design Skill

When changing the site's HTML or CSS (the templates and `CSS` string in `src/build_site.py`):
1. **A newspaper, not an app**: No cards, drop shadows, rounded corners, pill badges, charts, canvas widgets, theme toggles, live readouts or JavaScript. Sections are divided with hairline rules like a broadsheet.
2. **Palette**: Newsprint cream `#faf7f2` page, ink `#111827` headlines, `#1f2937` body text, `#57534e` secondary text, `#e5e0d8` hairlines, `#111827` for strong rules, burgundy `#881337` for section labels and the source link. Colors live only as custom properties on `:root`. Light only.
3. **Typography**: Google Fonts `Playfair Display` for the nameplate and all headlines; `Source Serif 4` for body, standfirsts and labels. Section labels are small uppercase burgundy with wide tracking. Article pages open with a drop cap.
4. **Layout**: Masthead = edition line (Global Edition, full date, Published daily) over a hairline, the "World Economy Watch" nameplate, then a double rule with the markets line. Front page = one lead story (grand headline beside a 2-sentence standfirst and the "Global Desk — <date>" dateline), then "Latest Reports" in a 3-column grid with 1px hairline dividers (one column below 56rem). Article pages are a 42rem reading column.
5. **Honest data**: The markets line is a build-time Yahoo Finance snapshot labelled "Markets as of <time>"; never show invented prices. Every article credits its primary source.
6. **Semantic HTML5 & accessibility**: `main`, `article`, `header`, `footer`, `time datetime=...`, one `h1` per page (visually hidden on the front page). Text contrast at least 4.5:1, visible focus outlines, no horizontal page scroll at 320px.
7. **Safety**: All article text goes through `html.escape`; links only allow `http(s)` URLs.
