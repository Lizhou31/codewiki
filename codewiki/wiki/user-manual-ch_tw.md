---
id: user-manual
type: manual
status: stable
parent: null
title: 使用手冊
summary: 安裝 CodeWiki、建立專案 Wiki、尋找文件，並保持頁面與原始碼參照為目前版本。
owns: []
related: []
depends_on: []
diagram_links: {}
refs: []
decisions: []
---

## 重點摘要 {#tl-dr}

- 從「開始使用」安裝 CodeWiki 並建置第一個 Wiki。
- 透過「閱讀與查詢」瀏覽 HTML 網站，或使用 CLI 取得聚焦的答案。
- 維護 Wiki 時，請閱讀「撰寫頁面」與「設定與疑難排解」。

## 選擇工作 {#choose-a-task}

| 我想要… | 指南 |
| --- | --- |
| 安裝 CodeWiki 或將它加入專案 | [開始使用](manual-getting-started.html) |
| 瀏覽頁面、檢視原始碼或從命令列搜尋 | [閱讀與查詢](manual-reading.html) |
| 建立頁面、整理章節或附加原始碼證據 | [撰寫頁面](manual-writing.html) |
| 審查過期頁面、確認文字無須修改，或在 CI 強制檢查 | [審查已過期的文件](manual-review.html) |
| 選擇實例、調整設定或修正建置錯誤 | [設定與疑難排解](manual-configuration.html) |

這些指南說明日常用法。框架內部元件請閱讀獨立的 [CodeWiki 架構](architecture.html) 區段。

## 日常流程 {#workflow}

1. 編輯實例 `wiki/` 目錄中的 Markdown。
2. 在專案目錄執行 `codewiki build --strict`。
3. 開啟產生的網站，或執行 `codewiki serve --no-open` 取得即時預覽。
4. 使用 `codewiki query tree` 尋找頁面，再只查詢需要的章節。
5. 使用 `codewiki review status` 審查受影響頁面，記錄結果與理由，再執行 `codewiki review check`。確認後重新建置以更新網站。

範例使用預設實例資料夾 `codewiki/`。若實例位於其他位置，請在 build、serve 與 query 傳入 `--config path/to/wiki.config.yaml`。
