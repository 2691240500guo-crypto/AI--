<template>
  <div class="agent-page">
    <!-- ===== 主对话区（单栏，全宽） ===== -->
    <main class="agent-main">
      <!-- 对话流（可滚动） -->
      <div class="chat-list" ref="chatListRef">
        <!-- 空状态 -->
        <div v-if="!messages.length" class="chat-empty">
          <div class="hero-badge">
            <div class="hero-badge-inner">
              <el-icon :size="34" color="#fff"><MagicStick /></el-icon>
            </div>
          </div>
          <div class="hero-tag">AI Agent</div>
          <h1 class="hero-title">岗位人才匹配Agent</h1>
          <p class="hero-subtitle">岗位需求解析 · 双向智能匹配 · 适配度打分 · 原因解释 · 可视化展示</p>

          <div class="hint-block">
            <div class="hint-label">我能帮你做什么</div>
            <div class="cap-row">
              <div v-for="c in CAPABILITIES" :key="c.text" class="cap-chip">
                <div class="cap-icon-wrap">
                  <el-icon :size="22" :color="c.color"><component :is="c.icon" /></el-icon>
                </div>
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
                <template #header><span>🏆 候选人才（按匹配度排序，点击「匹配依据」看为什么）</span></template>
                <div v-for="r in m.results" :key="r.talent_id" class="cand-wrap">
                  <div class="cand-row">
                    <div class="cand-left" @click="toggleDetail(m, r)">
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
                      <div class="cand-opts">
                        <el-button link type="primary" size="small" @click.stop="toggleDetail(m, r)">
                          {{ isActiveDetail(m, r) ? '收起依据 ▲' : '匹配依据 ▼' }}
                        </el-button>
                        <el-button v-if="r.match_id && !isActiveDetail(m, r)" link type="info" size="small" @click.stop="loadExplain(m, r)">
                          💬 生成解释
                        </el-button>
                      </div>
                    </div>
                  </div>

                  <!-- 匹配依据详情：雷达图 + 四维得分条 + LLM 自然语言解释 -->
                  <div v-if="isActiveDetail(m, r)" class="cand-detail">
                    <div class="detail-grid">
                      <div :data-radar-key="detailKey(m, r)" class="radar-box" />
                      <div class="detail-dims">
                        <div v-for="(v, k) in parseDims(r.dimension_json)" :key="k" class="detail-bar">
                          <span class="detail-dl">{{ DIM_LABEL[k] || k }}</span>
                          <el-progress :percentage="Number(v)" :stroke-width="10" :color="barColor(Number(v))" class="detail-prog" />
                          <b class="detail-dv">{{ v }}</b>
                        </div>
                      </div>
                    </div>
                    <div class="detail-explain">
                      <div class="detail-ex-head">
                        <b>💬 匹配原因（LLM 生成）</b>
                        <el-button v-if="r.match_id && !detailLoading" link type="primary" size="small" @click="loadExplain(m, r, true)">重新生成</el-button>
                      </div>
                      <div v-if="detailLoading" class="detail-ex-loading">AI 正在分析匹配原因…</div>
                      <div v-else class="detail-ex-text">{{ detailExplain || r.explain || '暂无解释，可点击「重新生成」让 AI 分析。' }}</div>
                    </div>
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
                  <el-table-column label="匹配依据" width="120" fixed="right">
                    <template #default="{ row }">
                      <el-button link type="primary" @click="openReverseReason(row)">查看</el-button>
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

      <!-- 输入栏（底部固定） -->
      <div class="chat-input-bar">
        <div class="chat-input-inner">
          <div class="chat-input-card">
            <el-input
              v-model="nlpInput"
              type="textarea"
              :rows="2"
              :autosize="{ minRows: 2, maxRows: 6 }"
              placeholder="试试这样说：帮我找适合后端开发的人才"
              :disabled="nlpLoading"
              class="input-area"
              @keydown.enter.exact.prevent="handleChat"
            />
            <div class="input-footer">
              <span class="input-tip">Enter 发送 · Shift+Enter 换行</span>
              <el-button
                class="send-btn"
                type="primary"
                size="large"
                :loading="nlpLoading"
                @click="handleChat"
              >
                <el-icon style="margin-right: 6px;"><Promotion /></el-icon>
                发送
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 反向匹配：岗位匹配依据弹窗（雷达 + 维度得分 + LLM 解释） -->
    <el-dialog v-model="reverseReason.visible" title="岗位匹配依据" width="560px" @opened="renderReverseReason" @closed="disposeReverseRadar">
      <div v-if="reverseReason.row">
        <div class="rr-top">
          <span class="rr-title">{{ reverseReason.row.position_name }}</span>
          <el-tag :type="Number(reverseReason.row.score) >= 80 ? 'success' : Number(reverseReason.row.score) >= 60 ? 'warning' : 'danger'">
            匹配度 {{ reverseReason.row.score }} 分
          </el-tag>
        </div>
        <div class="rr-grid">
          <div ref="reverseRadarEl" class="radar-box" />
          <div class="detail-dims">
            <div v-for="(v, k) in parseDims(reverseReason.row.dimension_json)" :key="k" class="detail-bar">
              <span class="detail-dl">{{ DIM_LABEL[k] || k }}</span>
              <el-progress :percentage="Number(v)" :stroke-width="10" :color="barColor(Number(v))" class="detail-prog" />
              <b class="detail-dv">{{ v }}</b>
            </div>
          </div>
        </div>
        <div class="detail-explain">
          <div class="detail-ex-head">
            <b>💬 匹配原因（LLM 生成）</b>
            <el-button v-if="reverseReason.row.match_id" link type="primary" size="small"
              :loading="reverseReason.loading" @click="loadReverseReasonExplain(true)">重新生成</el-button>
          </div>
          <div v-if="reverseReason.loading" class="detail-ex-loading">AI 正在分析匹配原因…</div>
          <div v-else class="detail-ex-text">{{ reverseReason.explain || reverseReason.row.explain || '暂无解释，可点击「重新生成」让 AI 分析。' }}</div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Aim, ChatLineRound, Document, MagicStick, Promotion, TrendCharts,
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { agentChat, getExplain } from '@/api/matching'

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
  { icon: Document, color: '#409eff', text: '岗位解析', desc: 'AI 拆解任职要求/技能/经验门槛' },
  { icon: Aim, color: '#67c23a', text: '人才匹配', desc: '向量检索+硬过滤+软加权打分排序' },
  { icon: TrendCharts, color: '#e6a23c', text: '可视化', desc: '柱状图/折线图/饼图展示匹配维度' },
  { icon: ChatLineRound, color: '#9c64f6', text: '匹配解释', desc: '说明推荐依据与维度得分' },
]

