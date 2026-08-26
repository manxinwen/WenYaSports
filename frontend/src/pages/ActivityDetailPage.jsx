import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Result, Spin } from 'antd';
import api from '../api';
import ActivityMap from '../components/ActivityMap';
import ActivityCharts from '../components/ActivityCharts';
import {
  formatDateTime, formatDistance, formatDuration,
  formatMeters, formatPace, formatSport,
} from '../utils/format';

const sportIconMap = {
  running: '🏃', cycling: '🚴', swimming: '🏊',
  walking: '🚶', hiking: '🥾',
};

const sportClassMap = {
  running: 'sport-run', cycling: 'sport-cycling',
  swimming: 'sport-swim', walking: 'sport-hike', hiking: 'sport-hike',
};

export default function ActivityDetailPage() {
  const { id } = useParams();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    api
      .get(`/activities/${id}`)
      .then((res) => setData(res.data))
      .catch((err) => setError(err.response?.data?.detail || '加载活动失败'))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="page" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="page">
        <Result
          status="error"
          title="活动加载失败"
          subTitle={error}
          extra={<Link to="/" className="btn btn-primary">返回仪表盘</Link>}
        />
      </div>
    );
  }

  const { metadata = {}, features = {}, recommendation = null, records = [] } = data;
  const hrZones = features.hr_zones || {};
  const sport = metadata.sport || 'running';
  const icon = sportIconMap[sport] || '⚡';
  const sportClass = sportClassMap[sport] || 'sport-run';

  const stats = [
    { label: '总距离', value: formatDistance(features.total_distance_m), unit: 'KM', color: 'var(--flame)' },
    { label: '总时长', value: formatDuration(features.total_duration_seconds), unit: '', color: 'var(--ink-100)' },
    { label: '平均配速', value: formatPace(features.avg_pace_min_per_km), unit: '/KM', color: 'var(--cyan)' },
    { label: '平均心率', value: metadata.avg_hr ?? '-', unit: metadata.avg_hr != null ? 'BPM' : '', color: 'var(--ink-100)' },
    { label: '最大心率', value: metadata.max_hr ?? '-', unit: metadata.max_hr != null ? 'BPM' : '', color: 'var(--danger)' },
    { label: '累计爬升', value: formatMeters(features.elevation_gain_m), unit: 'M', color: 'var(--lime)' },
    { label: '训练负荷', value: features.training_load ?? 0, unit: 'TRIMP', color: 'var(--ink-100)' },
    { label: '训练类型', value: features.intensity_distribution || '-', unit: '', color: 'var(--flame)' },
  ];

  const zones = [
    { key: 'zone1', label: 'Z1 · 恢复' },
    { key: 'zone2', label: 'Z2 · 有氧' },
    { key: 'zone3', label: 'Z3 · 节奏' },
    { key: 'zone4', label: 'Z4 · 乳酸' },
    { key: 'zone5', label: 'Z5 · 最大' },
  ];

  return (
    <div className="page fade-in">
      <div style={{ marginBottom: 24 }}>
        <Link to="/activities" style={{
          color: 'var(--ink-300)',
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          letterSpacing: '0.15em',
          textTransform: 'uppercase',
          textDecoration: 'none',
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          marginBottom: 16,
        }}>
          ← 返回活动列表
        </Link>
      </div>

      <div className="page-header">
        <div className="page-title-block">
          <div className="page-eyebrow">// ACTIVITY #{id}</div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <span>{icon}</span>
            <span>{formatSport(sport)}</span>
          </h1>
          <p className="page-subtitle">
            {formatDateTime(metadata.start_time)} · 训练详情与数据分析
          </p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          {features.intensity_distribution && (
            <span className="panel-tag" style={{ padding: '8px 16px', fontSize: 11 }}>
              {features.intensity_distribution}
            </span>
          )}
        </div>
      </div>

      {/* Stats grid */}
      <div className="stat-grid fade-in-delay-1">
        {stats.map((s) => (
          <div key={s.label} className="stat-card">
            <div className="stat-label"><span className="dot"></span> {s.label}</div>
            <div>
              <span className="stat-value" style={{ color: s.color, fontSize: s.value.length > 8 ? 28 : 42 }}>
                {String(s.value)}
              </span>
              {s.unit && <span className="stat-unit">{s.unit}</span>}
            </div>
          </div>
        ))}
      </div>

      {/* HR zones */}
      <div className="panel fade-in-delay-2" style={{ marginBottom: 24 }}>
        <div className="panel-header">
          <div>
            <div className="panel-title">心率区间分布</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-300)', marginTop: 4, letterSpacing: '0.1em' }}>
              HEART RATE ZONES
            </div>
          </div>
          <span className="panel-tag">5 ZONES</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {zones.map((z) => {
            const value = hrZones[z.key];
            return (
              <div key={z.key} style={{
                display: 'flex',
                alignItems: 'center',
                gap: 16,
                padding: '12px 16px',
                background: 'rgba(255,255,255,0.02)',
                borderRadius: 10,
              }}>
                <div style={{ width: 120, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--ink-200)', letterSpacing: '0.05em' }}>
                  {z.label}
                </div>
                <div style={{ flex: 1, height: 8, background: 'rgba(255,255,255,0.06)', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%',
                    width: value ? `${Math.min(value * 3, 100)}%` : '0%',
                    background: 'var(--gradient-flame)',
                    borderRadius: 4,
                    transition: 'width 1s ease',
                  }} />
                </div>
                <div style={{ width: 60, textAlign: 'right', fontFamily: 'var(--font-display)', fontSize: 20, color: value ? 'var(--flame)' : 'var(--ink-500)', fontWeight: 700 }}>
                  {value != null ? `${value.toFixed(1)}%` : '—'}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Map + recommendation */}
      <div className="grid-2 fade-in-delay-3" style={{ marginBottom: 24 }}>
        {records.some((r) => r.lat != null && r.lon != null) ? (
          <div className="panel">
            <div className="panel-header">
              <div className="panel-title">训练轨迹</div>
              <span className="panel-tag">MAP</span>
            </div>
            <div style={{ height: 360, borderRadius: 10, overflow: 'hidden' }}>
              <ActivityMap records={records} />
            </div>
          </div>
        ) : (
          <div className="panel" style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 300,
            flexDirection: 'column',
            gap: 12,
          }}>
            <div style={{ fontSize: 48 }}>🗺️</div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--ink-200)' }}>
              暂无轨迹数据
            </div>
            <div style={{ fontSize: 13, color: 'var(--ink-400)' }}>
              本次活动未记录 GPS 坐标
            </div>
          </div>
        )}

        <div className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-title">AI 训练建议</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-300)', marginTop: 4, letterSpacing: '0.1em' }}>
                COACH RECOMMENDATION
              </div>
            </div>
            <span className="panel-tag">AI</span>
          </div>

          {recommendation ? (
            <>
              <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--ink-100)', marginBottom: 20 }}>
                {recommendation.suggestion_text}
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{
                  padding: 14,
                  background: 'rgba(255,106,0,0.08)',
                  border: '1px solid rgba(255,106,0,0.2)',
                  borderRadius: 10,
                }}>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--flame)', letterSpacing: '0.2em', textTransform: 'uppercase', marginBottom: 6 }}>
                    恢复建议
                  </div>
                  <div style={{ fontFamily: 'var(--font-display)', fontSize: 24, color: 'var(--ink-100)', fontWeight: 700 }}>
                    {recommendation.recovery_days} 天
                  </div>
                </div>

                {recommendation.training_zones && (
                  <>
                    <div style={{
                      padding: 14,
                      background: 'rgba(0,212,255,0.06)',
                      border: '1px solid rgba(0,212,255,0.15)',
                      borderRadius: 10,
                    }}>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--cyan)', letterSpacing: '0.2em', textTransform: 'uppercase', marginBottom: 6 }}>
                        目标心率区间
                      </div>
                      <div style={{ fontSize: 14, color: 'var(--ink-100)' }}>
                        {recommendation.training_zones.hr_zone || '—'}
                      </div>
                    </div>

                    <div style={{
                      padding: 14,
                      background: 'rgba(198,255,61,0.06)',
                      border: '1px solid rgba(198,255,61,0.15)',
                      borderRadius: 10,
                    }}>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--lime)', letterSpacing: '0.2em', textTransform: 'uppercase', marginBottom: 6 }}>
                        建议配速
                      </div>
                      <div style={{ fontSize: 14, color: 'var(--ink-100)' }}>
                        {recommendation.training_zones.pace_range || '—'}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--ink-400)' }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>⏳</div>
              <div>训练建议生成中...</div>
            </div>
          )}
        </div>
      </div>

      {/* Charts */}
      <div className="panel fade-in-delay-4" style={{ marginBottom: 32 }}>
        <div className="panel-header">
          <div>
            <div className="panel-title">训练数据曲线</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-300)', marginTop: 4, letterSpacing: '0.1em' }}>
              HEART RATE · PACE · ELEVATION
            </div>
          </div>
          <span className="panel-tag">TIME SERIES</span>
        </div>
        <ActivityCharts records={records} />
      </div>
    </div>
  );
}
