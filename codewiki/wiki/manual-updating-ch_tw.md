---
id: manual-updating
type: manual
status: stable
parent: user-manual
title: 更新既有 Wiki
summary: 升級框架並更新已初始化專案的支援檔案，同時保留撰寫內容與本機客製化。
related: [manual-getting-started, manual-configuration, updates]
---

## 重點摘要 {#tl-dr}

在已初始化的專案中執行：

```sh
codewiki update
codewiki build --strict
```

`update` 會在執行命令的 Python 環境安裝最新發佈的 `codewiki-framework`，再以該版本更新此專案的支援檔案。需要已包含 update 命令的版本（0.5.0 或更新版本）。舊安裝必須先安裝含此命令的版本，或從原始碼建置。

## 選擇框架來源 {#source}

| 命令 | 更新專案所使用的框架 |
| --- | --- |
| `codewiki update` | 設定之套件索引中的最新發佈版本 |
| `codewiki update --source /path/to/codewiki` | 重新建置並安裝指定的本機框架原始碼 |
| `codewiki update --installed` | 目前執行中的框架，不安裝套件 |

從原始碼建置時使用 `--source`。命令採用指定工作目錄目前的內容，不會擷取 Git 更新、切換分支或選擇版本標籤。需要更新的原始碼時，請先自行更新該工作目錄。可編輯安裝已直接使用工作目錄內容，因此開發時可用 `--installed`。

發佈版與原始碼安裝會使用目前 Python 環境的 pip；若沒有 pip，則使用 uv 並指定完全相同的 Python 執行檔。安裝程式的設定、認證與套件索引設定仍適用。相依套件由安裝程式解析；pip 的強制重新安裝也可能重新安裝相依套件。安裝會將可編輯安裝替換成一般套件，但保留磁碟上的原始碼。若要保留可編輯安裝，請使用獨立環境。找不到發佈版本時，不會自動改用 Git。

更新共用 Python 環境會影響使用該環境的所有專案，但各專案中的支援檔案仍需分別更新。環境升級一次後，其餘專案可使用 `--installed`。

## 選擇專案與預覽 {#selection}

Update 使用與 build、query 相同的設定探索方式。自訂位置範例：

```sh
codewiki update --config docs/codewiki/wiki.config.yaml
codewiki update --installed --dry-run --config docs/codewiki/wiki.config.yaml
```

`--dry-run` 不安裝套件，也不寫入檔案。未搭配 `--installed` 時，只顯示安裝命令與後續計畫，不會假裝已比較尚未取得的發佈版本。搭配 `--installed` 時，會比較目前框架的支援檔案並顯示衝突。

新實例在 `.codewiki-manifest.json` 記錄專案根目錄。舊實例若使用一般的 `codewiki/`、`code_wiki/` 或 `.codewiki/` 目錄，可推定其父目錄。舊的巢狀或自訂位置請搭配 `--config` 指定 `--root /path/to/project`。Wiki 必須位於專案內，設定的 `wiki_dir` 必須位於實例內。受管理路徑若是符號連結，更新器會拒絕處理。

## 更新哪些檔案 {#files}

更新器管理 Wiki 實例內的可重用檔案：

- 套件提供的 `skills/` 與 `integrations/`。
- 設定之 `wiki_dir` 內的 `_templates/` 與 `TAGS.md`。
- 實例的 `AGENTS.md`，以及專案根目錄 `AGENTS.md` 尚未加入的參照區段。

已撰寫的頁面、`wiki.config.yaml`、審查紀錄、原始碼標籤與主題覆寫都會保留。根目錄代理指示保留既有內容與客製化參照區段。新版套件已移除的檔案仍保留於本機。網站與索引只在後續建置時更新。更新不會確認文件審查，也不會安裝選用的 hook 或 CI 範例。

請將 `.codewiki-manifest.json` 納入專案 Git 歷史。它記錄受管理檔案的套件雜湊，以及最後完整完成整合的框架版本。未修改的副本可自動替換；套件內容未改變時，本機客製化會直接保留，不產生衝突。新增或缺少的支援檔案會補入。

## 處理本機修改與舊實例 {#conflicts}

當套件與本機內容都不同於記錄的套件副本，更新會保留本機檔案，將新版放到 `.codewiki-update/` 的相同相對路徑。其他安全的更新仍可完成。結束碼 1 表示仍有衝突；在目前支援檔案全部完成整合前，manifest 的完成版本不會前進。

比較檔案後，可用新版替換本機檔案並執行 `codewiki update --installed`；也可保留或合併客製化，再明確記錄選擇：

```sh
codewiki update --installed --keep-local skills/wiki-query/SKILL.md
```

多個已檢查的檔案可重複指定 `--keep-local`，路徑相對於實例。此操作記錄已考量目前套件內容，但不替換本機文字。之後套件再次變更時，仍會要求比較。後續衝突可能更新比較副本；合併時請編輯真正的本機檔案。已解決的比較副本會保留，檢查後可手動移除。

舊實例沒有原始支援檔案的可信雜湊。相同檔案會建立基準、缺少檔案會補入；不同檔案則列為衝突，不會假設可以覆寫。第一次整合會建立未來自動更新所需的資料。重複執行 `init` 無法取代這個更新流程。

## 驗證結果 {#verification}

```sh
codewiki build --strict
codewiki query tree
codewiki review check
```

自訂位置請使用相同的 `--config`。嚴格建置會驗證新版框架與既有頁面及綁定；review check 仍可能回報原本就待審查的文件。安裝失敗時不會更新實例。若安裝成功但更新失敗，環境已使用新版框架；修正回報問題後，以 `--installed` 重試。套件安裝與多檔案更新不是單一原子交易；每個個別檔案則以原子替換方式寫入。
