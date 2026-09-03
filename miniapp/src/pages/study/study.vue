<script setup>
import { computed, onMounted, ref } from 'vue'
import { onPullDownRefresh } from '@dcloudio/uni-app'
import {
  currentTalentId,
  getCourseVideoStreamUrl,
  listCourseLessons,
  listMyPlans,
  listOnlineCourses,
  listTrainingCourses,
  reportOnlineCourseProgress,
  updateLearningProgress
} from '@/api'
import GrowthPath from '@/components/GrowthPath.vue'
import UiState from '@/components/UiState.vue'

const loading = ref(false)
const lessonLoading = ref(false)
const updating = ref(false)
const onlineCourses = ref([])
const plans = ref([])
const courses = ref([])
const selectedKey = ref('')
const selectedLessonId = ref(0)
const watchSecond = ref(0)
const videoDurationSecond = ref(0)
const lastReportSecond = ref(0)
const loadedLessonCourses = new Set()

const planStatusText = { 0: '未开始', 1: '进行中', 2: '已完成', 3: '已逾期' }

const courseCards = computed(() => {
  // 合并三处来源：① 在线视频课（video_ready）；② 培训计划拆解的课程；③ 课程库兜底
  // 修复: 原版"有 video_ready 就 early-return"会完全跳过 plan，导致培训计划课程永远不显示
  const onlineRows = onlineCourses.value.map(buildOnlineCourseCard).filter((course) => course.video_ready)
  const courseMap = new Map(courses.value.map((course) => [course.id, course]))
  const planRows = []
  plans.value.forEach((plan) => {
    splitIds(plan.course_ids).forEach((courseId) => {
      const course = courseMap.get(courseId)
      if (!course) return
      const record = (plan.records || []).find((item) => Number(item.course_id) === courseId)
      planRows.push(buildCourseCard(course, plan, record))
    })
  })
  // 按 video_id 去重（在线视频课核心标识），无 video_id 的计划拆解课程按 id 去重
  // 彻底修复：同一视频/课程被多 plan 引用或 online 接口去重未到位时都不重复展示
  const merged = [...planRows, ...onlineRows]
  const seen = new Set()
  const dedup = []
  for (const c of merged) {
    const key = c.video_id != null ? `v:${c.video_id}` : `c:${c.id}`
    if (seen.has(key)) continue
    seen.add(key)
    dedup.push(c)
  }
  if (dedup.length) return dedup
  return courses.value.map((course) => buildCourseCard(course, null, null))
})

const summary = computed(() => {
  const total = courseCards.value.length
  const completed = courseCards.value.filter((course) => course.progress >= 100).length
  const learnedMinutes = courseCards.value.reduce((sum, course) => sum + course.learned_minutes, 0)
  const avgProgress = total
    ? Math.round(courseCards.value.reduce((sum, course) => sum + course.progress, 0) / total)
    : 0
  return { total, completed, learnedMinutes, avgProgress }
})

const learningSteps = computed(() => [
  { label: '诊断', mark: '诊', status: summary.value.total ? 'done' : 'todo', caption: '识别短板' },
  { label: '推荐', mark: '荐', status: summary.value.total ? 'done' : 'todo', caption: '匹配课程' },
  { label: '学习', mark: '学', status: activeCourse.value?.progress > 0 ? 'current' : 'todo', caption: activeCourse.value?.status_label || '待开始' },
  { label: '提升', mark: '升', status: summary.value.completed ? 'current' : 'todo', caption: '形成节点' }
])

const activeCourse = computed(() => {
  return courseCards.value.find((course) => course.key === selectedKey.value) || courseCards.value[0] || null
})

const activeLessons = computed(() => activeCourse.value?.lessons || [])

const activeLesson = computed(() => {
  return activeLessons.value.find((lesson) => lesson.id === Number(selectedLessonId.value)) || activeLessons.value[0] || null
})

const headerSub = computed(() => {
  if (!summary.value.total) return '课程数据来自在线学习接口'
  const source = courseCards.value.some((course) => course.source === 'online') ? '在线视频课程' : 'P5 培训接口'
  return `${source} · ${summary.value.total} 门课程 · 已学 ${formatMinutes(summary.value.learnedMinutes)}`
})

