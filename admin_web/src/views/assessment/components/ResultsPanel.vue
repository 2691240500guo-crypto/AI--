<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { getBatchStatistics, getQuestionStatistics, getStatistics, listAssessmentBatches, listPapers, listResults } from '@/api/assessment'
import AssessmentRadar from './AssessmentRadar.vue'
import ResultDetailDrawer from './ResultDetailDrawer.vue'

const papers = ref([])
const batches = ref([])
const rows = ref([])
const questionStats = ref([])
const batchStats = ref([])
const loading = ref(false)
const statsLoading = ref(false)
const errorMessage = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const selectedResultId = ref(null)
const drawerVisible = ref(false)
const stats = reactive({ total_results: 0, completed_results: 0, average_score: 0, pass_count: 0, pass_rate: 0, dimensions: [] })
const filters = reactive({ talent_id: null, paper_id: null, batch_id: null, status: null })
const statusLabels = { 0: '未答', 1: '答题中', 2: '已交卷', 3: '报告已生成' }
const radarDimensions = computed(() => (stats.dimensions || []).map((item) => ({ ...item, rate: item.accuracy })))
const filteredBatches = computed(() => filters.paper_id
  ? batches.value.filter((batch) => batch.paper_id === filters.paper_id)
  : batches.value)

async function load() {
  loading.value = true
  statsLoading.value = true
  errorMessage.value = ''
  try {
    const params = { page: page.value, page_size: pageSize.value, ...filters }
    const filterParams = { talent_id: filters.talent_id, paper_id: filters.paper_id, batch_id: filters.batch_id }
    const [resultResponse, statsResponse, questionResponse, batchResponse] = await Promise.all([
      listResults(params),
      getStatistics(filterParams),
      getQuestionStatistics({ paper_id: filters.paper_id, batch_id: filters.batch_id }),
      getBatchStatistics({ paper_id: filters.paper_id, batch_id: filters.batch_id }),
    ])
    rows.value = resultResponse.data.items || []
    total.value = resultResponse.data.meta?.total || 0
    Object.assign(stats, statsResponse.data || {})
    questionStats.value = questionResponse.data.items || []
    batchStats.value = batchResponse.data.items || []
  } catch (error) {
    errorMessage.value = error?.message || '成绩统计加载失败，请重试'
  } finally {
    loading.value = false
    statsLoading.value = false
  }
}

async function loadPapersAndBatches() {
  const [paperResponse, batchResponse] = await Promise.all([
    listPapers({ page: 1, page_size: 200 }),
    listAssessmentBatches({ page: 1, page_size: 200 }),
  ])
  papers.value = paperResponse.data.items || []
  batches.value = batchResponse.data.items || []
}

function search() { page.value = 1; load() }
function reset() {
  Object.assign(filters, { talent_id: null, paper_id: null, batch_id: null, status: null })
  search()
}
function openDetail(row) { selectedResultId.value = row.id; drawerVisible.value = true }
function formatDate(value) { return value ? new Date(value).toLocaleString() : '—' }
function percent(value) { return `${Math.round(Number(value || 0) * 100)}%` }
function questionLabel(row) { return `#${row.question_id} ${row.content}` }
function scoreLabel(row) { return `${row.score ?? 0} / ${row.paper_total_score ?? '—'}` }
function dimensionRate(row) { return Number(row.accuracy || 0) }
function dimensionSort(a, b) { return dimensionRate(b) - dimensionRate(a) }

onMounted(async () => {
  try { await loadPapersAndBatches() } catch (error) { errorMessage.value = error?.message || '筛选项加载失败，请重试' }
  await load()
})
</script>

