<template>
  <div class="agent-page">
    <!-- ===== 对话流（可滚动） ===== -->
    <div class="chat-list" ref="chatListRef">
      <!-- 空状态：欢迎语 + 能力 + 快问 -->
      <div v-if="!messages.length" class="chat-empty">
        <div class="hero-icon">📊</div>
        <h1 class="hero-title">岗位图表生成Agent</h1>
        <p class="hero-subtitle">一句话生成任意岗位的折线图 / 柱状图 / 饼图</p>

        <div class="hint-block">
          <div class="hint-label">我能帮你做什么</div>
          <div class="cap-row">
            <div v-for="c in CAPABILITIES" :key="c.text" class="cap-chip">
              <span class="cap-icon">{{ c.icon }}</span>
              <div>
                <div class="cap-text">{{ c.text }}</div>
                <div class="cap-desc">{{ c.desc }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="hint-block">
          <div class="hint-label">试试这样问</div>
          <div class="quick-row">
            <span v-for="q in QUICK_QUERIES" :key="q" class="quick-chip" @click="fillNlp(q)">{{ q }}</span>
          </div>
        </div>
      </div>

      <!-- 消息流 -->
      <template v-for="m in messages" :key="m.id">
        <!-- 用户消息 -->
        <div v-if="m.role === 'user'" class="msg-row user-msg">
          <div class="msg-bubble user-bubble">{{ m.text }}</div>
        </div>
        <!-- AI 回复 -->
        <div v-else class="msg-row agent-msg">
          <div class="agent-avatar">AI</div>
          <div class="agent-content">
            <!-- 回复气泡（loading / 文本） -->
            <div class="reply-bubble" :class="{ 'is-loading': m.loading }">
              <template v-if="m.loading">思考中…</template>
              <template v-else>{{ m.reply || '（无回复）' }}</template>
            </div>

            <!-- 岗位解析卡片（parse 意图） -->
            <el-card v-if="m.parsed" shadow="never" class="section-card">
              <template #header>
                <div class="card-header">
                  <span>📋 岗位智能解析：{{ m.parsed.title }}</span>
                  <el-tag v-for="t in m.parsed.tags" :key="t" size="small" class="tag" type="info">{{ t }}</el-tag>
                </div>
              </template>
              <el-row :gutter="16">
                <el-col :span="8">
                  <div class="dim-box">
                    <div class="dim-title">🎯 核心要求</div>
                    <ul class="dim-list">
                      <li v-for="(c, i) in m.parsed.core_requirements" :key="i">{{ c }}</li>
                      <li v-if="!m.parsed.core_requirements.length" class="empty">暂无</li>
                    </ul>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="dim-box">
                    <div class="dim-title">🛠 技能标准</div>
                    <div class="skill-tags">
                      <el-tag v-for="s in m.parsed.skill_standards" :key="s" class="tag" type="primary" effect="plain">{{ s }}</el-tag>
                      <span v-if="!m.parsed.skill_standards.length" class="empty">暂无</span>
                    </div>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="dim-box">
                    <div class="dim-title">📏 门槛条件</div>
                    <div class="gate-line">学历要求：<el-tag size="small" type="warning">{{ m.parsed.degree_threshold || '不限' }}</el-tag></div>
                    <div class="gate-line">经验要求：<el-tag size="small" type="warning">{{ m.parsed.experience_threshold?.text || '不限' }}</el-tag></div>
                    <div class="gate-line">综合素质：{{ m.parsed.quality_dimensions.join('、') || '—' }}</div>
                  </div>
                </el-col>
              </el-row>
            </el-card>

            <!-- 图表（chart 意图：单张对应类型大图） -->
            <el-card v-if="m.chartType && m.results && m.results.length" shadow="never" class="section-card charts-card">
              <template #header>
                <span>📊 {{ CHART_LABEL[m.chartType] || '' }} · {{ m.chartTitle || '候选人匹配度' }}</span>
              </template>
              <div class="single-chart-wrap">
                <div :ref="(el) => bindChartEl(m.id, 'bar', el)" v-show="m.chartType === 'bar'" class="chart chart-single" />
                <div :ref="(el) => bindChartEl(m.id, 'line', el)" v-show="m.chartType === 'line'" class="chart chart-single" />
                <div :ref="(el) => bindChartEl(m.id, 'pie', el)" v-show="m.chartType === 'pie'" class="chart chart-single" />
              </div>
            </el-card>
          </div>
        </div>
      </template>
    </div>

    <!-- ===== 输入栏（固定底部） ===== -->
    <div class="chat-input-bar">
      <div class="chat-input-inner">
        <div class="chat-input-card">
          <el-input
            v-model="nlpInput"
            type="textarea"
            :rows="2"
            :autosize="{ minRows: 2, maxRows: 6 }"
            placeholder="试试这样说：生成后端开发的折线图（Enter 发送，Shift+Enter 换行）"
            :disabled="nlpLoading"
            @keydown.enter.exact.prevent="handleChat"
          />
          <el-button
            class="send-btn"
            type="primary"
            size="large"
            :loading="nlpLoading"
            @click="handleChat"
          >🚀 发送</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { agentChat } from '@/api/matching'

const DIM_LABEL = { skill: '技能', degree: '学历', years: '经验', quality: '综合素质' }
const CHART_LABEL = { bar: '柱状图', line: '折线图', pie: '饼图' }
const CHART_TITLE = {
  bar: '各候选人匹配度对比',
  line: '候选人匹配度走势',
  pie: '匹配结果分布（推荐/候选/储备）',
}

// 一句话快问（点击自动填入）
const QUICK_QUERIES = [
  '生成后端开发的折线图',
  '生成AI架构师的柱状图',
  '生成前端开发的饼图',
  '分析后端开发工程师的岗位要求',
]

const CAPABILITIES = [
  { icon: '📈', text: '折线图', desc: 'Top10 候选人匹配度走势' },
  { icon: '📊', text: '柱状图', desc: '各候选人匹配度对比' },
  { icon: '🥧', text: '饼图', desc: '匹配结果分布占比' },
  { icon: '📋', text: '岗位解析', desc: 'AI 拆解岗位任职要求' },
]

// ===== 状态 =====
const messages = ref([])  // [{id, role, text, reply, loading, parsed, chartType, results, chartTitle}]
const nlpInput = ref('')
const nlpLoading = ref(false)
let msgSeq = 0
let chartEls = new Map()      // `${msgId}:${type}` -> DOM
let chartInstances = new Map()  // `${msgId}:${type}` -> echarts 实例

function fillNlp(text) { nlpInput.value = text }

// ===== 自然语言聊天 =====
async function handleChat() {
  const msg = nlpInput.value.trim()
  if (!msg) return ElMessage.warning('请输入指令')
  nlpLoading.value = true

  const userMsg = { id: ++msgSeq, role: 'user', text: msg }
  const agentMsg = { id: ++msgSeq, role: 'agent', loading: true, reply: '' }
  messages.value.push(userMsg, agentMsg)
  nlpInput.value = ''
  scrollToBottom()

  try {
    const res = await agentChat({ message: msg })
    const data = res.data
    agentMsg.loading = false
    agentMsg.reply = data.reply || ''
    const { intent, result } = data
    if (intent === 'parse' && result) {
      agentMsg.parsed = result
    } else if (intent === 'chart' && result) {
      agentMsg.chartType = data.chart_type || 'bar'
      agentMsg.results = result.results || []
      agentMsg.chartTitle = CHART_TITLE[agentMsg.chartType] || '候选人匹配度'
      // 主动渲染（修改对象内部属性不会触发 watch(messages)）
      await nextTick()
      renderChart(agentMsg)
    }
    // match/reverse/explain/unknown：仅展示 reply
  } finally {
    nlpLoading.value = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
  })
}

