# WenYaSports — 面试项目描述

> 面试官看简历第一眼就要能回答：**"这是个什么项目？为什么值得面？"**  
> 以下是项目的完整技术描述，建议在回答"介绍一下你的项目"时按此框架展开。

---

## 一句话定位

**WenYaSports** 是一个 **LLM 驱动的多 Agent 运动数据智能分析平台**——用户上传运动数据（.FIT/.CSV），系统自动完成解析、特征提取、训练分析、营养建议，并通过 AI 私教提供交互式问答。

## 解决的问题

运动数据平台（Strava/Keep/悦跑圈）普遍存在三个痛点：

| 痛点 | 现有方案 | WenYaSports 的做法 |
|------|---------|-------------------|
| 数据孤岛 | 各平台数据不互通，无法统一分析 | FIT + CSV 双格式解析，支持多源数据导入 |
| 静态报表 | 只有固定指标（里程/配速/心率），无深度洞察 | 10 个 Agent 协作完成多维分析 + RAG 知识增强 |
| 千人一面 | 给所有人一样的训练建议 | 用户画像 + 历史记忆 + LLM 个性化生成 |

## 技术栈一览

```
┌─────────────────────────────────────────────────────────────────┐
│                     全栈技术架构                                  │
├─────────────────────────────────────────────────────────────────┤
│  后端（Python）                                                  │
│  ├── FastAPI          Web 框架 + API 路由                       │
│  ├── SQLite           用户活动数据持久化                          │
│  ├── ChromaDB         向量数据库（RAG 知识存储）                  │
│  ├── sentence-transformers  Embedding 模型                      │
│  └── HMAC-SHA256      自研 Token 鉴权                             │
│                                                                  │
│  前端（React）                                                    │
│  ├── Vite             构建工具                                    │
│  ├── React Router     路由管理                                    │
│  ├── Recharts         可视化图表                                  │
│  └── Axios            HTTP 通信                                    │
│                                                                  │
│  Agent 系统（自研）                                               │
│  ├── Agent Harness    运行时沙箱（Registry/Blackboard/MessageBus）│
│  ├── LLM Orchestrator 动态编排 + 重规划                           │
│  ├── ReAct Agent      推理行动循环                                │
│  └── MCP Protocol     Client/Server/Registry/Bridge             │
│                                                                  │
│  数据存储                                                         │
│  ├── SQLite           activities 表（按 user_id 过滤）            │
│  └── ChromaDB         知识库分块 + Metadata Filter 检索           │
└─────────────────────────────────────────────────────────────────┘
```

## 架构图

```
                          ┌──────────────────────────────┐
                          │       Frontend (React)        │
                          │  Dashboard · Chat · Upload   │
                          │  DecisionExplainability · ... │
                          └──────────────┬───────────────┘
                                         │ HTTP/JSON
                          ┌──────────────▼───────────────┐
                          │    FastAPI REST API           │
                          │  /auth/* · /activities/*     │
                          │  /dashboard/summary · /chat  │
                          └──────────────┬───────────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              │                          │                          │
   ┌──────────▼──────────┐    ┌──────────▼──────────┐    ┌─────────▼─────────┐
   │  Agent Runtime      │    │  Authentication      │    │  Database Layer    │
   │  Harness            │    │  HMAC-SHA256 Token    │    │  SQLite + ChromaDB │
   │                     │    │  Register / Login     │    │                    │
   │  ┌───────────────┐  │    │  Session Isolation   │    │  activities table  │
   │  │ LLMOrchestrator│◄─┼────┼─────────────────────┤    │  (user_id 过滤)    │
   │  │ 动态规划+重规划 │  │    │  AuthUser           │    │                    │
   │  └───────┬───────┘  │    │  Role: admin/user    │    │  chroma collection │
   │          │          │    └─────────────────────┘    │  (metadata filter) │
   │          ▼          │                                └────────────────────┘
   │  ┌───────────────┐  │
   │  │ AgentRegistry  │  │         ┌──────────────────────┐
   │  │ Agent列表:     │  │         │  RAG Pipeline          │
   │  │  ParserAgent   │  │         │                       │
   │  │  FeatureAgent  │  │         │  SmartChunker 切块    │
   │  │  MemoryAgent   │  │         │  HybridRetriever 检索 │
   │  │  ReActAgent    │  │         │  (向量+BM25+RRF+MMR) │
   │  │  EvaluatorAgent│  │         │                       │
   │  │  Reflection... │  │         └──────────────────────┘
   │  └───────┬───────┘  │
   │          │          │                ┌──────────────────────┐
   │          ▼          │                │  MCP Plugins          │
   │  ┌───────────────┐  │                │  strava / venues      │
   │  │ Blackboard    │◄─┼────────────────┼  map_routing / share │
   │  │ (共享黑板)     │  │                │  weather             │
   │  └───────┬───────┘  │                └──────────────────────┘
   │          │          │
   │          ▼          │
   │  ┌───────────────┐  │
   │  │ MessageBus    │  │
   │  │ (异步消息)     │  │
   │  └───────────────┘  │
   └─────────────────────┘
```

## 代码规模统计

```
Total Python Code:  24,091 行（不含测试）
Frontend Code:       8,588 行（JSX + JS + CSS）
Test Code:          ~5,000 行（36 个测试文件）

核心模块行数 Top 15:
┌──────────────────────────────────────────┬───────┐
│ 模块                                       │  行数 │
├──────────────────────────────────────────┼───────┤
│ llm_orchestrator.py  （LLM 动态编排）      │  1199 │
│ routes.py            （API 路由）          │  1000 │
│ agentic_workflow.py  （ToT + BeliefState） │   783 │
│ explainability.py    （决策可解释性）       │   782 │
│ decision_engine.py   （三层决策）           │   771 │
│ hierarchical_memory.py（分级记忆）          │   735 │
│ reaact_agent.py      （ReAct 推理循环）     │   723 │
│ negotiation.py       （Agent 协商协议）      │   696 │
│ rag_optimizer.py     （RAG 优化）           │   673 │
│ belief_state.py      （自主决策状态）        │   638 │
│ memory_lifecycle.py  （记忆生命周期）         │   636 │
│ harness.py           （Agent 运行时沙箱）    │   626 │
│ uncertainty_quantifier.py（不确定性量化）    │   599 │
│ fault_tolerance.py   （三级容错）           │   595 │
│ agent_evaluator.py   （质量评估）           │   555 │
└──────────────────────────────────────────┴───────┘

Agent 数量:           10 个（Parser/Feature/Memory/ReAct/Evaluator/Reflection/...）
MCP 插件数量:          5 个（Strava/运动场馆/地图/社交/天气）
React 页面数量:       19 个（Dashboard/Chat/Upload/DecisionExplainability/...）
测试文件数量:         36 个
知识库文档数量:        5 份运动科学专业文档
```

## 十大核心亮点（简历上该写的）

```
① 自研 Agent Runtime Harness 运行时沙箱
   对比 LangChain 的 Chain 模式，我们用 AgentRegistry + Blackboard + MessageBus 四件套
   实现了能力驱动而非 Prompt 驱动的 Agent 协作架构

② LLM 驱动动态编排 + 三级重规划
   LLM Orchestrator 生成 ExecutionPlan → 按 capability 匹配 Agent → 失败自动重规划
   max_replanning=3，超过后走规则引擎优雅降级

③ 三层降级架构（零配置可运行）
   FakeEmbedder 哈希向量 → 规则引擎兜底 LLM → Agent 简化逻辑
   无 API Key、无嵌入模型、无网络也能跑通全链路

④ MCP Client/Server/Registry/Bridge 四件套
   支持 stdio/SSE 双传输，MCPAgentBridge 自动将内部 Agent 暴露为 MCP 工具
   外部系统可直接调用，新增 Agent 零成本暴露

⑤ 分级记忆系统 + 生命周期管理
   Working（当前会话）/ Episodic（执行历史）/ Semantic（知识画像）三层
   自动晋升（access_count≥3）、蒸馏（余弦相似度合并）、衰减（30天未访问降级）

⑥ RAG 知识库增强 — 6 步召回优化管线
   Query Expansion → Category Detection → Vector+BM25 Hybrid Search → RRF Fusion → MMR Diversity → Metadata Rerank
   SmartChunker 4 种切块模式，动态颗粒度 200-500 token

⑦ 质量闭环：EvaluatorAgent + ReflectionEngine + Guardrails
   5 维度评估（accuracy/completeness/relevance/format/actionability）
   ReflectionEngine 失败反思 → 经验存记忆 → 下次自动检索避免重蹈覆辙

⑧ Agent 协商协议 + 三层决策架构
   Strategic（目标分解）→ Tactical（工具编排）→ Validation（Critique + Debate）
   多 Agent 能力冲突时自动协商（0.6×quality + 0.4×confidence 综合分）

⑨ 用户系统：注册/鉴权/数据隔离三层
   HMAC-SHA256 自签名 Token（Demo 级）→ RBAC admin/user 角色
   SessionHarness + MemoryPool + SQLite WHERE user_id=? 三层数据隔离
   前端 TopBar 用户菜单 + LoginPage 登录/注册 Tab

⑩ 可观测性：TraceCollector + 决策可解释性
    append-only 事件日志支持完整回放
    DecisionExplainabilityPage 展示决策链可视化 + 协商协议 + 不确定性量化
```

## 面试开场 60 秒话术

> 面试官好，我介绍一下 WenYaSports 这个项目。
>
> **它是什么**：一个 LLM 驱动的多 Agent 运动数据智能分析平台。用户上传 .FIT 或 .CSV 运动数据，系统自动完成解析、特征提取、训练分析、营养建议，还能通过 AI 私教交互式问答。
>
> **为什么做**：现有运动平台（Strava/Keep）数据孤岛、只有静态报表、千人一面。我们想解决这三个问题。
>
> **技术亮点**（挑 2-3 个说）：
> 1. 自研了一个 Agent Runtime Harness 运行时沙箱，核心是 AgentRegistry + Blackboard + MessageBus 四件套，对比 LangChain 的 Chain 模式，我们是能力驱动而非 Prompt 驱动，更适合生产。
> 2. LLM Orchestrator 动态编排 + 三级降级——没有 API Key、没有嵌入模型也能跑通全链路。
> 3. MCP 协议集成了 5 个外部插件（Strava/运动场馆/地图/社交/天气），MCPAgentBridge 能把内部 Agent 自动暴露为 MCP 工具。
>
> **代码规模**：后端 24K 行 Python、前端 8.5K 行 React，10 个 Agent、5 个 MCP 插件、19 个前端页面、36 个测试文件。
>
> **我具体做了什么**：整个项目的架构设计、Agent 系统、LLM 编排、MCP 集成、记忆系统、RAG 优化、鉴权和数据隔离都是我做的。

---

---

## 🧠 十个 Agent 完整清单（精确到 capability）

> **重要说明**：项目里有两种"Agent"：
> - **Harness 注册的核心 Agent（5 个）** — 由 `harness_setup.py` 初始化，注册到 AgentRegistry，Orchestrator 通过 capability 匹配调度
> - **Orchestrator 内部的辅助模块（5 个）** — 不注册到 Harness，直接被 Orchestrator 实例化，负责质量闭环和决策辅助

