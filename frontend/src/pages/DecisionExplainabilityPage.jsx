import { useState } from 'react';

const DECISION_CHAIN = [
  {
    id: 'root_001',
    type: 'plan_generation',
    typeLabel: '计划生成',
    icon: '📋',
    color: '#00d4ff',
    title: '生成执行计划',
    context: '目标: 分析运动数据并给出训练建议',
    chosen: '4-step pipeline',
    reasoning: 'LLM 分析目标后，生成解析→特征→记忆→推荐四阶段流水线',
    confidence: 0.92,
    children: ['sel_001'],
    timestamp: '10:23:01',
  },
  {
    id: 'sel_001',
    type: 'agent_selection',
    typeLabel: 'Agent 选择',
    icon: '🤝',
    color: '#ff6a00',
    title: '选择数据解析 Agent',
    context: '步骤 1: 数据解析',
    chosen: 'parser_agent',
    alternatives: ['reaact_agent', 'feature_extractor_agent'],
    scores: { parser_agent: 0.95, reaact_agent: 0.72, feature_extractor_agent: 0.48 },
    reasoning: '通过协商协议，parser 在解析能力和历史质量上均胜出',
    negotiation: true,
    confidence: 0.88,
    children: ['sel_002'],
    timestamp: '10:23:02',
  },
  {
    id: 'sel_002',
    type: 'agent_selection',
    typeLabel: 'Agent 选择',
    icon: '🤝',
    color: '#ff6a00',
    title: '协商选择特征提取 Agent',
    context: '步骤 2: 特征提取',
    chosen: 'feature_extractor_agent',
    alternatives: ['reaact_agent'],
    scores: { feature_extractor_agent: 0.91, reaact_agent: 0.65 },
    reasoning: '协商结果: 专业特征提取 Agent 得分更高 (0.91 vs 0.65)',
    negotiation: true,
    confidence: 0.85,
    children: ['qual_001'],
    timestamp: '10:23:04',
  },
  {
    id: 'qual_001',
    type: 'quality_assessment',
    typeLabel: '质量评估',
    icon: '✅',
    color: '#c6ff3d',
    title: '评估产出质量',
    context: '最终产出: 训练建议报告',
    chosen: 'quality_pass',
    scores: { accuracy: 0.92, completeness: 0.88, operability: 0.85 },
    reasoning: '三维度评分均在阈值以上，产出质量合格',
    confidence: 0.90,
    children: [],
    timestamp: '10:23:08',
  },
];

const NEGOTIATION_SCENARIOS = [
  {
    id: 'neg_001',
    topic: '数据解析任务分配',
    type: 'capability_dispute',
    winner: 'parser_agent',
    consensusType: 'hybrid',
    rounds: 2,
    candidates: [
      { id: 'parser_agent', score: 0.95, confidence: 0.92, quality: 0.93 },
      { id: 'reaact_agent', score: 0.72, confidence: 0.68, quality: 0.70 },
      { id: 'feature_extractor_agent', score: 0.48, confidence: 0.45, quality: 0.52 },
    ],
    explanation: 'parser_agent 在综合评分（70%）和投票权重（30%）中均胜出',
  },
  {
    id: 'neg_002',
    topic: '特征提取能力争议',
    type: 'capability_dispute',
    winner: 'feature_extractor_agent',
    consensusType: 'score_based',
    rounds: 1,
    candidates: [
      { id: 'feature_extractor_agent', score: 0.91, confidence: 0.88, quality: 0.90 },
      { id: 'reaact_agent', score: 0.65, confidence: 0.60, quality: 0.68 },
    ],
    explanation: 'feature_extractor_agent 综合得分 0.91，远超第二名 reaact_agent (0.65)',
  },
  {
    id: 'neg_003',
    topic: '记忆管理策略选择',
    type: 'task_delegation',
    winner: 'memory_agent',
    consensusType: 'unanimous',
    rounds: 1,
    candidates: [
      { id: 'memory_agent', score: 0.96, confidence: 0.95, quality: 0.94 },
      { id: 'coordinator_agent', score: 0.78, confidence: 0.75, quality: 0.80 },
    ],
    explanation: '所有投票者一致选择 memory_agent，达成一致同意',
  },
];

