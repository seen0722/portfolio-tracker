# 投資組合追蹤器

追蹤同時包含美元與新台幣的投資組合，保存每日總價值，並以電子郵件寄送報表。

## 先決條件
- 建議使用 Python 3.9 以上版本
- 支援應用程式密碼的 SMTP 信箱（例如 Gmail）

## 安裝步驟
1. 下載或 clone 此專案。
2. 建立並啟用虛擬環境：
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. 安裝相依套件：
   ```bash
   pip install -r requirements.txt
   ```
4. （可選）讓一鍵腳本可執行：
   ```bash
   chmod +x run_portfolio.sh
   ```

## 執行每日追蹤
`main.py` 會讀取 `portfolio.json`，透過 `PriceFetcher` 從 Yahoo Finance、臺灣證交所 (TWSE) API、Stooq 或 `price_overrides.json` 取得報價，並利用 `CurrencyConverter` 進行美元與新台幣換算。最後把結果寫入 `history.csv`，若同日資料已存在則覆蓋並重新計算每日報酬率。

推薦使用 `run_portfolio.sh`，它會自動建立虛擬環境、安裝依賴並轉呼叫 `main.py`，可把原本給 `main.py` 的參數原封不動傳入：

```bash
./run_portfolio.sh --dry-run --overrides-only
```

若你想自行控制虛擬環境，也可直接呼叫 Python：

```bash
python3.13 main.py \
  --portfolio portfolio.json \
  --overrides price_overrides.json \
  --history history.csv
```

若 `history.csv` 不存在，首次執行會自動建立。若系統有多個 Python 版本，可以直接執行 `./main.py` 使用內建的 shebang。

> 若 Yahoo Finance 無法連線，系統會嘗試改用 Stooq 的報價資料作為備援。
> 若兩者皆失敗，可在專案根目錄建立 `price_overrides.json`（格式如 `{"AAPL": 150.0, "2330.TW": 600.0}`）提供離線價格。
> CLI 會輸出 `[INFO]` 提示，告知目前使用的是線上資料或離線覆寫，並列出每檔持股與現金的換算明細與組合佔比。

常用參數：
- `--overrides-only`：僅使用離線覆寫價，不連線。
- `--dry-run`：只計算，不寫入 `history.csv`。
- `-v / -vv`：增加日誌資訊（INFO / DEBUG）。

終端輸出已整合 [Rich](https://github.com/Textualize/rich) 的表格與彩色面板，讓總覽與持倉明細更易讀；若環境未安裝 Rich，仍會退回純文字格式。

## 啟動網頁儀表板
`dashboard_app.py` 提供 Flask 版儀表板，可直接在本機預覽：

```bash
export FLASK_APP=dashboard_app.py
flask run --reload
```

或使用 `gunicorn dashboard_app:app` 啟動 production 伺服器。可用的環境變數：

| 變數 | 預設值 | 說明 |
| ---- | ------ | ---- |
| `PORTFOLIO_FILE` | `portfolio.json` | 投資組合設定檔路徑 |
| `PRICE_OVERRIDES_FILE` | `price_overrides.json` | 離線報價檔路徑 |
| `HISTORY_FILE` | `history.csv` | 歷史紀錄 CSV |
| `OVERRIDES_ONLY` | `false` | 設為 `true` 時僅使用離線報價 |
| `MAX_HISTORY_POINTS` | `90` | 圖表最多顯示的日數 |

頁面會即時計算最新持倉，並使用 Chart.js 顯示歷史走勢與每日報酬率。

## 部署到 Render
倘若想要公開儀表板，可利用根目錄的 `render.yaml` 建立即時部署：

1. 更新 GitHub repo，確保 `portfolio.json`、`history.csv` 等檔案包含在版本控制或改為引用外部儲存位置。
2. 登入 [Render](https://render.com) 並建立 New + Blueprint，指向該 repo。
3. Render 會讀取 `render.yaml`，自動安裝需求並以 `gunicorn dashboard_app:app` 啟動服務。
4. 可視需求於 Render 介面覆寫環境變數（例如改用只限離線報價的 `OVERRIDES_ONLY=true`）。

> Render 免費方案會在服務閒置時自動休眠，首次喚醒可能需數秒；若要保存 `history.csv` 的最新狀態，可建立 Persistent Disk 或改用雲端資料庫儲存歷史紀錄。

## 寄送每日報表
將 `email_report.py` 檔案最上方的寄件者、收件者與密碼變數改為自己的 SMTP 設定後，執行：

```bash
python3.13 email_report.py
```

郵件內容包含最新總資產、美金與台幣數值、當日報酬率，以及最近五筆歷史紀錄。

## 自訂投資組合
編輯 `portfolio.json` 即可調整持股與現金。股票代碼結尾為 `.TW` 時會視為台股，以新台幣表示價值並轉換成美金；現金則以 ISO 貨幣代碼表示。

## 資料檔案
`history.csv` 位於專案根目錄，每筆資料包含：
- `date`
- `total_usd`
- `total_twd`
- `daily_return_pct`
