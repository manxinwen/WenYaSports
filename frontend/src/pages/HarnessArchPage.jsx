import { useState, useEffect } from 'react';

const API_BASE = 'http://localhost:8000/api';

const AGENT_DATA = [
  {
    id: 'parser',
    name: 'FIT Parser',
    icon: '🔧',
    color: '#00d4ff',
    gradient: 'linear-gradient(135deg, #00d4ff 0%, #0066ff 100%)',
    capabilities: ['fit_parsing', 'data_extraction', 'metadata_parsing'],
    status: 'idle',
    execution_count: 156,
    description: '专业解析 Garmin FIT 文件',
    metrics: { records_parsed: '47,320', avg_time_ms: 450 },
  },
  {
    id: 'feature_extractor',
    name: 'Feature Extractor',
    icon: '📊',
    color: '#ff6a00',
    gradient: 'linear-gradient(135deg, #ff6a00 0%, #ff3366 100%)',
    capabilities: ['feature_engineering', 'statistics', 'intensity_distribution'],
    status: 'idle',
    execution_count: 142,
    description: '提取训练指标与统计数据',
    metrics: { features_computed: '12,480', avg_time_ms: 320 },
  },
  {
    id: 'memory',
    name: 'Memory Manager',
    icon: '🧠',
    color: '#c6ff3d',
    gradient: 'linear-gradient(135deg, #c6ff3d 0%, #33cc99 100%)',
    capabilities: ['user_profile', 'context_retrieval', 'memory_update'],
    status: 'idle',
    execution_count: 284,
    description: '管理用户画像与训练历史',
    metrics: { profiles_managed: 47, sessions_cached: 128 },
  },
  {
    id: 'recommender',
    name: 'Recommendation Engine',
    icon: '💡',
    color: '#a855f7',
    gradient: 'linear-gradient(135deg, #a855f7 0%, #ec4899 100%)',
    capabilities: ['training_advice', 'rule_engine', 'llm_generation'],
    status: 'idle',
    execution_count: 98,
    description: '生成个性化训练建议',
    metrics: { rules_applied: 1240, llm_calls: 567 },
  },
  {
    id: 'react',
    name: 'ReAct Agent',
    icon: '⚡',
    color: '#ffd700',
    gradient: 'linear-gradient(135deg, #ffd700 0%, #ff6a00 100%)',
    capabilities: ['tool_calling', 'reasoning', 'multi_step_planning'],
    status: 'idle',
    execution_count: 67,
    description: '思考-行动-观察循环推理',
    metrics: { tool_calls: 342, avg_iterations: 3.2 },
  },
];

const HARNESS_COMPONENTS = [
  {
    id: 'registry',
    name: 'AgentRegistry',
    icon: '📋',
    description: '管理 Agent 生命周期',
    stats: { registered: 5, active: 5, total_capabilities: 12 },
    color: '#00d4ff',
  },
  {
    id: 'blackboard',
    name: 'Blackboard',
    icon: '📝',
    description: 'Agent 间共享状态',
    stats: { namespaces: 8, keys_stored: 47, reads_today: 1284 },
    color: '#c6ff3d',
  },
  {
    id: 'message_bus',
    name: 'MessageBus',
    icon: '📡',
    description: 'Agent 间通信总线',
    stats: { messages_sent: 3420, subscribers: 5, broadcasts: 892 },
    color: '#ff6a00',
  },
  {
    id: 'governance',
    name: 'GovernanceEngine',
    icon: '⚖️',
    description: '治理与预算控制',
    stats: { rules_enforced: 15, budgets_tracked: 5, violations: 0 },
    color: '#a855f7',
  },
];

