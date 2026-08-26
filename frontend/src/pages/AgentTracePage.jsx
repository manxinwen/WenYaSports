import { useState, useEffect } from 'react';

const API_BASE = 'http://localhost:8000/api';

function AgentTracePage() {
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [traceSteps, setTraceSteps] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Mock data for demo (since backend might not be fully ready)
    const mockSessions = [
      {
        session_id: 'demo-session-1',
        user_request: '帮我分析一下最近的训练强度',
        user_id: 'demo_user',
        status: 'completed',
        timestamp: Date.now() - 3600000,
        time_str: '2026-08-27 14:30:15',
        total_steps: 8,
        agents_used: ['parser_agent', 'memory_agent', 'recommendation_agent'],
      },
      {
        session_id: 'demo-session-2',
        user_request: '这次跑步感觉怎么样？',
        user_id: 'demo_user',
        status: 'running',
        timestamp: Date.now() - 1800000,
        time_str: '2026-08-27 14:45:02',
        total_steps: 3,
        agents_used: ['reaact_agent'],
      },
    ];
    setSessions(mockSessions);
    setSelectedSession(mockSessions[0]);
    setTraceSteps(getMockTrace());
    setLoading(false);

    // try {
    //   const res = await fetch(`${API_BASE}/agent-traces`);
    //   const data = await res.json();
    //   setSessions(data.sessions);
    // } catch (e) { console.error(e); }
  }, []);

  const getMockTrace = () => [
    { type: 'thought', agent: 'reaact_agent', content: '收到用户请求："帮我分析最近的训练强度"', time: '14:30:15' },
    { type: 'action', agent: 'reaact_agent', content: '调用 memory_agent.query_user_profile', time: '14:30:15', tool: true },
    { type: 'observation', agent: 'memory_agent', content: '返回用户画像：3个月内跑量增加 20%', time: '14:30:16' },
    { type: 'thought', agent: 'reaact_agent', content: '用户跑量上升，但需要分析强度分布', time: '14:30:16' },
    { type: 'action', agent: 'reaact_agent', content: '调用 parser_agent.get_recent_activities', time: '14:30:16', tool: true },
    { type: 'observation', agent: 'parser_agent', content: '返回最近 5 次活动详情', time: '14:30:17' },
    { type: 'thought', agent: 'reaact_agent', content: '综合分析：用户高强度训练占比过高 (35%)', time: '14:30:17' },
    { type: 'final', agent: 'reaact_agent', content: '生成建议：建议调整训练计划，增加恢复日', time: '14:30:18' },
  ];

  const getStepIcon = (type) => {
    switch (type) {
      case 'thought': return '💭';
      case 'action': return '⚡';
      case 'observation': return '👁️';
      case 'final': return '✅';
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

  const getStepBg = (type) => {
    switch (type) {
      case 'thought': return 'rgba(0, 212, 255, 0.08)';
      case 'action': return 'rgba(255, 106, 0, 0.08)';
      case 'observation': return 'rgba(198, 255, 61, 0.08)';
      case 'final': return 'rgba(34, 197, 94, 0.08)';
      default: return 'rgba(255, 255, 255, 0.02)';
    }
  };

  return (
    <div className="page">
      <div className="page-header fade-in">
        <div className="page-title-block">
          <div className="page-eyebrow">// AGENT OBSERVABILITY</div>
          <h1 className="page-title">Agent Trace Dashboard</h1>
          <div className="page-subtitle">追踪每一个 Agent 的思考、行动与观察</div>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <div className="badge-live">LIVE</div>
          <div className="panel-tag" style={{ padding: '6px 14px' }}>
            <span style={{ color: 'var(--flame)' }}>{sessions.length}</span> SESSIONS
          </div>
        </div>
      </div>

      <div className="grid-main-side" style={{ minHeight: 'calc(100vh - 180px)' }}>
        {/* Left: Session List */}
        <div className="panel fade-in-delay-1" style={{ overflow: 'hidden' }}>
          <div className="panel-header">
            <div className="panel-title">// SESSION HISTORY</div>
            <button className="btn btn-ghost" style={{ padding: '6px 12px', fontSize: 11 }}>
              ⟳ REFRESH
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 'calc(100vh - 240px)', overflowY: 'auto' }}>
            {sessions.map((s) => (
              <div
                key={s.session_id}
                onClick={() => { setSelectedSession(s); setTraceSteps(getMockTrace()); }}
                className="session-card"
                style={{
                  background: selectedSession?.session_id === s.session_id ? 'rgba(255, 106, 0, 0.1)' : 'rgba(255, 255, 255, 0.02)',
                  border: selectedSession?.session_id === s.session_id ? '1px solid rgba(255, 106, 0, 0.4)' : '1px solid rgba(255, 255, 255, 0.05)',
                  borderRadius: 10,
                  padding: 14,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  borderLeft: selectedSession?.session_id === s.session_id ? '3px solid var(--flame)' : '3px solid transparent',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-400)', letterSpacing: '0.1em' }}>
                    #{s.session_id.split('-').pop().toUpperCase()}
                  </div>
                  <span style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 9,
                    padding: '2px 8px',
                    borderRadius: 10,
                    background: s.status === 'completed' ? 'rgba(34, 197, 94, 0.15)' : s.status === 'running' ? 'rgba(255, 106, 0, 0.15)' : 'rgba(255, 59, 92, 0.15)',
                    color: s.status === 'completed' ? '#22c55e' : s.status === 'running' ? 'var(--flame)' : 'var(--danger)',
                    textTransform: 'uppercase',
                    fontWeight: 600,
                  }}>
                    {s.status}
                  </span>
                </div>
                <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink-100)', marginBottom: 8, lineHeight: 1.4 }}>
                  {s.user_request}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--ink-400)' }}>
                  <span>{s.time_str}</span>
                  <span>{s.total_steps} steps</span>
                </div>
                <div style={{ marginTop: 8, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {s.agents_used.map(a => (
                    <span key={a} style={{
                      fontSize: 9,
                      padding: '2px 6px',
                      background: 'rgba(0, 212, 255, 0.1)',
                      color: 'var(--cyan)',
                      borderRadius: 4,
                      fontFamily: 'var(--font-mono)',
                    }}>
                      {a}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Trace Timeline */}
        <div className="panel fade-in-delay-2" style={{ overflow: 'hidden' }}>
          <div className="panel-header">
            <div className="panel-title">// TRACE TIMELINE</div>
            <div className="panel-tag">
              {traceSteps.length} STEPS
            </div>
          </div>

          <div style={{ 
            background: 'rgba(0, 0, 0, 0.3)', 
            borderRadius: 8, 
            padding: 20, 
            height: 'calc(100vh - 240px)',
            overflowY: 'auto',
            border: '1px solid rgba(255, 255, 255, 0.04)',
            fontFamily: 'var(--font-mono)',
          }}>
            {/* Trace Steps */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {traceSteps.map((step, i) => (
                <div key={i} className="trace-step" style={{
                  background: getStepBg(step.type),
                  borderLeft: `3px solid ${getStepColor(step.type)}`,
                  padding: '12px 16px',
                  borderRadius: '0 8px 8px 0',
                  position: 'relative',
                  animationDelay: `${i * 0.05}s`,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                    <span style={{ fontSize: 16 }}>{getStepIcon(step.type)}</span>
                    <span style={{
                      fontSize: 10,
                      textTransform: 'uppercase',
                      letterSpacing: '0.15em',
                      fontWeight: 700,
                      color: getStepColor(step.type),
                    }}>
                      {step.type}
                    </span>
                    <span style={{ fontSize: 10, color: 'var(--ink-400)', marginLeft: 'auto' }}>
                      {step.time}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--ink-100)', lineHeight: 1.6, paddingLeft: 30 }}>
                    <span style={{ color: getStepColor(step.type), fontWeight: 600 }}>[{step.agent}]</span>
                    {' '}
                    {step.content}
                  </div>
                  {step.tool && (
                    <div style={{ marginTop: 8, paddingLeft: 30 }}>
                      <span style={{
                        fontSize: 9,
                        padding: '2px 6px',
                        background: 'rgba(255, 106, 0, 0.15)',
                        color: 'var(--flame)',
                        borderRadius: 3,
                        textTransform: 'uppercase',
                        letterSpacing: '0.1em',
                      }}>
                        ⚙ TOOL CALL
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Legend */}
          <div style={{ display: 'flex', gap: 16, marginTop: 16, padding: '0 8px' }}>
            {[
              { type: 'thought', label: 'Thought', color: '#00d4ff' },
              { type: 'action', label: 'Action', color: '#ff6a00' },
              { type: 'observation', label: 'Observation', color: '#c6ff3d' },
              { type: 'final', label: 'Final', color: '#22c55e' },
            ].map(item => (
              <div key={item.type} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: item.color }} />
                <span style={{ fontSize: 10, color: 'var(--ink-300)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                  {item.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default AgentTracePage;