const canTrackProgress = computed(() => Boolean(activeCourse.value?.source === 'online' || activeCourse.value?.plan_id))

async function load() {
  loading.value = true
  loadedLessonCourses.clear()
  try {
    const [onlineResult, planResult, courseResult] = await Promise.allSettled([
      listOnlineCourses(),
      listMyPlans(),
      listTrainingCourses({ page: 1, page_size: 200, status: 1 })
    ])

    onlineCourses.value = onlineResult.status === 'fulfilled'
      ? (onlineResult.value.data?.items || []).map(normalizeOnlineCourse)
      : []
    plans.value = planResult.status === 'fulfilled' ? (planResult.value.data || []) : []
    courses.value = courseResult.status === 'fulfilled'
      ? (courseResult.value.data?.items || []).map(normalizeCourse)
      : []
    syncSelection()
  } finally {
    loading.value = false
  }
}

function splitIds(value) {
  if (Array.isArray(value)) return value.map(Number).filter((id) => !Number.isNaN(id))
  return String(value || '')
    .split(/[,，]+/)
    .map((item) => Number(item.trim()))
    .filter((id) => !Number.isNaN(id))
}

function normalizeCourse(course) {
  return {
    ...course,
    id: Number(course.id),
    title: course.title || `课程#${course.id}`,
    category: course.category || '未分类',
    cover: course.cover || '',
    intro: course.intro || '暂无课程简介',
    score: Number(course.score) || 0,
    lesson_count: Number(course.lesson_count || course.lessons?.length || 0),
    lessons: normalizeLessons(course.lessons)
  }
}

function normalizeOnlineCourse(course) {
  const videoId = Number(course.video_id)
  const duration = Math.max(
    0,
    Math.floor(Number(course.duration) || Number(course.progress?.duration) || 0)
  )

  return {
    ...course,
    id: Number(course.id),
    video_id: videoId,
    title: course.title || `课程#${course.id}`,
    description: course.description || '',
    duration,
    video_ready: Boolean(course.video_ready && videoId)
  }
}

function buildOnlineCourseCard(course) {
  const progressInfo = course.progress || {}
  const position = Math.max(0, Math.floor(Number(progressInfo.position) || 0))
  const duration = Math.max(
    Number(course.duration) || 0,
    Math.floor(Number(progressInfo.duration) || 0)
  )
  const progress = clampProgress(progressInfo.percent || secondsToProgress(position, duration))
  const lesson = {
    id: Number(course.video_id),
    title: course.title,
    content: course.description || '',
    file_url: getCourseVideoStreamUrl(course.video_id),
    duration: duration ? Math.ceil(duration / 60) : 0,
    duration_seconds: duration,
    position,
    sort: 1,
    source: 'online'
  }

  return {
    source: 'online',
    key: `online-${course.id}`,
    id: Number(course.id),
    video_id: Number(course.video_id),
    video_ready: course.video_ready,
    title: course.title,
    category: '在线视频',
    cover: '',
    intro: course.description || '暂无课程简介',
    score: duration ? Math.max(0.1, Number((duration / 3600).toFixed(1))) : 0,
    study_time_text: duration ? formatMinutes(Math.ceil(duration / 60)) : '未配置时长',
    lesson_count: 1,
    lessons: [lesson],
    plan_id: null,
    plan_title: '在线学习课程',
    plan_status: null,
    progress,
    learned_minutes: Math.ceil(position / 60),
    last_lesson_id: lesson.id,
    last_lesson_title: position ? lesson.title : '',
    status_label: progress >= 100 ? '已完成' : progress > 0 ? '学习中' : '未开始'
  }
}

function normalizeLessons(lessons = []) {
  return lessons
    .map((lesson, index) => ({
      ...lesson,
      id: Number(lesson.id),
      title: lesson.title || `课节 ${index + 1}`,
      content: lesson.content || '',
      // 培训课节已挂视频素材(video_id) → 播放视频流；否则回退 file_url(课件/外链)
      file_url: lesson.video_id ? getCourseVideoStreamUrl(Number(lesson.video_id)) : (lesson.file_url || ''),
      video_id: lesson.video_id ? Number(lesson.video_id) : null,
      duration: Number(lesson.duration) || 0,
      sort: Number(lesson.sort || index + 1)
    }))
    .filter((lesson) => lesson.id)
    .sort((a, b) => a.sort - b.sort || a.id - b.id)
}

