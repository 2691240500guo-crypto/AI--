<template>
  <div class="dashboard">
    <el-form inline class="filter-bar">
      <el-form-item label="时间">
        <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD"
          start-placeholder="开始" end-placeholder="结束" @change="load" />
      </el-form-item>
      <el-form-item label="部门">
        <el-select v-model="deptId" placeholder="全部" clearable @change="load" style="width:160px">
          <el-option v-for="d in deptOptions" :key="d.value" :label="d.label" :value="d.value" />
        </el-select>
      </el-form-item>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </el-form>

    <el-row :gutter="16" v-if="kpis.length">
      <el-col :span="6" v-for="k in kpis" :key="k.key">
        <el-card><el-statistic :title="k.label" :value="k.value" /><div class="delta">{{ k.suffix || '—' }}</div></el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="charts">
      <el-col :span="12"><el-card><template #header>趋势</template><EChart :option="trendOption" /></el-card></el-col>
      <el-col :span="12"><el-card><template #header>状态分布</template><EChart :option="pieOption" /></el-card></el-col>
      <el-col :span="12"><el-card><template #header>部门分布</template><EChart :option="barOption" /></el-card></el-col>
      <el-col :span="12"><el-card><template #header>能力维度</template><EChart :option="radarOption" /></el-card></el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import EChart from '@/components/EChart.vue'
import { getOverview, getTrend, getDistribution } from '@/api/analytics.js'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const kpis = ref([])
const charts = ref({})
const dateRange = ref(null)
const deptId = ref(null)
const deptOptions = ref([{ value: 1, label: '研发部' }, { value: 2, label: '产品部' }])

async function load() {
  loading.value = true
  try {
    const p = {}
    if (dateRange.value) { p.from = dateRange.value[0]; p.to = dateRange.value[1] }
    if (deptId.value) p.dept_id = deptId.value
    const ov = (await getOverview(p)).data
    kpis.value = [
      { key: 'talent_total', label: '人才总量', value: ov.talent_total ?? 0 },
      { key: 'assess_pass_rate', label: '测评合格率', value: Math.round((ov.assess_pass_rate ?? 0) * 100), suffix: '%' },
      { key: 'training_completion_rate', label: '培训完成率', value: Math.round((ov.training_completion_rate ?? 0) * 100), suffix: '%' },
      { key: 'match_avg_score', label: '平均匹配度', value: ov.match_avg_score ?? 0 },
    ]
    const degree = Object.entries(ov.talent_by_degree || {}).map(([name, value]) => ({ name, value }))
    const trend = (await getTrend({ metric: 'talent_new', days: 30 })).data || []
    const dist = (await getDistribution({ dimension: 'degree' })).data || []
    charts.value = { degree, trend_line: trend, dist_items: dist, score_radar: [] }
  } catch { ElMessage.error('看板加载失败') } finally { loading.value = false }
}


const trendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: (charts.value.trend_line || []).map(i => i.date) },
  yAxis: { type: 'value' },
  series: [{ type: 'line', smooth: true, data: (charts.value.trend_line || []).map(i => i.count) }]
}))
const pieOption = computed(() => ({
  tooltip: { trigger: 'item' }, legend: { bottom: 0 },
  series: [{ type: 'pie', radius: '55%', data: charts.value.degree || [] }]
}))
const barOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: (charts.value.degree || []).map(i => i.name) },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: (charts.value.degree || []).map(i => i.value) }]
}))
const radarOption = computed(() => {
  const r = charts.value.score_radar || []
  return {
    tooltip: {},
    radar: { indicator: r.map(i => ({ name: i.indicator, max: i.max })) },
    series: [{ type: 'radar', data: [{ value: r.map(i => i.value), name: '综合' }] }]
  }
})
onMounted(load)
</script>

<style scoped>
.dashboard { padding: 16px; } .filter-bar { margin-bottom: 16px; }
.charts { margin-top: 16px; } .delta { color: #909399; font-size: 12px; }
</style>