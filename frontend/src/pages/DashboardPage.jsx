import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell, Legend,
  LineChart, Line,
} from 'recharts';

const weeklyData = [
  { day: '周一', 距离: 5.2, 时长: 32, 卡路里: 412 },
  { day: '周二', 距离: 0, 时长: 0, 卡路里: 0 },
  { day: '周三', 距离: 8.4, 时长: 51, 卡路里: 684 },
  { day: '周四', 距离: 3.1, 时长: 19, 卡路里: 248 },
  { day: '周五', 距离: 0, 时长: 0, 卡路里: 0 },
  { day: '周六', 距离: 12.6, 时长: 78, 卡路里: 1040 },
  { day: '周日', 距离: 6.8, 时长: 42, 卡路里: 560 },
];

const monthlyTrend = [
  { month: '1月', 活动: 12, 公里: 78 },
  { month: '2月', 活动: 15, 公里: 92 },
  { month: '3月', 活动: 11, 公里: 68 },
  { month: '4月', 活动: 18, 公里: 124 },
  { month: '5月', 活动: 22, 公里: 156 },
  { month: '6月', 活动: 19, 公里: 138 },
];

const sportDistribution = [
  { name: '跑步', value: 45, color: '#ff6a00' },
  { name: '骑行', value: 25, color: '#00d4ff' },
  { name: '徒步', value: 18, color: '#c6ff3d' },
  { name: '游泳', value: 12, color: '#60a5fa' },
];

const recentActivities = [
  { id: 1, type: 'run', name: '晨跑 · 滨江步道', date: '今天', time: '06:42', distance: '8.42 km', duration: '51:24', pace: "6'05\"", calories: 684 },
  { id: 2, type: 'cycling', name: '城市骑行', date: '昨天', time: '18:15', distance: '22.5 km', duration: '1:08:30', pace: '24.3 km/h', calories: 562 },
  { id: 3, type: 'hike', name: '西山徒步', date: '周六', time: '08:00', distance: '12.6 km', duration: '3:24:12', pace: '2.7 km/h', calories: 1040 },
  { id: 4, type: 'run', name: '间歇训练', date: '周五', time: '17:30', distance: '6.0 km', duration: '38:20', pace: "6'26\"", calories: 412 },
];

const sportMeta = {
  run: { icon: '🏃', label: '跑步', className: 'sport-run' },
  cycling: { icon: '🚴', label: '骑行', className: 'sport-cycling' },
  hike: { icon: '🥾', label: '徒步', className: 'sport-hike' },
  swim: { icon: '🏊', label: '游泳', className: 'sport-swim' },
};

