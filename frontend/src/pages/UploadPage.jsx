import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { message } from 'antd';
import api from '../api';

export default function UploadPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [userId] = useState('demo_user');
  const [sessionId] = useState(`session_${Date.now()}`);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  };

  const handleFileSelect = (e) => {
    const f = e.target.files[0];
    if (f) setFile(f);
  };

  const handleUpload = async () => {
    if (!file) {
      message.warning('请先选择 FIT 文件');
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('user_id', userId);
      formData.append('session_id', sessionId);

      const { data } = await api.post('/upload', formData);
      message.success('上传成功！AI 分析完成');
      navigate(`/activity/${data.activity_id}`);
    } catch (err) {
      const detail = err.response?.data?.detail;
      message.error(detail || '上传失败，请检查后端服务');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="page fade-in">
      <div className="page-header">
        <div className="page-title-block">
          <div className="page-eyebrow">// UPLOAD WORKOUT</div>
          <h1 className="page-title">上传活动</h1>
          <p className="page-subtitle">支持 .fit 文件 · 自动解析 · AI 深度分析</p>
        </div>
      </div>

      <div className="upload-hero fade-in-delay-1">
        <div className="upload-content">
          <span className="upload-icon">🚴</span>
          <h2 className="upload-title">把你的训练数据带过来</h2>
          <p className="upload-desc">
            从 Garmin、Suunto、Polar、Keep 等运动设备导出 .fit 文件<br />
            上传后系统会自动生成训练报告和个性化建议
          </p>

          <div
            className={`upload-dropzone ${dragging ? 'dragging' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => document.getElementById('file-input').click()}
          >
            <div style={{ fontSize: 40, marginBottom: 12 }}>📁</div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, color: 'var(--ink-100)', marginBottom: 6, letterSpacing: '0.05em' }}>
              {file ? file.name : '拖拽 FIT 文件到这里'}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-300)', letterSpacing: '0.15em', textTransform: 'uppercase' }}>
              {file ? `${(file.size / 1024).toFixed(1)} KB · 点击重新选择` : '或点击选择文件 · 仅支持 .fit'}
            </div>
            <input
              id="file-input"
              type="file"
              accept=".fit"
              style={{ display: 'none' }}
              onChange={handleFileSelect}
            />
          </div>

          {file && (
            <button
              className="btn btn-primary"
              style={{ marginTop: 28 }}
              onClick={handleUpload}
              disabled={uploading}
            >
              {uploading ? '⚡ AI 分析中...' : '⚡ 上传并分析'}
            </button>
          )}
        </div>
      </div>

      <div className="grid-3 fade-in-delay-2" style={{ marginTop: 32 }}>
        {[
          { icon: '📊', title: '自动数据解析', desc: '解析 GPS、心率、海拔等完整数据' },
          { icon: '🤖', title: 'AI 智能分析', desc: '基于你的历史数据进行个性化对比' },
          { icon: '💡', title: '训练建议', desc: '生成本次训练的改进方向和建议' },
        ].map((f) => (
          <div key={f.title} className="panel" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>{f.icon}</div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 15, color: 'var(--ink-100)', letterSpacing: '0.05em', marginBottom: 6 }}>
              {f.title}
            </div>
            <div style={{ fontSize: 13, color: 'var(--ink-300)', lineHeight: 1.5 }}>{f.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
