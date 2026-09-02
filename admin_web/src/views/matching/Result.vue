<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, View, Sunny, Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
  listResults, getExplain, runMatch, listPositions, updateWarm,
  updateResultStatus, evaluateMatch,
} from '@/api/matching'

const router = useRouter()

// 维度中文映射
const DIM_LABEL = { skill: '技能', degree: '学历', years: '经验', quality: '综合素质' }
const SORT_OPTIONS = [
  { value: 'score', label: '匹配度' },
  { value: 'level', label: '能力等级' },
  { value: 'years', label: '从业经验' },
  { value: 'quality', label: '综合评分' },
]
const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 0, label: '候选' },
  { value: 1, label: '推荐' },
  { value: 2, label: '录用' },
]
const WARM_OPTIONS = [
  { value: 0, label: '无保温' },
  { value: 1, label: '低' },
  { value: 2, label: '中' },
  { value: 3, label: '高' },
]

// ===== 列表与查询 =====
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const query = reactive({
  page: 1, page_size: 10, talent_id: '', position_id: '', min_score: '',
  sort_by: 'score', status: '',
})

// 岗位 id->名称 映射（用于列表展示岗位名，前端只读复用岗位数据）
const positions = ref([])
const posMap = computed(() => {
  const m = {}
  positions.value.forEach((p) => (m[p.id] = p.name))
  return m
})

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
    if (query.talent_id) params.talent_id = query.talent_id
    if (query.position_id) params.position_id = query.position_id
    if (query.min_score) params.min_score = query.min_score
    if (query.sort_by) params.sort_by = query.sort_by
    if (query.status !== '') params.status = Number(query.status)
    const res = await listResults(params)
    rows.value = res.data.items
    total.value = res.data.meta.total
  } finally {
    loading.value = false
  }
}

// 重置过滤条件（保留当前分页与排序默认值）
function resetQuery() {
  query.talent_id = ''
  query.position_id = ''
  query.min_score = ''
  query.status = ''
  query.page = 1
  load()
}

