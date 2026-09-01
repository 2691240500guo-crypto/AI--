import http from '@/utils/request'

// 消息中心（H01-H04）
export function listMyMessages(params) {
  return http.get('/messages', { params })
}
export function sendMessage(data) {
  return http.post('/messages', data)
}
export function markMessageRead(id) {
  return http.post(`/messages/${id}/read`, {})
}
export function getUnreadCount() {
  return http.get('/messages/unread-count')
}
