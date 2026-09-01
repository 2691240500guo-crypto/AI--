<template>
  <div class="agent-page">
    <!-- ===== 对话流（可滚动） ===== -->
    <div class="chat-list" ref="chatListRef">
      <!-- 空状态：欢迎语 + 能力 + 快问 -->
      <div v-if="!messages.length" class="chat-empty">
        <div class="hero-icon">🤖</div>
        <h1 class="hero-title">岗位人才匹配Agent</h1>
        <p class="hero-subtitle">用一句话描述需求，AI 自动完成岗位解析 / 智能匹配 / 反向匹配 / 依据解释</p>

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

            <!-- 解析结果 -->
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

            <!-- 匹配结果：Top3 + 表格 -->
            <el-card v-if="m.results && m.results.length" shadow="never" class="section-card">
              <template #header><span>🏆 候选人才排序（Top3 卡片化）</span></template>
              <el-row :gutter="16" class="top3-row">
                <el-col v-for="r in m.results.slice(0, 3)" :key="r.talent_id" :xs="24" :sm="8">
                  <el-card class="talent-card" :class="{ 'is-top1': r.rank === 1 }" shadow="hover">
                    <div class="tc-head">
                      <el-avatar :size="54" :src="r.avatar || ''" class="tc-avatar">{{ (r.talent_name || '人').slice(0, 1) }}</el-avatar>
                      <div class="tc-info">
                        <div class="tc-name">
                          {{ r.talent_name || `人才${r.talent_id}` }}
                          <el-tag v-if="r.rank === 1" type="danger" size="small" effect="dark">最适配</el-tag>
                          <el-tag v-else-if="r.rank === 2" type="warning" size="small" effect="dark">次选</el-tag>
                        </div>
                        <div class="tc-meta">{{ r.current_title || '暂无职位' }}{{ r.current_company ? ' · ' + r.current_company : '' }}</div>
                        <div class="tc-meta">人才#{{ r.talent_id }} · {{ r.degree || '学历未知' }} · {{ r.years || 0 }}年经验</div>
                      </div>
                    </div>
                    <div class="tc-body">
                      <el-progress type="dashboard" :percentage="Number(r.score)" :color="scoreColor(r.score)" :width="104" class="tc-ring">
                        <template #default="{ percentage }">
                          <div class="tc-ring-inner"><b>{{ percentage }}</b><span>匹配度</span></div>
                        </template>
                      </el-progress>
                      <div class="tc-dims">
                        <div v-for="(v, k) in parseDims(r.dimension_json)" :key="k" class="tc-dim">
                          <span class="tc-dim-label">{{ DIM_LABEL[k] }}</span>
                          <el-progress :percentage="Number(v)" :stroke-width="7" :show-text="false" :color="scoreColor(v)" class="tc-dim-bar" />
                          <span class="tc-dim-val">{{ v }}</span>
                        </div>
                      </div>
                    </div>
                    <div class="tc-foot">
                      <el-button size="small" type="primary" plain @click="goProfile(r)">👤 档案</el-button>
                      <el-button size="small" :type="r.status === 1 ? 'primary' : 'default'" plain :disabled="r.status === 1 || r.status === 2" @click="setStatus(r, 1)">推荐</el-button>
                      <el-button size="small" :type="r.status === 2 ? 'success' : 'default'" plain :disabled="r.status === 2" @click="setStatus(r, 2)">录用</el-button>
                    </div>
                  </el-card>
                </el-col>
              </el-row>

              <el-table :data="m.results" stripe border class="mt">
                <el-table-column label="排名" width="64" align="center">
                  <template #default="{ row }">
                    <el-tag :type="row.rank <= 3 ? 'danger' : 'info'" effect="dark" round>{{ row.rank }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="人才" min-width="140">
                  <template #default="{ row }">
                    <div class="tal-cell">
                      <el-avatar :size="28" :src="row.avatar || ''" class="tal-avatar">{{ (row.talent_name || '人').slice(0, 1) }}</el-avatar>
                      <div>
                        <div class="tal-name">{{ row.talent_name || `人才${row.talent_id}` }}<span class="tal-id">#{{ row.talent_id }}</span></div>
                        <div class="tal-pos">{{ row.current_title || '—' }}</div>
                      </div>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="匹配度" width="170">
                  <template #default="{ row }">
                    <el-progress :percentage="Number(row.score)" :color="scoreColor(row.score)" :stroke-width="10" />
                    <span class="score-num">{{ row.score }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="四维得分" min-width="210">
                  <template #default="{ row }">
                    <div class="dims">
                      <span v-for="(v, k) in parseDims(row.dimension_json)" :key="k" class="dim-item">
                        {{ DIM_LABEL[k] }}<b>{{ v }}</b>
                      </span>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="72" align="center">
                  <template #default="{ row }">
                    <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="180" align="center" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small" type="primary" link @click="showExplain(row)">依据</el-button>
                    <el-button size="small" type="info" link @click="goProfile(row)">档案</el-button>
                    <el-button size="small" type="success" link :disabled="row.status === 2" @click="setStatus(row, 2)">录用</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>

            <!-- 反向匹配结果 -->
            <el-card v-if="m.reverseResults && m.reverseResults.length" shadow="never" class="section-card">
              <template #header><span>🔄 人才适配岗位（反向匹配）</span></template>
              <el-table :data="m.reverseResults" stripe border>
                <el-table-column label="岗位ID" prop="position_id" width="80" align="center" />
                <el-table-column label="岗位名称" prop="position_name" min-width="160" />
                <el-table-column label="匹配度" width="180">
                  <template #default="{ row }">
                    <el-progress :percentage="Number(row.score)" :color="scoreColor(row.score)" :stroke-width="10" />
                  </template>
                </el-table-column>
                <el-table-column label="四维得分" min-width="210">
                  <template #default="{ row }">
                    <div class="dims">
                      <span v-for="(v, k) in parseDims(row.dimension_json)" :key="k" class="dim-item">
                        {{ DIM_LABEL[k] }}<b>{{ v }}</b>
                      </span>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </div>
        </div>
      </template>

      <!-- 最新匹配的可视化图表（chart 意图→单图，默认→四图） -->
      <el-card v-if="latestMatchResults.length" shadow="never" class="section-card charts-card">
        <template #header>
          <span>📊 匹配可视化{{ latestChartType ? ` · ${CHART_LABEL[latestChartType] || ''}` : '' }}</span>
        </template>

        <!-- chart 意图：只渲染指定单图（全宽大图） -->
        <div v-if="latestChartType" class="single-chart-wrap">
          <div ref="barChart" v-if="latestChartType === 'bar'" class="chart chart-single" />
          <div ref="lineChart" v-if="latestChartType === 'line'" class="chart chart-single" />
          <div ref="pieChart" v-if="latestChartType === 'pie'" class="chart chart-single" />
        </div>

        <!-- 默认：四图 2x2 -->
        <template v-else>
          <el-row :gutter="16">
            <el-col :span="12">
              <div class="chart-title">柱状图 · 候选人才匹配度总分</div>
              <div ref="barChart" class="chart" />
            </el-col>
            <el-col :span="12">
              <div class="chart-title">折线图 · Top5 各维度得分走势</div>
              <div ref="lineChart" class="chart" />
            </el-col>
          </el-row>
          <el-row :gutter="16" class="mt">
            <el-col :span="12">
              <div class="chart-title">饼图 · 匹配结果分布（推荐/候选/储备）</div>
              <div ref="pieChart" class="chart" />
            </el-col>
            <el-col :span="12">
              <div class="chart-title">维度权重占比（默认规则）</div>
              <div ref="pieWeightChart" class="chart" />
            </el-col>
          </el-row>
        </template>
      </el-card>
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
            placeholder="试试这样说：帮我找适合后端开发岗位的人才，要求硕士、3年以上经验、会Python（Ctrl+Enter 发送）"
            :disabled="nlpLoading"
            @keydown.enter.prevent.ctrl="handleChat"
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

    <!-- ===== 匹配依据解释弹窗 ===== -->
    <el-dialog v-model="explainDialog.visible" title="匹配依据 · 得分解释" width="560px">
      <template v-if="explainDialog.data">
        <div class="explain-score">
          <span class="big">{{ explainDialog.data.score }}</span>
          <span class="unit">分</span>
          <el-tag :type="scoreColor(explainDialog.data.score)" effect="dark" class="ml">{{ explainDialog.data.score >= 80 ? '推荐录用' : explainDialog.data.score >= 60 ? '储备候选' : '暂不推荐' }}</el-tag>
        </div>
        <el-descriptions :column="2" border class="mt">
          <el-descriptions-item v-for="(v, k) in parseDims(explainDialog.data.dimension_json)" :key="k" :label="DIM_LABEL[k]">
            <b>{{ v }}</b>
          </el-descriptions-item>
        </el-descriptions>
        <div class="explain-text">{{ explainDialog.data.explain || '暂无解释' }}</div>
      </template>
      <template #footer>
        <el-button @click="explainDialog.visible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import { agentChat, updateResultStatus } from '@/api/matching'

const router = useRouter()

const DIM_LABEL = { skill: '技能', degree: '学历', years: '经验', quality: '综合素质' }
const DEGREE_WEIGHTS = { skill: 0.4, degree: 0.2, years: 0.2, quality: 0.2 }

const QUICK_QUERIES = [
  '分析后端开发工程师的岗位要求',
  '帮我找适合后端开发岗位的人才，要求硕士、3年以上经验、会Python',
  '人才5适合什么岗位',
  '为什么人才7排第一',
]

const CAPABILITIES = [
  { icon: '📋', text: '岗位解析', desc: 'AI 拆解任职要求/技能/经验门槛' },
  { icon: '🎯', text: '智能匹配', desc: '按条件筛选并排序候选人' },
  { icon: '🔄', text: '反向匹配', desc: '按人才找适配岗位' },
  { icon: '💬', text: '匹配解释', desc: '解释推荐依据与维度得分' },
]

// ===== 消息流 =====
const messages = ref([])  // [{id, role:'user'|'agent', text, reply, loading, parsed, results, reverseResults}]
const nlpInput = ref('')
const nlpLoading = ref(false)
const chatListRef = ref(null)
let msgSeq = 0

// 最新一次有结果的匹配数据（用于图表）
const latestMatchResults = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    if (m.role === 'agent' && m.results && m.results.length) return m.results
  }
  return []
})

