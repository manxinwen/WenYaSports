# FIT 运动分析与多智能体训练推荐系统

基于 **FastAPI + 多智能体架构** 的 FIT 运动文件解析与训练分析系统，提供 RESTful API 与 React 前端，实现「上传 FIT 文件 → 解析 → 特征提取 → 记忆管理 → 生成个性化训练建议 → 可视化展示」的完整流程。

## 项目简介

- 解析 Garmin/佳明等运动设备导出的 `.fit` 运动记录文件
- 计算心率区间、平均配速、累计爬升、训练负荷（TRIMP）、间歇训练识别等特征
- 规则引擎 + LLM 混合的个性化训练建议生成（LLM 不可用时自动降级为规则建议）
- 短期记忆（TTL 缓存）与长期记忆（SQLite）支撑用户画像与近期训练负荷追踪
- 前端可视化：指标卡片、Leaflet 轨迹地图、Recharts 心率/配速/海拔曲线

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.14、FastAPI、Uvicorn、Pydantic v2、Polars、fitparse |
| 存储 | SQLite（长期记忆）、cachetools.TTLCache（短期记忆） |
| LLM | openai（可选，用于生成自然语言建议） |
| 前端 | React 19、Vite、Ant Design 6、Axios、React Router、Leaflet、Recharts |
| 测试 | pytest、FastAPI TestClient、httpx、unittest.mock |

## 系统架构（多智能体流水线）

```
                    ┌────────────────────────────────────────────────┐
 上传 FIT 文件 ───▶ │ CoordinatorAgent（协调者）                       │
                    │  1. ParserAgent         → ParsedActivity        │
                    │  2. FeatureExtractorAgent → ActivityFeatures    │
                    │  3. MemoryAgent.get_context → 用户画像/近期负荷 │
                    │  4. RecommendationAgent → 训练建议(规则+LLM)    │
                    │  5. MemoryAgent.update   → 持久化+画像更新      │
                    └────────────────────────────────────────────────┘
```

- **ParserAgent**：`fitparse` 读取 FIT，提取 record/session，字段归一化、单位换算（经纬度、海拔、速度等）
- **FeatureExtractorAgent**：心率区间占比、配速、爬升、TRIMP 训练负荷、间歇训练识别、强度类型判定
- **MemoryAgent**：`TTLCache(maxsize=100, ttl=1800)` 短期会话记忆；SQLite 存储用户画像与活动记录
- **RecommendationAgent**：规则引擎计算恢复天数与训练区间；LLM 仅生成自然语言建议，失败自动降级
- **CoordinatorAgent**：编排流水线，异常分级处理（解析失败 400 / 其他 500 / 推荐失败降级返回部分结果）

## 目录结构

```
.
├── app/
│   ├── main.py                  # FastAPI 入口（CORS、路由挂载、DB 初始化）
│   ├── agents/                  # 各 Agent：base/parser/feature/memory/coordinator/recommendation
│   ├── models/                  # Pydantic 模型：activity/features/recommendation
│   ├── services/                # 业务逻辑：fit_parser/feature_engine/recommendation_rules
│   ├── db/                      # SQLite 持久化（users / activities 表）
│   ├── api/routes.py            # REST API 路由
│   └── utils/
├── frontend/                    # React 前端（Vite + antd + Leaflet + Recharts）
│   └── src/
│       ├── pages/               # UploadPage / ActivityDetailPage
│       ├── components/          # ActivityMap / ActivityCharts
│       ├── utils/format.js      # 展示格式化
│       └── api.js               # Axios 实例（/api 代理）
├── tests/                       # pytest 单元测试 + 端到端测试
└── requirements.txt
```

## 安装与运行

### 后端

```bash
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 启动服务（默认 http://127.0.0.1:8000）
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

环境变量（可选）：

| 变量 | 说明 |
| --- | --- |
| `FIT_APP_DB` | SQLite 数据库文件路径，默认 `app.db` |
| `FIT_UPLOAD_DIR` | 上传文件保存目录，默认系统临时目录 |
| `OPENAI_API_KEY` | 提供后启用 LLM 建议生成（未提供时自动使用规则建议） |

### 前端

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 （/api 已代理到后端 8000）
```

生产构建：`npm run build`，产物在 `frontend/dist`。

## API 文档

启动后端后访问 `http://127.0.0.1:8000/docs`（Swagger UI）可交互调试。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查，返回 `{"status": "ok"}` |
| POST | `/api/upload` | 上传 FIT 文件（multipart：`file`、`user_id`、`session_id`），返回活动 ID、metadata、features、recommendation、user_profile_summary |
| GET | `/api/activities?user_id=xxx&limit=10` | 用户最近活动简要列表 |
| GET | `/api/activities/{activity_id}` | 活动完整数据（metadata、features、recommendation 及重新解析的轨迹点 records） |
| GET | `/api/user/profile?user_id=xxx` | 用户画像（含近 7/42 天平均训练负荷） |

统一错误格式：`{"detail": "错误信息"}`，异常状态码：解析失败 400、资源不存在 404、其他 500。

### POST /api/upload 示例

```bash
curl -X POST http://127.0.0.1:8000/api/upload \
  -F "file=@activity.fit" \
  -F "user_id=demo" \
  -F "session_id=s1"
```

## 测试

```bash
pytest tests/ -q          # 运行全部测试
pytest tests/test_api.py -q   # 仅 API 测试
```

测试覆盖：

- `test_health.py`：健康检查
- `test_parser.py`：FIT 解析（含构造的合法 FIT 样例文件）
- `test_features.py`：特征提取（心率区间、训练负荷、间歇训练识别）
- `test_coordinator.py`：协调者编排、异常分级与降级
- `test_memory.py`：SQLite 持久化、短期缓存 TTL
- `test_recommendation.py`：规则引擎与 LLM 降级
- `test_api.py`：REST 路由（上传、列表、详情、画像、错误处理）
- `test_e2e.py`：端到端全链路（上传→列表→详情→画像）

## 演示说明

1. 分别启动后端（`uvicorn app.main:app --port 8000`）与前端（`npm run dev`）
2. 打开 `http://localhost:5173`
3. 在首页拖拽或点击上传 `.fit` 文件，填写用户 ID（或使用默认值），点击「上传并分析」
4. 自动跳转活动详情页，展示：
   - 指标卡片：运动类型、日期、总距离、总时长、平均配速、心率、爬升、训练负荷、恢复天数、心率区间占比
   - 轨迹地图（Leaflet）：起点/终点标注与路线折线
   - 训练建议：恢复天数、目标心率区间与配速区间
   - 训练图表（Recharts）：心率、配速、海拔时序曲线（Tab 切换）
5. 再次上传同一用户的新活动，可在详情/列表中看到历史活动与画像累积

> 注：示例 FIT 文件可由 `tests/fit_gen.py` 生成（`python -c "from tests.fit_gen import generate_fit; generate_fit('/tmp/demo.fit', n_records=300)"`）。