// ===== 对话历史（localStorage 持久化） =====
const STORAGE_KEY = 'agent_conv_history_v2'
const conversations = ref(loadConversations())
const activeConvId = ref(null)
const messages = ref([])
const nlpInput = ref('')
const nlpLoading = ref(false)
let msgSeq = 0
let chartInstances = new Map()

// 按时间分组（今天/昨天/更早）
const groupedConvs = computed(() => {
  const now = Date.now()
  const oneDay = 86400 * 1000
  const today = [], yesterday = [], older = []
  for (const c of conversations.value) {
    if (now - c.updatedAt < oneDay) today.push(c)
    else if (now - c.updatedAt < 2 * oneDay) yesterday.push(c)
    else older.push(c)
  }
  const groups = []
  if (today.length) groups.push({ label: '今天', items: today })
  if (yesterday.length) groups.push({ label: '昨天', items: yesterday })
  if (older.length) groups.push({ label: '更早', items: older })
  return groups
})

function loadConversations() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const list = JSON.parse(raw)
    // 过滤掉旧版本可能残留的 loading 字段
    return list.map((c) => ({ ...c, messages: (c.messages || []).map((m) => ({ ...m, loading: false })) }))
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
  // 保存当前
  if (activeConvId.value) persistCurrentConv()
  disposeCharts()
  activeConvId.value = null
  messages.value = []
  msgSeq = 0
}

