---
id: manual-reading
type: manual
status: stable
parent: user-manual
title: 閱讀與查詢
summary: 瀏覽產生的網站、透過命令列取得精準文件，並在確認新鮮度後檢視原始碼證據。
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

- 用總覽與側邊欄選擇指南，再沿本頁目錄深入閱讀。
- CLI 依序提供樹狀總覽、頁面摘要、章節、符號與原始碼。
- 輸入變更後先重新建置，再信任原始碼位置。

## 瀏覽 HTML 網站 {#browse}

開啟 `codewiki/site/index.html`，或啟動 `codewiki serve --no-open` 後開啟 `http://localhost:8000`。頁面、圖表與語法醒目提示使用本地資產，靜態輸出可以離線閱讀。

**總覽**連到頂層指南。**使用手冊**提供日常操作；**CodeWiki 架構**介紹內部元件。**瀏覽文件**側邊欄反映各頁的 `parent` 階層，手冊根頁排在其他根頁前。

使用頁面群組旁的箭頭展開或收合子頁，點選頁名則開啟該頁。鍵盤使用者可將焦點移到箭頭控制項，再按 Enter 或空白鍵。目前頁面與祖先預設展開。**全部展開**與**全部收合**控制整棵樹。

展開選擇只作用於目前開啟的頁面。前往另一頁或重新載入時，會恢復該頁的初始群組狀態。窄螢幕上請先開啟**瀏覽文件**面板。

側邊欄的**尋找頁面**欄位篩選頁面標題，並展開通往符合頁面的群組。清除欄位或按 Escape，可恢復先前展開狀態；篩選期間停用全部群組控制。**本頁目錄**可跳到目前頁面的標題。

標題比對不分大小寫，且需要符合輸入的每個詞。父頁符合時，不會自動顯示未符合的子頁；清除搜尋即可瀏覽完整分支。個別展開箭頭無須 JavaScript，搜尋與全部群組控制則需要。

架構圖可連到頁面或章節。點選連結節點，或使用圖表下方的一般連結。展開圖表可取得更大的視野，按 Escape 關閉。展開**實作**面板以閱讀附加的程式碼；**在編輯器開啟**使用專案設定的編輯器連結。

使用 **+**、**−** 或在圖表上滾動來縮放；以滑鼠或單指拖曳來移動，**符合視窗**可恢復完整圖表。縮放範圍為符合視窗時的 25% 至 800%。展開後也能使用相同控制，開啟或關閉展開視窗會保留位置與縮放比例。使用鍵盤時，先將焦點移到圖表畫布，再用 **+ / −** 縮放、方向鍵移動、**0** 或 **Home** 恢復完整視野。點選節點仍會開啟連結，拖曳則不會。

**原始碼索引**列出具有文件連結的檔案。若要搜尋正文或原始碼符號，而非頁面標題，請使用下方 CLI 搜尋命令。

總覽與個別頁面也顯示文件審查狀態：**unreviewed** 表示沒有基準，**outdated** 表示審查後輸入已有變更，**current** 表示內容與已審查版本一致。標籤反映上一次建置結果。即時狀態與處理方式請見[審查已過期的文件](manual-review.html)。

## 尋找頁面或章節 {#query}

建置框架自己的 Wiki 後，在框架儲存庫執行：

```sh
codewiki query tree
codewiki query doc user-manual
codewiki query doc manual-getting-started
codewiki query section manual-getting-started.install
codewiki query search 'source roots' --limit 5
```

`tree` 顯示階層與摘要；`doc` 提供頁面摘要、關係與章節 ID；`section` 擷取所選 Markdown 及可用原始碼證據。查詢其他專案時，請使用該 Wiki 回傳的 ID。

```sh
codewiki query doc manual-writing --full --limit 40
codewiki query doc manual-writing --full --offset 40 --limit 40
codewiki query --json search 'source roots' --limit 5
```

`--full` 要求原始 Markdown。`--limit` 與 `--offset` 依查詢類型對項目或文字行數分頁，不是 token 預算。JSON 回應在仍有內容時提供 `next_offset`，請依該值繼續閱讀。限制值必須介於 1 與 200。

## 檢視原始碼證據 {#source}

對框架自己的原始碼，可嘗試：

```sh
codewiki query file src/codewiki/build.py
codewiki query symbol codewiki.build.run
codewiki query source codewiki.build.run --limit 40
```

`file` 找出檔案相關文件；`symbol` 顯示宣告中繼資料；`source` 讀取索引記錄的原始碼行。名稱有歧義時，請使用查詢回傳的精確 ID 或檔案限定名稱，不要猜測。

## 保持結果為目前版本 {#freshness}

查詢使用已儲存的 `index.json`，並檢查輸入是否改變。編輯 Markdown、原始碼、設定或主題後執行：

```sh
codewiki build --strict
```

過期索引仍可能回傳舊文件並提示新鮮度警告，但原始碼查詢會拒絕過期位置。重新建置失敗時，請先修正問題再使用行範圍，詳見[疑難排解](manual-configuration.html#troubleshooting)。

## 切換 HTML 語言 {#translations}

有翻譯時，頂端列提供 **English** 與**繁體中文（台灣）**。選擇語言即可開啟相同頁面的對應版本；導覽、頁面連結與圖表保留該語言。缺少翻譯的頁面顯示英文備援提示。切換器可離線且不依賴 JavaScript。無論瀏覽器選擇哪種語言，CLI 命令與技能都繼續回傳英文。
