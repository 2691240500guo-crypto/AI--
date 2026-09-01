<template>
  <div class="agent-page">
    <!-- ===== 历史对话列表（activeConvId 为空时显示） ===== -->
    <div v-if="!activeConvId" class="conv-list-page">
      <div class="conv-list-header">
        <h2>💬 我的对话</h2>
        <el-button type="primary" :icon="Promotion" @click="createNewConv">+ 新对话</el-button>
      </div>

      <el-empty v-if="!conversations.length" description="还没有对话，开始第一次吧！" />

      <el-row v-else :gutter="16">
        <el-col v-for="c in conversations" :key="c.id" :xs="24" :sm="12" :md="8" :lg="6">
          <el-card class="conv-card" shadow="hover" @click="openConv(c.id)">
            <div class="conv-title">{{ c.title || '（未命名对话）' }}</div>
            <div class="conv-preview">{{ c.preview || '点击查看' }}</div>
            <div class="conv-meta">
              <span>💬 {{ c.messageCount }} 条消息</span>
              <span>{{ formatTime(c.updatedAt) }}</span>
            </div>
            <el-button class="conv-del" size="small" type="danger" plain :icon="Delete" @click.stop="deleteConv(c.id)">删除</el-button>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- ===== 对话界面（activeConvId 有值时显示） ===== -->
    <template v-else>
      <!-- 顶部操作栏（返回 + 当前对话标题） -->
      <div class="conv-topbar">
        <el-button :icon="ArrowLeft" plain @click="backToList">← 对话列表</el-button>
        <span class="conv-current-title">{{ currentConv?.title || '新对话' }}</span>
        <el-button class="new-conv-btn" :icon="Promotion" plain size="small" @click="createNewConv">+ 新对话</el-button>
      </div>

      <!-- 对话流（可滚动） -->
      <div class="chat-list" ref="chatListRef">
        <!-- 空状态 -->
        <div v-if="!messages.length" class="chat-empty">
          <div class="hero-icon">🤖</div>
          <h1 class="hero-title">岗位人才匹配Agent</h1>
          <p class="hero-subtitle">岗位需求解析 · 双向智能匹配 · 适配度打分 · 原因解释 · 可视化展示</p>

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
          <div v-if="m.role === 'user'" class="msg-row user-msg">
            <div class="msg-bubble user-bubble">{{ m.text }}</div>
          </div>
          <div v-else class="msg-row agent-msg">
            <div class="agent-avatar">AI</div>
            <div class="agent-content">
              <div class="reply-bubble" :class="{ 'is-loading': m.loading }">
                <template v-if="m.loading">思考中…</template>
                <template v-else>{{ m.reply || '（无回复）' }}</template>
              </div>

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

              <el-card v-if="m.results && m.results.length && !m.chartType" shadow="never" class="section-card">
                <template #header><span>🏆 候选人才（按匹配度排序）</span></template>
                <div v-for="r in m.results" :key="r.talent_id" class="cand-row">
                  <div class="cand-left">
                    <el-tag :type="r.rank <= 3 ? 'danger' : 'info'" effect="dark" round size="small" class="cand-rank">{{ r.rank }}</el-tag>
                    <el-avatar :size="34" :src="r.avatar || ''" class="cand-avatar">{{ (r.talent_name || '人').slice(0, 1) }}</el-avatar>
                    <div class="cand-id">
                      <div class="cand-name">{{ r.talent_name || `人才${r.talent_id}` }}<span class="cand-tag">#{{ r.talent_id }}</span></div>
                      <div class="cand-meta">{{ r.current_title || '暂无职位' }} · {{ r.degree || '学历未知' }} · {{ r.years || 0 }}年经验</div>
                    </div>
                  </div>
                  <div class="cand-right">
                    <div class="cand-score">
                      <el-progress :percentage="Number(r.score)" :color="scoreColor(r.score)" :stroke-width="9" class="cand-bar" />
                      <b class="cand-num">{{ r.score }}</b>
                    </div>
                    <div class="cand-dims">
                      <span v-for="(v, k) in parseDims(r.dimension_json)" :key="k" class="dim-chip">
                        {{ DIM_LABEL[k] }}<b>{{ v }}</b>
                      </span>
                    </div>
                    <div v-if="r.explain" class="cand-explain">💬 {{ r.explain }}</div>
                  </div>
                </div>
              </el-card>

              <el-card v-if="m.reverseResults && m.reverseResults.length" shadow="never" class="section-card">
                <template #header><span>🔄 人才适配岗位（反向匹配）</span></template>
                <el-table :data="m.reverseResults" stripe border>
                  <el-table-column label="岗位" prop="position_name" min-width="160" />
                  <el-table-column label="匹配度" width="180">
                    <template #default="{ row }">
                      <el-progress :percentage="Number(row.score)" :color="scoreColor(row.score)" :stroke-width="10" />
                    </template>
                  </el-table-column>
                  <el-table-column label="四维得分" min-width="210">
                    <template #default="{ row }">
                      <div class="dims">
                        <span v-for="(v, k) in parseDims(row.dimension_json)" :key="k" class="dim-chip">
                          {{ DIM_LABEL[k] }}<b>{{ v }}</b>
                        </span>
                      </div>
                    </template>
                  </el-table-column>
                </el-table>
              </el-card>

              <el-card v-if="m.chartType && m.results && m.results.length" shadow="never" class="section-card charts-card">
                <template #header>
                  <span>📊 {{ CHART_LABEL[m.chartType] || '' }} · {{ m.chartTitle || '候选人匹配度' }}</span>
                </template>
                <div class="single-chart-wrap">
                  <div :data-chart-id="m.id" :data-chart-type="'bar'" v-show="m.chartType === 'bar'" class="chart chart-single" />
                  <div :data-chart-id="m.id" :data-chart-type="'line'" v-show="m.chartType === 'line'" class="chart chart-single" />
                  <div :data-chart-id="m.id" :data-chart-type="'pie'" v-show="m.chartType === 'pie'" class="chart chart-single" />
                </div>
              </el-card>
            </div>
          </div>
        </template>
      </div>

      <!-- 输入栏（固定底部） -->
      <div class="chat-input-bar">
        <div class="chat-input-inner">
          <div class="chat-input-card">
            <el-input
              v-model="nlpInput"
              type="textarea"
              :rows="2"
              :autosize="{ minRows: 2, maxRows: 6 }"
              placeholder="试试这样说：帮我找适合后端开发的人才（Enter 发送，Shift+Enter 换行）"
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
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Delete, Promotion } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { agentChat } from '@/api/matching'

