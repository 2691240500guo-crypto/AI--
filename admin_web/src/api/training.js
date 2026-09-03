/**
 * 智能培训模块 API —— 真实后端接口版
 * 后端路由：/api/v1/training/*（app/routers/training.py）
 *
 * 枚举约定（与后端 int 状态的映射，团队需统一知晓）：
 * - 课程 status：0=已下架(offline) 1=已上架(published) 2=草稿(draft)   （模型原有 1上架/0下架，扩展 2=草稿）
 * - 计划 status：0=未开始 1=进行中 2=已完成 3=已逾期
 * - 标签/课程ID 在库里是逗号分隔字符串，接口层做 数组<->字符串 转换
 */
import http from '@/utils/request'

const courseStatusMap = {
  published: '已上架',
  draft: '草稿',
  offline: '已下架'
}

const planStatusMap = {
  not_started: '未开始',
  in_progress: '进行中',
  done: '已完成',
  overdue: '已逾期'
}

const courseStatusToInt = { published: 1, draft: 2, offline: 0 }
const courseStatusFromInt = { 1: 'published', 2: 'draft', 0: 'offline' }
const planStatusToInt = { not_started: 0, in_progress: 1, done: 2, overdue: 3 }
const planStatusFromInt = { 0: 'not_started', 1: 'in_progress', 2: 'done', 3: 'overdue' }

