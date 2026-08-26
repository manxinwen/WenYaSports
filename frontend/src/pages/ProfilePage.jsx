import { useState } from 'react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Tooltip,
  LineChart, Line, XAxis, YAxis, CartesianGrid,
} from 'recharts';

const radarData = [
  { subject: '耐力', score: 82 },
  { subject: '力量', score: 64 },
  { subject: '速度', score: 74 },
  { subject: '柔韧', score: 58 },
  { subject: '节奏', score: 88 },
  { subject: '恢复', score: 71 },
];

const heartRateData = [
  { zone: 'Z1', active: 28, recovery: 12 },
  { zone: 'Z2', active: 34, recovery: 8 },
  { zone: 'Z3', active: 24, recovery: 4 },
  { zone: 'Z4', active: 10, recovery: 2 },
  { zone: 'Z5', active: 4, recovery: 0 },
];

const achievements = [
  { icon: '🏆', label: '月跑量破百', date: '2025年1月', tier: 'gold' },
  { icon: '🔥', label: '连续训练 21 天', date: '2024年12月', tier: 'gold' },
  { icon: '⭐', label: '半马 1:52 完成', date: '2024年11月', tier: 'silver' },
  { icon: '💎', label: '10K 52分达成', date: '2024年10月', tier: 'silver' },
  { icon: '🚀', label: '首月 50K 达成', date: '2024年8月', tier: 'bronze' },
  { icon: '🌱', label: '开启训练之旅', date: '2024年6月', tier: 'bronze' },
];

