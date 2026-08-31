import http from '@/utils/request'

export function login(data) {
  return http.post('/auth/login', data)
}
export function refresh(data) {
  return http.post('/auth/refresh', data)
}
export function getMyMenus() {
  return http.get('/menus/mine')
}
export function logout() {
  return http.post('/auth/logout')
}