import http from '@/utils/request'

// 菜单/权限码管理（A06）
export function listMenus() {
  return http.get('/menus')
}
export function createMenu(data) {
  return http.post('/menus', data)
}
export function updateMenu(id, data) {
  return http.put(`/menus/${id}`, data)
}
export function deleteMenu(id) {
  return http.delete(`/menus/${id}`)
}