function ProfilePage() {
  const [tab, setTab] = useState('overview');

  return (
    <div className="page fade-in">
      <div className="page-header">
        <div className="page-title-block">
          <div className="page-eyebrow">// ATHLETE PROFILE</div>
          <h1 className="page-title">个人中心</h1>
          <p className="page-subtitle">运动档案 · 身体数据 · 训练成就</p>
        </div>
        <button className="btn btn-ghost">编辑资料</button>
      </div>

      {/* Hero */}
      <div className="profile-hero fade-in-delay-1">
        <div className="profile-header">
          <div className="profile-avatar-lg">D</div>
          <div className="profile-info">
            <h2>Demo User</h2>
            <p className="profile-bio">周末马拉松爱好者 · 城市骑行通勤党 · 正在备战个人首马。相信积累的力量，每一步都是进步。</p>
            <div className="profile-tags">
              <span className="profile-tag">MVP 候选人</span>
              <span className="profile-tag">Sub-2 目标</span>
              <span className="profile-tag">All-Weather</span>
              <span className="profile-tag">Early Bird</span>
            </div>
          </div>
        </div>

        <div className="profile-stat-row">
          <div className="profile-stat-cell">
            <div className="profile-stat-value">128</div>
            <div className="profile-stat-label">TOTAL SESSIONS</div>
          </div>
          <div className="profile-stat-cell">
            <div className="profile-stat-value">1,248</div>
            <div className="profile-stat-label">TOTAL KM</div>
          </div>
          <div className="profile-stat-cell">
            <div className="profile-stat-value">92:14</div>
            <div className="profile-stat-label">TOTAL HOURS</div>
          </div>
          <div className="profile-stat-cell">
            <div className="profile-stat-value">12</div>
            <div className="profile-stat-label">ACHIEVEMENTS</div>
          </div>
          <div className="profile-stat-cell">
            <div className="profile-stat-value">A+</div>
            <div className="profile-stat-label">FITNESS GRADE</div>
          </div>
        </div>
      </div>

      {/* Tab nav */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        {[
          { v: 'overview', l: '综合评估' },
          { v: 'body', l: '身体数据' },
          { v: 'achievements', l: '成就徽章' },
          { v: 'goals', l: '目标计划' },
        ].map((t) => (
          <button
            key={t.v}
            onClick={() => setTab(t.v)}
            style={{
              padding: '12px 24px',
              background: 'transparent',
              border: 'none',
              borderBottom: tab === t.v ? '2px solid var(--flame)' : '2px solid transparent',
              color: tab === t.v ? 'var(--flame)' : 'var(--ink-300)',
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              cursor: 'pointer',
              fontWeight: 600,
              transition: 'all 0.2s ease',
              marginBottom: -1,
            }}
          >
            {t.l}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'overview' && (
        <>
          <div className="grid-2 fade-in-delay-2" style={{ marginBottom: 24 }}>
            <div className="panel">
              <div className="panel-header">
                <div>
                  <div className="panel-title">综合能力雷达</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-300)', marginTop: 4, letterSpacing: '0.1em' }}>
                    FITNESS SCORE · 82 / 100
                  </div>
                </div>
                <span className="panel-tag">BALANCED</span>
              </div>
              <div style={{ height: 280 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="rgba(255,255,255,0.1)" />
                    <PolarAngleAxis dataKey="subject" stroke="#a8b1c8" tick={{ fontSize: 12, fontFamily: 'Manrope' }} />
                    <PolarRadiusAxis stroke="rgba(255,255,255,0.1)" tick={{ fill: '#6b7896', fontSize: 10 }} />
                    <Radar dataKey="score" stroke="#ff6a00" fill="#ff6a00" fillOpacity={0.25} strokeWidth={2.5} />
                    <Tooltip
                      contentStyle={{
                        background: '#111827',
                        border: '1px solid rgba(255,106,0,0.3)',
                        borderRadius: 10,
                        fontFamily: 'JetBrains Mono',
                        fontSize: 12,
                      }}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">
                <div className="panel-title">心率区间分布</div>
                <span className="panel-tag">LAST 30D</span>
              </div>
              <div style={{ height: 280 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={heartRateData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="zone" stroke="#6b7896" tickLine={false} axisLine={false} />
                    <YAxis stroke="#6b7896" tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{
                        background: '#111827',
                        border: '1px solid rgba(255,106,0,0.3)',
                        borderRadius: 10,
                        fontFamily: 'JetBrains Mono',
                        fontSize: 12,
                      }}
                    />
                    <Line type="monotone" dataKey="active" stroke="#ff6a00" strokeWidth={2.5} name="活跃时长" dot={{ fill: '#ff6a00', r: 4 }} />
                    <Line type="monotone" dataKey="recovery" stroke="#00d4ff" strokeWidth={2} name="恢复时长" dot={{ fill: '#00d4ff', r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="panel fade-in-delay-3">
            <div className="panel-header">
              <div className="panel-title">能力评估详情</div>
              <span className="panel-tag">AI COACH</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
              {radarData.map((r) => (
                <div key={r.subject} style={{
                  padding: '16px',
                  background: 'rgba(255,255,255,0.02)',
                  borderRadius: 10,
                  border: '1px solid rgba(255,255,255,0.04)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                    <span style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--ink-100)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                      {r.subject}
                    </span>
                    <span style={{ fontFamily: 'var(--font-display)', fontSize: 20, color: 'var(--flame)', fontWeight: 700 }}>
                      {r.score}
                    </span>
                  </div>
                  <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{
                      height: '100%',
                      width: `${r.score}%`,
                      background: 'var(--gradient-flame)',
                      borderRadius: 2,
                      transition: 'width 1s ease',
                    }} />
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--ink-400)', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
                    {r.score >= 80 ? '★ 优秀' : r.score >= 65 ? '◈ 良好' : '○ 待提升'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {tab === 'body' && (
        <div className="grid-3 fade-in-delay-2">
          {[
            { label: '身高', value: '178', unit: 'cm', trend: '—' },
            { label: '体重', value: '68.5', unit: 'kg', trend: '↓ 1.2' },
            { label: '体脂率', value: '12.4', unit: '%', trend: '↓ 0.8%' },
            { label: '基础代谢', value: '1,642', unit: 'kcal', trend: '↑ 3%' },
            { label: '静息心率', value: '54', unit: 'bpm', trend: '↓ 2' },
            { label: '最大心率', value: '192', unit: 'bpm', trend: '稳定' },
            { label: 'VO2 Max', value: '56.8', unit: 'ml/kg', trend: '↑ 2.4' },
            { label: 'BMI', value: '21.6', unit: '', trend: '正常' },
          ].map((m) => (
            <div key={m.label} className="stat-card">
              <div className="stat-label"><span className="dot"></span> {m.label}</div>
              <div>
                <span className="stat-value">{m.value}</span>
                <span className="stat-unit">{m.unit}</span>
              </div>
              <div className={`stat-delta ${m.trend.startsWith('↓') && !m.trend.includes('bmi') ? 'down' : ''}`}>{m.trend}</div>
            </div>
          ))}
        </div>
      )}

      {tab === 'achievements' && (
        <div className="panel fade-in-delay-2">
          <div className="panel-header">
            <div className="panel-title">成就徽章</div>
            <span className="panel-tag">{achievements.length} UNLOCKED</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 16 }}>
            {achievements.map((a, i) => (
              <div key={i} style={{
                padding: 20,
                background: a.tier === 'gold' ? 'linear-gradient(145deg, rgba(255,106,0,0.15), rgba(204,68,0,0.08))' :
                  a.tier === 'silver' ? 'linear-gradient(145deg, rgba(168,177,200,0.12), rgba(107,120,150,0.05))' :
                  'linear-gradient(145deg, rgba(198,255,61,0.1), rgba(107,120,150,0.05))',
                borderRadius: 12,
                border: `1px solid ${
                  a.tier === 'gold' ? 'rgba(255,106,0,0.3)' :
                  a.tier === 'silver' ? 'rgba(168,177,200,0.3)' :
                  'rgba(198,255,61,0.3)'
                }`,
                textAlign: 'center',
              }}>
                <div style={{ fontSize: 36, marginBottom: 8 }}>{a.icon}</div>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 14, color: 'var(--ink-100)', letterSpacing: '0.04em', marginBottom: 6 }}>
                  {a.label}
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-400)', letterSpacing: '0.1em' }}>
                  {a.date}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'goals' && (
        <div className="grid-2 fade-in-delay-2">
          <div className="panel">
            <div className="panel-header">
              <div className="panel-title">2025 赛季目标</div>
              <span className="panel-tag">AMBITION</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {[
                { label: '完成首马（42.195km）', progress: 68, due: '2025-03-22', status: '进行中' },
                { label: '半马突破 1:40', progress: 85, due: '2025-04-15', status: '良好' },
                { label: '月跑量稳定 150km', progress: 72, due: '2025-12-31', status: '达标' },
                { label: '减重 5kg', progress: 40, due: '2025-06-30', status: '进行中' },
                { label: '越野 25km 完赛', progress: 30, due: '2025-05-20', status: '待开始' },
              ].map((g, i) => (
                <div key={i} style={{ padding: '14px 16px', background: 'rgba(255,255,255,0.02)', borderRadius: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                    <span style={{ fontFamily: 'var(--font-display)', fontSize: 15, color: 'var(--ink-100)', letterSpacing: '0.03em' }}>{g.label}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--flame)', fontWeight: 600 }}>{g.progress}%</span>
                  </div>
                  <div style={{ height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden', marginBottom: 8 }}>
                    <div style={{ height: '100%', width: `${g.progress}%`, background: 'var(--gradient-flame)', borderRadius: 3 }} />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--ink-400)', letterSpacing: '0.1em' }}>
                    <span>目标日期：{g.due}</span>
                    <span>{g.status}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <div className="panel-title">里程碑</div>
              <span className="panel-tag">TIMELINE</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, position: 'relative', paddingLeft: 20 }}>
              <div style={{ position: 'absolute', left: 6, top: 8, bottom: 8, width: 2, background: 'rgba(255,255,255,0.08)' }} />
              {[
                { date: '2024.06', event: '开启第一次跑步 · 3KM' },
                { date: '2024.08', event: '达成月 50KM 里程碑' },
                { date: '2024.10', event: '10KM 跑进 52 分钟' },
                { date: '2024.11', event: '首个半马 · 1:52:14' },
                { date: '2024.12', event: '连续训练 21 天' },
                { date: '2025.01', event: '月跑量破百 · 108KM' },
                { date: '2025.03', event: '🎯 目标：首马完赛' },
              ].map((m, i) => (
                <div key={i} style={{ position: 'relative' }}>
                  <div style={{
                    position: 'absolute',
                    left: -20,
                    top: 4,
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    background: m.event.includes('🎯') ? 'var(--flame)' : 'var(--ink-500)',
                    boxShadow: m.event.includes('🎯') ? '0 0 12px var(--flame)' : 'none',
                  }} />
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--flame)', letterSpacing: '0.1em', marginBottom: 4 }}>
                    {m.date}
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--ink-100)' }}>{m.event}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProfilePage;
