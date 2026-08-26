import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts';

const activities = [
  { id: 1, type: 'run', name: '晨跑 · 滨江步道', date: '2025-01-15', time: '06:42', distance: '8.42', duration: '51:24', pace: "6'05\"", calories: 684, elevation: 42, avgHr: 156, maxHr: 178 },
  { id: 2, type: 'cycling', name: '城市骑行', date: '2025-01-14', time: '18:15', distance: '22.5', duration: '1:08:30', pace: '24.3 km/h', calories: 562, elevation: 120, avgHr: 132, maxHr: 156 },
  { id: 3, type: 'hike', name: '西山徒步', date: '2025-01-12', time: '08:00', distance: '12.6', duration: '3:24:12', pace: '2.7 km/h', calories: 1040, elevation: 842, avgHr: 128, maxHr: 152 },
  { id: 4, type: 'run', name: '间歇训练 · 400m×8', date: '2025-01-11', time: '17:30', distance: '8.2', duration: '42:18', pace: "5'08\"", calories: 612, elevation: 28, avgHr: 168, maxHr: 189 },
  { id: 5, type: 'run', name: '轻松恢复跑', date: '2025-01-10', time: '07:00', distance: '5.2', duration: '32:48', pace: "6'18\"", calories: 324, elevation: 18, avgHr: 142, maxHr: 158 },
  { id: 6, type: 'swim', name: '自由泳训练', date: '2025-01-09', time: '20:00', distance: '1.5', duration: '45:00', pace: "1'48\"/100m", calories: 486, elevation: 0, avgHr: 148, maxHr: 172 },
  { id: 7, type: 'cycling', name: '周末长距离', date: '2025-01-05', time: '09:00', distance: '48.2', duration: '2:18:40', pace: '20.8 km/h', calories: 1124, elevation: 326, avgHr: 145, maxHr: 168 },
  { id: 8, type: 'hike', name: '莫干山穿越', date: '2025-01-03', time: '07:30', distance: '18.4', duration: '4:42:28', pace: '3.9 km/h', calories: 1524, elevation: 1240, avgHr: 134, maxHr: 162 },
  { id: 9, type: 'run', name: '年终10K', date: '2024-12-31', time: '08:00', distance: '10.0', duration: '52:18', pace: "5'14\"", calories: 742, elevation: 52, avgHr: 162, maxHr: 182 },
  { id: 10, type: 'run', name: '冬日晨跑', date: '2024-12-28', time: '06:30', distance: '6.8', duration: '41:52', pace: "6'10\"", calories: 456, elevation: 32, avgHr: 152, maxHr: 172 },
];

const sportMeta = {
  run: { icon: '🏃', label: '跑步', className: 'sport-run' },
  cycling: { icon: '🚴', label: '骑行', className: 'sport-cycling' },
  hike: { icon: '🥾', label: '徒步', className: 'sport-hike' },
  swim: { icon: '🏊', label: '游泳', className: 'sport-swim' },
};

const monthData = [
  { week: 'W1', 里程: 42 },
  { week: 'W2', 里程: 58 },
  { week: 'W3', 里程: 36 },
  { week: 'W4', 里程: 74 },
];

