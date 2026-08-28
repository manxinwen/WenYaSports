import { useState, useRef, useEffect } from 'react';
import { BrowserRouter, Route, Routes, NavLink, useLocation, Navigate, useNavigate } from 'react-router-dom';
import DashboardPage from './pages/DashboardPage';
import ActivitiesPage from './pages/ActivitiesPage';
import ActivityDetailPage from './pages/ActivityDetailPage';
import ChatPage from './pages/ChatPage';
import ProfilePage from './pages/ProfilePage';
import UploadPage from './pages/UploadPage';
import AgentTracePage from './pages/AgentTracePage';
import MemoryInspectorPage from './pages/MemoryInspectorPage';
import TestPlaygroundPage from './pages/TestPlaygroundPage';
import HarnessArchPage from './pages/HarnessArchPage';
import DecisionExplainabilityPage from './pages/DecisionExplainabilityPage';
import LoginPage from './pages/LoginPage';
import KnowledgeManagerPage from './pages/KnowledgeManagerPage';
import { AuthProvider, useAuth } from './AuthContext';
import './index.css';

const navItems = [
  { path: '/', icon: '🏊', label: '仪表盘', sub: 'DASHBOARD' },
  { path: '/activities', icon: '🏃', label: '运动历史', sub: 'ACTIVITIES' },
  { path: '/upload', icon: '⬆', label: '上传活动', sub: 'UPLOAD' },
  { path: '/chat', icon: '💬', label: 'AI 私教', sub: 'AI COACH' },
  { path: '/profile', icon: '◉', label: '个人中心', sub: 'PROFILE' },
];

const devNavItems = [
  { path: '/harness', icon: '🏗️', label: 'Harness 架构', sub: 'HARNESS' },
  { path: '/explainability', icon: '🔍', label: '决策解释', sub: 'DECISION' },
  { path: '/agent-trace', icon: '🔬', label: 'Agent 轨迹', sub: 'TRACE' },
  { path: '/memory', icon: '🧠', label: '记忆探针', sub: 'MEMORY' },
  { path: '/test-lab', icon: '🧪', label: '测试操场', sub: 'TEST LAB' },
  { path: '/knowledge', icon: '📚', label: '知识库管理', sub: 'KNOWLEDGE' },
];

function Sidebar() {
  const location = useLocation();
  const { user, isAdmin, logout } = useAuth();

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="logo-icon">W</div>
        <div className="logo-text">
          <h1>WenYaSports</h1>
          <span>AI · PERSONAL COACH</span>
        </div>
      </div>

      <div style={{ padding: '16px 14px 4px' }}>
        <div className="sidebar-section-title">导航</div>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) =>
              `nav-item ${isActive ? 'active' : ''}`
            }
          >
            <span className="nav-icon">{item.icon}</span>
            <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
              <span style={{ fontSize: 14, fontWeight: 500 }}>{item.label}</span>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                letterSpacing: '0.2em',
                color: 'var(--ink-400)',
                textTransform: 'uppercase',
                marginTop: 2,
              }}>
                {item.sub}
              </span>
            </div>
          </NavLink>
        ))}
      </nav>

      {/* Developer section */}
      <div style={{ padding: '16px 14px 4px', marginTop: 'auto' }}>
        <div className="sidebar-section-title" style={{ color: 'var(--cyan)' }}>
          <span style={{ color: 'var(--flame)' }}>●</span> AGENT DEVELOPER
        </div>
      </div>

      <nav className="sidebar-nav" style={{ paddingTop: 0 }}>
        {devNavItems.map((item) => {
          // Knowledge management requires admin
          if (item.path === '/knowledge' && !isAdmin) {
            return (
              <NavLink
                key={item.path}
                to="/login"
                state={{ from: '/knowledge', role: 'admin' }}
                className={({ isActive }) =>
                  `nav-item ${isActive ? 'active' : ''}`
                }
              >
                <span className="nav-icon" style={{ opacity: 0.8 }}>{item.icon}</span>
                <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
                  <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink-200)' }}>
                    {item.label} {!isAdmin && '🔒'}
                  </span>
                  <span style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 8,
                    letterSpacing: '0.15em',
                    color: 'var(--ink-500)',
                    textTransform: 'uppercase',
                    marginTop: 2,
                  }}>
                    {item.sub}
                  </span>
                </div>
              </NavLink>
            );
          }
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `nav-item ${isActive ? 'active' : ''}`
              }
            >
              <span className="nav-icon" style={{ opacity: 0.8 }}>{item.icon}</span>
              <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
                <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink-200)' }}>
                  {item.label}
                  {item.path === '/knowledge' && isAdmin && ' ✅'}
                </span>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 8,
                  letterSpacing: '0.15em',
                  color: 'var(--ink-500)',
                  textTransform: 'uppercase',
                  marginTop: 2,
                }}>
                  {item.sub}
                </span>
              </div>
            </NavLink>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div style={{ marginBottom: 14, padding: '10px 12px', background: 'rgba(255,106,0,0.08)', borderRadius: 8, border: '1px solid rgba(255,106,0,0.15)' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'var(--flame)', marginBottom: 4 }}>
            本周目标
          </div>
          <div style={{ height: 4, background: 'rgba(255,255,255,0.08)', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: '68%', background: 'var(--gradient-flame)', borderRadius: 2 }} />
          </div>
          <div style={{ fontSize: 10, color: 'var(--ink-300)', marginTop: 6, fontFamily: 'var(--font-mono)' }}>
            68 / 100 KM
          </div>
        </div>

        <UserArea />
      </div>
    </aside>
  );
}