async function loadPositions() {
  // PageParams.page_size 上限 200（后端 le=200），须循环分页拉全量岗位，避免 422 Validation error
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

function scoreType(s) {
  const n = Number(s)
  if (n >= 80) return 'success'
  if (n >= 60) return 'warning'
  return 'danger'
}
function statusLabel(s) {
  return { 0: '候选', 1: '推荐', 2: '录用' }[s] ?? '候选'
}
function statusType(s) {
  return { 0: 'info', 1: 'warning', 2: 'success' }[s] ?? 'info'
}
function parseDims(json) {
  if (!json) return {}
  try {
    return JSON.parse(json)
  } catch {
    return {}
  }
}
function fmtDim(json, key) {
  const d = parseDims(json)
  const v = Number(d[key])
  if (!Number.isFinite(v)) return '-'
  return v.toFixed(0)
}

// ===== 解释详情抽屉 =====
const drawer = reactive({ visible: false, loading: false, id: null, explain: '', dims: {} })
let radarChart = null
const radarEl = ref(null)

function renderRadar() {
  if (!radarEl.value) return
  disposeRadar()
  const dims = drawer.dims || {}
  const hasDim = Object.keys(dims).length
  if (!hasDim) return
  radarChart = echarts.init(radarEl.value)
  radarChart.setOption({
    tooltip: {},
    radar: {
      indicator: [
        { name: '技能', max: 100 }, { name: '学历', max: 100 },
        { name: '经验', max: 100 }, { name: '综合素质', max: 100 },
      ],
      radius: '68%',
      splitArea: { areaStyle: { color: ['rgba(64,158,255,0.03)', 'rgba(64,158,255,0.06)'] } },
    },
    series: [{
      type: 'radar',
      symbolSize: 5,
      data: [{
        value: [Number(dims.skill || 0), Number(dims.degree || 0), Number(dims.years || 0), Number(dims.quality || 0)],
        name: '匹配维度',
        areaStyle: { color: 'rgba(37,99,235,0.22)' },
        lineStyle: { color: '#2563eb', width: 2 },
        itemStyle: { color: '#2563eb' },
      }],
    }],
  }, true)
  radarChart.resize()
}
function disposeRadar() {
  if (radarChart) { try { radarChart.dispose() } catch { /* noop */ } radarChart = null }
}

async function openExplain(row) {
  drawer.id = row.id
  drawer.explain = row.explain || ''
  drawer.dims = parseDims(row.dimension_json)
  drawer.visible = true
  // 抽屉渲染完成后画雷达
  await nextTick()
  setTimeout(() => renderRadar(), 80)
  // 已有解释直接展示，否则调用 /explain 生成（依赖 LLM，不可用时后端降级为规则解释）
  if (!drawer.explain) {
    drawer.loading = true
    try {
      const res = await getExplain(row.id)
      drawer.explain = res.data.explain || ''
    } finally {
      drawer.loading = false
    }
  }
}

async function regenerate() {
  drawer.loading = true
  try {
    // 传 force=1 触发后端重新生成（LLM 重新解释；LLM 不可用时后端自动降级为规则解释）
    const res = await getExplain(drawer.id, true)
    drawer.explain = res.data.explain || ''
    ElMessage.success('解释已刷新')
  } finally {
    drawer.loading = false
  }
}

// ===== 一键查看人才档案（需求3，跳转 T 域人才详情页，前端复用只读路由） =====
import { getTalent } from '@/api/talent'
async function viewTalent(row) {
  // T 域档案可能因数据未同步而不存在（旧匹配人才id），先校验避免跳到 404 空白页
  try {
    await getTalent(row.talent_id)
  } catch {
    return // 404 等错误已由拦截器提示，阻止无谓跳转
  }
  router.push({ name: 'talent-detail', params: { id: row.talent_id } })
}

// ===== 储备保温管理（需求4）：展示态/跟进弹窗复用共享工具与组件（与 Alert 页一致） =====
import { warmLabel, fmtTime, warmState, warmMeta } from '@/utils/matchingWarm'
import FollowDialog from './FollowDialog.vue'

// 表格紧凑用：MM-DD HH:mm（省略年份与秒，让"生成时间"列不再被截）
function fmtShort(t) {
  if (!t) return '—'
  const s = String(t).replace('T', ' ')
  // 取 "MM-DD HH:mm" 段
  const m = s.match(/(\d{2})-(\d{2})\s+(\d{2}):(\d{2})/)
  return m ? `${m[1]}-${m[2]} ${m[3]}:${m[4]}` : s.slice(5, 16)
}

const followTarget = ref(null)
const showFollow = ref(false)
function openFollow(row) {
  followTarget.value = row
  showFollow.value = true
}
function onFollowSuccess(u) {
  // 本地立即生效：该行保温状态/跟进时间实时回到"火热"，无需整页刷新
  const r = rows.value.find((x) => x.id === u.id)
  if (r) {
    r.warm_level = u.warm_level
    r.last_follow_up = u.last_follow_up
  }
}
// ===== 状态流转（0候选 1推荐 2录用） =====
async function changeStatus(row) {
  const next = row.status >= 2 ? 0 : row.status + 1
  const label = { 0: '候选', 1: '推荐', 2: '录用' }
  try {
    await ElMessageBox.confirm(`将记录「${label[row.status]}」→「${label[next]}」？`, '状态流转', { type: 'warning' })
  } catch {
    return
  }
  try {
    await updateResultStatus(row.id, next)
    ElMessage.success(`已更新为「${label[next]}」`)
    load()
  } catch { /* error shown by interceptor */ }
}

// ===== 匹配精度评估（需求2） =====
const evalLoading = ref(false)
const evalResult = ref(null)
const evalCollapsed = ref(false)
const evalTopK = ref(3)  // 每岗作为「推」的 TopK 候选，与 HR 实际选人范围一致
// 真正可用：自动从当前结果构建小规模真值参考集（每岗 top1 = 正例，top2-3 = 反例）→ 跑 reference 模式
// → 拿到的是真正的 precision/recall/F1，可直接对照"≥85%"验收口径
async function runEvaluate() {
  evalLoading.value = true
  evalCollapsed.value = false
  try {
    const topK = Number(evalTopK.value) || 3
    const reference = []
    const byPos = {}
    for (const r of rows.value) {
      if (!byPos[r.position_id]) byPos[r.position_id] = []
      byPos[r.position_id].push(r)
    }
    let posCount = 0
    for (const pid of Object.keys(byPos)) {
      const cands = byPos[pid].slice().sort((a, b) => Number(b.score) - Number(a.score))
      if (cands.length >= 1) {
        posCount++
        // top1 = 应该推（正例）
        reference.push({ position_id: Number(pid), talent_id: cands[0].talent_id, is_match: true })
        // top2..topK = 不应该推（反例）
        for (let i = 1; i < Math.min(topK, cands.length); i++) {
          reference.push({ position_id: Number(pid), talent_id: cands[i].talent_id, is_match: false })
        }
      }
    }
    if (!reference.length) {
      ElMessage.warning('当前列表为空，无法构建评估参考集；请先发起匹配或加载结果')
      return
    }
    const res = await evaluateMatch({ top_k: topK, reference })
    evalResult.value = { ...res.data, _autoPos: posCount }
    ElMessage.success(`已用 ${posCount} 个岗位的 Top${topK} 真值参考集评估完成`)
  } finally {
    evalLoading.value = false
  }
}

// ===== 双向匹配：发起匹配（岗位→人才）+ 反向匹配（人才→岗位） =====
import { agentReverse } from '@/api/matching'

const matchDialog = reactive({ visible: false, loading: false })
const matchForm = reactive({ position_ids: [], top_k: 10 })

const reverseDialog = reactive({ visible: false, loading: false, results: [] })
const reverseForm = reactive({ talent_id: '', top_k: 10 })

function openMatch() {
  matchForm.position_ids = []
  matchForm.top_k = 10
  matchDialog.visible = true
}

async function submitMatch() {
  matchDialog.loading = true
  try {
    const payload = { top_k: matchForm.top_k }
    if (matchForm.position_ids.length) payload.position_ids = matchForm.position_ids
    const res = await runMatch(payload)
    ElMessage.success(`匹配完成，共 ${res.data.total} 条结果`)
    matchDialog.visible = false
    if (matchForm.position_ids.length === 1) {
      query.position_id = String(matchForm.position_ids[0])
      query.talent_id = ''
    } else {
      query.position_id = ''
      query.talent_id = ''
    }
    query.page_size = matchForm.top_k
    query.min_score = ''
    query.page = 1
    load()
  } finally {
    matchDialog.loading = false
  }
}

function openReverse() {
  // 反向匹配：默认带入当前查询的人才 ID（如果有），方便"我先查到这个人，再看 ta 适合什么岗位"
  reverseForm.talent_id = query.talent_id || ''
  reverseForm.top_k = 10
  reverseDialog.results = []
  reverseDialog.visible = true
}

async function submitReverse() {
  if (!reverseForm.talent_id) {
    ElMessage.warning('请输入人才 ID')
    return
  }
  const tid = Number(reverseForm.talent_id)
  if (!Number.isInteger(tid) || tid <= 0) {
    ElMessage.error('人才 ID 必须是正整数')
    return
  }
  reverseDialog.loading = true
  try {
    const res = await agentReverse({ talent_id: tid, top_k: reverseForm.top_k })
    const items = res.data?.results || res.data || []
    reverseDialog.results = items
    ElMessage.success(`已为人才 #${tid} 找到 ${items.length} 个适配岗位`)
  } finally {
    reverseDialog.loading = false
  }
}

function viewReversePosition(row) {
  // 反向匹配结果：点击岗位 → 把岗位 ID 回填到查询栏 + 跳到匹配结果过滤视图
  query.position_id = String(row.position_id)
  query.talent_id = ''
  query.page = 1
  reverseDialog.visible = false
  load()
}

onBeforeUnmount(() => disposeRadar())

// 从预警页「查看该人才」跳入时（/matching/result?talent_id=N），自动按人才过滤
watch(
  () => router.currentRoute.value.query.talent_id,
  (v) => {
    if (v) {
      query.talent_id = String(v)
      query.position_id = ''
      query.page = 1
      load()
    }
  }
)

onMounted(async () => {
  await loadPositions()
  const tid = router.currentRoute.value.query.talent_id
  if (tid) query.talent_id = String(tid)
  load()
})
</script>

<template>
  <el-card>
    <!-- 工具栏第一行：查询条件（人才/岗位/分数/排序 + 查询/重置） -->
    <el-card shadow="never" class="filter-card">
      <div class="filter-title">📋 筛选条件</div>
      <div class="bar bar-filter">
        <el-input v-model="query.talent_id" placeholder="人才" style="width:130px" clearable
          @keyup.enter="query.page = 1; load()">
          <template #prefix><span style="color:#9ca3af">ID</span></template>
        </el-input>
        <el-input v-model="query.position_id" placeholder="岗位" style="width:130px" clearable
          @keyup.enter="query.page = 1; load()">
          <template #prefix><span style="color:#9ca3af">ID</span></template>
        </el-input>
        <el-input v-model="query.min_score" placeholder="≥分" style="width:110px" clearable
          @keyup.enter="query.page = 1; load()" />
        <el-select v-model="query.sort_by" style="width:130px" @change="query.page = 1; load()">
          <el-option v-for="o in SORT_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-button type="primary" @click="query.page = 1; load()">查询</el-button>
        <el-button @click="resetQuery">重置</el-button>
        <div class="bar-spacer" />
        <span class="bar-total">共 <b>{{ total }}</b> 条</span>
      </div>
    </el-card>

    <!-- 两向匹配概览：详细铺开 岗→人 / 人→岗 两条链路（替代旧的批量操作工具栏） -->
    <div class="match-overview">
      <div class="overview-card" @click="openMatch">
        <div class="ovc-icon ovc-blue">↗</div>
        <div class="ovc-body">
          <div class="ovc-head">
            <span class="ovc-title">岗位匹配人才</span>
            <span class="ovc-tag">岗位 → 人才</span>
          </div>
          <div class="ovc-desc">选岗位 → 推 TopK 候选人：bge-m3 向量 + 硬过滤 + 软加权</div>
          <div class="ovc-actions">
            <el-button type="primary" size="small" @click.stop="openMatch">发起匹配</el-button>
            <span class="ovc-hint">HR 知道缺哪个岗</span>
          </div>
        </div>
      </div>
      <div class="overview-card" @click="openReverse">
        <div class="ovc-icon ovc-green">↗</div>
        <div class="ovc-body">
          <div class="ovc-head">
            <span class="ovc-title">人才适配岗位</span>
            <span class="ovc-tag">人才 → 岗位</span>
          </div>
          <div class="ovc-desc">选人才 → 推 TopK 适配岗位：同算法反向召回并解释</div>
          <div class="ovc-actions">
            <el-button type="success" size="small" @click.stop="openReverse">反向匹配</el-button>
            <span class="ovc-hint">HR 看好某人看他还能放哪</span>
          </div>
        </div>
      </div>
      <div class="overview-card ovc-mini" @click="runEvaluate">
        <div class="ovc-icon ovc-gray">📊</div>
        <div class="ovc-body">
          <div class="ovc-head">
            <span class="ovc-title">匹配精度评估</span>
            <span class="ovc-tag">对照 ≥85%</span>
          </div>
          <div class="ovc-desc">真值参考集 → precision / recall / F1</div>
          <div class="ovc-actions">
            <el-button :loading="evalLoading" plain size="small" @click.stop="runEvaluate">开始评估</el-button>
            <span v-if="evalResult" class="ovc-result-tag" :class="evalResult.precision_pct >= 85 ? 'ok' : 'warn'">
              P{{ evalResult.precision_pct }} · R{{ (evalResult.recall*100).toFixed(0) }} · F1{{ (evalResult.f1*100).toFixed(0) }}
              {{ evalResult.precision_pct >= 85 ? '✅' : '❌' }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 精度评估结果（需求2）：reference 真值模式，显示 precision/recall/F1 -->
    <div v-if="evalResult && !evalCollapsed" class="eval-box">
      <div class="eval-head">
        <div class="eval-title">
          <b>📊 精度评估结果</b>
          <el-tag size="small" type="success" effect="plain">{{ evalResult.mode === 'reference' ? '真值评估（reference）' : '自检（粗估）' }}</el-tag>
          <span class="eval-meta" v-if="evalResult.mode === 'reference'">
            · 评估 {{ evalResult._autoPos || 0 }} 个岗位 · 每岗取算法 Top{{ evalResult.top_k || 3 }} 作为「推」
            · 推 {{ evalResult.predicted }} 条 / 应推 {{ evalResult.relevant }} 条 / 命中 {{ evalResult.tp }} 条
          </span>
          <span class="eval-meta" v-else>
            · 评估 {{ evalResult.positions_scored }} 个岗位
          </span>
        </div>
        <el-button link type="primary" @click="evalCollapsed = true">收起</el-button>
      </div>
      <div v-if="evalResult.mode === 'reference'" class="eval-metrics">
        <div class="metric">
          <div class="metric-label">精准率 Precision</div>
          <div class="metric-value" :class="evalResult.precision_pct >= 85 ? 'ok' : 'warn'">
            {{ evalResult.precision_pct }}<span class="metric-unit">%</span>
          </div>
          <div class="metric-desc">推的对 ÷ 推的总数</div>
        </div>
        <div class="metric">
          <div class="metric-label">召回率 Recall</div>
          <div class="metric-value" :class="(evalResult.recall*100) >= 80 ? 'ok' : 'warn'">
            {{ (evalResult.recall*100).toFixed(1) }}<span class="metric-unit">%</span>
          </div>
          <div class="metric-desc">推的对 ÷ 应推总数</div>
        </div>
        <div class="metric">
          <div class="metric-label">F1 值</div>
          <div class="metric-value" :class="(evalResult.f1*100) >= 80 ? 'ok' : 'warn'">
            {{ (evalResult.f1*100).toFixed(1) }}<span class="metric-unit">%</span>
          </div>
          <div class="metric-desc">2PR / (P+R) 综合</div>
        </div>
        <div class="metric" :class="evalResult.precision_pct >= 85 ? 'metric-pass' : 'metric-fail'">
          <div class="metric-label">验收结论</div>
          <div class="metric-value pass-fail">{{ evalResult.precision_pct >= 85 ? '✅ 满足' : '❌ 未达' }}</div>
          <div class="metric-desc">对照需求 ≥85%</div>
        </div>
      </div>
      <div v-else class="eval-metrics">
        <div class="metric">
          <div class="metric-label">命中率</div>
          <div class="metric-value warn">{{ evalResult.precision_pct }}<span class="metric-unit">%</span></div>
          <div class="metric-desc">top1 命中 {{ evalResult.top1_hit }} / 岗位 {{ evalResult.positions_scored }}</div>
        </div>
        <div class="metric">
          <div class="metric-label">口径</div>
          <div class="metric-desc" style="margin-top:14px;line-height:1.6">
            top1 且 skill 维度 ≥60 视为命中。<br/>
            当前结果来自自动构建的真值参考集（top1=正例/top2-4=反例），
            如需更严谨：人工标注真值后用 reference 模式。
          </div>
        </div>
      </div>
      <div class="eval-note" v-if="evalResult.mode === 'reference'">
        📌 评估口径：每岗取算法 Top{{ evalResult.top_k || 3 }} 候选作为"推"，对应 HR 实际"看 Top 选人"的工作流；
        top1=正例、top2-{{ evalResult.top_k || 3 }}=反例 构成自洽真值集测算 precision/recall/F1；
        想要更贴近业务的人工真值，可在 <code>/matching/eval</code> 接口传入更精细的标注数据。
      </div>
      <div class="eval-note" v-else>{{ evalResult.note }}</div>
    </div>

    <el-table :data="rows" v-loading="loading" stripe row-key="id">
      <el-table-column prop="id" label="ID" width="52" />
      <el-table-column prop="talent_id" label="人才ID" width="74" />
      <el-table-column label="岗位" min-width="120">
        <template #default="{ row }">{{ posMap[row.position_id] || ('#' + row.position_id) }}</template>
      </el-table-column>
      <el-table-column label="匹配度" width="78" sortable :sort-by="(r)=>Number(r.score)">
        <template #default="{ row }">
          <el-tag :type="scoreType(row.score)" size="small">{{ Number(row.score).toFixed(1) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="72">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="保温状态" width="108">
        <template #default="{ row }">
          <el-tooltip :content="warmMeta(row)" placement="top">
            <el-tag :type="warmState(row).type" size="small" effect="dark">{{ warmState(row).label }}</el-tag>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="生成时间" width="118" sortable :sort-by="(r)=>r.created_at">
        <template #default="{ row }">
          <el-tooltip :content="row.created_at" placement="top">
            <span>{{ fmtShort(row.created_at) }}</span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <div class="row-actions">
            <el-tooltip content="查看人才档案" placement="top">
              <el-button type="primary" link size="small" @click="viewTalent(row)">
                <el-icon style="vertical-align:-2px;margin-right:2px"><User /></el-icon>档案
              </el-button>
            </el-tooltip>
            <el-tooltip content="查看匹配解释" placement="top">
              <el-button type="primary" link size="small" @click="openExplain(row)">
                <el-icon style="vertical-align:-2px;margin-right:2px"><View /></el-icon>解释
              </el-button>
            </el-tooltip>
            <el-tooltip content="记录一次保温跟进（话术/记录/加热）" placement="top">
              <el-button type="warning" link size="small" @click="openFollow(row)">
                <el-icon style="vertical-align:-2px;margin-right:2px"><Sunny /></el-icon>跟进
              </el-button>
            </el-tooltip>
            <el-tooltip content="状态流转：候选→推荐→录用" placement="top">
              <el-button type="success" link size="small" @click="changeStatus(row)">
                <el-icon style="vertical-align:-2px;margin-right:2px"><Refresh /></el-icon>流转
              </el-button>
            </el-tooltip>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination style="margin-top:14px" layout="total, prev, pager, next" :total="total"
      v-model:current-page="query.page" :page-size="query.page_size" @current-change="load" />
  </el-card>

  <!-- 保温跟进弹窗（公共组件，与预警页一致） -->
  <FollowDialog v-model="showFollow" :row="followTarget" @success="onFollowSuccess" />

  <!-- 解释详情抽屉 -->
  <el-drawer v-model="drawer.visible" title="匹配解释详情" size="460px" @closed="disposeRadar">
    <div v-loading="drawer.loading">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="记录ID">{{ drawer.id }}</el-descriptions-item>
        <el-descriptions-item label="解释生成">LLM/规则</el-descriptions-item>
      </el-descriptions>

      <!-- 雷达图：四维得分可视化 -->
      <div v-if="Object.keys(drawer.dims).length" class="block-title">维度雷达</div>
      <div ref="radarEl" v-if="Object.keys(drawer.dims).length" class="radar-box" />

      <div class="block-title">维度得分</div>
      <div v-if="Object.keys(drawer.dims).length" class="dim-list">
        <div v-for="(v, k) in drawer.dims" :key="k" class="dim-item">
          <span class="dim-label">{{ DIM_LABEL[k] || k }}</span>
          <el-progress :percentage="Number(v)" :stroke-width="8" :color="'#2563eb'"
            :status="Number(v) >= 80 ? 'success' : ''" />
        </div>
      </div>
      <el-empty v-else description="无维度得分" :image-size="60" />

      <div class="block-title">匹配依据</div>
      <div class="explain-text">{{ drawer.explain || '—' }}</div>

      <div style="margin-top:16px">
        <el-button type="primary" plain size="small" @click="regenerate" :loading="drawer.loading">刷新解释</el-button>
      </div>
    </div>
  </el-drawer>

  <!-- 反向匹配：人才 → 岗位（深度学习向量检索：Milvus position_vec 召回 + 软加权打分） -->
  <el-dialog v-model="reverseDialog.visible" title="反向匹配（人才适配岗位）" width="720px" append-to-body>
    <el-form label-width="100px" :inline="false">
      <el-form-item label="人才 ID">
        <el-input-number v-model="reverseForm.talent_id" :min="1" :max="9999" controls-position="right"
          placeholder="请输入人才 ID" style="width:180px" />
        <span style="margin-left:12px;color:#9ca3af;font-size:12px">
          （从 tal_talent 档案中取一个；不记得 ID 时可先在「匹配结果」用 talent_id 筛到该人才后点反向）
        </span>
      </el-form-item>
      <el-form-item label="召回量 TopK">
        <el-input-number v-model="reverseForm.top_k" :min="1" :max="100" controls-position="right" />
      </el-form-item>
    </el-form>
    <div class="tip">
      算法：基于深度学习 bge-m3 向量相似度 + 学历/经验/技能硬过滤 + 维度软加权打分，输出最适合该人才的 Top K 个岗位。
    </div>

    <template v-if="reverseDialog.results.length">
      <div class="rev-header">
        <b>人才 #{{ reverseForm.talent_id }}</b> 适配岗位 Top{{ reverseDialog.results.length }}
        <span class="rev-sub">（按匹配度降序）</span>
      </div>
      <el-table :data="reverseDialog.results" stripe max-height="360">
        <el-table-column prop="rank" label="#" width="48" />
        <el-table-column label="岗位" min-width="180">
          <template #default="{ row }">
            <b>{{ row.position_name }}</b>
            <div style="color:#9ca3af;font-size:12px">岗位 ID: {{ row.position_id }}</div>
          </template>
        </el-table-column>
        <el-table-column label="匹配度" width="120" sortable :sort-method="(a,b)=>a.score-b.score">
          <template #default="{ row }">
            <el-tag :type="Number(row.score) >= 80 ? 'success' : (Number(row.score) >= 60 ? 'warning' : 'danger')">
              {{ Number(row.score).toFixed(1) }} 分
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="四维得分" min-width="240">
          <template #default="{ row }">
            <div class="rev-dims" v-if="row.dimension_json">
              <span>技能 <b>{{ fmtDim(row.dimension_json, 'skill') }}</b></span>
              <span>学历 <b>{{ fmtDim(row.dimension_json, 'degree') }}</b></span>
              <span>经验 <b>{{ fmtDim(row.dimension_json, 'years') }}</b></span>
              <span>素质 <b>{{ fmtDim(row.dimension_json, 'quality') }}</b></span>
            </div>
            <span v-else style="color:#9ca3af">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewReversePosition(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </template>
    <el-empty v-else-if="!reverseDialog.loading" description="输入人才 ID 后点「开始反向匹配」" :image-size="60" />

    <template #footer>
      <el-button @click="reverseDialog.visible = false">关闭</el-button>
      <el-button type="primary" @click="submitReverse" :loading="reverseDialog.loading">开始反向匹配</el-button>
    </template>
  </el-dialog>

  <!-- 发起匹配（岗位→人才） -->
  <el-dialog v-model="matchDialog.visible" title="发起双向匹配" width="460px">
    <el-form label-width="100px">
      <el-form-item label="匹配岗位">
        <el-select v-model="matchForm.position_ids" multiple filterable placeholder="留空则匹配全部启用岗位" style="width:100%">
          <el-option v-for="p in positions" :key="p.id" :label="`${p.name}(${p.code})`" :value="p.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="召回量TopK">
        <el-input-number v-model="matchForm.top_k" :min="1" :max="100" controls-position="right" />
      </el-form-item>
    </el-form>
    <div class="tip">需 Milvus 的 position_vec / talent_vec 集合就绪；岗位需先执行画像向量化。</div>
    <template #footer>
      <el-button @click="matchDialog.visible = false">取消</el-button>
      <el-button type="primary" @click="submitMatch" :loading="matchDialog.loading">开始匹配</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.bar-filter { gap: 10px; }
.bar-spacer { flex: 1; }
.bar-total { color: #6b7280; font-size: 13px; }
.bar-total b { color: #2563eb; font-size: 15px; margin: 0 2px; }

/* 筛选卡（与下方卡片区视觉平衡） */
.filter-card { margin-bottom: 14px; padding: 4px 0; }
.filter-title { font-size: 13px; font-weight: 600; color: #6b7280; padding: 0 4px 8px; border-bottom: 1px dashed #e5e7eb; margin-bottom: 10px; }

/* === 两向匹配概览卡片（紧凑版，与筛选行视觉平衡） === */
.match-overview { display: grid; grid-template-columns: 1fr 1fr 0.7fr; gap: 12px; margin-bottom: 16px; }
.overview-card { display: flex; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; cursor: pointer; transition: all .2s; align-items: center; }
.overview-card:hover { border-color: #93c5fd; box-shadow: 0 4px 12px rgba(0,0,0,0.06); transform: translateY(-1px); }
.ovc-icon { width: 40px; height: 40px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: 700; color: #fff; flex-shrink: 0; }
.ovc-blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.ovc-green { background: linear-gradient(135deg, #10b981, #059669); }
.ovc-gray { background: linear-gradient(135deg, #6b7280, #4b5563); }
.ovc-body { flex: 1; min-width: 0; }
.ovc-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.ovc-title { font-size: 14px; font-weight: 700; color: #1f2937; }
.ovc-tag { font-size: 10px; font-weight: 500; color: #6b7280; background: #f3f4f6; padding: 1px 6px; border-radius: 3px; }
.ovc-desc { color: #6b7280; font-size: 12px; line-height: 1.4; margin: 4px 0 8px; }
.ovc-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ovc-hint { color: #9ca3af; font-size: 11px; }
.ovc-mini { background: #f9fafb; }
.ovc-result-tag { font-size: 11px; padding: 1px 6px; border-radius: 3px; font-family: ui-monospace, monospace; font-weight: 600; }
.ovc-result-tag.ok { background: #ecfdf5; color: #059669; }
.ovc-result-tag.warn { background: #fef2f2; color: #dc2626; }
@media (max-width: 1200px) { .match-overview { grid-template-columns: 1fr 1fr; } .ovc-mini { grid-column: 1 / -1; } }
@media (max-width: 760px) { .match-overview { grid-template-columns: 1fr; } }
.block-title { font-weight: 600; margin: 18px 0 10px; color: #1f2937; }
.radar-box { width: 100%; height: 240px; margin-bottom: 4px; }
.dim-list { display: flex; flex-direction: column; gap: 10px; }
.dim-item { display: flex; align-items: center; gap: 10px; }
.dim-label { width: 70px; color: #6b7280; font-size: 13px; flex-shrink: 0; }
.explain-text { background: #f5f7fa; border-radius: 8px; padding: 12px; line-height: 1.7; color: #1f2937; font-size: 14px; }
.warm-meta { font-size: 11px; color: #9ca3af; line-height: 1.4; margin-top: 2px; white-space: nowrap; }
.tpl-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.row-actions { display: flex; align-items: center; gap: 4px; flex-wrap: nowrap; }
.row-actions .el-button { padding: 4px 6px; }
.row-actions .el-icon { font-size: 14px; }
.tip { color: #9ca3af; font-size: 12px; margin-top: 4px; }
.rev-header { font-size: 14px; color: #1f2937; margin: 10px 0 8px; padding: 8px 12px; background: #ecfdf5; border-left: 3px solid #10b981; border-radius: 4px; }
.rev-header .rev-sub { color: #9ca3af; font-weight: normal; margin-left: 6px; }
.rev-dims { display: flex; flex-wrap: wrap; gap: 4px 10px; font-size: 12px; color: #4b5563; }
.rev-dims b { color: #2563eb; margin-left: 2px; }
.eval-box {
  background: linear-gradient(135deg, #f0f7ff, #e0f2fe);
  border: 1px solid #93c5fd; border-radius: 10px;
  padding: 14px 18px; margin-bottom: 16px;
}
.eval-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.eval-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 14px; }
.eval-title b { font-size: 15px; }
.eval-meta { color: #6b7280; font-size: 12px; }
.eval-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.metric { background: #fff; border: 1px solid #dbeafe; border-radius: 8px; padding: 12px 14px; text-align: center; }
.metric-label { color: #6b7280; font-size: 12px; margin-bottom: 6px; }
.metric-value { font-size: 30px; font-weight: 800; line-height: 1.1; color: #1f2937; font-family: ui-monospace, monospace; }
.metric-value .metric-unit { font-size: 16px; font-weight: 600; margin-left: 2px; opacity: 0.6; }
.metric-value.ok { color: #059669; }
.metric-value.warn { color: #d97706; }
.metric-value.pass-fail { font-size: 22px; }
.metric.metric-pass { background: #ecfdf5; border-color: #6ee7b7; }
.metric.metric-fail { background: #fef2f2; border-color: #fca5a5; }
.metric.metric-pass .metric-value { color: #059669; }
.metric.metric-fail .metric-value { color: #dc2626; }
.metric-desc { color: #9ca3af; font-size: 11px; margin-top: 4px; }
.eval-note { color: #475569; font-size: 12px; line-height: 1.6; margin-top: 10px; padding: 8px 12px; background: #f8fafc; border-radius: 6px; }
.eval-note code { background: #e2e8f0; padding: 1px 5px; border-radius: 3px; font-family: ui-monospace, monospace; font-size: 11px; }
</style>
