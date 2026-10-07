<script setup>
import { computed, ref } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { analyzeAssessmentVision, getAnswerView, recordAssessmentEvent, saveAnswer, submitAnswer } from '@/api'
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
const visionStatus = ref('idle')
const visionMessage = ref('')
const visionMount = ref(null)
const visionFloat = ref(null)
const floatPos = ref(null)  // { x, y } 由拖拽设置；null 时用 CSS 默认定位
const violationCount = ref(0)
const violationTriggered = ref(false)
const violationLimit = 5
let cameraVideo = null  // 原生 <video> 节点，由 ensureNativeMediaElements 创建
let cameraCanvas = null  // 原生 <canvas> 节点
const isH5 = process.env.UNI_PLATFORM === 'h5'
let resultId = null
let cameraStream = null
let visionTimer = null
let dragState = null  // { pointerId, startX, startY, originX, originY }

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
const visionFloatStyle = computed(() => {
  const base = {
    position: 'fixed',
    top: '96px',
    right: '12px',
    width: '160px',
    height: '160px',
    zIndex: 1000,
    background: '#fff',
    border: '1px solid #bfe7f3',
    borderRadius: '12px',
    boxShadow: '0 6px 20px rgba(85, 188, 235, .22)',
    cursor: 'move',
    userSelect: 'none',
    touchAction: 'none',
    overflow: 'hidden',
  }
  if (!floatPos.value) return base
  // 拖拽后：用 left/top 替换 right
  return { ...base, left: `${floatPos.value.x}px`, top: `${floatPos.value.y}px`, right: 'auto' }
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
    if (isH5) {
      window.addEventListener('blur', onWindowBlur)
      document.addEventListener('visibilitychange', onVisibilityChange)
      setTimeout(setupFloatDrag, 100)
      setTimeout(startVisionMonitor, 300)
    }
  } catch (error) { errorMessage.value = error?.message || '测评加载失败，请返回重试' } finally { loading.value = false }
})

onUnload(() => {
  clearInterval(timer.value); clearTimeout(draftTimer.value); stopVisionMonitor()
  violationCount.value = 0
  violationTriggered.value = false
  if (isH5) { window.removeEventListener('blur', onWindowBlur); document.removeEventListener('visibilitychange', onVisibilityChange) }
})

