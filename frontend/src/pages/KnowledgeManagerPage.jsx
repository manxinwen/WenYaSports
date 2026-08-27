import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../AuthContext';
import api from '../api';

const CATEGORY_NAMES = {
  strength: '💪 力量训练',
  endurance: '🏃 耐力训练',
  nutrition: '🥗 运动营养',
  physiology: '🧬 运动生理学',
  technique: '🎯 运动技术',
  sports_science: '🔬 运动科学',
  general: '📚 综合',
};

function KnowledgeManagerPage() {
  const { user, isAdmin, logout } = useAuth();
  const [stats, setStats] = useState(null);
  const [files, setFiles] = useState([]);
  const [categories, setCategories] = useState([]);
  const [filterCategory, setFilterCategory] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [previewResult, setPreviewResult] = useState(null);
  const [classifyPreview, setClassifyPreview] = useState(null);
  const [newCategory, setNewCategory] = useState('general');
  const [selectedFile, setSelectedFile] = useState(null);
  const [message, setMessage] = useState('');

  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get('/knowledge/stats');
      setStats(res.data);
    } catch (e) { console.error(e); }
  }, []);

  const fetchFiles = useCallback(async () => {
    try {
      const params = {};
      if (filterCategory) params.category = filterCategory;
      if (filterStatus) params.status = filterStatus;
      const res = await api.get('/knowledge/list', { params });
      setFiles(res.data.files);
    } catch (e) { console.error(e); }
  }, [filterCategory, filterStatus]);

  const fetchCategories = useCallback(async () => {
    try {
      const res = await api.get('/auth/categories');
      setCategories(res.data.categories);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => {
    fetchStats();
    fetchFiles();
    fetchCategories();
  }, [fetchStats, fetchFiles, fetchCategories]);

  const showMessage = (msg, isError = false) => {
    setMessage(msg);
    setTimeout(() => setMessage(''), 3000);
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // 先预览分类
    try {
      setUploading(true);
      const fd = new FormData();
      fd.append('file', file);
      const previewRes = await api.post('/knowledge/classify', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setClassifyPreview(previewRes.data);
      setPreviewResult(file);
    } catch (e) {
      console.error(e);
      showMessage('分类预览失败', true);
    } finally {
      setUploading(false);
    }
  };

  const handleConfirmUpload = async () => {
    if (!previewResult) return;
    try {
      setUploading(true);
      const fd = new FormData();
      fd.append('file', previewResult);
      // 如果手动选了分类，强制使用
      if (newCategory !== 'general' || classifyPreview?.needs_review) {
        fd.append('force_category', newCategory);
      }
      const res = await api.post('/knowledge/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setUploadResult(res.data);
      showMessage('上传成功！' + (res.data.indexed ? '已向量化' : '待处理'));
      fetchStats();
      fetchFiles();
    } catch (e) {
      showMessage('上传失败: ' + (e.response?.data?.detail || e.message), true);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (fileId) => {
    if (!confirm('确定删除此文件？原始文件和向量数据都会被删除。')) return;
    try {
      await api.post(`/knowledge/${fileId}/delete`);
      showMessage('已删除');
      fetchStats();
      fetchFiles();
    } catch (e) {
      showMessage('删除失败', true);
    }
  };

  const handleReclassify = async (fileId) => {
    try {
      const res = await api.post(`/knowledge/${fileId}/reclassify`);
      showMessage(`重新分类成功: ${CATEGORY_NAMES[res.data.new_category] || res.data.new_category}`);
      fetchFiles();
    } catch (e) {
      showMessage('重新分类失败', true);
    }
  };

  const handleUpdateCategory = async (fileId, category) => {
    try {
      await api.post(`/knowledge/${fileId}/category`, { new_category: category });
      showMessage('分类已更新');
      fetchFiles();
      fetchStats();
    } catch (e) {
      showMessage('更新失败', true);
    }
  };

  const handleRebuild = async () => {
    if (!confirm('确定重建所有索引？这将删除所有向量并重新向量化。')) return;
    try {
      const res = await api.post('/knowledge/rebuild');
      showMessage(`重建完成: ${res.data.indexed}/${res.data.total_files} 文件, ${res.data.total_chunks} 片段`);
      fetchStats();
      fetchFiles();
    } catch (e) {
      showMessage('重建失败', true);
    }
  };

  if (!isAdmin) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <h2>需要管理员权限</h2>
        <button onClick={logout}>退出登录</button>
      </div>
    );
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: 24, padding: '16px 24px',
        background: 'var(--panel)', borderRadius: 12, border: '1px solid var(--border)',
      }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22 }}>📚 知识库管理</h1>
          <p style={{ margin: '4px 0 0', color: 'var(--ink-400)', fontSize: 13 }}>
            管理员: {user?.username} · 自动分类 + 向量化索引
          </p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <button onClick={fetchStats} style={btnStyle('ghost')}>🔄 刷新</button>
          <button onClick={handleRebuild} style={btnStyle('flame')}>🔨 重建索引</button>
          <button onClick={logout} style={btnStyle('danger')}>🚪 退出</button>
        </div>
      </div>

      {message && (
        <div style={{
          padding: '10px 16px', marginBottom: 16,
          background: message.includes('失败') || message.includes('错误')
            ? 'rgba(255,68,68,0.1)' : 'rgba(0,212,255,0.1)',
          border: `1px solid ${message.includes('失败') || message.includes('错误')
            ? 'rgba(255,68,68,0.3)' : 'rgba(0,212,255,0.3)'}`,
          borderRadius: 8, fontSize: 13,
        }}>{message}</div>
      )}

      {/* Stats */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, marginBottom: 24 }}>
          <StatCard label="文件总数" value={stats.total_files} icon="📄" color="var(--cyan)" />
          <StatCard label="已索引" value={stats.indexed} icon="✅" color="#4ade80" />
          <StatCard label="待处理" value={stats.pending} icon="⏳" color="#fbbf24" />
          <StatCard label="失败" value={stats.failed} icon="❌" color="#f87171" />
          <StatCard label="向量片段" value={stats.total_chunks} icon="🧩" color="var(--flame)" />
        </div>
      )}

      {/* Upload Section */}
      <div style={{
        padding: 24, marginBottom: 24,
        background: 'var(--panel)', borderRadius: 12, border: '1px solid var(--border)',
      }}>
        <h2 style={{ fontSize: 16, marginBottom: 16 }}>📤 上传知识文件</h2>

        {!uploading && !classifyPreview && (
          <label style={{
            display: 'block', padding: 40, textAlign: 'center',
            border: '2px dashed var(--border)', borderRadius: 12,
            cursor: 'pointer', transition: 'all 0.2s',
          }}
          onMouseOver={(e) => e.currentTarget.style.borderColor = 'var(--cyan)'}
          onMouseOut={(e) => e.currentTarget.style.borderColor = 'var(--border)'}
          >
            <input
              type="file"
              accept=".md,.txt,.pdf"
              onChange={handleFileUpload}
              style={{ display: 'none' }}
            />
            <div style={{ fontSize: 36, marginBottom: 12 }}>📁</div>
            <div style={{ fontSize: 14, color: 'var(--ink-200)' }}>
              点击或拖拽上传文件
            </div>
            <div style={{ fontSize: 12, color: 'var(--ink-400)', marginTop: 4 }}>
              支持 .md / .txt / .pdf（最大 50MB）
            </div>
          </label>
        )}

        {uploading && (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--ink-300)' }}>
            <div style={{ fontSize: 24 }}>⏳</div>
            <div style={{ marginTop: 8 }}>处理中...</div>
          </div>
        )}

        {classifyPreview && !uploading && (
          <div style={{ padding: 16, background: 'var(--bg-2)', borderRadius: 8 }}>
            <div style={{ marginBottom: 16 }}>
              <strong>🔍 AutoClassifyAgent 分类结果：</strong>
            </div>

            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
              <div style={{ padding: '8px 16px', background: 'rgba(0,212,255,0.1)', borderRadius: 8 }}>
                分类: <strong>{CATEGORY_NAMES[classifyPreview.primary_category] || classifyPreview.primary_category}</strong>
              </div>
              <div style={{ padding: '8px 16px', background: classifyPreview.confidence >= 0.7 ? 'rgba(74,222,128,0.1)' : 'rgba(251,191,36,0.1)', borderRadius: 8 }}>
                置信度: <strong>{(classifyPreview.confidence * 100).toFixed(0)}%</strong>
              </div>
              <div style={{ padding: '8px 16px', background: classifyPreview.needs_review ? 'rgba(248,113,113,0.1)' : 'rgba(74,222,128,0.1)', borderRadius: 8 }}>
                {classifyPreview.needs_review ? '⚠️ 需要人工确认' : '✅ 高置信度'}
              </div>
            </div>

            <div style={{ marginBottom: 16, fontSize: 13, color: 'var(--ink-300)' }}>
              💭 {classifyPreview.reasoning}
            </div>

            {classifyPreview.candidates?.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 8 }}>候选分类:</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {classifyPreview.candidates.slice(0, 5).map((c) => (
                    <span key={c.category} style={{
                      padding: '4px 10px', fontSize: 12,
                      background: 'rgba(255,255,255,0.05)', borderRadius: 6,
                    }}>
                      {CATEGORY_NAMES[c.category] || c.category} ({(c.confidence * 100).toFixed(0)}%)
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 13, marginRight: 8 }}>
                {classifyPreview.needs_review ? '⚠️ 请手动选择分类:' : '覆盖分类 (可选):'}
              </label>
              <select
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                style={selectStyle}
              >
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', gap: 12 }}>
              <button onClick={handleConfirmUpload} style={btnStyle('gradient')}>
                ✅ 确认上传 & 向量化
              </button>
              <button
                onClick={() => { setClassifyPreview(null); setPreviewResult(null); setUploadResult(null); }}
                style={btnStyle('ghost')}
              >
                取消
              </button>
            </div>
          </div>
        )}

        {uploadResult && (
          <div style={{
            padding: 16, marginTop: 16,
            background: 'rgba(74,222,128,0.1)', border: '1px solid rgba(74,222,128,0.3)',
            borderRadius: 8,
          }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>
              ✅ 上传成功!
            </div>
            <div style={{ fontSize: 13, color: 'var(--ink-200)' }}>
              文件: {uploadResult.original_filename} → {CATEGORY_NAMES[uploadResult.category] || uploadResult.category}
              {uploadResult.indexed && ` · ${uploadResult.chunk_count} 个片段已向量化`}
            </div>
          </div>
        )}
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <select
          value={filterCategory}
          onChange={(e) => { setFilterCategory(e.target.value); fetchFiles(); }}
          style={selectStyle}
        >
          <option value="">全部分类</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <select
          value={filterStatus}
          onChange={(e) => { setFilterStatus(e.target.value); fetchFiles(); }}
          style={selectStyle}
        >
          <option value="">全部状态</option>
          <option value="pending">待处理</option>
          <option value="indexed">已索引</option>
          <option value="failed">失败</option>
        </select>
      </div>

      {/* File List */}
      <div style={{
        background: 'var(--panel)', borderRadius: 12, border: '1px solid var(--border)',
        overflow: 'hidden',
      }}>
        <div style={{
          padding: '14px 20px', borderBottom: '1px solid var(--border)',
          display: 'grid', gridTemplateColumns: '2fr 1.5fr 1fr 1fr 1.5fr', gap: 12,
          fontSize: 12, color: 'var(--ink-400)', textTransform: 'uppercase', letterSpacing: '0.1em',
        }}>
          <div>文件名</div>
          <div>分类</div>
          <div>置信度</div>
          <div>状态</div>
          <div>操作</div>
        </div>

        {files.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--ink-400)' }}>
            <div style={{ fontSize: 36, marginBottom: 8 }}>📭</div>
            <div>暂无知识文件</div>
            <div style={{ fontSize: 12, marginTop: 4 }}>上传 .md / .txt / .pdf 文件开始构建知识库</div>
          </div>
        ) : (
          files.map((f) => (
            <div
              key={f.file_id}
              style={{
                padding: '12px 20px', borderBottom: '1px solid var(--border)',
                display: 'grid', gridTemplateColumns: '2fr 1.5fr 1fr 1fr 1.5fr', gap: 12,
                alignItems: 'center', fontSize: 13,
              }}
            >
              <div>
                <div style={{ fontWeight: 500, color: 'var(--ink-100)' }}>
                  {f.original_filename || f.filename}
                </div>
                <div style={{ fontSize: 11, color: 'var(--ink-500)', fontFamily: 'var(--font-mono)' }}>
                  {f.file_id?.slice(0, 12)} · {f.chunk_count || 0} chunks
                </div>
              </div>
              <div>
                <select
                  value={f.category}
                  onChange={(e) => handleUpdateCategory(f.file_id, e.target.value)}
                  style={{ ...selectStyle, padding: '4px 8px', fontSize: 12 }}
                >
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
              <div>
                {f.classification_confidence > 0 ? (
                  <span style={{
                    color: f.classification_confidence >= 0.7 ? '#4ade80'
                      : f.classification_confidence >= 0.4 ? '#fbbf24' : '#f87171',
                    fontWeight: 500,
                  }}>
                    {(f.classification_confidence * 100).toFixed(0)}%
                  </span>
                ) : '—'}
              </div>
              <div>
                <StatusBadge status={f.status} />
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={() => handleReclassify(f.file_id)}
                  title="重新自动分类"
                  style={iconBtnStyle}
                >🔄</button>
                <button
                  onClick={() => setSelectedFile(f)}
                  title="详情"
                  style={iconBtnStyle}
                >👁️</button>
                <button
                  onClick={() => handleDelete(f.file_id)}
                  title="删除"
                  style={{ ...iconBtnStyle, color: '#f87171' }}
                >🗑️</button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* File Detail Modal */}
      {selectedFile && (
        <div
          onClick={() => setSelectedFile(null)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: 'var(--panel)', borderRadius: 16, padding: 32,
              width: 500, maxWidth: '90vw', border: '1px solid var(--border)',
            }}
          >
            <h3 style={{ margin: '0 0 16px' }}>📄 文件详情</h3>
            <div style={{ display: 'grid', gap: 12, fontSize: 14 }}>
              <DetailRow label="文件名" value={selectedFile.original_filename} />
              <DetailRow label="文件ID" value={selectedFile.file_id?.slice(0, 16)} mono />
              <DetailRow label="存储路径" value={selectedFile.stored_path} mono />
              <DetailRow label="分类" value={CATEGORY_NAMES[selectedFile.category] || selectedFile.category} />
              <DetailRow label="置信度" value={`${(selectedFile.classification_confidence * 100).toFixed(0)}%`} />
              <DetailRow label="状态" value={selectedFile.status} />
              <DetailRow label="片段数" value={String(selectedFile.chunk_count || 0)} />
              <DetailRow label="上传时间" value={selectedFile.upload_time || '—'} />
              {selectedFile.error_message && (
                <DetailRow label="错误" value={selectedFile.error_message} />
              )}
            </div>
            <button
              onClick={() => setSelectedFile(null)}
              style={{ ...btnStyle('gradient'), marginTop: 24, width: '100%' }}
            >
              关闭
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon, color }) {
  return (
    <div style={{
      padding: 16, background: 'var(--panel)', borderRadius: 12,
      border: '1px solid var(--border)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 20 }}>{icon}</span>
        <span style={{ fontSize: 12, color: 'var(--ink-400)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          {label}
        </span>
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

function StatusBadge({ status }) {
  const colors = {
    pending: { bg: 'rgba(251,191,36,0.15)', color: '#fbbf24' },
    indexed: { bg: 'rgba(74,222,128,0.15)', color: '#4ade80' },
    failed: { bg: 'rgba(248,113,113,0.15)', color: '#f87171' },
  };
  const c = colors[status] || { bg: 'rgba(255,255,255,0.1)', color: 'var(--ink-300)' };
  return (
    <span style={{
      padding: '3px 10px', borderRadius: 12, fontSize: 11,
      background: c.bg, color: c.color, fontWeight: 500,
    }}>
      {status}
    </span>
  );
}

function DetailRow({ label, value, mono }) {
  return (
    <div style={{ display: 'flex', gap: 12 }}>
      <div style={{ width: 80, color: 'var(--ink-400)', fontSize: 12, flexShrink: 0 }}>{label}</div>
      <div style={{
        color: 'var(--ink-100)',
        fontFamily: mono ? 'var(--font-mono)' : 'inherit',
        fontSize: 13, wordBreak: 'break-all',
      }}>{value}</div>
    </div>
  );
}

function btnStyle(variant) {
  const base = {
    padding: '8px 16px', borderRadius: 8, border: 'none',
    cursor: 'pointer', fontSize: 13, fontWeight: 500,
  };
  if (variant === 'gradient') {
    return { ...base, background: 'var(--gradient)', color: '#000' };
  }
  if (variant === 'flame') {
    return { ...base, background: 'var(--gradient-flame)', color: '#000' };
  }
  if (variant === 'danger') {
    return { ...base, background: 'rgba(248,113,113,0.15)', color: '#f87171', border: '1px solid rgba(248,113,113,0.3)' };
  }
  if (variant === 'ghost') {
    return { ...base, background: 'transparent', color: 'var(--ink-200)', border: '1px solid var(--border)' };
  }
  return base;
}

const selectStyle = {
  padding: '8px 12px', background: 'var(--bg-2)',
  border: '1px solid var(--border)', borderRadius: 8,
  color: 'var(--ink-100)', fontSize: 13, outline: 'none',
  cursor: 'pointer',
};

const iconBtnStyle = {
  background: 'transparent', border: '1px solid var(--border)',
  borderRadius: 6, width: 28, height: 28, cursor: 'pointer',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  fontSize: 14, padding: 0,
};

export default KnowledgeManagerPage;