function persistCurrentConv() {
  if (!activeConvId.value) return
  const c = conversations.value.find((x) => x.id === activeConvId.value)
  if (!c) return
  const cleanMsgs = messages.value.filter((m) => !m.loading).map((m) => ({
    id: m.id, role: m.role, text: m.text, reply: m.reply,
    chartType: m.chartType, results: m.results || [], reverseResults: m.reverseResults || [], parsed: m.parsed || null,
  }))
  c.messages = cleanMsgs
  c.messageCount = cleanMsgs.length
  c.preview = cleanMsgs.find((m) => m.role === 'user')?.text || c.preview || ''
  c.updatedAt = Date.now()
  if (!c.title && c.preview) c.title = c.preview.slice(0, 20)
}

function openConv(id) {
  if (activeConvId.value) persistCurrentConv()
  clearDetail()
  const c = conversations.value.find((x) => x.id === id)
  if (!c) return
  activeConvId.value = id
  messages.value = (c.messages || []).map((m) => ({ ...m, loading: false }))
  msgSeq = messages.value.reduce((acc, m) => Math.max(acc, m.id || 0), 0)
  nextTick(() => {
    setTimeout(() => {
      messages.value.forEach((m) => {
        if (m.chartType && m.results && m.results.length) renderChart(m)
      })
    }, 100)
  })
}

async function deleteConv(id) {
  try {
    await ElMessageBox.confirm('确定删除这条对话吗？', '确认', { type: 'warning' })
  } catch { return }
  const idx = conversations.value.findIndex((c) => c.id === id)
  if (idx >= 0) {
    conversations.value.splice(idx, 1)
    saveConversations()
  }
  if (activeConvId.value === id) {
    activeConvId.value = null
    messages.value = []
    disposeCharts()
  }
  ElMessage.success('已删除')
}

function fillNlp(text) {
  nlpInput.value = text
  // 自动滚动到输入栏并聚焦（快问点完没反应是因为输入栏被滚动到页面下方，看不到）
  nextTick(() => {
    const inputCard = document.querySelector('.chat-input-card')
    if (inputCard) inputCard.scrollIntoView({ behavior: 'smooth', block: 'center' })
    const textarea = document.querySelector('.chat-input-card textarea')
    if (textarea) textarea.focus()
  })
}

