<script setup>
import { computed, ref } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { getAnswerView, saveAnswer, submitAnswer } from '@/api'

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
        question_count: total.value,
      },
      details: res.data.details || [],
    }
    uni.setStorageSync(`assessment-result-${resultId}`, instantResult)
    uni.showToast({ title: `得分 ${score} 分`, icon: 'none', duration: 1600 })
    setTimeout(() => uni.redirectTo({ url: `/pages/assessment/result?id=${resultId}` }), 120)
  } catch { submitting.value = false; startTimer() }
}
</script>

<template>
  <view class="page">
    <view v-if="loading" class="state">正在加载试卷...</view>
    <view v-else-if="errorMessage" class="state error">{{ errorMessage }}</view>
    <template v-else-if="view">
      <view class="top"><view class="title-wrap"><text class="top-title">{{ view.paper_title }}</text><text class="top-meta">{{ view.paper_total_score }} 分 · {{ total }} 题</text></view><view class="timer" :class="{ danger: view.deadline_at && remain < 300 }"><text>{{ fmtRemain }}</text><small>{{ view.deadline_at ? '剩余' : '时间' }}</small></view></view>
      <view class="progress-row"><text>已答 {{ answeredCount }}/{{ total }}</text><text>{{ saving ? '保存中...' : savedAt ? `已保存 ${savedAt}` : '自动保存' }}</text></view><view class="progress-bar"><view class="progress-fill" :style="{ width: progress + '%' }"></view></view>
      <view v-if="currentQuestion" class="question-card"><view class="question-head"><text class="q-number">{{ current + 1 }}</text><text class="q-type">{{ currentQuestion.type === 'single' ? '单选题' : currentQuestion.type === 'multi' ? '多选题' : '判断题' }}</text><text class="q-score">{{ currentQuestion.score }} 分</text></view><text class="dimension">{{ currentQuestion.dimension }}</text><view class="question-content">{{ currentQuestion.content }}</view>
        <radio-group v-if="currentQuestion.type === 'single'" class="options" @change="(event) => setAnswer(event.detail.value)"><label v-for="option in (currentQuestion.options || [])" :key="optionValue(option)" class="option" :class="{ selected: answers[currentQuestion.question_id] === optionValue(option) }"><radio :value="String(optionValue(option))" :checked="answers[currentQuestion.question_id] === optionValue(option)" color="#2563eb" /><text>{{ optionText(option) }}</text></label></radio-group>
        <checkbox-group v-else-if="currentQuestion.type === 'multi'" class="options" @change="(event) => setAnswer(event.detail.value)"><label v-for="option in (currentQuestion.options || [])" :key="optionValue(option)" class="option" :class="{ selected: (answers[currentQuestion.question_id] || []).includes(optionValue(option)) }"><checkbox :value="String(optionValue(option))" :checked="(answers[currentQuestion.question_id] || []).includes(optionValue(option))" color="#2563eb" /><text>{{ optionText(option) }}</text></label></checkbox-group>
        <radio-group v-else class="options" @change="(event) => setAnswer(event.detail.value)"><label class="option" :class="{ selected: answers[currentQuestion.question_id] === '正确' }"><radio value="正确" :checked="answers[currentQuestion.question_id] === '正确'" color="#2563eb" /><text>正确</text></label><label class="option" :class="{ selected: answers[currentQuestion.question_id] === '错误' }"><radio value="错误" :checked="answers[currentQuestion.question_id] === '错误'" color="#2563eb" /><text>错误</text></label></radio-group>
      </view>
      <view class="answer-sheet"><view class="sheet-title"><text>答题卡</text><text class="sheet-hint">点击题号快速跳转</text></view><view class="sheet-grid"><view v-for="(question, index) in questions" :key="question.question_id" class="sheet-num" :class="[answerClass(question.question_id), { current: index === current }]" @click="goTo(index)">{{ index + 1 }}</view></view></view>
      <view class="footer"><button class="nav-button" :disabled="current === 0" @click="goTo(current - 1)">上一题</button><button v-if="current < total - 1" class="nav-button primary" @click="goTo(current + 1)">下一题</button><button v-else class="nav-button primary" :loading="submitting" @click="submit()">交卷</button></view>
    </template>
  </view>