// ===== 图表渲染（按消息隔离，chart 意图渲染对应类型单图） =====
function bindChartEl(msgId, type, el) {
  if (el) {
    chartEls.set(`${msgId}:${type}`, el)
  } else {
    chartEls.delete(`${msgId}:${type}`)
  }
}

// 监听消息流：新出现带 chartType 的消息 → 渲染其图表
watch(messages, async (list) => {
  const chartMsgs = list.filter((m) => m.role === 'agent' && m.chartType && m.results && m.results.length)
  for (const m of chartMsgs) {
    await nextTick()
    renderChart(m)
  }
})

function renderChart(m) {
  const type = m.chartType
  const el = chartEls.get(`${m.id}:${type}`)
  if (!el) return
  const key = `${m.id}:${type}`
  // 复用实例或新建
  let chart = chartInstances.get(key)
  if (!chart) {
    chart = echarts.init(el)
    chartInstances.set(key, chart)
  }
  if (type === 'bar') setBarOption(chart, m.results)
  else if (type === 'line') setLineOption(chart, m.results)
  else if (type === 'pie') setPieOption(chart, m.results)
}

function setBarOption(chart, list) {
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 30, top: 30, bottom: 40 },
    xAxis: {
      type: 'category', name: '候选人',
      data: list.map((r) => r.talent_name || `人才${r.talent_id}`),
      axisLabel: { fontSize: 12, color: '#6e7681', interval: 0, rotate: 30 },
    },
    yAxis: {
      type: 'value', name: '匹配度', max: 100,
      axisLabel: { fontSize: 12, color: '#6e7681' },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
    },
    series: [{
      type: 'bar', barWidth: 28,
      data: list.map((r) => Number(r.score)),
      itemStyle: { color: (p) => (p.value >= 80 ? '#67c23a' : p.value >= 60 ? '#e6a23c' : '#f56c6c') },
      label: { show: true, position: 'top', fontSize: 11, color: '#6e7681' },
    }],
  }, true)
}

