import http from '@/utils/request'

export function getOverview(params) { return http.get('/analytics/overview', { params }) }
export function getTrend(params) { return http.get('/analytics/trend', { params }) }
export function getDistribution(params) { return http.get('/analytics/distribution', { params }) }
export function getDimFilter(params) { return http.get('/analytics/dim-filter', { params }) }
export function exportReport(data) {
  return http.post('/analytics/export', data)   // 返回 {file_name, file_url}，前端拿 file_url 走 /export/download 下载
}