</template>

<style lang="scss" scoped>
.page { min-height: 100vh; padding-bottom: 180rpx; background: #f5f7fa; }.state { padding: 120rpx 30rpx; color: #98a2b3; text-align: center; font-size: 26rpx; }.state.error { color: #b42318; }
.top { display: flex; align-items: center; justify-content: space-between; gap: 18rpx; padding: 28rpx 30rpx 22rpx; background: #fff; border-bottom: 1rpx solid #edf0f4; }.title-wrap { min-width: 0; flex: 1; }.top-title { display: block; overflow: hidden; color: #1f2937; font-size: 30rpx; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }.top-meta { display: block; margin-top: 8rpx; color: #98a2b3; font-size: 21rpx; }.timer { display: flex; flex: none; flex-direction: column; align-items: center; color: #2563eb; }.timer text { font-size: 34rpx; font-weight: 700; }.timer small { margin-top: 3rpx; color: #98a2b3; font-size: 19rpx; }.timer.danger text { color: #dc2626; }
.progress-row { display: flex; justify-content: space-between; padding: 18rpx 30rpx 12rpx; color: #8a94a6; background: #fff; font-size: 21rpx; }.progress-bar { height: 7rpx; background: #e7ebf1; }.progress-fill { height: 100%; background: #2563eb; transition: width .25s; }
.question-card { margin: 24rpx; padding: 30rpx; background: #fff; border-radius: 18rpx; box-shadow: 0 3rpx 12rpx rgba(16,24,40,.04); }.question-head { display: flex; align-items: center; gap: 14rpx; }.q-number { width: 52rpx; height: 52rpx; color: #fff; background: #2563eb; border-radius: 50%; line-height: 52rpx; text-align: center; font-size: 25rpx; font-weight: 700; }.q-type { color: #667085; font-size: 23rpx; }.q-score { margin-left: auto; color: #c66a08; font-size: 23rpx; }.dimension { display: inline-block; margin-top: 22rpx; padding: 6rpx 13rpx; color: #2563eb; background: #edf3ff; border-radius: 8rpx; font-size: 21rpx; }.question-content { margin: 20rpx 0 30rpx; color: #1f2937; font-size: 31rpx; line-height: 1.7; }.options { display: flex; flex-direction: column; gap: 16rpx; }.option { display: flex; align-items: center; gap: 12rpx; min-height: 76rpx; padding: 0 18rpx; color: #374151; background: #fafbfc; border: 2rpx solid #edf0f4; border-radius: 12rpx; font-size: 27rpx; }.option.selected { color: #1d4ed8; background: #eff5ff; border-color: #8eb5ff; }
.answer-sheet { margin: 24rpx; padding: 26rpx; background: #fff; border-radius: 18rpx; }.sheet-title { display: flex; justify-content: space-between; margin-bottom: 20rpx; color: #344054; font-size: 27rpx; font-weight: 600; }.sheet-hint { color: #98a2b3; font-size: 21rpx; font-weight: normal; }.sheet-grid { display: flex; flex-wrap: wrap; gap: 14rpx; }.sheet-num { width: 62rpx; height: 62rpx; color: #667085; background: #fff; border: 2rpx solid #e5e9f0; border-radius: 10rpx; line-height: 58rpx; text-align: center; font-size: 23rpx; }.sheet-num.done { color: #2563eb; background: #edf3ff; border-color: #8eb5ff; }.sheet-num.current { color: #fff; background: #2563eb; border-color: #2563eb; }
.footer { position: fixed; right: 0; bottom: 0; left: 0; display: flex; gap: 18rpx; padding: 20rpx 30rpx calc(20rpx + env(safe-area-inset-bottom)); background: #fff; box-shadow: 0 -4rpx 14rpx rgba(16,24,40,.08); z-index: 10; }.nav-button { flex: 1; height: 82rpx; margin: 0; color: #344054; background: #fff; border: 2rpx solid #e0e5ec; border-radius: 41rpx; font-size: 27rpx; line-height: 78rpx; }.nav-button::after { border: 0; }.nav-button.primary { color: #fff; background: #2563eb; border-color: #2563eb; }
</style>