const UNCERTAINTY_REPORTS = [
  {
    id: 'unc_001',
    conclusion: '用户本周训练强度适中，建议保持当前训练计划',
    confidence: 0.82,
    level: 'medium',
    evidenceStrength: 0.78,
    dataQuality: 0.85,
    keyUncertainties: ['样本量仅 3 天', '未考虑天气因素'],
    recommendations: ['建议结合更长时间周期分析'],
    caveats: ['结论基于有限数据，建议作为参考而非定论'],
  },
  {
    id: 'unc_002',
    conclusion: '心率数据异常可能由运动强度突变引起',
    confidence: 0.91,
    level: 'low',
    evidenceStrength: 0.88,
    dataQuality: 0.94,
    keyUncertainties: [],
    recommendations: ['可作为高可信度结论'],
    caveats: [],
  },
  {
    id: 'unc_003',
    conclusion: '用户 VO2max 可能高于平均水平',
    confidence: 0.52,
    level: 'high',
    evidenceStrength: 0.45,
    dataQuality: 0.48,
    keyUncertainties: ['直接测量缺失', '使用估算公式', '个体差异大'],
    recommendations: ['建议进行专业 VO2max 测试', '增加运动数据采集'],
    caveats: ['此结论可信度较低，仅作参考', '建议通过专业检测验证'],
  },
];

const NEGOTIATION_TYPES = {
  capability_dispute: { label: '能力争议', color: '#ff6a00' },
  task_delegation: { label: '任务委派', color: '#00d4ff' },
  conflict_resolution: { label: '冲突解决', color: '#a855f7' },
  consensus_voting: { label: '共识投票', color: '#c6ff3d' },
};

const UNCERTAINTY_LEVELS = {
  low: { label: '低不确定性', color: '#c6ff3d', bg: 'rgba(198, 255, 61, 0.1)' },
  medium: { label: '中等不确定性', color: '#ffd700', bg: 'rgba(255, 215, 0, 0.1)' },
  high: { label: '高不确定性', color: '#ff6a00', bg: 'rgba(255, 106, 0, 0.1)' },
  very_high: { label: '极高不确定性', color: '#ff3333', bg: 'rgba(255, 51, 51, 0.1)' },
};