<template>
  <div v-loading="statsLoading" class="results-panel">
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''" />
    <el-row :gutter="14" class="stat-row">
      <el-col :xs="12" :sm="6"><el-card shadow="never"><el-statistic title="测评总数" :value="stats.total_results" /></el-card></el-col>
      <el-col :xs="12" :sm="6"><el-card shadow="never"><el-statistic title="已完成" :value="stats.completed_results" /></el-card></el-col>
      <el-col :xs="12" :sm="6"><el-card shadow="never"><el-statistic title="平均得分率" :value="Number(stats.average_rate || 0) * 100" suffix="%" :precision="1" /></el-card></el-col>
      <el-col :xs="12" :sm="6"><el-card shadow="never"><el-statistic title="合格率" :value="Number(stats.pass_rate || 0) * 100" suffix="%" :precision="1" /></el-card></el-col>
    </el-row>
    <el-card shadow="never" class="table-card">
      <div class="filters">
        <el-input-number v-model="filters.talent_id" :min="1" :controls="false" placeholder="人员 ID" />
        <el-select v-model="filters.paper_id" clearable placeholder="全部试卷" style="width:220px" @change="filters.batch_id = null">
          <el-option v-for="paper in papers" :key="paper.id" :label="paper.title" :value="paper.id" />
        </el-select>
        <el-select v-model="filters.batch_id" clearable filterable placeholder="全部批次" style="width:240px">
          <el-option v-for="batch in filteredBatches" :key="batch.id" :label="`${batch.name}（${batch.batch_no}）`" :value="batch.id" />
        </el-select>
        <el-select v-model="filters.status" clearable placeholder="全部状态" style="width:140px"><el-option v-for="(label, value) in statusLabels" :key="value" :label="label" :value="Number(value)" /></el-select>
        <el-button type="primary" @click="search">查询</el-button><el-button @click="reset">重置</el-button>
      </div>
      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="65" />
        <el-table-column prop="talent_name" label="人员" width="120" />
        <el-table-column prop="paper_title" label="试卷" min-width="180" show-overflow-tooltip />
        <el-table-column prop="batch_name" label="批次" min-width="170" show-overflow-tooltip />
        <el-table-column label="状态" width="105"><template #default="{ row }"><el-tag size="small" :type="row.status >= 2 ? 'success' : 'warning'">{{ statusLabels[row.status] }}</el-tag></template></el-table-column>
        <el-table-column label="得分" width="120"><template #default="{ row }">{{ scoreLabel(row) }}</template></el-table-column>
        <el-table-column prop="correct_count" label="答对" width="75" />
        <el-table-column label="交卷时间" width="175"><template #default="{ row }">{{ formatDate(row.end_at) }}</template></el-table-column>
        <el-table-column label="操作" width="90" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openDetail(row)">查看详情</el-button></template></el-table-column>
      </el-table>
      <el-empty v-if="!rows.length && !loading" description="暂无测评结果" />
      <div class="pagination"><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[10, 20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="load" @current-change="load" /></div>
    </el-card>
    <el-card shadow="never" class="dimension-card">
      <el-tabs v-if="stats.dimensions?.length || batchStats.length || questionStats.length" type="border-card">
        <el-tab-pane label="能力雷达">
          <div class="analysis-layout">
            <div class="radar-wrap"><AssessmentRadar :dimensions="radarDimensions" /></div>
            <div class="dimension-list">
              <div class="analysis-heading"><strong>能力维度</strong><span>按得分率从高到低</span></div>
              <div v-for="row in [...stats.dimensions].sort(dimensionSort)" :key="row.dimension" class="dimension-item">
                <div class="dimension-item__head"><span>{{ row.dimension }}</span><strong>{{ percent(row.accuracy) }}</strong></div>
                <el-progress :percentage="Math.round(dimensionRate(row) * 100)" :show-text="false" :stroke-width="8" />
                <small>{{ row.score }} / {{ row.total_score }} 分 · {{ row.result_count || 0 }} 人 · {{ row.question_count || 0 }} 题</small>
              </div>
            </div>
          </div>
        </el-tab-pane>
        <el-tab-pane label="批次分析">
          <el-table v-if="batchStats.length" :data="batchStats" stripe>
        <el-table-column prop="batch_no" label="批次号" min-width="170" />
        <el-table-column prop="batch_name" label="批次名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="total_results" label="应测" width="75" />
        <el-table-column prop="completed_results" label="已完成" width="85" />
        <el-table-column label="完成率" width="90"><template #default="{ row }">{{ percent(row.completion_rate) }}</template></el-table-column>
        <el-table-column prop="pass_count" label="合格人数" width="90" />
        <el-table-column label="合格率" width="90"><template #default="{ row }">{{ percent(row.pass_rate) }}</template></el-table-column>
        <el-table-column prop="average_score" label="平均分" width="90" />
          </el-table>
          <el-empty v-else description="暂无批次统计" />
        </el-tab-pane>
        <el-tab-pane label="题目分析">
          <el-table v-if="questionStats.length" :data="questionStats" stripe>
        <el-table-column label="题目" min-width="300" show-overflow-tooltip><template #default="{ row }">{{ questionLabel(row) }}</template></el-table-column>
        <el-table-column prop="dimension" label="能力维度" width="120" />
        <el-table-column prop="attempt_count" label="作答次数" width="90" />
        <el-table-column prop="answered_count" label="有答案" width="80" />
        <el-table-column prop="correct_count" label="答对次数" width="90" />
        <el-table-column label="正确率" width="85"><template #default="{ row }">{{ percent(row.accuracy) }}</template></el-table-column>
        <el-table-column prop="average_score" label="平均得分" width="90" />
          </el-table>
          <el-empty v-else description="暂无题目统计" />
        </el-tab-pane>
      </el-tabs>
      <el-empty v-else description="当前筛选条件下暂无分析数据" />
    </el-card>
    <ResultDetailDrawer v-model="drawerVisible" :result-id="selectedResultId" />
  </div>
</template>

<style scoped>
.stat-row { margin-bottom: 14px; }
.table-card, .dimension-card { margin-top: 14px; }
.filters { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; }
.filters :deep(.el-input-number) { width: 130px; }
.pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
.analysis-layout { display: grid; grid-template-columns: minmax(360px, 1.1fr) minmax(280px, .9fr); gap: 26px; align-items: center; }
.radar-wrap { min-width: 0; }
.dimension-list { display: flex; flex-direction: column; gap: 16px; }
.analysis-heading { display: flex; justify-content: space-between; color: #172033; }
.analysis-heading span, .dimension-item small { color: #98a2b3; font-size: 12px; }
.dimension-item__head { display: flex; justify-content: space-between; margin-bottom: 7px; color: #344054; }
.dimension-item__head strong { color: #2563eb; }
@media (max-width: 800px) { .analysis-layout { grid-template-columns: 1fr; gap: 8px; } }
</style>