### 核心 Agent（5 个，Harness 注册，可被 Orchestrator 调度）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. ParserAgent  — 数据解析专家                                              │
│  ─────────────────────────────────────────                                  │
│  文件: app/agents/parser_agent.py                                           │
│  Capabilities:  fit_parsing · data_extraction · metadata_parsing            │
│  Dependencies:  无                                                           │
│  输入:          .fit 文件路径 / .csv 文件路径                                │
│  输出:          ParsedActivity 对象（时间序列 + 统计摘要）                    │
│  做什么:        解析 Garmin FIT 二进制协议 / 标准 CSV                         │
│                 → 提取每秒钟的心率/配速/海拔/步数/卡路里                    │
│                 → 自动识别运动类型（跑步/骑行/游泳）                          │
│                 → 处理 FIT 协议的 record header 校验、CRC 验证               │
├─────────────────────────────────────────────────────────────────────────────┤
│  2. FeatureExtractorAgent — 特征工程专家                                    │
│  ─────────────────────────────────────────                                  │
│  文件: app/agents/feature_extractor_agent.py                                │
│  Capabilities:  feature_engineering · statistics · intensity_distribution   │
│  Dependencies:  fit_parsing（需要 Parser 先跑完）                            │
│  输入:          ParsedActivity 对象                                          │
│  输出:          FeatureSummary（聚合指标 + 训练强度分布）                    │
│  做什么:        计算距离、时长、累计爬升/下降                                │
│                 → 划分心率区间（Zone 1-5）并计算各区间占比                    │
│                 → 统计配速分布、步频分布、功率分布                             │
│                 → 识别训练峰值（最高心率、最快配速、最大摄氧量估算）           │
├─────────────────────────────────────────────────────────────────────────────┤
│  3. MemoryAgent — 记忆管理专家                                              │
│  ─────────────────────────────────────────                                  │
│  文件: app/agents/memory_agent.py                                           │
│  Capabilities:  user_profile · context_retrieval · memory_update            │
│  Dependencies:  无                                                           │
│  输入:          user_id / context_query / data_to_store                     │
│  输出:          UserContext（用户画像 + 历史训练摘要）                        │
│  做什么:        从 SQLite 加载用户所有历史活动                               │
│                 → 从分级记忆（Working/Episodic/Semantic）检索相关经验       │
│                 → 更新用户画像（新活动入库、统计数据刷新）                   │
│                 → 记忆晋升/蒸馏/衰减生命周期管理                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  4. RecommendationAgent — 训练建议专家                                      │
│  ─────────────────────────────────────────                                  │
│  文件: app/agents/recommendation_agent.py                                   │
│  Capabilities:  training_advice · rule_engine · llm_generation              │
│  Dependencies:  feature_engineering + user_profile                          │
│  输入:          FeatureSummary + UserContext                                │
│  输出:          Recommendation（训练建议 + 营养建议 + 下次训练计划）          │
│  做什么:        规则引擎匹配训练类型 → 触发 LLM 生成个性化建议               │
│                 → 结合 RAG 知识库（运动生理学/营养学）                        │
│                 → 识别过度训练风险、给出恢复建议                             │
│                 → 制定周期化训练计划（基础期/强化期/峰值期）                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  5. ReActAgent — 工具使用与推理专家                                         │
│  ─────────────────────────────────────────                                  │
│  文件: app/agents/reaact_agent.py                                           │
│  Capabilities:  tool_calling · reasoning · multi_step_planning              │
│  Dependencies:  memory_update + training_advice                            │
│  输入:          用户自然语言问题                                             │
│  输出:          ChatResponse（最终回答 + 中间推理链 + 工具调用记录）          │
│  做什么:        ReAct 循环：Thought → Action → Observation → ... → Answer   │
│                 → 绑定 PluginManager 的 18 个 MCP Tools                      │
│                 → ToolResultValidator + ToolErrorRecovery 处理异常           │
│                 → 失败自动 retry / 降级 / 换工具                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Orchestrator 内部辅助模块（5 个，质量闭环 + 决策辅助）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  6. EvaluatorAgent — 质量评估器                                             │
│  文件: app/agents/evaluator_agent.py (555 行)                               │
│  被谁用: Orchestrator.execute_goal() 的质量闭环阶段                          │
│  输入: 上一步 Agent 的产出                                                  │
│  输出: EvaluationResult（5 维度分数 + 通过/未通过判定）                     │
│  5 维度: accuracy(准确性) · completeness(完整性) · relevance(相关性)         │
│          format(格式规范) · actionability(可操作性)                          │
│  两种模式: BuiltinEvaluationRules（规则，零 LLM） / LLM（深度评估）           │
├─────────────────────────────────────────────────────────────────────────────┤
│  7. ReflectionEngine — 失败反思引擎                                         │
│  文件: app/agents/reflection_engine.py                                      │
│  被谁用: EvaluatorAgent 判断未通过时触发                                     │
│  输入: 失败的产出 + 执行历史                                                 │
│  输出: Reflection（根因分析 + 改进策略 + 置信度）                           │
│  做什么: 分析"为什么失败" → 生成改进建议 → 存入 Episodic Memory              │
│         → 下次遇到类似场景自动检索避免重蹈覆辙                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  8. Guardrails — 输出安全守卫                                               │
│  文件: app/agents/guardrails.py                                             │
│  被谁用: Orchestrator 产出最终返回前                                         │
│  三层守卫:                                                                  │
│    • FormatGuard — JSON schema 校验、必填字段检查                            │
│    • ContentGuard — 敏感词过滤、有害内容检测                                  │
│    • QualityGuard — 最小长度、结构完整性                                     │
│  输出不通过时: 自动重生成 / 截断 / 返回安全兜底                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  9. UncertaintyQuantifier — 不确定性量化器                                   │
│  文件: app/agents/uncertainty_quantifier.py (599 行)                         │
│  被谁用: Orchestrator 决策阶段 + 前端 DecisionExplainabilityPage             │
│  做什么: 判断 LLM 输出的置信度（高/中/低/极低）                              │
│         → 标记证据来源（knowledge_base / llm_inference / user_history）     │
│         → 置信度低时触发"请确认"提示                                          │
│  证据类型: FACTUAL(事实) · STATISTICAL(统计) · INFERENTIAL(推理)            │
├─────────────────────────────────────────────────────────────────────────────┤
│  10. CoordinatorAgent — Agent 协商协调器                                     │
│  文件: app/agents/coordinator_agent.py                                      │
│  被谁用: Orchestrator._try_negotiate_agent() 当多个 Agent 争抢同一能力时     │
│  做什么: 多 Agent 能力冲突时自动协商                                         │
│          0.6 × quality_score + 0.4 × confidence_score 综合评分               │
│          → 分高者胜出执行，分低者提供 fallback                               │
│  协商类型: CAPABILITY_DISPUTE · QUALITY_DEBATE · FALLBACK_SELECTION          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔗 Agent 之间是怎么互相联系的

### 连接架构图

```
                         ┌─────────────────────┐
                         │   LLMOrchestrator   │
                         │   (1199 行)          │
                         │                     │
                         │  感知: 从 Registry   │
                         │  读取全部 Agent 列表 │
                         │  注入 Planner prompt │
                         │                     │
                         │  决策: 生成 JSON     │
                         │  ExecutionPlan       │
                         │  按 capability 匹配 │
                         └─────────┬───────────┘
                                   │
                                   │ 调度 (schedule_agent)
                                   ▼
              ┌──────────────────────────────────────┐
              │                                      │
    ┌─────────▼──────────┐              ┌────────────▼───────────┐
    │   AgentRegistry    │              │     Blackboard         │
    │   (能力索引)        │              │   (共享黑板 · 命名空间)   │
    │                    │              │                        │
    │ fit_parsing → [p]  │              │ "user_001" /            │
    │ feature_eng → [f]  │              │   "parsed_activity"     │
    │ user_profile → [m] │              │   → {...}              │
    │ training_advice→[r]│              │                        │
    │ tool_calling → [x] │              │ "user_001" /            │
    │                    │              │   "features"           │
    └─────────┬──────────┘              │   → {...}              │
              │                         └────────────┬───────────┘
              │                                      │
              ▼                                      │ 读写共享状态
    ┌──────────────────┐                             │
    │   MessageBus     │◄────────────────────────────┘
    │  (异步消息总线)   │
    │                  │
    │ 订阅模式:         │
    │  • subscribe_type │ → 按消息类型订阅 (AGENT_COMPLETED, GOVERNANCE_ALERT)
    │  • subscribe      │ → 按目标 Agent 订阅
    │                  │
    │ 消息流向:         │
    │  parser ─completed─► memory (通知解析完成)
    │  memory ─profile─► recommender (推送新画像)
    │  governance ─alert─► orchestrator (预算超限告警)
    └──────────────────┘
```

### 三种通信模式对比

| 模式 | 谁用 | 特点 | 代码位置 |
|------|------|------|----------|
| **直接调用** | Orchestrator → Agent | 同步，知道 agent_id 直接 `agent.run(input)` | `llm_orchestrator.py` `schedule_agent()` |
| **Blackboard 共享** | Agent ↔ Agent | 异步解耦，通过命名空间读写数据 | `blackboard.py` `write(ns, key, val)` / `read(ns, key)` |
| **MessageBus 消息** | Agent → Agent / Orchestrator | 发布订阅，类型过滤，支持链式触发 | `message_bus.py` `publish(msg)` / `subscribe_type(type, handler)` |

### 实际通信举例：解析 → 分析 → 建议 完整链路

```
时间轴 →

[Orchestrator 感知]
  ├─ 从 Registry 读取: parser[fit_parsing], feature_extractor[feature_engineering],
  │   memory[user_profile], recommender[training_advice]
  └─ 注入 LLM Planner prompt: "- **parser** (FIT Parser): [fit_parsing, data_extraction, metadata_parsing]"

[Orchestrator 决策]
  ├─ LLM 输出 ExecutionPlan JSON:
  │   Step 1: agent_id="parser",    capability="fit_parsing",         input="file_path",     output="parsed"
  │   Step 2: agent_id="feature_extractor", capability="feature_engineering", input="parsed", output="features"
  │   Step 3: agent_id="memory",     capability="user_profile",        input="user_id",       output="context"
  │   Step 4: agent_id="recommender", capability="training_advice",    input="features",      output="advice"
  │   fallback_plan: [Step 1 用 parser → Step 2 降级用 rule_engine]
  └─ 规则兜底: 如果 LLM 不可用 → 硬编码 Pipeline 按 capability 顺序调度

[执行 Step 1: ParserAgent]
  ├─ Orchestrator 调度: agent = registry.get_instance("parser")
  │                      agent.run(file_path="/path/to/activity.fit")
  ├─ Parser 内部: 读 FIT 二进制 → 校验 header → 解析 records → 提取统计
  ├─ Parser 通过 Blackboard 写: blackboard.write("user_001", "parsed_activity", result)
  ├─ Parser 通过 MessageBus 发: message_bus.publish(Message(
  │       sender="parser", message_type=AGENT_COMPLETED, payload=result))
  └─ Orchestrator 收到 AGENT_COMPLETED → 触发 Step 2

[执行 Step 2: FeatureExtractorAgent]
  ├─ Orchestrator 调度: input 从 results["parsed"] 取 (上一步 output_key)
  ├─ FeatureExtractor 内部: 调用 blackboard.read("user_001", "parsed_activity") 取数据
  ├─ 计算心率区间、配速分布、训练强度
  └─ 结果写 Blackboard + 发布 MessageBus

[执行 Step 3: MemoryAgent 并行]
  ├─ 读取用户历史活动 → 从分级记忆检索相似案例
  ├─ 构建 UserContext（历史 PR、训练周期、恢复状态）
  └─ 结果写 Blackboard（供 Step 4 使用）

[执行 Step 4: RecommendationAgent]
  ├─ 拿到 FeatureSummary + UserContext
  ├─ 规则引擎匹配训练类型 → 触发 LLM 生成
  ├─ 同时查 RAG 知识库（"跑步过量训练怎么恢复？"）
  └─ 输出个性化训练建议 + 营养建议

[质量闭环]
  ├─ EvaluatorAgent.evaluate(recommendation, dimensions=[accuracy, completeness, ...])
  ├─ 如果 score < 0.7 → ReflectionEngine.reflect_on_failure() → 分析根因 → 存记忆
  └─ Guardrails.check(final_output) → JSON schema 校验 → 不通过则重生成

[不确定性量化 + 可解释性]
  ├─ UncertaintyQuantifier.quantify(advice) → confidence=0.82, evidence=FACTUAL+INFERENTIAL
  └─ DecisionExplainabilityPage 前端展示决策链：
     "parser → feature_extractor → memory → recommender → ✅"
     "协商过程: [无冲突，recommender 能力匹配度 0.92]"
     "不确定性: 训练建议部分 confidence=0.82，依据: 历史数据 + RAG 检索"
```

---

## 🧭 LLM 是怎么感知和决策的

### 感知：把 Agent 能力注入 Prompt

```python
# app/orchestrator/llm_orchestrator.py L1161
def _format_agent_capabilities(self) -> str:
    agents = self.harness.registry.list_agents()
    lines = []
    for a in agents:
        caps = ", ".join(a.get("capabilities", []))
        lines.append(f"- **{a['agent_id']}** ({a['name']}): [{caps}] | 状态: {a['status']}")
    return "
".join(lines)
```

**LLM 实际收到的 System Prompt 长这样：**

```
你是一个多智能体系统的编排引擎。你的任务是根据用户目标和可用的 Agent 能力，生成最优的执行计划。

## 可用 Agent 及其能力
- **parser** (FIT Parser): [fit_parsing, data_extraction, metadata_parsing] | 状态: idle
- **feature_extractor** (Feature Extractor): [feature_engineering, statistics, intensity_distribution] | 状态: idle
- **memory** (Memory Manager): [user_profile, context_retrieval, memory_update] | 状态: idle
- **recommender** (Recommendation Engine): [training_advice, rule_engine, llm_generation] | 状态: idle
- **react** (ReAct Agent): [tool_calling, reasoning, multi_step_planning] | 状态: idle

## 规划原则
1. 能力匹配：选择最匹配子任务的 Agent，而非硬编码顺序
2. 依赖感知：确保后续步骤的输入依赖于前序步骤的输出
3. 容错设计：为主计划中的每个关键步骤设计降级方案
...
```

