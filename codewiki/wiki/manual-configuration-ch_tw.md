---
id: manual-configuration
type: manual
status: stable
parent: user-manual
title: 設定與疑難排解
summary: 選擇正確的 Wiki 實例，設定原始碼掃描與預覽，並解決常見的建置及查詢問題。
related:
- manual-getting-started
- manual-writing
- manual-reading
owns: []
depends_on: []
diagram_links: {}
refs: []
decisions: []
---

## 重點摘要 {#tl-dr}

- 設定與 frontmatter 中的路徑，都從 `wiki.config.yaml` 所在目錄解析。
- 同時操作多個實例時，請傳入 `--config`。
- 嚴格建置會回報錯誤，驗證失敗時保留先前發佈的輸出。

## 選擇實例 {#select-instance}

Build、query 與 serve 會從工作目錄向上尋找設定。明確指定的 `--config` 優先於 `CODE_WIKI_CONFIG`，環境變數又優先於自動探索。

```sh
codewiki build --strict --config /path/to/project/codewiki/wiki.config.yaml
codewiki query --config /path/to/project/codewiki/wiki.config.yaml tree
codewiki serve --config /path/to/project/codewiki/wiki.config.yaml --no-open
```

三個命令請使用同一份設定。若命令顯示錯誤的專案，請檢查工作目錄與 `CODE_WIKI_CONFIG`。

## 設定專案 {#settings}

採用預設 `project/codewiki/wiki.config.yaml` 配置時，常見設定如下：

```yaml
wiki_dir: wiki
site_dir: site
code_roots:
  - ../src
  - ../tests
exclude_globs:
  - '*/build/*'
  - '*/__pycache__/*'
readonly_globs:
  - '../src/vendor/*'
languages: {}
max_snippet_lines: 120
editor_url_template: 'vscode://file/{abs}:{line}'
project:
  name: My Project
  subtitle: Project documentation
```

| 設定 | 用途 |
| --- | --- |
| `wiki_dir` | 作者維護的 Markdown 目錄 |
| `site_dir` | 產生的 HTML 目錄；應與輸入分開 |
| `code_roots` | 要掃描的原始碼檔案或目錄 |
| `exclude_globs` | 原始碼掃描要排除的路徑 |
| `readonly_globs` | 不允許加入原始碼標籤的路徑；改用文件端參照 |
| `languages` | 副檔名對應覆寫；空對應表示使用內建偵測 |
| `max_snippet_lines` | 渲染宣告片段的最大行數 |
| `editor_url_template` | 使用絕對路徑與行號佔位符的編輯器連結 |
| `project` | 網站名稱與副標題 |

客製化主題時，只需將要覆寫的檔案放入 `wiki/_theme/`，例如 `style.css`。其他檔案仍使用套件預設值。變更設定或主題後請重新建置。

## 預覽變更 {#preview}

```sh
codewiki serve --no-open --port 8001
```

開啟 `http://localhost:8001`。預覽會監看 Markdown、原始碼根目錄、設定、審查紀錄與主題檔案，在變更後重新建置並通知瀏覽器。修正畫面上的驗證錯誤後即可恢復正常預覽。變更 `site_dir` 後請重新啟動伺服器。預設連接埠為 8000；`--no-open` 會停用自動開啟瀏覽器。

## 疑難排解 {#troubleshooting}

| 症狀 | 處理方式 |
| --- | --- |
| 找不到 `codewiki` 命令 | 啟用安裝框架的環境，並嘗試在其中執行 `python -m codewiki --help`。 |
| 找不到 `wiki.config.yaml` | 在已初始化的專案中執行、傳入 `--config`，或先初始化。 |
| 新頁面沒有出現 | 檢查 YAML frontmatter 與唯一 ID，移出底線開頭的資料夾，再重新建置。 |
| 頁面位於錯誤的階層 | 將 `parent` 設成預期的頁面 ID；獨立根頁使用 `null`。 |
| 嚴格建置回報父頁或相關頁失效 | 修正參照 ID 或還原缺少的頁面。 |
| 原始碼參照失效 | 檢查相對於設定目錄的路徑、掃描根目錄、排除規則與符號拼字。 |
| 標籤指向不存在的錨點 | 確認 `page-id.slug` 符合頁面 ID 與明確的 `{#slug}` 標題，再重新建置。 |
| 錨點顯示未綁定 | 若章節描述實作，請補上原始碼證據。純操作指南可維持未綁定；這只是資訊提示。 |
| 查詢回報索引過期或不相容 | 使用已安裝的框架與同一份設定重新建置，再重試查詢。 |
| 出錯後 HTML 仍顯示舊版 | 修正建置錯誤後重新建置；嚴格驗證失敗會保留上次發佈的輸出。 |
| 頁面尚未審查或審查後已有變更 | 檢查目前原始碼與說明，再使用附帶理由的 `review updated` 或 `review pass`。重新建置不會確認審查。 |
| 審查紀錄無效 | 在 Git 中修復結構或內容；不要刪除紀錄來跳過審查。`review check` 會回報錯誤。 |
| 預覽連接埠已被使用 | 使用 `--port` 選擇其他連接埠。 |

使用 `codewiki build --help`、`codewiki query --help`、`codewiki serve --help` 與 `codewiki init --help`，查看已安裝版本的命令選項。