function secondsToProgress(position, duration) {
  if (!duration) return 0
  return Math.round(Math.min(position, duration) * 100 / duration)
}

function buildCourseCard(course, plan, record) {
  const progress = clampProgress(record?.progress)
  const lastLessonId = Number(record?.last_lesson_id || record?.lesson_id || 0)
  const lastLesson = course.lessons.find((lesson) => lesson.id === lastLessonId)

  return {
    ...course,
    key: String(course.id),
    plan_id: plan?.id || null,
    plan_title: plan?.title || '课程库',
    plan_status: plan?.status ?? null,
    progress,
    learned_minutes: Math.max(0, Number(record?.learned_minutes) || 0),
    last_lesson_id: lastLessonId,
    last_lesson_title: lastLesson?.title || '',
    status_label: progress >= 100 ? '已完成' : progress > 0 ? '学习中' : (plan ? '未开始' : '可学习')
  }
}

function clampProgress(value) {
  const progress = Number(value) || 0
  return Math.max(0, Math.min(100, Math.round(progress)))
}

function syncSelection() {
  if (!courseCards.value.length) {
    selectedKey.value = ''
    selectedLessonId.value = 0
    return
  }

  let course = courseCards.value.find((item) => item.key === selectedKey.value)
  if (!course) {
    course = courseCards.value[0]
    selectedKey.value = course.key
  }

  const hasLesson = course.lessons.some((lesson) => lesson.id === Number(selectedLessonId.value))
  if (!hasLesson) selectedLessonId.value = pickStartLesson(course)?.id || 0
}

function pickStartLesson(course) {
  if (!course?.lessons?.length) return null
  return course.lessons.find((lesson) => lesson.id === course.last_lesson_id)
    || course.lessons.find((lesson) => lesson.file_url)
    || course.lessons[0]
}

async function selectCourse(course) {
  selectedKey.value = course.key
  selectedLessonId.value = pickStartLesson(course)?.id || 0
  watchSecond.value = 0
  videoDurationSecond.value = 0
  lastReportSecond.value = 0
  await ensureLessons(course)
  syncSelection()
}

function selectLesson(lesson) {
  selectedLessonId.value = lesson.id
  watchSecond.value = 0
  videoDurationSecond.value = 0
  lastReportSecond.value = 0
}

async function ensureLessons(course) {
  if (course?.source === 'online') return
  if (!course?.id || course.lessons.length || loadedLessonCourses.has(course.id)) return
  lessonLoading.value = true
  try {
    const res = await listCourseLessons(course.id)
    patchCourseLessons(course.id, res.data || [])
    loadedLessonCourses.add(course.id)
  } finally {
    lessonLoading.value = false
  }
}

function patchCourseLessons(courseId, lessons) {
  courses.value = courses.value.map((course) => {
    if (course.id !== Number(courseId)) return course
    return { ...course, lessons: normalizeLessons(lessons), lesson_count: lessons.length }
  })
}

function handleTimeUpdate(event) {
  const detail = event.detail || {}
  watchSecond.value = Math.floor(detail.currentTime || 0)
  if (detail.duration) videoDurationSecond.value = Math.floor(detail.duration)
  queueOnlineProgressReport()
}

function handleVideoError() {
  uni.showToast({ title: '视频地址暂不可播放', icon: 'none' })
}

async function handleVideoEnded() {
  if (!activeCourse.value || !activeLesson.value || !canTrackProgress.value) return
  const duration = resolveLessonSeconds(activeCourse.value, activeLesson.value)
  await saveProgress(activeCourse.value, activeLesson.value, 100, totalLessonMinutes(activeCourse.value), {
    position: duration,
    duration
  })
}