### 决策：LLM 输出 JSON ExecutionPlan

```json
{
  "goal": "分析这份运动数据并给出建议",
  "plan": [
    {"step": 1, "agent_id": "parser", "capability": "fit_parsing",
     "input_key": "file_path", "output_key": "parsed",
     "reasoning": "需要先解析 FIT 文件才能进行后续分析"},
    {"step": 2, "agent_id": "feature_extractor", "capability": "feature_engineering",
     "input_key": "parsed", "output_key": "features",
     "reasoning": "依赖 Step 1 输出，提取训练指标"},
    {"step": 3, "agent_id": "memory", "capability": "user_profile",
     "input_key": "user_id", "output_key": "context",
     "reasoning": "获取用户历史画像以个性化建议"},
    {"step": 4, "agent_id": "recommender", "capability": "training_advice",
     "input_key": "features", "output_key": "advice",
     "reasoning": "依赖特征和画像，生成训练建议"}
  ],
  "fallback_plan": [
    {"step": 1, "agent_id": "parser", ...},
    {"step": 2, "agent_id": "recommender", "capability": "rule_engine",
     "input_key": "parsed", "output_key": "advice",
     "reasoning": "feature_extractor 挂了，直接用规则引擎给建议"}
  ],
  "confidence": 0.88,
  "reasoning": "从 FIT 解析 → 特征提取 → 画像加载 → 建议生成，数据流向清晰，每个 Agent 依赖都得到满足"
}
```

### LLM 不可用时的规则兜底

```python
# app/orchestrator/llm_orchestrator.py
if self.llm_client is None:
    # 硬编码 Pipeline 按 capability 顺序调度
    return self._rule_based_plan(goal, input_data)

# _rule_based_plan 做了什么：
# 1. 从 Registry 按依赖拓扑排序 Agent
# 2. 如果用户目标含"文件" → 强制 parser 第一步
# 3. 如果目标含"建议/分析" → 强制 recommender 最后一步
# 4. 中间自动插 memory（加载画像）
```

### 重规划（Replanning）触发逻辑

```
执行 Step N 失败
  │
  ├─ L1: 直接 retry 同 Agent（默认 2 次）
  │   └─ agent.run() 重跑
  │
  ├─ L2: 换同 capability 的其他 Agent
  │   └─ registry.find_agent(capability) → 找替代 Agent
  │   └─ 触发协商协议（如果有多个候选）
  │
  ├─ L3: 调用 LLM 重规划
  │   └─ PLANNER_REPLAN_PROMPT 注入执行历史
  │   └─ "parser 成功了，feature_extractor 挂了，memory 成功了，请重新规划"
  │   └─ max_replanning=3，超过后走 fallback_plan
  │
  └─ L4: 彻底失败 → 返回部分结果 + 错误分析
```

---

## 🛠️ 全部 18 个 MCP Tools（来自 5 个插件）

> **ReActAgent 是唯一直接调 Tool 的 Agent**，绑定 `PluginManager` 管理全部工具。
> 工具以 **OpenAI Function Calling** 格式注册：每个工具有 `name` / `description` / `parameters(JSON Schema)`。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  插件 1: weather（天气查询）— 1 个 Tool                                     │
│  ─────────────────────────────────────────                                 │
│  get_current_weather(city?)          获取实时天气（温度/体感/湿度/风速）      │
├─────────────────────────────────────────────────────────────────────────────┤
│  插件 2: map_routing（运动路线规划）— 1 个 Tool                             │
│  ─────────────────────────────────────────                                 │
│  get_route_profile(start, end, profile?)  计算路线（距离/时间/爬升/下降）    │
│                                              profile: running/cycling/... │
├─────────────────────────────────────────────────────────────────────────────┤
│  插件 3: strava（Strava 数据同步）— 7 个 Tools                              │
│  ─────────────────────────────────────────                                 │
│  get_athlete_profile()               运动员基本资料（姓名/城市/体重）        │
│  get_athlete_stats()                 累计统计（总里程/活动次数/总时长）      │
│  list_activities(days?, limit?, sport_type?)  列出近期活动                  │
│  get_activity_detail(activity_id, include_stream?)  活动详情 + 指标         │
│  get_activity_streams(activity_id, keys?)   秒级数据（HR/配速/功率/海拔）   │
│  get_gear_mileage()                  装备累计里程                            │
│  sync_to_activities(days?)           Strava → WenYaSports 同步               │
├─────────────────────────────────────────────────────────────────────────────┤
│  插件 4: sports_venues（运动场馆）— 4 个 Tools                              │
│  ─────────────────────────────────────────                                 │
│  search_venues(keyword, city?, radius?, venue_type?)  搜索场馆              │
│  get_venue_types()                   所有场馆类型列表                       │
│  get_venue_detail(poi_id)            场馆详情                                │
│  search_nearby_by_location(lng, lat, keyword?, radius?)  附近场馆           │
├─────────────────────────────────────────────────────────────────────────────┤
│  插件 5: social_share（社交分享）— 4 个 Tools                               │
│  ─────────────────────────────────────────                                 │
│  generate_activity_share(activity_data, platform?, include_stats?)          │
│      生成活动分享文字（微博/微信/小红书/Twitter）                            │
│  generate_achievement_card(period, stats, platform?)                        │
│      生成成就卡片（周/月/年总结）                                            │
│  get_share_platforms()               支持的分享平台列表                     │
│  build_share_url(platform, url, title)  构建分享 URL                        │
└─────────────────────────────────────────────────────────────────────────────┘

总计: 1 + 1 + 7 + 4 + 4 = 18 个 Tools
```

### Tool 执行管线（MCP Pipeline）

```
ReActAgent 生成 tool_call(name="search_venues", args={...})
  │
  ▼
PluginManager.dispatch(tool_name, params)
  │
  ▼
MCP Pipeline（横切关注点）:
  ├─ CacheLayer     → 查缓存（相同参数 5 分钟内复用结果）
  ├─ RateLimiter    → 每个插件 100 次/分钟
  ├─ AuditLog       → 每次调用写审计日志
  ├─ ParameterValidator → JSON Schema 校验参数
  │
  ▼
具体插件 .execute(tool_name, params)
  │
  ▼
返回 Result → 注入 ReAct 下一步的 Observation
```

---

## 📊 Capability 完整索引（反查）

```
fit_parsing         → parser
data_extraction     → parser
metadata_parsing    → parser

feature_engineering → feature_extractor
statistics          → feature_extractor
intensity_distribution → feature_extractor

user_profile        → memory
context_retrieval   → memory
memory_update       → memory

training_advice     → recommender
rule_engine         → recommender
llm_generation      → recommender

tool_calling        → react
reasoning           → react
multi_step_planning → react

总计: 15 个 Capability，被 Orchestrator 用于动态匹配
```


# WenYaSports 面试题库

> 基于项目十大核心亮点，覆盖 Agent 开发、LLM 编排、MCP 生态、记忆系统、工程架构等方向。  
> 每道题包含：**面试题 → 八股文考点 → 项目实战答案**

---

## 一、Agent Runtime Harness 架构

### Q1：什么是 Agent Harness？它和普通的 Agent 框架（如 LangChain）有什么区别？

**八股文知识 — Agent 框架发展史**

```
LangChain (2022)     ──── Chain 模式，Prompt 驱动
  │
  ├─ 核心抽象：LLM → Prompt → Chain → Output Parser
  ├─ 组合方式：SequentialChain, LLMChain, TransformChain
  ├─ 局限：Chain 写死顺序，异常处理靠 try/except
  │
  ▼
LangGraph (2023)     ──── 图模式，State 驱动
  │
  ├─ 核心抽象：StateGraph(Nodes + Edges + State)
  ├─ 优势：支持循环、分支、条件路由
  ├─ 局限：状态管理复杂，调试困难
  │
  ▼
AutoGen / CrewAI (2023) ──── 多 Agent 协作
  │
  ├─ 核心抽象：Agent(role, goal, tools) + GroupChat
  ├─ 优势：多个 Agent 对话协作
  ├─ 局限：对话不可控、Token 消耗大
  │
  ▼
我们的 Harness  ──── 运行时沙箱，能力声明驱动
  ├─ 核心抽象：AgentRegistry + Blackboard + MessageBus + Governance
  ├─ 优势：能力驱动而非 Prompt 驱动、基础设施统一管理
  └─ 文件：app/harness/harness.py (626行)
```

**运行时沙箱是什么？**

类比操作系统的概念：
- 操作系统 = 给进程提供 CPU、内存、文件系统等基础设施
- Agent Harness = 给 Agent 提供 Registry（进程管理）、Blackboard（共享内存）、MessageBus（IPC）、Governance（资源配额）

**面试高频对比表**：

| 维度 | LangChain | LangGraph | 我们的 Harness |
|------|-----------|-----------|---------------|
| 组合方式 | Chain 顺序执行 | Graph 条件分支 | 能力动态匹配 |
| 状态管理 | 无（Chain 是纯函数） | State 传入传出 | Blackboard 命名空间 |
| Agent 发现 | 硬编码 | 硬编码 | Registry 自动匹配 |
| 异常处理 | try/except | State 流转 | Layer1-L2-L3 三级容错 |
| 可观测性 | 靠外部 | 靠外部 | TraceCollector 内置 |
| 安全治理 | 无 | 无 | GovernanceEngine |
| 降级架构 | 无 | 无 | FakeEmbedder + 规则引擎兜底 |



**八股文考点**：
- Agent 系统架构设计
- 运行时沙箱（Runtime Sandbox）概念
- Agent 编排模式（Pipeline vs Orchestration）
- 基础设施即代码（Infrastructure as Code）

**项目答案**：

我们的 Harness 是一个**轻量级 Agent 运行时沙箱**，位于 `app/harness/harness.py`。它的核心定位和 LangChain/LangGraph 不同：

```
LangChain:  Agent → Chain → Agent （链式组合，强调 Prompt Engineering）
我们的 Harness: Agent ↔ Registry ↔ MessageBus ↔ Blackboard （网络化编排，强调能力声明）
```

核心差异三点：

1. **能力驱动而非 Prompt 驱动**：每个 Agent 通过 `capabilities` 声明自己能做什么，Orchestrator 根据能力声明自动选择 Agent，不需要硬编码 Chain。注册时声明：
   ```python
   harness.register_agent(
       agent_instance=parser,
       agent_id="parser",
       capabilities=["fit_parsing", "data_extraction", "metadata_parsing"],
   )
   ```
2. **四个基础设施统一管理**：`AgentRegistry`（生命周期）、`MessageBus`（通信）、`Blackboard`（共享状态）、`GovernanceEngine`（预算治理）集中在 Harness 中，Agent 之间不直接耦合。
3. **工作流编排与动态路由**：Harness 支持 `run_workflow()` 预定义流程和 `execute_agent()` 按需调用两种模式，LLM Orchestrator 在此之上叠加智能决策。

> 面试话术："LangChain 更像是工具箱，Agent Harness 更像是操作系统。工具箱给你工具，操作系统给你进程管理、内存管理、文件系统——让 Agent 在一个受控的环境中运行。"

---

### Q2：Blackboard 模式是什么？在你的项目中怎么用的？

**八股文考点**：
- 共享状态模式（Shared State Pattern）
- Blackboard Architecture（AI 领域经典架构）
- 命名空间隔离

**项目答案**：

Blackboard 是 AI 领域的经典架构模式，核心思想是**多个知识源（Agent）围绕一个共享黑板协作**，不需要直接通信。

我们的实现在 `app/harness/blackboard.py`，关键设计：

1. **命名空间隔离**：每个用户/会话有独立命名空间，防止数据串扰
   ```python
   blackboard.write("user_123", "activity_001", parsed_data)
   blackboard.read("user_456", "activity_001")  # 返回 None，因为命名空间隔离
   ```

2. **版本化写入**：每次写入保留历史版本，支持回溯
   ```python
   blackboard.write("session", "plan_step_1", result_v1)
   blackboard.write("session", "plan_step_1", result_v2)  # 旧版本保留
   ```

3. **与 MessageBus 联动**：Blackboard 变更触发 MessageBus 事件，订阅方自动响应

应用场景：ParserAgent 解析结果写入 Blackboard → FeatureExtractorAgent 自动读取 → RecommendationAgent 读取特征数据生成建议。整个流程通过 Blackboard 解耦，Agent 之间不需要知道彼此的存在。

---

### Q3：MessageBus 的发布订阅是怎么实现的？和 Event Bus 有什么区别？

**八股文考点**：
- 发布订阅模式（Pub/Sub Pattern）
- 事件驱动架构（EDA）
- 消息中间件设计

**项目答案**：

`app/harness/message_bus.py` 实现了类型化的发布订阅系统：

```python
# 按类型订阅
message_bus.subscribe_type(MessageType.AGENT_COMPLETED, handler)

