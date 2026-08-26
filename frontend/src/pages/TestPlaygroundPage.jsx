import { useState } from 'react';

const testScenarios = [
  {
    id: 'normal',
    name: '正常流程',
    icon: '✅',
    description: '用户请求正常问答，Agent 成功调用工具并返回答案',
    difficulty: 'Easy',
    color: '#22c55e',
    steps: [
      { type: 'thought', content: '分析用户意图：需要查询配速数据', agent: 'reaact_agent' },
      { type: 'action', content: '调用 query_user_profile 工具', agent: 'reaact_agent', tool: 'query_user_profile' },
      { type: 'observation', content: '获取到用户配速数据：5:30/km', agent: 'memory_agent' },
      { type: 'thought', content: '数据完整，可以生成回答了', agent: 'reaact_agent' },
      { type: 'final', content: '生成最终答案：您的配速稳定，建议保持', agent: 'reaact_agent' },
    ],
    success: true,
    latency: 1250,
  },
  {
    id: 'tool_failure',
    name: '工具降级',
    icon: '⚠️',
    description: '模拟 LLM 决定调用不存在的工具，Agent 如何降级处理',
    difficulty: 'Medium',
    color: '#f59e0b',
    steps: [
      { type: 'thought', content: '分析用户意图：查询天气情况', agent: 'reaact_agent' },
      { type: 'action', content: '调用 get_weather 工具 (不存在)', agent: 'reaact_agent', tool: 'get_weather' },
      { type: 'observation', content: '⚠️ 工具调用失败：ToolNotFoundError', agent: 'system' },
      { type: 'thought', content: '无法获取实时天气，降级使用本地知识回答', agent: 'reaact_agent' },
      { type: 'action', content: '调用 search_knowledge_base 工具', agent: 'reaact_agent', tool: 'search_knowledge_base' },
      { type: 'observation', content: '获取到季节性训练建议', agent: 'memory_agent' },
      { type: 'final', content: '生成降级答案：根据您的历史数据和当前季节...', agent: 'reaact_agent' },
    ],
    success: true,
    latency: 2100,
  },
  {
    id: 'max_loop',
    name: '最大迭代',
    icon: '🔄',
    description: '模拟 Agent 陷入循环，达到最大迭代次数上限',
    difficulty: 'Hard',
    color: '#3b82f6',
    steps: [
      { type: 'thought', content: '第 1 轮：尝试调用工具 A', agent: 'reaact_agent' },
      { type: 'action', content: '调用 get_complex_data', agent: 'reaact_agent', tool: 'get_complex_data' },
      { type: 'observation', content: '返回结果不完整 (missing fields)', agent: 'memory_agent' },
      { type: 'thought', content: '第 2 轮：尝试调用工具 B 补充信息', agent: 'reaact_agent' },
      { type: 'action', content: '调用 get_additional_info', agent: 'reaact_agent', tool: 'get_additional_info' },
      { type: 'observation', content: '返回结果仍不完整', agent: 'memory_agent' },
      { type: 'thought', content: '第 3 轮：继续尝试更多工具...', agent: 'reaact_agent' },
      { type: 'action', content: '调用 analyze_historical_data', agent: 'reaact_agent', tool: 'analyze_historical_data' },
      { type: 'observation', content: '结果仍不令人满意', agent: 'memory_agent' },
      { type: 'thought', content: '第 4-5 轮：持续循环但无法收敛', agent: 'reaact_agent' },
      { type: 'final', content: '⛔ 达到最大迭代次数 (5)，返回失败', agent: 'reaact_agent' },
    ],
    success: false,
    latency: 5000,
  },
  {
    id: 'ambiguous',
    name: '模糊意图',
    icon: '❓',
    description: '处理用户模糊请求，需要多轮澄清对话',
    difficulty: 'Medium',
    color: '#8b5cf6',
    steps: [
      { type: 'thought', content: '用户意图模糊："我该怎么训练"', agent: 'reaact_agent' },
      { type: 'action', content: '判断：需要先澄清用户目标', agent: 'reaact_agent' },
      { type: 'final', content: '生成澄清问题："您的目标是减脂还是提高成绩？"', agent: 'reaact_agent' },
      { type: 'thought', content: '用户回复："提高半马成绩"', agent: 'reaact_agent' },
      { type: 'action', content: '调用 query_user_profile 获取半马历史', agent: 'reaact_agent', tool: 'query_user_profile' },
      { type: 'observation', content: '获取到当前半马 PB: 1:55, 目标: 1:40', agent: 'memory_agent' },
      { type: 'thought', content: '目标明确，可以制定针对性计划了', agent: 'reaact_agent' },
      { type: 'action', content: '调用 get_training_plan 生成计划', agent: 'reaact_agent', tool: 'get_training_plan' },
      { type: 'observation', content: '生成 8 周半马训练计划', agent: 'memory_agent' },
      { type: 'final', content: '生成完整的训练计划和注意事项', agent: 'reaact_agent' },
    ],
    success: true,
    latency: 3200,
  },
];