async function markLessonDone() {
  if (!activeCourse.value || !activeLesson.value) return
  const duration = resolveLessonSeconds(activeCourse.value, activeLesson.value)
  await saveProgress(activeCourse.value, activeLesson.value, undefined, undefined, {
    position: duration || watchSecond.value,
    duration
  })
}

async function markCourseDone() {
  if (!activeCourse.value || !activeLessons.value.length) return
  const lastLesson = activeLessons.value[activeLessons.value.length - 1]
  const duration = resolveLessonSeconds(activeCourse.value, lastLesson)
  await saveProgress(activeCourse.value, lastLesson, 100, totalLessonMinutes(activeCourse.value), {
    position: duration || watchSecond.value,
    duration
  })
}

async function saveProgress(course, lesson, targetProgress, targetMinutes, timing = {}) {
  if (course.source === 'online') {
    if (updating.value) return

    let duration = Math.max(
      0,
      Math.floor(Number(timing.duration) || resolveLessonSeconds(course, lesson) || watchSecond.value || 0)
    )
    let position = Math.max(
      0,
      Math.floor(Number(timing.position) || watchSecond.value || duration)
    )
    if (targetProgress >= 100 && !duration) {
      duration = Math.max(position, 1)
      position = duration
    }

    updating.value = true
    try {
      const res = await reportOnlineCourseProgress({
        course_id: course.id,
        position: duration ? Math.min(position, duration) : position,
        duration
      })
      const data = res.data || {}
      const progress = clampProgress(data.percent ?? targetProgress ?? secondsToProgress(position, duration))
      patchOnlineCourseProgress(course.id, {
        position: duration ? Math.min(position, duration) : position,
        duration,
        percent: progress,
        completed: Number(data.completed ?? (progress >= 100 ? 1 : 0)),
        last_watch_at: new Date().toISOString()
      })
      if (!timing.silent) {
        uni.showToast({ title: progress >= 100 ? '课程已完成' : '进度已更新', icon: 'success' })
      }
    } finally {
      updating.value = false
    }
    return
  }

  if (!course.plan_id) {
    uni.showToast({ title: '暂无学习计划，进度不记录', icon: 'none' })
    return
  }
  if (updating.value) return

  const progress = Math.max(course.progress, clampProgress(targetProgress ?? progressAfterLesson(course, lesson)))
  const learnedMinutes = Math.max(
    course.learned_minutes,
    Number(targetMinutes) || minutesAfterLesson(course, lesson, progress),
    Math.ceil(watchSecond.value / 60)
  )

  updating.value = true
  try {
    await updateLearningProgress(course.plan_id, {
      course_id: course.id,
      lesson_id: lesson.id,
      progress,
      learned_minutes: learnedMinutes
    })
    patchRecord(course.plan_id, course.id, {
      lesson_id: lesson.id,
      last_lesson_id: lesson.id,
      progress,
      learned_minutes: learnedMinutes
    })
    uni.showToast({ title: progress >= 100 ? '课程已完成' : '进度已更新', icon: 'success' })
  } finally {
    updating.value = false
  }
}

function queueOnlineProgressReport() {
  if (activeCourse.value?.source !== 'online' || !activeLesson.value || updating.value) return
  if (watchSecond.value < 5 || watchSecond.value - lastReportSecond.value < 15) return
  lastReportSecond.value = watchSecond.value
  saveProgress(activeCourse.value, activeLesson.value, undefined, undefined, {
    position: watchSecond.value,
    duration: resolveLessonSeconds(activeCourse.value, activeLesson.value),
    silent: true
  }).catch(() => {})
}

function resolveLessonSeconds(course, lesson) {
  return Math.max(
    0,
    Math.floor(
      Number(videoDurationSecond.value)
      || Number(lesson?.duration_seconds)
      || Number(course?.duration)
      || 0
    )
  )
}

function patchRecord(planId, courseId, patch) {
  plans.value = plans.value.map((plan) => {
    if (Number(plan.id) !== Number(planId)) return plan
    const records = [...(plan.records || [])]
    const index = records.findIndex((record) => Number(record.course_id) === Number(courseId))
    const nextRecord = { course_id: Number(courseId), ...patch }
    if (index >= 0) records[index] = { ...records[index], ...nextRecord }
    else records.push(nextRecord)
    return { ...plan, records }
  })
}

