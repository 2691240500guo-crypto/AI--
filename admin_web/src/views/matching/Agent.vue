<template>
  <div class="agent-page">
    <!-- ===== 步骤条 ===== -->
    <el-card shadow="never" class="step-card">
      <el-steps :active="activeStep" align-center finish-status="success">
        <el-step title="选择岗位" description="选择待匹配岗位" />
        <el-step title="解析需求" description="AI 拆解岗位要求" />
        <el-step title="执行匹配" description="向量检索+双重打分" />
        <el-step title="查看结果" description="排序/解释/图表" />
      </el-steps>

      <div class="toolbar">
        <el-select v-model="positionId" placeholder="选择岗位" filterable style="width: 260px" @change="onPositionChange">
          <el-option v-for="p in positions" :key="p.id" :label="`${p.name} (${p.code})`" :value="p.id" />
        </el-select>
        <el-button type="primary" :loading="parsing" :disabled="!positionId" @click="parseAndMatch">🚀 一键解析并匹配</el-button>
        <el-divider direction="vertical" />
        <span class="tip">反向匹配：</span>
        <el-input v-model="reverseTalentId" placeholder="输入人才ID" style="width: 120px" clearable />
        <el-button :loading="reversing" :disabled="!reverseTalentId" @click="doReverse">人才→岗位</el-button>
      </div>

      <!-- 自然语言操作入口 -->
      <el-divider content-position="left"><span class="tip">💬 自然语言操作</span></el-divider>
      <el-input
        v-model="nlpInput"
        placeholder="直接用自然语言操作 Agent，例如：帮我找适合后端开发岗位的人才，要求硕士、3年以上经验、会Python"
        clearable
        @keyup.enter="handleChat"
      >
        <template #append>
          <el-button :loading="nlpLoading" @click="handleChat">发送</el-button>
        </template>
      </el-input>
      <div v-if="nlpReply" class="nlp-reply">🤖 {{ nlpReply }}</div>
      <div class="nlp-examples">
        示例：
        <el-tag size="small" effect="plain" class="tag" @click="fillNlp('分析后端开发工程师的岗位要求')">分析XX岗位的要求</el-tag>
        <el-tag size="small" effect="plain" class="tag" @click="fillNlp('帮我找适合后端开发岗位的人才，要求硕士、3年以上经验、会Python')">按条件找人才</el-tag>
        <el-tag size="small" effect="plain" class="tag" @click="fillNlp('人才5适合什么岗位')">人才反向匹配</el-tag>
        <el-tag size="small" effect="plain" class="tag" @click="fillNlp('为什么人才7排第一')">匹配依据解释</el-tag>
      </div>
    </el-card>

    <!-- ===== 岗位需求解析区 ===== -->
    <el-card v-if="parsed" shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span>📋 岗位智能解析：{{ parsed.title }}</span>
          <el-tag v-for="t in parsed.tags" :key="t" size="small" class="tag" type="info">{{ t }}</el-tag>
        </div>
      </template>
      <el-row :gutter="16">
        <el-col :span="8">
          <div class="dim-box">
            <div class="dim-title">🎯 核心要求</div>
            <ul class="dim-list">
              <li v-for="(c, i) in parsed.core_requirements" :key="i">{{ c }}</li>
              <li v-if="!parsed.core_requirements.length" class="empty">暂无</li>
            </ul>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="dim-box">
            <div class="dim-title">🛠 技能标准</div>
            <div class="skill-tags">
              <el-tag v-for="s in parsed.skill_standards" :key="s" class="tag" type="primary" effect="plain">{{ s }}</el-tag>
              <span v-if="!parsed.skill_standards.length" class="empty">暂无</span>
            </div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="dim-box">
            <div class="dim-title">📏 门槛条件</div>
            <div class="gate-line">学历要求：<el-tag size="small" type="warning">{{ parsed.degree_threshold || '不限' }}</el-tag></div>
            <div class="gate-line">经验要求：<el-tag size="small" type="warning">{{ parsed.experience_threshold?.text || '不限' }}</el-tag></div>
            <div class="gate-line">综合素质：{{ parsed.quality_dimensions.join('、') || '—' }}</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- ===== 筛选排序区 ===== -->
    <el-card v-if="parsed" shadow="never" class="section-card">
      <div class="toolbar">
        <span class="tip">筛选条件：</span>
        <el-select v-model="filterDegree" placeholder="学历门槛（覆盖）" clearable style="width: 140px">
          <el-option v-for="d in ['博士', '硕士', '本科', '大专']" :key="d" :label="d" :value="d" />
        </el-select>
        <el-input-number v-model="filterYears" :min="0" :max="20" placeholder="经验门槛（年）" style="width: 150px" />
        <el-input v-model="filterSkills" placeholder="必备技能（逗号分隔，如 Python,MySQL）" clearable style="width: 240px" />
        <el-button type="primary" plain :loading="matching" @click="doMatch">🔍 重新匹配</el-button>
        <span class="tip ml">共 {{ results.length }} 名候选</span>
      </div>
    </el-card>

    <!-- ===== 可视化区：柱状图/折线图/饼图 ===== -->
    <el-card v-if="results.length" shadow="never" class="section-card">
      <template #header><span>📊 匹配可视化</span></template>
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
    </el-card>

    <!-- ===== 匹配结果表 ===== -->
    <el-card v-if="results.length" shadow="never" class="section-card">
      <template #header><span>🏆 候选人才排序</span></template>
      <el-table :data="results" stripe border v-loading="matching">
        <el-table-column label="排名" width="64" align="center">
          <template #default="{ row }">
            <el-tag :type="row.rank <= 3 ? 'danger' : 'info'" effect="dark" round>{{ row.rank }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="人才ID" prop="talent_id" width="80" align="center" />
        <el-table-column label="学历" prop="degree" width="80" align="center">
          <template #default="{ row }">{{ row.degree || '未知' }}</template>
        </el-table-column>
        <el-table-column label="经验" width="80" align="center">
          <template #default="{ row }">{{ row.years }} 年</template>
        </el-table-column>
        <el-table-column label="技能" min-width="140">
          <template #default="{ row }">
            <el-tag v-for="s in (row.skills || []).slice(0, 5)" :key="s" size="small" effect="plain" class="tag">{{ s }}</el-tag>
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
              <span v-for="(v, k) in parseDims(row.dimension_json)" :key="k" class="dim-item" :title="DIM_LABEL[k]">
                {{ DIM_LABEL[k] }}<b>{{ v }}</b>
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="showExplain(row)">匹配依据</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- ===== 反向匹配结果 ===== -->
    <el-card v-if="reverseResults.length" shadow="never" class="section-card">
      <template #header><span>🔄 人才 {{ reverseTalentId }} 适配岗位（反向匹配）</span></template>
      <el-table :data="reverseResults" stripe border>
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
        <div class="explain-text">{{ explainDialog.data.explain || '暂无解释（可点击重新生成）' }}</div>
      </template>
      <template #footer>
        <el-button @click="explainDialog.visible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { agentChat, agentParse, agentReverse, agentRun, listPositions } from '@/api/matching'

const DIM_LABEL = { skill: '技能', degree: '学历', years: '经验', quality: '综合素质' }
const DEGREE_WEIGHTS = { skill: 0.4, degree: 0.2, years: 0.2, quality: 0.2 }

// ===== 岗位 =====
const positions = ref([])
const positionId = ref(null)
async function loadPositions() {
  const all = []
  let page = 1
  for (;;) {
    const res = await listPositions({ page, page_size: 200 })
    const items = res.data.items || []
    all.push(...items)
    const meta = res.data.meta
    if (!items.length || (meta && page >= meta.total_pages)) break
    page++
  }
  positions.value = all
}

// ===== 解析 & 匹配 =====
const activeStep = ref(0)
const parsed = ref(null)
const results = ref([])
const reverseResults = ref([])
const parsing = ref(false)
const matching = ref(false)
const reversing = ref(false)
const reverseTalentId = ref('')

// 筛选覆盖
const filterDegree = ref('')
const filterYears = ref(null)
const filterSkills = ref('')

function onPositionChange() {
  parsed.value = null
  results.value = []
  activeStep.value = 0
  disposeCharts()
}

async function parseAndMatch() {
  if (!positionId.value) return ElMessage.warning('请先选择岗位')
  parsing.value = true
  try {
    const res = await agentParse({ position_id: positionId.value })
    parsed.value = res.data
    activeStep.value = 1
    ElMessage.success('岗位需求解析完成')
    await doMatch()
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    parsing.value = false
  }
}

async function doMatch() {
  matching.value = true
  try {
    const payload = { position_id: positionId.value, top_k: 10, gen_explain: true, min_score: 0 }
    if (filterDegree.value) payload.degree_required = filterDegree.value
    if (filterYears.value !== null && filterYears.value !== undefined && filterYears.value !== '') {
      payload.years_required = Number(filterYears.value)
    }
    if (filterSkills.value.trim()) {
      payload.mandatory_skills = filterSkills.value.split(/[,，;；]/).map((s) => s.trim()).filter(Boolean)
    }
    const res = await agentRun(payload)
    results.value = res.data.results || []
    activeStep.value = 2
    if (results.value.length) {
      activeStep.value = 3
      renderCharts()
      ElMessage.success(`匹配完成，共 ${results.value.length} 名候选`)
    } else {
      ElMessage.warning('无符合条件的候选，可放宽筛选条件')
    }
  } finally {
    matching.value = false
  }
}

async function doReverse() {
  const tid = Number(reverseTalentId.value)
  if (!tid) return ElMessage.warning('请输入人才ID')
  reversing.value = true
  try {
    const res = await agentReverse({ talent_id: tid, top_k: 10, min_score: 0 })
    reverseResults.value = res.data.results || []
    if (!reverseResults.value.length) ElMessage.warning('未找到适配岗位（请确认人才ID存在且已向量化）')
  } finally {
    reversing.value = false
  }
}

// ===== 自然语言操作 =====
const nlpInput = ref('')
const nlpReply = ref('')
const nlpLoading = ref(false)

function fillNlp(text) {
  nlpInput.value = text
}

async function handleChat() {
  const msg = nlpInput.value.trim()
  if (!msg) return ElMessage.warning('请输入指令')
  nlpLoading.value = true
  nlpReply.value = ''
  try {
    const res = await agentChat({ message: msg })
    const data = res.data
    nlpReply.value = data.reply || ''
    const { intent, result } = data
    if (intent === 'parse' && result) {
      parsed.value = result
      activeStep.value = Math.max(activeStep.value, 1)
    } else if (intent === 'match' && result) {
      results.value = result.results || []
      if (results.value.length) {
        activeStep.value = 3
        renderCharts()
      }
    } else if (intent === 'reverse' && result) {
      reverseResults.value = result.results || []
    } else if (intent === 'explain' && result) {
      explainDialog.data = {
        talent_id: result.talent_id, score: result.score,
        dimension_json: result.dimension_json, explain: result.explain,
      }
      explainDialog.visible = true
    }
  } finally {
    nlpLoading.value = false
  }
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

// ===== 解释弹窗 =====
const explainDialog = reactive({ visible: false, data: null })
function showExplain(row) {
  explainDialog.data = row
  explainDialog.visible = true
}

// ===== ECharts 可视化 =====
const barChart = ref(null)
const lineChart = ref(null)
const pieChart = ref(null)
const pieWeightChart = ref(null)
let chartInstances = []

function renderCharts() {
  const list = results.value
  if (!list.length) return
  disposeCharts()

  // 柱状图：Top10 人才总分
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

  // 折线图：Top5 各维度得分走势
  const top5 = list.slice(0, 5)
  const line = echarts.init(lineChart.value)
  line.setOption({
    tooltip: { trigger: 'axis' },
    legend: { top: 0, data: ['技能', '学历', '经验', '综合素质'] },
    grid: { left: 40, right: 20, top: 34, bottom: 30 },
    xAxis: { type: 'category', data: top5.map((r) => `人才${r.talent_id}`) },
    yAxis: { type: 'value', max: 100 },
    series: ['skill', 'degree', 'years', 'quality'].map((k, i) => ({
      name: DIM_LABEL[k], type: 'line', smooth: true,
      data: top5.map((r) => Number(parseDims(r.dimension_json)[k] ?? 0)),
    })),
  })
  chartInstances.push(line)

  // 饼图：匹配结果分布
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

  // 饼图：维度权重占比
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

onBeforeUnmount(disposeCharts)

// 初始化
loadPositions()
window.addEventListener('resize', resizeCharts)
onBeforeUnmount(() => window.removeEventListener('resize', resizeCharts))
</script>

<style scoped>
.agent-page { padding: 4px; }
.step-card { margin-bottom: 16px; }
.section-card { margin-bottom: 16px; }
.toolbar { display: flex; align-items: center; gap: 8px; margin-top: 16px; flex-wrap: wrap; }
.tip { color: #909399; font-size: 13px; }
.ml { margin-left: 8px; }
.tag { margin: 0 4px 4px 0; }
.card-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dim-box { border: 1px solid #ebeef5; border-radius: 6px; padding: 12px; height: 100%; }
.dim-title { font-weight: 600; margin-bottom: 8px; color: #303133; }
.dim-list { margin: 0; padding-left: 18px; color: #606266; font-size: 13px; }
.dim-list li { margin-bottom: 4px; }
.gate-line { font-size: 13px; color: #606266; margin-bottom: 6px; }
.skill-tags { display: flex; flex-wrap: wrap; }
.empty { color: #c0c4cc; font-size: 13px; }
.chart { height: 280px; }
.chart-title { font-size: 13px; color: #909399; margin-bottom: 8px; }
.mt { margin-top: 16px; }
.dims { display: flex; gap: 10px; flex-wrap: wrap; font-size: 12px; color: #909399; }
.dim-item b { color: #409eff; margin-left: 2px; }
.score-num { font-weight: 700; color: #409eff; margin-left: 6px; }
.explain-score { display: flex; align-items: baseline; gap: 8px; margin-bottom: 14px; }
.big { font-size: 36px; font-weight: 700; color: #409eff; }
.unit { color: #909399; }
.explain-text { margin-top: 14px; padding: 12px; background: #f5f7fa; border-radius: 6px; color: #303133; line-height: 1.7; font-size: 14px; }
.nlp-reply { margin-top: 10px; padding: 10px 14px; background: #f0f9eb; border: 1px solid #e1f3d8; border-radius: 6px; color: #303133; line-height: 1.6; font-size: 14px; }
.nlp-examples { margin-top: 8px; font-size: 12px; color: #909399; display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.nlp-examples .tag { cursor: pointer; }
</style>
