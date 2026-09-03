<template>
  <div class="dashboard">
    <el-row :gutter="16" v-if="kpis.length">
      <el-col :span="6" v-for="k in kpis" :key="k.key">
        <el-card><el-statistic :title="k.label" :value="k.value" /><div class="delta">{{ k.suffix || '—' }}</div></el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="charts">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center;width:100%">
              <span>增量趋势</span>
              <el-select v-model="trendCompare" size="small" style="width:104px" @change="reloadTrend">
                <el-option label="本期" value="none" />
                <el-option label="同比" value="yoy" />
                <el-option label="环比" value="mom" />
              </el-select>
            </div>
          </template>
          <EChart :option="trendOption" />
        </el-card>
      </el-col>
      <el-col :span="12"><el-card><template #header>状态分布</template><EChart :option="pieOption" /></el-card></el-col>
      <el-col :span="12"><el-card><template #header>部门分布</template><EChart :option="barOption" /></el-card></el-col>
      <el-col :span="12"><el-card><template #header>等级分布</template><EChart :option="levelOption" /></el-card></el-col>
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
const trendCompare = ref('none')

async function load() {
  loading.value = true
  try {
    // 后端 /overview 为全局聚合，不接收筛选参数（方案甲，2026-09-02 移除筛选条）
    const [overviewRes, deptRes, trendRes] = await Promise.all([
      getOverview(),
      getDistribution({ dimension: 'dept' }),
      getTrend({ metric: 'talent_new', days: 30, compare: trendCompare.value }),
    ])
    const ov = overviewRes.data
    kpis.value = [
      { key: 'talent_total', label: '人才总量', value: ov.talent_total ?? 0 },
      { key: 'assess_pass_rate', label: '测评合格率', value: Math.round((ov.assess_pass_rate ?? 0) * 100), suffix: '%' },
      { key: 'training_completion_rate', label: '培训完成率', value: Math.round((ov.training_completion_rate ?? 0) * 100), suffix: '%' },
      { key: 'match_avg_score', label: '平均匹配度', value: ov.match_avg_score ?? 0 },
    ]
    const degree = Object.entries(ov.talent_by_degree || {}).map(([name, value]) => ({ name, value }))
    // 等级分布（柱图数据源）：来自 overview.talent_by_level（等级 P5/P6/P7…）
    const level = Object.entries(ov.talent_by_level || {}).map(([name, value]) => ({ name, value }))
    // 部门分布（柱图数据源）：走后端 /distribution?dimension=dept（真实部门，2026-09-02 修正原误用学历数据）
    const dept = deptRes.data || []
    // 趋势折线（近30天新增，含同比/环比对比，层B 完整闭环）
    const trend = trendRes.data || {}
    charts.value = { degree, level, dept, trend_line: trend }
  } catch { ElMessage.error('看板加载失败') } finally { loading.value = false }
}


const trendOption = computed(() => {
  const trend = charts.value.trend_line || {}
  const current = trend.current || []
  const previous = trend.previous || null
  const series = [{
    name: '本期', type: 'line', smooth: true,
    data: current.map(i => i.count), areaStyle: { opacity: 0.12 }
  }]
  if (previous) {
    series.push({
      name: '上期', type: 'line', smooth: true,
      data: previous.map(i => i.count),
      lineStyle: { type: 'dashed' }, itemStyle: { color: '#909399' }
    })
  }
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0, data: previous ? ['本期', '上期'] : ['本期'] },
    xAxis: { type: 'category', data: current.map(i => i.date) },
    yAxis: { type: 'value' },
    series
  }
})
async function reloadTrend() {
  try {
    const trendRes = await getTrend({ metric: 'talent_new', days: 30, compare: trendCompare.value })
    charts.value = { ...charts.value, trend_line: trendRes.data || {} }
  } catch { ElMessage.error('趋势加载失败') }
}
const pieOption = computed(() => ({
  tooltip: { trigger: 'item' }, legend: { bottom: 0 },
  series: [{ type: 'pie', radius: '55%', data: charts.value.degree || [] }]
}))
// 部门分布柱图：数据源为真实部门 dept（不再复用学历 degree，2026-09-02）
const barOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { bottom: 80 },
  xAxis: {
    type: 'category',
    data: (charts.value.dept || []).map(i => i.name),
    axisLabel: { interval: 0, rotate: 30 }   // 强制全显 + 倾斜避免重叠隐藏
  },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: (charts.value.dept || []).map(i => i.value), name: '人数' }]
}))
// 等级分布柱图：数据源 talent_by_level（等级如 P5/P6/P7…）
const levelOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { bottom: 80 },
  xAxis: {
    type: 'category',
    data: (charts.value.level || []).map(i => i.name),
    axisLabel: { interval: 0, rotate: 30 }   // 强制全显 + 倾斜避免重叠隐藏
  },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: (charts.value.level || []).map(i => i.value), name: '人数' }]
}))
onMounted(load)
</script>

<style scoped>
.dashboard { padding: 16px; }
.charts { margin-top: 16px; } .delta { color: #909399; font-size: 12px; }
</style>
