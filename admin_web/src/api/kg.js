// M1 知识图谱 API（与后端 app/routers/kg.py 对齐，挂在 /api/v1/kg 下）
import http from '@/utils/request'

// 单人才画像关系网（1 跳子图，ECharts graph 直接消费）
export function getTalentGraph(id) {
  return http.get(`/kg/talent/${id}/graph`)
}

// 子图相似人才（共享技能/标签/项目加权计分）
export function getTalentSimilar(id, limit = 5) {
  return http.post(`/kg/talent/${id}/similar`, null, { params: { limit } })
}

// 全量重建图谱（存量人才一键图谱化，验收/演示用；权限 talent:manage）
export function syncAllKg() {
  return http.post('/kg/sync-all')
}
