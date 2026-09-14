# 一般外科國際會議訂閱日曆

已建立可供 Google Calendar 與 Apple 行事曆訂閱的標準 iCalendar（`.ics`）日曆、訂閱頁面與每日更新程式。**目前是本機版本，尚未部署固定 HTTPS 網址，定期排程尚未啟用。** 下載並匯入 `.ics` 只會得到當時快照；要持續同步，必須使用上線後的網址訂閱。

資料來自使用者提供的 `Schedule of international conference - GS.pptx`，原始檔案未修改。涵蓋 42 個會議系列、59 屆紀錄；實際事件數與核對狀態見 `public/status.json`。

## 可用日曆

| 檔案 | 內容 |
|---|---|
| `public/all.ics` | 全部開會日期與已知投稿截止 |
| `public/subsidized.ics` | 院內補助名單學會的開會與投稿 |
| `public/deadlines.ics` | 僅投稿截止 |
| `public/subsidized-deadlines.ics` | 院內補助學會的投稿截止 |
| `public/reminders.ics` | 全部投稿前 30、14、7、1 天的獨立提醒事件 |
| `public/subsidized-reminders.ics` | 院內補助學會的獨立提醒事件 |

主要日曆選一個即可，避免同時訂閱全部／補助子集合而重複顯示。獨立提醒日曆可額外訂閱。日曆事件也包含 `VALARM`，但是否通知取決於用戶端設定，不保證 Google 會採用來源檔中的提醒。

院內補助註記來自簡報第12頁圖片：SAGES、ACS、EAES、ELSA、IHPBA、A-PHPBA（原圖 APHPBA）、AHPBA、EHS、AHS、APHS。這表示列於提供的名單，並非個人已獲補助核准。原始名單未載適用年度與申請條件。

## 訂閱方式

上線後的網址形如 `https://你的帳號.github.io/conference-calendar/all.ics`。這是格式示例，並非目前已存在的網址。

- Google Calendar 網頁版：「其他日曆」旁＋ →「加入日曆的網址」→ 貼上 `.ics` 網址。初次加入需要電腦瀏覽器；Google 自行決定重新抓取的時間。參考 [Google 官方說明](https://support.google.com/calendar/answer/37100?hl=zh-Hant)。
- Mac 行事曆：「檔案 → 新增行事曆訂閱」，貼上網址。選 iCloud 可同步到同帳號裝置，設定自動重新整理；要保留提醒，取消移除提示的選項。參考 [Apple 訂閱說明](https://support.apple.com/zh-tw/guide/calendar/icl1022/mac) 與 [重新整理說明](https://support.apple.com/zh-tw/guide/calendar/icl1024/mac)。

## 自動更新的實際範圍

1. `monitor.py` 讀取 `data/conferences.json` 中的官方來源，記錄成功、失敗與內容變更。首次人工研究核對與程式抓取成功是不同狀態。
2. `data/rules.json` 包含按會議屆次與欄位限定的解析規則。符合規則且日期／年份一致時，變更須在至少相隔六小時的兩次成功觀測中相同才會自動套用。每日排程下通常隔天套用。
3. 不明確、只寫月份、圖片、JavaScript 才能顯示的公告、尚未公布的新年度、來源衝突或擋爬蟲，會列入 `data/review.json` 與網頁「更新與待確認項目」。**這些項目目前需要人工核對，不能宣稱 42 個學會皆可完全無人維護。** 新年度連結會被發現並列出，但不會自動把未知網頁的日期當作確定會議資訊。
4. 讀取失敗保留最後資料，不會清空日曆。每次檢查的結果在 `data/monitor-state.json`；套用日期變更保留於 `data/change-log.json`。只追蹤到官網變更不等於已驗證日期。
5. 同一事件的 UID 固定，內容變更才提高 `SEQUENCE` 與 `LAST-MODIFIED`，訂閱者重新整理後應更新原事件。取消請在會議或截止資料中加 `"cancelled": true`，保留事件 ID；不要直接刪除既有事件。
6. 開會採所在地曆日的全天事件，結束日依 iCalendar 規格加一天。已公告時區與時間的投稿截止轉為 UTC，顯示時依使用者時區。只公布日期的項目維持全天，不虛構 23:59。

已發現的重要差異：WCTC 摘要截止從簡報預估 2027/1 更新為官方 **2027-02-26**（[官方頁面](https://thyroidworldcongress.com/abstracts/)）；ESA 與 ASC 的截止資訊存在差異，暫不建立確定截止事件。每個事件與清單均保留來源及是否僅據簡報的註記。

## 本機使用

需要 Python 3.10 以上、curl 與系統時區資料；正式程式不需付費 API 或額外 Python 套件。

```bash
cd /home/stevenhsu/conference-calendar
python3 -m unittest -v
python3 calendar_app.py build
python3 server.py
```

開啟 `http://127.0.0.1:8765/`。伺服器僅提供 `public/`，原簡報、圖片與抓取快取不會被提供。

手動更新：

```bash
python3 monitor.py
```

網路失敗或來源需要瀏覽器時，檢查頁面會記錄狀態；請勿把「腳本完成」視為所有官網日期都已核對。

## 部署至 GitHub Pages 與每日更新

已準備 `.github/workflows/calendar.yml`。需先有可使用的 GitHub 帳號／repository；目前尚未連線或建立遠端 repository。

1. 建立名為 `conference-calendar` 的 repository，將本目錄程式與 `data/`、`public/`、`.github/` 放到 `main`。不要上傳原始簡報、圖片、cache、其他病人或院內資料。
2. Repository 的 Settings → Pages → Source 選 GitHub Actions。預設採公開資料庫與公開日曆，只含會議資訊與名單註記；若院內有其他公開限制，應使用合適的託管政策。
3. Actions 中執行 `Update and publish conference calendars`。確認工作流程與 Pages 部署成功後，才使用 GitHub 顯示的正式網址。
4. 工作流程設為每天 UTC 00:17（台灣 08:17）檢查，保存事件狀態，再發布 `public/`。GitHub 排程可能延遲；公開 repository 長期無活動也可能停用排程，需注意 Actions 與網頁最近檢查時間。
5. 在上線頁面複製日曆網址，分別加入 Google 或 Apple。兩者訂閱同一來源，不需各自維護。

參考 [GitHub Pages 工作流程](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) 與 [排程行為](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

## 維護與驗證

- 日常資料：`data/conferences.json`。補助來源：`data/subsidies.json`。
- 新來源／規則：修改 `make_rules.py` 後執行 `python3 make_rules.py`；檢查年份、會議身分和日期類型，避免將註冊或其他學會的日期混入。
- `enrich.py` 是首次整理的歷史腳本，日常更新**不要重跑**，以免覆蓋後續人工核對。
- `test_calendar.py` 驗證時區與夏令時間、全天結束日、UID／版本更新、來源歧義、不同投稿類型、補助篩選及取消事件。
- `check_page.mjs` 是本機獨立 Chrome 的介面檢查輔助腳本，不屬於每日排程。
