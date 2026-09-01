<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAnswerView, submitAnswer } from '@/api/assessment'

const route = useRoute()
const router = useRouter()
const loading = ref(true)
const view = ref(null)
const answers = ref({})          // question_id -> user_answer
const submitting = ref(false)
const currentIndex = ref(0)
const remain = ref(0)            // 剩余秒数
const timer = ref(null)
const draftKey = ref('')

const draftSaved = ref(false)

const currentQuestion = computed(() => view.value?.questions[currentIndex.value])
const total = computed(() => view.value?.questions.length || 0)
const answeredCount = computed(() => Object.keys(answers.value).filter(k => answers.value[k] && answers.value[k].length).length)
const fmtRemain = computed(() => {
  const m = Math.floor(remain.value / 60)
  const s = remain.value % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})
const remainPercent = computed(() => {
  if (!view.value) return 100
  return Math.round(remain.value / (view.value.duration * 60) * 100)
})

async function load() {
  loading.value = true
  try {
    const res = await getAnswerView(route.params.id)
    view.value = res.data
    draftKey.value = `asm_draft_${route.params.id}`
    // 回填服务端已有答案 + 本地草稿（本地草稿优先）
    const serverAnswers = {}
    for (const a of res.data.previous_answers || []) {
      if (a.question_type === 'multi') serverAnswers[a.question_id] = a.user_answer.split(',')
      else serverAnswers[a.question_id] = a.user_answer
    }
    const draft = uniStorageGet(draftKey.value)
    answers.value = draft || serverAnswers
    startTimer()
  } finally { loading.value = false }
}

function uniStorageGet(key) {
  try { return JSON.parse(localStorage.getItem(key)) } catch { return null }
}
function uniStorageSet(key, val) {
  try { localStorage.setItem(key, JSON.stringify(val)) } catch {}
}

function startTimer() {
  remain.value = view.value.duration * 60
  timer.value = setInterval(() => {
    remain.value--
    if (remain.value <= 0) {
      clearInterval(timer.value)
      ElMessage.warning('时间到，自动交卷')
      submit(true)
    }
  }, 1000)
}

function saveDraft() {
  uniStorageSet(draftKey.value, answers.value)
  draftSaved.value = true
  setTimeout(() => (draftSaved.value = false), 1500)
}

function goTo(i) {
  if (i >= 0 && i < total.value) currentIndex.value = i
}

function prevQ() { goTo(currentIndex.value - 1) }
function nextQ() { goTo(currentIndex.value + 1) }

async function submit(auto = false) {
  if (submitting.value) return
  const unanswered = total.value - answeredCount.value
  if (!auto && unanswered > 0) {
    try {
      await ElMessageBox.confirm(`还有 ${unanswered} 题未作答，确定交卷？`, '提示', { type: 'warning' })
    } catch { return }
  }
  submitting.value = true
  try {
    const payload = { answers: view.value.questions.map(q => ({ question_id: q.id, user_answer: normalizeAnswer(q, answers.value[q.id]) })) }
    const res = await submitAnswer(route.params.id, payload)
    localStorage.removeItem(draftKey.value)
    ElMessage.success(`交卷成功，得分 ${res.data.score} 分`)
    router.replace('/assessment/result')
  } finally { submitting.value = false }
}

function normalizeAnswer(q, val) {
  if (!val || !val.length) return ''
  if (q.type === 'multi') return [...val].sort().join(',')
  return val
}

// 防切屏提醒（简单版）
function onVisibility() {
  if (document.hidden && view.value && !submitting.value) {
    ElMessage.warning('检测到离开答题页面，请注意作答时间')
  }
}

onMounted(() => {
  load()
  document.addEventListener('visibilitychange', onVisibility)
})
onUnmounted(() => {
  clearInterval(timer.value)
  document.removeEventListener('visibilitychange', onVisibility)
  if (view.value) uniStorageSet(draftKey.value, answers.value)
})
</script>

