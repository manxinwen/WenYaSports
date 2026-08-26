import { BrowserRouter, Route, Routes, NavLink, useLocation } from 'react-router-dom';
import DashboardPage from './pages/DashboardPage';
import ActivitiesPage from './pages/ActivitiesPage';
import ActivityDetailPage from './pages/ActivityDetailPage';
import ChatPage from './pages/ChatPage';
import ProfilePage from './pages/ProfilePage';
import UploadPage from './pages/UploadPage';
import AgentTracePage from './pages/AgentTracePage';
import MemoryInspectorPage from './pages/MemoryInspectorPage';
import TestPlaygroundPage from './pages/TestPlaygroundPage';
import './index.css';

const navItems = [
  { path: '/', icon: '🏊', label: '仪表盘', sub: 'DASHBOARD' },
  { path: '/activities', icon: '🏃', label: '运动历史', sub: 'ACTIVITIES' },
  { path: '/upload', icon: '⬆', label: '上传活动', sub: 'UPLOAD' },
  { path: '/chat', icon: '💬', label: 'AI 私教', sub: 'AI COACH' },
  { path: '/profile', icon: '◉', label: '个人中心', sub: 'PROFILE' },
];

const devNavItems = [
  { path: '/agent-trace', icon: '🔍', label: 'Agent 轨迹', sub: 'TRACE' },
  { path: '/memory', icon: '🧠', label: '记忆探针', sub: 'MEMORY' },
  { path: '/test-lab', icon: '🧪', label: '测试操场', sub: 'TEST LAB' },
];

function Sidebar() {
  const location = useLocation();

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
        {devNavItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `nav-item ${isActive ? 'active' : ''}`
            }
          >
            <span className="nav-icon" style={{ opacity: 0.8 }}>{item.icon}</span>
            <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink-200)' }}>{item.label}</span>
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
        ))}
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

        <div className="user-info">
          <div className="avatar">D</div>
          <div className="user-detail">
            <span className="user-name">Demo User</span>
            <span className="user-status">● ONLINE</span>
          </div>
        </div>
      </div>
    </aside>
  );
}

function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/activities" element={<ActivitiesPage />} />
            <Route path="/activity/:id" element={<ActivityDetailPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            {/* Agent Developer Pages */}
            <Route path="/agent-trace" element={<AgentTracePage />} />
            <Route path="/memory" element={<MemoryInspectorPage />} />
            <Route path="/test-lab" element={<TestPlaygroundPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