function patchOnlineCourseProgress(courseId, patch) {
  onlineCourses.value = onlineCourses.value.map((course) => {
    if (Number(course.id) !== Number(courseId)) return course
    return {
      ...course,
      progress: {
        ...(course.progress || {}),
        ...patch
      }
    }
  })
}

function progressAfterLesson(course, lesson) {
  const index = course.lessons.findIndex((item) => item.id === lesson.id)
  if (index < 0 || !course.lessons.length) return course.progress
  return Math.round(((index + 1) / course.lessons.length) * 100)
}

function minutesAfterLesson(course, lesson, progress) {
  const index = course.lessons.findIndex((item) => item.id === lesson.id)
  const learnedByLessons = index >= 0
    ? course.lessons.slice(0, index + 1).reduce((sum, item) => sum + item.duration, 0)
    : 0
  if (learnedByLessons) return learnedByLessons
  return Math.round((course.score || 0) * 60 * progress / 100)
}

function totalLessonMinutes(course) {
  const total = course.lessons.reduce((sum, lesson) => sum + lesson.duration, 0)
  return total || Math.round((course.score || 0) * 60)
}

function isLessonDone(course, lesson) {
  if (!course?.lessons?.length) return false
  const index = course.lessons.findIndex((item) => item.id === lesson.id)
  if (index < 0) return false
  return Math.round(((index + 1) / course.lessons.length) * 100) <= course.progress
}

function selectNextLesson() {
  const index = activeLessons.value.findIndex((lesson) => lesson.id === activeLesson.value?.id)
  if (index >= 0 && index < activeLessons.value.length - 1) {
    selectLesson(activeLessons.value[index + 1])
    return
  }
  uni.showToast({ title: '已经是最后一节', icon: 'none' })
}

function statusColor(course) {
  if (!course.plan_id && course.source !== 'online') return '#708692'
  if (course.progress >= 100) return '#FF7F78'
  if (course.progress > 0) return '#55BCEB'
  return '#D98C23'
}
function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack({ delta: 1 })
  } else {
    uni.switchTab({ url: '/pages/index/index' })
  }
}

function courseInitial(title) {
  return String(title || '课').slice(0, 1)
}

function formatMinutes(value) {
  const minutes = Math.max(0, Number(value) || 0)
  if (minutes >= 60) return `${(minutes / 60).toFixed(minutes % 60 ? 1 : 0)} 小时`
  return `${minutes} 分钟`
}

