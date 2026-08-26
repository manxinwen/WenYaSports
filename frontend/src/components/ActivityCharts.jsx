import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Empty, Tabs } from 'antd';

/** 将 records 转换为图表友好的时序数据 */
function prepareSeries(records) {
  if (!records || records.length === 0) return [];
  const start = new Date(records[0].timestamp).getTime();
  return records.map((r, i) => {
    const t = new Date(r.timestamp).getTime();
    const elapsed = Number.isFinite(t) ? Math.round((t - start) / 1000) : i;
    return {
      t: elapsed,
      hr: r.hr ?? null,
      pace: r.speed && r.speed > 0 ? Number((60 / r.speed).toFixed(2)) : null,
      alt: r.alt ?? null,
    };
  });
}

/** 秒 -> "M′SS″" */
function timeTick(v) {
  if (v == null) return '';
  const m = Math.floor(v / 60);
  const s = v % 60;
  return `${m}′${String(s).padStart(2, '0')}″`;
}

/** 配速(分钟/公里) -> "mm:ss" */
function paceTick(v) {
  if (v == null) return '';
  const s = Math.round(v * 60);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export default function ActivityCharts({ records }) {
  const data = prepareSeries(records);
  if (data.length === 0) {
    return <Empty description="没有可用于绘图的时序数据" />;
  }

  const items = [
    {
      key: 'hr',
      label: '心率',
      children: (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data} margin={{ top: 8, right: 24, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="t"
              tickFormatter={timeTick}
              label={{ value: '时间', position: 'insideBottom', offset: -2 }}
            />
            <YAxis
              domain={['dataMin - 10', 'dataMax + 10']}
              label={{ value: 'bpm', angle: -90, position: 'insideLeft' }}
            />
            <Tooltip labelFormatter={(v) => `时间 ${timeTick(v)}`} />
            <Legend />
            <Line type="monotone" dataKey="hr" name="心率 (bpm)" stroke="#ff7875" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      ),
    },
    {
      key: 'pace',
      label: '配速',
      children: (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data} margin={{ top: 8, right: 24, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="t"
              tickFormatter={timeTick}
              label={{ value: '时间', position: 'insideBottom', offset: -2 }}
            />
            <YAxis
              reversed
              domain={['dataMin - 0.5', 'dataMax + 0.5']}
              tickFormatter={paceTick}
              label={{ value: 'min/km', angle: -90, position: 'insideLeft' }}
            />
            <Tooltip labelFormatter={(v) => `时间 ${timeTick(v)}`} formatter={(v) => [paceTick(v), '配速']} />
            <Legend />
            <Line type="monotone" dataKey="pace" name="配速 (min/km)" stroke="#1677ff" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      ),
    },
    {
      key: 'alt',
      label: '海拔',
      children: (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data} margin={{ top: 8, right: 24, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="t"
              tickFormatter={timeTick}
              label={{ value: '时间', position: 'insideBottom', offset: -2 }}
            />
            <YAxis
              domain={['dataMin - 10', 'dataMax + 10']}
              label={{ value: 'm', angle: -90, position: 'insideLeft' }}
            />
            <Tooltip labelFormatter={(v) => `时间 ${timeTick(v)}`} />
            <Legend />
            <Line type="monotone" dataKey="alt" name="海拔 (m)" stroke="#faad14" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      ),
    },
  ];

  return <Tabs items={items} />;
}
