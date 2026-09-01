import http from '@/utils/request'

// 操作日志（A08/I01）
export function listOperationLogs(params) {
  return http.get('/audit/operations', { params })
}
export function exportOperationLogs(params) {
  return http.get('/audit/operations/export', { params, responseType: 'blob' })
}

// 登录日志（A09）
export function listLoginLogs(params) {
  return http.get('/audit/logins', { params })
}
export function exportLoginLogs(params) {
  return http.get('/audit/logins/export', { params, responseType: 'blob' })
}