function formatWatchSecond(value) {
  const seconds = Math.max(0, Number(value) || 0)
  const min = Math.floor(seconds / 60)
  const sec = seconds % 60
  return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function planStatusLabel(status) {
  return planStatusText[status] || ''
}

function courseReason(course) {
  if (!course) return '围绕当前成长阶段推荐'
  if (course.plan_title && course.plan_title !== '课程库') return `来自 ${course.plan_title}`
  if (course.source === 'online') return '在线视频课程，可记录学习进度'
  return `${course.category || '能力'}方向课程`
}

onMounted(load)
onPullDownRefresh(async () => {
  await load()
  uni.stopPullDownRefresh()
})
</script>

<template>
  <view class="app-page study-page">
    <view class="page-back" hover-class="page-back--active" @click="goBack" aria-label="返回">
      <text class="page-back-icon">‹</text>
    </view>
    <view class="header surface">
      <view>
        <text class="eyebrow">提升能力</text>
        <text class="title">在线学习</text>
        <text class="subtitle">{{ headerSub }}</text>
      </view>
      <view class="talent">人才ID {{ currentTalentId() }}</view>
    </view>

    <view class="growth-card surface">
      <GrowthPath :steps="learningSteps" compact />
    </view>

    <view class="summary surface">
      <view class="summary-item">
        <text class="summary-num">{{ summary.avgProgress }}%</text>
        <text class="summary-label">平均进度</text>
      </view>
      <view class="summary-item">
        <text class="summary-num green">{{ summary.completed }}</text>
        <text class="summary-label">已完成</text>
      </view>
      <view class="summary-item">
        <text class="summary-num amber">{{ formatMinutes(summary.learnedMinutes) }}</text>
        <text class="summary-label">累计学习</text>
      </view>
    </view>

    <UiState v-if="loading" tone="loading" title="正在加载课程" hint="正在同步在线课程和学习计划。" />
    <UiState
      v-else-if="!courseCards.length"
      title="暂无可学习课程"
      hint="请先在管理端上传视频并生成课程，或给当前人才分配学习计划。"
    />

    <template v-else>
      <view class="section-title">我的课程</view>
      <scroll-view class="course-scroll" scroll-x>
        <view class="course-row">
          <view
            v-for="course in courseCards"
            :key="course.key"
            class="course-card"
            :class="{ active: activeCourse && activeCourse.key === course.key }"
            @click="selectCourse(course)"
          >
            <image v-if="course.cover" class="cover" :src="course.cover" mode="aspectFill" />
            <view v-else class="cover placeholder">
              <text>{{ courseInitial(course.title) }}</text>
            </view>
            <view class="course-body">
              <view class="course-top">
                <text class="tag">{{ course.category }}</text>
                <text class="status" :style="{ background: statusColor(course) }">{{ course.status_label }}</text>
              </view>
              <text class="course-title">{{ course.title }}</text>
              <text class="course-reason">{{ courseReason(course) }}</text>
              <text class="course-intro">{{ course.intro }}</text>
              <view class="meta">
                <text>{{ course.lessons.length || course.lesson_count }} 课节</text>
                <text>{{ course.study_time_text || course.score + ' 学时' }}</text>
                <text v-if="course.plan_id">{{ planStatusLabel(course.plan_status) }}</text>
              </view>
              <view class="progress-line">
                <view class="progress-bar">
                  <view class="progress-fill" :style="{ width: course.progress + '%' }"></view>
                </view>
                <text>{{ course.progress }}%</text>
              </view>
            </view>
          </view>
        </view>
      </scroll-view>

      <view v-if="activeCourse" class="player-panel">
        <view class="player-head">
          <view class="player-title-wrap">
            <text class="player-title">{{ activeCourse.title }}</text>
            <text class="player-sub">
              {{ activeCourse.plan_title }}
              <template v-if="activeCourse.last_lesson_title"> · 上次学到 {{ activeCourse.last_lesson_title }}</template>
            </text>
          </view>
          <text class="player-progress">{{ activeCourse.progress }}%</text>
        </view>

        <video
          v-if="activeLesson && activeLesson.file_url"
          :key="activeLesson.file_url"
          class="video"
          :src="activeLesson.file_url"
          :initial-time="activeLesson.position || 0"
          controls
          @timeupdate="handleTimeUpdate"
          @ended="handleVideoEnded"
          @error="handleVideoError"
        />
        <view v-else class="video empty-video">
          <text>当前课节暂无视频地址</text>
        </view>

        <view class="lesson-current">
          <text class="lesson-title">{{ activeLesson?.title || '暂无课节' }}</text>
          <text class="lesson-time">
            {{ activeLesson?.duration ? formatMinutes(activeLesson.duration) : '未配置时长' }}
            <template v-if="watchSecond"> · 本次播放 {{ formatWatchSecond(watchSecond) }}</template>
          </text>
        </view>

        <view v-if="!canTrackProgress" class="notice">暂无学习计划，仅支持试看，进度不会保存</view>

        <view class="actions">
          <button class="action" :disabled="!activeLesson" @click="selectNextLesson">下一节</button>
          <button class="action primary" :loading="updating" :disabled="!canTrackProgress || !activeLesson" @click="markLessonDone">
            继续学习
          </button>
          <button class="action success" :loading="updating" :disabled="!canTrackProgress || !activeLessons.length" @click="markCourseDone">
            整课完成
          </button>
        </view>

        <view class="lesson-section">
          <view class="section-title inner">课程课节</view>
          <view v-if="lessonLoading" class="lesson-loading">课节加载中...</view>
          <view
            v-for="lesson in activeLessons"
            :key="lesson.id"
            class="lesson-row"
            :class="{
              active: activeLesson && lesson.id === activeLesson.id,
              done: isLessonDone(activeCourse, lesson)
            }"
            @click="selectLesson(lesson)"
          >
            <view class="lesson-dot"></view>
            <view class="lesson-info">
              <text class="lesson-name">{{ lesson.title }}</text>
              <text class="lesson-meta">{{ lesson.duration ? formatMinutes(lesson.duration) : '未配置时长' }}</text>
            </view>
            <text class="lesson-state">{{ isLessonDone(activeCourse, lesson) ? '已学' : lesson.file_url ? '可播放' : '无视频' }}</text>
          </view>
        </view>
      </view>
    </template>
  </view>