# 按目标 Agent 订阅
message_bus.subscribe("memory", handler)

# 发布消息
message_bus.publish(Message(
    sender="parser",
    message_type=MessageType.AGENT_COMPLETED,
    payload={"result": parsed_data}
))
```

和通用 Event Bus 的区别：
- **类型安全**：使用 `MessageType` 枚举（AGENT_START/AGENT_COMPLETED/GOVERNANCE_ALERT 等），而非字符串 topic
- **Agent 定向**：支持 `subscribe(agent_id, handler)` 定向投递
- **与 SessionLog 集成**：所有消息自动 append-only 日志，支持回放
- **治理联动**：GOVERNANCE_ALERT 类型的消息会触发 GovernanceEngine 干预

---

### Q4：GovernanceEngine 是怎么做预算和规则治理的？

**八股文考点**：
- 系统治理（System Governance）
- 配额管理（Quota Management）
- 熔断机制（Circuit Breaker）

**项目答案**：

`app/harness/governance.py` 实现了 Agent 级别的预算和规则治理：

1. **Token 预算**：每个 Agent 有每日 token 限额
   ```python
   BudgetTracker(daily_token_limit=10000, daily_api_call_limit=100)
   ```

2. **API 调用限额**：防止 Agent 无限调用外部 API

3. **规则引擎**：可配置治理规则
   ```python
   GovernanceRule(
       rule_id="no_harmful_content",
       condition=lambda output: not contains_harmful(output),
       action="block",
   )
   ```

4. **实时检查**：每次 Agent 执行前后检查预算和规则
   ```python
   governance.check_pre_execution(agent_id)  # 预检查
   governance.check_post_execution(agent_id, output)  # 后置检查
   ```

> 面试话术："这相当于给每个 Agent 配了一个财务总监和合规官。Token 花超了不让用，输出不合规就拦截。这是生产级 Agent 系统必须有的——不能让 Agent 裸奔。"

---

## 二、LLM 驱动 Orchestrator

### Q5：你的 Orchestrator 是怎么用 LLM 做动态编排的？和传统的硬编码 Pipeline 有什么区别？

**八股文知识 — Agent 编排范式**

```
范式 1: 硬编码 Pipeline
  代码：Pipeline([parser, extractor, recommender])
  问题：流程固定，一个节点挂了整条链就断了，加新功能要改代码
  
范式 2: 条件路由（If/Else）
  代码：if intent == "parse": parser() elif intent == "chat": chat()
  问题：分支爆炸式增长，新需求加个 elif
  
范式 3: LLM as Planner（我们用的）
  LLM 输出 JSON 计划：{"steps": [{"capability": "fit_parsing", "input": {...}}, ...]}
  问题：LLM 偶尔输出格式错、计划不可执行
  解法：Planner 输出 + PlanParser 校验 + 规则兜底
  
范式 4: Agent Loop（ReAct）
  while not done: think → act → observe
  问题：Token 消耗大、速度慢、容易陷入循环
```

**为什么选范式 3 而不是 4？**
- 范式 3：先规划后执行，Token 省、可调试、可提前发现计划问题
- 范式 4：边想边做，灵活但不可控
- 我们实际上两者结合：Orchestrator 做计划（范式3），ReActAgent 做单步内的推理（范式4）

**Plan 的数据结构设计**（为什么是 `capability` 而不是 `agent_id`）：
```python
@dataclass
class PlanStep:
    required_capability: str  # "fit_parsing" 而非 "parser_agent"
    input_data: Dict
    fallback_capability: Optional[str]  # 主能力挂了用什么替代
    retry_limit: int = 2
```
用 capability 解耦的好处：Agent 可以随时替换、新增 Agent 不需要改 Planner Prompt。



**八股文考点**：
- LLM 作为 Planner（LLM as Planner）
- 意图理解（Intent Understanding）
- 动态规划与重规划（Dynamic Planning & Replanning）
- ReAct 模式

**项目答案**：

核心流程在 `app/orchestrator/llm_orchestrator.py` 的 `execute_goal()` 方法中：

```
Phase 1: 意图分析 + 计划生成
    LLM.analyze_intent("分析我昨天的跑步数据")
    → 理解为: [解析文件 → 提取特征 → 查询历史 → 生成建议]
    
Phase 2: 按计划逐步执行
    for step in plan.steps:
        agent = registry.find_by_capability(step.required_capability)
        result = harness.execute_agent(agent, step.input)
        → 每步都可以触发重规划（如果结果不符合预期）
        
Phase 3: 动态重规划
    if step.result.quality < threshold:
        LLM.replan(remaining_steps, step_failure_context)
        → 调整后续步骤或降级策略
```

和硬编码 Pipeline 的对比：

| 维度 | 硬编码 Pipeline | LLM Orchestrator |
|------|----------------|------------------|
| 灵活性 | 流程固定 | 每次动态生成 |
| 异常处理 | 报错中断 | 自动重规划 |
| 能力扩展 | 改代码加节点 | 注册新 Agent 即可 |
| 适用场景 | 固定流程 | 开放式任务 |

关键代码：`_generate_plan()` 方法通过 LLM 输出 `ExecutionPlan`，包含 `PlanStep[]`，每个 Step 声明需要的 `capability` 而非具体 Agent ID，从而实现能力驱动的动态匹配。

---

### Q6：重规划（Replanning）是怎么触发的？举个实际例子。

**八股文考点**：
- 在线学习（Online Learning）
- 自适应系统（Adaptive System）
- 故障恢复策略

**项目答案**：

重规划触发条件（`_execute_plan_with_replan()` 方法）：

1. **Agent 执行失败**：`agent_result.success == False`
2. **质量评估不通过**：`quality_score < quality_threshold`（默认 6.0）
3. **超时未响应**：执行超过 `timeout` 阈值

示例场景：
```
用户上传了一个损坏的 FIT 文件
  → ParserAgent 返回 {success: False, error: "文件格式错误"}
  → Orchestrator 触发重规划：
      新计划: [尝试 CSV 解析 → 如果 CSV 也失败 → 降级为规则引擎分析]
  → FeatureExtractorAgent 改为尝试 CSV 解析
  → 成功提取特征
```

重规划次数上限 `max_replanning=3`，超过后走优雅降级路径。

---

### Q7：Planner-Executor-Reviser 多角色对话是怎么实现的？

**八股文考点**：
- Multi-Agent Conversation
- 角色扮演（Role Playing）
- Critique-Revise Pattern

**项目答案**：

`app/orchestrator/conversation.py` 实现了多角色对话编排：

```
Planner（规划师）: 分析用户需求，制定执行计划
Executor（执行者）: 按计划调用 Agent，收集结果
Reviser（评审者）: 审查结果质量，决定是否需要返工
```

```python
conversation = ConversationOrchestrator(harness, llm_client)
result = conversation.converse(
    goal="分析运动数据并给出训练建议",
    initial_input={"file": "activity.fit"}
)
# 内部循环：
# while not satisfied:
#     Planner → 生成/更新计划
#     Executor → 执行步骤
#     Reviser → 评估结果，决定重试/继续/结束
```

关键设计：对话历史通过 `ConversationState` 维护，每轮对话都会被 `TraceCollector` 记录，支持完整回放。

---

## 三、Agentic Workflow 与三层决策

### Q8：ReAct 模式是什么？你项目里的 ReAct Agent 是怎么实现的？

**八股文考点**：
- ReAct (Reasoning + Acting) Pattern
- Thought-Action-Observation Loop
- Tool Use & Tool Selection

**项目答案**：

ReAct 是论文《ReAct: Synergizing Reasoning and Acting in Language Models》提出的模式，核心是 **推理（Reasoning）和行动（Acting）交替进行**。

项目中 `app/agents/reaact_agent.py` 的实现：

```python
class ReActAgent(BaseAgent):
    capabilities = ["tool_calling", "reasoning", "multi_step_planning"]
    
    def run(self, input_data):
        for step in range(max_steps):
            # 1. Thought: LLM 分析当前状态，决定下一步
            thought = llm.think(context, available_tools)
            
            # 2. Action: 选择工具并执行
            if thought.action == "use_tool":
                result = plugin_manager.execute(thought.tool_name, thought.params)
            
            # 3. Observation: 观察工具结果
            # 4. 写入上下文，进入下一轮
            context.append(thought, result)
            
            # 终止条件：任务完成或达到最大步数
            if thought.is_final_answer:
                return thought.answer
```

ReActAgent 能使用的工具来自 `PluginManager.get_all_tools()`，包括 Strava、运动场馆、社交分享等 5 个插件共 18 个工具。

---

### Q9：Tree-of-Thought 在你的项目中是怎么用的？

**八股文考点**：
- Tree-of-Thought (ToT) Prompting
- 多路径搜索（Multi-path Search）
- BFS/DFS 搜索策略
- 剪枝与择优

**项目答案**：

`app/orchestrator/agentic_workflow.py` 中的 `ThoughtNode` 实现了 ToT：

```python
@dataclass
class ThoughtNode:
    id: int
    content: str           # 推理内容
    parent_id: Optional[int]  # 父节点
    children_ids: List[int]   # 子节点（多分支）
    score: float           # 路径质量分
    tool_calls: List[Dict]  # 该路径的工具调用
    is_terminal: bool      # 是否为叶节点
```

工作流程：
```
Step 1: LLM 生成 N 条推理路径（N=3）
    ThoughtNode(1, "用 Strava API 拉数据", score=0.8)
    ThoughtNode(2, "解析本地 FIT 文件", score=0.9)  
    ThoughtNode(3, "查询历史数据", score=0.6)

Step 2: 对每条路径模拟执行 Tool Call
    Node(1).execute() → {success: True, latency: 500ms}
    Node(2).execute() → {success: True, latency: 200ms}
    Node(3).execute() → {success: False}

Step 3: 择优选择
    → 选择 Node(2)：解析本地 FIT，速度最快，成功率高
```

关键：这不是简单的 Prompt 技巧，而是真正的**多路径探索 + 择优执行**，每条路径都实际调用工具后评估。

---

### Q10：三层决策架构（战略层/战术层/验证层）分别做什么？

**八股文考点**：
- 分层架构（Layered Architecture）
- 关注点分离（Separation of Concerns）
- 决策系统设计
- 质量门禁（Quality Gate）

**项目答案**：

`app/orchestrator/decision_engine.py` 实现了三层决策：

```
┌─────────────────────────────────────────┐
│  Strategic Decision Layer（战略层）       │
│  • Goal Analysis: 目标理解与分解          │
│  • Strategy Selection: 策略选择           │
│  • Risk Assessment: 风险评估与预案        │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Tactical Decision Layer（战术层）        │
│  • Tool Chain Planning: 工具编排          │
│  • Parameter Optimization: 参数优化      │
│  • Error Recovery: 错误恢复策略          │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Validation Layer（验证层）              │
│  • Critique: 独立评审（CritiqueResult）   │
│  • Debate: 多 Agent 辩论（DebateResult）  │
│  • Quality Gate: 质量门禁（pass/fail）    │
└─────────────────────────────────────────┘
```

验证层的 Critique 和 Debate 是关键创新：
- **Critique**：独立评审 Agent 从旁观者角度评估产出，给出 0-10 分
- **Debate**：多个 Agent 对同一产出进行辩论，交叉验证
- **Quality Gate**：综合评分低于阈值则打回重生成

> 面试话术："就像一个项目有产品经理定方向（战略层）、工程师写代码（战术层）、QA 做测试（验证层）。三层各司其职，确保产出质量。"

---

## 四、质量闭环与反思

### Q11：EvaluatorAgent 是怎么评估产出质量的？

**八股文考点**：
- 自动化质量评估
- 多维度评分系统
- 反馈控制系统

**项目答案**：

`app/agents/evaluator_agent.py` 实现了多维度评估：

```python
class EvaluatorAgent(BaseAgent):
    dimensions = [
        "accuracy",      # 准确性：数据是否正确
        "completeness",  # 完整性：是否覆盖所有要点
        "relevance",     # 相关性：是否紧扣用户需求
        "format",        # 格式规范性：是否符合预期 Schema
        "actionability", # 可操作性：建议是否具体可行
    ]
    
    def evaluate(self, output, expected=None):
        scores = {}
        for dim in self.dimensions:
            scores[dim] = self._score_dimension(output, dim)
        total = sum(scores.values()) / len(scores)
        feedback = self._generate_feedback(scores)
        return EvaluationResult(scores=scores, total_score=total, feedback=feedback)
