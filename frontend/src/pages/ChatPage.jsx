import { useState, useRef, useEffect } from 'react';

const initialContext = [
  { role: 'bot', text: '你好！我是 WenYa AI 运动私教。我已经分析了你的 10 次训练记录，本周你完成了 42.3 公里的里程，平均配速 5\'42"/km。今天我们聊点什么？', trace: null },
  { role: 'user', text: '我下周想跑一个半马，这周该怎么安排训练？', trace: null },
  { role: 'bot', text: '根据你最近 6 周的训练数据，你的半马潜力约为 1:42:00。建议本周采用 10K + 16K + 10K 的减量周模式：\n\n• 周二：10K 轻松跑 · 配速 6\'00"\n• 周四：6K + 4×400m 间歇\n• 周六：16K 目标配速 5\'50"\n• 周日：4K 恢复跑\n\n重点注意碳水补充和睡眠质量，建议每晚 7.5 小时以上。', trace: null },
];

const quickPrompts = [
  { icon: '📈', label: '分析我的跑步数据' },
  { icon: '🔥', label: '制定本周训练计划' },
  { icon: '💪', label: '如何提升耐力' },
  { icon: '🥗', label: '跑步后如何恢复' },
];

function ChatPage() {
  const [messages, setMessages] = useState(initialContext);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [showTrace, setShowTrace] = useState(false);
  const [expandedTrace, setExpandedTrace] = useState(null);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const generateTrace = (userText) => {
    return [
      { type: 'thought', content: `用户问："${userText}"，需要分析其运动历史和当前状态`, agent: 'reaact_agent' },
      { type: 'action', content: '调用 query_user_profile 获取用户画像', agent: 'reaact_agent', tool: 'query_user_profile' },
      { type: 'observation', content: '返回：用户每周跑量 42KM，当前配速 5:42，心率区间分布正常', agent: 'memory_agent' },
      { type: 'thought', content: '用户配速稳定，训练负荷适中。需要给出针对性的训练建议', agent: 'reaact_agent' },
      { type: 'action', content: '调用 get_recommendation_rules 查询适用的训练规则', agent: 'reaact_agent', tool: 'get_recommendation_rules' },
      { type: 'observation', content: '返回：中等强度间歇训练方案 + 长距离慢跑组合', agent: 'memory_agent' },
      { type: 'final', content: '综合用户数据和规则，生成最终训练建议', agent: 'reaact_agent' },
    ];
  };

  const sendMessage = (text) => {
    if (!text.trim()) return;
    const userMsg = { role: 'user', text, trace: null };
    setMessages((m) => [...m, userMsg]);
    setInput('');
    setLoading(true);

    setTimeout(() => {
      const trace = generateTrace(text);
      const reply = {
        role: 'bot',
        text: `收到！基于你的运动数据，我建议关注以下几点：\n\n1. 你本周的训练负荷比上周高出 12%，属于正常渐进范围\n2. 心率区间 3 训练占比 42%，表现不错\n3. 建议增加 1 次力量训练（下肢），预防过度使用\n4. 保持当前配速，赛前 10 天开始减量周\n\n需要我展开详细计划吗？`,
        trace: trace,
      };
      setMessages((m) => [...m, reply]);
      setLoading(false);
      // Auto-expand the trace for the new message
      setExpandedTrace(messages.length + 1);
    }, 1500);
  };

  const getStepTypeIcon = (type) => {
    switch (type) {
      case 'thought': return '💭';
      case 'action': return '⚡';
      case 'observation': return '👁️';
      case 'final': return '🎯';
      default: return '•';
    }
  };

  const getStepTypeColor = (type) => {
    switch (type) {
      case 'thought': return '#00d4ff';
      case 'action': return '#ff6a00';
      case 'observation': return '#c6ff3d';
      case 'final': return '#22c55e';
      default: return '#6b7896';
    }
  };

  return (
    <div className="page fade-in">
      <div className="page-header">
        <div className="page-title-block">
          <div className="page-eyebrow">// AI COACH</div>
          <h1 className="page-title">AI 私教</h1>
          <p className="page-subtitle">基于你的完整运动档案 · 智能分析 · 个性化建议</p>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <button
            onClick={() => setShowTrace(!showTrace)}
            className="btn"
            style={{
              padding: '8px 16px',
              fontSize: 11,
              background: showTrace ? 'rgba(0, 212, 255, 0.15)' : 'transparent',
              border: `1px solid ${showTrace ? 'var(--cyan)' : 'rgba(255, 255, 255, 0.12)'}`,
              color: showTrace ? 'var(--cyan)' : 'var(--ink-300)',
              cursor: 'pointer',
            }}
          >
            {showTrace ? '🔍' : '💭'} {showTrace ? '隐藏思考过程' : '显示思考过程'}
          </button>
          <span className="badge-live">实时分析</span>
        </div>
      </div>

      {/* Context card */}
      <div className="chat-context-card fade-in-delay-1">
        <span>📋</span>
        <span><strong>已接入数据：</strong>最近 90 天 · {128} 条运动记录 · 总里程 1,248 KM</span>
      </div>

      <div className="chat-container fade-in-delay-2">
        <div className="chat-messages">
          {messages.map((msg, i) => (
            <div key={i} className={`chat-message ${msg.role}`} style={{ maxWidth: showTrace ? '95%' : '80%' }}>
              <div className="chat-avatar">{msg.role === 'bot' ? 'AI' : 'D'}</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxWidth: '100%' }}>
                <div className="chat-bubble" style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>
                
                {/* Trace Expand Button */}
                {showTrace && msg.role === 'bot' && msg.trace && (
                  <button
                    onClick={() => setExpandedTrace(expandedTrace === i ? null : i)}
                    style={{
                      alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                      padding: '6px 12px',
                      background: expandedTrace === i ? 'rgba(0, 212, 255, 0.15)' : 'rgba(255, 255, 255, 0.04)',
                      border: `1px solid ${expandedTrace === i ? 'rgba(0, 212, 255, 0.4)' : 'rgba(255, 255, 255, 0.1)'}`,
                      borderRadius: 6,
                      color: expandedTrace === i ? 'var(--cyan)' : 'var(--ink-300)',
                      fontSize: 10,
                      fontFamily: 'var(--font-mono)',
                      letterSpacing: '0.1em',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      alignSelf: 'flex-start',
                    }}
                  >
                    {expandedTrace === i ? '▼' : '▶'} REASONING TRACE ({msg.trace.length} steps)
                  </button>
                )}

                {/* Trace Details */}
                {showTrace && msg.role === 'bot' && msg.trace && expandedTrace === i && (
                  <div style={{
                    background: 'rgba(0, 0, 0, 0.4)',
                    border: '1px solid rgba(0, 212, 255, 0.2)',
                    borderRadius: 10,
                    padding: 12,
                    marginTop: 4,
                    fontFamily: 'var(--font-mono)',
                    fontSize: 11,
                    maxWidth: 500,
                  }}>
                    <div style={{ fontSize: 9, color: 'var(--ink-400)', marginBottom: 10, letterSpacing: '0.15em', textTransform: 'uppercase' }}>
                      // AGENT REASONING PATH
                    </div>
                    {msg.trace.map((step, si) => (
                      <div key={si} style={{
                        display: 'flex',
                        gap: 8,
                        marginBottom: 8,
                        padding: '6px 8px',
                        background: 'rgba(255, 255, 255, 0.02)',
                        borderRadius: 4,
                        borderLeft: `2px solid ${getStepTypeColor(step.type)}`,
                      }}>
                        <span style={{ fontSize: 12, flexShrink: 0 }}>{getStepTypeIcon(step.type)}</span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 2 }}>
                            <span style={{ fontSize: 9, color: getStepTypeColor(step.type), fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                              {step.type}
                            </span>
                            <span style={{ fontSize: 9, color: 'var(--ink-500)' }}>@ {step.agent}</span>
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--ink-200)', lineHeight: 1.4, wordBreak: 'break-word' }}>
                            {step.content}
                          </div>
                          {step.tool && (
                            <div style={{ marginTop: 4 }}>
                              <span style={{
                                fontSize: 8,
                                padding: '2px 6px',
                                background: 'rgba(255, 106, 0, 0.2)',
                                color: 'var(--flame)',
                                borderRadius: 2,
                                letterSpacing: '0.1em',
                              }}>
                                ⚙ {step.tool}()
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="chat-message bot">
              <div className="chat-avatar">AI</div>
              <div className="chat-bubble" style={{ display: 'flex', gap: 4, alignItems: 'center', width: 'fit-content' }}>
                <span className="animate-pulse-glow" style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--flame)' }} />
                <span className="animate-pulse-glow" style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--flame)', animationDelay: '0.2s' }} />
                <span className="animate-pulse-glow" style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--flame)', animationDelay: '0.4s' }} />
                <span style={{ marginLeft: 8, fontFamily: 'var(--font-mono)', fontSize: 12 }}>分析数据中...</span>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Quick prompts */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
          {quickPrompts.map((p) => (
            <button
              key={p.label}
              onClick={() => sendMessage(p.label)}
              className="kbd"
              style={{
                padding: '8px 14px',
                cursor: 'pointer',
                fontSize: 11,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                transition: 'all 0.2s ease',
              }}
            >
              <span>{p.icon}</span> {p.label}
            </button>
          ))}
        </div>

        <div className="chat-input-area">
          <textarea
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage(input);
              }
            }}
            placeholder="问我任何关于你训练的问题... 例如：'我这周配速下降了，什么原因？'"
            rows={1}
          />
          <button
            className="chat-send-btn"
            onClick={() => sendMessage(input)}
            disabled={!input.trim()}
            style={{ opacity: !input.trim() ? 0.5 : 1 }}
          >
            ↑
          </button>
        </div>
      </div>
    </div>
  );
}

export default ChatPage;
