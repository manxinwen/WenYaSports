import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import api from '../api';

function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const { login, logout, isLoggedIn, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from || '/';
  const targetRole = location.state?.role || 'user';

  // 如果已登录，显示切换账号界面
  if (isLoggedIn) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg)',
      }}>
        <div style={{
          width: 440,
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
            <h2 style={{ margin: 0, fontSize: 22 }}>账号切换</h2>
            <p style={{ color: 'var(--ink-400)', fontSize: 13, marginTop: 8 }}>
              当前已登录，可切换其他账号
            </p>
          </div>

          <div style={{
            padding: 16, marginBottom: 24,
            background: 'var(--bg-2)', borderRadius: 10,
            border: '1px solid var(--border)',
          }}>
            <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 6 }}>
              当前账号
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10,
                background: user?.is_admin
                  ? 'linear-gradient(135deg, #ff6a00, #ee0979)'
                  : 'linear-gradient(135deg, #00d4ff, #0099cc)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#000', fontWeight: 700, fontSize: 14,
              }}>
                {user?.is_admin ? 'A' : user?.username?.[0]?.toUpperCase() || 'U'}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{user?.username}</div>
                <div style={{
                  fontSize: 11,
                  color: user?.is_admin ? 'var(--flame)' : 'var(--cyan)',
                  letterSpacing: '0.1em',
                }}>
                  {user?.is_admin ? '● ADMIN' : '● USER'}
                </div>
              </div>
            </div>
          </div>

          <form onSubmit={handleSwitchSubmit}>
            <div style={{ marginBottom: 16 }}>
              <label style={{
                display: 'block', fontSize: 12, marginBottom: 6,
                color: 'var(--ink-300)', letterSpacing: '0.1em', textTransform: 'uppercase',
              }}>新用户名</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="输入新用户名"
                style={inputStyle}
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
                style={inputStyle}
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
                letterSpacing: '0.05em', marginBottom: 10,
              }}
            >
              {loading ? '切换中...' : '切换账号'}
            </button>

            <button
              type="button"
              onClick={() => navigate(from, { replace: true })}
              style={{
                width: '100%', padding: '10px',
                background: 'transparent', color: 'var(--ink-400)',
                border: '1px solid var(--border)', borderRadius: 8,
                fontSize: 13, cursor: 'pointer',
              }}
            >
              返回，不切换
            </button>
          </form>

          <div style={hintStyle}>
            💡 管理员: <code style={{ color: 'var(--cyan)' }}>admin</code> / <code style={{ color: 'var(--flame)' }}>wenyasports2024</code>
            <br />普通用户: 任意用户名 + 密码
          </div>
        </div>
      </div>
    );
  }

  async function handleSwitchSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      // 先退出旧账号
      logout();
      // 再登录新账号
      const newUser = await login(username, password);
      if (targetRole === 'admin' && !newUser.is_admin) {
        setError('该账号不是管理员，无法进入');
        return;
      }
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || '登录失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleLoginSubmit(e) {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);
    try {
      const newUser = await login(username, password);
      if (targetRole === 'admin' && !newUser.is_admin) {
        setError('该账号不是管理员，无法进入知识库管理');
        return;
      }
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || '登录失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleRegisterSubmit(e) {
    e.preventDefault();
    setError('');
    setSuccess('');

    // 前端验证
    if (username.trim().length < 3) {
      setError('用户名至少为 3 个字符');
      return;
    }
    if (password.length < 6) {
      setError('密码至少为 6 个字符');
      return;
    }
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }

    setLoading(true);
    try {
      const res = await api.post('/auth/register', {
        username: username.trim(),
        password,
      });
      // 注册成功，自动登录
      const newUser = await login(username.trim(), password);
      setSuccess(res.data?.message || '注册成功');
      if (targetRole === 'admin' && !newUser.is_admin) {
        // 注册用户默认是普通用户，无法进入管理员
        navigate(from, { replace: true });
      } else {
        navigate(from, { replace: true });
      }
    } catch (err) {
      setError(err.response?.data?.detail || '注册失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg)',
    }}>
      <div style={{
        width: 420,
        padding: 40,
        background: 'var(--panel)',
        borderRadius: 16,
        border: '1px solid var(--border)',
        boxShadow: '0 8px 40px rgba(0,0,0,0.3)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{
            width: 64, height: 64, margin: '0 auto 16px',
            background: 'linear-gradient(135deg, var(--cyan), var(--flame))',
            borderRadius: 16,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 28,
          }}>🏃</div>
          <h2 style={{ margin: 0, fontSize: 22 }}>欢迎回来</h2>
          <p style={{ color: 'var(--ink-400)', fontSize: 13, marginTop: 8 }}>
            WenYaSports · AI 运动私教
          </p>
        </div>

        {/* Tab 切换 */}
        <div style={{
          display: 'flex', marginBottom: 24,
          background: 'var(--bg-2)', borderRadius: 10, padding: 4,
        }}>
          <button
            onClick={() => { setMode('login'); setError(''); setSuccess(''); }}
            style={{
              flex: 1, padding: '10px 14px',
              background: mode === 'login' ? 'var(--gradient)' : 'transparent',
              color: mode === 'login' ? '#000' : 'var(--ink-300)',
              border: 'none', borderRadius: 7,
              fontSize: 13, fontWeight: mode === 'login' ? 600 : 500,
              cursor: 'pointer', transition: 'all 0.2s',
            }}
          >
            登录
          </button>
          <button
            onClick={() => { setMode('register'); setError(''); setSuccess(''); }}
            style={{
              flex: 1, padding: '10px 14px',
              background: mode === 'register' ? 'var(--gradient)' : 'transparent',
              color: mode === 'register' ? '#000' : 'var(--ink-300)',
              border: 'none', borderRadius: 7,
              fontSize: 13, fontWeight: mode === 'register' ? 600 : 500,
              cursor: 'pointer', transition: 'all 0.2s',
            }}
          >
            注册
          </button>
        </div>

        {mode === 'login' ? (
          <form onSubmit={handleLoginSubmit}>
            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>用户名</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="输入用户名"
                style={inputStyle}
                autoFocus
              />
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={labelStyle}>密码</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                style={inputStyle}
              />
            </div>

            {error && (
              <div style={errorBoxStyle}>{error}</div>
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
              {loading ? '登录中...' : targetRole === 'admin' ? '管理员登录' : '登 录'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleRegisterSubmit}>
            <div style={{ marginBottom: 14 }}>
              <label style={labelStyle}>用户名</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="3-32 个字符"
                style={inputStyle}
                autoFocus
              />
            </div>

            <div style={{ marginBottom: 14 }}>
              <label style={labelStyle}>密码</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="至少 6 位"
                style={inputStyle}
              />
            </div>

            <div style={{ marginBottom: 18 }}>
              <label style={labelStyle}>确认密码</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="再次输入密码"
                style={inputStyle}
              />
            </div>

            {error && (
              <div style={errorBoxStyle}>{error}</div>
            )}

            {success && (
              <div style={{
                ...errorBoxStyle,
                background: 'rgba(34,197,94,0.1)',
                border: '1px solid rgba(34,197,94,0.3)',
                color: '#22c55e',
              }}>{success}</div>
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
              {loading ? '注册中...' : '创建账号'}
            </button>
          </form>
        )}

        <div style={hintStyle}>
          <div style={{ marginBottom: 4 }}>
            💡 管理员: <code style={{ color: 'var(--cyan)' }}>admin</code> / <code style={{ color: 'var(--flame)' }}>wenyasports2024</code>
          </div>
          <div>
            👤 普通用户: 注册新账号或使用已有账号登录
          </div>
        </div>

        {targetRole !== 'admin' && mode === 'login' && (
          <div style={{ marginTop: 16, textAlign: 'center' }}>
            <button
              type="button"
              onClick={() => navigate('/login', { state: { role: 'admin' } })}
              style={{
                background: 'transparent', border: 'none',
                color: 'var(--cyan)', fontSize: 13, cursor: 'pointer',
                textDecoration: 'underline',
              }}
            >
              管理员登录 →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

const inputStyle = {
  width: '100%', padding: '12px 14px',
  background: 'var(--bg-2)', border: '1px solid var(--border)',
  borderRadius: 8, color: 'var(--ink-100)', fontSize: 14,
  outline: 'none', boxSizing: 'border-box',
};

const labelStyle = {
  display: 'block', fontSize: 12, marginBottom: 6,
  color: 'var(--ink-300)', letterSpacing: '0.1em', textTransform: 'uppercase',
};

const hintStyle = {
  marginTop: 24, padding: '12px',
  background: 'rgba(0,212,255,0.05)', border: '1px dashed rgba(0,212,255,0.2)',
  borderRadius: 8, fontSize: 12, color: 'var(--ink-400)',
};

const errorBoxStyle = {
  padding: '10px 14px', marginBottom: 16,
  background: 'rgba(255,68,68,0.1)', border: '1px solid rgba(255,68,68,0.3)',
  borderRadius: 8, color: '#ff6b6b', fontSize: 13,
};

export default LoginPage;