// 最新图表类型（chart 意图指定 bar/line/pie，否则 null 显示默认 4 图）
const latestChartType = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    if (m.role === 'agent' && m.chartType) return m.chartType
  }
  return null
})
const CHART_LABEL = { bar: '柱状图', line: '折线图', pie: '饼图' }

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
function statusLabel(s) { return { 0: '候选', 1: '推荐', 2: '录用' }[s] ?? '候选' }
function statusType(s) { return { 0: 'info', 1: 'warning', 2: 'success' }[s] ?? 'info' }

function fillNlp(text) { nlpInput.value = text }

// ===== 解释弹窗 =====
const explainDialog = reactive({ visible: false, data: null })
function showExplain(row) {
  explainDialog.data = row
  explainDialog.visible = true
}

// ===== 操作闭环 =====
function goProfile(row) { router.push(`/talent/detail/${row.talent_id}`) }
async function setStatus(row, status) {
  const label = { 1: '推荐', 2: '录用' }[status]
  try {
    await ElMessageBox.confirm(`确认将 人才${row.talent_id}（${row.talent_name || ''}）标记为「${label}」？`, '操作确认', { type: 'warning' })
  } catch { return }
  try {
    const res = await updateResultStatus(row.match_id, status)
    row.status = res.data.status
    ElMessage.success(`已标记为「${label}」`)
  } catch { /* 拦截器已提示 */ }
}

