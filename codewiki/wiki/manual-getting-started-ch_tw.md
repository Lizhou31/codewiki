---
id: manual-getting-started
type: manual
status: stable
parent: user-manual
title: 開始使用
summary: 安裝框架、建置範例 Wiki，並在自己的專案中初始化文件。
related:
- manual-reading
- manual-writing
- manual-configuration
owns: []
depends_on: []
diagram_links: {}
refs: []
decisions: []
---

## 重點摘要 {#tl-dr}

- CodeWiki 需要 Python 3.10 或更新版本。
- 在虛擬環境中安裝框架，再於既有專案中初始化 Wiki。
- 使用 `--strict` 建置，並在本機預覽產生的 HTML。

## 安裝並試用範例 {#install}

在 CodeWiki 框架儲存庫中執行：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
codewiki build --strict
codewiki serve --no-open
```

在瀏覽器開啟 `http://localhost:8000`。於總覽頁選擇**使用手冊**閱讀操作指南，或選擇 **CodeWiki 架構**閱讀實作文件。按 Ctrl+C 停止預覽。

也可直接開啟 `codewiki/site/index.html`。建置後的頁面、語法醒目提示與圖表使用隨附資產，可離線運作。

## 在專案中加入 Wiki {#initialize}

保持安裝框架的環境啟用。將以下範例路徑與專案名稱換成自己的資料；專案必須已存在。

```sh
codewiki init --root /path/to/project --code-root src --name 'My Project'
cd /path/to/project
codewiki build --strict
codewiki serve --no-open
```

`--code-root src` 選擇相對於專案根目錄的目錄。可重複指定，例如 `--code-root src --code-root tests`，也支援個別原始碼檔案。若需要不同的實例目錄，初始化時使用 `--dir docs/codewiki`。

初始化會建立：

| `codewiki/` 內的路徑 | 用途 |
| --- | --- |
| `wiki.config.yaml` | 專案名稱、原始碼根目錄與輸出設定 |
| `wiki/architecture.md` | 應替換成專案說明的起始頁 |
| `wiki/_templates/` | 可重用的頁面範本 |
| `wiki/TAGS.md` | 原始碼標籤語法與範例 |
| `integrations/` | 選用的 shell、pre-push 與 CI 範例 |
| `skills/` 與 `AGENTS.md` | 操作此 Wiki 的代理指示 |

初始化也會在專案根目錄建立 `AGENTS.md`，或在既有檔案末尾加入一小段帶標記的指示。這段指示要求代理在處理原始碼或文件前閱讀 `codewiki/AGENTS.md`，讓 Wiki 查詢與審查流程也適用於 Wiki 資料夾以外的工作。使用 `--dir docs/codewiki` 時，參照會改為 `docs/codewiki/AGENTS.md`。既有根目錄指示會保留；重複初始化不會重複加入或覆寫同一實例的區段。客製化區段時請保留標記。舊實例可重新執行 `init` 加入根目錄參照，且不會覆寫既有實例指南。

可攜式技能仍需透過代理客戶端支援的探索位置註冊；複製到 Wiki 並不代表自動完成註冊。

建置會產生 `site/` 與 `index.json`。請編輯 Markdown 輸入，再重新建置以更新 HTML 與查詢索引。重複執行 `init` 會保留既有實例檔案，不覆寫已撰寫的頁面。

## 進行第一次編輯 {#first-edit}

開啟 `codewiki/wiki/architecture.md`，保留穩定的 `id`，將起始標題、摘要與文字改成專案資訊。執行：

```sh
codewiki build --strict
codewiki query tree
```

樹狀列表會顯示頁面，並可透過 `query doc <id>` 取得章節。接著閱讀[撰寫頁面](manual-writing.html)，加入子頁或獨立的頂層手冊。位置不是預設值時，請明確指定設定檔：

```sh
codewiki build --strict --config docs/codewiki/wiki.config.yaml
codewiki serve --no-open --config docs/codewiki/wiki.config.yaml
```

新頁面一開始尚未審查。替換起始內容並檢查原始碼後，請依[審查流程](manual-review.html) 建立明確的基準紀錄。