function DashboardPage() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 60000);
    return () => clearInterval(t);
  }, []);

  const todayTotal = weeklyData.reduce((s, d) => s + d.距离, 0);
  const weekActiveDays = weeklyData.filter(d => d.距离 > 0).length;

  const formatDate = (d) => {
    const months = ['一月','二月','三月','四月','五月','六月','七月','八月','九月','十月','十一月','十二月'];
    return `${d.getFullYear()} · ${months[d.getMonth()]} · ${d.getDate()}日`;
  };

  return (
    <div className="page fade-in">
      <div className="page-header">
        <div className="page-title-block">
          <div className="page-eyebrow">// ATHLETE DASHBOARD</div>
          <h1 className="page-title">运动仪表盘</h1>
          <p className="page-subtitle">{formatDate(time)} · 第 {weekActiveDays} 个活跃日 · 本周累计 {todayTotal.toFixed(1)} KM</p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <Link to="/upload" className="btn btn-primary">
            <span>＋</span> 上传活动
          </Link>
          <Link to="/chat" className="btn btn-ghost">
            AI 分析 →
          </Link>
        </div>
      </div>

      {/* HERO STAT GRID */}
      <div className="stat-grid fade-in-delay-1">
        <div className="stat-card">
          <div className="stat-label"><span className="dot"></span> 本周里程</div>
          <div>
            <span className="stat-value">{todayTotal.toFixed(1)}</span>
            <span className="stat-unit">KM</span>
          </div>
          <div className="stat-delta">↑ 12.4% vs 上周</div>
        </div>

        <div className="stat-card">
          <div className="stat-label"><span className="dot"></span> 活动时长</div>
          <div>
            <span className="stat-value">222</span>
            <span className="stat-unit">MIN</span>
          </div>
          <div className="stat-delta">↑ 8.2% vs 上周</div>
        </div>

        <div className="stat-card">
          <div className="stat-label"><span className="dot"></span> 消耗能量</div>
          <div>
            <span className="stat-value">2,944</span>
            <span className="stat-unit">KCAL</span>
          </div>
          <div className="stat-delta down">↓ 3.1% vs 上周</div>
        </div>

        <div className="stat-card">
          <div className="stat-label"><span className="dot"></span> 平均配速</div>
          <div>
            <span className="stat-value">5'42"</span>
            <span className="stat-unit">/KM</span>
          </div>
          <div className="stat-delta">↑ 速度提升</div>
        </div>
      </div>

      {/* MAIN CHART + SIDE */}
      <div className="grid-main-side">
        {/* Weekly Volume Chart */}
        <div className="panel panel-accent fade-in-delay-2">
          <div className="panel-header">
            <div>
              <div className="panel-title">本周训练强度</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-300)', marginTop: 4, letterSpacing: '0.1em' }}>
                DISTANCE × DURATION × CALORIES
              </div>
            </div>
            <span className="panel-tag">7 DAYS</span>
          </div>
          <div style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={weeklyData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="flameGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ff6a00" stopOpacity={0.6} />
                    <stop offset="100%" stopColor="#ff6a00" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="cyanGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00d4ff" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#00d4ff" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="day" stroke="#6b7896" tickLine={false} axisLine={false} />
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
                <Area type="monotone" dataKey="距离" stroke="#ff6a00" strokeWidth={2.5} fill="url(#flameGrad)" name="里程 (KM)" />
                <Area type="monotone" dataKey="时长" stroke="#00d4ff" strokeWidth={2} fill="url(#cyanGrad)" name="时长 (MIN)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Sports distribution */}
        <div className="panel fade-in-delay-2">
          <div className="panel-header">
            <div className="panel-title">运动类型分布</div>
            <span className="panel-tag">YTD</span>
          </div>
          <div style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={sportDistribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                  strokeWidth={0}
                >
                  {sportDistribution.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: '#111827',
                    border: '1px solid rgba(255,106,0,0.3)',
                    borderRadius: 10,
                    fontFamily: 'JetBrains Mono',
                    fontSize: 12,
                  }}
                  formatter={(value) => [`${value}%`, '占比']}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
            {sportDistribution.map((s) => (
              <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12 }}>
                <div style={{ width: 10, height: 10, borderRadius: 3, background: s.color }} />
                <span style={{ flex: 1, color: 'var(--ink-200)', fontFamily: 'var(--font-mono)', letterSpacing: '0.05em' }}>{s.name}</span>
                <span style={{ color: 'var(--ink-100)', fontWeight: 600, fontFamily: 'var(--font-display)' }}>{s.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Monthly Trend + PRs */}
      <div className="grid-2 fade-in-delay-3">
        <div className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-title">年度进步曲线</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-300)', marginTop: 4, letterSpacing: '0.1em' }}>
                MONTHLY VOLUME PROGRESSION
              </div>
            </div>
            <span className="panel-tag">6 MONTHS</span>
          </div>
          <div style={{ height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={monthlyTrend} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="month" stroke="#6b7896" tickLine={false} axisLine={false} />
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
                <Bar dataKey="公里" fill="#ff6a00" radius={[6, 6, 0, 0]} name="里程 (KM)" />
                <Bar dataKey="活动" fill="#00d4ff" radius={[6, 6, 0, 0]} name="活动次数" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">个人记录</div>
            <span className="panel-tag">PR</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {[
              { label: '最远距离', value: '42.6', unit: 'KM', sport: '全马', accent: '#ff6a00' },
              { label: '最长时间', value: '4:28', unit: 'HH:MM', sport: '超马', accent: '#00d4ff' },
              { label: '最快5K', value: '22:14', unit: 'MIN', sport: '5KM', accent: '#c6ff3d' },
              { label: '最高海拔', value: '3,842', unit: 'M', sport: '徒步', accent: '#60a5fa' },
              { label: '周里程纪录', value: '84.2', unit: 'KM', sport: '周', accent: '#ff3b5c' },
            ].map((pr) => (
              <div key={pr.label} style={{
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                padding: '12px 14px',
                background: 'rgba(255,255,255,0.02)',
                borderRadius: 10,
                border: '1px solid rgba(255,255,255,0.04)',
              }}>
                <div style={{
                  width: 4, height: 36, background: pr.accent, borderRadius: 2,
                }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, color: 'var(--ink-300)', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                    {pr.label}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--ink-400)', marginTop: 2 }}>{pr.sport}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontFamily: 'var(--font-display)', fontSize: 24, fontWeight: 700, color: 'var(--ink-100)', lineHeight: 1 }}>
                    {pr.value}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--ink-400)', fontFamily: 'var(--font-mono)', letterSpacing: '0.15em', marginTop: 2 }}>
                    {pr.unit}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* RECENT ACTIVITIES */}
      <div className="panel fade-in-delay-4" style={{ marginBottom: 32 }}>
        <div className="panel-header">
          <div>
            <div className="panel-title">最近活动</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-300)', marginTop: 4, letterSpacing: '0.1em' }}>
              RECENT WORKOUTS
            </div>
          </div>
          <Link to="/activities" style={{ color: 'var(--flame)', fontSize: 12, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            查看全部 →
          </Link>
        </div>

        <div className="activity-list">
          {recentActivities.map((a) => {
            const meta = sportMeta[a.type];
            return (
              <div key={a.id} className="activity-row">
                <div className="activity-date">
                  {a.date}
                  <small>{a.time}</small>
                </div>
                <div className="activity-info">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                    <span className={`activity-sport-badge ${meta.className}`}>{meta.icon} {meta.label}</span>
                    <span className="activity-sport">{a.name}</span>
                  </div>
                </div>
                <div className="activity-stat">
                  <div className="activity-stat-value">{a.distance}</div>
                  <div className="activity-stat-label">DISTANCE</div>
                </div>
                <div className="activity-stat">
                  <div className="activity-stat-value">{a.duration}</div>
                  <div className="activity-stat-label">DURATION</div>
                </div>
                <div className="activity-stat">
                  <div className="activity-stat-value" style={{ color: 'var(--flame)' }}>{a.calories}</div>
                  <div className="activity-stat-label">KCAL</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default DashboardPage;