const DIM_LABEL = { skill: '技能', degree: '学历', years: '经验', quality: '综合素质' }
const CHART_LABEL = { bar: '柱状图', line: '折线图', pie: '饼图' }
const CHART_TITLE = {
  bar: '各候选人匹配度对比',
  line: '候选人匹配度走势',
  pie: '匹配结果分布（推荐/候选/储备）',
}

const QUICK_QUERIES = [
  '帮我找适合后端开发的人才',
  '分析后端开发工程师的岗位要求',
  '生成后端开发的折线图',
  '为什么人才4排第一',
  '人才5适合什么岗位',
]

const CAPABILITIES = [
  { icon: '📋', text: '岗位解析', desc: 'AI 拆解任职要求/技能/经验门槛' },
  { icon: '🎯', text: '人才匹配', desc: '向量检索+硬过滤+软加权打分排序' },
  { icon: '📊', text: '可视化', desc: '柱状图/折线图/饼图展示匹配维度' },
  { icon: '💬', text: '匹配解释', desc: '说明推荐依据与维度得分' },
]

// ===== 对话历史（localStorage 持久化） =====
const STORAGE_KEY = 'agent_conv_history_v1'
const conversations = ref(loadConversations())
const activeConvId = ref(null)
const messages = ref([])
let msgSeq = 0
let chartInstances = new Map()

