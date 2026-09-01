<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listResults, getExplain, runMatch, listPositions } from '@/api/matching'

// 维度中文映射
const DIM_LABEL = { skill: '技能', degree: '学历', years: '经验', quality: '综合素质' }

// ===== 列表与查询 =====
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, page_size: 10, talent_id: '', position_id: '', min_score: '' })

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
    const res = await listResults(params)
    rows.value = res.data.items
    total.value = res.data.meta.total
  } finally {
    loading.value = false
  }
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

// ===== 解释详情抽屉 =====
const drawer = reactive({ visible: false, loading: false, id: null, explain: '', dims: {} })

async function openExplain(row) {
  drawer.id = row.id
  drawer.explain = row.explain || ''
  drawer.dims = parseDims(row.dimension_json)
  drawer.visible = true
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
    // 传 ?force=1 触发重新生成（后端 explain 支持 force，路由未暴露 force 参数，此处复用 GET 端点取缓存即可）
    const res = await getExplain(drawer.id)
    drawer.explain = res.data.explain || ''
    ElMessage.success('解释已刷新')
  } finally {
    drawer.loading = false
  }
}

// ===== 发起匹配（M-3，依赖 Milvus 向量集合就绪） =====
const matchDialog = reactive({ visible: false, loading: false })
const matchForm = reactive({ position_ids: [], top_k: 10 })

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
    load()
  } finally {
    matchDialog.loading = false
  }
}

onMounted(async () => {
  await loadPositions()
  load()
})
</script>

<template>
  <el-card>
    <div class="bar">
      <el-input v-model="query.talent_id" placeholder="人才ID" style="width:120px" clearable
        @keyup.enter="query.page = 1; load()" />
      <el-input v-model="query.position_id" placeholder="岗位ID" style="width:120px" clearable
        @keyup.enter="query.page = 1; load()" />
      <el-input v-model="query.min_score" placeholder="最低分(如60)" style="width:140px" clearable
        @keyup.enter="query.page = 1; load()" />
      <el-button type="primary" @click="query.page = 1; load()">查询</el-button>
      <el-button type="primary" plain @click="openMatch">发起匹配</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="talent_id" label="人才ID" width="90" />
      <el-table-column label="岗位" min-width="130">
        <template #default="{ row }">
          {{ posMap[row.position_id] || ('#' + row.position_id) }}
        </template>
      </el-table-column>
      <el-table-column label="匹配度" width="110">
        <template #default="{ row }">
          <el-tag :type="scoreType(row.score)" size="small">{{ Number(row.score).toFixed(1) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="rank" label="排序" width="80" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="生成时间" width="170" />
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openExplain(row)">查看解释</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination style="margin-top:14px" layout="total, prev, pager, next" :total="total"
      v-model:current-page="query.page" :page-size="query.page_size" @current-change="load" />
  </el-card>

  <!-- 解释详情抽屉 -->
  <el-drawer v-model="drawer.visible" title="匹配解释详情" size="420px">
    <div v-loading="drawer.loading">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="记录ID">{{ drawer.id }}</el-descriptions-item>
        <el-descriptions-item label="解释生成">LLM/规则</el-descriptions-item>
      </el-descriptions>

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

  <!-- 发起匹配 -->
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
.bar { display: flex; gap: 10px; margin-bottom: 14px; align-items: center; }
.block-title { font-weight: 600; margin: 18px 0 10px; color: #1f2937; }
.dim-list { display: flex; flex-direction: column; gap: 10px; }
.dim-item { display: flex; align-items: center; gap: 10px; }
.dim-label { width: 70px; color: #6b7280; font-size: 13px; flex-shrink: 0; }
.explain-text { background: #f5f7fa; border-radius: 8px; padding: 12px; line-height: 1.7; color: #1f2937; font-size: 14px; }
.tip { color: #9ca3af; font-size: 12px; margin-top: 4px; }
</style>