function TestPlaygroundPage() {
  const [selectedScenario, setSelectedScenario] = useState(testScenarios[0]);
  const [playingStep, setPlayingStep] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);

  const playScenario = () => {
    setIsPlaying(true);
    setPlayingStep(-1);
    let step = -1;
    const interval = setInterval(() => {
      step++;
      setPlayingStep(step);
      if (step >= selectedScenario.steps.length - 1) {
        clearInterval(interval);
        setIsPlaying(false);
      }
    }, 600);
  };

  const getStepIcon = (type) => {
    switch (type) {
      case 'thought': return '💭';
      case 'action': return '⚡';
      case 'observation': return '👁️';
      case 'final': return '🎯';
      default: return '•';
    }
  };

  const getStepColor = (type) => {
    switch (type) {
      case 'thought': return '#00d4ff';
      case 'action': return '#ff6a00';
      case 'observation': return '#c6ff3d';
      case 'final': return '#22c55e';
      default: return '#6b7896';
    }
  };

  return (
    <div className="page">
      <div className="page-header fade-in">
        <div className="page-title-block">
          <div className="page-eyebrow">// AGENT TEST PLAYGROUND</div>
          <h1 className="page-title">智能体测试操场</h1>
          <div className="page-subtitle">模拟 Agent 在不同场景下的决策与容错行为</div>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <button
            onClick={playScenario}
            disabled={isPlaying}
            className="btn btn-primary"
            style={{ opacity: isPlaying ? 0.5 : 1 }}
          >
            {isPlaying ? '⏳ RUNNING...' : '▶ RUN TEST'}
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 24 }}>
        {/* Scenario List */}
        <div className="panel fade-in-delay-1">
          <div className="panel-header">
            <div className="panel-title">// TEST SCENARIOS</div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {testScenarios.map((s) => (
              <div
                key={s.id}
                onClick={() => { setSelectedScenario(s); setPlayingStep(-1); }}
                style={{
                  background: selectedScenario.id === s.id ? 'rgba(255, 106, 0, 0.1)' : 'rgba(255, 255, 255, 0.02)',
                  border: selectedScenario.id === s.id ? `1px solid ${s.color}` : '1px solid rgba(255, 255, 255, 0.05)',
                  borderRadius: 10,
                  padding: 14,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  borderLeft: `3px solid ${s.color}`,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                  <span style={{ fontSize: 20 }}>{s.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink-100)' }}>
                      {s.name}
                    </div>
                    <div style={{ fontSize: 9, color: s.color, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>
                      {s.difficulty.toUpperCase()}
                    </div>
                  </div>
                </div>
                <div style={{ fontSize: 11, color: 'var(--ink-400)', lineHeight: 1.5 }}>
                  {s.description}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Test Execution */}
        <div className="panel fade-in-delay-2" style={{ overflow: 'hidden' }}>
          {/* Scenario Info Header */}
          <div style={{
            background: 'rgba(0, 0, 0, 0.3)',
            borderRadius: 10,
            padding: 16,
            marginBottom: 20,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 28 }}>{selectedScenario.icon}</span>
              <div>
                <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--ink-100)' }}>
                  {selectedScenario.name}
                </div>
                <div style={{ fontSize: 11, color: 'var(--ink-400)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                  {selectedScenario.description}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 16 }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 20, fontWeight: 700, color: selectedScenario.color, fontFamily: 'var(--font-display)' }}>
                  {playingStep + 1 >= selectedScenario.steps.length && selectedScenario.success ? '✓' : playingStep + 1 >= selectedScenario.steps.length && !selectedScenario.success ? '✗' : `${playingStep + 1}/${selectedScenario.steps.length}`}
                </div>
                <div style={{ fontSize: 9, color: 'var(--ink-400)', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>
                  STEPS
                </div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--cyan)', fontFamily: 'var(--font-display)' }}>
                  {selectedScenario.latency}ms
                </div>
                <div style={{ fontSize: 9, color: 'var(--ink-400)', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>
                  LATENCY
                </div>
              </div>
            </div>
          </div>

          {/* Execution Trace */}
          <div style={{
            background: 'rgba(0, 0, 0, 0.2)',
            borderRadius: 10,
            padding: 16,
            height: 'calc(100vh - 320px)',
            overflowY: 'auto',
            border: '1px solid rgba(255, 255, 255, 0.04)',
          }}>
            <div style={{ fontSize: 10, color: 'var(--ink-400)', marginBottom: 16, fontFamily: 'var(--font-mono)', letterSpacing: '0.15em' }}>
              // EXECUTION LOG
            </div>
            
            {selectedScenario.steps.map((step, i) => {
              const isVisible = playingStep >= i;
              const isActive = playingStep === i && isPlaying;
              
              return (
                <div
                  key={i}
                  style={{
                    opacity: isVisible ? 1 : 0.25,
                    transition: 'opacity 0.3s',
                    marginBottom: 12,
                    padding: '12px 16px',
                    background: isVisible ? 'rgba(255, 255, 255, 0.02)' : 'transparent',
                    borderRadius: 8,
                    borderLeft: `3px solid ${isVisible ? getStepColor(step.type) : 'rgba(255,255,255,0.1)'}`,
                    position: 'relative',
                  }}
                >
                  {isActive && (
                    <div style={{
                      position: 'absolute',
                      left: -3,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      width: 3,
                      height: '20px',
                      background: getStepColor(step.type),
                      animation: 'pulse-glow 0.8s infinite',
                    }} />
                  )}
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                    <span style={{ fontSize: 14 }}>{getStepIcon(step.type)}</span>
                    <span style={{
                      fontSize: 9,
                      color: getStepColor(step.type),
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.15em',
                      fontFamily: 'var(--font-mono)',
                    }}>
                      {step.type}
                    </span>
                    {step.tool && (
                      <span style={{
                        fontSize: 8,
                        padding: '2px 8px',
                        background: 'rgba(255, 106, 0, 0.15)',
                        color: 'var(--flame)',
                        borderRadius: 3,
                        fontFamily: 'var(--font-mono)',
                        fontWeight: 600,
                      }}>
                        ⚙ {step.tool}()
                      </span>
                    )}
                    <span style={{ 
                      fontSize: 9, 
                      color: 'var(--ink-500)',
                      fontFamily: 'var(--font-mono)',
                      marginLeft: 'auto',
                    }}>
                      @ {step.agent}
                    </span>
                  </div>
                  
                  <div style={{ 
                    fontSize: 12, 
                    color: 'var(--ink-200)', 
                    lineHeight: 1.5,
                    paddingLeft: 24,
                    fontFamily: 'var(--font-mono)',
                  }}>
                    {step.content}
                  </div>
                </div>
              );
            })}

            {playingStep + 1 >= selectedScenario.steps.length && (
              <div style={{
                marginTop: 20,
                padding: 16,
                borderRadius: 10,
                background: selectedScenario.success ? 'rgba(34, 197, 94, 0.1)' : 'rgba(255, 59, 92, 0.1)',
                border: `1px solid ${selectedScenario.success ? '#22c55e' : 'var(--danger)'}`,
                textAlign: 'center',
              }}>
                <div style={{ fontSize: 24, marginBottom: 8 }}>
                  {selectedScenario.success ? '🎉' : '❌'}
                </div>
                <div style={{ 
                  fontSize: 14, 
                  fontWeight: 600,
                  color: selectedScenario.success ? '#22c55e' : 'var(--danger)',
                  fontFamily: 'var(--font-mono)',
                  letterSpacing: '0.1em',
                }}>
                  TEST {selectedScenario.success ? 'PASSED' : 'FAILED'}
                </div>
                <div style={{ fontSize: 11, color: 'var(--ink-400)', marginTop: 6 }}>
                  Agent completed {selectedScenario.steps.length} steps in {selectedScenario.latency}ms
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default TestPlaygroundPage;