function UserArea() {
  const { user, isAdmin, isLoggedIn, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const handleSwitch = () => {
    navigate('/login');
  };

  const handleLogin = () => {
    navigate('/login');
  };

  if (!isLoggedIn) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', gap: 8,
        padding: '12px 14px',
        background: 'var(--panel)',
        borderRadius: 10,
        border: '1px solid var(--border)',
      }}>
        <div style={{ fontSize: 12, color: 'var(--ink-400)' }}>
          未登录 · 游客模式
        </div>
        <button
          onClick={handleLogin}
          style={{
            padding: '10px 14px',
            background: 'var(--gradient)',
            color: '#000',
            border: 'none',
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
          }}
        >
          🔐 登录
        </button>
      </div>
    );
  }

  return (
    <div style={{
      padding: '12px 14px',
      background: 'var(--panel)',
      borderRadius: 10,
      border: '1px solid var(--border)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <div className="avatar" style={{
          background: isAdmin
            ? 'linear-gradient(135deg, #ff6a00, #ee0979)'
            : 'linear-gradient(135deg, #00d4ff, #0099cc)',
        }}>
          {isAdmin ? 'A' : user?.username?.[0]?.toUpperCase() || 'U'}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 13, fontWeight: 600,
            color: 'var(--ink-100)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {user?.username || 'User'}
          </div>
          <div style={{
            fontSize: 10,
            color: isAdmin ? 'var(--flame)' : 'var(--cyan)',
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            fontWeight: 500,
          }}>
            {isAdmin ? '● ADMIN' : '● USER'}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 6 }}>
        <button
          onClick={handleSwitch}
          style={{
            flex: 1,
            padding: '7px 10px',
            background: 'var(--bg-2)',
            color: 'var(--ink-200)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            fontSize: 11,
            cursor: 'pointer',
            fontWeight: 500,
          }}
        >
          🔄 切换
        </button>
        <button
          onClick={handleLogout}
          style={{
            flex: 1,
            padding: '7px 10px',
            background: 'rgba(248,113,113,0.1)',
            color: '#f87171',
            border: '1px solid rgba(248,113,113,0.3)',
            borderRadius: 6,
            fontSize: 11,
            cursor: 'pointer',
            fontWeight: 500,
          }}
        >
          🚪 退出
        </button>
      </div>
    </div>
  );
}

function AdminRoute({ children }) {
  const { isAdmin, isLoggedIn } = useAuth();
  if (!isLoggedIn) {
    return <Navigate to="/login" state={{ from: '/knowledge', role: 'admin' }} replace />;
  }
  if (!isAdmin) {
    return <Navigate to="/login" state={{ from: '/knowledge', role: 'admin' }} replace />;
  }
  return children;
}

