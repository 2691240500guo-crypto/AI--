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
        <el-descriptions :column="1" border v-loading="loading">
          <el-descriptions-item label="指标">{{ metricLabel }}</el-descriptions-item>
          <el-descriptions-item label="本期值">{{ result.current ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="对比期值">{{ result.previous ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="变化率">
            {{ result.change_rate == null ? '—' : (result.change_rate * 100).toFixed(1) + '%' }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup>
import { ref, computed } from 'vue'
import { getDimFilter } from '@/api/analytics'
import { ElMessage } from 'element-plus'

const deptOptions = [{ value: 1, label: '研发部' }, { value: 2, label: '产品部' }]
const levelOptions = [{ value: 'S', label: 'S' }, { value: 'A', label: 'A' }, { value: 'B', label: 'B' }, { value: 'C', label: 'C' }]
const metricOptions = [
  { value: 'talent_total', label: '人才总量' },
  { value: 'assess_pass_rate', label: '测评合格率' },
  { value: 'training_completion_rate', label: '培训完成率' },
  { value: 'match_avg_score', label: '平均匹配度' },
]
const metricLabel = computed(() => (metricOptions.find(m => m.value === sel.value.metric) || {}).label || '')

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