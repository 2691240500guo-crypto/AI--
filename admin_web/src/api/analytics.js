import http from '@/utils/request'

export function getOverview(params) { return http.get('/analytics/overview', { params }) }
export function getTrend(params) { return http.get('/analytics/trend', { params }) }
export function getDistribution(params) { return http.get('/analytics/distribution', { params }) }
export function getDimFilter(params) { return http.get('/analytics/dim-filter', { params }) }
export function exportReport(data) {
  return http.post('/analytics/export', data)   // 返回 {file_name, file_url}，前端拿 file_url 走 /export/download 下载
}
// 下载导出文件：带 token 走 /export/download，返回 blob（拦截器对 blob 直接返回文件流）
export function downloadReportFile(object_name) {
  return http.get('/analytics/export/download', {
    params: { object_name },
    responseType: 'blob',
  })
}
// 为什么用 object_name 参数而不是直接 GET file_url：
// axios 的 http 实例会自动带 Authorization（request.js L11-12 从 sessionStorage 取 token），
// 从 /analytics/export/download 相对路径走，跟导出返回的 file_url 是同一个端点，
// 但更干净、不受 host/前缀影响。


// AI 问数（D-3 / Agent⑤）：自然语言 → {sql, columns, rows, chart_json, status}
export function askNL2SQL(data) {
  return http.post('/analytics/nl2sql', data)
}
