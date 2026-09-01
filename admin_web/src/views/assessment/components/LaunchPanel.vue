<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { launchAssessment, listPapers, listResults } from '@/api/assessment'
import { listUsers } from '@/api/user'

const papers = ref([])
const users = ref([])
const records = ref([])
const loading = ref(false)
const form = reactive({ paper_id: null, talent_ids: [], batch_name: '', started_at: '', deadline_at: '' })
const statusLabels = { 0: '未答', 1: '答题中', 2: '已交卷', 3: '报告已生成' }

async function load() {
  loading.value = true
  try {
    const [paperRes, userRes, resultRes] = await Promise.all([
      listPapers({ page: 1, page_size: 200, status: 1 }),
      listUsers({ page: 1, page_size: 200, status: 1 }),
      listResults({ page: 1, page_size: 50 })
    ])
    papers.value = paperRes.data.items
    users.value = userRes.data.items
    records.value = resultRes.data.items
  } finally { loading.value = false }
}
async function submit() {
  if (!form.paper_id || !form.talent_ids.length) return ElMessage.warning('请选择试卷和测试人员')
  const paper = papers.value.find((item) => item.id === form.paper_id)
  const started = form.started_at || new Date().toISOString().slice(0, 19)
  const deadline = form.deadline_at || new Date(Date.now() + paper.duration * 60000).toISOString().slice(0, 19)
  if (new Date(deadline) <= new Date(started)) return ElMessage.warning('截止时间必须晚于开始时间')
  await launchAssessment({ paper_id: form.paper_id, talent_ids: form.talent_ids, started_at: started, deadline_at: deadline })
  ElMessage.success('测评已发起')
  Object.assign(form, { paper_id: null, talent_ids: [], batch_name: '', started_at: '', deadline_at: '' })
  await load()
}
function formatDate(value) { return value ? new Date(value).toLocaleString() : '—' }
onMounted(load)
</script>

<template>
  <el-row :gutter="18">
    <el-col :xs="24" :lg="9"><el-card shadow="never"><template #header>发起新测评</template><el-form label-width="90px"><el-form-item label="试卷"><el-select v-model="form.paper_id" filterable style="width:100%"><el-option v-for="paper in papers" :key="paper.id" :label="`${paper.title}（${paper.total_score}分）`" :value="paper.id" /></el-select></el-form-item><el-form-item label="批次名称"><el-input v-model="form.batch_name" maxlength="128" show-word-limit placeholder="可选，默认按试卷和时间生成" /></el-form-item><el-form-item label="测试人员"><el-select v-model="form.talent_ids" multiple filterable style="width:100%"><el-option v-for="user in users" :key="user.id" :label="`${user.nickname || user.username}（${user.username}）`" :value="user.id" /></el-select></el-form-item><el-form-item label="开始时间"><el-date-picker v-model="form.started_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="立即开始" style="width:100%" /></el-form-item><el-form-item label="截止时间"><el-date-picker v-model="form.deadline_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="按试卷时长计算" style="width:100%" /></el-form-item><el-button type="primary" style="width:100%" @click="submit">发起测评</el-button></el-form></el-card></el-col>
    <el-col :xs="24" :lg="15"><el-card shadow="never"><template #header><div class="card-head"><span>已发起记录</span><el-button link @click="load">刷新</el-button></div></template><el-table :data="records" v-loading="loading" stripe><el-table-column prop="id" label="ID" width="65" /><el-table-column prop="paper_title" label="试卷" min-width="150" show-overflow-tooltip /><el-table-column prop="talent_name" label="人员" width="110" /><el-table-column label="状态" width="100"><template #default="{ row }"><el-tag size="small" :type="row.status >= 2 ? 'success' : 'warning'">{{ statusLabels[row.status] }}</el-tag></template></el-table-column><el-table-column prop="score" label="得分" width="75" /><el-table-column label="截止时间" width="170"><template #default="{ row }">{{ formatDate(row.deadline_at) }}</template></el-table-column></el-table><el-empty v-if="!records.length && !loading" description="暂无发起记录" /></el-card></el-col>
  </el-row>
</template>

<style scoped>
.card-head { display: flex; justify-content: space-between; align-items: center; }
</style>
