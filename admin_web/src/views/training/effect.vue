<script setup>
import { computed, onMounted, ref } from 'vue'
import { Histogram, PieChart, Tickets, TrendCharts, User } from '@element-plus/icons-vue'
import { getTrainingEffects } from '@/api/training'

const loading = ref(false)
const activeChart = ref('category')
const activeTable = ref('ranking')
const summary = ref({
  course_count: 0,
  plan_count: 0,
  learned_hours: 0,
  completed_rate: 0,
  pass_rate: 0,
  avg_progress: 0,
  avg_improvement: 0
})
const categoryHours = ref([])
const statusData = ref([])
const trends = ref([])
const ranking = ref([])
const talentEffects = ref([])

const chartTabs = [
  { key: 'category', label: '分类学时分布', icon: Histogram },
  { key: 'trend', label: '培训趋势', icon: TrendCharts },
  { key: 'status', label: '计划状态分布', icon: PieChart }
]
const tableTabs = [
  { key: 'ranking', label: '课程效果排行', icon: Tickets },
  { key: 'talent', label: '人员培训明细', icon: User }
]

const maxCategoryHours = computed(() => Math.max(...categoryHours.value.map((item) => item.hours), 1))
const maxStatusCount = computed(() => Math.max(...statusData.value.map((item) => item.count), 1))
const maxTrendHours = computed(() => Math.max(...trends.value.map((item) => item.hours), 1))
const maxTrendImprovement = computed(() => Math.max(...trends.value.map((item) => item.improvement), 20))
const activeChartMeta = computed(() => {
  const metaMap = {
    category: { count: `分类 ${categoryHours.value.length} 项`, focus: '当前查看：分类学时分布' },
    trend: { count: `趋势 ${trends.value.length} 个月`, focus: '当前查看：培训趋势' },
    status: { count: `状态 ${statusData.value.length} 类`, focus: '当前查看：计划状态分布' }
  }
  return metaMap[activeChart.value] || metaMap.category
})
const activeTableMeta = computed(() => {
  const metaMap = {
    ranking: { count: `课程 ${ranking.value.length} 条`, focus: '当前查看：课程效果排行' },
    talent: { count: `人员 ${talentEffects.value.length} 条`, focus: '当前查看：人员培训明细' }
  }
  return metaMap[activeTable.value] || metaMap.ranking
})

async function load() {
  loading.value = true
  try {
    const res = await getTrainingEffects()
    summary.value = res.data.summary
    categoryHours.value = res.data.category_hours
    statusData.value = res.data.status_data
    trends.value = res.data.trends
    ranking.value = res.data.ranking
    talentEffects.value = res.data.talent_effects
  } finally {
    loading.value = false
  }
}

function percent(value, max) {
  if (!max) return 0
  return Math.round((Number(value) / max) * 100)
}

function trendX(index) {
  if (trends.value.length <= 1) return 36
  return 36 + (index * 468) / (trends.value.length - 1)
}

function trendY(value, max) {
  return 154 - (Number(value) / max) * 108
}

function trendPoints(field, max) {
  return trends.value.map((item, index) => `${trendX(index)},${trendY(item[field], max)}`).join(' ')
}

