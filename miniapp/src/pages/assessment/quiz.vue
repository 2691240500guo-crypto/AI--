<script setup>
import { computed, ref } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { getAnswerView, saveAnswer, submitAnswer } from '@/api'
import UiState from '@/components/UiState.vue'

const loading = ref(true)
const view = ref(null)
const answers = ref({})
const submitting = ref(false)
const saving = ref(false)
const savedAt = ref('')
const current = ref(0)
const remain = ref(0)
const timer = ref(null)
const draftTimer = ref(null)
const errorMessage = ref('')
let resultId = null

const questions = computed(() => view.value?.questions || [])
const total = computed(() => questions.value.length)
const currentQuestion = computed(() => questions.value[current.value])
const answeredCount = computed(() => questions.value.filter((q) => isAnswered(answers.value[q.question_id])).length)
const progress = computed(() => total.value ? Math.round(answeredCount.value / total.value * 100) : 0)
const fmtRemain = computed(() => {
  if (!view.value?.deadline_at) return '不限时'
  const m = Math.floor(remain.value / 60)
  const s = remain.value % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})

function isAnswered(value) { return Array.isArray(value) ? value.length > 0 : value !== undefined && value !== null && value !== '' }
function optionValue(option) { return typeof option === 'object' ? (option.value ?? option.key ?? option.text) : option }
function optionText(option) { return typeof option === 'object' ? (option.text ?? option.label ?? option.value) : option }
function setAnswer(value) { if (!currentQuestion.value) return; answers.value[currentQuestion.value.question_id] = value; queueSave() }
function queueSave() { clearTimeout(draftTimer.value); draftTimer.value = setTimeout(saveDraft, 450) }
async function saveDraft() {
  if (!resultId || submitting.value) return
  saving.value = true
  try { await saveAnswer(resultId, answers.value); savedAt.value = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) } catch { savedAt.value = '' } finally { saving.value = false }
}

onLoad(async (options) => {
  resultId = options.id
  if (!resultId) { errorMessage.value = '缺少测评记录编号'; loading.value = false; return }
  try {
    const res = await getAnswerView(resultId)
    view.value = res.data
    answers.value = { ...(res.data.answers || {}) }
    remain.value = Math.max(0, Number(res.data.remaining_seconds || 0))
    if (view.value.status >= 2) { uni.redirectTo({ url: `/pages/assessment/result?id=${resultId}` }); return }
    if (view.value.deadline_at) startTimer()
  } catch (error) { errorMessage.value = error?.message || '测评加载失败，请返回重试' } finally { loading.value = false }
})

onUnload(() => { clearInterval(timer.value); clearTimeout(draftTimer.value) })
function startTimer() {
  if (!view.value?.deadline_at) return
  clearInterval(timer.value)
  timer.value = setInterval(() => { remain.value -= 1; if (remain.value <= 0) { remain.value = 0; clearInterval(timer.value); submit(true) } }, 1000)
}
function goTo(index) { if (index >= 0 && index < total.value) current.value = index }
function answerClass(questionId) { return isAnswered(answers.value[questionId]) ? 'done' : '' }
function questionType(type) { return type === 'single' ? '单选题' : type === 'multi' ? '多选题' : '判断题' }

async function submit(auto = false) {
  if (submitting.value || !view.value) return
  const unanswered = total.value - answeredCount.value
  if (!auto && unanswered > 0) {
    const confirmed = await new Promise((resolve) => uni.showModal({ title: '确认交卷', content: `还有 ${unanswered} 题未作答，确定现在交卷吗？`, success: (response) => resolve(response.confirm) }))
    if (!confirmed) return
  }
  submitting.value = true
  clearInterval(timer.value)
  clearTimeout(draftTimer.value)
  try {
    const res = await submitAnswer(resultId, answers.value)
    const score = res.data?.result?.score ?? 0
    const instantResult = {
      result: {
        ...res.data.result,
        paper_title: view.value.paper_title,
        paper_total_score: view.value.paper_total_score,
        question_count: total.value
      },
      details: res.data.details || []
    }
    uni.setStorageSync(`assessment-result-${resultId}`, instantResult)
    uni.showToast({ title: `得分 ${score} 分`, icon: 'none', duration: 1600 })
    setTimeout(() => uni.redirectTo({ url: `/pages/assessment/result?id=${resultId}` }), 120)
  } catch { submitting.value = false; startTimer() }
}
</script>