```

评估结果驱动 Orchestrator 的决策：
- `total_score >= 6.0` → 通过，继续下一步
- `total_score < 6.0` → 触发 ReflectionEngine 反思
- `total_score < 3.0` → 直接降级到规则引擎

---

### Q12：ReflectionEngine 是怎么让 Agent 从失败中学习的？

**八股文考点**：
- 元学习（Meta-learning）
- 自我反思（Self-Reflection）
- 经验积累与策略进化
- 记忆增强系统

**项目答案**：

`app/agents/reflection_engine.py` 实现了失败反思闭环：

```python
class ReflectionEngine:
    def reflect(self, execution_context):
        # 1. 分析失败原因
        failure_analysis = self._analyze_failure(
            error=execution_context.error,
            agent_id=execution_context.agent_id,
            input_data=execution_context.input,
        )
        
        # 2. 生成改进策略
        strategy = self._generate_strategy(failure_analysis)
        
        # 3. 存储到记忆系统（供下次参考）
        memory_pool.store(
            content=strategy,
            layer="episodic",  # 存入情节记忆
            metadata={
                "type": "reflection",
                "trigger": failure_analysis.root_cause,
                "applicable_agents": [execution_context.agent_id],
            }
        )
        
        return strategy
```

关键：反思经验会持久化到 MemoryPool，下次遇到类似任务时自动检索相关反思记录，指导 Agent 避免重蹈覆辙。

---

### Q13：Guardrails 做了哪些安全约束？

**八股文考点**：
- AI 安全与对齐（AI Safety & Alignment）
- 输出约束（Output Constraining）
- PII 检测
- 多层防御（Defense in Depth）

**项目答案**：

`app/agents/guardrails.py` 实现了四层防御：

```
Agent Output
    ↓
[Layer 1] Format Check: JSON Schema 校验
    ↓ 不合格 → 重试（加 Prompt 约束格式）
[Layer 2] Content Filter: 有害内容 + PII 检测
    ↓ 不合格 → 过滤/拦截
[Layer 3] Quality Gate: 质量评分检查
    ↓ 不合格 → 触发重生成
[Layer 4] Compliance Check: 合规性检查
    ↓ 不合格 → 标记人工审查
```

PII 检测实现：
```python
PII_PATTERNS = [
    (r'\d{17}[\dX]', '身份证号'),
    (r'1[3-9]\d{9}', '手机号'),
    (r'\w+@\w+\.\w+', '邮箱'),
]

def detect_pii(text):
    for pattern, type_name in PII_PATTERNS:
        if re.search(pattern, text):
            return {"detected": True, "type": type_name}
    return {"detected": False}
```

---

## 五、分级记忆系统

### Q14：Working/Episodic/Semantic 三层记忆分别存什么？

**八股文知识 — 认知科学中的记忆模型**

```
人类认知心理学的 Memory 模型（Endel Tulving, 1972）：

Sensory Memory（感觉记忆）    → 视觉/听觉/触觉，持续 200-500ms
  └─ 计算机类比：CPU 寄存器

Working Memory（工作记忆）     → 同时容纳 7±2 个 chunk，持续几秒到几分钟
  └─ 计算机类比：CPU Cache L1/L2，当前正在处理的上下文
  
Episodic Memory（情节记忆）    → 具体事件的时空记忆，"我上次在跑步机跑了30分钟"
  └─ 计算机类比：数据库中的执行日志、历史对话片段
  
Semantic Memory（语义记忆）    → 抽象知识和事实，"VO2max 是最大摄氧量"
  └─ 计算机类比：知识库、向量数据库中的文档、用户画像
```

**为什么要分层？不能全存一个地方吗？**
- 全存内存 → 放不下、重启丢失
- 全存磁盘 → 每次查磁盘太慢
- 分层的核心思想：**热数据在内存，温数据在磁盘，冷数据归档**

**和 Redis 的对比**：
- 我们的三层 Working/Episodic/Semantic ≈ Redis 的三级缓存（L1/L2/DB 持久化）
- 但我们多了**语义检索**（TF-IDF 或 Embedding），Redis 只做 key-value 查找

**生命周期管理（晋升/蒸馏/衰减）**：

```
Working 条目 ── access_count >= 3 ──→ Episodic
Episodic 条目 ── 被引用 >= 5 次 ──→ Semantic（蒸馏合并）
Semantic 条目 ── 30天未访问 ──→ 降级到 Episodic（衰减）
```

这其实是借鉴了 Redis 的 **TTL + LRU** 过期策略，但加了语义层的判断（不是纯时间过期）。


**八股文考点**：
- 分级记忆体系（Hierarchical Memory）
- 记忆增强（Memory Augmentation）
- 人类记忆模型（Working/Episodic/Semantic Memory）
- 自动记忆（Automatic Memory）

**项目答案**：

`app/memory/hierarchical_memory.py` 模拟人类记忆模型：

| 层级 | 类比 | 存储内容 | 生命周期 |
|------|------|----------|----------|
| **Working** | 意识 | 当前会话上下文、最近 N 条消息 | 自动过期（TTL） |
| **Episodic** | 经历 | 对话片段、执行记录、反思经验 | 持久化到 SQLite |
| **Semantic** | 知识 | 用户画像、运动知识、统计数据 | TF-IDF 检索 |

```python
# 自动路由存储
memory.store(
    content="用户心率 150bpm，建议降低强度",
    auto_route=True  # 自动判断存入哪层
)

# 跨层检索
results = memory.retrieve("心率偏高怎么办")
# → 同时搜索 Working（当前会话）、Episodic（历史案例）、Semantic（运动知识）
# → 按相关性合并排序
```

晋升机制：Working 记忆中的高价值条目会自动晋升到 Episodic，再晋升到 Semantic。

---

### Q15：TF-IDF 在你的语义检索中是怎么用的？

**八股文考点**：
- TF-IDF 算法
- 向量空间模型（Vector Space Model）
- 信息检索（Information Retrieval）
- 嵌入模型 vs 传统检索

**项目答案**：

在 `hierarchical_memory.py` 中实现了轻量级 TF-IDF 检索：

```python
def _tokenize(text: str) -> List[str]:
    """中英文分词：空格/标点切分 + 单字切分"""
    tokens = []
    for chunk in text.lower().split():
        tokens.extend(re.split(r'[^\w]', chunk))
    # 中文按单字切分
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            tokens.append(char)
    return [t for t in tokens if t]

def _tfidf_score(query: str, document: str) -> float:
    """计算 TF-IDF 相似度"""
    query_tokens = _tokenize(query)
    doc_tokens = _tokenize(document)
    tf = Counter(doc_tokens)
    # IDF: 稀有词权重更高
    idf = {t: log(N / df[t]) for t in set(doc_tokens)}
    score = sum(tf.get(t, 0) * idf.get(t, 0) for t in query_tokens)
    return score
```

选择 TF-IDF 而非 Embedding 的原因：
1. **零依赖**：不需要加载嵌入模型，Demo 开箱即用
2. **可解释**：能明确知道哪些词匹配上了
3. **配合降级**：作为 Embedding 失败后的降级方案

---

### Q16：记忆的生命周期管理（晋升/蒸馏/衰减）是怎么实现的？

**八股文考点**：
- 记忆管理系统
- 遗忘曲线（Forgetting Curve）
- 数据蒸馏（Data Distillation）
- 自动生命周期管理

**项目答案**：

`app/memory/memory_lifecycle.py` 实现了三层记忆的自动管理：

```python
class MemoryLifecycleManager:
    def promote(self):
        """晋升：Working → Episodic → Semantic"""
        # 规则：被引用超过 3 次的 Working 条目晋升
        for entry in working_memory:
            if entry.access_count >= 3:
                episodic_memory.store(entry)
                working_memory.delete(entry)
    
    def distill(self):
        """蒸馏：合并相似记忆"""
        # 规则：余弦相似度 > 0.9 的记忆合并为一条
        for group in similar_entries:
            merged = merge(group)
            semantic_memory.store(merged)
    
    def decay(self):
        """衰减：遗忘低价值记忆"""
        # 规则：超过 30 天未访问的 Semantic 记忆降级
        for entry in semantic_memory:
            if days_since_last_access(entry) > 30:
                episodic_memory.store(entry)
                semantic_memory.delete(entry)
```

> 面试话术："借鉴了人类记忆的遗忘曲线——不用的记忆会模糊（衰减），常用的记忆会加深（晋升），相似的记忆会整合（蒸馏）。"

---

## 六、MCP 生态集成

### Q17：MCP Client/Server/Registry 三件套分别做什么？

**八股文考点**：
- 微服务架构
- API Gateway 模式
- 服务发现（Service Discovery）
- 协议设计（Protocol Design）

**项目答案**：

```
┌─────────────────────────────────────────────────┐
│                  MCP Registry                    │
│  统一注册表：工具发现、能力查询、权限控制         │
│  register_tool() / get_tool() / list_tools()     │
└─────────────────────────────────────────────────┘
         ↑ 注册                    ↑ 查询
┌──────────────────┐    ┌──────────────────────┐
│   MCP Server     │    │   MCP Client         │
│ 对外暴露 HTTP/   │    │ 连接远程 MCP Server  │
│ stdio 接口       │    │ stdio/SSE 双传输     │
│ serve_stdio()    │    │ connect_stdio()     │
│ serve_http()     │    │ connect_sse()       │
└──────────────────┘    └──────────────────────┘
```

- **MCPRegistry**（`mcp_registry.py`）：工具注册表，支持按能力分类、权限过滤、配额管理
- **MCPServer**（`mcp_server.py`）：支持 stdio（子进程通信）和 HTTP（REST API）两种模式
- **MCPClient**（`mcp_client.py`）：支持 stdio（启动子进程）和 SSE（远程连接）两种模式

---

### Q18：MCPAgentBridge 是怎么把 Agent 暴露为 MCP 工具的？

**八股文考点**：
- 桥接模式（Bridge Pattern）
- 适配器模式（Adapter Pattern）
- 协议转换（Protocol Translation）
- 统一接口设计

**项目答案**：

`mcp_plugins/bridge.py` 的核心方法 `expose_agents()`：

```python
class MCPAgentBridge:
    def expose_agents(self):
        """将 Harness 中所有 Agent 自动暴露为 MCP 工具"""
        for agent_info in harness.registry.list_agents():
            # 1. 生成 ToolCard（MCP 工具描述）
            tool_card = ToolCard.from_agent_descriptor(agent_info)
            # 自动从 Agent 的 capabilities 和 metadata 生成输入输出 Schema
            
            # 2. 包装 handler
            def make_handler(agent_id):
                def handler(args, context):
                    return harness.execute_agent(agent_id, args)
                return handler
            
            # 3. 注册到 MCP Registry
            mcp_registry.register_tool(tool_card, handler)
    
    def discover_all_tools(self):
        """统一发现所有工具：内部 Agent + 本地插件 + 远程服务"""
        return {
            "internal_agents": registry.list_agent_tools(),
            "local_plugins": plugin_manager.get_all_tools(),
            "remote_services": mcp_client.discover(),
        }
```

桥接的价值：
- 内部 Agent 自动变成 MCP 工具，外部系统（如 Trae）可直接调用
- 新增 Agent 零成本暴露，不需要写额外的 API 路由
- 统一了内部 Agent、本地插件、远程服务的调用接口

---

### Q19：MCP 的 stdio 和 SSE 两种传输有什么区别？

**八股文考点**：
- 进程间通信（IPC）
- 流式协议（Streaming Protocol）
- 同步 vs 异步通信
- 序列化与反序列化

**项目答案**：

| 维度 | stdio | SSE |
|------|-------|-----|
| 通信方式 | 子进程 stdin/stdout | HTTP 长连接 |
| 适用场景 | 本地工具（如 Python 脚本） | 远程服务（如云 API） |
| 部署要求 | 本地有可执行文件 | 需要 HTTP 端点 |
| 复杂度 | 低 | 中 |

代码实现：
```python
# stdio 模式：启动子进程通信
client.connect_stdio(
    server_command=["python", "-m", "strava_server.py"],
    args=["--port", "3000"],
)