// ===== 自然语言聊天（对话流） =====
async function handleChat() {
  const msg = nlpInput.value.trim()
  if (!msg) return ElMessage.warning('请输入指令')
  nlpLoading.value = true

  // 1. 推入用户消息
  const userMsg = { id: ++msgSeq, role: 'user', text: msg }
  messages.value.push(userMsg)
  // 2. 推入 agent loading 消息（reply 暂空）
  const agentMsg = { id: ++msgSeq, role: 'agent', loading: true, reply: '' }
  messages.value.push(agentMsg)
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
    } else if (intent === 'reverse' && result) {
      agentMsg.reverseResults = result.results || []
    } else if (intent === 'explain' && result) {
      explainDialog.data = {
        talent_id: result.talent_id, score: result.score,
        dimension_json: result.dimension_json, explain: result.explain,
      }
      explainDialog.visible = true
    }
  } finally {
    nlpLoading.value = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatListRef.value) chatListRef.value.scrollTop = chatListRef.value.scrollHeight
  })
}

// ===== ECharts 可视化（fix: nextTick 等待 DOM） =====
const barChart = ref(null)
const lineChart = ref(null)
const pieChart = ref(null)
const pieWeightChart = ref(null)
let chartInstances = []

function renderCharts(list, type) {
  if (!list.length) return
  disposeCharts()
  if (type) {
    // chart 意图：只渲染指定类型单图
    if (type === 'bar' && barChart.value) initBar(list)
    else if (type === 'line' && lineChart.value) initLine(list)
    else if (type === 'pie' && pieChart.value) initPie(list)
    return
  }
  // 默认四图
  if (barChart.value) initBar(list)
  if (lineChart.value) initLine(list)
  if (pieChart.value) initPie(list)
  if (pieWeightChart.value) initPieWeight()
}