const currentConv = computed(() => conversations.value.find((c) => c.id === activeConvId.value))

function loadConversations() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveConversations() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations.value))
  } catch { /* ignore */ }
}

function createNewConv() {
  // 保存当前对话（如果有）
  if (activeConvId.value) {
    persistCurrentConv()
    disposeCharts()
  }
  activeConvId.value = null
  messages.value = []
  msgSeq = 0
}

function persistCurrentConv() {
  if (!activeConvId.value) return
  const c = conversations.value.find((x) => x.id === activeConvId.value)
  if (!c) return
  // 过滤掉 loading 状态的消息
  const cleanMsgs = messages.value.filter((m) => !m.loading).map((m) => {
    const { loading, chartType, results, reverseResults, parsed, ...rest } = m
    return { ...rest, chartType, results: results || [], reverseResults: reverseResults || [], parsed: parsed || null }
  })
  c.messages = cleanMsgs
  c.messageCount = cleanMsgs.length
  c.preview = cleanMsgs.find((m) => m.role === 'user')?.text || c.preview || ''
  c.updatedAt = Date.now()
  if (!c.title) c.title = (c.preview || '新对话').slice(0, 20)
}

function openConv(id) {
  // 保存当前
  if (activeConvId.value) persistCurrentConv()
  const c = conversations.value.find((x) => x.id === id)
  if (!c) return
  activeConvId.value = id
  // 恢复消息
  messages.value = (c.messages || []).map((m) => ({ ...m, loading: false }))
  msgSeq = messages.value.reduce((acc, m) => Math.max(acc, m.id || 0), 0)
  // 重渲染图表
  nextTick(() => {
    setTimeout(() => {
      messages.value.forEach((m) => {
        if (m.chartType && m.results && m.results.length) renderChart(m)
      })
    }, 100)
  })
}

function backToList() {
  persistCurrentConv()
  saveConversations()
  activeConvId.value = null
  disposeCharts()
  messages.value = []
}

async function deleteConv(id) {
  try {
    await ElMessageBox.confirm('确定删除这条对话吗？', '确认', { type: 'warning' })
  } catch { return }
  conversations.value = conversations.value.filter((c) => c.id !== id)
  saveConversations()
  if (activeConvId.value === id) {
    activeConvId.value = null
    messages.value = []
    disposeCharts()
  }
  ElMessage.success('已删除')
}

function formatTime(t) {
  if (!t) return ''
  const d = new Date(t)
  const now = new Date()
  const diff = (now - d) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} 天前`
  return d.toLocaleDateString('zh-CN')
}

function fillNlp(text) { nlpInput.value = text }

// ===== 自然语言聊天 =====
async function handleChat() {
  const msg = nlpInput.value.trim()
  if (!msg) return ElMessage.warning('请输入指令')

  // 首次发送：自动创建对话
  if (!activeConvId.value) {
    const id = `c_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
    const newConv = {
      id, title: msg.slice(0, 20), preview: msg,
      messages: [], messageCount: 0,
      createdAt: Date.now(), updatedAt: Date.now(),
    }
    conversations.value.unshift(newConv)
    activeConvId.value = id
  }

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
    } else if (intent === 'match' && result) {
      agentMsg.results = result.results || []
    } else if (intent === 'chart' && result) {
      agentMsg.chartType = data.chart_type || 'bar'
      agentMsg.results = result.results || []
      agentMsg.chartTitle = CHART_TITLE[agentMsg.chartType] || '候选人匹配度'
      await nextTick()
      setTimeout(() => renderChart(agentMsg), 50)
    } else if (intent === 'reverse' && result) {
      agentMsg.reverseResults = result.results || []
    }
    // 自动保存
    persistCurrentConv()
    saveConversations()
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

