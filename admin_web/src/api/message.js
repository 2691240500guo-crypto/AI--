import http from '@/utils/request'

// 消息中心（H01-H04）
export function listMyMessages(params) {
  return http.get('/messages', { params })
}
export function sendMessage(data) {
  return http.post('/messages/send', data)  // 按需求文档路径调用发送消息接口
}
export function markMessageRead(id) {
  return http.post(`/messages/${id}/read`, {})
}
export function getUnreadCount() {
  return http.get('/messages/unread-count')
}
export function getMessageDetail(id) {
  return http.get(`/messages/${id}`)
}
export function pushMessageReminder(id) {
  return http.post(`/messages/${id}/push-miniapp`, {})
}
