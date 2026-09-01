import http from '@/utils/request'

// ===== 岗位匹配域（M 域）接口封装 =====
// 后端路由前缀：/api/v1/matching（见 app/routers/api.py）

// 岗位 CRUD（M-1）
export function listPositions(params) {
  return http.get('/matching/positions', { params })
}
export function getPosition(id) {
  return http.get(`/matching/positions/${id}`)
}
export function createPosition(data) {
  return http.post('/matching/positions', data)
}
export function updatePosition(id, data) {
  return http.put(`/matching/positions/${id}`, data)
}
export function deletePosition(id) {
  return http.delete(`/matching/positions/${id}`)
}

// 岗位画像向量化（M-2）
export function vectorizePosition(id) {
  return http.post(`/matching/positions/${id}/vector`)
}

// 匹配结果列表 + 解释（M-3 / M-4）
export function listResults(params) {
  return http.get('/matching/results', { params })
}
export function getExplain(id) {
  return http.get(`/matching/result/${id}/explain`)
}

// 发起双向匹配（M-3）
export function runMatch(data) {
  return http.post('/matching/match', data)
}

// 匹配规则（支撑 M-3）
export function listRules() {
  return http.get('/matching/rules')
}

// 储备/空缺预警（M-5）
export function listAlerts(params) {
  return http.get('/matching/alerts', { params })
}