function setLineOption(chart, list) {
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 30, top: 30, bottom: 40 },
    xAxis: {
      type: 'category', name: '排名',
      data: list.map((r) => r.rank),
      boundaryGap: false,
      axisLabel: { fontSize: 12, color: '#6e7681' },
    },
    yAxis: {
      type: 'value', name: '匹配度', min: (v) => Math.max(0, Math.floor(v.min - 5)), max: 100,
      axisLabel: { fontSize: 12, color: '#6e7681' },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
    },
    series: [{
      type: 'line', smooth: false,
      symbol: 'circle', symbolSize: 8,
      data: list.map((r) => ({ value: Number(r.score), name: `人才${r.talent_id}` })),
      itemStyle: { color: '#409eff', borderColor: '#fff', borderWidth: 2 },
      lineStyle: { color: '#409eff', width: 2 },
      label: { show: true, position: 'top', fontSize: 11, color: '#6e7681', formatter: '{c}' },
      areaStyle: { color: 'rgba(64, 158, 255, 0.08)' },
    }],
  }, true)
}

function setPieOption(chart, list) {
  const dist = { 推荐: 0, 候选: 0, 储备: 0 }
  list.forEach((r) => {
    const s = Number(r.score)
    if (s >= 80) dist.推荐++
    else if (s >= 60) dist.候选++
    else dist.储备++
  })
  chart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie', radius: ['40%', '65%'],
      data: Object.entries(dist).map(([name, value]) => ({ name, value })),
      label: { formatter: '{b}: {c} 人 ({d}%)', fontSize: 12, color: '#6e7681' },
    }],
  }, true)
}

// ===== 生命周期 =====
function resizeAll() {
  chartInstances.forEach((c) => c.resize())
}
onMounted(() => window.addEventListener('resize', resizeAll))
onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeAll)
  chartInstances.forEach((c) => { try { c.dispose() } catch { /* noop */ } })
})
</script>

<style scoped>
.agent-page {
  padding: 0 0 200px;
  min-height: 100vh;
}

/* ===== 对话流 ===== */
.chat-list {
  max-width: 760px;
  margin: 0 auto;
  padding: 24px 16px 0;
}

