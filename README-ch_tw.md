# CodeWiki

[English](README.md)

獨立版本管理的架構文件框架，讓文件與各專案的原始碼放在一起。Markdown 保存說明，原始碼標籤與符號參照在建置時附上實作。同一份文件透過靜態 HTML 服務人類讀者，並透過漸進式 CLI 查詢服務 LLM。

本儲存庫在 `codewiki/` 中記錄框架自身。

[使用手冊](codewiki/wiki/user-manual-ch_tw.md) 涵蓋安裝、閱讀與查詢、撰寫頁面及設定。它在建置網站中是與架構並列的獨立頂層區段（`codewiki/site/user-manual-ch_tw.html`）。

```text
Code_Wiki/                    # 工作區，不是 Git 儲存庫
├── P729/                     # 目標測試專案，有自己的儲存庫
└── codewiki/                 # 本框架儲存庫
    ├── src/codewiki/         # Python 套件與共用資源
    ├── codewiki/             # 框架自己的 Wiki 實例
    │   ├── wiki.config.yaml
    │   ├── wiki/             # 架構與使用手冊頁面
    │   └── site/             # 產生的 HTML
    ├── tests/
    └── pyproject.toml
```

請在框架儲存庫（`Code_Wiki/codewiki/`）中執行下列命令。