function onWindowBlur() { recordAssessmentEvent(resultId, 'blur', '答题窗口失去焦点').catch(() => {}) }
function onVisibilityChange() {
  recordAssessmentEvent(resultId, document.hidden ? 'leave' : 'resume', document.hidden ? '页面不可见' : '页面恢复可见').catch(() => {})
}
async function startVisionMonitor() {
  if (!isH5 || !navigator.mediaDevices?.getUserMedia) {
    visionStatus.value = 'unavailable'; visionMessage.value = '当前端不支持浏览器摄像头监控'; return
  }
  // —— 阶段 0：动态创建原生 <video> + <canvas> 挂到 visionMount，彻底绕开 uniapp 模板组件包装 ——
  const videoEl = await ensureNativeMediaElements()
  if (!videoEl) {
    visionStatus.value = 'unavailable'; visionMessage.value = '未找到视频挂载点，可点击重新请求重试'; return
  }
  try {
    // —— 阶段 1：请求摄像头（此步失败 = 浏览器/系统授权问题，会弹窗）——
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: 640, height: 480 }, audio: false })
  } catch (error) {
    failVisionWith(error, 'getUserMedia')
    return
  }
  try {
    // —— 阶段 2：绑定流并播放（此步失败 = video 元素问题）——
    videoEl.srcObject = cameraStream
    await videoEl.play()
  } catch (error) {
    failVisionWith(error, 'videoPlay')
    return
  }
  visionStatus.value = 'active'
  visionMessage.value = '视觉监控已开启'
  captureVisionFrame()
  visionTimer = setInterval(captureVisionFrame, 5000)
}
async function ensureNativeMediaElements() {
  // 最多等 2s 让 visionMount 挂载（路由动画/HMR 可能拖慢）
  let mount = null
  for (let i = 0; i < 20; i++) {
    mount = (visionMount.value && visionMount.value.$el) || visionMount.value
    if (mount && typeof mount.appendChild === 'function') break
    await new Promise((resolve) => setTimeout(resolve, 100))
    mount = null
  }
  if (!mount) return null
  if (!cameraVideo) {
    const v = document.createElement('video')
    v.className = 'camera-preview'
    v.muted = true
    v.setAttribute('playsinline', '')
    v.setAttribute('autoplay', '')
    // ⚠️ 直接 inline style 强制 160×160 正方形，绕开 vue scoped + :deep 在动态 video 上不命中
    v.style.cssText = 'display:block;width:160px;height:160px;object-fit:cover;background:#dcecf1;border-radius:10px;'
    mount.appendChild(v)
    cameraVideo = v
  }
  if (!cameraCanvas) {
    const c = document.createElement('canvas')
    c.style.cssText = 'position:fixed;left:-9999px;top:-9999px;'
    document.body.appendChild(c)
    cameraCanvas = c
  }
  return cameraVideo
}
function failVisionWith(error, stage) {
  visionStatus.value = 'unavailable'
  const name = error?.name || ''
  const msg = error?.message || ''
  console.error(`[vision:${stage}]`, error)
  if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
    visionMessage.value = '摄像头权限被拒绝：请点击右侧"重新请求"，并在地址栏 / 系统设置中允许该站点使用摄像头'
  } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
    visionMessage.value = '未检测到摄像头设备，请检查设备连接或驱动'
  } else if (name === 'NotReadableError' || name === 'TrackStartError') {
    visionMessage.value = '摄像头被其他程序占用（如会议软件），关闭后点击重新请求'
  } else if (name === 'OverconstrainedError') {
    visionMessage.value = '摄像头不支持当前取流参数'
  } else {
    visionMessage.value = `${stage} 失败（${name || '未知错误'}）：${msg || ''}`
  }
  recordAssessmentEvent(resultId, 'vision', `camera_unavailable:${stage}`).catch(() => {})
}
async function retryVisionMonitor() {
  stopVisionMonitor()
  visionStatus.value = 'idle'
  visionMessage.value = ''
  await new Promise((resolve) => setTimeout(resolve, 60))
  await startVisionMonitor()
}
function setupFloatDrag() {
  // 用原生 pointer 事件统一处理鼠标 + 触摸拖拽，挂在浮窗根 DOM 上
  const el = (visionFloat.value && visionFloat.value.$el) || visionFloat.value
  if (!el || el.__draggableInited) return
  el.__draggableInited = true
  el.addEventListener('pointerdown', (e) => {
    if (e.button && e.pointerType === 'mouse') return
    const rect = el.getBoundingClientRect()
    dragState = {
      pointerId: e.pointerId,
      startX: e.clientX, startY: e.clientY,
      originX: rect.left, originY: rect.top
    }
    try { el.setPointerCapture(e.pointerId) } catch (_) {}
    e.preventDefault()
  })
  el.addEventListener('pointermove', (e) => {
    if (!dragState || e.pointerId !== dragState.pointerId) return
    const dx = e.clientX - dragState.startX
    const dy = e.clientY - dragState.startY
    const winW = window.innerWidth, winH = window.innerHeight
    const w = el.offsetWidth, h = el.offsetHeight
    const x = Math.max(0, Math.min(winW - w, dragState.originX + dx))
    const y = Math.max(0, Math.min(winH - h, dragState.originY + dy))
    floatPos.value = { x, y }
    e.preventDefault()
  })
  const endDrag = (e) => {
    if (!dragState) return
    try { el.releasePointerCapture(e.pointerId) } catch (_) {}
    dragState = null
  }
  el.addEventListener('pointerup', endDrag)
  el.addEventListener('pointercancel', endDrag)
}
function stopVisionMonitor() {
  clearInterval(visionTimer); visionTimer = null
  if (cameraStream) cameraStream.getTracks().forEach((track) => track.stop())
  cameraStream = null
}
function captureVisionFrame() {
  if (visionStatus.value !== 'active') return
  const video = cameraVideo
  const canvas = cameraCanvas
  if (!video || !canvas || typeof canvas.getContext !== 'function') return
  if (!video.videoWidth || !video.videoHeight) return
  try {
    canvas.width = 640; canvas.height = Math.round(640 * video.videoHeight / video.videoWidth)
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
  } catch (error) {
    console.error('[vision:capture]', error)
    return
  }
  analyzeAssessmentVision(resultId, canvas.toDataURL('image/jpeg', 0.65)).then((res) => {
    const data = (res && res.data) || {}
    console.log('[vision:response]', res, data)
    if (data.status === 'unavailable') {
      // 模型暂不可用不影响摄像头流，仅更新提示，监控仍保持 active
      visionMessage.value = `⚠ ${data.message || '视觉模型暂不可用'}${data.detail ? `（${data.detail}）` : ''}`
      return
    }
    const signals = data.signals || []
    if (signals.length && !violationTriggered.value) {
      // 累计违规：只增不减，达到阈值自动交卷（中途正常帧不清零）
      violationCount.value += 1
      visionMessage.value = `🚨 违规 ${violationCount.value}/${violationLimit}：${signals.join('、')}`
      if (violationCount.value >= violationLimit) {
        violationTriggered.value = true
        uni.showToast({ title: `累计 ${violationLimit} 次违规，自动交卷`, icon: 'none', duration: 1800 })
        stopVisionMonitor()
        setTimeout(() => submit(true), 200)
      }
    } else {
      // 无违规帧：不清零，仅刷新正常状态文案
      const faceText = data.face_detection_available === false ? '人脸检测降级' : `${data.face_count ?? 0} 张人脸`
      visionMessage.value = `视觉监控已开启（${faceText} · ${data.person_count ?? 0} 个人）${violationCount.value ? `｜已违规 ${violationCount.value}/${violationLimit}` : ''}`
    }
  }).catch((err) => console.error('[vision:api]', err))
}
function startTimer() {
  if (!view.value?.deadline_at) return
  clearInterval(timer.value)
  timer.value = setInterval(() => { remain.value -= 1; if (remain.value <= 0) { remain.value = 0; clearInterval(timer.value); submit(true) } }, 1000)
}
function goTo(index) { if (index >= 0 && index < total.value) current.value = index }
function answerClass(questionId) { return isAnswered(answers.value[questionId]) ? 'done' : '' }
function questionType(type) { return type === 'single' ? '单选题' : type === 'multi' ? '多选题' : type === 'essay' ? '主观题' : '判断题' }

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

      <view v-if="isH5" ref="visionFloat" class="vision-float" :class="[visionStatus, { violation: violationCount > 0 && visionStatus === 'active' }]" :style="visionFloatStyle">
        <view ref="visionMount" class="vision-mount"></view>
        <view class="vision-info" :class="{ violation: violationCount > 0 && visionStatus === 'active' }">
          <text class="vision-text">{{ visionStatus === 'active' ? (visionMessage || '视觉监控已开启') : (visionMessage || '正在请求摄像头权限') }}</text>
          <view v-if="visionStatus === 'unavailable'" class="vision-retry" @click.stop="retryVisionMonitor">
            <text>重新请求</text>
          </view>
        </view>
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
            <radio :value="String(optionValue(option))" :checked="answers[currentQuestion.question_id] === optionValue(option)" color="#55BCEB" />
            <text>{{ optionText(option) }}</text>
          </label>
        </radio-group>
        <checkbox-group v-else-if="currentQuestion.type === 'multi'" class="options" @change="(event) => setAnswer(event.detail.value)">
          <label v-for="option in (currentQuestion.options || [])" :key="optionValue(option)" class="option" :class="{ selected: (answers[currentQuestion.question_id] || []).includes(optionValue(option)) }">
            <checkbox :value="String(optionValue(option))" :checked="(answers[currentQuestion.question_id] || []).includes(optionValue(option))" color="#55BCEB" />
            <text>{{ optionText(option) }}</text>
          </label>
        </checkbox-group>
        <textarea
          v-else-if="currentQuestion.type === 'essay'"
          class="essay-input"
          :value="answers[currentQuestion.question_id] || ''"
          maxlength="5000"
          placeholder="请输入你的答案"
          @input="(event) => setAnswer(event.detail.value)"
        />
        <radio-group v-else class="options" @change="(event) => setAnswer(event.detail.value)">
          <label class="option" :class="{ selected: answers[currentQuestion.question_id] === '正确' }">
            <radio value="正确" :checked="answers[currentQuestion.question_id] === '正确'" color="#55BCEB" />
            <text>正确</text>
          </label>
          <label class="option" :class="{ selected: answers[currentQuestion.question_id] === '错误' }">
            <radio value="错误" :checked="answers[currentQuestion.question_id] === '错误'" color="#55BCEB" />
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

