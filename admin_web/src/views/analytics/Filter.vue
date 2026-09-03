<template>
  <el-row :gutter="16" class="filter-page">
    <el-col :span="8">
      <el-card title="筛选条件">
        <el-form label-width="80px">
          <el-form-item label="部门">
            <el-select v-model="sel.dept_id" clearable placeholder="全部" style="width:100%">
              <el-option v-for="d in deptOptions" :key="d.value" :label="d.label" :value="d.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="岗位">
            <el-input v-model="sel.position" clearable placeholder="模糊匹配" style="width:100%" />
          </el-form-item>
          <el-form-item label="等级">
            <el-select v-model="sel.level" clearable placeholder="全部" style="width:100%">
              <el-option v-for="l in levelOptions" :key="l.value" :label="l.label" :value="l.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="时间">
            <el-date-picker v-model="sel.dateRange" type="daterange" value-format="YYYY-MM-DD" style="width:100%" />
          </el-form-item>
          <el-form-item label="对比">
            <el-radio-group v-model="sel.compare">
              <el-radio value="none">不对比</el-radio>
              <el-radio value="yoy">同比</el-radio>
              <el-radio value="mom">环比</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="指标">
            <el-select v-model="sel.metric" style="width:100%">
              <el-option v-for="m in metricOptions" :key="m.value" :label="m.label" :value="m.value" />
            </el-select>
          </el-form-item>
          <el-button type="primary" :loading="loading" @click="run">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form>
      </el-card>
    </el-col>

    <el-col :span="16">
      <el-card title="对比结果">
        <el-alert v-if="isGlobalMetric" type="info" :closable="false" style="margin-bottom:12px"
          title="该指标为全局口径：部门/岗位/等级筛选暂不生效（跨域部门归属待统一）；时间窗口与同比/环比可正常使用" />
        <el-descriptions :column="1" border v-loading="loading">
          <el-descriptions-item label="指标">{{ metricLabel }}</el-descriptions-item>
          <el-descriptions-item label="本期值">{{ fmtValue(result.current) }}</el-descriptions-item>
          <el-descriptions-item label="对比期值">{{ fmtValue(result.previous) }}</el-descriptions-item>
          <el-descriptions-item label="变化率">
            {{ result.change_rate == null ? '—' : (result.change_rate * 100).toFixed(1) + '%' }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getDimFilter } from '@/api/analytics'
import { listDepts } from '@/api/dept'
import { ElMessage } from 'element-plus'

// 部门下拉：从后端 /depts（sys_dept）动态加载，不再硬编码（2026-09-02）
const deptOptions = ref([])
async function loadDepts() {
  try {
    const list = (await listDepts()).data || []
    deptOptions.value = list.filter(d => d.status !== 0).map(d => ({ value: d.id, label: d.name }))
  } catch { /* 拉取失败留空，不阻塞筛选 */ }
}
onMounted(loadDepts)
const levelOptions = [{ value: 'S', label: 'S' }, { value: 'A', label: 'A' }, { value: 'B', label: 'B' }, { value: 'C', label: 'C' }]
// 全局口径指标：后端忽略部门/岗位/等级筛选，但时间窗口 + 同比/环比已支持（方案② 修订 2026-09-03）
const GLOBAL_METRICS = ['assess_pass_rate', 'training_completion_rate', 'match_avg_score']
const metricOptions = [
  { value: 'talent_total', label: '人才总量' },
  { value: 'assess_pass_rate', label: '测评合格率' },
  { value: 'training_completion_rate', label: '培训完成率' },
  { value: 'match_avg_score', label: '平均匹配度' },
]
const metricLabel = computed(() => (metricOptions.find(m => m.value === sel.value.metric) || {}).label || '')
const isGlobalMetric = computed(() => GLOBAL_METRICS.includes(sel.value.metric))

// 本期值/对比期值格式化：合格率、完成率×100 加 %；匹配度保留 1 位小数；人才计数原样
function fmtValue(v) {
  if (v == null) return '—'
  if (sel.value.metric === 'assess_pass_rate' || sel.value.metric === 'training_completion_rate') return (v * 100).toFixed(1) + '%'
  if (sel.value.metric === 'match_avg_score') return Number(v).toFixed(1)
  return v
}

const sel = ref({ dept_id: null, position: '', level: null, dateRange: null, compare: 'none', metric: 'talent_total' })
const result = ref({ current: null, previous: null, change_rate: null })
const loading = ref(false)

async function run() {
  loading.value = true
  try {
    const params = {}
    if (sel.value.dept_id) params.dept_id = sel.value.dept_id
    if (sel.value.position) params.position = sel.value.position
    if (sel.value.level) params.level = sel.value.level
    if (sel.value.dateRange) { params.start_date = sel.value.dateRange[0]; params.end_date = sel.value.dateRange[1] }
    params.compare = sel.value.compare
    params.metric = sel.value.metric
    result.value = (await getDimFilter(params)).data || {}
  } catch { ElMessage.error('查询失败') } finally { loading.value = false }
}
function reset() {
  sel.value = { dept_id: null, position: '', level: null, dateRange: null, compare: 'none', metric: 'talent_total' }
  result.value = { current: null, previous: null, change_rate: null }
}
</script>

<style scoped>.filter-page { padding: 16px; }</style>