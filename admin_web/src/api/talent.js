import http from '@/utils/request'

// 人才档案（T 域，需求文档 3.3 接口；后端由人才域 P2 提供）
export function listTalents(params) { return http.get('/talent', { params }) }
export function getTalent(id) { return http.get(`/talent/${id}`) }
export function createTalent(data) { return http.post('/talent', data) }
export function updateTalent(id, data) { return http.put(`/talent/${id}`, data) }
export function deleteTalent(id) { return http.delete(`/talent/${id}`) }
export function exportTalents(params) { return http.get('/talent/export', { params }) }
export function importTalents(data) { return http.post('/talent/import', data) }
export function setTalentTags(id, data) { return http.post(`/talent/${id}/tags`, data) }
export function checkDuplicate(data) { return http.post('/talent/check-duplicate', data) }
export function parseResume(data) { return http.post('/talent/parse-resume', data) }
