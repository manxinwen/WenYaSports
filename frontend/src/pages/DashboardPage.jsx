import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell, Legend,
} from 'recharts';
import { useAuth } from '../AuthContext';
import api from '../api';

const sportMeta = {
  run: { icon: '🏃', label: '跑步', className: 'sport-run' },
  cycling: { icon: '🚴', label: '骑行', className: 'sport-cycling' },
  hike: { icon: '🥾', label: '徒步', className: 'sport-hike' },
  swim: { icon: '🏊', label: '游泳', className: 'sport-swim' },
  walk: { icon: '🚶', label: '步行', className: 'sport-walk' },
};

function DashboardPage() {
  const { user } = useAuth();
  const [time, setTime] = useState(new Date());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 60000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!user?.user_id) return;
    setLoading(true);
    setError('');
    api.get('/dashboard/summary', { params: { user_id: user.user_id } })
      .then(res => setData(res.data))
      .catch(err => setError(err.response?.data?.detail || '加载数据失败'))
      .finally(() => setLoading(false));
  }, [user?.user_id]);

  const formatDate = (d) => {
    const months = ['一月','二月','三月','四月','五月','六月','七月','八月','九月','十月','十一月','十二月'];
    return `${d.getFullYear()} · ${months[d.getMonth()]} · ${d.getDate()}日`;
  };

  // ---- Loading State ----
  if (loading) {
    return (
      <div className="page fade-in" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>⏳</div>
          <div style={{ color: 'var(--ink-300)', fontSize: 14, letterSpacing: '0.1em' }}>加载运动数据...</div>
        </div>
      </div>
    );
  }

  // ---- Error State ----
  if (error) {
    return (
      <div className="page fade-in" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div style={{ textAlign: 'center', maxWidth: 400 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
          <div style={{ color: '#f87171', fontSize: 14, marginBottom: 16 }}>{error}</div>
          <button
            onClick={() => window.location.reload()}
            style={{ padding: '10px 20px', background: 'var(--gradient)', color: '#000', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}
          >重试</button>
        </div>
      </div>
    );
  }

  const isEmpty = data?.empty;

  // ---- 数据准备（新用户也显示完整仪表盘，数值为 0） ----
  const weeklyData = data?.weekly?.length ? data.weekly : (() => {
    const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    return days.map(d => ({ day: d, 距离: 0, 时长: 0, 卡路里: 0 }));
  })();
  const sports = data?.sports?.length ? data.sports : [];
  const monthlyTrend = data?.monthly?.length ? data.monthly : (() => {
    const now = new Date();
    const arr = [];
    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      arr.push({ month: `${d.getMonth() + 1}月`, 活动: 0, 公里: 0 });
    }
    return arr;
  })();
  const recentActivities = data?.recent?.length ? data.recent : [];
  const prs = data?.prs?.length ? data.prs : [
    { label: '最远距离', value: '0.0', unit: 'KM', sport: '暂无', accent: '#ff6a00' },
    { label: '最长时间', value: '0', unit: 'MIN', sport: '暂无', accent: '#00d4ff' },
    { label: '最高海拔', value: '0', unit: 'M', sport: '暂无', accent: '#60a5fa' },
    { label: '活动次数', value: '0', unit: '', sport: '总', accent: '#c6ff3d' },
  ];

  const todayTotal = weeklyData.reduce((s, d) => s + (d.距离 || 0), 0);
  const weekActiveDays = weeklyData.filter(d => (d.距离 || 0) > 0).length;
  const totalDuration = weeklyData.reduce((s, d) => s + (d.时长 || 0), 0);
  const totalCalories = weeklyData.reduce((s, d) => s + (d.卡路里 || 0), 0);
  const totalSportsKm = sports.reduce((s, c) => s + (c.total_km || 0), 0);
  const avgPace = totalSportsKm > 0 && totalDuration > 0
    ? `${Math.round(totalDuration / totalSportsKm)}'`
    : "—";
  const totalActivities = data?.total_activities || 0;

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
          <div className="stat-delta">{weekActiveDays} 天 · 共 {totalActivities} 次活动</div>
        </div>

        <div className="stat-card">
          <div className="stat-label"><span className="dot"></span> 活动时长</div>
          <div>
            <span className="stat-value">{totalDuration}</span>
            <span className="stat-unit">MIN</span>
          </div>
          <div className="stat-delta">本周累计</div>
        </div>

        <div className="stat-card">
          <div className="stat-label"><span className="dot"></span> 消耗能量</div>
          <div>
            <span className="stat-value">{totalCalories.toLocaleString()}</span>
            <span className="stat-unit">KCAL</span>
          </div>
          <div className="stat-delta down">本周累计</div>
        </div>

        <div className="stat-card">
          <div className="stat-label"><span className="dot"></span> 平均配速</div>
          <div>
            <span className="stat-value">{avgPace}</span>
            <span className="stat-unit">/KM</span>
          </div>
          <div className="stat-delta">{totalSportsKm.toFixed(1)} KM 总计</div>
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
            <span className="panel-tag">TOTAL</span>
          </div>
          <div style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={sports}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                  strokeWidth={0}
                >
                  {sports.map((entry, i) => (
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
            {sports.map((s) => (
              <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12 }}>
                <div style={{ width: 10, height: 10, borderRadius: 3, background: s.color }} />
                <span style={{ flex: 1, color: 'var(--ink-200)', fontFamily: 'var(--font-mono)', letterSpacing: '0.05em' }}>{s.name}</span>
                <span style={{ color: 'var(--ink-100)', fontWeight: 600, fontFamily: 'var(--font-display)' }}>{s.value}%</span>
                <span style={{ color: 'var(--ink-400)', fontSize: 10 }}>{s.total_km}km</span>
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
              <div className="panel-title">月度进步曲线</div>
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
            {prs.map((pr) => (
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
          {recentActivities.length === 0 ? (
            <div style={{
              padding: '40px 20px',
              textAlign: 'center',
              color: 'var(--ink-400)',
              fontSize: 13,
            }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>📋</div>
              还没有活动记录，
              <Link to="/upload" style={{ color: 'var(--cyan)', textDecoration: 'none', marginLeft: 4 }}>
                上传第一条活动 →
              </Link>
            </div>
          ) : recentActivities.map((a) => {
            const meta = sportMeta[a.type] || { icon: '🏃', label: a.type, className: 'sport-run' };
            return (
              <div key={a.id} className="activity-row">
                <div className="activity-date">
                  {a.date?.slice(5) || '—'}
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
