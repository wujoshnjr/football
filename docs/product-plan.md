# Product Plan

## 目標

建立一個世界盃足球預測平台，先做資料分析與模型預測，不碰真實下注。

## MVP 功能

1. 世界盃賽程列表
2. 勝、平、負機率
3. 預期進球與可能比分
4. 模型理由與信心等級
5. 模型版本追蹤

## 發展階段

### Phase 1

完成 FastAPI 後端與 Next.js 首頁，使用 demo fixture 確認資料流與 UI。

### Phase 2

串接 API-Football 或 Football-Data.org，將 fixtures、teams、scores 存入資料庫。

### Phase 3

加入 PostgreSQL、模型績效表、每日同步腳本。

### Phase 4

加入 XGBoost / LightGBM、賠率隱含機率、傷停資料、使用者模擬競猜。

## 原則

- 所有預測都要有 model_version
- 賽前預測不可覆寫，只能新增版本
- 不提供真金流下注
- 每個模型都要能回測
