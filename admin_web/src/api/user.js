import http from '@/utils/request'

// 用户管理（system:user）示例 —— 后来者照抄此文件写其他模块 API
export function listUsers(params) {
  return http.get('/users', { params })
}
export function getUser(id) {
  return http.get(`/users/${id}`)
}
export function createUser(data) {
  return http.post('/users', data)
}
export function updateUser(id, data) {
  return http.put(`/users/${id}`, data)
}
export function deleteUser(id) {
  return http.delete(`/users/${id}`)
}