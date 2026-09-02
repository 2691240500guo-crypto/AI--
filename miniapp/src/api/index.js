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
export const listMyResults = () => req({ url: '/assessment/results', data: { talent_id: currentTalentId() } })
export const getAnswerView = (rid) => req({ url: `/assessment/results/${rid}/answer` })
export const submitAnswer = (rid, payload) => req({ url: `/assessment/results/${rid}/submit`, method: 'POST', data: payload })
export const getReport = (rid) => req({ url: `/assessment/results/${rid}/report` })

// 人才档案
export const getTalent = (id) => req({ url: `/talent/${id}` })

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
