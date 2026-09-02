<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { getStatistics } from '@/api/assessment'
import QuestionBankPanel from './components/QuestionBankPanel.vue'
import PaperPanel from './components/PaperPanel.vue'
import LaunchPanel from './components/LaunchPanel.vue'
import ResultsPanel from './components/ResultsPanel.vue'

const activeTab = ref('banks')
const refreshKey = ref(0)
const overviewLoading = ref(false)
const overview = reactive({ total_results: 0, completed_results: 0, average_score: 0, pass_rate: 0 })
const overviewItems = computed(() => [
  { label: '测评总数', value: overview.total_results, suffix: '场' },
  { label: '已完成', value: overview.completed_results, suffix: '场' },
  { label: '平均分', value: Number(overview.average_score || 0).toFixed(2), suffix: '分' },
  { label: '合格率', value: `${Math.round(Number(overview.pass_rate || 0) * 100)}%`, suffix: '' },
])
function refreshAll() {
  refreshKey.value += 1
  loadOverview()
}
async function loadOverview() {
  overviewLoading.value = true
  try { Object.assign(overview, (await getStatistics({})).data || {}) } finally { overviewLoading.value = false }
}
onMounted(loadOverview)
</script>

<template>
  <div class="assessment-page">
    <div class="page-head">
      <div>
        <h2>智能测评</h2>
        <p>题库、试卷、测评任务与能力报告统一管理</p>
      </div>
      <el-button @click="refreshAll">刷新数据</el-button>
    </div>

    <el-row :gutter="14" class="overview-row" v-loading="overviewLoading">
      <el-col v-for="item in overviewItems" :key="item.label" :xs="12" :sm="6">
        <el-card shadow="never" class="overview-card"><div class="overview-label">{{ item.label }}</div><div class="overview-value">{{ item.value }}<small>{{ item.suffix }}</small></div></el-card>
      </el-col>
    </el-row>

    <el-card class="workspace" shadow="never">
      <el-tabs v-model="activeTab" class="assessment-tabs">
        <el-tab-pane label="题库管理" name="banks" lazy><QuestionBankPanel :key="`banks-${refreshKey}`" /></el-tab-pane>
        <el-tab-pane label="组卷管理" name="papers" lazy><PaperPanel :key="`papers-${refreshKey}`" /></el-tab-pane>
        <el-tab-pane label="发起测评" name="launch" lazy><LaunchPanel :key="`launch-${refreshKey}`" /></el-tab-pane>
        <el-tab-pane label="成绩统计" name="results" lazy><ResultsPanel :key="`results-${refreshKey}`" /></el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.assessment-page { min-height: 100%; }
.page-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-head h2 { margin: 0; color: #172033; font-size: 22px; }
.page-head p { margin: 7px 0 0; color: #778196; font-size: 13px; }
.overview-row { margin-bottom: 14px; }
.overview-card { min-height: 92px; }
.overview-label { color: #778196; font-size: 13px; }
.overview-value { color: #172033; font-size: 25px; font-weight: 700; margin-top: 10px; }
.overview-value small { color: #778196; font-size: 12px; font-weight: normal; margin-left: 4px; }
.workspace { border: 0; }
.assessment-tabs :deep(.el-tabs__content) { overflow: visible; }
@media (max-width: 720px) {
  .page-head { align-items: stretch; gap: 12px; flex-direction: column; }
}
</style>
