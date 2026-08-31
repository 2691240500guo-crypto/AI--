const STORAGE_KEY = 'ai-talent-training-admin-v1'

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

const seedState = {
  courses: [
    {
      id: 1001,
      title: 'AI 办公提效实战',
      category: '通识',
      level: '入门',
      score: 6,
      lecturer: '数字化人才学院',
      rating: 4.7,
      status: 'published',
      allow_tags: ['AI工具', '效率提升', '办公自动化'],
      intro: '围绕文档、表格、汇报和知识检索场景，帮助员工掌握 AI 办公工作流。',
      lessons: [
        { title: '提示词基础与安全边界', duration: 45, file_url: 'course-files/ai-office/lesson-1.mp4' },
        { title: '表格分析与汇报自动化', duration: 60, file_url: 'course-files/ai-office/lesson-2.pdf' },
        { title: '个人知识库搭建', duration: 50, file_url: 'course-files/ai-office/lesson-3.mp4' }
      ],
      updated_at: '2026-08-31'
    },
    {
      id: 1002,
      title: '数据分析与经营看板',
      category: '技术',
      level: '进阶',
      score: 8,
      lecturer: '数据中台组',
      rating: 4.6,
      status: 'published',
      allow_tags: ['数据分析', '经营指标', '可视化'],
      intro: '覆盖指标拆解、SQL 分析、可视化表达和业务复盘，提升数据驱动决策能力。',
      lessons: [
        { title: '核心指标口径设计', duration: 55, file_url: 'course-files/data-dashboard/lesson-1.pdf' },
        { title: '分析查询与异常定位', duration: 70, file_url: 'course-files/data-dashboard/lesson-2.mp4' },
        { title: '看板讲述与复盘', duration: 45, file_url: 'course-files/data-dashboard/lesson-3.pdf' }
      ],
      updated_at: '2026-08-31'
    },
    {
      id: 1003,
      title: '项目经理 AI 协同工作坊',
      category: '管理',
      level: '进阶',
      score: 5,
      lecturer: 'PMO',
      rating: 4.5,
      status: 'published',
      allow_tags: ['项目管理', '跨部门协作', '风险识别'],
      intro: '训练项目计划拆解、会议纪要、风险跟踪和跨部门协同中的 AI 辅助方法。',
      lessons: [
        { title: '需求拆解与任务跟踪', duration: 50, file_url: 'course-files/pm-ai/lesson-1.mp4' },
        { title: '会议纪要与风险清单', duration: 40, file_url: 'course-files/pm-ai/lesson-2.pdf' }
      ],
      updated_at: '2026-08-30'
    },
    {
      id: 1004,
      title: '生成式 AI 应用安全',
      category: '认证',
      level: '高级',
      score: 7,
      lecturer: '安全合规部',
      rating: 4.8,
      status: 'draft',
      allow_tags: ['安全合规', '数据保护', 'AI治理'],
      intro: '面向 AI 应用使用与建设中的数据安全、权限控制、提示注入和审计要求。',
      lessons: [
        { title: 'AI 数据安全红线', duration: 45, file_url: 'course-files/ai-security/lesson-1.pdf' },
        { title: '提示注入与越权防护', duration: 65, file_url: 'course-files/ai-security/lesson-2.mp4' }
      ],
      updated_at: '2026-08-29'
    }
  ],
  plans: [
    {
      id: 2001,
      title: '张敏 AI 办公能力提升计划',
      talent_name: '张敏',
      dept: '人力资源部',
      target_role: 'HRBP',
      weakness_tags: ['AI工具', '数据分析'],
      course_ids: [1001, 1002],
      source: 'agent',
      status: 'in_progress',
      deadline: '2026-09-15',
      generated_by: 'Agent④',
      improvement: 12,
      records: [
        { course_id: 1001, progress: 85, exam_score: 88, last_lesson: '个人知识库搭建' },
        { course_id: 1002, progress: 40, exam_score: null, last_lesson: '核心指标口径设计' }
      ],
      created_at: '2026-08-31'
    },
    {
      id: 2002,
      title: '李强 数据化项目管理计划',
      talent_name: '李强',
      dept: '项目管理部',
      target_role: '项目经理',
      weakness_tags: ['项目管理', '经营指标'],
      course_ids: [1002, 1003],
      source: 'manual',
      status: 'in_progress',
      deadline: '2026-09-20',
      generated_by: '何然',
      improvement: 9,
      records: [
        { course_id: 1002, progress: 65, exam_score: 76, last_lesson: '分析查询与异常定位' },
        { course_id: 1003, progress: 55, exam_score: 82, last_lesson: '会议纪要与风险清单' }
      ],
      created_at: '2026-08-30'
    },
    {
      id: 2003,
      title: '王璐 新员工 AI 通识训练',
      talent_name: '王璐',
      dept: '产品部',
      target_role: '产品助理',
      weakness_tags: ['AI工具', '效率提升'],
      course_ids: [1001],
      source: 'agent',
      status: 'done',
      deadline: '2026-08-31',
      generated_by: 'Agent④',
      improvement: 18,
      records: [
        { course_id: 1001, progress: 100, exam_score: 91, last_lesson: '个人知识库搭建' }
      ],
      created_at: '2026-08-25'
    },
    {
      id: 2004,
      title: '陈晨 AI 安全认证预学习',
      talent_name: '陈晨',
      dept: '研发中心',
      target_role: 'AI 应用工程师',
      weakness_tags: ['安全合规', 'AI治理'],
      course_ids: [1004],
      source: 'manual',
      status: 'not_started',
      deadline: '2026-09-30',
      generated_by: '何然',
      improvement: 0,
      records: [
        { course_id: 1004, progress: 0, exam_score: null, last_lesson: '' }
      ],
      created_at: '2026-08-31'
    }
  ],
  trends: [
    { month: '4月', hours: 42, pass_rate: 72, improvement: 7 },
    { month: '5月', hours: 58, pass_rate: 76, improvement: 9 },
    { month: '6月', hours: 71, pass_rate: 81, improvement: 10 },
    { month: '7月', hours: 86, pass_rate: 84, improvement: 13 },
    { month: '8月', hours: 112, pass_rate: 88, improvement: 15 }
  ]
}