function ActivitiesPage() {
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState('date');

  const filtered = activities.filter(a => filter === 'all' || a.type === filter);
  const sorted = [...filtered].sort((a, b) => {
    if (sort === 'distance') return parseFloat(b.distance) - parseFloat(a.distance);
    if (sort === 'calories') return b.calories - a.calories;
    return new Date(b.date) - new Date(a.date);
  });

  const totalKm = activities.reduce((s, a) => s + parseFloat(a.distance), 0);
  const totalCal = activities.reduce((s, a) => s + a.calories, 0);
  const totalHours = activities.reduce((sum, a) => {
    const [h, m, sec] = a.duration.split(':').map(Number);
    return sum + (h || 0) + m / 60 + (sec || 0) / 3600;
  }, 0);

  return (
    <div className="page fade-in">
      <div className="page-header">
        <div className="page-title-block">
          <div className="page-eyebrow">// ACTIVITY ARCHIVE</div>
          <h1 className="page-title">运动历史</h1>
          <p className="page-subtitle">{activities.length} 条记录 · 总里程 {totalKm.toFixed(1)} KM · 总时长 {totalHours.toFixed(1)} HRS</p>
        </div>
        <Link to="/upload" className="btn btn-primary">＋ 上传活动</Link>
      </div>

      {/* Summary row */}
      <div className="stat-grid fade-in-delay-1">
        <div className="stat-card">
          <div className="stat-label"><span className="dot"></span> 本月活动</div>
          <div><span className="stat-value">{activities.length}</span><span className="stat-unit">SESSIONS</span></div>
          <div className="stat-delta">↑ 对比上月</div>
        </div>
        <div className="stat-card">
          <div className="stat-label"><span className="dot"></span> 累计里程</div>
          <div><span className="stat-value">{totalKm.toFixed(1)}</span><span className="stat-unit">KM</span></div>
          <div className="stat-delta">↑ 稳定进步</div>
        </div>
        <div className="stat-card">
          <div className="stat-label"><span className="dot"></span> 总消耗</div>
          <div><span className="stat-value">{totalCal.toLocaleString()}</span><span className="stat-unit">KCAL</span></div>
          <div className="stat-delta">↑ 持续燃烧</div>
        </div>
        <div className="stat-card">
          <div className="stat-label"><span className="dot"></span> 训练时长</div>
          <div><span className="stat-value">{totalHours.toFixed(1)}</span><span className="stat-unit">HRS</span></div>
          <div className="stat-delta down">↓ 本周略减</div>
        </div>
      </div>

      {/* Monthly mini chart */}
      <div className="panel fade-in-delay-2" style={{ marginBottom: 24 }}>
        <div className="panel-header">
          <div>
            <div className="panel-title">月度训练量分布</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-300)', marginTop: 4, letterSpacing: '0.1em' }}>
              WEEKLY VOLUME · JAN 2025
            </div>
          </div>
          <span className="panel-tag">4 WEEKS</span>
        </div>
        <div style={{ height: 140 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={monthData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="week" stroke="#6b7896" tickLine={false} axisLine={false} />
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
              <Bar dataKey="里程" fill="#ff6a00" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Filter bar */}
      <div className="panel fade-in-delay-3" style={{ padding: 16, marginBottom: 20, display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-300)', letterSpacing: '0.15em', textTransform: 'uppercase', marginRight: 8 }}>筛选</span>
          {[
            { v: 'all', l: '全部' },
            { v: 'run', l: '跑步' },
            { v: 'cycling', l: '骑行' },
            { v: 'hike', l: '徒步' },
            { v: 'swim', l: '游泳' },
          ].map((f) => (
            <button
              key={f.v}
              onClick={() => setFilter(f.v)}
              style={{
                padding: '6px 14px',
                borderRadius: 20,
                border: '1px solid ' + (filter === f.v ? 'var(--flame)' : 'rgba(255,255,255,0.1)'),
                background: filter === f.v ? 'rgba(255,106,0,0.15)' : 'transparent',
                color: filter === f.v ? 'var(--flame)' : 'var(--ink-200)',
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                cursor: 'pointer',
                fontWeight: 600,
                transition: 'all 0.2s ease',
              }}
            >
              {f.l}
            </button>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-300)', letterSpacing: '0.15em', textTransform: 'uppercase' }}>排序</span>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: 8,
              border: '1px solid rgba(255,255,255,0.1)',
              background: 'rgba(255,255,255,0.04)',
              color: 'var(--ink-100)',
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            <option value="date">按日期</option>
            <option value="distance">按距离</option>
            <option value="calories">按消耗</option>
          </select>
        </div>
      </div>

      {/* Activity list */}
      <div className="activity-list fade-in-delay-4" style={{ marginBottom: 32 }}>
        {sorted.map((a) => {
          const meta = sportMeta[a.type];
          const dateObj = new Date(a.date);
          const month = dateObj.toLocaleString('zh-CN', { month: 'short' }).replace('月', '');
          const day = dateObj.getDate();
          return (
            <Link key={a.id} to={`/activity/${a.id}`} className="activity-row" style={{ textDecoration: 'none' }}>
              <div className="activity-date">
                <div style={{ color: 'var(--flame)', fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700, lineHeight: 1 }}>{day}</div>
                <small>{month}月 · {a.time}</small>
              </div>
              <div className="activity-info">
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                  <span className={`activity-sport-badge ${meta.className}`}>{meta.icon} {meta.label}</span>
                  <span className="activity-sport">{a.name}</span>
                </div>
                <div style={{ display: 'flex', gap: 16, fontSize: 11, color: 'var(--ink-400)', fontFamily: 'var(--font-mono)', letterSpacing: '0.05em' }}>
                  <span>↑ {a.elevation}m</span>
                  <span>♥ {a.avgHr} bpm</span>
                  <span>MAX {a.maxHr} bpm</span>
                </div>
              </div>
              <div className="activity-stat">
                <div className="activity-stat-value">{a.distance}</div>
                <div className="activity-stat-label">KM</div>
              </div>
              <div className="activity-stat">
                <div className="activity-stat-value">{a.duration}</div>
                <div className="activity-stat-label">DURATION</div>
              </div>
              <div className="activity-stat">
                <div className="activity-stat-value" style={{ color: 'var(--flame)' }}>{a.calories}</div>
                <div className="activity-stat-label">KCAL</div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export default ActivitiesPage;