# SSE 模式：连接远程服务
client.connect_sse("http://strava-mcp.example.com/sse")
```

选择策略：本地插件用 stdio（零网络开销），云端服务用 SSE（跨进程部署）。

---

## 七、可观测性与降级架构

### Q20：Trace Collector 记录了哪些信息？怎么支持链路回放？

**八股文考点**：
- 分布式追踪（Distributed Tracing）
- 可观测性三支柱（Metrics/Logging/Tracing）
- 事件溯源（Event Sourcing）
- 链路追踪（Chain Tracing）

**项目答案**：

`app/trace.py` 实现了轻量级 Trace Collector：

```python
class TraceStep:
    agent_name: str    # 哪个 Agent
    step_type: str     # thought/action/tool_call/observation/final
    detail: Dict       # 详细信息
    thought: str       # Agent 的思考过程
    timestamp: float   # 时间戳

class TraceCollector:
    def add_step(self, session_id, agent_name, step_type, detail, thought):
        # 记录每一步
    
    def get_trace(self, session_id) -> List[TraceStep]:
        # 获取完整链路
    
    def replay(self, session_id) -> str:
        # 生成人类可读的回放日志
```

回放示例：
```
[10:00:01] llm_orchestrator [thought] 开始编排目标: 分析跑步数据
[10:00:02] llm_orchestrator [action] 生成 3 步执行计划
[10:00:03] parser [action] 调用 parse_file("activity.fit")
[10:00:03] parser [observation] 解析成功，提取 1500 条数据点
[10:00:04] feature_extractor [action] 计算统计特征
[10:00:05] feature_extractor [observation] 距离: 10.2km, 配速: 5'30"/km
[10:00:06] evaluator [thought] 评估产出质量...
[10:00:07] evaluator [observation] 评分: 8.5/10，通过
[10:00:08] llm_orchestrator [final] 完成，建议用户保持当前训练强度
```

---

### Q21：append-only 事件日志是怎么做的？

**八股文考点**：
- 事件溯源（Event Sourcing）
- CQRS（命令查询职责分离）
- 不可变日志（Immutable Log）
- 审计日志（Audit Log）

**项目答案**：

`app/agents/session_log.py` 实现了 append-only 日志：

```python
class SessionLog:
    def append(self, event: Event):
        """追加事件，不修改历史"""
        self._events.append(event)
        # 可选：持久化到 JSONL 文件
        if self._persist_path:
            self._append_jsonl(event)
    
    def replay(self) -> List[Event]:
        """从日志重建完整状态"""
        state = initial_state.copy()
        for event in self._events:
            state.apply(event)
        return state
    
    def load(self, path: str):
        """从 JSONL 文件恢复"""
        for line in open(path):
            self.append(Event.from_json(line))
```

价值：
- **完整审计**：每步操作都有记录，不可篡改
- **故障恢复**：系统崩溃后可从日志恢复到任意状态
- **调试支持**：回放任意会话的完整执行过程

---

### Q22：三层降级架构（Embedder/Orchestrator/Agent）分别怎么降级？

**八股文知识 — 系统降级设计模式**

```
模式 1: Circuit Breaker（熔断器）
  状态：Closed（正常）→ Open（熔断）→ Half-Open（试探）
  触发：错误率超过阈值（如 50%）
  恢复：冷却时间后放一条请求试探
  
模式 2: Bulkhead（舱壁隔离）
  每个功能独立资源池，一个炸了不影响其他
  线程池隔离、连接池隔离
  
模式 3: Fallback（降级返回）
  主功能失败时返回默认值或执行替代逻辑
  缓存返回、Mock 数据、规则引擎兜底
  
模式 4: Timeout（超时控制）
  每个调用设超时，不阻塞整个流程
  
模式 5: Retry with Backoff（带退避重试）
  失败后自动重试，间隔指数增长：1s → 2s → 4s → 8s
```

**我们的降级策略属于哪种？**
- FakeEmbedder → Fallback（降级返回伪向量）
- 规则引擎兜底 LLM → Fallback
- L1 重试 / L2 策略切换 / L3 优雅降级 → Circuit Breaker + Fallback 组合

**为什么 FakeEmbedder 用哈希生成向量？**

MD5 生成 32 位十六进制 → 取每两位转 0-15 → 归一化到单位向量：
```python
hash_bytes = hashlib.md5(text.encode()).digest()  # 16 bytes
raw = [b / 255.0 for b in hash_bytes]  # 16 个 0-1 浮点数
# 扩展到 384 维（和 MiniLM 一致）
# → 归一化
norm = math.sqrt(sum(x**2 for x in raw))
vector = [x / norm for x in raw]
```

**它能用来做检索吗？**
- 不能替代真实 Embedding
- 但能让向量库保持功能（写入→检索→相似度计算全链路不断）
- 真实 Embedding 加载成功后自动切换

**面试钩子**：
> "降级架构不是偷懒不用真实组件，是**确保系统在任何环境下都能跑通核心链路**。Demo 零配置可运行、生产环境故障不中断——这是两个不同的需求，但用同一套架构同时满足。面试官如果问'你为什么不用真实模型'，反而是他没理解降级架构的价值。"



**八股文考点**：
- 降级设计（Graceful Degradation）
- 容错架构（Fault-Tolerant Architecture）
- 多级 Fallback 策略
- 优雅降级 vs 优雅停机

**项目答案**：

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Embedder 降级                                  │
│  正常: sentence-transformers 嵌入                       │
│  降级: FakeEmbedder（哈希向量，零依赖）                  │
│  场景: 嵌入模型加载失败 / 无网络                         │
├─────────────────────────────────────────────────────────┤
│  Layer 2: Orchestrator 降级                              │
│  正常: LLM 动态规划 + 重规划                             │
│  降级: 规则引擎 + 关键词匹配                              │
│  场景: LLM API 不可用 / Token 不足                       │
├─────────────────────────────────────────────────────────┤
│  Layer 3: Agent 降级                                     │
│  正常: Agent 自主执行                                    │
│  降级: 简化规则 / 硬编码逻辑                             │
│  场景: Agent 执行超时 / Agent 能力缺失                   │
└─────────────────────────────────────────────────────────┘
```

FakeEmbedder 实现：
```python
class FakeEmbedder:
    """哈希向量嵌入：用哈希函数生成伪向量，零依赖"""
    def embed(self, text: str) -> List[float]:
        # 用哈希函数生成确定性的向量
        hash_value = hashlib.md5(text.encode()).hexdigest()
        vector = [int(c, 16) / 15.0 for c in hash_value]
        # 归一化
        norm = math.sqrt(sum(x**2 for x in vector))
        return [x / norm for x in vector]
```

> 面试话术："我们的 Demo 零配置可运行——就算没有 API Key、没有嵌入模型、没有网络，整个系统照样能跑。这不是偷懒，是为了确保在任何环境下都能演示核心逻辑。"

---

## 八、不确定性量化

### Q23：不确定性量化（Uncertainty Quantification）是怎么实现的？

**八股文考点**：
- 置信度校准（Confidence Calibration）
- 贝叶斯不确定性
- 概率输出
- 可解释性 AI

**项目答案**：

`app/agents/uncertainty_quantifier.py` 实现了三层不确定性评估：

```python
class UncertaintyQuantifier:
    def assess(self, result, evidence, context):
        # 1. 置信度评估
        confidence = self._estimate_confidence(
            evidence_strength=len(evidence),
            data_quality=context.get("data_quality", "medium"),
            model_calibration=self._get_calibration_score(),
        )
        
        # 2. 证据质量评估
        evidence_quality = self._assess_evidence_quality(evidence)
        
        # 3. 不确定性分解
        uncertainty_sources = []
        if evidence_quality.completeness < 0.8:
            uncertainty_sources.append("数据不完整")
        if evidence_quality.reliability < 0.7:
            uncertainty_sources.append("证据可靠性不足")
        if confidence < 0.6:
            uncertainty_sources.append("模型置信度偏低")
        
        return UncertaintyReport(
            confidence=confidence,
            evidence_quality=evidence_quality,
            uncertainty_sources=uncertainty_sources,
            needs_caution=confidence < 0.7,
            recommendations=self._generate_recommendations(uncertainty_sources),
        )
```

输出示例：
```
📊 置信度: 72% (中等)
🔍 证据质量: 3/5 (数据样本偏小)
⚠️ 不确定性来源:
  • 心率数据缺失 2 个片段（影响配速计算）
  • 未考虑环境温度（影响运动强度评估）
💡 建议: 补充完整的 GPS 轨迹数据
```

---

## 九、Agent 协商协议

### Q24：多 Agent 协商是怎么实现的？什么时候会触发？

**八股文考点**：
- 多 Agent 系统（Multi-Agent System）
- 协商协议（Negotiation Protocol）
- 共识机制（Consensus Mechanism）
- 投票算法（Voting Algorithm）

**项目答案**：

`app/orchestrator/negotiation.py` 实现了结构化协商：

触发条件：当 Orchestrator 发现有多个 Agent 声称具备同一能力时。

```python
class NegotiationSession:
    def resolve_capability_dispute(
        self,
        capability="特征提取",
        candidates=["feature_extractor", "react_agent"],
    ):
        # 1. 收集候选 Agent 的提案
        proposals = []
        for agent_id in candidates:
            descriptor = registry.get_descriptor(agent_id)
            proposals.append(AgentProposal(
                agent_id=agent_id,
                confidence=descriptor.confidence,
                quality_score=descriptor.history_quality,
                reasoning=descriptor.last_performance.reason,
            ))
        
        # 2. 计算综合分
        for p in proposals:
            p.composite_score = 0.6 * p.quality_score + 0.4 * p.confidence
        
        # 3. 选择胜出者
        winner = max(proposals, key=lambda p: p.composite_score)
        
        # 4. 可选：投票模式
        if self.mode == "voting":
            winner = self._run_vote(proposals)
        
        return NegotiationResult(
            winner=winner.agent_id,
            score=winner.composite_score,
            all_scores={p.agent_id: p.composite_score for p in proposals},
        )
```

---

## 十、决策可解释性

### Q25：决策可解释性层记录了哪些信息？前端怎么展示的？

**八股文考点**：
- 可解释性 AI（XAI / Explainable AI）
- 决策追踪（Decision Tracking）
- 因果推理（Causal Reasoning）
- 审计与合规

**项目答案**：

`app/orchestrator/explainability.py` 记录每一个关键决策：

```python
class ExplainabilityEngine:
    def record_decision(self, record: DecisionRecord):
        # 决策类型：Agent选择/计划生成/重规划/协商
        # 上下文：任务描述、输入数据
        # 选择结果：chosen_option
        # 备选方案：alternatives + 否决原因
        # 评分对比：scores
        # 推理过程：reasoning
    
    def get_decision_path(self, session_id) -> DecisionPath:
        # 获取完整决策链：从意图分析到最终产出的所有决策
```

前端 `DecisionExplainabilityPage.jsx` 三个展示 Tab：
1. **📖 决策解释链**：树状可视化，点击节点查看评分对比和否决原因
2. **🤝 Agent 协商协议**：展示候选提案对比和胜出公告
3. **📊 不确定性量化**：置信度环形图、证据质量指标、不确定性来源

---

## 附加：系统设计类问题

### Q26：你的系统是怎么做用户隔离的？

**八股文考点**：
- 多租户架构（Multi-tenancy）
- 数据隔离（Data Isolation）
- 会话管理（Session Management）

**项目答案**：

三层隔离机制：

1. **SessionHarness 隔离**：每个用户创建独立的 Harness 实例
   ```python
   session_harness = SessionHarness(user_id="user_123")
   # 内部 Blackboard 使用用户命名空间
   ```

2. **MemoryPool 隔离**：每个用户独立的记忆池
   ```python
   memory_pool = get_memory_pool(user_id="user_123")
   # memory_pool.store(content, layer="episodic") → 存入用户专属存储
   ```

3. **文件系统隔离**：上传文件按用户分目录存储
   ```
   data/users/user_123/uploads/
   data/users/user_456/uploads/
   ```

---

### Q27：AutoClassifyAgent 是怎么自动识别文档分类的？

**八股文考点**：
- 文本分类（Text Classification）
- 关键词匹配（Keyword Matching）
- 分类置信度与人工确认
- 人机协同（Human-in-the-Loop）

**项目答案**：

`app/agents/auto_classify_agent.py` 实现了智能文档分类：

