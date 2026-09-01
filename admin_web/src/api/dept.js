import http from '@/utils/request'

// 部门/组织架构管理（A07）
export function listDepts() {
  return http.get('/depts')
}
export function createDept(data) {
  return http.post('/depts', data)
}
export function updateDept(id, data) {
  return http.put(`/depts/${id}`, data)
}
export function deleteDept(id) {
  return http.delete(`/depts/${id}`)
}
