---
id: manual-writing
type: manual
status: stable
parent: user-manual
title: 撰寫頁面
summary: 建立 Markdown 頁面，將手冊與架構分開整理，並把說明連結到原始碼。
related:
- manual-getting-started
- manual-configuration
owns: []
depends_on: []
diagram_links: {}
refs: []
decisions: []
---

## 重點摘要 {#tl-dr}

- 每頁都需要 YAML frontmatter，並具有唯一且穩定的 `id`。
- 頂層頁面使用 `parent: null`，子頁則指定父頁 ID。
- 編輯後執行嚴格建置，並檢查 HTML 頁面與 CLI 章節。

## 建立獨立手冊 {#hierarchy}

在專案中將下列內容儲存為 `codewiki/wiki/user-manual.md`：

```markdown
---
id: user-manual
type: manual
status: stable
parent: null
title: User manual
summary: Learn how to set up and use this project.
---

## TL;DR

- Start with the setup guide.

## First steps {#first-steps}

Open [Getting started](getting-started.html).
```

將連結的子頁建立為 `codewiki/wiki/getting-started.md`：

```markdown
---
id: getting-started
type: manual
status: stable
parent: user-manual
title: Getting started
summary: Set up the project and complete a first task.
---

## TL;DR

- Follow the setup steps below.

## Setup {#setup}

Write the prerequisites, commands, and expected result here.
```

兩頁都會出現在側邊欄。根頁取得總覽卡片，子頁顯示在其下方。`parent` 決定階層，與檔案所在目錄無關。手冊頁使用 `type: manual`；架構元件頁則留在既有架構根頁之下。

## 連結頁面與標題 {#links}

`getting-started` 之類的 ID 會產生 `getting-started.html`。使用 `[Setup](getting-started.html#setup)` 連到其明確標題；同頁內使用 `[Setup](#setup)`。上方標題也具有 CLI 章節 ID `getting-started.setup`。

重新命名標題時，保留頁面 ID 與明確標題 slug。使用 `related` 加入其他頁面連結，而不改變主要階層：

```yaml
related: [getting-started]
```

頁面 ID 必須唯一；`index` 與 `files` 是保留名稱。已撰寫頁面不要放在 `_templates/` 等底線開頭的目錄，因為探索頁面時會排除這些位置。`README.md` 與 `TAGS.md` 是參考檔案，不是 Wiki 頁面。

## 附加原始碼證據 {#evidence}

需要連結實作的說明，可在 ID 為 `scheduler` 的頁面中加入 `### Dispatch {#dispatch}` 這類明確標題。將標籤直接放在原始碼宣告上方：

```python
# @wiki:impl scheduler.dispatch
def dispatch(value):
    return value + 1
```

剖析器辨識宣告；標籤指定文件錨點，而非函式名稱。`impl` 連結實作，`gotcha` 連結已記錄的注意事項，`entry` 標記進入點。使用者操作程序可以獨立存在，不一定需要實作標籤。

無法加入註記的原始碼，改用 frontmatter 參照：

```yaml
refs:
  - file: ../src/scheduler.py
    symbols: [dispatch]
```

路徑相對於設定目錄，而非 Markdown 檔案。各語言範例請查看實例的 `wiki/TAGS.md`。位於 `readonly_globs` 的原始碼必須使用文件端參照。

## 驗證與預覽 {#validate}

```sh
codewiki build --strict
codewiki query doc getting-started
codewiki query section getting-started.setup
codewiki serve --no-open
```

開啟頁面、逐一確認連結，並檢查顯示的命令範例。嚴格驗證會檢查 ID、階層、宣告的關係、標籤及原始碼參照；它無法證明文字正確，也不保證每個一般 Markdown 超連結都有有效目的地。

架構圖的節點 ID 可指向頁面或本地標題。明確的跨頁目標使用 `diagram_links`；解析規則請參閱獨立的 [HTML 渲染器指南](renderer.html#navigation)。

## 更新既有文件 {#refresh}

對框架自己的 Wiki，請在框架儲存庫中執行：

```sh
.venv/bin/codewiki build --strict
.venv/bin/codewiki query tree
.venv/bin/codewiki query file src/codewiki/build.py
.venv/bin/codewiki query section build.orchestration
```

透過檔案涵蓋範圍找出變更原始碼所附的說明，再閱讀目前實作後修訂頁面。保留既有頁面 ID 與明確標題 slug，使原始碼標籤與連入連結持續有效。使用者可見行為改變時，同時更新手冊程序與架構說明。編輯 `codewiki/wiki/` 下的 Markdown；建置器會重新產生 `codewiki/site/` 與 `codewiki/index.json`。

編輯後再次嚴格建置、查詢受影響章節，並開啟產生的頁面檢查連結與原始碼面板。純文件更新需要這些內容及渲染檢查；框架行為變更另需相關的[自動化檢查](testing.html)。

檢查最終說明與原始碼後，以 `codewiki review updated <id> --reason "..."` 記錄結果；文字已正確時使用 `codewiki review pass <id> --reason "..."`。重新建置以顯示新狀態，再執行 `codewiki review check`。[審查已過期的文件](manual-review.html) 說明初次基準、特定版本的確認與 CI 整合。只重新建置不會清除待審查項目。

## 加入 HTML 翻譯 {#translations}

保留原始英文頁面，再複製成例如 `getting-started-ch_tw.md` 的同層檔案。將標題、摘要與文字翻成台灣繁體中文。保留 frontmatter 的相同 `id`，以及每個標題的錨點、層級與順序。英文隱含標題 `## First steps` 應翻為 `## 開始使用 {#first-steps}`。命令、原始碼標籤、路徑與關係 ID 維持原值。

執行 `codewiki build --strict`。HTML 的語言連結可在 English 與繁體中文（台灣）之間切換，包含總覽與原始碼索引。標準頁面連結維持所選語言；缺少翻譯時會明確顯示英文備援內容。CLI 查詢與技能始終讀取原始英文頁面；翻譯 Markdown 只用於 HTML 渲染。命名、驗證與自訂主題規則請見 [HTML 翻譯](renderer.html#translations)。
