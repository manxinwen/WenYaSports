import axios from 'axios';

// 开发环境通过 Vite proxy 将 /api 转发到后端 (http://127.0.0.1:8000)
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 60000,
});

export default api;
