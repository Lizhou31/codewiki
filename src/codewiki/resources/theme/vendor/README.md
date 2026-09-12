Vendored browser assets so the generated site works with no network access.

| File                | Package                      | Version |
|---------------------|------------------------------|---------|
| `mermaid.min.js`    | `mermaid` (UMD build)        | 11.17.2 |
| `highlight.min.js`  | `@highlightjs/cdn-assets`    | 11.12.0 |
| `hljs-light.css`    | `@highlightjs/cdn-assets`    | 11.12.0 |
| `hljs-dark.css`     | `@highlightjs/cdn-assets`    | 11.12.0 |

Refresh with:

    npm pack mermaid@11 @highlightjs/cdn-assets@11
    # extract, then copy dist/mermaid.min.js, highlight.min.js, styles/github*.css

Licences are alongside (both MIT / BSD-3-Clause respectively).