// 摄像头预览浮窗：可拖拽、显示视觉监控状态与违规计数
.vision-float {
  // 尺寸/位置由 inline style 控制（绕开 scoped + :deep 在动态子元素上的不可靠问题）
  overflow: hidden;
  background: #fff;
}

.vision-mount {
  position: relative;
  width: 100%;
  height: 100%;
  background: #dcecf1;
  overflow: hidden;
}

.vision-info {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  gap: 6rpx;
  padding: 6rpx 8rpx;
  color: #27708c;
  background: rgba(238, 250, 255, .92);
  font-size: 11px;
  line-height: 1.3;
  backdrop-filter: blur(4px);
}

.vision-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.vision-float.unavailable .vision-info {
  color: #9a6b28;
  background: #fff8e9;
}

.vision-float.violation .vision-info {
  color: #b3261e;
  background: #fdecea;
}

.vision-float.violation .vision-text {
  font-weight: 700;
}

.vision-retry {
  flex: none;
  padding: 4rpx 12rpx;
  color: #fff;
  background: #e6a23c;
  border-radius: 999rpx;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.4;
  cursor: pointer;
}

.vision-retry:active {
  opacity: .8;
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

.essay-input {
  width: 100%;
  min-height: 260rpx;
  padding: 20rpx;
  color: var(--color-text);
  background: #F9FCFD;
  border: 2rpx solid var(--color-border);
  border-radius: var(--radius-sm);
  box-sizing: border-box;
  font-size: 27rpx;
  line-height: 1.65;
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
  border-color: rgba(85, 188, 235, .45);
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
  border-color: rgba(85, 188, 235, .35);
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
  box-shadow: 0 -8rpx 24rpx rgba(85, 188, 235, .08);
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
