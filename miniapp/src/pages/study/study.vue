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
  const onlineRows = onlineCourses.value.map(buildOnlineCourseCard).filter((course) => course.video_ready)
  if (onlineRows.length) return onlineRows

  const courseMap = new Map(courses.value.map((course) => [course.id, course]))
  const rows = []

  plans.value.forEach((plan) => {
    splitIds(plan.course_ids).forEach((courseId) => {
      const course = courseMap.get(courseId)
      if (!course) return
      const record = (plan.records || []).find((item) => Number(item.course_id) === courseId)
      rows.push(buildCourseCard(course, plan, record))
    })
  })

  if (rows.length) return rows
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
      file_url: lesson.file_url || '',
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
    key: `${plan?.id || 'course'}-${course.id}`,
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
  if (!course.plan_id && course.source !== 'online') return '#64748b'
  if (course.progress >= 100) return '#16a34a'
  if (course.progress > 0) return '#2563eb'
  return '#f59e0b'
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

onMounted(load)
onPullDownRefresh(async () => {
  await load()
  uni.stopPullDownRefresh()
})
</script>

<template>
  <view class="page">
    <view class="header">
      <view>
        <text class="eyebrow">智能培训</text>
        <text class="title">在线学习</text>
        <text class="subtitle">{{ headerSub }}</text>
      </view>
      <view class="talent">人才ID {{ currentTalentId() }}</view>
    </view>

    <view class="summary">
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

    <view v-if="loading" class="state">加载中...</view>
    <view v-else-if="!courseCards.length" class="empty">
      <text class="empty-title">暂无可学习课程</text>
      <text class="empty-hint">请先在管理端上传视频并生成课程，或给当前人才分配学习计划</text>
    </view>

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
            完成本课节
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
.page {
  min-height: 100vh;
  padding: 32rpx 28rpx 80rpx;
  background: #f5f7fa;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24rpx;
  padding: 10rpx 0 26rpx;
}
.eyebrow,
.subtitle,
.title {
  display: block;
}
.eyebrow {
  color: #2563eb;
  font-size: 24rpx;
  font-weight: 600;
}
.title {
  margin-top: 4rpx;
  color: #1f2937;
  font-size: 44rpx;
  font-weight: 700;
}
.subtitle {
  margin-top: 8rpx;
  color: #6b7280;
  font-size: 24rpx;
}
.talent {
  flex-shrink: 0;
  padding: 10rpx 18rpx;
  color: #64748b;
  font-size: 22rpx;
  background: #fff;
  border-radius: 28rpx;
}
.summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14rpx;
  margin-bottom: 28rpx;
}
.summary-item {
  min-width: 0;
  padding: 24rpx 10rpx;
  text-align: center;
  background: #fff;
  border-radius: 18rpx;
  box-shadow: 0 2rpx 10rpx rgba(16, 24, 40, .04);
}
.summary-num {
  display: block;
  color: #2563eb;
  font-size: 34rpx;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.summary-num.green {
  color: #16a34a;
}
.summary-num.amber {
  color: #d97706;
  font-size: 30rpx;
}
.summary-label {
  display: block;
  margin-top: 8rpx;
  color: #9ca3af;
  font-size: 22rpx;
}
.state,
.empty {
  padding: 90rpx 24rpx;
  color: #9ca3af;
  text-align: center;
}
.empty-title {
  display: block;
  color: #374151;
  font-size: 30rpx;
  font-weight: 600;
}
.empty-hint {
  display: block;
  margin-top: 14rpx;
  color: #9ca3af;
  font-size: 24rpx;
}
.section-title {
  margin: 4rpx 0 18rpx;
  color: #1f2937;
  font-size: 30rpx;
  font-weight: 700;
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
  min-height: 238rpx;
  overflow: hidden;
  vertical-align: top;
  background: #fff;
  border: 2rpx solid transparent;
  border-radius: 18rpx;
  box-shadow: 0 2rpx 12rpx rgba(16, 24, 40, .05);
}
.course-card.active {
  border-color: #2563eb;
}
.cover {
  width: 180rpx;
  min-height: 238rpx;
  background: #e5e7eb;
}
.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 58rpx;
  font-weight: 700;
  background: linear-gradient(135deg, #2563eb, #14b8a6);
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
  color: #2563eb;
  background: #eff6ff;
}
.status {
  color: #fff;
}
.course-title {
  display: block;
  margin-top: 14rpx;
  color: #111827;
  font-size: 30rpx;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.course-intro {
  display: -webkit-box;
  height: 66rpx;
  margin-top: 8rpx;
  overflow: hidden;
  color: #6b7280;
  font-size: 23rpx;
  line-height: 33rpx;
  white-space: normal;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.meta {
  gap: 14rpx;
  margin-top: 12rpx;
  color: #64748b;
  font-size: 22rpx;
}
.progress-line {
  gap: 12rpx;
  margin-top: 14rpx;
  color: #2563eb;
  font-size: 22rpx;
}
.progress-bar {
  flex: 1;
  height: 10rpx;
  overflow: hidden;
  background: #e5e7eb;
  border-radius: 999rpx;
}
.progress-fill {
  height: 100%;
  background: #2563eb;
  border-radius: 999rpx;
}
.player-panel {
  padding: 28rpx;
  background: #fff;
  border-radius: 20rpx;
  box-shadow: 0 2rpx 12rpx rgba(16, 24, 40, .05);
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
  color: #111827;
  font-size: 34rpx;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.player-sub {
  display: block;
  margin-top: 8rpx;
  color: #6b7280;
  font-size: 24rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.player-progress {
  flex-shrink: 0;
  color: #2563eb;
  font-size: 34rpx;
  font-weight: 700;
}
.video {
  width: 100%;
  height: 390rpx;
  overflow: hidden;
  background: #111827;
  border-radius: 14rpx;
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
  color: #111827;
  font-size: 30rpx;
  font-weight: 600;
}
.lesson-time {
  display: block;
  margin-top: 8rpx;
  color: #64748b;
  font-size: 24rpx;
}
.notice {
  margin: 16rpx 0 8rpx;
  padding: 16rpx 20rpx;
  color: #92400e;
  font-size: 24rpx;
  background: #fffbeb;
  border-radius: 14rpx;
}
.actions {
  gap: 14rpx;
  margin-top: 18rpx;
}
.action {
  flex: 1;
  height: 78rpx;
  margin: 0;
  color: #374151;
  font-size: 25rpx;
  line-height: 78rpx;
  background: #fff;
  border: 2rpx solid #e5e7eb;
  border-radius: 40rpx;
}
.action.primary {
  color: #fff;
  background: #2563eb;
  border-color: #2563eb;
}
.action.success {
  color: #fff;
  background: #16a34a;
  border-color: #16a34a;
}
.action[disabled] {
  color: #9ca3af;
  background: #f3f4f6;
  border-color: #eef1f5;
}
.lesson-loading {
  padding: 24rpx 0;
  color: #9ca3af;
  text-align: center;
  font-size: 24rpx;
}
.lesson-row {
  gap: 18rpx;
  min-height: 94rpx;
  padding: 18rpx 0;
  border-top: 1rpx solid #eef1f5;
}
.lesson-row.active .lesson-name {
  color: #2563eb;
}
.lesson-row.done .lesson-dot {
  background: #16a34a;
}
.lesson-dot {
  width: 18rpx;
  height: 18rpx;
  flex-shrink: 0;
  background: #cbd5e1;
  border-radius: 50%;
}
.lesson-info {
  flex: 1;
  min-width: 0;
}
.lesson-name {
  display: block;
  color: #1f2937;
  font-size: 28rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.lesson-meta {
  display: block;
  margin-top: 6rpx;
  color: #9ca3af;
  font-size: 22rpx;
}
.lesson-state {
  flex-shrink: 0;
  color: #64748b;
  font-size: 23rpx;
}
</style>