// ===== 自然语言聊天 =====
async function handleChat() {
  const msg = nlpInput.value.trim()
  if (!msg) return ElMessage.warning('请输入指令')
  clearDetail()   // 发送新指令前收起旧的展开详情/弹窗

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
    persistCurrentConv()
    saveConversations()
  } finally {
    nlpLoading.value = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    const el = document.querySelector('.chat-list')
    if (el) el.scrollTop = el.scrollHeight
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
function barColor(s) {
  const n = Number(s)
  return n >= 80 ? '#3b6d11' : n >= 60 ? '#ba7517' : '#a32d2d'
}

// ===== 匹配依据详情（为什么 86 分：雷达图 + 四维得分条 + LLM 解释） =====
const activeDetailKey = ref('')       // `${msgId}:${talentId}` 当前展开的候选
const detailExplain = ref('')         // 当前展开候选的解释（独立于 r.explain 便于按需生成）
const detailLoading = ref(false)
let radarInstances = new Map()

function detailKey(m, r) { return `${m.id}:${r.talent_id}` }
function isActiveDetail(m, r) { return activeDetailKey.value === detailKey(m, r) }

async function toggleDetail(m, r) {
  const key = detailKey(m, r)
  if (activeDetailKey.value === key) {           // 再次点击收起
    activeDetailKey.value = ''
    disposeRadar(key)
    return
  }
  activeDetailKey.value = key
  detailExplain.value = r.explain || ''
  await nextTick()
  renderRadar(m, r)
  // 已有解释直接展示；没有则自动生成一次（match_id 存在时）
  if (!detailExplain.value && r.match_id && !detailLoading.value) {
    loadExplain(m, r)
  }
}

function renderRadar(m, r) {
  const key = detailKey(m, r)
  const el = document.querySelector(`[data-radar-key="${key}"]`)
  if (!el) return
  disposeRadar(key)
  const dims = parseDims(r.dimension_json) || {}
  const chart = echarts.init(el)
  radarInstances.set(key, chart)
  chart.setOption({
    tooltip: {},
    legend: { show: false },
    radar: {
      indicator: [
        { name: '技能', max: 100 }, { name: '学历', max: 100 },
        { name: '经验', max: 100 }, { name: '综合素质', max: 100 },
      ],
      radius: '70%',
      splitArea: { areaStyle: { color: ['rgba(64,158,255,0.03)', 'rgba(64,158,255,0.06)'] } },
    },
    series: [{
      type: 'radar',
      symbolSize: 5,
      data: [{
        value: [Number(dims.skill || 0), Number(dims.degree || 0), Number(dims.years || 0), Number(dims.quality || 0)],
        name: '匹配维度',
        areaStyle: { color: 'rgba(64,158,255,0.25)' },
        lineStyle: { color: '#409eff', width: 2 },
        itemStyle: { color: '#409eff' },
      }],
    }],
  }, true)
  chart.resize()
}

function disposeRadar(key) {
  const chart = radarInstances.get(key)
  if (chart) { try { chart.dispose() } catch { /* noop */ } radarInstances.delete(key) }
}

async function loadExplain(m, r, force) {
  if (!r.match_id) {
    ElMessage.warning('该候选暂无可生成的匹配记录')
    return
  }
  detailLoading.value = true
  try {
    const res = await getExplain(r.match_id, force)
    const explain = res.data?.explain || ''
    detailExplain.value = explain
    r.explain = explain          // 回写，避免重复请求
  } catch { /* 拦截器已提示 */ } finally {
    detailLoading.value = false
  }
}

// 切换消息/收起时清空详情面板
function clearDetail() {
  radarInstances.forEach((_, key) => disposeRadar(key))
  activeDetailKey.value = ''
  detailExplain.value = ''
  if (reverseReason.value?.visible) reverseReason.value.visible = false
  disposeReverseRadar()
}

// ===== 反向匹配（人才→岗位）：匹配依据弹窗 =====
const reverseReason = ref({ visible: false, row: null, explain: '', loading: false })
const reverseRadarEl = ref(null)
let reverseRadarChart = null

function openReverseReason(row) {
  reverseReason.value = { visible: true, row, explain: row.explain || '', loading: false }
}

async function renderReverseReason() {
  disposeReverseRadar()
  const row = reverseReason.value.row
  if (!row || !reverseRadarEl.value) return
  const dims = parseDims(row.dimension_json) || {}
  reverseRadarChart = echarts.init(reverseRadarEl.value)
  reverseRadarChart.setOption({
    tooltip: {},
    radar: {
      indicator: [
        { name: '技能', max: 100 }, { name: '学历', max: 100 },
        { name: '经验', max: 100 }, { name: '综合素质', max: 100 },
      ],
      radius: '70%',
      splitArea: { areaStyle: { color: ['rgba(64,158,255,0.03)', 'rgba(64,158,255,0.06)'] } },
    },
    series: [{
      type: 'radar',
      symbolSize: 5,
      data: [{
        value: [Number(dims.skill || 0), Number(dims.degree || 0), Number(dims.years || 0), Number(dims.quality || 0)],
        name: '匹配维度',
        areaStyle: { color: 'rgba(64,158,255,0.25)' },
        lineStyle: { color: '#409eff', width: 2 },
        itemStyle: { color: '#409eff' },
      }],
    }],
  }, true)
  reverseRadarChart.resize()
}

function disposeReverseRadar() {
  if (reverseRadarChart) { try { reverseRadarChart.dispose() } catch { /* noop */ } reverseRadarChart = null }
}

async function loadReverseReasonExplain(force) {
  const row = reverseReason.value.row
  if (!row?.match_id) {
    ElMessage.warning('该记录暂无可生成的匹配解释')
    return
  }
  reverseReason.value.loading = true
  try {
    const res = await getExplain(row.match_id, force)
    const explain = res.data?.explain || ''
    reverseReason.value.explain = explain
    row.explain = explain
  } catch { /* 拦截器已提示 */ } finally {
    reverseReason.value.loading = false
  }
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

function resizeAll() { chartInstances.forEach((c) => c.resize()); radarInstances.forEach((c) => c.resize()) }
function disposeCharts() { chartInstances.forEach((c) => { try { c.dispose() } catch { /* noop */ } }); chartInstances.clear(); clearDetail() }
onMounted(() => window.addEventListener('resize', resizeAll))
onBeforeUnmount(() => { window.removeEventListener('resize', resizeAll); disposeCharts() })
</script>

<style scoped>
/* ===== 单栏布局（填满 el-main 区域） ===== */
.agent-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  overflow: hidden;
}

/* ===== 主对话区 ===== */
.agent-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0; /* 关键：允许 flex 子项收缩 */
  overflow: hidden;
  background: #fff;
}
.chat-list {
  flex: 1;
  min-height: 0; /* 关键 */
  overflow-y: auto;
  padding: 24px 24px 16px;
  /* 关键：放弃 820px 定宽居中方案——column flex 下 stretch 会让
     max-width/margin:auto 失效导致居中失败、内容仍贴左。
     改为 chat-list 直接填满 agent-main 宽度（去掉 max-width 限制），
     内部 cap-row / hero 自身居中各自负责，彻底消除右侧空白。 */
  width: 100%;
}

