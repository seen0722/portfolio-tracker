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

## 執行每日追蹤
`main.py` 會讀取 `portfolio.json`，透過 `PriceFetcher` 從 Yahoo Finance、Stooq 或 `price_overrides.json` 取得報價，並利用 `CurrencyConverter` 進行美元與新台幣換算。最後把結果寫入 `history.csv`，若同日資料已存在則覆蓋並重新計算每日報酬率。

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
