# WenYaSports 面试题库

> 基于项目十大核心亮点，覆盖 Agent 开发、LLM 编排、MCP 生态、记忆系统、工程架构等方向。  
> 每道题包含：**面试题 → 八股文考点 → 项目实战答案**

---

## 一、Agent Runtime Harness 架构

### Q1：什么是 Agent Harness？它和普通的 Agent 框架（如 LangChain）有什么区别？

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

*本文档基于 WenYaSports 项目实际代码编写，所有答案均有对应实现支撑。*
