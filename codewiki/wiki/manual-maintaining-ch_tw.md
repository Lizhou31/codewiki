---
id: manual-maintaining
type: manual
status: stable
parent: user-manual
title: 文件維護規則
summary: 在程式碼變更後保持說明正確，並透過連結提交的決策紀錄保存重要的設計理由。
related: [manual-writing, manual-review, history]
---

## 重點摘要 {#tl-dr}

- 重構或修改程式碼後，檢查受影響的 Wiki 頁面，更新已不符合程式碼的說明。
- 若設計選擇值得保留，也要記錄變更理由，並附上相關 commit 或 PR。
- 簡短理由可用決策條目；重大變更則建立獨立的決策頁面。
- 建置並檢查結果。決策紀錄與建置成功都不代表文件已完成審查確認。

## 判斷需要維護的內容 {#rules}

頁面正文說明**程式碼目前如何運作**。決策紀錄說明**設計為何改變**。
審查確認則記錄**已檢查哪個版本的說明與連結原始碼**。

| 情況 | 處理方式 |
| --- | --- |
| 變更使說明、圖表、範例或原始碼參照不再正確 | 更新受影響的頁面，使其符合目前實作。 |
| 選擇有值得保留的理由、取捨、未採用方案或相容性影響 | 另外新增決策條目或獨立的決策頁面。 |
| 內部重構後，原有說明仍然正確 | 檢查內容而無須重寫正確文字；若理由有價值，仍可記錄決策。 |
| 例行修改沒有長期值得保留的設計理由 | 視需要更新文件；不強制新增決策紀錄。 |

記錄能幫助未來讀者理解或重新評估設計的選擇。檔案差異只能顯示修改了什麼，
無法證明修改原因。使用已提供的理由與已確認的證據；未知理由應列為待釐清問題。

## 尋找並更新受影響的頁面 {#affected-pages}

檢查 commit 或差異，再尋找既有說明：

```sh
codewiki review status --outdated
codewiki query tree
codewiki query file src/example.py
codewiki query doc example-component
```

將範例檔案與文件 ID 換成專案的實際值。若查詢回報索引過期，先執行
`codewiki build --strict` 重新建置，再使用原始碼行號範圍。
同時檢查目前程式碼與差異，更新受影響的架構、行為、圖表、範例與使用流程。
移動或重新命名宣告時，保留穩定的頁面 ID、明確的標題錨點與原始碼標籤。

主要說明應聚焦於目前實作。歷史性的前後比較放在決策條目或決策頁面中。
未連結至文件的原始碼變更，不會自動產生新增 Wiki 頁面的要求。

## 附加簡短決策 {#decision-entry}

在受影響頁面既有的 YAML frontmatter `decisions` 清單中新增條目，保留先前紀錄。例如：

```yaml
decisions:
  - id: extract-validation
    reason: >
      Centralized validation so the CLI and build pipeline apply
      the same rules.
    anchors: [example-component.validation]
    commits: ["<full-commit-sha>"]
```

將範例理由、錨點與 commit 換成實際值。`id` 是頁面內穩定的識別碼，
`reason` 為必填。選填的 `anchors` 必須指向既有的明確章節錨點；不需要時可省略。
commit ID 必須加上引號。選填的 `prs` 清單接受 HTTP(S) PR 網址。
若頁面已有 `decisions`，不要再新增第二個同名 YAML 欄位。

## 建立重大決策頁面 {#decision-page}

變更跨越多個元件，或需要詳細說明替代方案與影響時，可使用實例中的
`wiki/_templates/decision.md` 範本（若有提供）。將新頁面存入設定的
`wiki_dir`，不要放在 `_templates/` 中。例如：

```markdown
---
id: refactor-validation
type: decision
status: draft
parent: architecture
title: Centralize validation
summary: Explain the shared validation design and its tradeoffs.
related: [example-component]
decisions:
  - id: centralize-validation
    reason: Share validation rules across CLI and build entry points.
    commits: ["<full-commit-sha>"]
---

## TL;DR {#tl-dr}

Summarize the change and its purpose.

## Context {#context}

Describe the original problem and constraints.

## Changes {#changes}

Explain the before-and-after structure and any compatibility impact.

## Alternatives {#alternatives}

Record known alternatives and the reasons for the chosen approach.

## Consequences {#consequences}

Describe benefits, tradeoffs, and conditions for revisiting the choice.

## Verification {#verification}

Record the checks performed and their results.
```

`parent` 與 `related` 應使用實際存在的頁面 ID。父頁面決定側邊欄中的位置，
相關頁面則顯示為標題附近的連結。也要從受影響的元件頁面連結至決策頁面，
讓讀者能從目前說明找到設計理由。元件頁面仍須配合新實作修正不再正確的內容。

## 閱讀決策歷史 {#presentation}

建置後，條目會出現在頁面主要內容下方的「決策與變更參照」。每個條目預設收合，
展開後可看到理由、錨點、commit 與 PR 參照。條目依撰寫清單的順序顯示。
commit 雜湊與錨點 ID 以程式碼文字呈現；PR 網址可以點擊。

獨立決策頁面使用一般頁面版型，並有自己的章節目錄。CLI 會回傳指定頁面的決策紀錄：

```sh
codewiki query history example-component
codewiki query history refactor-validation
```

請查詢實際存放紀錄的頁面；`related` 不會彙整其他頁面的歷史。
CodeWiki 不會自動探索 Git／PR 的設計理由、驗證參照的 commit 或 PR 內容，
也不會重建頁面的舊版本。與建置快照的差異請參閱[來源追溯與決策](history.html)。

## 驗證並保存變更 {#verification}

1. 執行 `codewiki build --strict`。
2. 檢查受影響的 HTML 頁面、決策條目與導覽連結。
3. 使用 `codewiki query section <page-id.section>` 與 `codewiki query history <page-id>` 檢查 CLI 呈現。
4. 檢查最終說明與連結原始碼，再依照[審查已過期的文件](manual-review.html)，使用具體理由與已檢查的指紋記錄 `updated` 或 `pass`。若審查保留給其他審查者，則維持待審查狀態。
5. 審查確認後重新建置，並執行 `codewiki review check`。待審查狀態與建置驗證分開處理。
6. 將撰寫的 Markdown 與已完成的審查紀錄一起提交至專案版本歷史。

若重構已有 commit，請在後續文件提交中引用該 SHA。若程式碼與文件仍在一起準備，
先記錄理由，並使用已有的 PR 網址，或稍後補上程式碼 commit 參照；
commit 無法在自身內容中包含自己的最終 SHA。後續選擇取代既有決策時，
保留先前紀錄，並在新條目或頁面中說明替代關係。
