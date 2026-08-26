import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  Button,
  Card,
  Col,
  Result,
  Row,
  Space,
  Spin,
  Statistic,
  Tag,
  Typography,
} from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import api from '../api';
import ActivityMap from '../components/ActivityMap';
import ActivityCharts from '../components/ActivityCharts';
import {
  formatDateTime,
  formatDistance,
  formatDuration,
  formatMeters,
  formatPace,
  formatSport,
} from '../utils/format';

const SPORT_COLORS = {
  running: 'blue',
  cycling: 'green',
  swimming: 'cyan',
  walking: 'default',
  hiking: 'orange',
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
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }
  if (error || !data) {
    return (
      <Result
        status="error"
        title="加载失败"
        subTitle={error}
        extra={
          <Link to="/">
            <Button type="primary">返回首页</Button>
          </Link>
        }
      />
    );
  }

  const { metadata = {}, features = {}, recommendation = null, records = [] } = data;
  const hrZones = features.hr_zones || {};
  const zones = [
    { key: 'zone1', label: 'Z1' },
    { key: 'zone2', label: 'Z2' },
    { key: 'zone3', label: 'Z3' },
    { key: 'zone4', label: 'Z4' },
    { key: 'zone5', label: 'Z5' },
  ];

  return (
    <div>
      <Link to="/">
        <Button icon={<ArrowLeftOutlined />} style={{ marginBottom: 16 }}>
          返回上传
        </Button>
      </Link>

      <Card
        style={{ marginBottom: 16 }}
        title={
          <Space>
            <Typography.Title level={4} style={{ margin: 0 }}>
              活动 #{id}
            </Typography.Title>
            <Tag color={SPORT_COLORS[metadata.sport] || 'default'}>
              {formatSport(metadata.sport)}
            </Tag>
            {features.intensity_distribution && (
              <Tag>{features.intensity_distribution}</Tag>
            )}
          </Space>
        }
      >
        <Row gutter={[16, 24]}>
          <Col xs={12} sm={8} md={6} lg={4}>
            <Statistic title="日期" value={formatDateTime(metadata.start_time)} valueStyle={{ fontSize: 14 }} />
          </Col>
          <Col xs={12} sm={8} md={6} lg={4}>
            <Statistic title="总距离" value={formatDistance(features.total_distance_m)} />
          </Col>
          <Col xs={12} sm={8} md={6} lg={4}>
            <Statistic title="总时长" value={formatDuration(features.total_duration_seconds)} />
          </Col>
          <Col xs={12} sm={8} md={6} lg={4}>
            <Statistic title="平均配速" value={formatPace(features.avg_pace_min_per_km)} />
          </Col>
          <Col xs={12} sm={8} md={6} lg={4}>
            <Statistic title="平均心率" value={metadata.avg_hr ?? '-'} suffix={metadata.avg_hr != null ? 'bpm' : ''} />
          </Col>
          <Col xs={12} sm={8} md={6} lg={4}>
            <Statistic title="最大心率" value={metadata.max_hr ?? '-'} suffix={metadata.max_hr != null ? 'bpm' : ''} />
          </Col>
          <Col xs={12} sm={8} md={6} lg={4}>
            <Statistic title="累计爬升" value={formatMeters(features.elevation_gain_m)} />
          </Col>
          <Col xs={12} sm={8} md={6} lg={4}>
            <Statistic title="训练负荷" value={features.training_load ?? 0} suffix="TRIMP" />
          </Col>
          <Col xs={12} sm={8} md={6} lg={4}>
            <Statistic
              title="恢复天数"
              value={recommendation?.recovery_days ?? '-'}
              suffix={recommendation?.recovery_days != null ? '天' : ''}
            />
          </Col>
          <Col xs={12} sm={8} md={6} lg={4}>
            <Statistic title="训练类型" value={features.intensity_distribution || '-'} valueStyle={{ fontSize: 16 }} />
          </Col>
        </Row>
        <Row gutter={[16, 8]} style={{ marginTop: 16 }}>
          {zones.map((z) => (
            <Col key={z.key}>
              <Space size={4}>
                <span style={{ color: '#666' }}>{z.label}</span>
                <Tag color={hrZones[z.key] ? 'processing' : 'default'}>
                  {hrZones[z.key] != null ? `${hrZones[z.key].toFixed(1)}%` : '-'}
                </Tag>
              </Space>
            </Col>
          ))}
        </Row>
      </Card>

      {records.some((r) => r.lat != null && r.lon != null) && (
        <Card title="轨迹地图" style={{ marginBottom: 16 }}>
          <ActivityMap records={records} />
        </Card>
      )}

      <Card title="训练建议" style={{ marginBottom: 16 }}>
        {recommendation ? (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Typography.Paragraph style={{ fontSize: 15, margin: 0 }}>
              {recommendation.suggestion_text}
            </Typography.Paragraph>
            <Space wrap>
              <Tag color="purple">恢复天数：{recommendation.recovery_days} 天</Tag>
              <Tag color="geekblue">
                目标心率区间：{recommendation.training_zones?.hr_zone}
              </Tag>
              <Tag color="cyan">
                建议配速：{recommendation.training_zones?.pace_range}
              </Tag>
            </Space>
          </Space>
        ) : (
          <Typography.Text type="secondary">暂无训练建议</Typography.Text>
        )}
      </Card>

      <Card title="训练图表">
        <ActivityCharts records={records} />
      </Card>
    </div>
  );
}