function initBar(list) {
  const bar = echarts.init(barChart.value)
  bar.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: list.map((r) => `人才${r.talent_id}`) },
    yAxis: { type: 'value', max: 100 },
    series: [{
      type: 'bar', data: list.map((r) => Number(r.score)), barWidth: 26,
      itemStyle: { color: (p) => (p.value >= 80 ? '#67c23a' : p.value >= 60 ? '#e6a23c' : '#f56c6c') },
      label: { show: true, position: 'top' },
    }],
  })
  chartInstances.push(bar)
}

function initLine(list) {
  const top5 = list.slice(0, 5)
  const line = echarts.init(lineChart.value)
  line.setOption({
    tooltip: { trigger: 'axis' },
    legend: { top: 0, data: ['技能', '学历', '经验', '综合素质'] },
    grid: { left: 40, right: 20, top: 34, bottom: 30 },
    xAxis: { type: 'category', data: top5.map((r) => `人才${r.talent_id}`) },
    yAxis: { type: 'value', max: 100 },
    series: ['skill', 'degree', 'years', 'quality'].map((k) => ({
      name: DIM_LABEL[k], type: 'line', smooth: true,
      data: top5.map((r) => Number(parseDims(r.dimension_json)[k] ?? 0)),
    })),
  })
  chartInstances.push(line)
}

function initPie(list) {
  const dist = { 推荐: 0, 候选: 0, 储备: 0 }
  list.forEach((r) => {
    const s = Number(r.score)
    if (s >= 80) dist.推荐++
    else if (s >= 60) dist.候选++
    else dist.储备++
  })
  const pie = echarts.init(pieChart.value)
  pie.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie', radius: ['40%', '65%'],
      data: Object.entries(dist).map(([name, value]) => ({ name, value })),
      label: { formatter: '{b}: {c} 人 ({d}%)' },
    }],
  })
  chartInstances.push(pie)
}

function initPieWeight() {
  const pieW = echarts.init(pieWeightChart.value)
  pieW.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie', radius: ['40%', '65%'],
      data: Object.entries(DEGREE_WEIGHTS).map(([k, v]) => ({ name: DIM_LABEL[k], value: v })),
      label: { formatter: '{b}: {d}%' },
    }],
  })
  chartInstances.push(pieW)
}