function TopBar() {
  const { user, isAdmin, isLoggedIn, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleLogout = () => {
    setOpen(false);
    logout();
    navigate('/login', { replace: true });
  };

  const handleSwitch = () => {
    setOpen(false);
    navigate('/login');
  };

  const handleLogin = () => {
    setOpen(false);
    navigate('/login');
  };

  return (
    <div ref={ref} style={{
      position: 'fixed',
      top: 16,
      right: 24,
      zIndex: 1000,
    }}>
      {!isLoggedIn ? (
        <button
          onClick={handleLogin}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 18px',
            background: 'var(--gradient)',
            color: '#000',
            border: 'none',
            borderRadius: 10,
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
            boxShadow: '0 4px 20px rgba(255,106,0,0.3)',
          }}
        >
          🔐 登录
        </button>
      ) : (
        <>
          <button
            onClick={() => setOpen(!open)}
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '8px 12px 8px 8px',
              background: 'rgba(0,0,0,0.6)',
              backdropFilter: 'blur(10px)',
              color: 'var(--ink-100)',
              border: '1px solid var(--border)',
              borderRadius: 30,
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
          >
            <div style={{
              width: 32, height: 32, borderRadius: '50%',
              background: isAdmin
                ? 'linear-gradient(135deg, #ff6a00, #ee0979)'
                : 'linear-gradient(135deg, #00d4ff, #0099cc)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#000', fontWeight: 700, fontSize: 13,
            }}>
              {isAdmin ? 'A' : user?.username?.[0]?.toUpperCase() || 'U'}
            </div>
            <div style={{ textAlign: 'left', paddingRight: 8 }}>
              <div style={{ fontSize: 12, fontWeight: 600, lineHeight: 1.2 }}>
                {user?.username || 'User'}
              </div>
              <div style={{
                fontSize: 9,
                color: isAdmin ? 'var(--flame)' : 'var(--cyan)',
                letterSpacing: '0.15em',
                fontWeight: 500,
              }}>
                {isAdmin ? '● ADMIN' : '● USER'}
              </div>
            </div>
            <span style={{ fontSize: 10, color: 'var(--ink-400)' }}>▼</span>
          </button>

          {open && (
            <div style={{
              position: 'absolute',
              top: 'calc(100% + 8px)',
              right: 0,
              width: 220,
              background: 'rgba(15,15,20,0.95)',
              backdropFilter: 'blur(20px)',
              border: '1px solid var(--border)',
              borderRadius: 12,
              padding: 8,
              boxShadow: '0 8px 40px rgba(0,0,0,0.5)',
            }}>
              <div style={{
                padding: '10px 12px',
                borderBottom: '1px solid var(--border)',
                marginBottom: 6,
              }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>
                  {user?.username}
                </div>
                <div style={{
                  fontSize: 10,
                  color: isAdmin ? 'var(--flame)' : 'var(--cyan)',
                  letterSpacing: '0.15em',
                }}>
                  {isAdmin ? 'ADMINISTRATOR' : 'REGULAR USER'}
                </div>
              </div>

              <button
                onClick={handleSwitch}
                style={{
                  width: '100%',
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 12px',
                  background: 'transparent',
                  color: 'var(--ink-200)',
                  border: 'none',
                  borderRadius: 8,
                  fontSize: 13,
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
              >
                <span style={{ fontSize: 16 }}>🔄</span>
                <span>切换账号</span>
              </button>

              <button
                onClick={handleLogout}
                style={{
                  width: '100%',
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 12px',
                  background: 'transparent',
                  color: '#f87171',
                  border: 'none',
                  borderRadius: 8,
                  fontSize: 13,
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(248,113,113,0.1)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
              >
                <span style={{ fontSize: 16 }}>🚪</span>
                <span>退出登录</span>
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function AppContent() {
  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <TopBar />
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/activities" element={<ActivitiesPage />} />
          <Route path="/activity/:id" element={<ActivityDetailPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          {/* Agent Developer Pages */}
          <Route path="/harness" element={<HarnessArchPage />} />
          <Route path="/explainability" element={<DecisionExplainabilityPage />} />
          <Route path="/agent-trace" element={<AgentTracePage />} />
          <Route path="/memory" element={<MemoryInspectorPage />} />
          <Route path="/test-lab" element={<TestPlaygroundPage />} />
          {/* Auth & Admin */}
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/knowledge"
            element={
              <AdminRoute>
                <KnowledgeManagerPage />
              </AdminRoute>
            }
          />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