function splitTags(value) {
  return String(value || '')
    .split(/[,，]+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function splitIds(value) {
  return String(value || '')
    .split(/[,，]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map(Number)
    .filter((n) => !Number.isNaN(n))
}

function toDate(value) {
  return value ? String(value).slice(0, 10) : ''
}

function normalizeLessons(lessons) {
  return (lessons || [])
    .map((lesson) => ({
      id: lesson.id || null,
      title: lesson.title || '',
      duration: Number(lesson.duration) || 0,
      file_url: lesson.file_url || '',
      video_id: lesson.video_id ? Number(lesson.video_id) : null
    }))
    .filter((lesson) => lesson.title)
}

// ---------- 字典 ----------

export function getTrainingDictionaries() {
  return {
    categories: ['技术', '管理', '通识', '认证'],
    courseStatus: courseStatusMap,
    planStatus: planStatusMap
  }
}

// ---------- 课程库 ----------

export async function listCourses(query = {}) {
  const params = {
    page: Number(query.page) || 1,
    page_size: Number(query.page_size) || 10
  }
  if (query.keyword) params.keyword = query.keyword
  if (query.category) params.category = query.category
  if (query.status !== '' && query.status != null) {
    params.status = courseStatusToInt[query.status] ?? query.status
  }
  const res = await http.get('/training/courses', { params })
  const items = (res.data.items || []).map((course) => {
    const statusKey = courseStatusFromInt[course.status] || 'draft'
    return {
      ...course,
      allow_tags: splitTags(course.allow_tags),
      status: statusKey,
      status_label: courseStatusMap[statusKey] || String(course.status),
      updated_at: toDate(course.updated_at || course.created_at),
      lessons: (course.lessons || []).map((lesson) => ({
        id: lesson.id,
        title: lesson.title,
        duration: lesson.duration,
        file_url: lesson.file_url || '',
        video_id: lesson.video_id ? Number(lesson.video_id) : null
      }))
    }
  })
  return { data: { items, meta: res.data.meta } }
}

export async function listCourseOptions() {
  const res = await http.get('/training/courses', { params: { page: 1, page_size: 200 } })
  const items = (res.data.items || [])
    .filter((course) => course.status !== 0)
    .map((course) => ({
      id: course.id,
      title: course.title,
      category: course.category,
      score: course.score
    }))
  return { data: items }
}

export async function createCourse(body) {
  const res = await http.post('/training/courses', {
    title: body.title,
    category: body.category,
    score: Number(body.score) || 0,
    intro: body.intro || '',
    allow_tags: body.allow_tags || '',
    status: courseStatusToInt[body.status] ?? 2
  })
  const course = res.data
  // 课节随课程一起保存（全量同步）
  const lessons = normalizeLessons(body.lessons)
  if (lessons.length) {
    await http.put(`/training/courses/${course.id}/lessons`, { lessons })
  }
  return { data: course }
}

export async function updateCourse(id, body) {
  await http.put(`/training/courses/${id}`, {
    title: body.title,
    category: body.category,
    score: Number(body.score) || 0,
    intro: body.intro || '',
    allow_tags: body.allow_tags || '',
    status: courseStatusToInt[body.status] ?? 2
  })
  // 课节全量同步：带 id 更新、无 id 新增、缺席删除
  const res = await http.put(`/training/courses/${id}/lessons`, {
    lessons: normalizeLessons(body.lessons)
  })
  return { data: res.data }
}

export async function deleteCourse(id) {
  await http.delete(`/training/courses/${id}`)
  return { data: null }
}

// ---------- 人才下拉（学习计划选择人员）----------

export async function listTalentOptions(keyword = '', options = {}) {
  const params = {}
  if (keyword) params.keyword = keyword
  if (options.messageRecipientOnly) params.message_recipient_only = true
  const res = await http.get('/training/talents', {
    params
  })
  return { data: res.data || [] }
}

// ---------- 学习计划 ----------

function decoratePlan(plan, courseMap) {
  const course_ids = splitIds(plan.course_ids)
  const records = (plan.records || []).map((record) => ({
    course_id: record.course_id,
    progress: Number(record.progress) || 0,
    learned_minutes: Number(record.learned_minutes) || 0,
    last_lesson: '',
    exam_score: null
  }))
  const course_names = course_ids.map((id) => courseMap.get(id)?.title || `课程#${id}`)
  const progress = records.length
    ? Math.round(records.reduce((sum, row) => sum + row.progress, 0) / records.length)
    : 0
  const learned_hours = records.reduce((sum, row) => {
    const course = courseMap.get(row.course_id)
    return sum + ((course?.score || 0) * (row.progress / 100))
  }, 0)
  const statusKey = planStatusFromInt[plan.status] || 'not_started'

  return {
    ...plan,
    talent_id: plan.talent_id,
    talent_name: plan.talent_name || `人才#${plan.talent_id}`,
    course_ids,
    weakness_tags: splitTags(plan.weakness_tags),
    records,
    course_names,
    progress,
    learned_hours: Number(learned_hours.toFixed(1)),
    exam_avg: plan.exam_avg === undefined ? null : plan.exam_avg,
    status: statusKey,
    status_label: planStatusMap[statusKey] || String(plan.status),
    deadline: toDate(plan.deadline),
    source_label: plan.source === 'agent' ? 'Agent 生成' : '手动创建'
  }
}

export async function listPlans(query = {}) {
  const [planRes, courseRes] = await Promise.all([
    http.get('/training/plans'),
    http.get('/training/courses', { params: { page: 1, page_size: 200 } })
  ])
  const courseMap = new Map(
    (courseRes.data.items || []).map((course) => [course.id, course])
  )
  let rows = (planRes.data || []).map((plan) => decoratePlan(plan, courseMap))

  const keyword = String(query.keyword || '').trim().toLowerCase()
  if (keyword) {
    rows = rows.filter((plan) => {
      const text = [
        plan.title,
        plan.talent_name,
        plan.generated_by,
        ...plan.weakness_tags,
        ...plan.course_names
      ].join(' ').toLowerCase()
      return text.includes(keyword)
    })
  }
  if (query.status) rows = rows.filter((plan) => plan.status === query.status)
  if (query.source) rows = rows.filter((plan) => plan.source === query.source)

  const page = Number(query.page) || 1
  const pageSize = Number(query.page_size) || 10
  const total = rows.length
  const start = (page - 1) * pageSize
  return {
    data: {
      items: rows.slice(start, start + pageSize),
      meta: { page, page_size: pageSize, total }
    }
  }
}

export async function createPlan(body) {
  const res = await http.post('/training/plans', {
    talent_id: Number(body.talent_id),
    title: body.title,
    course_ids: (body.course_ids || []).map(Number),
    weakness_tags: splitTags(body.weakness_tags),
    deadline: body.deadline || null,
    status: planStatusToInt[body.status] ?? 0,
    generated_by: body.generated_by || '管理员',
    improvement: Number(body.improvement) || 0,
    push: body.notify_employee !== false
  })
  return { data: res.data }
}

export async function updatePlan(id, body) {
  const res = await http.put(`/training/plans/${id}`, {
    title: body.title,
    course_ids: (body.course_ids || []).map(Number),
    weakness_tags: splitTags(body.weakness_tags),
    status: planStatusToInt[body.status] ?? 0,
    deadline: body.deadline || null,
    generated_by: body.generated_by || '',
    improvement: Number(body.improvement) || 0
  })
  return { data: res.data }
}

export async function updatePlanRecords(id, records, status) {
  // 逐课程更新进度（learned_minutes 保留库中原值）
  for (const record of records || []) {
    await http.put(`/training/plan/${id}/progress`, {
      course_id: Number(record.course_id),
      lesson_id: 0,
      progress: Number(record.progress) || 0,
      learned_minutes: Number(record.learned_minutes) || 0
    })
  }
  // 更新计划状态
  if (status) {
    await http.put(`/training/plans/${id}`, { status: planStatusToInt[status] ?? 1 })
  }
  return { data: null }
}

export async function deletePlan(id) {
  await http.delete(`/training/plans/${id}`)
  return { data: null }
}

// ---------- 效果分析 ----------

export async function getTrainingEffects() {
  const res = await http.get('/training/effects/full')
  return { data: res.data }
}
