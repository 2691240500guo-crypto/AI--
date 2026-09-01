<script setup>
import { computed, ref } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { getAnswerView, submitAnswer, getReport } from '@/api'

const loading = ref(true)
const view = ref(null)
const answers = ref({})
const submitting = ref(false)
const current = ref(0)
const remain = ref(0)
const timer = ref(null)

const total = computed(() => view.value?.questions.length || 0)
const currentQ = computed(() => view.value?.questions[current.value])
const answeredCount = computed(() => Object.keys(answers.value).filter(k => answers.value[k] && answers.value[k].length).length)
const fmtRemain = computed(() => {
  const m = Math.floor(remain.value / 60)
  const s = remain.value % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})

let resultId = null

onLoad(async (options) => {
  resultId = options.id
  try {
    const res = await getAnswerView(resultId)
    view.value = res.data
    // 回填已有答案
    for (const a of res.data.previous_answers || []) {
      if (a.question_type === 'multi') answers.value[a.question_id] = a.user_answer.split(',')
      else answers.value[a.question_id] = a.user_answer
    }
    startTimer()
  } finally { loading.value = false }
})

onUnload(() => clearInterval(timer.value))

function startTimer() {
  remain.value = view.value.duration_min * 60
  timer.value = setInterval(() => {
    remain.value--
    if (remain.value <= 0) { clearInterval(timer.value); submit(true) }
  }, 1000)
}

function goTo(i) {
  if (i >= 0 && i < total.value) current.value = i
}

function normalizeAnswer(q, val) {
  if (!val || !val.length) return ''
  if (q.type === 'multi') return [...val].sort().join(',')
  return val
}

async function submit(auto = false) {
  if (submitting.value) return
  const unanswered = total.value - answeredCount.value
  if (!auto && unanswered > 0) {
    const ok = await new Promise((resolve) => {
      uni.showModal({
        title: '提示',
        content: `还有 ${unanswered} 题未作答，确定交卷？`,
        success: (r) => resolve(r.confirm)
      })
    })
    if (!ok) return
  }
  submitting.value = true
  try {
    const payload = { answers: view.value.questions.map(q => ({ question_id: q.id, user_answer: normalizeAnswer(q, answers.value[q.id]) })) }
    const res = await submitAnswer(resultId, payload)
    uni.showToast({ title: `得分 ${res.data.score} 分`, icon: 'none', duration: 2000 })
    setTimeout(() => {
      uni.redirectTo({ url: '/pages/profile/profile?tab=result' })
    }, 1500)
  } catch { submitting.value = false }
}
</script>