function statusType(label) {
  return { 已完成: 'success', 进行中: 'primary', 未开始: 'info', 已逾期: 'danger' }[label] || 'info'
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="effect-page">
    <div class="kpi-grid">
      <el-card class="kpi">
        <el-statistic title="课程总数" :value="summary.course_count" />
      </el-card>
      <el-card class="kpi">
        <el-statistic title="学习计划" :value="summary.plan_count" />
      </el-card>
      <el-card class="kpi">
        <el-statistic title="已学学时" :value="summary.learned_hours" suffix="h" />
      </el-card>
      <el-card class="kpi">
        <el-statistic title="计划完成率" :value="summary.completed_rate" suffix="%" />
      </el-card>
      <el-card class="kpi">
        <el-statistic title="考核通过率" :value="summary.pass_rate" suffix="%" />
      </el-card>
      <el-card class="kpi">
        <el-statistic title="平均能力提升" :value="summary.avg_improvement" suffix="分" />
      </el-card>
    </div>

    <el-card class="switch-card chart-card">
      <template #header>
        <div class="switch-header">
          <div class="switch-actions" role="group" aria-label="切换图表">
            <el-button
              v-for="item in chartTabs"
              :key="item.key"
              :type="activeChart === item.key ? 'primary' : 'default'"
              :plain="activeChart !== item.key"
              @click="activeChart = item.key"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </el-button>
          </div>
          <div class="switch-meta">
            <span>{{ activeChartMeta.count }}</span>
            <span>{{ activeChartMeta.focus }}</span>
          </div>
        </div>
      </template>

      <div class="chart-panel">
        <div v-if="activeChart === 'category'" class="chart-view">
          <div class="panel-title">
            <span>分类学时分布</span>
            <span class="panel-note">按已学学时</span>
          </div>
          <div v-if="categoryHours.length" class="bar-chart">
            <div v-for="item in categoryHours" :key="item.name" class="bar-row">
              <span class="bar-name">{{ item.name }}</span>
              <div class="bar-track">
                <div class="bar-fill teal" :style="{ width: `${percent(item.hours, maxCategoryHours)}%` }" />
              </div>
              <span class="bar-value">{{ item.hours }}h</span>
            </div>
          </div>
          <el-empty v-else description="暂无分类学时数据" />
        </div>

        <div v-else-if="activeChart === 'trend'" class="chart-view trend-panel">
          <div class="panel-title">
            <span>培训趋势</span>
            <span class="panel-note">学时 / 通过率 / 提升分</span>
          </div>
          <template v-if="trends.length">
            <svg class="trend-svg" viewBox="0 0 540 190" role="img" aria-label="培训趋势图">
              <line x1="36" y1="154" x2="508" y2="154" class="axis" />
              <line x1="36" y1="46" x2="36" y2="154" class="axis" />
              <polyline :points="trendPoints('hours', maxTrendHours)" class="trend-line hours" />
              <polyline :points="trendPoints('pass_rate', 100)" class="trend-line pass" />
              <polyline :points="trendPoints('improvement', maxTrendImprovement)" class="trend-line improve" />
              <g v-for="(item, index) in trends" :key="item.month">
                <circle :cx="trendX(index)" :cy="trendY(item.hours, maxTrendHours)" r="3.5" class="dot hours-dot" />
                <circle :cx="trendX(index)" :cy="trendY(item.pass_rate, 100)" r="3.5" class="dot pass-dot" />
                <circle :cx="trendX(index)" :cy="trendY(item.improvement, maxTrendImprovement)" r="3.5" class="dot improve-dot" />
                <text :x="trendX(index)" y="178" text-anchor="middle" class="axis-label">{{ item.month }}</text>
              </g>
            </svg>
            <div class="legend">
              <span><i class="legend-dot hours-bg" />学时</span>
              <span><i class="legend-dot pass-bg" />通过率</span>
              <span><i class="legend-dot improve-bg" />提升分</span>
            </div>
          </template>
          <el-empty v-else description="暂无培训趋势数据" />
        </div>

        <div v-else class="chart-view">
          <div class="panel-title">
            <span>计划状态分布</span>
            <span class="panel-note">共 {{ summary.plan_count }} 个</span>
          </div>
          <div v-if="statusData.length" class="bar-chart">
            <div v-for="item in statusData" :key="item.status" class="bar-row">
              <span class="bar-name">{{ item.name }}</span>
              <div class="bar-track">
                <div class="bar-fill amber" :style="{ width: `${percent(item.count, maxStatusCount)}%` }" />
              </div>
              <span class="bar-value">{{ item.count }}个</span>
            </div>
          </div>
          <el-empty v-else description="暂无计划状态数据" />
        </div>
      </div>
    </el-card>

    <el-card class="switch-card table-card">
      <template #header>
        <div class="switch-header">
          <div class="switch-actions" role="group" aria-label="切换表格">
            <el-button
              v-for="item in tableTabs"
              :key="item.key"
              :type="activeTable === item.key ? 'primary' : 'default'"
              :plain="activeTable !== item.key"
              @click="activeTable = item.key"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </el-button>
          </div>
          <div class="switch-meta">
            <span>{{ activeTableMeta.count }}</span>
            <span>{{ activeTableMeta.focus }}</span>
          </div>
        </div>
      </template>

      <el-table v-if="activeTable === 'ranking'" :data="ranking" stripe>
        <el-table-column prop="title" label="课程名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="90" />
        <el-table-column prop="learner_count" label="学习人数" width="100" />
        <el-table-column prop="learned_hours" label="已学学时" width="100" />
        <el-table-column label="通过率" width="160">
          <template #default="{ row }">
            <el-progress :percentage="row.pass_rate" :stroke-width="8" />
          </template>
        </el-table-column>
      </el-table>

      <el-table v-else :data="talentEffects" stripe>
        <el-table-column prop="talent_name" label="人员" width="100" />
        <el-table-column prop="title" label="学习计划" min-width="240" show-overflow-tooltip />
        <el-table-column label="学习进度" width="160">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :stroke-width="8" />
          </template>
        </el-table-column>
        <el-table-column prop="learned_hours" label="已学学时" width="100" />
        <el-table-column label="考核均分" width="100">
          <template #default="{ row }">{{ row.exam_avg === null ? '-' : row.exam_avg }}</template>
        </el-table-column>
        <el-table-column prop="improvement" label="提升分" width="90" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status_label)" size="small">{{ row.status_label }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.effect-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(150px, 1fr));
  gap: 14px;
}
.kpi {
  min-height: 94px;
}
.switch-card {
  width: 100%;
}
.switch-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.switch-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.switch-actions :deep(.el-button) {
  margin-left: 0;
}
.switch-actions :deep(.el-button > span) {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.switch-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: #909399;
  font-size: 13px;
}
.chart-panel {
  min-height: 258px;
}
.chart-view {
  min-height: 258px;
}
.panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  color: #303133;
  font-size: 14px;
  font-weight: 600;
}
.panel-note {
  color: #909399;
  font-size: 13px;
  font-weight: 400;
  white-space: nowrap;
}
.bar-chart {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-top: 8px;
  max-width: 760px;
}
.bar-row {
  display: grid;
  grid-template-columns: 96px minmax(160px, 1fr) 72px;
  gap: 10px;
  align-items: center;
}
.bar-name,
.bar-value {
  color: #606266;
  font-size: 13px;
}
.bar-value {
  text-align: right;
}
.bar-track {
  height: 12px;
  overflow: hidden;
  background: #eef1f5;
  border-radius: 8px;
}
.bar-fill {
  height: 100%;
  border-radius: 8px;
}
.teal {
  background: #14b8a6;
}
.amber {
  background: #f59e0b;
}
.trend-panel {
  overflow: hidden;
}
.trend-svg {
  display: block;
  width: 100%;
  height: 220px;
}
.axis {
  stroke: #dcdfe6;
  stroke-width: 1;
}
.axis-label {
  fill: #909399;
  font-size: 12px;
}
.trend-line {
  fill: none;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.hours {
  stroke: #2563eb;
}
.pass {
  stroke: #16a34a;
}
.improve {
  stroke: #f97316;
}
.dot {
  stroke: #fff;
  stroke-width: 1.5;
}
.hours-dot,
.hours-bg {
  background: #2563eb;
  fill: #2563eb;
}
.pass-dot,
.pass-bg {
  background: #16a34a;
  fill: #16a34a;
}
.improve-dot,
.improve-bg {
  background: #f97316;
  fill: #f97316;
}
.legend {
  display: flex;
  gap: 18px;
  align-items: center;
  color: #606266;
  font-size: 13px;
}
.legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.legend-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
}
@media (max-width: 1280px) {
  .kpi-grid {
    grid-template-columns: repeat(3, minmax(150px, 1fr));
  }
}
@media (max-width: 760px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }
  .switch-header {
    align-items: flex-start;
    flex-direction: column;
  }
  .switch-actions,
  .switch-actions :deep(.el-button) {
    width: 100%;
  }
  .switch-actions :deep(.el-button) {
    justify-content: center;
  }
  .switch-meta {
    gap: 6px;
    flex-direction: column;
  }
  .bar-row {
    grid-template-columns: 70px minmax(110px, 1fr) 58px;
  }
}
</style>
