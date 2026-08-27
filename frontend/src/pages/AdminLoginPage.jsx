import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../AuthContext';

function AdminLoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from || '/knowledge';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const user = await login(username, password);
      if (user.is_admin) {
        navigate(from, { replace: true });
      } else {
        setError('该账号不是管理员，无法进入知识库管理');
      }
    } catch (err) {
      setError(err.response?.data?.detail || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg)',
    }}>
      <div style={{
        width: 400,
        padding: 40,
        background: 'var(--panel)',
        borderRadius: 16,
        border: '1px solid var(--border)',
        boxShadow: '0 8px 40px rgba(0,0,0,0.3)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 64, height: 64, margin: '0 auto 16px',
            background: 'linear-gradient(135deg, var(--cyan), var(--flame))',
            borderRadius: 16,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 28,
          }}>🔐</div>
          <h2 style={{ margin: 0, fontSize: 22 }}>管理员登录</h2>
          <p style={{ color: 'var(--ink-400)', fontSize: 13, marginTop: 8 }}>
            WenYaSports 知识库管理系统
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{
              display: 'block', fontSize: 12, marginBottom: 6,
              color: 'var(--ink-300)', letterSpacing: '0.1em', textTransform: 'uppercase',
            }}>用户名</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              style={{
                width: '100%', padding: '12px 14px',
                background: 'var(--bg-2)', border: '1px solid var(--border)',
                borderRadius: 8, color: 'var(--ink-100)', fontSize: 14,
                outline: 'none', boxSizing: 'border-box',
              }}
              autoFocus
            />
          </div>

          <div style={{ marginBottom: 20 }}>
            <label style={{
              display: 'block', fontSize: 12, marginBottom: 6,
              color: 'var(--ink-300)', letterSpacing: '0.1em', textTransform: 'uppercase',
            }}>密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              style={{
                width: '100%', padding: '12px 14px',
                background: 'var(--bg-2)', border: '1px solid var(--border)',
                borderRadius: 8, color: 'var(--ink-100)', fontSize: 14,
                outline: 'none', boxSizing: 'border-box',
              }}
            />
          </div>

          {error && (
            <div style={{
              padding: '10px 14px', marginBottom: 16,
              background: 'rgba(255,68,68,0.1)', border: '1px solid rgba(255,68,68,0.3)',
              borderRadius: 8, color: '#ff6b6b', fontSize: 13,
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%', padding: '12px',
              background: loading ? 'var(--ink-500)' : 'var(--gradient)',
              color: '#000', border: 'none', borderRadius: 8,
              fontSize: 14, fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer',
              letterSpacing: '0.05em',
            }}
          >
            {loading ? '登录中...' : '登 录'}
          </button>
        </form>

        <div style={{
          marginTop: 24, padding: '12px',
          background: 'rgba(0,212,255,0.05)', border: '1px dashed rgba(0,212,255,0.2)',
          borderRadius: 8, fontSize: 12, color: 'var(--ink-400)',
        }}>
          💡 默认账号: <code style={{ color: 'var(--cyan)' }}>admin</code> / <code style={{ color: 'var(--flame)' }}>wenyasports2024</code>
        </div>
      </div>
    </div>
  );
}

export default AdminLoginPage;