function clone(data) {
  return JSON.parse(JSON.stringify(data))
}

function loadState() {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    const state = clone(seedState)
    saveState(state)
    return state
  }
  try {
    return JSON.parse(raw)
  } catch {
    const state = clone(seedState)
    saveState(state)
    return state
  }
}

function saveState(state) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function nextId(rows) {
  return rows.length ? Math.max(...rows.map((row) => Number(row.id) || 0)) + 1 : 1
}

function paginate(rows, page = 1, pageSize = 10) {
  const total = rows.length
  const start = (page - 1) * pageSize
  return {
    items: rows.slice(start, start + pageSize),
    meta: { page, page_size: pageSize, total }
  }
}

function normalizeTags(value) {
  if (Array.isArray(value)) return value.filter(Boolean)
  return String(value || '')
    .split(/[,，\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function normalizeLessons(lessons) {
  return (lessons || [])
    .map((lesson) => ({
      title: lesson.title || '',
      duration: Number(lesson.duration) || 0,
      file_url: lesson.file_url || ''
    }))
    .filter((lesson) => lesson.title)
}

function getCourseMap(courses) {
  return new Map(courses.map((course) => [course.id, course]))
}

function decoratePlan(plan, courses) {
  const courseMap = getCourseMap(courses)
  const course_names = plan.course_ids.map((id) => courseMap.get(id)?.title || `课程#${id}`)
  const records = plan.records || []
  const progress = records.length
    ? Math.round(records.reduce((sum, row) => sum + (Number(row.progress) || 0), 0) / records.length)
    : 0
  const learned_hours = records.reduce((sum, row) => {
    const course = courseMap.get(row.course_id)
    return sum + ((course?.score || 0) * ((Number(row.progress) || 0) / 100))
  }, 0)
  const examRows = records.filter((row) => row.exam_score !== null && row.exam_score !== undefined && row.exam_score !== '')
  const exam_avg = examRows.length
    ? Math.round(examRows.reduce((sum, row) => sum + Number(row.exam_score), 0) / examRows.length)
    : null

  return {
    ...plan,
    course_names,
    progress,
    learned_hours: Number(learned_hours.toFixed(1)),
    exam_avg,
    status_label: planStatusMap[plan.status] || plan.status,
    source_label: plan.source === 'agent' ? 'Agent 生成' : '手动创建'
  }
}

export function getTrainingDictionaries() {
  return {
    categories: ['技术', '管理', '通识', '认证'],
    levels: ['入门', '进阶', '高级'],
    courseStatus: courseStatusMap,
    planStatus: planStatusMap
  }
}

export async function listCourses(query = {}) {
  const state = loadState()
  const keyword = String(query.keyword || '').trim().toLowerCase()
  const page = Number(query.page) || 1
  const pageSize = Number(query.page_size) || 10
  let rows = state.courses.map((course) => ({
    ...course,
    lesson_count: course.lessons?.length || 0,
    status_label: courseStatusMap[course.status] || course.status
  }))

  if (keyword) {
    rows = rows.filter((course) => {
      const text = [
        course.title,
        course.category,
        course.level,
        course.lecturer,
        course.intro,
        ...(course.allow_tags || [])
      ].join(' ').toLowerCase()
      return text.includes(keyword)
    })
  }
  if (query.category) rows = rows.filter((course) => course.category === query.category)
  if (query.status) rows = rows.filter((course) => course.status === query.status)
  rows = rows.sort((a, b) => b.id - a.id)
  return { data: paginate(rows, page, pageSize) }
}

export async function listCourseOptions() {
  const state = loadState()
  return {
    data: state.courses
      .filter((course) => course.status !== 'offline')
      .map((course) => ({
        id: course.id,
        title: course.title,
        category: course.category,
        score: course.score
      }))
  }
}

export async function createCourse(body) {
  const state = loadState()
  const now = new Date().toISOString().slice(0, 10)
  const course = {
    id: nextId(state.courses),
    title: body.title,
    category: body.category,
    level: body.level,
    score: Number(body.score) || 0,
    lecturer: body.lecturer || '',
    rating: Number(body.rating) || 0,
    status: body.status || 'draft',
    allow_tags: normalizeTags(body.allow_tags),
    intro: body.intro || '',
    lessons: normalizeLessons(body.lessons),
    updated_at: now
  }
  state.courses.push(course)
  saveState(state)
  return { data: course }
}

export async function updateCourse(id, body) {
  const state = loadState()
  const index = state.courses.findIndex((course) => course.id === id)
  if (index < 0) throw new Error('课程不存在')
  const now = new Date().toISOString().slice(0, 10)
  state.courses[index] = {
    ...state.courses[index],
    ...body,
    id,
    score: Number(body.score) || 0,
    rating: Number(body.rating) || 0,
    allow_tags: normalizeTags(body.allow_tags),
    lessons: normalizeLessons(body.lessons),
    updated_at: now
  }
  saveState(state)
  return { data: state.courses[index] }
}

export async function deleteCourse(id) {
  const state = loadState()
  state.courses = state.courses.filter((course) => course.id !== id)
  state.plans = state.plans.map((plan) => ({
    ...plan,
    course_ids: plan.course_ids.filter((courseId) => courseId !== id),
    records: (plan.records || []).filter((record) => record.course_id !== id)
  }))
  saveState(state)
  return { data: null }
}

export async function listPlans(query = {}) {
  const state = loadState()
  const keyword = String(query.keyword || '').trim().toLowerCase()
  const page = Number(query.page) || 1
  const pageSize = Number(query.page_size) || 10
  let rows = state.plans.map((plan) => decoratePlan(plan, state.courses))

  if (keyword) {
    rows = rows.filter((plan) => {
      const text = [
        plan.title,
        plan.talent_name,
        plan.dept,
        plan.target_role,
        plan.generated_by,
        ...(plan.weakness_tags || []),
        ...(plan.course_names || [])
      ].join(' ').toLowerCase()
      return text.includes(keyword)
    })
  }
  if (query.status) rows = rows.filter((plan) => plan.status === query.status)
  if (query.source) rows = rows.filter((plan) => plan.source === query.source)
  rows = rows.sort((a, b) => b.id - a.id)
  return { data: paginate(rows, page, pageSize) }
}

export async function createPlan(body) {
  const state = loadState()
  const courseIds = (body.course_ids || []).map(Number)
  const plan = {
    id: nextId(state.plans),
    title: body.title,
    talent_name: body.talent_name,
    dept: body.dept || '',
    target_role: body.target_role || '',
    weakness_tags: normalizeTags(body.weakness_tags),
    course_ids: courseIds,
    source: body.source || 'manual',
    status: body.status || 'not_started',
    deadline: body.deadline || '',
    generated_by: body.generated_by || '管理员',
    improvement: Number(body.improvement) || 0,
    records: courseIds.map((courseId) => ({ course_id: courseId, progress: 0, exam_score: null, last_lesson: '' })),
    created_at: new Date().toISOString().slice(0, 10)
  }
  state.plans.push(plan)
  saveState(state)
  return { data: plan }
}

export async function updatePlan(id, body) {
  const state = loadState()
  const index = state.plans.findIndex((plan) => plan.id === id)
  if (index < 0) throw new Error('学习计划不存在')
  const oldPlan = state.plans[index]
  const courseIds = (body.course_ids || []).map(Number)
  const oldRecordMap = new Map((oldPlan.records || []).map((record) => [record.course_id, record]))
  state.plans[index] = {
    ...oldPlan,
    ...body,
    id,
    weakness_tags: normalizeTags(body.weakness_tags),
    course_ids: courseIds,
    improvement: Number(body.improvement) || 0,
    records: courseIds.map((courseId) => oldRecordMap.get(courseId) || {
      course_id: courseId,
      progress: 0,
      exam_score: null,
      last_lesson: ''
    })
  }
  saveState(state)
  return { data: state.plans[index] }
}

export async function updatePlanRecords(id, records, status) {
  const state = loadState()
  const index = state.plans.findIndex((plan) => plan.id === id)
  if (index < 0) throw new Error('学习计划不存在')
  const normalized = records.map((record) => ({
    course_id: Number(record.course_id),
    progress: Number(record.progress) || 0,
    exam_score: record.exam_score === '' || record.exam_score === null || record.exam_score === undefined
      ? null
      : Number(record.exam_score),
    last_lesson: record.last_lesson || ''
  }))
  const allDone = normalized.length > 0 && normalized.every((record) => Number(record.progress) >= 100)
  state.plans[index] = {
    ...state.plans[index],
    records: normalized,
    status: status || (allDone ? 'done' : 'in_progress')
  }
  saveState(state)
  return { data: state.plans[index] }
}

export async function deletePlan(id) {
  const state = loadState()
  state.plans = state.plans.filter((plan) => plan.id !== id)
  saveState(state)
  return { data: null }
}

export async function getTrainingEffects() {
  const state = loadState()
  const courses = state.courses
  const plans = state.plans.map((plan) => decoratePlan(plan, courses))
  const records = plans.flatMap((plan) => (plan.records || []).map((record) => ({ ...record, plan })))
  const learnedHours = plans.reduce((sum, plan) => sum + plan.learned_hours, 0)
  const examRows = records.filter((record) => record.exam_score !== null && record.exam_score !== undefined && record.exam_score !== '')
  const passedRows = examRows.filter((record) => Number(record.exam_score) >= 60)
  const donePlans = plans.filter((plan) => plan.status === 'done')
  const completedRate = plans.length ? Math.round((donePlans.length / plans.length) * 100) : 0
  const passRate = examRows.length ? Math.round((passedRows.length / examRows.length) * 100) : 0
  const avgProgress = plans.length
    ? Math.round(plans.reduce((sum, plan) => sum + plan.progress, 0) / plans.length)
    : 0
  const avgImprovement = plans.length
    ? Math.round(plans.reduce((sum, plan) => sum + (Number(plan.improvement) || 0), 0) / plans.length)
    : 0

  const categoryMap = new Map()
  const courseMap = getCourseMap(courses)
  for (const record of records) {
    const course = courseMap.get(record.course_id)
    if (!course) continue
    const current = categoryMap.get(course.category) || { name: course.category, hours: 0, count: 0 }
    current.hours += (course.score || 0) * ((Number(record.progress) || 0) / 100)
    current.count += 1
    categoryMap.set(course.category, current)
  }

  const statusData = Object.keys(planStatusMap).map((status) => ({
    status,
    name: planStatusMap[status],
    count: plans.filter((plan) => plan.status === status).length
  }))

  const ranking = courses.map((course) => {
    const courseRecords = records.filter((record) => record.course_id === course.id)
    const examRecords = courseRecords.filter((record) => record.exam_score !== null && record.exam_score !== undefined && record.exam_score !== '')
    const pass = examRecords.filter((record) => Number(record.exam_score) >= 60)
    const hours = courseRecords.reduce((sum, record) => sum + ((course.score || 0) * ((Number(record.progress) || 0) / 100)), 0)
    return {
      id: course.id,
      title: course.title,
      category: course.category,
      learner_count: courseRecords.length,
      learned_hours: Number(hours.toFixed(1)),
      pass_rate: examRecords.length ? Math.round((pass.length / examRecords.length) * 100) : 0,
      rating: course.rating
    }
  }).sort((a, b) => b.learned_hours - a.learned_hours)

  return {
    data: {
      summary: {
        course_count: courses.length,
        plan_count: plans.length,
        learned_hours: Number(learnedHours.toFixed(1)),
        completed_rate: completedRate,
        pass_rate: passRate,
        avg_progress: avgProgress,
        avg_improvement: avgImprovement
      },
      category_hours: Array.from(categoryMap.values()).map((row) => ({ ...row, hours: Number(row.hours.toFixed(1)) })),
      status_data: statusData,
      trends: clone(state.trends),
      ranking,
      talent_effects: plans.map((plan) => ({
        id: plan.id,
        title: plan.title,
        talent_name: plan.talent_name,
        dept: plan.dept,
        progress: plan.progress,
        learned_hours: plan.learned_hours,
        exam_avg: plan.exam_avg,
        improvement: plan.improvement,
        status_label: plan.status_label
      }))
    }
  }
}
