# 投資組合追蹤器

追蹤同時包含美元與新台幣的投資組合，保存每日總價值，計算未實現損益 (P/L) 與報酬率 (ROI)，並以電子郵件寄送報表。

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
`main.py` 會讀取 `portfolio.json`，透過 `PriceFetcher` 從 Yahoo Finance、臺灣證交所 (TWSE) API、Stooq 或 `price_overrides.json` 取得報價，並利用 `CurrencyConverter` 進行美元與新台幣換算。最後計算總市值、成本與損益，將結果寫入 `history.csv`。

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

頁面會即時計算最新持倉，並顯示：
- **資產歷史走勢圖**
- **資產配置圓餅圖** (Asset Allocation)
- **詳細損益表** (包含成本、未實現損益、報酬率)

介面採用現代化 Dark Mode 設計，並支援手機版面 (RWD)。

## 部署到 Render
倘若想要公開儀表板，可利用根目錄的 `render.yaml` 建立即時部署：

1. 更新 GitHub repo，確保 `portfolio.json`、`history.csv` 等檔案包含在版本控制或改為引用外部儲存位置。
2. 登入 [Render](https://render.com) 並建立 New + Blueprint，指向該 repo。
3. Render 會讀取 `render.yaml`，自動安裝需求並以 `gunicorn dashboard_app:app` 啟動服務。
4. 可視需求於 Render 介面覆寫環境變數（例如改用只限離線報價的 `OVERRIDES_ONLY=true`）。

> Render 免費方案會在服務閒置時自動休眠，首次喚醒可能需數秒；若要保存 `history.csv` 的最新狀態，可建立 Persistent Disk 或改用雲端資料庫儲存歷史紀錄。

## 部署到 Vultr (Ubuntu VPS)
若您擁有 Vultr 或其他 Ubuntu VPS，可使用專案內建的 `deploy.sh` 快速部署：

1. **準備 VPS**：建立一個 Ubuntu 20.04 或 22.04 的實例。
2. **上傳腳本**：將 `deploy.sh` 上傳到伺服器，或直接在伺服器上建立該檔案。
   ```bash
   scp deploy.sh root@<your_server_ip>:~/
   ```
3. **執行部署**：
   SSH 進入伺服器後執行：
   ```bash
   # 賦予執行權限
   chmod +x deploy.sh
   
   # 執行腳本 (需 sudo 權限)
   # 用法: sudo ./deploy.sh <GitHub_Repo_URL> <Server_IP_or_Domain>
   sudo ./deploy.sh https://github.com/seen0722/portfolio-tracker.git zmlab.io
   ```
   
腳本會自動完成以下工作：
- 更新系統與安裝相依套件 (Python, Nginx, Git 等)
- Clone 專案並建立虛擬環境
- 設定 Systemd 服務以背景執行應用程式
- 設定 Nginx 反向代理與防火牆

部署完成後，即可透過瀏覽器訪問 `http://<Server_IP>`。

## 寄送每日報表
將 `email_report.py` 檔案最上方的寄件者、收件者與密碼變數改為自己的 SMTP 設定後，執行：

```bash
python3.13 email_report.py
```

郵件內容包含最新總資產、美金與台幣數值、當日報酬率，以及最近五筆歷史紀錄。

## 自訂投資組合
編輯 `portfolio.json` 即可調整持股與現金。股票代碼結尾為 `.TW` 時會視為台股。

為了計算損益，請在每個持股中加入 `average_cost` (平均成本)：

```json
{
  "stocks": [
    {
      "symbol": "GOOG",
      "shares": 95.04,
      "average_cost": 105.50
    },
    {
      "symbol": "2330.TW",
      "shares": 1000,
      "average_cost": 500.0
    }
  ],
  "cash": [ ... ]
}
```

## 資料檔案
`history.csv` 位於專案根目錄，每筆資料包含：
- `date`
- `total_usd`
- `total_twd`
- `daily_return_pct`
