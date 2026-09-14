# 驗證紀錄

2026-09-14：11 項 Python 測試通過。

- 已使用獨立 icalendar 函式庫讀取六種 ICS，驗證格式、UID 唯一性與事件起迄。
- Chrome 驗證：59 筆清單、補助篩選、SAGES 搜尋、390px 手機寬度正常，ICS 回傳 HTTP 200 與 text/calendar。
- 時區含夏令時間、跨月多日事件、延期後原 UID 與 SEQUENCE、來源衝突、抓取失敗保留原事件均經測試。
- 官網實測：57 個來源，46 個可讀、11 個失敗；46 條規則中 36 條能從已抓取內容解析，涵蓋 28 屆。可讀不等於日期已核對。
- 已人工核對 WCTC 投稿截止為 2027-02-26；ESA／ASC 截止日期存在衝突，未生成確定截止事件。
- 已完成 GitHub Pages 上線與首次遠端工作流程；公開 all.ics 已透過獨立函式庫驗證 71 個事件與 71 個唯一 UID。每日排程已配置，首次排程觸發尚待下一個排程時間。
- 未測試事項：使用者 Google／Apple 帳號內的實際訂閱同步與通知。

正式上線前需確認固定 HTTPS URL 可由外部匿名讀取 ICS，部署工作流程成功，以及訂閱端收到事件。

正式網站：https://dr-chhsu.github.io/conference-calendar/
首次成功工作流程：https://github.com/dr-chhsu/conference-calendar/actions/runs/34824803801
遠端來源檢查：57 個來源中 44 個可讀、13 個失敗；會依當次來源網站與 GitHub 網路狀態變動。