function disposeCharts() {
  chartInstances.forEach((c) => { try { c.dispose() } catch { /* noop */ } })
  chartInstances = []
}
function resizeCharts() {
  chartInstances.forEach((c) => c.resize())
}

// 监听最新匹配结果与图表类型：等 DOM 更新完成后再渲染图表（修复 charts 不显示的 bug）
watch([latestMatchResults, latestChartType], async ([val, ctype]) => {
  if (val.length) {
    await nextTick()
    renderCharts(val, ctype)
  } else {
    disposeCharts()
  }
})

onMounted(() => window.addEventListener('resize', resizeCharts))
onBeforeUnmount(() => {
  disposeCharts()
  window.removeEventListener('resize', resizeCharts)
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
.chat-empty {
  text-align: center;
  padding: 60px 0 40px;
}
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

/* ===== 结果区 ===== */
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

/* ===== Top3 卡片 ===== */
.top3-row { margin-bottom: 16px; }
.talent-card { border-radius: 10px; transition: all 0.25s; }
.talent-card.is-top1 { border: 1px solid #f56c6c; box-shadow: 0 2px 12px rgba(245, 108, 108, 0.15); }
.talent-card.is-top1 .tc-name { color: #f56c6c; }
.tc-head { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.tc-avatar { background: #409eff; color: #fff; font-weight: 600; flex-shrink: 0; }
.tc-name { font-size: 16px; font-weight: 700; color: #303133; display: flex; align-items: center; gap: 6px; }
.tc-meta { font-size: 12px; color: #909399; margin-top: 2px; }
.tc-body { display: flex; align-items: center; gap: 14px; }
.tc-ring { flex-shrink: 0; }
.tc-ring-inner { text-align: center; }
.tc-ring-inner b { display: block; font-size: 22px; color: #303133; line-height: 1.1; }
.tc-ring-inner span { font-size: 11px; color: #909399; }
.tc-dims { flex: 1; display: flex; flex-direction: column; gap: 7px; }
.tc-dim { display: flex; align-items: center; gap: 6px; }
.tc-dim-label { font-size: 12px; color: #606266; width: 52px; flex-shrink: 0; }
.tc-dim-bar { flex: 1; }
.tc-dim-val { font-size: 12px; font-weight: 600; color: #409eff; width: 30px; text-align: right; }
.tc-foot { display: flex; justify-content: center; gap: 8px; margin-top: 14px; }

/* ===== 表格人才列 ===== */
.tal-cell { display: flex; align-items: center; gap: 8px; }
.tal-avatar { background: #409eff; color: #fff; font-weight: 600; flex-shrink: 0; }
.tal-name { font-weight: 600; color: #303133; }
.tal-id { color: #c0c4cc; font-size: 12px; margin-left: 4px; }
.tal-pos { font-size: 12px; color: #909399; }
.dims { display: flex; gap: 10px; flex-wrap: wrap; font-size: 12px; color: #909399; }
.dim-item b { color: #409eff; margin-left: 2px; }
.score-num { font-weight: 700; color: #409eff; margin-left: 6px; }
.mt { margin-top: 12px; }

/* ===== 图表 ===== */
.charts-card { background: #fafbfc; }
.chart { height: 260px; width: 100%; }
.chart-title { font-size: 13px; color: #6e7681; margin-bottom: 8px; font-weight: 500; }
.single-chart-wrap { max-width: 640px; margin: 0 auto; }
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

/* ===== 弹窗 ===== */
.explain-score { display: flex; align-items: baseline; gap: 8px; margin-bottom: 14px; }
.big { font-size: 36px; font-weight: 700; color: #409eff; }
.unit { color: #909399; }
.ml { margin-left: 8px; }
.explain-text { margin-top: 14px; padding: 12px; background: #f5f7fa; border-radius: 6px; color: #303133; line-height: 1.7; font-size: 14px; }
</style>