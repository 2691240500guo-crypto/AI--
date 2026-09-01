<script setup>
import { computed, onMounted, ref } from 'vue'
import { getTrainingEffects } from '@/api/training'

const loading = ref(false)
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

const maxCategoryHours = computed(() => Math.max(...categoryHours.value.map((item) => item.hours), 1))
const maxStatusCount = computed(() => Math.max(...statusData.value.map((item) => item.count), 1))
const maxTrendHours = computed(() => Math.max(...trends.value.map((item) => item.hours), 1))
const maxTrendImprovement = computed(() => Math.max(...trends.value.map((item) => item.improvement), 20))

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

    <div class="chart-grid">
      <el-card class="panel">
        <template #header>分类学时分布</template>
        <div class="bar-chart">
          <div v-for="item in categoryHours" :key="item.name" class="bar-row">
            <span class="bar-name">{{ item.name }}</span>
            <div class="bar-track">
              <div class="bar-fill teal" :style="{ width: `${percent(item.hours, maxCategoryHours)}%` }" />
            </div>
            <span class="bar-value">{{ item.hours }}h</span>
          </div>
        </div>
      </el-card>

      <el-card class="panel">
        <template #header>计划状态分布</template>
        <div class="bar-chart">
          <div v-for="item in statusData" :key="item.status" class="bar-row">
            <span class="bar-name">{{ item.name }}</span>
            <div class="bar-track">
              <div class="bar-fill amber" :style="{ width: `${percent(item.count, maxStatusCount)}%` }" />
            </div>
            <span class="bar-value">{{ item.count }}个</span>
          </div>
        </div>
      </el-card>

      <el-card class="panel trend-panel">
        <template #header>培训趋势</template>
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
      </el-card>
    </div>

    <el-card class="table-card">
      <template #header>课程效果排行</template>
      <el-table :data="ranking" stripe>
        <el-table-column prop="title" label="课程名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="90" />
        <el-table-column prop="learner_count" label="学习人数" width="100" />
        <el-table-column prop="learned_hours" label="已学学时" width="100" />
        <el-table-column label="通过率" width="140">
          <template #default="{ row }">
            <el-progress :percentage="row.pass_rate" :stroke-width="8" />
          </template>
        </el-table-column>
        <el-table-column prop="rating" label="课程评分" width="100" />
      </el-table>
    </el-card>

    <el-card class="table-card">
      <template #header>人员培训效果明细</template>
      <el-table :data="talentEffects" stripe>
        <el-table-column prop="talent_name" label="人员" width="100" />
        <el-table-column prop="dept" label="部门" width="130" show-overflow-tooltip />
        <el-table-column prop="title" label="学习计划" min-width="220" show-overflow-tooltip />
        <el-table-column label="学习进度" width="150">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :stroke-width="8" />
          </template>
        </el-table-column>
        <el-table-column prop="learned_hours" label="已学学时" width="100" />
        <el-table-column label="考核均分" width="100">
          <template #default="{ row }">{{ row.exam_avg === null ? '-' : row.exam_avg }}</template>
        </el-table-column>
        <el-table-column prop="improvement" label="提升分" width="90" />
        <el-table-column prop="status_label" label="状态" width="90" />
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
.chart-grid {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(260px, 1fr) minmax(420px, 1.4fr);
  gap: 16px;
}
.panel {
  min-height: 276px;
}
.bar-chart {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-top: 8px;
}
.bar-row {
  display: grid;
  grid-template-columns: 72px minmax(120px, 1fr) 58px;
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
  height: 210px;
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
.table-card {
  width: 100%;
}
@media (max-width: 1280px) {
  .kpi-grid {
    grid-template-columns: repeat(3, minmax(150px, 1fr));
  }
  .chart-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 760px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