</template>

<style scoped>
.study-page {
  padding-bottom: 84rpx;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24rpx;
  padding: 30rpx;
}
.eyebrow,
.subtitle,
.title {
  display: block;
}
.eyebrow {
  color: var(--color-coral);
  font-size: 24rpx;
  font-weight: 800;
}
.title {
  margin-top: 4rpx;
  color: var(--color-text);
  font-size: 44rpx;
  font-weight: 800;
}
.subtitle {
  margin-top: 8rpx;
  color: var(--color-muted);
  font-size: 24rpx;
  line-height: 1.5;
}
.talent {
  flex-shrink: 0;
  padding: 10rpx 18rpx;
  color: var(--color-brand);
  font-size: 22rpx;
  background: var(--color-brand-soft);
  border-radius: var(--radius-sm);
}
.growth-card {
  margin-top: 18rpx;
  padding: 24rpx;
}
.summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14rpx;
  margin-top: 18rpx;
  margin-bottom: 28rpx;
  padding: 14rpx;
}
.summary-item {
  min-width: 0;
  padding: 12rpx 8rpx;
  text-align: center;
}
.summary-num {
  display: block;
  color: var(--color-brand);
  font-size: 34rpx;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.summary-num.green {
  color: var(--color-success);
}
.summary-num.amber {
  color: var(--color-coral);
  font-size: 30rpx;
}
.summary-label {
  display: block;
  margin-top: 8rpx;
  color: var(--color-muted);
  font-size: 22rpx;
}
.section-title {
  margin: 4rpx 0 18rpx;
  color: var(--color-text);
  font-size: 30rpx;
  font-weight: 750;
}
.section-title.inner {
  margin-top: 30rpx;
}
.course-scroll {
  width: 100%;
  margin-bottom: 24rpx;
  white-space: nowrap;
}
.course-row {
  display: flex;
  gap: 18rpx;
  width: max-content;
}
.course-card {
  display: inline-flex;
  width: 560rpx;
  min-height: 258rpx;
  overflow: hidden;
  vertical-align: top;
  background: #fff;
  border: 2rpx solid transparent;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-soft);
}
.course-card.active {
  border-color: rgba(255, 127, 120, .55);
}
.cover {
  width: 180rpx;
  min-height: 258rpx;
  background: #EAF4F8;
}
.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 58rpx;
  font-weight: 700;
  background: linear-gradient(135deg, var(--color-brand), var(--color-sky));
}
.course-body {
  flex: 1;
  min-width: 0;
  padding: 22rpx;
}
.course-top,
.meta,
.progress-line,
.player-head,
.actions,
.lesson-row {
  display: flex;
  align-items: center;
}
.course-top {
  justify-content: space-between;
  gap: 12rpx;
}
.tag,
.status {
  flex-shrink: 0;
  padding: 4rpx 12rpx;
  font-size: 20rpx;
  border-radius: 18rpx;
}
.tag {
  color: var(--color-brand);
  background: var(--color-brand-soft);
}
.status {
  color: #fff;
}
.course-title {
  display: block;
  margin-top: 14rpx;
  color: var(--color-text);
  font-size: 30rpx;
  font-weight: 750;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.course-reason {
  display: block;
  margin-top: 8rpx;
  color: var(--color-coral);
  font-size: 22rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.course-intro {
  display: -webkit-box;
  height: 66rpx;
  margin-top: 8rpx;
  overflow: hidden;
  color: var(--color-muted);
  font-size: 23rpx;
  line-height: 33rpx;
  white-space: normal;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.meta {
  gap: 14rpx;
  margin-top: 12rpx;
  color: var(--color-muted);
  font-size: 22rpx;
}
.progress-line {
  gap: 12rpx;
  margin-top: 14rpx;
  color: var(--color-brand);
  font-size: 22rpx;
}
.progress-bar {
  flex: 1;
  height: 10rpx;
  overflow: hidden;
  background: #ECF4F7;
  border-radius: 999rpx;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-brand), var(--color-coral));
  border-radius: 999rpx;
}
.player-panel {
  padding: 28rpx;
  background: #fff;
  border: 1rpx solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-soft);
}
.player-head {
  justify-content: space-between;
  gap: 18rpx;
  margin-bottom: 22rpx;
}
.player-title-wrap {
  min-width: 0;
}
.player-title {
  display: block;
  color: var(--color-text);
  font-size: 34rpx;
  font-weight: 750;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.player-sub {
  display: block;
  margin-top: 8rpx;
  color: var(--color-muted);
  font-size: 24rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.player-progress {
  flex-shrink: 0;
  color: var(--color-coral);
  font-size: 34rpx;
  font-weight: 800;
}
.video {
  width: 100%;
  height: 390rpx;
  overflow: hidden;
  background: #20313C;
  border-radius: var(--radius-md);
}
.empty-video {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #cbd5e1;
  font-size: 26rpx;
}
.lesson-current {
  padding: 22rpx 0 8rpx;
}
.lesson-title {
  display: block;
  color: var(--color-text);
  font-size: 30rpx;
  font-weight: 700;
}
.lesson-time {
  display: block;
  margin-top: 8rpx;
  color: var(--color-muted);
  font-size: 24rpx;
}
.notice {
  margin: 16rpx 0 8rpx;
  padding: 16rpx 20rpx;
  color: var(--color-warning);
  font-size: 24rpx;
  background: #FFF7E8;
  border-radius: var(--radius-sm);
}
.actions {
  gap: 14rpx;
  margin-top: 18rpx;
}
.action {
  flex: 1;
  height: 100rpx;
  margin: 0;
  color: var(--color-text);
  font-size: 28rpx;
  line-height: 100rpx;
  background: #fff;
  border: 2rpx solid var(--color-border);
  border-radius: var(--radius-md);
}
.action.primary {
  color: #fff;
  background: var(--color-brand);
  border-color: var(--color-brand);
  font-weight: 700;
}
.action.success {
  color: #fff;
  background: var(--color-coral);
  border-color: var(--color-coral);
  font-weight: 700;
}
.action[disabled] {
  color: #A7B7C0;
  background: #F2F7F9;
  border-color: #EAF2F6;
}
.lesson-loading {
  padding: 24rpx 0;
  color: var(--color-muted);
  text-align: center;
  font-size: 24rpx;
}
.lesson-row {
  gap: 18rpx;
  min-height: 94rpx;
  padding: 18rpx 0;
  border-top: 1rpx solid var(--color-border);
}
.lesson-row.active .lesson-name {
  color: var(--color-brand);
}
.lesson-row.done .lesson-dot {
  background: var(--color-coral);
}
.lesson-dot {
  width: 18rpx;
  height: 18rpx;
  flex-shrink: 0;
  background: #BED5DE;
  border-radius: 50%;
}
.lesson-info {
  flex: 1;
  min-width: 0;
}
.lesson-name {
  display: block;
  color: var(--color-text);
  font-size: 28rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.lesson-meta {
  display: block;
  margin-top: 6rpx;
  color: var(--color-muted);
  font-size: 22rpx;
}
.lesson-state {
  flex-shrink: 0;
  color: var(--color-muted);
  font-size: 23rpx;
}

.page-back {
  position: fixed;
  top: 18rpx;
  left: 16rpx;
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 60rpx;
  height: 60rpx;
  background: rgba(255, 255, 255, 0.18);
  border-radius: 50%;
  box-sizing: border-box;
}
.page-back-icon {
  color: #fff;
  font-size: 44rpx;
  font-weight: 600;
  line-height: 1;
  margin-top: -6rpx;
}
.page-back--active {
  background: rgba(255, 255, 255, 0.36);
}
</style>
