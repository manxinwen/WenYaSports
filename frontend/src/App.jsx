import { BrowserRouter, Link, Route, Routes } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import UploadPage from './pages/UploadPage';
import ActivityDetailPage from './pages/ActivityDetailPage';

export default function App() {
  return (
    <BrowserRouter>
      <Layout style={{ minHeight: '100vh' }}>
        <Layout.Header style={{ display: 'flex', alignItems: 'center' }}>
          <Menu
            theme="dark"
            mode="horizontal"
            selectable={false}
            style={{ flex: 1, minWidth: 0 }}
            items={[
              { key: 'home', label: <Link to="/">FIT 运动分析</Link> },
            ]}
          />
        </Layout.Header>
        <Layout.Content style={{ padding: 24 }}>
          <Routes>
            <Route path="/" element={<UploadPage />} />
            <Route path="/activity/:id" element={<ActivityDetailPage />} />
          </Routes>
        </Layout.Content>
      </Layout>
    </BrowserRouter>
  );
}