<template>
  <view class="page">
    <view v-if="loading" class="center">加载中...</view>
    <template v-else-if="view">
      <!-- 顶部栏 -->
      <view class="top">
        <text class="top-title">{{ view.paper_title }}</text>
        <text class="timer" :class="{ danger: remain < 300 }">{{ fmtRemain }}</text>
        <text class="progress">已答 {{ answeredCount }}/{{ total }}</text>
      </view>
      <view class="progress-bar">
        <view class="progress-fill" :style="{ width: (answeredCount / total * 100) + '%' }"></view>
      </view>

      <!-- 题目 -->
      <view class="q-wrap" v-if="currentQ">
        <view class="q-head">
          <text class="q-no">{{ current + 1 }}</text>
          <text class="q-type">{{ currentQ.type === 'single' ? '单选' : currentQ.type === 'multi' ? '多选' : '判断' }}</text>
          <text class="q-score">{{ currentQ.score }}分</text>
        </view>
        <view class="q-content">{{ currentQ.content }}</view>

        <radio-group v-if="currentQ.type === 'single'" class="opts" @change="(e) => (answers[currentQ.id] = e.detail.value)">
          <label v-for="o in currentQ.options" :key="o.key" class="opt">
            <radio :value="o.key" :checked="answers[currentQ.id] === o.key" color="#2563eb" />
            <text class="opt-text">{{ o.key }}. {{ o.text }}</text>
          </label>
        </radio-group>

        <checkbox-group v-else-if="currentQ.type === 'multi'" class="opts" @change="(e) => (answers[currentQ.id] = e.detail.value)">
          <label v-for="o in currentQ.options" :key="o.key" class="opt">
            <checkbox :value="o.key" :checked="(answers[currentQ.id] || []).includes(o.key)" color="#2563eb" />
            <text class="opt-text">{{ o.key }}. {{ o.text }}</text>
          </label>
        </checkbox-group>

        <radio-group v-else class="opts" @change="(e) => (answers[currentQ.id] = e.detail.value)">
          <label class="opt"><radio value="true" :checked="answers[currentQ.id] === 'true'" color="#2563eb" /><text class="opt-text">正确</text></label>
          <label class="opt"><radio value="false" :checked="answers[currentQ.id] === 'false'" color="#2563eb" /><text class="opt-text">错误</text></label>
        </radio-group>
      </view>

      <!-- 答题卡 -->
      <view class="nav">
        <view v-for="(q, i) in view.questions" :key="q.id" class="nav-num"
          :class="{ cur: i === current, done: answers[q.id] && answers[q.id].length }"
          @click="goTo(i)">{{ i + 1 }}</view>
      </view>

      <!-- 底部操作 -->
      <view class="foot">
        <button class="btn" :disabled="current === 0" @click="goTo(current - 1)">上一题</button>
        <button v-if="current < total - 1" class="btn primary" @click="goTo(current + 1)">下一题</button>
        <button v-else class="btn primary" :loading="submitting" @click="submit()">交卷</button>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; background: #f5f7fa; padding-bottom: 180rpx; }
.center { text-align: center; padding: 120rpx 0; color: #9ca3af; }

.top { background: #fff; padding: 20rpx 32rpx; display: flex; align-items: center; gap: 20rpx; border-bottom: 1rpx solid #eef1f5; position: sticky; top: 0; z-index: 10; }
.top-title { font-size: 32rpx; font-weight: 600; color: #1f2937; flex: 1; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.timer { font-size: 32rpx; font-weight: 600; color: #1f2937; }
.timer.danger { color: #dc2626; }
.progress { font-size: 24rpx; color: #6b7280; }

.progress-bar { height: 6rpx; background: #e5e7eb; }
.progress-fill { height: 100%; background: #4f46e5; transition: width .3s; }

.q-wrap { background: #fff; margin: 24rpx; border-radius: 16rpx; padding: 32rpx; }
.q-head { display: flex; align-items: center; gap: 16rpx; margin-bottom: 20rpx; }
.q-no { width: 44rpx; height: 44rpx; border-radius: 50%; background: #4f46e5; color: #fff; text-align: center; line-height: 44rpx; font-size: 24rpx; }
.q-type { color: #6b7280; font-size: 24rpx; }
.q-score { margin-left: auto; color: #f59e0b; font-size: 24rpx; }
.q-content { font-size: 30rpx; line-height: 1.7; margin-bottom: 24rpx; color: #1f2937; }

.opts { display: flex; flex-direction: column; gap: 20rpx; }
.opt { display: flex; align-items: center; gap: 14rpx; }
.opt-text { font-size: 28rpx; color: #374151; }

.nav { display: flex; flex-wrap: wrap; gap: 14rpx; padding: 0 24rpx; }
.nav-num { width: 72rpx; height: 72rpx; border: 2rpx solid #e5e7eb; border-radius: 12rpx; text-align: center; line-height: 68rpx; font-size: 26rpx; color: #6b7280; background: #fff; }
.nav-num.done { background: #eef2ff; border-color: #6366f1; color: #4f46e5; }
.nav-num.cur { background: #4f46e5; border-color: #4f46e5; color: #fff; }

.foot { position: fixed; bottom: 0; left: 0; right: 0; background: #fff; padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom)); display: flex; gap: 20rpx; }
.btn { flex: 1; height: 84rpx; line-height: 84rpx; border-radius: 42rpx; font-size: 28rpx; background: #fff; color: #374151; border: 2rpx solid #e5e7eb; }
.btn.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
</style>