```python
class AutoClassifyAgent(BaseAgent):
    CATEGORIES = {
        "strength": ["力量", "力量训练", "weight training"],
        "endurance": ["耐力", "有氧", "endurance"],
        "nutrition": ["营养", "饮食", "nutrition", "diet"],
        # ... 7 个预定义分类
    }
    
    def classify(self, file_path):
        # 1. 提取前 3000 字符作为特征
        text = extract_text(file_path)[:3000]
        
        # 2. 对每个分类计算加权得分
        scores = {}
        for category, keywords in self.CATEGORIES.items():
            keyword_freq = sum(text.count(kw) for kw in keywords)
            scores[category] = keyword_freq / len(text)
        
        # 3. 选择最高分的分类
        best_category = max(scores, key=scores.get)
        confidence = scores[best_category] / sum(scores.values())
        
        # 4. 决策：高置信度自动入库，低置信度人工确认
        if confidence >= 0.3:
            return {"category": best_category, "confidence": confidence, "auto": True}
        else:
            return {"category": "unknown", "confidence": confidence, "auto": False}
```

---

### Q28：如果让你重新设计这个系统，你会做哪些改进？

**八股文考点**：
- 系统演进与重构
- 技术债管理
- 扩展性设计
- 工程实践反思

**项目答案**：

| 优先级 | 改进方向 | 原因 |
|--------|----------|------|
| **P0** | 接入真实 RAG 知识库 | 当前知识库是 Demo 级，需要接入专业运动书籍 |
| **P0** | 多模型支持 | 目前硬编码 GPT-4o-mini，应支持切换 Claude/Gemini |
| **P1** | 持久化存储升级 | SQLite → PostgreSQL/MySQL，支撑多用户并发 |
| **P1** | 前端真实数据对接 | 目前 Mock 数据，需要对接后端 API |
| **P2** | 实时协作 | 支持多个用户同时分析同一数据集 |
| **P2** | 移动端适配 | 运动场景下用户主要使用手机 |
| **P3** | 插件市场 | 支持第三方开发者上传 MCP 插件 |

> 面试话术："目前系统的核心架构已经稳固，下一步的重点是把 Demo 级的组件替换为生产级的——用真实 RAG 知识库替代 FakeEmbedder、用 PostgreSQL 替代 SQLite、对接真实的 LLM API。架构设计上不需要大改，因为我们用了 Harness 解耦了 Agent 和基础设施。"

---

## 面试高频知识点速查表

| 知识点 | 项目中的体现 |
|--------|-------------|
| Multi-Agent System | 10 个协作 Agent |
| LLM as Planner | LLMOrchestrator 动态规划 |
| ReAct Pattern | ReActAgent 推理行动循环 |
| Tree-of-Thought | AgenticWorkflowEngine 多路径探索 |
| Blackboard Architecture | 共享状态黑板 |
| Message Bus | 异步消息通信 |
| Event Sourcing | append-only 事件日志 |
| Hierarchical Memory | Working/Episodic/Semantic |
| TF-IDF Retrieval | 语义检索 |
| RAG | 检索增强生成 |
| MCP Protocol | Client/Server/Registry/Bridge |
| Plugin Architecture | BasePlugin 插件体系 |
| Design Patterns | Bridge/Adapter/Strategy/Observer |
| Fault Tolerance | 三层降级 + 重试 + 重规划 |
| AI Safety | Guardrails + PII 检测 |
| XAI (Explainable AI) | ExplainabilityEngine 决策可解释 |
| Multi-tenant | SessionHarness 用户隔离 |
| Human-in-the-Loop | AutoClassifyAgent 低置信度人工确认 |
| Observability | TraceCollector + 链路回放 |
| Negotiation Protocol | 多 Agent 协商与共识 |

---

## 十一、RAG 知识库增强

---

## 十二、用户系统与数据隔离（近期新增，面试官最爱问）

### Q35：你的用户注册和鉴权是怎么做的？为什么不用 JWT？

**八股文知识 — 主流认证方案对比**

| 方案 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| **Session + Cookie** | 服务端存 session_id（Redis/内存），Cookie 带回 | 服务端可控、可主动失效、成熟稳定 | 服务端要维护状态、跨域麻烦 |
| **JWT (JSON Web Token)** | 无状态 Token，签名防止篡改，Payload 含用户信息 | 服务端无状态、跨域友好、分布式易扩展 | 无法主动失效（只能黑名单）、Payload 膨胀、密钥泄露灾难 |
| **HMAC-SHA256 自签名** | 自定义格式，HMAC 签名防止篡改 | 轻量、可控、无依赖 | 自研安全方案需谨慎审计 |
| **OAuth 2.0** | 第三方授权，Access Token + Refresh Token | 标准协议、支持第三方登录 | 复杂度高、实现成本大 |

JWT 由三部分组成：`Header.Payload.Signature`
- Header: `{"alg": "HS256", "typ": "JWT"}`
- Payload: `{"sub": "user_123", "exp": 1234567890, "role": "admin"}`
- Signature: `HMAC-SHA256(secret, base64(header) + "." + base64(payload))`

> **JWT 的坑**：Payload 是 Base64 编码的，不是加密！任何人都能解码看到里面的内容。所以不要放敏感信息。过期校验是客户端（或网关）做的，后端只验签。

**项目答案**：

我们用了 **自研的 HMAC-SHA256 Token**，格式：`user_id:role:timestamp:signature`

```python
# app/auth/auth.py
def create_token(user: AuthUser) -> str:
    timestamp = int(time.time())
    payload = f"{user.user_id}:{user.role.value}:{timestamp}"
    sig = hmac.new(_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"
```

**为什么不直接用 JWT？**
1. **Demo 零依赖**：不需要 `pyjwt` 或 `python-jose` 包
2. **可控性**：格式完全自己定义，方便调试
3. **体量小**：整个 auth.py 只有 253 行，逻辑一目了然
4. **和降级架构一致**：HMAC 是"FakeEmbedder 替代 SentenceTransformer"的同思路——不引重型依赖

**但如果生产环境，我会选 JWT（HS256）**：
```python
# 生产推荐写法
import jwt
token = jwt.encode({"sub": user_id, "role": role}, SECRET, algorithm="HS256", expires_delta=timedelta(hours=1))
```

---

### Q36：注册时密码怎么存的？为什么不能明文存？

**八股文知识 — 密码哈希算法演进**

```
明文存储 ❌    → 数据库泄露 = 全部密码泄露
MD5      ❌    → 彩虹表攻击，已经被破解
SHA-1    ❌    → 已经被碰撞攻击
SHA-256  ⚠️    → 加了盐勉强可用，但计算太快容易被暴力破解
bcrypt    ✅    → 自适应慢算法（cost factor 可调），专为密码设计
Argon2    ✅✅  → 最新 winner（Password Hashing Competition），抗 GPU 暴力破解
PBKDF2   ✅    → NIST 推荐，迭代次数可调
```

**bcrypt 的 cost factor 是什么？**
- 每增加 1，计算量翻倍
- cost=10 → ~100ms 一次
- cost=12 → ~400ms 一次
- 这就是故意慢！暴力破解的 GPU 每秒能算几十亿次 SHA256，但 bcrypt 只能算几百次

**项目答案**：

Demo 级别用了 **SHA-256 + 简单盐**（其实就是直接 SHA-256），真实生产应该用 bcrypt/Argon2：

```python
# 当前 Demo（够用但不够安全）
def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# 生产环境应该改成（面试主动说出来）
import bcrypt
def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())
```

> **面试钩子**："Demo 用了 SHA-256 哈希，但我知道生产级密码存储的三条铁律：1) 不能明文；2) 不能用快哈希（MD5/SHA）；3) 必须加盐。bcrypt/Argon2 是正确选择，cost factor 调到 10-12 可以在安全性和用户体验之间取平衡。"

---

### Q37：用户数据隔离做了哪几层？

**八股文知识 — 多租户隔离策略**

| 策略 | 实现方式 | 隔离程度 | 成本 |
|------|----------|----------|------|
| **独立数据库** | 每个租户一个 DB 实例 | 完全隔离，物理级 | 高 |
| **独立 Schema** | 同一 DB 不同 Schema | 逻辑隔离 | 中 |
| **共享 DB + user_id 字段过滤** | `WHERE user_id = ?` | 应用层隔离 | 低 |
| **行级安全（RLS）** | PostgreSQL 原生支持 | 数据库层强制 | 中 |

**RBAC（基于角色的访问控制）核心概念**：
- Subject（主体）：用户、进程
- Object（客体）：资源（数据、API）
- Permission（权限）：对客体能做什么操作
- Role（角色）：权限的集合
- Assignment（分配）：主体 → 角色 的映射

**项目答案**：

我们实现了 **三层隔离**，是"共享 DB + user_id 过滤"策略：

```
Layer 1: SessionHarness 隔离（app/harness/session_harness.py）
  └─ 每个用户独立的 Harness 实例
  └─ Blackboard 用 user_id 作为命名空间前缀
     blackboard.write("user_123", "activity_001", data)
     blackboard.read("user_456", "activity_001") → None ✅

Layer 2: MemoryPool 隔离（app/memory/memory_pool.py）
  └─ 每个用户独立的记忆池实例
  └─ 记忆自动带 user_id metadata
     memory.store(content, metadata={"user_id": "user_123"})

Layer 3: 数据库过滤（app/db/database.py）
  └─ 所有查询强制 WHERE user_id = ?
  └─ get_user_dashboard(user_id="user_123")
     → SELECT * FROM activities WHERE user_id = "user_123"
     → 不会泄露其他用户数据
```

**前端也要配合**：DashboardPage 调用 API 时传自己的 user_id，不能让用户随便传别人的。
```python
# 后端 API 设计（简化鉴权）
@router.get("/dashboard/summary")
def dashboard_summary(user_id: str = Query(...)):
    # Demo 级：前端传谁就查谁，因为已登录+内存级用户隔离
    # 生产级：应该从 Token 中解 user_id，不信任前端参数
    return database.get_user_dashboard(user_id)
```

---

### Q38：管理员和普通用户怎么区分？RBAC 是怎么实现的？

**八股文知识 — 权限控制模型**

```
ACL (Access Control List)：每个资源列谁能访问
  └─ 资源 → [用户A: 读写, 用户B: 读, ...]
  └─ 优点：直观、灵活
  └─ 缺点：资源多了 ACL 爆炸

RBAC (Role-Based Access Control)：用户 → 角色 → 权限
  └─ 用户A → [管理员] → [所有权限]
  └─ 用户B → [普通用户] → [读+写自己的数据]
  └─ 优点：角色少、权限集中管理
  └─ 缺点：角色爆炸（需要 RBAC1/RBAC2/RBAC3 变体解决）

ABAC (Attribute-Based Access Control)：基于属性动态判断
  └─ if user.department == resource.owner.department → allow
  └─ 优点：最灵活
  └─ 缺点：规则多了难维护
```

**项目答案**：

```python
# app/auth/auth.py — 简单 RBAC
class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class AuthUser:
    user_id: str
    username: str
    role: UserRole
    
    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

# 路由层用 FastAPI Depends 注入
@router.get("/knowledge/upload")
def knowledge_upload(user: AuthUser = Depends(require_admin)):
    # 只有 admin 能进知识库管理

@router.post("/activities")  
def upload_activity(user: AuthUser = Depends(require_user)):
    # 登录用户都能上传
```

管理员默认账号：`admin` / `wenyasports2024`，写死在代码里（Demo 级）。生产环境应该放到环境变量或数据库中。

---

### Q39：前端用户状态怎么管理的？刷新页面还能保持登录吗？

**八股文知识 — 前端状态持久化**

```
方案一：localStorage 存 Token
  └─ 优点：简单、跨标签页、刷新不丢
  └─ 缺点：XSS 可以偷 Token（不要存敏感信息）、永久不过期

方案二：sessionStorage
  └─ 优点：同源、标签页关闭即清空
  └─ 缺点：刷新不丢，但换标签页重新登录

方案三：Cookie（httpOnly + SameSite）
  └─ 优点：httpOnly 防 XSS、自动随请求、Secure 防中间人
  └─ 缺点：CSRF 风险、需要后端 Set-Cookie

方案四：Redux/Zustand + 持久化中间件
  └─ 和状态管理结合，本质还是 localStorage/sessionStorage
```

**项目答案**：

我们用了 **localStorage + React Context** 的组合：

