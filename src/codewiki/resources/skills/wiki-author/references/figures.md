# Hand-drawn SVG figures

Use an SVG figure only for what Mermaid cannot express: timing diagrams, memory or
register layouts, protocol frames, or lanes whose placement carries meaning. Keep
flowcharts, sequences, and state machines in Mermaid so they stay linkable text.

## Reference the file

Store the SVG beside the page (for example `wiki/figures/`) and put the image on a
line of its own, optionally followed by a caption paragraph:

```markdown
![Hold key and latch pair timing](figures/latch-timing.svg)
Figure: Same key sequence, two results.
```

The path is relative to the Markdown file and must stay inside the wiki instance.
A translation may reference its own localized copy, such as `latch-timing-ch_tw.svg`.

## Draw with theme classes

Give the root `<svg>` a `viewBox` and no fixed colors; the page theme supplies them
and switches for dark mode. Use double- or single-quoted attributes.

| Class | Use |
| --- | --- |
| `fig-text` | Ordinary text; combine with `fig-muted`, `fig-code`, `fig-title` |
| `fig-label`, `fig-accent` | Text in the group color: lane titles, highlights |
| `fig-box` | Box with page background and group-colored border |
| `fig-tint` | Box filled with the group's soft color |
| `fig-lane` | Soft background band without border |
| `fig-line` | Connector or axis; add `fig-dash` for dashed |
| `fig-wave` | Signal or state waveform (`polyline`) |
| `fig-head` | Path inside a `<marker>` used as an arrowhead |
| `fig-grid` | Dotted guide line |
| `fig-halo` | Outline that keeps text readable over lines |

Set `data-group="<group>"` on an element or `<g>` to color everything inside it with
a group declared in `wiki.config.yaml`. Elements without a group use neutral colors.
Wrap a label or box in `<a data-link="<page-id>">` or `<a data-link="<page-id.slug>">`
to link it; the build resolves and validates the target like `diagram_links`.

## Rules

- Include `<title>` (and `<desc>` for complex figures) and reference them with
  `aria-labelledby`; IDs are prefixed per figure, so plain names are safe.
- No `<script>`, `<iframe>`, `<embed>`, `<object>`, `on*=` handlers, or
  `javascript:` URLs; strict builds reject them.
- Show only behavior you verified in source; a figure is an explanation, and the
  page's review covers it. Editing the SVG makes the page outdated for review.
- Run `codewiki build --strict` and inspect the page in light and dark mode.

## Minimal example

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 120" aria-labelledby="t">
  <title id="t">Key level and active layer</title>
  <g data-group="riscv">
    <text x="10" y="40" class="fig-label">KEY</text>
    <polyline class="fig-wave" points="120,50 220,50 220,25 380,25 380,50 580,50"/>
  </g>
  <a data-link="layer-switch">
    <g data-group="cm33">
      <text x="10" y="95" class="fig-label">LAYER</text>
      <polyline class="fig-wave" points="120,105 240,105 240,80 400,80 400,105 580,105"/>
    </g>
  </a>
</svg>
```
