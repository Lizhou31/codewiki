---
id: authoring
type: component
status: stable
parent: architecture
related: []
refs: []
title: 初始化與預覽
summary: 建立專案內的 Wiki 實例，撰寫以原始碼為依據的頁面，驗證連結，並使用已安裝的框架預覽。
owns:
- ../src/codewiki/init_project.py
- ../src/codewiki/serve.py
depends_on:
- templates
- documents
- build
diagram_links:
  scaffold: authoring.scaffold
  templates: templates
  skills: skills
  preview: authoring.preview
  build: build
decisions: []
---

## 撰寫循環 {#the-authoring-loop}

```mermaid
flowchart TB
  templates["文件範本"] --> scaffold["初始化專案實例"]
  skills["可攜式技能指示"] --> scaffold
  scaffold --> preview["監看 Markdown 與原始碼變更"]
  preview --> build["建置並重新載入本機預覽"]
```

## 重點摘要 {#tl-dr}

- 初始化會建立專案擁有的設定、起始 Markdown、範本與可攜式技能。
- 穩定 ID 與原創說明保留在原始碼儲存庫中。
- 本機伺服器在輸入變更時重新建置，並回報驗證失敗。

## 核心概念 {#concepts}

### 只建立專案應擁有的檔案 {#scaffold}

`codewiki init --root <project> --code-root src` 建立 `codewiki/` 實例。重複使用 `--code-root` 可加入更多原始碼根目錄。初始化會保留既有檔案，升級時不會覆寫使用者的客製化內容。只有在尚無已撰寫頁面時才加入架構起始頁。複製的範本涵蓋架構、子系統、元件與決策文件；請用觀察到的事實取代起始文字。選用的 shell、Git hook 與 CI 範例會複製到 `integrations/`，但不會安裝 hook 或變更遠端儲存庫政策。

### 預覽建置契約 {#preview}

`codewiki serve` 在本機迴路位址提供產生的 HTML，並在監看的輸入變更時重新建置。瀏覽器重新載入通知與驗證錯誤屬於開發伺服器；沒有伺服器時，靜態建置輸出仍可使用。變更輸出目錄後請重新啟動伺服器。CLI 查詢直接使用已儲存的索引，不需要伺服器。

## 技能 {#skills}

框架在 `src/codewiki/resources/skills/` 提供 `wiki-init`、`wiki-query`、`wiki-author`、`wiki-build` 與 `wiki-review`。初始化會將它們複製到實例中。每項技能都使用已安裝的 CLI，因此不依賴 Claude 專用的外掛目錄。請透過所用客戶端的技能探索機制註冊這些檔案。根目錄的代理指示可參照實例指南，定義專案範圍的操作方式。

## 維護 {#maintenance}

修改已有文件涵蓋的檔案前，先查詢其文件。行為改變時，在同一次變更中更新說明。移動或重新命名宣告時保留原始碼標籤；設定為唯讀的程式碼使用文件端參照。執行嚴格建置，接著透過瀏覽器與 CLI 檢查受影響章節。

## 預覽輸入 {#preview-inputs}

預覽會監看實例設定、Markdown、原始碼根目錄、明確擁有或參照的資產、審查紀錄與主題檔案。重新建置前會重新載入設定，因此可識別變更後的原始碼根目錄。設定無效時，預覽會持續顯示錯誤直到修正。
