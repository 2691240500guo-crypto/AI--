<template>
  <div class="matching-alert">
    <!-- 页头：类型 + 岗位筛选 + 生成预警 -->
    <el-card shadow="never" class="toolbar">
      <div class="toolbar-row">
        <el-select v-model="typeFilter" style="width:120px" @change="load">
          <el-option label="全部类型" value="" />
          <el-option label="岗位空缺" value="vacancy" />
          <el-option label="人才储备" value="reserve" />
        </el-select>
        <el-select v-model="positionId" placeholder="全部岗位" clearable filterable style="width:200px"
          @change="load">
          <el-option v-for="p in positions" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-button type="primary" :loading="generating" @click="generate">生成储备/空缺预警</el-button>
        <el-button :disabled="rows.length === 0" @click="load">刷新</el-button>
        <span style="margin-left:auto;color:#999;font-size:12px">
          🔥 {{ vacancyRows.length }} 条空缺 · 🟡 {{ reserveRows.length }} 条储备
        </span>
      </div>
    </el-card>

    <!-- 区块 1：🔥 岗位空缺（卡片式，补位清单默认展开） -->
    <el-card v-if="showVacancy" shadow="never" class="section">
      <template #header>
        <div class="sec-header">
          <span class="sec-title danger">🔥 岗位空缺</span>
          <el-tag type="danger" effect="dark" size="small">共 {{ vacancyRows.length }} 条</el-tag>
          <span class="sec-trigger">
            <b>触发条件：</b>岗位编制数大于实际到岗数（编制 > 到岗）时，系统自动检测缺口并按匹配分推荐 Top3 储备人才清单（24h 内同清单不重推）
          </span>
        </div>
      </template>
      <el-empty v-if="!vacancyRows.length" description="🎉 暂无空缺岗位，所有启用岗位均已满员" :image-size="60" />
      <div v-else class="vacancy-cards">
        <div v-for="row in vacancyRows" :key="row.id" class="vacancy-card">
          <div class="vc-head">
            <div class="vc-pos">
              <div class="vc-pos-name">{{ row.position_name || '#' + row.position_id }}</div>
              <el-tag size="small" type="info" effect="plain" class="vc-code"
                v-if="positionInfo(row.position_id)?.code">
                code: {{ positionInfo(row.position_id).code }}
              </el-tag>
              <span class="vc-stats">编制 {{ positionInfo(row.position_id)?.headcount ?? '-' }} / 到岗 {{ positionInfo(row.position_id)?.filled ?? '-' }}</span>
            </div>
            <div class="vc-shortage" :title="'该岗位需要补 ' + vacancyCount(row) + ' 人'">
              <div class="vc-shortage-label">需补</div>
              <div class="vc-shortage-num">{{ vacancyCount(row) }}</div>
              <div class="vc-shortage-unit">人</div>
            </div>
          </div>
          <div class="vc-meta">
            <span>📅 {{ fmt(row.created_at) }} 触发 · 24h 内同清单不重复</span>
            <el-button link type="primary" size="small" @click="refreshCandidates(row)">刷新清单</el-button>
          </div>
          <div class="vc-list-title">
            🔥 按匹配分降序推荐 <b>{{ candidates(row.position_id).length || '?' }}</b> 人（缺 {{ vacancyCount(row) }} 人）
          </div>
          <div v-loading="candidatesLoading(row.position_id)" class="backfill-list">
            <div v-for="(c, i) in candidates(row.position_id)" :key="c.id" class="backfill-card">
              <div class="bf-rank">{{ i + 1 }}</div>
              <div class="bf-main">
                <div class="bf-line">
                  <b>{{ c.talent_name || ('人才#' + c.talent_id) }}</b>
                  <span style="color:#9ca3af;font-size:12px;margin-left:4px">#{{ c.talent_id }}</span>
                  <el-tag :type="Number(c.score) >= 80 ? 'success' : 'warning'" size="small" effect="plain">
                    匹配 {{ Number(c.score).toFixed(1) }} 分
                    <span v-if="Number(c.score) >= 80">（达标）</span>
                    <span v-else>（未达标）</span>
                  </el-tag>
                  <el-tooltip :content="warmMeta(c)" placement="top">
                    <el-tag :type="warmState(c).type" size="small" effect="dark">{{ warmState(c).label }}</el-tag>
                  </el-tooltip>
                </div>
                <div class="bf-sub">{{ warmMeta(c) }}</div>
              </div>
              <div class="bf-actions">
                <el-button link type="primary" size="small" @click="goResult(c)">查看该人才</el-button>
                <el-button link type="warning" size="small" @click="openCandidateFollow(c)">立即跟进</el-button>
              </div>
            </div>
            <el-empty v-if="candidates(row.position_id) && !candidates(row.position_id).length"
              description="该岗位暂无补位候选" :image-size="48" />
          </div>
        </div>
      </div>
    </el-card>

    <!-- 区块 2：🟡 人才储备（紧凑列表） -->
    <el-card v-if="showReserve" shadow="never" class="section">
      <template #header>
        <div class="sec-header">
          <span class="sec-title warning">🟡 人才储备</span>
          <el-tag type="warning" effect="dark" size="small">共 {{ reserveRows.length }} 条</el-tag>
          <span class="sec-trigger">
            <b>触发条件：</b>匹配分 ≥ 80 且仍为候选（状态0）的高分人才，建议纳入保温池持续维护（24h 内同人×同岗不重推）
          </span>
        </div>
      </template>
      <el-empty v-if="!reserveRows.length" description="暂无储备人才预警，可点击上方「生成」按钮触发" :image-size="60" />
      <el-table v-else :data="reserveRows" stripe row-key="id">
        <el-table-column prop="id" label="ID" width="64" />
        <el-table-column label="岗位" min-width="130">
          <template #default="{ row }">{{ row.position_name || ('#' + (row.position_id ?? '')) }}</template>
        </el-table-column>
        <el-table-column label="人才" min-width="120">
          <template #default="{ row }">
            <span>{{ talentLabel(row.talent_id) || ('人才#' + row.talent_id) }}</span>
            <span style="color:#9ca3af;font-size:12px;margin-left:4px">#{{ row.talent_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="匹配分" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.score != null" :type="Number(row.score) >= 80 ? 'success' : 'warning'" size="small">
              {{ Number(row.score).toFixed(1) }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="保温状态" width="130">
          <template #default="{ row }">
            <el-tooltip :content="warmMeta(row)" placement="top">
              <el-tag :type="warmState(row).type" size="small" effect="dark">{{ warmState(row).label }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="推送消息" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.msg_title || '—' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="触发时间" width="160" />
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.match_id" link type="warning" @click="openAlertFollow(row)">保温跟进</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 保温跟进弹窗（公共组件，与匹配结果页一致） -->
    <FollowDialog v-model="showFollow" :row="followTarget" @success="onFollowSuccess" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { listPositions, listResults, listAlerts, generateAlerts } from '@/api/matching'
import { getTalent } from '@/api/talent'
import { warmState, warmMeta } from '@/utils/matchingWarm'
import FollowDialog from './FollowDialog.vue'

const router = useRouter()
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const generating = ref(false)
const positionId = ref(null)
const typeFilter = ref('')
const positions = ref([])

// 按类型分桶（自动响应 rows 变化）
const vacancyRows = computed(() => rows.value.filter((r) => r.type === 'vacancy'))
const reserveRows = computed(() => rows.value.filter((r) => r.type === 'reserve'))

// 区块显隐：选具体类型时只显示对应区块；"全部类型"则两个都显示
const showVacancy = computed(() => !typeFilter.value || typeFilter.value === 'vacancy')
const showReserve = computed(() => !typeFilter.value || typeFilter.value === 'reserve')

// 岗位额外信息（编制/到岗/code）—— 来自 loadPositions 列表，构建索引
const positionMap = computed(() => {
  const m = {}
  for (const p of positions.value) m[p.id] = p
  return m
})
function positionInfo(pid) { return positionMap.value[pid] || null }
function vacancyCount(row) {
  const p = positionInfo(row.position_id)
  if (!p) return null
  return Math.max(0, Number(p.headcount || 0) - Number(p.filled || 0))
}
function fmt(t) { return t ? String(t).replace('T', ' ').slice(0, 19) : '-' }

// hq+ 2026-09-04：人才姓名索引（预警接口未返回姓名，前端批量补齐）
const talentNameMap = reactive({})
async function fillTalentNames(ids) {
  const missing = ids.filter((i) => i && talentNameMap[i] == null)
  if (!missing.length) return
  await Promise.all(missing.map(async (id) => {
    try {
      const res = await getTalent(id)
      talentNameMap[id] = res.data?.name || ''
    } catch { talentNameMap[id] = '' }
  }))
}
function talentLabel(id) {
  const n = talentNameMap[id]
  return n ? n : `人才#${id}`
}

// 空缺补位清单缓存：position_id -> 候选人才列表（来自 /matching/results，与匹配结果页同源）
const candMap = reactive({})
const candLoading = reactive({})

function candidates(pid) { return candMap[pid] || [] }
function candidatesLoading(pid) { return !!candLoading[pid] }

// 保温跟进（公共弹窗）
const showFollow = ref(false)
const followTarget = ref(null)
// 预警行对象主键是日志 id，保温跟进需要的是 match_result.id → 归一化
function openAlertFollow(row) {
  followTarget.value = {
    id: row.match_id, talent_id: row.talent_id, position_id: row.position_id,
    score: row.score, warm_level: row.warm_level || 0,
    last_follow_up: row.last_follow_up, status: row.match_status,
  }
  showFollow.value = true
}
function openCandidateFollow(c) {
  followTarget.value = c
  showFollow.value = true
}
function onFollowSuccess(u) {
  // 同步已展开的补位候选卡片状态，再刷新预警列表（锚行温度/时间回火热）
  for (const pid of Object.keys(candMap)) {
    const c = (candMap[pid] || []).find((x) => x.id === u.id)
    if (c) { c.warm_level = u.warm_level; c.last_follow_up = u.last_follow_up }
  }
  load()
}

// 加载预警时并行预取所有空缺岗位的补位清单（一打开页面就能看到 Top3）
async function preloadVacancyCandidates() {
  const pids = [...new Set(vacancyRows.value.map((r) => r.position_id).filter(Boolean))]
  await Promise.all(pids.map((pid) => refreshCandidatesByPid(pid, true)))
}
// 按需：候选取 top min(缺编数, 5)，缺几个就推几个（演示"缺几个推几个"的承诺）
async function refreshCandidatesByPid(pid, silent = false) {
  if (!pid) return
  if (!silent) candLoading[pid] = true
  try {
    const res = await listResults({ position_id: pid, page: 1, page_size: 50, sort_by: 'score' })
    const items = res.data?.items || []
    // 从本地推算该岗位缺编数（避免再发请求）
    const pos = positions.value.find((p) => p.id === pid)
    const vac = pos ? Math.max(0, Number(pos.headcount || 0) - Number(pos.filled || 0)) : 0
    const cap = Math.min(vac || 3, 5) // 缺 0 的兜底取 3，缺编时严格按缺编数，封顶 5
    // 剔除已录用，按匹配分降序取 cap 个
    candMap[pid] = items.filter((x) => Number(x.status) !== 2).slice(0, cap)
  } catch { /* error shown by interceptor */ } finally {
    candLoading[pid] = false
  }
}
async function refreshCandidates(row) {
  return refreshCandidatesByPid(row.position_id)
}

async function load() {
  loading.value = true
  try {
    const params = {}
    if (positionId.value != null) params.position_id = positionId.value
    if (typeFilter.value) params.type = typeFilter.value
    const res = await listAlerts(params)
    rows.value = res.data || []
    total.value = rows.value.length
    // hq+ 2026-09-04：批量预取预警行涉及的人才姓名
    const ids = [...new Set(rows.value.map((r) => r.talent_id).filter(Boolean))]
    await fillTalentNames(ids)
    // 拉到的空缺岗位 → 并行预取补位清单（卡片默认展开需要数据）
    await preloadVacancyCandidates()
  } finally {
    loading.value = false
  }
}

async function loadPositions() {
  try {
    const all = []
    let page = 1
    for (;;) {
      const res = await listPositions({ page, page_size: 200, status: 1 })
      const items = res.data?.items || []
      all.push(...items)
      const meta = res.data?.meta
      if (!items.length || (meta && page >= meta.total_pages)) break
      page++
    }
    positions.value = all
  } catch { /* 岗位列表加载失败不阻塞预警展示 */ }
}

async function generate() {
  generating.value = true
  try {
    const params = {}
    if (positionId.value != null) params.position_id = positionId.value
    const res = await generateAlerts(params)
    const created = res.data?.total ?? 0
    ElMessage.success(created > 0 ? `已生成 ${created} 条预警（24h 去重窗口内已存在的不重复生成）` : '没有新的预警（24h 去重窗口内均已生成）')
    load()
  } finally {
    generating.value = false
  }
}

// 跳转匹配结果页并按人才过滤（配合 Result 页路由入参 talent_id）
function goResult(c) {
  router.push({ path: '/matching/result', query: { talent_id: c.talent_id } })
}

onMounted(() => { loadPositions(); load() })
</script>

<style scoped>
.toolbar-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.section { margin-top: 12px; }
.sec-header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.sec-title { font-size: 16px; font-weight: 700; }
.sec-title.danger { color: #dc2626; }
.sec-title.warning { color: #d97706; }
.sec-trigger { color: #6b7280; font-size: 12px; line-height: 1.5; flex: 1; min-width: 280px; }
.vacancy-cards { display: flex; flex-direction: column; gap: 14px; }
.vacancy-card {
  background: #fff; border: 1px solid #fecaca; border-radius: 10px;
  padding: 12px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.vc-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.vc-pos { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; min-width: 0; }
.vc-pos-name { font-size: 17px; font-weight: 700; color: #111827; }
.vc-code { font-family: ui-monospace, monospace; }
.vc-stats { color: #9ca3af; font-size: 12px; }
.vc-shortage {
  display: flex; align-items: baseline; gap: 4px;
  background: linear-gradient(135deg, #dc2626, #ef4444);
  color: #fff; border-radius: 10px; padding: 8px 16px;
  box-shadow: 0 4px 12px rgba(220, 38, 38, 0.25);
  flex-shrink: 0;
}
.vc-shortage-label { font-size: 13px; opacity: 0.9; }
.vc-shortage-num { font-size: 30px; font-weight: 800; line-height: 1; font-family: ui-monospace, monospace; }
.vc-shortage-unit { font-size: 13px; opacity: 0.9; }
.vc-meta { display: flex; align-items: center; gap: 12px; color: #9ca3af; font-size: 12px; margin-top: 8px; flex-wrap: wrap; }
.vc-list-title { color: #374151; font-size: 13px; font-weight: 600; margin: 12px 0 8px; padding-left: 4px; }
.backfill-list { display: flex; flex-direction: column; gap: 8px; min-height: 40px; }
.backfill-card {
  display: flex; align-items: center; gap: 12px;
  background: #f7f9fc; border: 1px solid #ebeef5; border-radius: 8px; padding: 8px 12px;
}
.bf-rank {
  width: 22px; height: 22px; border-radius: 50%; background: #2563eb; color: #fff;
  font-size: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.bf-main { flex: 1; min-width: 0; }
.bf-line { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.bf-sub { color: #9ca3af; font-size: 12px; margin-top: 2px; }
.bf-actions { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
.reserve-note { color: #9ca3af; font-size: 13px; padding: 10px 4px; }
</style>
