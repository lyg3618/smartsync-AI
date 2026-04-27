import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 60000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('smartsync_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = err.response?.data?.detail || err.message || '璇锋眰澶辫触'
    if (err.response?.status === 401) {
      localStorage.removeItem('smartsync_token')
      window.location.href = '/login'
    } else if (err.response?.status !== undefined) {
      // Only show error for non-API-fallback situations
      console.warn('API error:', msg)
    }
    return Promise.reject(err)
  }
)
export default api
