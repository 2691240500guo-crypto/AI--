import http from '@/utils/request'

// 角色管理（A05 RBAC）
export function listRoles(params) {
  return http.get('/roles', { params })
}
export function createRole(data) {
  return http.post('/roles', data)
}
export function updateRole(id, data) {
  return http.put(`/roles/${id}`, data)
}
export function deleteRole(id) {
  return http.delete(`/roles/${id}`)
}
