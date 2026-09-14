---
id: manual-review
type: manual
status: stable
parent: user-manual
title: 審查已過期的文件
summary: 找出受原始碼變更影響的既有頁面，審查或更新內容並記錄理由，然後在 CI 中執行相同檢查。
related:
- manual-writing
- manual-configuration
- reviews
owns: []
depends_on: []
diagram_links: {}
refs: []
decisions: []
---

## 重點摘要 {#tl-dr}

- 執行 `codewiki review status --outdated` 找出待處理頁面，不必先建置。
- 審查說明與原始碼後，以 `updated` 或 `pass` 記錄結果與理由。
- 將審查紀錄與專案一同提交，並在 CI 執行 `codewiki review check`。

## 找出受影響頁面 {#status}

```sh
codewiki review status --outdated
codewiki review status --outdated --json
```

報告掃描目前的原始碼與 Markdown。沒有紀錄的新頁面或既有頁面為 **unreviewed（尚未審查）**。上次審查後，Markdown、連結的原始碼內容或原始碼關聯改變時，頁面成為 **outdated（審查後已有變更）**。**current** 表示這些輸入與已審查內容一致。此流程只維護既有文件；沒有連結到文件的原始碼變更，不會要求新增頁面。

閱讀頁面、列出的變更原始碼與相關 Git 差異。JSON 包含先前與目前的雜湊及涵蓋範圍。雜湊能識別內容，但不是舊原始碼的副本。有 Git 歷史時請使用歷史；否則以目前原始碼核對說明，並在理由中交代。信任一般 `query source` 回傳的行範圍之前，請先重新建置。

## 更新或確認通過，並附上理由 {#resolve}

說明需要修改時，先編輯並驗證 Markdown，再確認：

```sh
codewiki build --strict
codewiki review updated build --reason "Explained the new content-based review stage."
```

若頁面仍正確，保留原有文字：

```sh
codewiki review pass build --reason "Reviewed the internal refactor; documented behavior is unchanged."
```

將 `build` 換成實際頁面 ID，並提供根據真實變更撰寫的理由。兩種操作都記錄目前原始碼與文件的雜湊。為避免審查後又發生編輯，請將已檢查 JSON 狀態中的精確 `fingerprint` 傳給 `--expected`。若不再符合，先審查新的變更。

Pass 是對這個版本的確認，不是永久忽略。後續變更仍會要求審查，沒有全面忽略開關或自動基準。請逐頁檢查內容與連結原始碼，再建立初次基準。隨附的 `wiki-review` 技能引導 AI 助理遵循相同流程。

刻意刪除頁面時，先修復連入的連結與原始碼標籤，再執行 `codewiki review retire <id> --reason "..."`。保留 Git 中的退役紀錄。

## 將審查與專案一起保存 {#history}

確認紀錄預設位於 `codewiki/reviews/<id>.json`。請與原始碼、Markdown 一起提交；專案現有 Git 歷史會管理三者版本。審查紀錄保存理由、結果、雜湊，以及供參考的提交 ID。產生的索引是獨立輸出，隨時可以重新建置。

確認審查後，重新產生網站：

```sh
codewiki build --strict
codewiki review check
```

總覽與文件頁顯示最近一次建置時的審查狀態；審查命令則始終檢查目前檔案。審查紀錄參與索引新鮮度檢查，也由 `serve` 監看，因此確認操作可更新預覽。

## 加入 CI 與本機提醒 {#ci}

在乾淨的 CI 工作目錄中，兩個命令使用同一份設定：

```sh
codewiki build --strict --config codewiki/wiki.config.yaml
codewiki review check --json --config codewiki/wiki.config.yaml
```

所有頁面均為 current 時，`check` 回傳 0；仍有待處理審查時回傳 1；輸入無效或結構／剖析出錯時回傳 2。`status` 會顯示待處理頁面，但不因此回傳 1，適合用於不阻擋工作的編輯器或代理提醒。兩者都不會默默記錄審查。請設定 CI 服務要求合併前通過此工作；獨立的 PR 核准由儲存庫政策執行。

`codewiki init` 會複製 `integrations/check-docs.sh`、`integrations/pre-push` 與 `integrations/github-actions.yml`。既有專案可用原始根目錄／實例目錄參數重跑 init，以新增缺少的資源而不覆寫檔案。使用 `sh` 執行 shell 範例，或將 pre-push 命令合併進現有 Git hook 並設為可執行。先啟用含 CodeWiki 的 Python 環境。Hook 檢查工作目錄，因此特定修訂版本應由 CI 驗證。

GitHub Actions 範例從框架工作目錄安裝。在使用框架的專案中，請將該步驟換成固定版本的框架 wheel／套件，並選擇正確設定。設成必要檢查前，先建立已審查基準。初始化不會代為安裝 hook、發佈工作流程或變更分支保護。