function DecisionExplainabilityPage() {
  const [selectedDecision, setSelectedDecision] = useState(null);
  const [activeTab, setActiveTab] = useState('explainability');
  const [selectedNegotiation, setSelectedNegotiation] = useState(null);
  const [selectedUncertainty, setSelectedUncertainty] = useState(null);

  const renderDecisionNode = (decision, depth = 0) => {
    const isSelected = selectedDecision?.id === decision.id;
    const typeIcon = decision.icon;
    const color = decision.color;

    return (
      <div key={decision.id} style={{ marginLeft: depth * 24 }}>
        <div
          className={`decision-node ${isSelected ? 'selected' : ''}`}
          style={{
            '--node-color': color,
            borderColor: isSelected ? color : 'rgba(255,255,255,0.1)',
            background: isSelected ? `${color}15` : 'rgba(255,255,255,0.03)',
          }}
          onClick={() => setSelectedDecision(decision)}
        >
          <div className="decision-node-header">
            <span className="decision-node-icon">{typeIcon}</span>
            <span className="decision-node-type" style={{ color }}>
              {decision.typeLabel}
            </span>
            <span className="decision-node-confidence">
              置信度 {(decision.confidence * 100).toFixed(0)}%
            </span>
            <span className="decision-node-time">{decision.timestamp}</span>
          </div>
          <div className="decision-node-title">{decision.title}</div>
          {decision.negotiation && (
            <div className="negotiation-badge">
              🤝 经协商协议
            </div>
          )}
        </div>
        {decision.children && decision.children.length > 0 && (
          <div className="decision-children">
            {decision.children.map(childId => {
              const child = DECISION_CHAIN.find(d => d.id === childId);
              return child ? renderDecisionNode(child, depth + 1) : null;
            })}
          </div>
        )}
      </div>
    );
  };

  const renderDecisionDetail = () => {
    if (!selectedDecision) {
      return (
        <div className="empty-state">
          <div className="empty-icon">📖</div>
          <div className="empty-title">点击左侧决策节点</div>
          <div className="empty-desc">查看每个决策的详细解释、评分对比和备选方案分析</div>
        </div>
      );
    }

    const d = selectedDecision;
    return (
      <div className="decision-detail">
        <div className="detail-header-section">
          <div className="detail-type-badge" style={{ background: `${d.color}20`, color: d.color }}>
            {d.icon} {d.typeLabel}
          </div>
          <h2 className="detail-title">{d.title}</h2>
          <div className="detail-meta">
            <span>🕐 {d.timestamp}</span>
            <span>📊 置信度 {(d.confidence * 100).toFixed(0)}%</span>
          </div>
        </div>

        <div className="detail-section-block">
          <div className="section-label">决策上下文</div>
          <div className="section-content context-box">{d.context}</div>
        </div>

        <div className="detail-section-block">
          <div className="section-label">选择结果</div>
          <div className="chosen-option" style={{ borderColor: d.color }}>
            <span className="chosen-label">✅ 选择</span>
            <span className="chosen-value">{d.chosen}</span>
          </div>
        </div>

        {d.scores && Object.keys(d.scores).length > 0 && (
          <div className="detail-section-block">
            <div className="section-label">评分对比</div>
            <div className="scores-comparison">
              {Object.entries(d.scores)
                .sort((a, b) => b[1] - a[1])
                .map(([option, score]) => (
                  <div key={option} className="score-bar-row">
                    <span className="score-name">
                      {option}
                      {option === d.chosen && <span className="chosen-tag"> ← 选择</span>}
                    </span>
                    <div className="score-bar-bg">
                      <div
                        className="score-bar-fill"
                        style={{
                          width: `${score * 100}%`,
                          background: option === d.chosen ? d.color : 'rgba(255,255,255,0.2)',
                        }}
                      />
                    </div>
                    <span className="score-value">{score.toFixed(2)}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {d.alternatives && d.alternatives.length > 0 && (
          <div className="detail-section-block">
            <div className="section-label">被否决的备选方案</div>
            <div className="alternatives-list">
              {d.alternatives.map(alt => (
                <div key={alt} className="alternative-item">
                  <span className="alt-name">{alt}</span>
                  <span className="alt-reason">得分低于 {d.chosen}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="detail-section-block">
          <div className="section-label">决策理由</div>
          <div className="reasoning-box">{d.reasoning}</div>
        </div>

        {d.negotiation && (
          <div className="negotiation-notice">
            <span className="notice-icon">🤝</span>
            <span>此决策通过 Agent 协商协议达成，支持多 Agent 能力争议解决</span>
          </div>
        )}
      </div>
    );
  };

  const renderNegotiationDetail = () => {
    if (!selectedNegotiation) {
      return (
        <div className="empty-state">
          <div className="empty-icon">🤝</div>
          <div className="empty-title">选择一个协商场景</div>
          <div className="empty-desc">查看多 Agent 如何通过协商协议解决能力争议</div>
        </div>
      );
    }

    const n = selectedNegotiation;
    const winnerType = NEGOTIATION_TYPES[n.type] || { label: n.type, color: '#fff' };

    return (
      <div className="negotiation-detail">
        <div className="detail-header-section">
          <div
            className="detail-type-badge"
            style={{ background: `${winnerType.color}20`, color: winnerType.color }}
          >
            🤝 {winnerType.label}
          </div>
          <h2 className="detail-title">{n.topic}</h2>
          <div className="detail-meta">
            <span>📊 共识方式: {n.consensusType}</span>
            <span>🔄 轮次: {n.rounds}</span>
          </div>
        </div>

        <div className="detail-section-block">
          <div className="section-label">协商结果</div>
          <div className="negotiation-result">
            <div className="winner-announcement">
              <span className="winner-trophy">🏆</span>
              <span className="winner-name">{n.winner}</span>
              <span className="winner-label">胜出</span>
            </div>
            <div className="explanation-box">{n.explanation}</div>
          </div>
        </div>

        <div className="detail-section-block">
          <div className="section-label">候选 Agent 提案对比</div>
          <div className="proposals-comparison">
            {n.candidates
              .sort((a, b) => b.score - a.score)
              .map((c, i) => (
                <div
                  key={c.id}
                  className={`proposal-card ${c.id === n.winner ? 'winner' : ''}`}
                  style={{ '--rank-color': i === 0 ? '#c6ff3d' : '#ff6a00' }}
                >
                  <div className="proposal-rank">#{i + 1}</div>
                  <div className="proposal-info">
                    <div className="proposal-id">{c.id}</div>
                    <div className="proposal-scores">
                      <div className="mini-stat">
                        <span className="mini-label">综合</span>
                        <span className="mini-value">{c.score.toFixed(2)}</span>
                      </div>
                      <div className="mini-stat">
                        <span className="mini-label">信心</span>
                        <span className="mini-value">{(c.confidence * 100).toFixed(0)}%</span>
                      </div>
                      <div className="mini-stat">
                        <span className="mini-label">质量</span>
                        <span className="mini-value">{(c.quality * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  </div>
                  {c.id === n.winner && <div className="winner-badge">WINNER</div>}
                </div>
              ))}
          </div>
        </div>

        <div className="detail-section-block">
          <div className="section-label">协商协议说明</div>
          <div className="protocol-info">
            <div className="protocol-step">
              <span className="step-num">1</span>
              <span>候选 Agent 提交能力提案（信心分 + 质量分 + 成本分）</span>
            </div>
            <div className="protocol-step">
              <span className="step-num">2</span>
              <span>通过 hybrid 策略计算综合评分（70%评分 + 30%投票）</span>
            </div>
            <div className="protocol-step">
              <span className="step-num">3</span>
              <span>得分最高者胜出；分差过小时自动进入新一轮协商</span>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderUncertaintyDetail = () => {
    if (!selectedUncertainty) {
      return (
        <div className="empty-state">
          <div className="empty-icon">📊</div>
          <div className="empty-title">选择一个不确定性报告</div>
          <div className="empty-desc">查看 Agent 如何量化自身结论的不确定性</div>
        </div>
      );
    }

    const u = selectedUncertainty;
    const level = UNCERTAINTY_LEVELS[u.level] || UNCERTAINTY_LEVELS.medium;

    return (
      <div className="uncertainty-detail">
        <div className="detail-header-section">
          <div
            className="detail-type-badge"
            style={{ background: level.bg, color: level.color }}
          >
            📊 {level.label}
          </div>
          <h2 className="detail-title">不确定性评估报告</h2>
        </div>

        <div className="detail-section-block">
          <div className="section-label">评估结论</div>
          <div className="conclusion-box">{u.conclusion}</div>
        </div>

        <div className="detail-section-block">
          <div className="section-label">量化指标</div>
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-ring" style={{ '--progress': `${u.confidence * 100}%`, '--ring-color': level.color }}>
                <span className="metric-ring-value">{(u.confidence * 100).toFixed(0)}%</span>
              </div>
              <div className="metric-name">置信度</div>
            </div>
            <div className="metric-card">
              <div className="metric-bar" style={{ '--bar-width': `${u.evidenceStrength * 100}%`, '--bar-color': '#00d4ff' }} />
              <div className="metric-name">证据强度 {(u.evidenceStrength * 100).toFixed(0)}%</div>
            </div>
            <div className="metric-card">
              <div className="metric-bar" style={{ '--bar-width': `${u.dataQuality * 100}%`, '--bar-color': '#c6ff3d' }} />
              <div className="metric-name">数据质量 {(u.dataQuality * 100).toFixed(0)}%</div>
            </div>
          </div>
        </div>

        {u.keyUncertainties.length > 0 && (
          <div className="detail-section-block">
            <div className="section-label">关键不确定性来源</div>
            <div className="uncertainty-list">
              {u.keyUncertainties.map((unc, i) => (
                <div key={i} className="uncertainty-item">
                  <span className="unc-icon">⚠️</span>
                  <span>{unc}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {u.recommendations.length > 0 && (
          <div className="detail-section-block">
            <div className="section-label">改进建议</div>
            <div className="recommendations-list">
              {u.recommendations.map((rec, i) => (
                <div key={i} className="recommendation-item">
                  <span className="rec-icon">💡</span>
                  <span>{rec}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {u.caveats.length > 0 && (
          <div className="detail-section-block">
            <div className="section-label">使用注意事项</div>
            <div className="caveats-list">
              {u.caveats.map((cav, i) => (
                <div key={i} className="caveat-item">
                  <span className="cav-icon">🔍</span>
                  <span>{cav}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="page explainability-page">
      <div className="page-header fade-in">
        <div className="page-title-block">
          <div className="page-eyebrow">// AI DECISION EXPLAINABILITY</div>
          <h1 className="page-title">决策可解释性与 Agent 协商</h1>
          <div className="page-subtitle">
            每个 AI 决策都有迹可循 · 多 Agent 协商解决能力争议 · 不确定性量化声明
          </div>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <div className="badge-live">TRANSPARENT</div>
          <div className="panel-tag" style={{ padding: '6px 14px' }}>
            <span style={{ color: 'var(--cyan)' }}>{DECISION_CHAIN.length}</span> DECISIONS LOGGED
          </div>
        </div>
      </div>

      {/* Feature Tabs */}
      <div className="explain-tabs fade-in-delay-1">
        <button
          className={`explain-tab ${activeTab === 'explainability' ? 'active' : ''}`}
          onClick={() => setActiveTab('explainability')}
        >
          📖 决策解释链
        </button>
        <button
          className={`explain-tab ${activeTab === 'negotiation' ? 'active' : ''}`}
          onClick={() => setActiveTab('negotiation')}
        >
          🤝 Agent 协商协议
        </button>
        <button
          className={`explain-tab ${activeTab === 'uncertainty' ? 'active' : ''}`}
          onClick={() => setActiveTab('uncertainty')}
        >
          📊 不确定性量化
        </button>
      </div>

      <div className="explain-content fade-in-delay-2">
        {activeTab === 'explainability' && (
          <>
            <div className="explain-left">
              <div className="panel">
                <div className="panel-header">
                  <div className="panel-title">// DECISION CHAIN</div>
                  <div className="panel-tag">
                    {selectedDecision ? '1 SELECTED' : 'CLICK TO EXPLORE'}
                  </div>
                </div>
                <div className="decision-tree">
                  {DECISION_CHAIN.map(decision => renderDecisionNode(decision, 0))}
                </div>
              </div>

              <div className="panel" style={{ marginTop: 16 }}>
                <div className="panel-header">
                  <div className="panel-title">// CHAIN STATISTICS</div>
                </div>
                <div className="stats-row">
                  <div className="stat-box">
                    <span className="stat-num">{DECISION_CHAIN.length}</span>
                    <span className="stat-desc">总决策数</span>
                  </div>
                  <div className="stat-box">
                    <span className="stat-num">2</span>
                    <span className="stat-desc">协商决策</span>
                  </div>
                  <div className="stat-box">
                    <span className="stat-num">4</span>
                    <span className="stat-desc">决策层数</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="explain-right">
              <div className="panel">
                <div className="panel-header">
                  <div className="panel-title">// DECISION DETAIL</div>
                </div>
                {renderDecisionDetail()}
              </div>
            </div>
          </>
        )}

        {activeTab === 'negotiation' && (
          <>
            <div className="explain-left">
              <div className="panel">
                <div className="panel-header">
                  <div className="panel-title">// NEGOTIATION SCENARIOS</div>
                </div>
                <div className="negotiation-list">
                  {NEGOTIATION_SCENARIOS.map(n => (
                    <div
                      key={n.id}
                      className={`negotiation-card ${selectedNegotiation?.id === n.id ? 'selected' : ''}`}
                      onClick={() => setSelectedNegotiation(n)}
                    >
                      <div className="neg-card-header">
                        <span className="neg-type" style={{ color: (NEGOTIATION_TYPES[n.type] || {}).color }}>
                          {(NEGOTIATION_TYPES[n.type] || {}).label}
                        </span>
                        <span className="neg-consensus">{n.consensusType}</span>
                      </div>
                      <div className="neg-topic">{n.topic}</div>
                      <div className="neg-winner">
                        🏆 <span>{n.winner}</span>
                      </div>
                      <div className="neg-rounds">{n.rounds} 轮 · {n.candidates.length} 候选</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="explain-right">
              <div className="panel">
                <div className="panel-header">
                  <div className="panel-title">// NEGOTIATION DETAIL</div>
                </div>
                {renderNegotiationDetail()}
              </div>
            </div>
          </>
        )}

        {activeTab === 'uncertainty' && (
          <>
            <div className="explain-left">
              <div className="panel">
                <div className="panel-header">
                  <div className="panel-title">// UNCERTAINTY REPORTS</div>
                </div>
                <div className="uncertainty-list-panel">
                  {UNCERTAINTY_REPORTS.map(u => {
                    const level = UNCERTAINTY_LEVELS[u.level];
                    return (
                      <div
                        key={u.id}
                        className={`unc-card ${selectedUncertainty?.id === u.id ? 'selected' : ''}`}
                        style={{ '--level-color': level.color, '--level-bg': level.bg }}
                        onClick={() => setSelectedUncertainty(u)}
                      >
                        <div className="unc-card-header">
                          <span className="unc-level-badge" style={{ background: level.bg, color: level.color }}>
                            {level.label}
                          </span>
                          <span className="unc-confidence">
                            置信 {(u.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div className="unc-conclusion">{u.conclusion}</div>
                        <div className="unc-indicators">
                          <div className="unc-indicator">
                            <span className="ind-label">证据</span>
                            <div className="ind-bar">
                              <div className="ind-fill" style={{ width: `${u.evidenceStrength * 100}%` }} />
                            </div>
                          </div>
                          <div className="unc-indicator">
                            <span className="ind-label">质量</span>
                            <div className="ind-bar">
                              <div className="ind-fill quality" style={{ width: `${u.dataQuality * 100}%` }} />
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="explain-right">
              <div className="panel">
                <div className="panel-header">
                  <div className="panel-title">// UNCERTAINTY DETAIL</div>
                </div>
                {renderUncertaintyDetail()}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Architecture Features */}
      <div className="arch-features fade-in-delay-2" style={{ marginTop: 24 }}>
        <div className="feature-card">
          <div className="feature-icon" style={{ color: '#00d4ff' }}>📖</div>
          <div className="feature-title">决策可解释层</div>
          <div className="feature-desc">每个 Agent 决策生成人类可读解释，支持决策链追踪和执行摘要生成，确保 AI 行为透明可追溯</div>
        </div>
        <div className="feature-card">
          <div className="feature-icon" style={{ color: '#ff6a00' }}>🤝</div>
          <div className="feature-title">Agent 协商协议</div>
          <div className="feature-desc">多 Agent 通过协商解决能力争议，支持评分/投票/混合/一致同意四种共识机制，实现最优 Agent 选择</div>
        </div>
        <div className="feature-card">
          <div className="feature-icon" style={{ color: '#c6ff3d' }}>📊</div>
          <div className="feature-title">不确定性量化</div>
          <div className="feature-desc">贝叶斯置信更新 + 证据质量评估，让 Agent 对结论的确定性进行量化声明，避免过度自信</div>
        </div>
        <div className="feature-card">
          <div className="feature-icon" style={{ color: '#a855f7' }}>🔄</div>
          <div className="feature-title">三级容错恢复</div>
          <div className="feature-desc">L1 快速重试 → L2 策略切换 → L3 优雅降级，每级降级都诚实告知用户，确保系统稳定</div>
        </div>
      </div>
    </div>
  );
}

export default DecisionExplainabilityPage;