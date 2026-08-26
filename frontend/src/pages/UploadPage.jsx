import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Form, Input, Typography, message } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import { Upload } from 'antd';
import api from '../api';

const { Dragger } = Upload;

export default function UploadPage() {
  const navigate = useNavigate();
  const [userId, setUserId] = useState('demo_user');
  const [sessionId, setSessionId] = useState(`session_${Date.now()}`);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  const handleUpload = async () => {
    if (!file) {
      message.warning('请先选择 FIT 文件');
      return;
    }
    if (!userId.trim()) {
      message.warning('请输入用户 ID');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', userId.trim());
    formData.append('session_id', sessionId.trim() || `session_${Date.now()}`);

    setUploading(true);
    try {
      const { data } = await api.post('/upload', formData);
      message.success('上传并分析成功');
      navigate(`/activity/${data.activity_id}`);
    } catch (err) {
      const detail = err.response?.data?.detail;
      message.error(detail || '上传失败，请检查后端服务是否启动');
    } finally {
      setUploading(false);
    }
  };

  return (
    <Card style={{ maxWidth: 680, margin: '0 auto' }}>
      <Typography.Title level={3}>上传 FIT 运动文件</Typography.Title>
      <Typography.Paragraph type="secondary">
        上传运动手表 / 码表导出的 .fit 文件，系统将自动解析并生成训练分析与建议。
      </Typography.Paragraph>

      <Dragger
        accept=".fit"
        maxCount={1}
        beforeUpload={(f) => {
          setFile(f);
          return false; // 阻止自动上传，由按钮统一触发
        }}
        onRemove={() => setFile(null)}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽 FIT 文件到此处</p>
        <p className="ant-upload-hint">仅支持 .fit 格式</p>
      </Dragger>

      <Form layout="vertical" style={{ marginTop: 24 }}>
        <Form.Item label="用户 ID" required>
          <Input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="请输入用户 ID"
          />
        </Form.Item>
        <Form.Item label="会话 ID">
          <Input
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="用于短期记忆的会话 ID"
          />
        </Form.Item>
        <Button
          type="primary"
          size="large"
          block
          loading={uploading}
          onClick={handleUpload}
        >
          {uploading ? '正在分析...' : '上传并分析'}
        </Button>
      </Form>
    </Card>
  );
}