## 安裝與試用

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
codewiki build --strict
codewiki serve --no-open
```

開啟 http://localhost:8000，或直接開啟 `codewiki/site/index.html`。網站可離線運作，Mermaid 與語法醒目提示資產均隨附。

```sh
codewiki query tree
codewiki query doc architecture
codewiki query section architecture.pipeline
codewiki query symbol codewiki.build.run
codewiki query source codewiki.build.run --limit 40
codewiki query --json search parsing --limit 5
```

## 在其他專案加入 Wiki

在該專案使用的環境安裝此套件，再執行：

```sh
codewiki init --root /path/to/project --code-root src --name 'My Project'
cd /path/to/project
codewiki build --strict
```

專案會取得 `codewiki/wiki.config.yaml`、Markdown、可重用頁面範本、可攜式技能、選用整合範例，以及 `codewiki/` 中的 `AGENTS.md`。核心與預設主題留在已安裝套件中。初始化也會在根目錄 `AGENTS.md` 加入帶標記的實例指南參照，保留既有指示並避免重複加入。從 `codewiki/skills/` 載入技能，或將需要的技能目錄複製到客戶端支援的位置。初始化保留既有檔案。

設定與 frontmatter 的路徑相對於設定所在目錄。需要時在每個命令傳入 `--config path/to/wiki.config.yaml`；否則會從工作目錄向上探索。`CODE_WIKI_CONFIG` 可明確選擇實例。也可用 `python -m codewiki` 執行命令。

## 文件契約

每頁都有穩定 `id`、選用 `parent`、簡短 `summary`、相關頁面 ID 與 Markdown 標題。明確的 `{#slug}` 標題定義穩定章節 ID（`page-id.slug`）。CLI 提供文件樹、摘要、章節大綱、原始 Markdown、程式碼符號與有限範圍的原始碼片段，不需要將整份 Wiki 載入 LLM 上下文。

```c
/* @wiki:impl scheduler.dispatch */
void dispatch(void) { /* implementation */ }
```

此標籤綁定到 `id: scheduler` 頁面的 `### Dispatch {#dispatch}`。符號名稱與原始碼範圍由剖析器取得。移動或重新命名宣告時請保留標籤。無法註記的程式碼使用 frontmatter `refs`。格式請見 `src/codewiki/resources/TAGS.md` 與框架自己的 Wiki。

支援的剖析器：C、Python、YAML、devicetree；陳述式掃描器：shell、Make、Kconfig、CMake 與 `.conf`。剖析處理結構，不建立完整語意呼叫圖，也不推論設計理由。

## 透過圖表探索架構

從 `codewiki/site/architecture.html` 查看框架範例。選擇元件，沿內部圖表前往章節，再展開帶標籤的實作。元件卡片、相依連結與原始碼路徑提供其他閱讀方式。圖表可展開為可用鍵盤操作的畫布，目的地也以一般文字連結提供。

符合文件 ID 的 Mermaid 節點會連到該頁，本地標題 slug 則連到章節。選用 frontmatter 可明確指定跨頁連結：

```yaml
depends_on: [documents]
diagram_links:
  parser: documents.sections
  renderer: renderer
```

此處名為 `parser` 的節點會開啟 `documents` 的 `sections` 標題。嚴格建置驗證目標並推導反向使用關係。`query doc` 向 LLM 工具提供相同關係。作者描述架構相依，程式碼標籤則把原始碼證據附到說明。

## HTML 語言

標準頁面保留英文。新增例如 `renderer-ch_tw.md` 的同層檔案，保持相同 frontmatter `id`、標題層級與穩定錨點。翻譯標題、摘要與正文，並在翻譯標題明確加入 `{#english-slug}`。執行 `codewiki build --strict` 產生具有語言切換器的英文與台灣繁體中文頁面。框架的 Wiki 頁面都提供翻譯。

導覽、圖表與頁面連結維持所選語言。缺少翻譯時顯示英文及備援提示。技能、CLI 查詢與審查紀錄繼續使用英文；翻譯檔案參與建置新鮮度與預覽。請見 [HTML 翻譯](codewiki/wiki/renderer-ch_tw.md#translations)。

## 客製化與升級

在已初始化專案執行 `codewiki update`，即可安裝最新發佈框架並更新複製的支援檔案。從原始碼建置時使用 `codewiki update --source /path/to/codewiki`；使用目前已安裝或可編輯框架時，執行 `codewiki update --installed`。可先用 `codewiki update --installed --dry-run` 預覽檔案變更，再以 `codewiki build --strict` 重新建置。

更新會保留已撰寫頁面、設定、審查與主題覆寫。未修改的支援檔案依 `.codewiki-manifest.json` 自動更新；衝突版本放入 `.codewiki-update/` 供比較。沒有 manifest 的舊實例會保留不同的檔案，直到完成整合。來源選擇、自訂路徑與保留或合併本機指示的方法，請見[更新既有 Wiki](codewiki/wiki/manual-updating-ch_tw.md)。

將選用主題覆寫放在 `wiki/_theme/`。各檔案覆寫隨附主題，新專案不必複製整份主題。使用完整 `_theme/` 的既有 P721 風格實例仍可運作。專案專用文字、路徑、原始碼排除規則、唯讀 glob 與覆寫都屬於專案。

目標測試專案是同層 `../P729/` 儲存庫，位於本框架儲存庫之外。其原有嵌入工具予以保留。可使用新框架操作：

```sh
codewiki build --strict --config ../P729/code_wiki/wiki.config.yaml
codewiki query --config ../P729/code_wiki/wiki.config.yaml doc p721-arch
```

## 文件審查

連結原始碼變更時，審查既有頁面。狀態依內容雜湊，不依提交日期；建置永遠不會自動核准文件。

```sh
codewiki review status --outdated --json
codewiki review pass build --reason "Reviewed refactor; documented behavior unchanged."
codewiki review updated build --reason "Updated the explanation for changed behavior."
codewiki review check
```

Pass 與 updated 範例是替代選項：閱讀頁面與程式碼後，選擇實際結果。每次確認將理由與精確輸入雜湊儲存於 `codewiki/reviews/<id>.json`；請與原專案一起提交。尚未審查的頁面需要明確基準，後續變更需要再次審查。沒有文件的原始碼不會產生新增文件要求。

`codewiki.review.report(Wiki(config_path))` 是共用即時 Python API。`review check` 通過回傳 0，有待審查項目回傳 1，輸入或結構／剖析失敗回傳 2。CI 中在 `build --strict` 後執行。初始化複製 `wiki-review` 技能及選用 shell、pre-push、GitHub Actions 範例，不會安裝 hook 或設定遠端分支保護。請見[審查已過期的文件](codewiki/wiki/manual-review-ch_tw.md)。

## 驗證與歷史

`codewiki build --strict` 拒絕無效文件、重複 ID、失效階層／關係、缺少原始碼參照與無效標籤。查詢回應會回報索引是否符合目前輸入。修改程式碼或文件後請重建；輸入改變代表需要審查，不代表文字必然錯誤。

選用決策紀錄支援理由、錨點 ID、提交 ID 與 PR 網址。建置記錄 Git 修訂版本與內容指紋。自動探索提交／PR、重建歷史與 MCP 伺服器屬於未來工作；請見 Wiki 的來源追溯與決策頁面。

執行 `python -m pytest` 進行剖析器、建置、查詢、初始化與相容性測試。隨附 JavaScript 授權保留於 `src/codewiki/resources/theme/vendor/`。本儲存庫不對抽離出的框架程式碼指定新的授權。