// ===== 工具 =====
function parseDims(json) {
  if (!json) return {}
  try { return JSON.parse(json) } catch { return {} }
}
function scoreColor(s) {
  const n = Number(s)
  if (n >= 80) return '#67c23a'
  if (n >= 60) return '#e6a23c'
  return '#f56c6c'
}

// ===== 图表渲染 =====
function renderChart(m) {
  const type = m.chartType
  const key = `${m.id}:${type}`
  const el = document.querySelector(`[data-chart-id="${m.id}"][data-chart-type="${type}"]`)
  if (!el) return
  let chart = chartInstances.get(key)
  if (!chart) {
    chart = echarts.init(el)
    chartInstances.set(key, chart)
  }
  if (type === 'bar') setBarOption(chart, m.results)
  else if (type === 'line') setLineOption(chart, m.results)
  else if (type === 'pie') setPieOption(chart, m.results)
  chart.resize()
}

function setBarOption(chart, list) {
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 30, top: 30, bottom: 40 },
    xAxis: { type: 'category', name: '候选人', data: list.map((r) => r.talent_name || `人才${r.talent_id}`), axisLabel: { fontSize: 12, color: '#6e7681', interval: 0, rotate: 30 } },
    yAxis: { type: 'value', name: '匹配度', max: 100, axisLabel: { fontSize: 12, color: '#6e7681' }, splitLine: { lineStyle: { color: '#f0f0f0' } } },
    series: [{ type: 'bar', barWidth: 28, data: list.map((r) => Number(r.score)), itemStyle: { color: (p) => (p.value >= 80 ? '#67c23a' : p.value >= 60 ? '#e6a23c' : '#f56c6c') }, label: { show: true, position: 'top', fontSize: 11, color: '#6e7681' } }],
  }, true)
}

function setLineOption(chart, list) {
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 60, top: 30, bottom: 50 },
    xAxis: { type: 'category', name: '排名', data: list.map((r) => r.rank), boundaryGap: false, axisLabel: { fontSize: 12, color: '#6e7681' } },
    yAxis: { type: 'value', name: '匹配度', min: (v) => Math.max(0, Math.floor(v.min - 5)), max: 100, axisLabel: { fontSize: 12, color: '#6e7681' }, splitLine: { lineStyle: { color: '#f0f0f0' } } },
    series: [{ type: 'line', smooth: false, symbol: 'circle', symbolSize: 8, data: list.map((r) => ({ value: Number(r.score), name: `人才${r.talent_id}` })), itemStyle: { color: '#409eff', borderColor: '#fff', borderWidth: 2 }, lineStyle: { color: '#409eff', width: 2 }, label: { show: true, position: 'top', fontSize: 11, color: '#6e7681', formatter: '{c}' }, areaStyle: { color: 'rgba(64, 158, 255, 0.08)' } }],
  }, true)
}

function setPieOption(chart, list) {
  const dist = { 推荐: 0, 候选: 0, 储备: 0 }
  list.forEach((r) => { const s = Number(r.score); if (s >= 80) dist.推荐++; else if (s >= 60) dist.候选++; else dist.储备++ })
  chart.setOption({
    tooltip: { trigger: 'item' }, legend: { bottom: 0 },
    series: [{ type: 'pie', radius: ['40%', '65%'], data: Object.entries(dist).map(([name, value]) => ({ name, value })), label: { formatter: '{b}: {c} 人 ({d}%)', fontSize: 12, color: '#6e7681' } }],
  }, true)
}

function resizeAll() { chartInstances.forEach((c) => c.resize()) }
function disposeCharts() { chartInstances.forEach((c) => { try { c.dispose() } catch { /* noop */ } }); chartInstances.clear() }
onMounted(() => window.addEventListener('resize', resizeAll))
onBeforeUnmount(() => { window.removeEventListener('resize', resizeAll); disposeCharts() })
</script>