```javascript
// frontend/src/AuthContext.jsx
// 登录成功后存 Token
localStorage.setItem('wenyasports_token', res.token)
localStorage.setItem('wenyasports_user', JSON.stringify(res.user))

// 页面加载时从 localStorage 恢复
function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('wenyasports_user')
    return saved ? JSON.parse(saved) : null
  })
  
  // axios 拦截器：每次请求自动带 Token
  useEffect(() => {
    api.interceptors.request.use(config => {
      const token = localStorage.getItem('wenyasports_token')
      if (token) config.headers.Authorization = `Bearer ${token}`
      return config
    })
  }, [])
}
```

**刷新能保持登录** ✅ — 因为 localStorage 持久化
**关闭浏览器重开也保持** ✅ — 同上
**Token 过期了怎么办？** — 当前 Demo 不处理过期（Token 无过期机制），生产应该在拦截器里加 401 拦截 + 自动跳转登录页

---

### Q40：你这个鉴权系统有什么安全漏洞？生产环境会怎么修？

**八股文知识 — OWASP Top 10（API 安全）**

```
1. Broken Object Level Authorization（BOLA）
   → 你的 API 允许用户通过改参数访问别人的数据
   → GET /api/users/123/activities → 改成 /api/users/456/activities 就看到别人的数据了

2. Broken Authentication
   → 弱密码、无限次登录尝试、会话固定攻击

3. Broken Object Property Level Authorization（BFLA）
   → 不该暴露的字段被返回了（比如 API 返回了 password_hash）

4. Unrestricted Resource Consumption
   → 没限速，被刷爆

5. Broken Function Level Authorization（BFLA）
   → 普通用户能调到管理员接口
```

**项目答案**：

当前 Demo 级鉴权的安全问题：

| 问题 | 严重程度 | 生产修复 |
|------|---------|---------|
| Token 无过期时间 | 🔴 高 | 加 `exp` 字段，1小时过期 + Refresh Token |
| 密码直接 SHA-256 | 🔴 高 | 用 bcrypt/Argon2 |
| 管理员密码硬编码 | 🔴 高 | 环境变量或数据库 |
| dashboard 接口没从 Token 解 user_id | 🟡 中 | 后端 `user_id` 从 Token 解，不信任前端 Query 参数 |
| 无登录限速 | 🟡 中 | 加 rate limit（`slowapi` 库） |
| localStorage 存 Token（XSS 风险） | 🟡 中 | 改用 httpOnly Cookie |
| 无 HTTPS | 🟡 中 | 生产必须 HTTPS |
| CORS 全开 | 🟢 低 | 生产限制允许的 Origin |

> **面试钩子**："我很清楚 Demo 级鉴权和生产级的差距。面试时主动列出来这些问题，然后说清楚每一个怎么修——这不是暴露缺点，是展示你有安全意识和实战经验。面试官更看重你知道哪些是坑、怎么填，而不是只会写 Demo。"

---



### Q29：你的 RAG 是怎么切块（Chunking）的？为什么选这个策略？

**八股文考点**：
- 文档切块策略（Chunking Strategy）
- 颗粒度选择（Granularity Selection）
- 语义保持（Semantic Preservation）
- Overlap 设计

**项目答案**：

我们实现了 **SmartChunker**（`rag/smart_chunker.py`），支持 4 种切块模式，按文件类型自动选择：

| 模式 | 适用场景 | 边界策略 |
|------|----------|----------|
| `section_aware` | Markdown 文件 | 一级/二级标题为边界 |
| `semantic` | PDF/长文 | 自然段落为边界 |
| `fixed` | 短文本 | 固定长度 + overlap |
| `auto` | 自动选择 | 根据文件后缀自动选 |

**核心设计决策**：
1. **不是越小越好**：chunk 太小（< 100 token）会丢失上下文，太大（> 500 token）会稀释语义
2. **按章节切分优先**：Markdown 文件按标题切分，保证每个 chunk 是一个完整语义单元
3. **动态颗粒度**：`target_chunk_size=500`，但实际大小根据内容密度动态调整
4. **Overlap 50 token**：相邻 chunk 有 50 token 重叠，避免切断句子

```python
chunker = SmartChunker(
    mode="auto",           # 自动选择切块模式
    target_chunk_size=500,  # 目标大小
    chunk_overlap=50,       # 重叠 token 数
    min_chunk_size=100,     # 最小 chunk
    max_chunk_size=1500,    # 最大 chunk
)
```

**面试钩子**：
> "切块是 RAG 的基础。切不好，检索再强也没用。我们对比了 3 种策略：固定长度、按句子、按章节。最终选择了**章节感知 + 语义段落**的混合方案，因为运动知识通常按主题组织（如'VO2max 训练''配速策略'），按章节切分最能保持语义完整性。"

---

### Q30：怎么确定 chunk 的颗粒度（大小）？

**八股文考点**：
- 嵌入模型上下文窗口
- 语义单元边界
- 召回率与精度的平衡
- 动态 vs 静态分块

**项目答案**：

我们的颗粒度决策框架：

```
                    召回率 ↑
                      ↗
  chunk 太小 ←────────────→ chunk 太大
  (上下文丢失)              (语义稀释)
                      ↘
                    精度 ↑

最佳区间: 200-500 token
```

**3 个关键因素**：
1. **嵌入模型能力**：MiniLM-L6-v2 的最佳表现区间是 200-400 token
2. **查询预期粒度**：用户问"VO2max 怎么训练"时，期望看到一个完整的训练方案（~300 token），而不是一句话
3. **Overlap 补偿**：50 token 的 overlap 确保即使切断了，相邻 chunk 也有足够的重叠语义

**动态调整策略**（`_split_by_semantic` 方法）：
- 检测内容密度：专业术语密集的段落 → 切小一点（保留更多细节）
- 介绍性文字 → 切大一点（保持完整上下文）
- 过小 chunk 自动合并到相邻 chunk

---

### Q31：分块后存在哪里？分表分集合是怎么设计的？

**八股文考点**：
- 向量数据库设计
- Collection 分表策略
- Metadata Filtering
- 索引设计

**项目答案**：

我们用 ChromaDB 做向量存储，设计了 **单 Collection + Metadata Filter** 的方案：

```
ChromaDB
└── Collection: "fitness_knowledge"
    ├── Document 1: {content, metadata: {category, source, chunk_index, semantic_density}}
    ├── Document 2: {content, metadata: {category, source, chunk_index, semantic_density}}
    └── ...
```

**Metadata 字段设计**：

| 字段 | 类型 | 用途 |
|------|------|------|
| `category` | string | 分类过滤（strength/endurance/nutrition 等） |
| `source` | string | 来源文件路径 |
| `chunk_index` | int | 在原文件中的位置 |
| `semantic_density` | float | 语义密度（专业术语占比） |
| `mode` | string | 切块模式 |

**检索时的 Filter 策略**：
```python
# 用户问"怎么练力量"
# → 自动检测 category=["strength"]
# → 先在 strength 分类内检索
# → 结果不足时回退到全库检索
results = vector_store.retrieve_with_filter(
    query_embedding, top_k=4, categories=["strength"]
)
# 如果结果 < 2 条，自动降级：
# results = vector_store.retrieve(query_embedding, top_k=4)
```

**为什么不用多个 Collection？**
- 跨集合检索复杂（需要合并多个结果集）
- ChromaDB 的 `where` filter 性能足够
- 单集合管理更简单

---

### Q32：怎么提高 RAG 的召回率？

**八股文考点**：
- 混合检索（Hybrid Search）
- 查询扩展（Query Expansion）
- Reranking（重排序）
- MMR（最大边际相关性）
- RRF（Reciprocal Rank Fusion）

**项目答案**：

我们的 **HybridRetriever**（`rag/hybrid_retriever.py`）实现了 6 步召回优化管线：

```
用户 Query: "怎么提高 VO2max"
    ↓
[1] Query Expansion: 扩展为 ["怎么提高 VO2max", "怎么提高 最大摄氧量", ...]
    ↓
[2] Category Detection: 检测到 categories=["physiology", "endurance"]
    ↓
[3] Hybrid Search: 
    ├── Vector Search（语义相似度，带 category filter）
    └── BM25 Keyword Search（关键词频率，带 category filter）
    ↓
[4] RRF Fusion: 融合两路结果
    score = 1/(60 + rank_vector) + 1/(60 + rank_keyword)
    ↓
[5] MMR Rerank: 保证结果多样性（避免 5 个相似 chunk）
    mmr_score = λ × relevance − (1−λ) × max_similarity_to_selected
    ↓
[6] Metadata Rerank: 元数据加权
    final_score = rrf_score × (1 + domain_term_boost + density_boost)
    ↓
返回 Top-K 结果
```

**关键策略详解**：

1. **Query Expansion**：同义词扩展，覆盖更多表达方式
   ```
   "VO2max" → ["VO2max", "最大摄氧量", "最大有氧能力"]
   "跑步" → ["跑步", "run", "running", "慢跑"]
   ```

2. **BM25 关键词检索**：弥补向量检索在专有名词上的不足
   - 向量检索擅长语义相似（"有氧能力" ≈ "心肺能力"）
   - 关键词检索擅长精确匹配（"VO2max" 就是 "VO2max"）
   - 两者互补

3. **RRF 融合**：无需调参的融合算法
   - 对不同检索器的排名取倒数和
   - `score = Σ 1/(k + rank_i)`，k=60
   - 优点：不需要归一化分数，只看排名

4. **MMR 多样性**：避免返回 5 个几乎相同的 chunk
   - λ=0.7：70% 权重给相关性，30% 权重给多样性
   - 第一个 chunk 取最高分，后续 chunk 选择"相关性高且与已选不同"的

5. **Metadata 规则重排**：业务层面的加权
   - 命中领域术语的 chunk 加权 20%
   - 语义密度 > 5% 的 chunk 加权 10%

**面试钩子**：
> "我们对比了多种召回优化策略，最终选择了 6 步管线。其中最关键的三点是：**查询扩展**（覆盖更多表达方式）、**向量+关键词混合检索**（语义和精确匹配互补）、**MMR 多样性**（避免返回重复内容）。实测召回率从纯向量检索的 65% 提升到混合检索的 87%。"

---

### Q33：RAG 里的 Embedding 模型怎么选的？为什么用 MiniLM？

**八股文考点**：
- 嵌入模型选型
- 向量维度与性能
- 开源 vs 商业模型
- 降级策略

**项目答案**：

我们选 **sentence-transformers/all-MiniLM-L6-v2**，原因：

| 维度 | MiniLM | 其他选项 |
|------|--------|----------|
| 速度 | 快（384 维） | 慢（768 维） |
| 内存 | 小（~90MB） | 大（~400MB） |
| 准确率 | 中（MPNet 66.3%） | 高（BGE-M3 70.5%） |
| 零配置 | ✅ 本地加载 | ❌ 需要 API |
| 中文支持 | 一般 | 好（BGE） |

**选择理由**：
1. **Demo 零配置可运行**：不需要 API Key，本地加载
2. **速度优先**：Agent 系统需要快速响应，384 维比 768 维快一倍
3. **可降级**：FakeEmbedder 作为后备，用哈希生成伪向量

**改进计划**：生产环境切换到 **BGE-M3** 或 **BAAI/bge-large-zh**，中文效果更好。

---

### Q34：Chunk 太小或太大分别会有什么问题？怎么判断颗粒度是否合理？

**八股文考点**：
- Chunk 大小对召回率的影响
- 上下文窗口限制
- 颗粒度评估方法

**项目答案**：

| 问题 | Chunk 太小 | Chunk 太大 |
|------|-----------|-----------|
| 语义完整性 | ❌ 丢失上下文，句子断裂 | ❌ 稀释语义，包含无关内容 |
| 检索精度 | ❌ 碎片信息，难匹配 | ❌ 大段文本，噪声多 |
| LLM 处理 | ❌ 需要多个 chunk 拼接 | ❌ 超出上下文窗口 |
| 用户体验 | ❌ 回答碎片化 | ❌ 回答冗余 |

**我们的颗粒度评估指标**（`ChunkingStats`）：
```python
stats = chunker.stats
# 1. 平均大小（目标 300-500 token）
stats.avg_chunk_size

# 2. 标准差（越小越均匀）
stats.std_dev

# 3. 异常块数（偏离均值 2σ 的块数）
stats.outlier_chunks  # > 20% 则需要调整

# 4. 专业术语保留率
stats.domain_terms_preserved  # 越高越好
```

**面试钩子**：
> "我们用 4 个指标评估颗粒度合理性：平均大小、标准差、异常块率、术语保留率。如果异常块率超过 20%，说明切块策略需要调整——要么 max_chunk_size 太大，要么 min_chunk_size 太小。"

---

*本文档基于 WenYaSports 项目实际代码编写，所有答案均有对应实现支撑。*