<template>
  <view class="quiz-page">
    <UiState v-if="loading" tone="loading" title="正在加载试卷" hint="题目和作答进度同步中。" />
    <UiState v-else-if="errorMessage" tone="error" title="测评加载失败" :hint="errorMessage" />

    <template v-else-if="view">
      <view class="top">
        <view class="title-wrap">
          <text class="top-title">{{ view.paper_title }}</text>
          <text class="top-meta">{{ view.paper_total_score }} 分 · {{ total }} 题</text>
        </view>
        <view class="timer" :class="{ danger: view.deadline_at && remain < 300 }">
          <text>{{ fmtRemain }}</text>
          <small>{{ view.deadline_at ? '剩余时间' : '答题时间' }}</small>
        </view>
      </view>

      <view class="progress-panel">
        <view class="progress-row">
          <text>已答 {{ answeredCount }}/{{ total }}</text>
          <text>{{ saving ? '保存中...' : savedAt ? `已保存 ${savedAt}` : '自动保存' }}</text>
        </view>
        <view class="progress-bar"><view class="progress-fill" :style="{ width: progress + '%' }"></view></view>
      </view>

      <view v-if="currentQuestion" class="question-card surface">
        <view class="question-head">
          <text class="q-number">{{ current + 1 }}</text>
          <text class="q-type">{{ questionType(currentQuestion.type) }}</text>
          <text class="q-score">{{ currentQuestion.score }} 分</text>
        </view>
        <text class="dimension">{{ currentQuestion.dimension }}</text>
        <view class="question-content">{{ currentQuestion.content }}</view>

        <radio-group v-if="currentQuestion.type === 'single'" class="options" @change="(event) => setAnswer(event.detail.value)">
          <label v-for="option in (currentQuestion.options || [])" :key="optionValue(option)" class="option" :class="{ selected: answers[currentQuestion.question_id] === optionValue(option) }">
            <radio :value="String(optionValue(option))" :checked="answers[currentQuestion.question_id] === optionValue(option)" color="#177EAD" />
            <text>{{ optionText(option) }}</text>
          </label>
        </radio-group>
        <checkbox-group v-else-if="currentQuestion.type === 'multi'" class="options" @change="(event) => setAnswer(event.detail.value)">
          <label v-for="option in (currentQuestion.options || [])" :key="optionValue(option)" class="option" :class="{ selected: (answers[currentQuestion.question_id] || []).includes(optionValue(option)) }">
            <checkbox :value="String(optionValue(option))" :checked="(answers[currentQuestion.question_id] || []).includes(optionValue(option))" color="#177EAD" />
            <text>{{ optionText(option) }}</text>
          </label>
        </checkbox-group>
        <radio-group v-else class="options" @change="(event) => setAnswer(event.detail.value)">
          <label class="option" :class="{ selected: answers[currentQuestion.question_id] === '正确' }">
            <radio value="正确" :checked="answers[currentQuestion.question_id] === '正确'" color="#177EAD" />
            <text>正确</text>
          </label>
          <label class="option" :class="{ selected: answers[currentQuestion.question_id] === '错误' }">
            <radio value="错误" :checked="answers[currentQuestion.question_id] === '错误'" color="#177EAD" />
            <text>错误</text>
          </label>
        </radio-group>
      </view>

      <view class="answer-sheet surface">
        <view class="sheet-title">
          <text>答题卡</text>
          <text class="sheet-hint">点击题号快速跳转</text>
        </view>
        <view class="sheet-grid">
          <view
            v-for="(question, index) in questions"
            :key="question.question_id"
            class="sheet-num"
            :class="[answerClass(question.question_id), { current: index === current }]"
            @click="goTo(index)"
          >
            {{ index + 1 }}
          </view>
        </view>
      </view>

      <view class="footer">
        <button class="nav-button" :disabled="current === 0" @click="goTo(current - 1)">上一题</button>
        <button v-if="current < total - 1" class="nav-button primary" @click="goTo(current + 1)">下一题</button>
        <button v-else class="nav-button primary" :loading="submitting" @click="submit()">交卷</button>
      </view>
    </template>
  </view>
</template>

<style lang="scss" scoped>
.quiz-page {
  min-height: 100vh;
  padding-bottom: 180rpx;
  background: var(--color-bg);
}

