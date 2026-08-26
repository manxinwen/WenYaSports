import { useState } from 'react';

function MemoryInspectorPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [activeTab, setActiveTab] = useState('state');

  const memoryState = {
    active_sessions: 2,
    total_sessions: 47,
    total_steps_recorded: 312,
    agents_tracked: ['reaact_agent', 'memory_agent', 'parser_agent', 'recommendation_agent'],
    vector_db_status: {
      embedding_model: 'sentence-transformers/all-MiniLM-L6-v2',
      vector_store: 'ChromaDB',
      collections: [
        { name: 'user_profiles', count: 156, description: '用户画像与历史运动数据' },
        { name: 'training_knowledge', count: 1240, description: '训练知识库与最佳实践' },
      ],
    },
  };

  const mockChunks = [
    { id: 1, content: '用户近一个月跑量增加 15%，从 80km 增长到 92km', score: 0.95, source: 'user_profile', timestamp: '2026-08-27 14:30:15' },
    { id: 2, content: '用户最近 5 次配速稳定在 5:30/km，心率区间 2 训练占比 68%', score: 0.88, source: 'activity_features', timestamp: '2026-08-27 14:28:02' },
    { id: 3, content: '用户有两次全马经历，平均完赛时间 4:15:00，PB 4:02:30', score: 0.82, source: 'user_profile', timestamp: '2026-08-26 10:15:30' },
    { id: 4, content: '用户在高温环境下的配速下降约 8-10%，建议调整训练时间', score: 0.76, source: 'training_knowledge', timestamp: '2026-08-25 16:42:18' },
    { id: 5, content: '用户本周训练负荷已达 85%，建议增加恢复日以预防过度训练', score: 0.72, source: 'user_profile', timestamp: '2026-08-27 08:00:00' },
  ];

  const handleSearch = () => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const results = mockChunks.filter(c => 
      c.content.toLowerCase().includes(searchQuery.toLowerCase())
    );
    setSearchResults(results);
  };

  const highlightMatch = (text, query) => {
    if (!query) return text;
    const regex = new RegExp(`(${query})`, 'gi');
    const parts = text.split(regex);
    return parts.map((part, i) => 
      regex.test(part) ? <mark key={i} style={{ background: 'rgba(255, 106, 0, 0.4)', color: 'var(--flame)', padding: '0 2px', borderRadius: 2 }}>{part}</mark> : part
    );
  };

  return (
    <div className="page">
      <div className="page-header fade-in">
        <div className="page-title-block">
          <div className="page-eyebrow">// AI MEMORY SYSTEM</div>
          <h1 className="page-title">Memory Inspector</h1>
          <div className="page-subtitle">检视 Agent 的长期记忆与知识储备</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button 
            className="btn btn-ghost" 
            style={{ padding: '10px 18px', fontSize: 11 }}
            onClick={() => setActiveTab('state')}
          >
            STATE
          </button>
          <button 
            className="btn btn-ghost" 
            style={{ padding: '10px 18px', fontSize: 11 }}
            onClick={() => setActiveTab('search')}
          >
            SEARCH
          </button>
        </div>
      </div>

      {activeTab === 'state' ? (
        <div className="grid-2 fade-in-delay-1" style={{ gridTemplateColumns: '1fr 1fr' }}>
          {/* Memory State Overview */}
          <div className="panel">
            <div className="panel-header">
              <div className="panel-title">// SYSTEM OVERVIEW</div>
              <div className="panel-tag">LIVE</div>
            </div>
            
            <div className="stat-grid" style={{ marginBottom: 20 }}>
              <div className="stat-card" style={{ padding: '16px' }}>
                <div className="stat-label"><span className="dot" style={{ background: '#22c55e', boxShadow: '0 0 8px #22c55e' }}></span>ACTIVE</div>
                <div className="stat-value" style={{ fontSize: 32 }}>{memoryState.active_sessions}</div>
              </div>
              <div className="stat-card" style={{ padding: '16px' }}>
                <div className="stat-label">SESSIONS</div>
                <div className="stat-value" style={{ fontSize: 32 }}>{memoryState.total_sessions}</div>
              </div>
              <div className="stat-card" style={{ padding: '16px' }}>
                <div className="stat-label">TOTAL STEPS</div>
                <div className="stat-value" style={{ fontSize: 32 }}>{memoryState.total_steps_recorded}</div>
              </div>
            </div>

            <div style={{ 
              background: 'rgba(0, 212, 255, 0.05)', 
              borderRadius: 10, 
              padding: 16,
              border: '1px solid rgba(0, 212, 255, 0.15)',
            }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--cyan)', letterSpacing: '0.1em', marginBottom: 12 }}>
                VECTOR DATABASE STATUS
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                  <span style={{ color: 'var(--ink-300)' }}>Engine</span>
                  <span style={{ color: 'var(--ink-100)', fontFamily: 'var(--font-mono)' }}>
                    {memoryState.vector_db_status.vector_store}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                  <span style={{ color: 'var(--ink-300)' }}>Embedding</span>
                  <span style={{ color: 'var(--ink-100)', fontFamily: 'var(--font-mono)', maxWidth: 200, textAlign: 'right' }}>
                    {memoryState.vector_db_status.embedding_model}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Collections */}
          <div className="panel">
            <div className="panel-header">
              <div className="panel-title">// VECTOR COLLECTIONS</div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {memoryState.vector_db_status.collections.map((col, i) => (
                <div key={i} style={{
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                  borderRadius: 12,
                  padding: 16,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <div style={{ 
                      fontFamily: 'var(--font-mono)', 
                      fontSize: 13, 
                      fontWeight: 600,
                      color: 'var(--ink-100)',
                      letterSpacing: '0.05em',
                    }}>
                      {col.name}
                    </div>
                    <div style={{ 
                      fontSize: 24, 
                      fontWeight: 700,
                      fontFamily: 'var(--font-display)',
                      color: 'var(--flame)',
                    }}>
                      {col.count.toLocaleString()}
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--ink-400)', lineHeight: 1.5 }}>
                    {col.description}
                  </div>
                  <div style={{ marginTop: 10, height: 4, background: 'rgba(255, 255, 255, 0.08)', borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${(col.count / 1500) * 100}%`, background: 'var(--gradient-flame)', borderRadius: 2 }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Agents Tracked */}
          <div className="panel fade-in-delay-2" style={{ gridColumn: '1 / -1' }}>
            <div className="panel-header">
              <div className="panel-title">// AGENTS TRACKED</div>
              <div className="panel-tag">{memoryState.agents_tracked.length} AGENTS</div>
            </div>
            
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {memoryState.agents_tracked.map(agent => (
                <div key={agent} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '12px 20px',
                  background: 'rgba(0, 212, 255, 0.08)',
                  border: '1px solid rgba(0, 212, 255, 0.2)',
                  borderRadius: 10,
                  fontFamily: 'var(--font-mono)',
                  fontSize: 12,
                  color: 'var(--cyan)',
                  fontWeight: 600,
                }}>
                  <div style={{ 
                    width: 8, 
                    height: 8, 
                    borderRadius: '50%', 
                    background: 'var(--cyan)',
                    boxShadow: '0 0 8px var(--cyan)',
                    animation: 'pulse-glow 2s infinite',
                  }} />
                  {agent}
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="panel fade-in-delay-1">
          <div className="panel-header">
            <div className="panel-title">// SEMANTIC MEMORY SEARCH</div>
            <div className="panel-tag">COSINE SIMILARITY</div>
          </div>

          <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', gap: 12 }}>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search memory chunks... (e.g., 配速, 心率, 马拉松)"
                style={{
                  flex: 1,
                  background: 'rgba(0, 0, 0, 0.3)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: 10,
                  padding: '14px 18px',
                  color: 'var(--ink-100)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 14,
                  outline: 'none',
                  transition: 'border-color 0.2s',
                }}
                onFocus={(e) => e.target.style.borderColor = 'var(--flame)'}
                onBlur={(e) => e.target.style.borderColor = 'rgba(255, 255, 255, 0.1)'}
              />
              <button onClick={handleSearch} className="btn btn-primary" style={{ padding: '0 24px' }}>
                SEARCH
              </button>
            </div>
            <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 11, color: 'var(--ink-400)', fontFamily: 'var(--font-mono)' }}>SUGGESTIONS:</span>
              {['配速', '心率', '马拉松', '跑量'].map(s => (
                <span
                  key={s}
                  onClick={() => setSearchQuery(s)}
                  style={{
                    fontSize: 11,
                    padding: '4px 12px',
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: 20,
                    color: 'var(--ink-200)',
                    cursor: 'pointer',
                    fontFamily: 'var(--font-mono)',
                    transition: 'all 0.2s',
                  }}
                  onMouseOver={(e) => { e.currentTarget.style.background = 'rgba(255, 106, 0, 0.1)'; e.currentTarget.style.borderColor = 'var(--flame)'; }}
                  onMouseOut={(e) => { e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'; e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.1)'; }}
                >
                  {s}
                </span>
              ))}
            </div>
          </div>

          <div style={{ 
            background: 'rgba(0, 0, 0, 0.2)', 
            borderRadius: 10, 
            padding: 20,
            minHeight: 300,
            maxHeight: 'calc(100vh - 300px)',
            overflowY: 'auto',
            border: '1px solid rgba(255, 255, 255, 0.04)',
          }}>
            {searchResults.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{ fontSize: 11, color: 'var(--ink-400)', fontFamily: 'var(--font-mono)', marginBottom: 8 }}>
                  Found {searchResults.length} matching chunks
                </div>
                {searchResults.map(chunk => (
                  <div key={chunk.id} style={{
                    background: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid rgba(255, 106, 0, 0.2)',
                    borderRadius: 10,
                    padding: 16,
                    borderLeft: '3px solid var(--flame)',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <span style={{
                          fontSize: 10,
                          padding: '3px 10px',
                          background: 'rgba(0, 212, 255, 0.15)',
                          color: 'var(--cyan)',
                          borderRadius: 4,
                          fontFamily: 'var(--font-mono)',
                          fontWeight: 600,
                        }}>
                          {chunk.source}
                        </span>
                        <span style={{
                          fontSize: 10,
                          color: 'var(--ink-400)',
                          fontFamily: 'var(--font-mono)',
                        }}>
                          {chunk.timestamp}
                        </span>
                      </div>
                      <div style={{
                        fontSize: 12,
                        fontFamily: 'var(--font-mono)',
                        color: '#22c55e',
                        fontWeight: 600,
                      }}>
                        {(chunk.score * 100).toFixed(1)}% SIM
                      </div>
                    </div>
                    <div style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--ink-100)' }}>
                      {highlightMatch(chunk.content, searchQuery)}
                    </div>
                  </div>
                ))}
              </div>
            ) : searchQuery ? (
              <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--ink-400)' }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>🔍</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  No chunks match "{searchQuery}"
                </div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--ink-400)' }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>💭</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  Enter a query to search the vector database
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default MemoryInspectorPage;