/* ===== 空状态 ===== */
.chat-empty { text-align: center; padding: 60px 0 40px; }
.hero-icon { font-size: 44px; line-height: 1; margin-bottom: 12px; }
.hero-title { font-size: 26px; font-weight: 700; color: #1f2328; margin: 0 0 6px; letter-spacing: 0.3px; }
.hero-subtitle { font-size: 13px; color: #6e7681; margin: 0 0 24px; line-height: 1.6; }
.hint-block { margin-top: 28px; text-align: left; }
.hint-label { font-size: 12px; font-weight: 600; color: #6e7681; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; }
.cap-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.cap-chip {
  display: flex; align-items: flex-start; gap: 8px; padding: 12px;
  background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; transition: all 0.2s;
}
.cap-chip:hover { border-color: #409eff; box-shadow: 0 2px 8px rgba(64, 158, 255, 0.08); }
.cap-icon { font-size: 20px; line-height: 1; flex-shrink: 0; margin-top: 2px; }
.cap-text { font-size: 13px; font-weight: 600; color: #1f2328; }
.cap-desc { font-size: 11px; color: #8b949e; margin-top: 3px; line-height: 1.5; }
.quick-row { display: flex; flex-wrap: wrap; gap: 8px; }
.quick-chip {
  display: inline-block; padding: 6px 14px; background: #fff;
  border: 1px solid #d0d7de; border-radius: 16px; font-size: 12px;
  color: #1f2328; cursor: pointer; user-select: none; transition: all 0.2s; line-height: 1.5;
}
.quick-chip:hover { background: #f6f8fa; border-color: #409eff; color: #409eff; }

/* ===== 消息流 ===== */
.msg-row { display: flex; margin: 16px 0; gap: 10px; }
.user-msg { justify-content: flex-end; }
.user-bubble {
  max-width: 75%;
  background: #409eff; color: #fff;
  padding: 10px 14px; border-radius: 14px 14px 4px 14px;
  font-size: 14px; line-height: 1.6; word-break: break-word;
}
.agent-msg { align-items: flex-start; }
.agent-avatar {
  width: 32px; height: 32px; flex-shrink: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700;
}
.agent-content { flex: 1; min-width: 0; }
.reply-bubble {
  background: #f6f8fa; border: 1px solid #e5e7eb;
  padding: 10px 14px; border-radius: 14px 14px 14px 4px;
  color: #1f2328; font-size: 14px; line-height: 1.6;
  margin-bottom: 12px;
}
.reply-bubble.is-loading { color: #8b949e; font-style: italic; }
.reply-bubble.is-loading::after {
  content: ''; display: inline-block; width: 6px; height: 6px;
  margin-left: 4px; border-radius: 50%; background: #409eff;
  animation: typing 1s infinite;
}
@keyframes typing {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
}

/* ===== 解析卡片 ===== */
.section-card { margin-top: 12px; border-radius: 10px; }
.card-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dim-box { border: 1px solid #ebeef5; border-radius: 6px; padding: 12px; height: 100%; }
.dim-title { font-weight: 600; margin-bottom: 8px; color: #303133; }
.dim-list { margin: 0; padding-left: 18px; color: #606266; font-size: 13px; }
.dim-list li { margin-bottom: 4px; }
.gate-line { font-size: 13px; color: #606266; margin-bottom: 6px; }
.skill-tags { display: flex; flex-wrap: wrap; }
.empty { color: #c0c4cc; font-size: 13px; }
.tag { margin: 0 4px 4px 0; }

/* ===== 图表 ===== */
.charts-card { background: #fafbfc; }
.single-chart-wrap { max-width: 640px; margin: 0 auto; }
.chart { width: 100%; }
.chart-single { height: 360px; }

/* ===== 输入栏（固定底部，避开侧边栏 220px） ===== */
.chat-input-bar {
  position: fixed; left: 220px; right: 0; bottom: 0;
  background: linear-gradient(to top, #ffffff 70%, rgba(255,255,255,0));
  padding: 16px 16px 20px; z-index: 5;
}
.chat-input-inner { max-width: 760px; margin: 0 auto; }
.chat-input-card {
  display: flex; align-items: flex-end; gap: 10px;
  background: #fff; border: 1px solid #e5e7eb; border-radius: 18px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  padding: 10px 12px 10px 16px;
  transition: border-color 0.2s;
}
.chat-input-card:focus-within { border-color: #409eff; box-shadow: 0 4px 20px rgba(64, 158, 255, 0.12); }
.chat-input-card :deep(.el-textarea__inner) {
  font-size: 15px; padding: 6px 0; border: none; box-shadow: none;
  resize: none; line-height: 1.6; color: #1f2328; background: transparent;
}
.chat-input-card :deep(.el-textarea__inner::placeholder) { color: #a1a8b3; }
.send-btn { border-radius: 14px !important; padding: 0 18px !important; height: 40px !important; }
</style>
