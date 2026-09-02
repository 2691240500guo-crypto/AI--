import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import router from '@/router'

const apiBase = import.meta.env.VITE_API_BASE || '/api/v1'

const http = axios.create({ baseURL: apiBase, timeout: 90000 })

http.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  config.headers['X-Client-Type'] = 'admin'
  return config
})

http.interceptors.response.use(
  (resp) => {
    // 文件流（blob）直接返回，不按统一响应解析
    if (resp.config.responseType === 'blob') {
      return resp.data
    }
    const body = resp.data
    // 后端统一响应 {code, message, data}
    if (body && body.code !== 0) {
      ElMessage.error(body.message || '请求失败')
      return Promise.reject(new Error(body.message))
    }
    return body
  },
  async (err) => {
    const status = err.response?.status
    if (status === 401) {
      // token 失效，尝试用 refresh_token 续期
      const ok = await tryRefresh()
      if (ok) return http(err.config)
      const user = useUserStore()
      user.logout()
    } else if (err.response) {
      // 有 HTTP 响应：正常弹后端 message
      ElMessage.error(err.response?.data?.message || err.message)
    }
    // 无 err.response = 网络层失败（连接被拒/超时/后端未启动），不弹 toast：
    // 该场景集中在后端重启窗口的会话恢复，交由路由守卫统一清凭证并跳登录，避免并发请求刷屏。
    return Promise.reject(err)
  }
)

async function tryRefresh() {
  const rt = sessionStorage.getItem('refresh_token')
  if (!rt) return false
  try {
    const res = await axios.post(
      `${apiBase}/auth/refresh`,
      { refresh_token: rt }
    )
    sessionStorage.setItem('token', res.data.data.access_token)
    sessionStorage.setItem('refresh_token', res.data.data.refresh_token)
    return true
  } catch {
    return false
  }
}

export default http
