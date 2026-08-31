// 请求封装：带 token、统一响应、401 续期（小程序版）
const BASE_URL = 'http://127.0.0.1:8000/api'

export function request(options) {
  return new Promise((resolve, reject) => {
    const token = uni.getStorageSync('token')
    uni.request({
      url: BASE_URL + options.url,
      method: options.method || 'GET',
      data: options.data || {},
      header: { Authorization: token ? `Bearer ${token}` : '', ...(options.header || {}) },
      success: async (res) => {
        const body = res.data
        if (res.statusCode === 401 || (body && body.code === 401)) {
          const ok = await tryRefresh()
          if (ok) { resolve(request(options)); return }
          uni.removeStorageSync('token')
          uni.navigateTo({ url: '/pages/login/login' })
          reject(body)
          return
        }
        if (body && body.code !== 0) {
          uni.showToast({ title: body.message || '请求失败', icon: 'none' })
          reject(body)
          return
        }
        resolve(body)
      },
      fail: reject
    })
  })
}

function tryRefresh() {
  return new Promise((resolve) => {
    const rt = uni.getStorageSync('refresh_token')
    if (!rt) return resolve(false)
    uni.request({
      url: `${BASE_URL}/auth/refresh`,
      method: 'POST',
      data: { refresh_token: rt },
      success: (res) => {
        const body = res.data
        if (body && body.code === 0) {
          uni.setStorageSync('token', body.data.access_token)
          uni.setStorageSync('refresh_token', body.data.refresh_token)
          resolve(true)
        } else resolve(false)
      },
      fail: () => resolve(false)
    })
  })
}

export default request