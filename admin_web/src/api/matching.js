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

// 岗位说明书文件导入（解析文本返回，供填入 description）
export function importPositionJd(id, file, onProgress) {
  const form = new FormData()
  form.append('file', file)
  return http.post(`/matching/positions/${id}/jd-import`, form, {
    timeout: 2 * 60 * 1000, // 覆盖 PDF/OCR 解析耗时
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total))
    },
  })
}

// 匹配结果列表 + 解释（M-3 / M-4）
export function listResults(params) {
  return http.get('/matching/results', { params })
}
export function getExplain(id, force) {
  return http.get(`/matching/result/${id}/explain`, { params: force ? { force: 1 } : {} })
}
// 储备人才保温更新（需求4）
export function updateWarm(id, warmLevel) {
  return http.put(`/matching/result/${id}/warm`, { warm_level: warmLevel })
}
// 批量保温（需求4）：统一设置多条匹配结果保温等级并刷新跟进时间
export function updateWarmBatch(matchIds, warmLevel) {
  return http.post('/matching/warm/batch', { match_ids: matchIds, warm_level: warmLevel })
}
// 匹配精度评估（需求2）
export function evaluateMatch(data) {
  return http.post('/matching/eval', data)
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
export function generateAlerts(params) {
  return http.post('/matching/alerts/generate', null, { params })
}

// ===== 岗位人才匹配 Agent（AI）=====
// 岗位智能解析
export function agentParse(data) {
  return http.post('/matching/agent/parse', data)
}

// 岗位→人才匹配
export function agentRun(data) {
  return http.post('/matching/agent/run', data)
}

// 人才→岗位反向匹配
export function agentReverse(data) {
  return http.post('/matching/agent/reverse', data)
}

// 自然语言操作
export function agentChat(data) {
  return http.post('/matching/agent/chat', data)
}

// 更新匹配结果状态（0候选 1推荐 2录用）
export function updateResultStatus(id, status) {
  return http.put(`/matching/result/${id}/status`, { status })
}
