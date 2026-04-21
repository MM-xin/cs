import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: '/api',
  withCredentials: true,
  timeout: 15000,
})

http.interceptors.request.use((config) => {
  config.metadata = { start: Date.now() }
  return config
})

const SKIP_TOAST_URL = ['/me']

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const url = error.config?.url || ''
    const skipToast = SKIP_TOAST_URL.some((path) => url.endsWith(path))

    if (!error.response) {
      if (!skipToast) ElMessage.error('网络异常，请稍后重试')
    } else if (status === 401) {
      if (!skipToast) ElMessage.warning('登录状态已失效，请重新登录')
      if (typeof window !== 'undefined' && !window.location.pathname.endsWith('/login')) {
        window.location.assign('/login')
      }
    } else if (status >= 500) {
      if (!skipToast) ElMessage.error(error.response?.data?.detail || '服务器异常，请稍后重试')
    } else if (status === 422) {
      if (!skipToast) ElMessage.error('请求参数异常')
    } else {
      const detail = error.response?.data?.detail
      if (!skipToast && detail) ElMessage.error(detail)
    }
    return Promise.reject(error)
  },
)

export default http