.top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
  padding: 28rpx 30rpx 22rpx;
  background: #fff;
  border-bottom: 1rpx solid var(--color-border);
}

.title-wrap {
  min-width: 0;
  flex: 1;
}

.top-title,
.top-meta {
  display: block;
}

.top-title {
  overflow: hidden;
  color: var(--color-text);
  font-size: 30rpx;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.top-meta {
  margin-top: 8rpx;
  color: var(--color-muted);
  font-size: 21rpx;
}

.timer {
  display: flex;
  flex: none;
  flex-direction: column;
  align-items: center;
  min-width: 124rpx;
  color: var(--color-brand);
}

.timer text {
  font-size: 34rpx;
  font-weight: 800;
}

.timer small {
  margin-top: 3rpx;
  color: var(--color-muted);
  font-size: 19rpx;
}

.timer.danger text {
  color: var(--color-coral);
}

.progress-panel {
  background: #fff;
}

.progress-row {
  display: flex;
  justify-content: space-between;
  gap: 20rpx;
  padding: 18rpx 30rpx 12rpx;
  color: var(--color-muted);
  font-size: 21rpx;
}

.progress-bar {
  height: 8rpx;
  background: #EAF4F8;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-brand), var(--color-coral));
  transition: width .25s;
}

.question-card {
  margin: 24rpx;
  padding: 30rpx;
}

.question-head {
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.q-number {
  width: 52rpx;
  height: 52rpx;
  color: #fff;
  background: var(--color-brand);
  border-radius: 50%;
  font-size: 25rpx;
  font-weight: 800;
  line-height: 52rpx;
  text-align: center;
}

.q-type {
  color: var(--color-muted);
  font-size: 23rpx;
}

.q-score {
  margin-left: auto;
  color: var(--color-coral);
  font-size: 23rpx;
  font-weight: 700;
}

.dimension {
  display: inline-block;
  margin-top: 22rpx;
  padding: 6rpx 13rpx;
  color: var(--color-brand);
  background: var(--color-brand-soft);
  border-radius: var(--radius-sm);
  font-size: 21rpx;
}

.question-content {
  margin: 20rpx 0 30rpx;
  color: var(--color-text);
  font-size: 31rpx;
  line-height: 1.72;
}

.options {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.option {
  display: flex;
  align-items: center;
  gap: 12rpx;
  min-height: 78rpx;
  padding: 0 18rpx;
  color: var(--color-text);
  background: #F9FCFD;
  border: 2rpx solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 27rpx;
  box-sizing: border-box;
}

.option.selected {
  color: var(--color-brand);
  background: #F0FAFD;
  border-color: rgba(23, 126, 173, .45);
}

.answer-sheet {
  margin: 24rpx;
  padding: 26rpx;
}

.sheet-title {
  display: flex;
  justify-content: space-between;
  gap: 20rpx;
  margin-bottom: 20rpx;
  color: var(--color-text);
  font-size: 27rpx;
  font-weight: 700;
}

.sheet-hint {
  color: var(--color-muted);
  font-size: 21rpx;
  font-weight: normal;
}

.sheet-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
}

.sheet-num {
  width: 62rpx;
  height: 62rpx;
  color: var(--color-muted);
  background: #fff;
  border: 2rpx solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 23rpx;
  line-height: 58rpx;
  text-align: center;
  box-sizing: border-box;
}

.sheet-num.done {
  color: var(--color-brand);
  background: var(--color-brand-soft);
  border-color: rgba(23, 126, 173, .35);
}

.sheet-num.current {
  color: #fff;
  background: var(--color-coral);
  border-color: var(--color-coral);
}

.footer {
  position: fixed;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 10;
  display: flex;
  gap: 18rpx;
  padding: 20rpx 30rpx calc(20rpx + env(safe-area-inset-bottom));
  background: #fff;
  border-top: 1rpx solid var(--color-border);
  box-shadow: 0 -8rpx 24rpx rgba(23, 126, 173, .08);
}

.nav-button {
  flex: 1;
  height: 82rpx;
  margin: 0;
  color: var(--color-text);
  background: #fff;
  border: 2rpx solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 27rpx;
  line-height: 78rpx;
}

.nav-button.primary {
  color: #fff;
  background: var(--color-brand);
  border-color: var(--color-brand);
  font-weight: 700;
}

.nav-button[disabled] {
  color: #B9C7CE;
  background: #F2F7F9;
}
</style>
