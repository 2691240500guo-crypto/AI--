import http from '@/utils/request'

// 操作日志（A08/I01）
export function listOperationLogs(params) {
  return http.get('/audit/logs', { params })
}
export function exportOperationLogs(params) {
  return http.get('/audit/logs/export', { params, responseType: 'blob' })
}

// 登录日志（A09）
export function listLoginLogs(params) {
  return http.get('/audit/login-logs', { params })
}
export function exportLoginLogs(params) {
  return http.get('/audit/login-logs/export', { params, responseType: 'blob' })
}
