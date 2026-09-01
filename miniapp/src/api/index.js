// miniapp 学生端 API 封装（走真实后端）
const BASE = 'http://127.0.0.1:8000/api/v1'

function req(options) {
  return new Promise((resolve, reject) => {
    const token = uni.getStorageSync('token')
    uni.request({
      url: BASE + options.url,
      method: options.method || 'GET',
      data: options.data || {},
      header: { Authorization: token ? `Bearer ${token}` : '' },
      success: (res) => {
        const body = res.data
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

// 当前学生身份（demo 用 talent_id=11 王五，已有测评数据）
export const STUDENT_TALENT_ID = 11
export const currentTalentId = () => uni.getStorageSync('user')?.talent_id || STUDENT_TALENT_ID

// 测评
export const listMyTodos = () => req({ url: `/assessment/todo?talent_id=${currentTalentId()}` })
export const listMyResults = () => req({ url: `/assessment/results?talent_id=${currentTalentId()}` })
export const getAnswerView = (rid) => req({ url: `/assessment/results/${rid}/answer` })
export const submitAnswer = (rid, payload) => req({ url: `/assessment/results/${rid}/submit`, method: 'POST', data: payload })
export const getReport = (rid) => req({ url: `/assessment/results/${rid}/report` })

// 人才档案
export const getTalent = (id) => req({ url: `/talent/${id}` })

// 学习计划
export const listMyPlans = () => req({ url: `/training/plans?talent_id=${currentTalentId()}` })

// NL2SQL 问数
export const askNL2SQL = (question) => req({ url: `/analytics/nl2sql`, method: 'POST', data: { question } })
