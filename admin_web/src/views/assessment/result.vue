<script setup>
import { nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getReport, getResult, listResults } from '@/api/assessment'

const STATUS_MAP = { 0: '未作答', 1: '答题中', 2: '已交卷', 3: '已出报告' }
const STATUS_TYPE = { 0: 'info', 1: 'warning', 2: 'success', 3: 'success' }
const TYPE_MAP = { single: '单选', multi: '多选', judge: '判断' }

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, page_size: 10, status: null })

const detailVisible = ref(false)
const detail = ref(null)
const report = ref(null)
const reportLoading = ref(false)

const radarChart = ref(null)
let radarInstance = null

async function load() {
  loading.value = true
  try {
    const res = await listResults(query)
    rows.value = res.data.items
    total.value = res.data.meta.total
  } finally { loading.value = false }
}

async function openDetail(row) {
  detailVisible.value = true
  detail.value = null
  report.value = null
  if (radarInstance) { radarInstance.dispose(); radarInstance = null }
  const res = await getResult(row.id)
  detail.value = res.data
  if (row.status >= 2) {
    reportLoading.value = true
    try { report.value = (await getReport(row.id)).data } finally { reportLoading.value = false }
  }
  await nextTick()
  renderRadar()
}

function fmtAnswer(row) {
  if (!row.user_answer) return '未作答'
  if (row.question && row.question.type === 'judge') return row.user_answer === 'true' ? '正确' : '错误'
  return row.user_answer
}

function renderRadar() {
  if (!report.value?.radar || !radarChart.value) return
  const entries = Object.entries(report.value.radar)
  if (!entries.length) return
  if (radarInstance) radarInstance.dispose()
  radarInstance = echarts.init(radarChart.value)
  radarInstance.setOption({
    title: { text: '能力雷达图', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'item' },
    radar: {
      indicator: entries.map(([name]) => ({ name, max: 100 })),
      shape: 'polygon',
      radius: '65%',
    },
    series: [{
      type: 'radar',
      data: [{
        value: entries.map(([, v]) => v),
        name: report.value.talent_name || '本次测评',
        areaStyle: { color: 'rgba(37,99,235,.25)' },
        lineStyle: { color: '#2563eb', width: 2 },
        itemStyle: { color: '#2563eb' },
      }],
    }],
  })
}

watch(report, () => nextTick(renderRadar))
onUnmounted(() => { if (radarInstance) radarInstance.dispose() })

function answerText(row) {
  if (!row.question) return ''
  return row.question.answer
}

onMounted(load)
</script>

<template>
  <el-card>
    <div class="bar">
      <el-select v-model="query.status" placeholder="状态" clearable style="width:140px" @change="query.page=1;load()">
        <el-option v-for="(v,k) in STATUS_MAP" :key="k" :label="v" :value="Number(k)" />
      </el-select>
      <el-button type="primary" @click="query.page=1;load()">查询</el-button>
    </div>
    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="批次ID" width="80" />
      <el-table-column prop="talent_id" label="人才ID" width="80" />
      <el-table-column prop="paper_id" label="试卷ID" width="80" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }"><el-tag :type="STATUS_TYPE[row.status]">{{ STATUS_MAP[row.status] }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="score" label="得分" width="80" />
      <el-table-column label="正确率" width="100">
        <template #default="{ row }">{{ row.correct_count }}/{{ row.total_count }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">{{ row.created_at?.replace('T', ' ').slice(0, 19) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button v-if="row.status < 2" link type="warning" @click="$router.push(`/assessment/answer/${row.id}`)">继续作答</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination style="margin-top:14px" layout="total, prev, pager, next" :total="total"
      v-model:current-page="query.page" :page-size="query.page_size" @current-change="load" />
  </el-card>

  <el-drawer v-model="detailVisible" title="测评详情" size="640px">
    <div v-if="detail">
      <el-descriptions :column="2" border style="margin-bottom:16px">
        <el-descriptions-item label="批次ID">{{ detail.id }}</el-descriptions-item>
        <el-descriptions-item label="得分">{{ detail.score }}</el-descriptions-item>
        <el-descriptions-item label="正确">{{ detail.correct_count }}/{{ detail.total_count }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ STATUS_MAP[detail.status] }}</el-descriptions-item>
      </el-descriptions>

      <el-divider content-position="left">作答明细</el-divider>
      <el-table :data="detail.details" size="small" border>
        <el-table-column prop="question_id" label="题号" width="70" />
        <el-table-column label="题干" show-overflow-tooltip>
          <template #default="{ row }">{{ row.question?.content }}</template>
        </el-table-column>
        <el-table-column label="题型" width="70">
          <template #default="{ row }">{{ TYPE_MAP[row.question?.type] }}</template>
        </el-table-column>
        <el-table-column label="我的答案" width="100">
          <template #default="{ row }"><span :style="{ color: row.is_correct ? '#16a34a' : '#dc2626' }">{{ fmtAnswer(row) }}</span></template>
        </el-table-column>
        <el-table-column label="正确答案" width="100">
          <template #default="{ row }">{{ answerText(row) }}</template>
        </el-table-column>
        <el-table-column prop="score" label="得分" width="60" />
      </el-table>

      <template v-if="report">
        <el-divider content-position="left">AI 测评报告</el-divider>
        <div v-loading="reportLoading">
          <div style="margin-bottom:10px">
            <el-tag type="warning" size="large">评级：{{ report.level }}</el-tag>
          </div>
          <div ref="radarChart" style="width:100%;height:320px;"></div>
          <div v-if="report.strengths?.length" style="margin-top:12px">
            <b>优势</b>
            <ul style="padding-left:18px;color:#16a34a"><li v-for="s in report.strengths" :key="s">{{ s }}</li></ul>
          </div>
          <div v-if="report.weaknesses?.length" style="margin-top:8px">
            <b>短板</b>
            <ul style="padding-left:18px;color:#dc2626"><li v-for="w in report.weaknesses" :key="w">{{ w }}</li></ul>
          </div>
          <div v-if="report.summary" style="margin-top:8px;color:#555;line-height:1.6">{{ report.summary }}</div>
        </div>
      </template>
    </div>
  </el-drawer>
</template>

<style scoped>
.bar { display: flex; gap: 10px; margin-bottom: 14px; }
</style>