const WORKFLOW_EXAMPLES = [
  {
    id: 'analysis',
    name: '活动分析工作流',
    steps: ['parser', 'feature_extractor', 'memory', 'recommender', 'memory'],
    description: '解析 → 特征提取 → 加载上下文 → 生成建议 → 更新记忆',
    color: '#00d4ff',
  },
  {
    id: 'chat',
    name: 'AI 对话工作流',
    steps: ['memory', 'react', 'memory'],
    description: '加载上下文 → ReAct 推理 → 更新记忆',
    color: '#ff6a00',
  },
  {
    id: 'orchestrate',
    name: '动态编排',
    steps: ['dynamic'],
    description: 'Agent 自主发现能力并协作完成目标',
    color: '#c6ff3d',
  },
];

function HarnessArchPage() {
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [activeWorkflow, setActiveWorkflow] = useState('analysis');
  const [stepIndex, setStepIndex] = useState(0);
  const [animating, setAnimating] = useState(false);
  const [pulsePhase, setPulsePhase] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setPulsePhase(p => (p + 1) % 4);
    }, 1500);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (activeWorkflow === 'orchestrate') return;
    setStepIndex(0);
    setAnimating(true);
    const steps = WORKFLOW_EXAMPLES.find(w => w.id === activeWorkflow)?.steps || [];
    if (steps.length <= 1) {
      setAnimating(false);
      return;
    }
    let i = 0;
    const timer = setInterval(() => {
      i++;
      if (i >= steps.length) {
        clearInterval(timer);
        setAnimating(false);
        return;
      }
      setStepIndex(i);
    }, 1200);
    return () => clearInterval(timer);
  }, [activeWorkflow]);

  const getWorkflowSteps = () => {
    const wf = WORKFLOW_EXAMPLES.find(w => w.id === activeWorkflow);
    if (!wf || activeWorkflow === 'orchestrate') return ['dynamic'];
    return wf.steps;
  };

  const renderAgentNode = (agent, index) => {
    const isActive = activeWorkflow !== 'orchestrate' && index <= stepIndex;
    const isCurrent = activeWorkflow !== 'orchestrate' && index === stepIndex;

    return (
      <div
        key={`${agent.id}-${index}`}
        className="agent-node"
        style={{
          '--agent-color': agent.color,
          animationDelay: `${index * 0.15}s`,
        }}
        onClick={() => setSelectedAgent(agent)}
      >
        <div
          className={`agent-card ${isActive ? 'active' : ''} ${isCurrent ? 'current' : ''}`}
          style={{
            borderColor: isActive ? agent.color : 'rgba(255,255,255,0.08)',
            boxShadow: isCurrent ? `0 0 30px ${agent.color}40` : 'none',
          }}
        >
          <div className="agent-card-icon" style={{ background: agent.gradient }}>
            {agent.icon}
          </div>
          <div className="agent-card-info">
            <div className="agent-card-name">{agent.name}</div>
            <div className="agent-card-id">{agent.id}</div>
          </div>
          {isCurrent && (
            <div className="agent-card-pulse" style={{ borderColor: agent.color }} />
          )}
        </div>
        {index < getWorkflowSteps().length - 1 && (
          <div
            className="flow-arrow"
            style={{
              opacity: index < stepIndex ? 1 : 0.3,
              color: agent.color,
            }}
          >
            <svg width="24" height="12" viewBox="0 0 24 12">
              <path
                d="M0 6 L18 6 M14 2 L18 6 L14 10"
                stroke="currentColor"
                strokeWidth="2"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="page harness-page">
      <div className="page-header fade-in">
        <div className="page-title-block">
          <div className="page-eyebrow">// HARNESS ARCHITECTURE</div>
          <h1 className="page-title">多智能体 Harness 架构</h1>
          <div className="page-subtitle">5 个 Agent · 消息总线 · 共享黑板 · 治理引擎</div>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <div className="badge-live">ACTIVE</div>
          <div className="panel-tag" style={{ padding: '6px 14px' }}>
            <span style={{ color: 'var(--cyan)' }}>5</span> AGENTS
          </div>
        </div>
      </div>

      {/* Architecture Diagram */}
      <div className="arch-section fade-in-delay-1">
        <div className="arch-diagram">
          <div className="arch-harness">
            <div className="arch-harness-title">
              <span className="pulse-dot" />
              HARNESS ORCHESTRATOR
            </div>
            <div className="arch-harness-grid">
              {HARNESS_COMPONENTS.map((comp, i) => (
                <div
                  key={comp.id}
                  className="arch-component"
                  style={{
                    '--comp-color': comp.color,
                    animationDelay: `${i * 0.1}s`,
                  }}
                >
                  <div className="comp-icon">{comp.icon}</div>
                  <div className="comp-name">{comp.name}</div>
                  <div className="comp-desc">{comp.description}</div>
                  <div className="comp-stats">
                    {Object.entries(comp.stats).map(([key, val]) => (
                      <div key={key} className="comp-stat">
                        <span className="stat-val">{val}</span>
                        <span className="stat-key">{key}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="arch-connection">
            <svg width="2" height="40" style={{ overflow: 'visible' }}>
              <line
                x1="1" y1="0" x2="1" y2="40"
                stroke="url(#connectionGradient)"
                strokeWidth="2"
                strokeDasharray="4 4"
                className="flow-line"
              />
              <defs>
                <linearGradient id="connectionGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00d4ff" />
                  <stop offset="50%" stopColor="#ff6a00" />
                  <stop offset="100%" stopColor="#c6ff3d" />
                </linearGradient>
              </defs>
            </svg>
          </div>

          <div className="arch-agents">
            <div className="arch-agents-title">AGENT POOL</div>
            <div className="arch-agents-grid">
              {AGENT_DATA.map((agent) => (
                <div
                  key={agent.id}
                  className={`agent-pulse ${selectedAgent?.id === agent.id ? 'selected' : ''}`}
                  style={{
                    '--agent-color': agent.color,
                    '--agent-gradient': agent.gradient,
                  }}
                  onClick={() => setSelectedAgent(agent)}
                >
                  <div className="agent-orb" />
                  <div className="agent-info-mini">
                    <span className="agent-name-mini">{agent.icon} {agent.name}</span>
                    <span className="agent-id-mini">{agent.execution_count} executions</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Agent Details & Workflow Simulation */}
      <div className="arch-content fade-in-delay-2">
        <div className="arch-left">
          <div className="panel">
            <div className="panel-header">
              <div className="panel-title">// AGENT DETAIL</div>
              {selectedAgent && (
                <div className="panel-tag">{selectedAgent.id.toUpperCase()}</div>
              )}
            </div>
            {selectedAgent ? (
              <div className="agent-detail" style={{ '--accent': selectedAgent.color }}>
                <div className="detail-header">
                  <div
                    className="detail-icon"
                    style={{ background: selectedAgent.gradient }}
                  >
                    {selectedAgent.icon}
                  </div>
                  <div>
                    <h3 className="detail-name">{selectedAgent.name}</h3>
                    <span className="detail-id">{selectedAgent.id}</span>
                  </div>
                </div>
                <p className="detail-desc">{selectedAgent.description}</p>

                <div className="detail-section">
                  <div className="detail-label">CAPABILITIES</div>
                  <div className="detail-caps">
                    {selectedAgent.capabilities.map(cap => (
                      <span key={cap} className="cap-chip">{cap}</span>
                    ))}
                  </div>
                </div>

                <div className="detail-section">
                  <div className="detail-label">METRICS</div>
                  <div className="detail-metrics">
                    {Object.entries(selectedAgent.metrics).map(([key, val]) => (
                      <div key={key} className="detail-metric">
                        <span className="metric-val">{val}</span>
                        <span className="metric-key">{key.replace(/_/g, ' ')}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="detail-section">
                  <div className="detail-label">STATUS</div>
                  <div className="detail-status">
                    <span className="status-dot" />
                    <span>IDLE · Last executed 2min ago</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="agent-empty">
                <div className="empty-icon">👆</div>
                <div>点击上方 Agent 查看详情</div>
              </div>
            )}
          </div>
        </div>

        <div className="arch-right">
          <div className="panel">
            <div className="panel-header">
              <div className="panel-title">// WORKFLOW SIMULATION</div>
              <div className="panel-tag">
                {animating ? 'RUNNING' : 'IDLE'}
              </div>
            </div>

            <div className="workflow-tabs">
              {WORKFLOW_EXAMPLES.map(wf => (
                <button
                  key={wf.id}
                  className={`wf-tab ${activeWorkflow === wf.id ? 'active' : ''}`}
                  style={{ '--wf-color': wf.color }}
                  onClick={() => setActiveWorkflow(wf.id)}
                  disabled={animating}
                >
                  {wf.name}
                </button>
              ))}
            </div>

            <div className="workflow-visualization">
              {activeWorkflow === 'orchestrate' ? (
                <div className="orchestrate-view">
                  <div className="orchestrate-center">
                    <div className="orchestrate-core">
                      <span>🤖</span>
                      <span className="orchestrate-label">DYNAMIC ORCHESTRATION</span>
                    </div>
                  </div>
                  <div className="orchestrate-ring">
                    {AGENT_DATA.map((agent, i) => (
                      <div
                        key={agent.id}
                        className="orchestrate-node"
                        style={{
                          '--node-color': agent.color,
                          transform: `rotate(${i * 72}deg) translateY(80px) rotate(-${i * 72}deg)`,
                          animationDelay: `${i * 0.2}s`,
                        }}
                      >
                        <div className="onode-icon" style={{ background: agent.gradient }}>
                          {agent.icon}
                        </div>
                        <span className="onode-label">{agent.name}</span>
                      </div>
                    ))}
                  </div>
                  <div className="orchestrate-desc">
                    <p>Agent 自主发现能力并动态协作</p>
                    <p>无需预定义工作流路径</p>
                  </div>
                </div>
              ) : (
                <div className="workflow-steps">
                  {getWorkflowSteps().map((stepId, i) => {
                    const agent = AGENT_DATA.find(a => a.id === stepId);
                    if (!agent) return null;
                    return renderAgentNode(agent, i);
                  })}
                </div>
              )}
            </div>

            <div className="workflow-info">
              <div className="wf-desc">
                {WORKFLOW_EXAMPLES.find(w => w.id === activeWorkflow)?.description}
              </div>
              {activeWorkflow !== 'orchestrate' && (
                <div className="wf-progress">
                  <div
                    className="progress-bar"
                    style={{
                      width: `${(stepIndex / Math.max(getWorkflowSteps().length - 1, 1)) * 100}%`,
                      background: 'var(--gradient-flame)',
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Architecture Features */}
      <div className="arch-features fade-in-delay-2">
        <div className="feature-card">
          <div className="feature-icon" style={{ color: '#00d4ff' }}>📡</div>
          <div className="feature-title">消息总线</div>
          <div className="feature-desc">支持点对点、广播和请求-响应三种通信模式，Agent 可动态发现和调用其他 Agent 的能力</div>
        </div>
        <div className="feature-card">
          <div className="feature-icon" style={{ color: '#c6ff3d' }}>📝</div>
          <div className="feature-title">共享黑板</div>
          <div className="feature-desc">多 Agent 间的共享内存，支持命名空间隔离、版本跟踪和订阅通知，实现数据流转</div>
        </div>
        <div className="feature-card">
          <div className="feature-icon" style={{ color: '#ff6a00' }}>⚖️</div>
          <div className="feature-title">治理引擎</div>
          <div className="feature-desc">规则执行、预算控制和安全约束，确保 Agent 操作在安全边界内运行</div>
        </div>
        <div className="feature-card">
          <div className="feature-icon" style={{ color: '#a855f7' }}>🔄</div>
          <div className="feature-title">动态编排</div>
          <div className="feature-desc">支持固定工作流和动态编排两种模式，Agent 可自主决策最佳协作路径</div>
        </div>
      </div>
    </div>
  );
}

export default HarnessArchPage;