/* ===== 空状态 ===== */
.chat-empty { text-align: center; padding: 56px 0 40px; }

/* ===== 顶部徽章：清爽蓝球（与 Element Plus 整体匹配） ===== */
.hero-badge {
  position: relative;
  width: 88px; height: 88px;
  margin: 0 auto 20px;
  display: flex; align-items: center; justify-content: center;
}
/* 柔和外晕（蓝色氛围光） */
.hero-badge::before {
  content: '';
  position: absolute;
  left: 50%; top: 50%;
  transform: translate(-50%, -50%);
  width: 140px; height: 140px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(64, 158, 255, 0.22) 0%, rgba(64, 158, 255, 0.07) 45%, transparent 70%);
  z-index: 0;
  pointer-events: none;
}
.hero-badge-inner {
  position: relative; z-index: 1;
  width: 72px; height: 72px;
  border-radius: 50%;
  background:
    radial-gradient(circle at 32% 26%, rgba(255,255,255,0.65) 0%, rgba(255,255,255,0) 45%),
    linear-gradient(150deg, #66b1ff 0%, #409eff 60%, #337ecc 100%);
  display: flex; align-items: center; justify-content: center;
  box-shadow:
    0 8px 20px rgba(64, 158, 255, 0.28),
    inset 0 1px 2px rgba(255, 255, 255, 0.5),
    inset 0 -5px 10px rgba(51, 126, 204, 0.3);
}

/* AI Agent 标签：浅蓝胶囊 */
.hero-tag {
  display: inline-block;
  padding: 5px 14px; border-radius: 999px;
  background: #ecf5ff;
  border: 1px solid #d9ecff;
  color: #409eff;
  font-size: 11px; font-weight: 600;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  margin-bottom: 16px;
}

/* 标题：深色正文 + 大留白 */
.hero-title {
  font-size: 27px; font-weight: 600;
  margin: 0 0 10px;
  color: #303133;
  letter-spacing: 1px;
}
.hero-subtitle { font-size: 13px; color: #909399; margin: 0 0 32px; line-height: 1.7; letter-spacing: 0.3px; }
.hint-block { margin-top: 28px; text-align: left; }
.hint-label { font-size: 12px; font-weight: 600; color: #6e7681; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; }
.cap-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.cap-chip {
  display: flex; align-items: flex-start; gap: 10px; padding: 12px;
  background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; transition: all 0.2s;
}
.cap-chip:hover { border-color: #409eff; box-shadow: 0 2px 8px rgba(64, 158, 255, 0.08); }
.cap-icon-wrap {
  flex-shrink: 0;
  width: 36px; height: 36px;
  display: inline-flex; align-items: center; justify-content: center;
  background: #f5f7fa; border-radius: 8px;
}
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
.cand-wrap { border-bottom: 1px solid #f0f2f5; }
.cand-wrap:last-child { border-bottom: none; }
.cand-row { display: flex; align-items: center; gap: 12px; padding: 10px 4px; }
.cand-row:hover { background: #fafbfc; border-radius: 8px; }
.cand-left { display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0; cursor: pointer; }
.cand-rank { flex-shrink: 0; }
.cand-avatar { background: #409eff; color: #fff; font-weight: 600; flex-shrink: 0; }
.cand-name { font-weight: 600; color: #1f2328; }
.cand-tag { color: #c0c4cc; font-size: 12px; margin-left: 4px; }
.cand-meta { font-size: 12px; color: #8b949e; margin-top: 2px; }
.cand-right { flex: 1.2; min-width: 0; }
.cand-score { display: flex; align-items: center; gap: 8px; }
.cand-bar { flex: 1; }
.cand-num { font-size: 15px; font-weight: 700; color: #409eff; }
.cand-opts { display: flex; align-items: center; justify-content: flex-end; gap: 2px; margin-top: 4px; }
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

/* ===== 匹配依据详情（为什么 86 分） ===== */
.cand-detail {
  margin: 2px 6px 12px;
  background: #fafbfc; border: 1px solid #eef1f5; border-radius: 10px;
  padding: 12px 14px;
}
.detail-grid { display: flex; gap: 18px; align-items: center; }
.radar-box { width: 220px; height: 200px; flex-shrink: 0; }
.detail-dims { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 10px; }
.detail-bar { display: flex; align-items: center; gap: 8px; }
.detail-dl { width: 70px; flex-shrink: 0; color: #606266; font-size: 12px; text-align: right; }
.detail-prog { flex: 1; }
.detail-dv { width: 34px; text-align: right; color: #1f2328; font-size: 13px; font-weight: 500; }
.detail-explain { margin-top: 12px; border-top: 1px dashed #e0e4ea; padding-top: 10px; }
.detail-ex-head { display: flex; align-items: center; justify-content: space-between; font-size: 12px; color: #303133; margin-bottom: 6px; }
.detail-ex-text {
  font-size: 13px; line-height: 1.7; color: #303133; background: #fff;
  border: 1px solid #eef1f5; border-radius: 8px; padding: 10px 12px;
  white-space: pre-wrap;
}
.detail-ex-loading { font-size: 13px; color: #8b949e; font-style: italic; padding: 8px 2px; }

/* ===== 图表 ===== */
.charts-card { background: #fafbfc; }
.single-chart-wrap { max-width: 640px; margin: 0 auto; }
.chart { width: 100%; }
.chart-single { height: 360px; }

/* ===== 输入栏（主区底部固定，高度自适应） ===== */
.chat-input-bar {
  flex-shrink: 0;
  padding: 12px 24px 16px;
  background: linear-gradient(to top, #ffffff 70%, rgba(255,255,255,0));
  border-top: 1px solid #f0f2f5;
}
.chat-input-inner { max-width: 820px; margin: 0 auto; }
.chat-input-card {
  background: #fff; border: 1px solid #e5e7eb; border-radius: 18px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  padding: 12px 16px 10px;
  transition: border-color 0.2s;
}
.chat-input-card:focus-within { border-color: #409eff; box-shadow: 0 4px 20px rgba(64, 158, 255, 0.12); }
.input-area { display: block; width: 100%; }
.chat-input-card :deep(.el-textarea) { display: block; width: 100%; }
.chat-input-card :deep(.el-textarea__inner) {
  font-size: 15px; padding: 6px 0; border: none; box-shadow: none;
  resize: none; line-height: 1.6; color: #1f2328; background: transparent;
  width: 100% !important; min-height: 40px !important;
}
.chat-input-card :deep(.el-textarea__inner::placeholder) { color: #a1a8b3; }
.input-footer {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 4px;
}
.input-tip { font-size: 12px; color: #a1a8b3; }
.send-btn { border-radius: 14px !important; padding: 0 18px !important; height: 40px !important; }
</style>