<template>
  <div class="answer-page">
    <div v-if="loading" class="center"><el-skeleton :rows="8" animated /></div>
    <template v-else-if="view">
      <header class="top">
        <div class="title">{{ view.paper_title }}</div>
        <div class="meta">
          共 {{ total }} 题 · 总分 {{ view.total_score }}
        </div>
        <div class="timer" :class="{ danger: remain < 300 }">
          <span class="timer-icon">⏱</span> {{ fmtRemain }}
        </div>
        <el-button type="primary" :loading="submitting" @click="submit()">交卷</el-button>
      </header>

      <!-- 答题进度条 -->
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: (answeredCount / total * 100) + '%' }"></div>
        <span class="progress-txt">已答 {{ answeredCount }}/{{ total }}</span>
      </div>

      <div class="main-wrap">
        <!-- 左侧：题目导航 -->
        <aside class="nav-panel">
          <div class="nav-title">答题卡</div>
          <div class="nav-grid">
            <button v-for="(q, i) in view.questions" :key="q.id" class="nav-num"
              :class="{ active: i === currentIndex, done: answers[q.id] && answers[q.id].length }"
              @click="goTo(i)">{{ i + 1 }}</button>
          </div>
          <div class="nav-legend">
            <span><i class="dot done"></i>已答</span>
            <span><i class="dot cur"></i>当前</span>
            <span><i class="dot"></i>未答</span>
          </div>
        </aside>

        <!-- 右侧：当前题目 -->
        <main class="question-area">
          <el-card v-if="currentQuestion" class="q-card">
            <div class="q-head">
              <span class="q-no">{{ currentIndex + 1 }}</span>
              <span class="q-type">{{ currentQuestion.type === 'single' ? '单选' : currentQuestion.type === 'multi' ? '多选' : '判断' }}</span>
              <span class="q-score">{{ currentQuestion.score }} 分</span>
              <span class="q-dim">{{ currentQuestion.dimension || '' }}</span>
            </div>
            <div class="q-content">{{ currentQuestion.content }}</div>

            <el-radio-group v-if="currentQuestion.type === 'single'" v-model="answers[currentQuestion.id]" class="opts">
              <el-radio v-for="o in currentQuestion.options" :key="o.key" :value="o.key" class="opt">{{ o.key }}. {{ o.text }}</el-radio>
            </el-radio-group>

            <el-checkbox-group v-else-if="currentQuestion.type === 'multi'" v-model="answers[currentQuestion.id]" class="opts">
              <el-checkbox v-for="o in currentQuestion.options" :key="o.key" :value="o.key" class="opt">{{ o.key }}. {{ o.text }}</el-checkbox>
            </el-checkbox-group>

            <el-radio-group v-else v-model="answers[currentQuestion.id]" class="opts">
              <el-radio value="true" class="opt">正确</el-radio>
              <el-radio value="false" class="opt">错误</el-radio>
            </el-radio-group>

            <div class="q-foot">
              <el-button :disabled="currentIndex === 0" @click="prevQ">上一题</el-button>
              <el-button v-if="currentIndex < total - 1" type="primary" plain @click="nextQ">下一题</el-button>
              <el-button v-else type="success" plain @click="submit()">最后一题，交卷</el-button>
              <el-button link type="info" @click="saveDraft">
                {{ draftSaved ? '✓ 草稿已保存' : '保存草稿' }}
              </el-button>
            </div>
          </el-card>
        </main>
      </div>
    </template>
  </div>
</template>

<style scoped>
.answer-page { min-height: 100vh; background: #f5f7fa; }
.center { padding: 60px 20px; max-width: 800px; margin: 0 auto; }

.top { position: sticky; top: 0; z-index: 10; background: #fff; padding: 14px 24px; display: flex; align-items: center; gap: 20px; border-bottom: 1px solid #eef1f5; }
.title { font-size: 18px; font-weight: 600; }
.meta { color: #888; font-size: 13px; flex: 1; }
.timer { font-size: 20px; font-weight: 600; color: #1f2937; display: flex; align-items: center; gap: 4px; }
.timer.danger { color: #dc2626; animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0.5; } }

.progress-bar { position: relative; height: 6px; background: #e5e7eb; }
.progress-fill { height: 100%; background: #4f46e5; transition: width .3s; }
.progress-txt { position: absolute; right: 12px; top: -20px; font-size: 12px; color: #888; }

.main-wrap { max-width: 960px; margin: 20px auto; padding: 0 16px 60px; display: flex; gap: 20px; align-items: flex-start; }
.nav-panel { width: 220px; background: #fff; border-radius: 12px; padding: 16px; position: sticky; top: 70px; }
.nav-title { font-size: 14px; font-weight: 500; margin-bottom: 12px; color: #1f2937; }
.nav-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
.nav-num { width: 100%; height: 32px; border: 1px solid #e5e7eb; border-radius: 6px; background: #fff; color: #6b7280; font-size: 13px; cursor: pointer; }
.nav-num.done { background: #eef2ff; border-color: #6366f1; color: #4f46e5; font-weight: 500; }
.nav-num.active { background: #4f46e5; border-color: #4f46e5; color: #fff; }
.nav-legend { margin-top: 14px; display: flex; flex-direction: column; gap: 6px; font-size: 12px; color: #888; }
.nav-legend span { display: flex; align-items: center; gap: 6px; }
.dot { width: 12px; height: 12px; border-radius: 3px; background: #fff; border: 1px solid #e5e7eb; display: inline-block; }
.dot.done { background: #eef2ff; border-color: #6366f1; }
.dot.cur { background: #4f46e5; border-color: #4f46e5; }

.question-area { flex: 1; min-width: 0; }
.q-card { }
.q-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.q-no { width: 26px; height: 26px; border-radius: 50%; background: #4f46e5; color: #fff; text-align: center; line-height: 26px; font-size: 14px; }
.q-type { color: #888; font-size: 12px; }
.q-score { color: #f59e0b; font-size: 13px; }
.q-dim { margin-left: auto; color: #9ca3af; font-size: 12px; }
.q-content { font-size: 15px; line-height: 1.7; margin-bottom: 18px; }
.opts { display: flex; flex-direction: column; gap: 10px; align-items: flex-start; }
.opt { height: auto; padding: 6px 0; }
.q-foot { margin-top: 20px; display: flex; gap: 10px; align-items: center; }
</style>
