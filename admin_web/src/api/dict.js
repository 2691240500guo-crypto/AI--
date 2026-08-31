import http from '@/utils/request'

// 数据字典（A11）
export function listDictTypes() {
  return http.get('/dicts/types')
}
export function createDictType(data) {
  return http.post('/dicts/types', data)
}
export function listDictItems(typeCode) {
  return http.get(`/dicts/items/${typeCode}`)
}
export function createDictItem(data) {
  return http.post('/dicts/items', data)
}
export function deleteDictItem(id) {
  return http.delete(`/dicts/items/${id}`)
}
