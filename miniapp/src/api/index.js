// miniapp 学生端 API 封装（走真实后端）
import request from '@/utils/request'

function req(options) {
  return request(options)
}

// 当前学生身份（demo 用 talent_id=11 王五，已有测评数据）
export const STUDENT_TALENT_ID = 11
export const currentTalentId = () => {
  const user = uni.getStorageSync('user') || {}
  return user.talent_id || user.talentId || user.talent?.id || STUDENT_TALENT_ID
}

// 测评
export const listMyTodos = () => req({ url: '/assessment/todo', data: { talent_id: currentTalentId() } })
export const listMyResults = () => req({ url: '/assessment/my-results' })
export const getMyResult = (rid) => req({ url: `/assessment/my-result/${rid}` })
export const getAnswerView = (rid) => req({ url: `/assessment/result/${rid}/answer` })
export const saveAnswer = (rid, answers) => req({ url: `/assessment/result/${rid}/answer`, method: 'POST', data: { answers } })
export const submitAnswer = (rid, answers) => req({ url: `/assessment/result/${rid}/submit`, method: 'POST', data: { answers } })
export const getReport = (rid) => req({ url: `/assessment/result/${rid}/report` })

// 人才档案
export const getTalent = (id) => req({ url: `/talent/${id}` })
export const getMyTalentProfile = () => req({ url: '/talent/me' })
export const getCurrentUser = () => req({ url: '/auth/me' })

// 消息中心（J06，对接 P1 msg_center，不接审计日志）
export const listMessages = (query = {}) => req({
  url: '/messages',
  data: { page: 1, page_size: 20, ...query }
})
export const getUnreadCount = () => req({ url: '/messages/unread-count' })
export const markMessageRead = (id) => req({ url: `/messages/${id}/read`, method: 'POST' })
export const markAllMessagesRead = () => req({ url: '/messages/read-all', method: 'POST' })
export const getMessageDetail = (id) => req({ url: `/messages/${id}` })

// 学习计划
export const listMyPlans = (talentId = currentTalentId()) => req({
  url: '/training/plans',
  data: { talent_id: talentId }
})
export const listTrainingCourses = (query = {}) => req({
  url: '/training/courses',
  data: { page: 1, page_size: 200, status: 1, ...query }
})
export const listCourseLessons = (courseId) => req({ url: `/training/courses/${courseId}/lessons` })
export const updateLearningProgress = (planId, payload) => req({
  url: `/training/plan/${planId}/progress`,
  method: 'PUT',
  data: {
    course_id: Number(payload.course_id),
    lesson_id: Number(payload.lesson_id) || 0,
    progress: Math.max(0, Math.min(100, Number(payload.progress) || 0)),
    learned_minutes: Math.max(0, Number(payload.learned_minutes) || 0)
  }
})

// NL2SQL 问数
export const askNL2SQL = (question) => req({ url: `/analytics/nl2sql`, method: 'POST', data: { question } })
export const askAiAssistant = (message, chartType = 'bar') => req({
  url: '/ai/chat',
  method: 'POST',
  data: { message, chart_type: chartType }
})
export const listAiConversations = (query = {}) => req({
  url: '/ai/conversations',
  data: { page: 1, page_size: 20, ...query }
})
