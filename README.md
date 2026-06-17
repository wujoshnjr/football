# Football World Cup Prediction Platform

這個專案是世界盃足球預測平台 MVP，目標是建立一個可驗證、可追蹤、可解釋的足球預測系統。

> 重要聲明：本專案只做資料分析、模型預測與模擬競猜，不提供真實金流下注、不串接下注服務，也不建議使用者將預測結果視為保證。

## MVP 目標

第一版先聚焦世界盃賽事：

- 取得世界盃賽程、球隊、比分與狀態
- 產生勝 / 平 / 負機率
- 產生預期進球與最可能比分
- 提供模型理由與信心等級
- 紀錄模型版本，方便日後追蹤命中率、Log Loss、Brier Score
- 前端提供簡潔的預測卡片與比賽列表

## 技術架構

```text
frontend/  Next.js + React + Tailwind-style CSS
backend/   FastAPI + Pydantic + httpx
ml/        Elo + Poisson + ensemble baseline
scripts/   資料同步腳本
docs/      產品、API、模型文件
```

## 快速啟動

### 1. 後端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

後端啟動後：

```bash
curl http://localhost:8000/health
curl http://localhost:8000/fixtures
curl http://localhost:8000/predictions/demo-arg-alg-2026
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

前端預設讀取：

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## 環境變數

請複製 `.env.example`，並依部署環境設定。

```bash
cp .env.example .env
```

## 第一版模型

目前先使用可解釋 baseline：

1. Elo 實力差模型
2. Poisson 進球模型
3. 簡單 ensemble 加權

輸出包含：

- home_win / draw / away_win
- expected_home_goals / expected_away_goals
- most_likely_scores
- confidence
- explanation
- model_version

## API 資料來源規劃

第一優先：API-Football / API-Sports

備援來源：Football-Data.org

歷史與事件資料研究：StatsBomb Open Data

完整說明請看：

- `docs/product-plan.md`
- `docs/api-sources.md`
- `docs/model-design.md`

## GitHub 開發流程建議

1. main 保持可部署
2. 每次新增功能開 issue
3. 功能完成後加測試
4. 模型預測必須保留 model_version
5. 賽前預測一旦產生不可覆寫，只能新增新版本

## 下一步

- 串接真實 API-Football fixture endpoint
- 增加 PostgreSQL 資料表
- 加入每日同步腳本
- 建立 Render 部署設定
- 加入模型績效頁