<style scoped>
.agent-page {
  padding: 0 0 200px;
  min-height: 100vh;
}

/* ===== 对话列表页 ===== */
.conv-list-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px 16px;
}
.conv-list-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 20px;
}
.conv-list-header h2 {
  margin: 0; font-size: 22px; font-weight: 700; color: #1f2328;
}
.conv-card {
  cursor: pointer; transition: all 0.2s; border-radius: 10px; height: 160px;
  position: relative;
}
.conv-card:hover { transform: translateY(-2px); border-color: #409eff; box-shadow: 0 4px 12px rgba(64, 158, 255, 0.12); }
.conv-card :deep(.el-card__body) { padding: 16px; height: 100%; display: flex; flex-direction: column; }
.conv-title {
  font-size: 15px; font-weight: 700; color: #1f2328;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.conv-preview {
  font-size: 12px; color: #6e7681; margin-top: 6px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; line-height: 1.5;
}
.conv-meta {
  margin-top: auto;
  display: flex; justify-content: space-between; align-items: center;
  font-size: 11px; color: #8b949e;
}
.conv-del { position: absolute; bottom: 8px; right: 8px; opacity: 0; transition: opacity 0.2s; }
.conv-card:hover .conv-del { opacity: 1; }

/* ===== 对话顶栏 ===== */
.conv-topbar {
  max-width: 760px; margin: 0 auto; padding: 14px 16px 0;
  display: flex; align-items: center; gap: 10px;
}
.conv-current-title {
  font-size: 15px; font-weight: 600; color: #1f2328;
  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.new-conv-btn { flex-shrink: 0; }

/* ===== 对话流 ===== */
.chat-list {
  max-width: 760px;
  margin: 0 auto;
  padding: 16px 16px 0;
}

/* ===== 空状态 ===== */
.chat-empty { text-align: center; padding: 60px 0 40px; }
.hero-icon { font-size: 44px; line-height: 1; margin-bottom: 12px; }
.hero-title { font-size: 26px; font-weight: 700; color: #1f2328; margin: 0 0 6px; }
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
  max-width: 75%; background: #409eff; color: #fff;
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
@keyframes typing { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }

/* ===== 结果卡片 ===== */
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

/* ===== 候选列表 ===== */
.cand-row {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 4px; border-bottom: 1px solid #f0f2f5;
}
.cand-row:last-child { border-bottom: none; }
.cand-row:hover { background: #fafbfc; border-radius: 8px; }
.cand-left { display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0; }
.cand-rank { flex-shrink: 0; }
.cand-avatar { background: #409eff; color: #fff; font-weight: 600; flex-shrink: 0; }
.cand-name { font-weight: 600; color: #1f2328; }
.cand-tag { color: #c0c4cc; font-size: 12px; margin-left: 4px; }
.cand-meta { font-size: 12px; color: #8b949e; margin-top: 2px; }
.cand-right { flex: 1.2; min-width: 0; }
.cand-score { display: flex; align-items: center; gap: 8px; }
.cand-bar { flex: 1; }
.cand-num { font-size: 15px; font-weight: 700; color: #409eff; }
.cand-dims { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }
.dim-chip {
  font-size: 11px; color: #606266; background: #f5f7fa;
  border: 1px solid #e5e7eb; border-radius: 4px; padding: 2px 6px;
}
.dim-chip b { color: #409eff; margin-left: 2px; }
.cand-explain {
  margin-top: 8px; font-size: 12px; color: #606266;
  background: #f0f9eb; border: 1px solid #e1f3d8; border-radius: 6px;
  padding: 8px 10px; line-height: 1.6;
}
.dims { display: flex; gap: 6px; flex-wrap: wrap; }

/* ===== 图表 ===== */
.charts-card { background: #fafbfc; }
.single-chart-wrap { max-width: 640px; margin: 0 auto; }
.chart { width: 100%; }
.chart-single { height: 360px; }

/* ===== 输入栏 ===== */
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