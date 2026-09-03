<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { launchAssessment, listPapers, listResults } from '@/api/assessment'
import { listTalents } from '@/api/talent'
import { assessmentStatusMeta } from '../status'

const papers = ref([])
const talents = ref([])
const records = ref([])
const loading = ref(false)
const submitting = ref(false)
const errorMessage = ref('')
const form = reactive({ paper_id: null, talent_ids: [], batch_name: '', started_at: '', deadline_at: '' })
const eligibleTalentCount = computed(() => talents.value.filter((talent) => talent.user_id).length)

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    const [paperRes, talentRes, resultRes] = await Promise.all([
      listPapers({ page: 1, page_size: 200, status: 1 }),
      listTalents({ page: 1, page_size: 200, status: 1 }),
      listResults({ page: 1, page_size: 50 }),
    ])
    papers.value = paperRes.data.items || []
    talents.value = talentRes.data.items || []
    records.value = resultRes.data.items || []
  } catch (error) {
    errorMessage.value = error?.message || '发起测评数据加载失败，请重试'
  } finally {
    loading.value = false
  }
}

function talentOptionLabel(talent) {
  const talentName = talent.name || `人才#${talent.id}`
  if (!talent.user_id) return `${talentName}（未关联可用员工账号）`
  const accountName = talent.nickname ? `${talent.nickname} / ${talent.username}` : talent.username
  return `${talentName}（账号：${accountName}，用户#${talent.user_id}）`
}

async function submit() {
  if (submitting.value) return
  if (!form.paper_id || !form.talent_ids.length) return ElMessage.warning('请选择试卷和测试人员')
  const paper = papers.value.find((item) => item.id === form.paper_id)
  if (!paper) return ElMessage.warning('所选试卷已不可用，请刷新后重选')
  const started = form.started_at || new Date().toISOString().slice(0, 19)
  const deadline = form.deadline_at || new Date(Date.now() + paper.duration * 60000).toISOString().slice(0, 19)
  if (new Date(deadline) <= new Date(started)) return ElMessage.warning('截止时间必须晚于开始时间')

  submitting.value = true
  try {
    await launchAssessment({
      paper_id: form.paper_id,
      talent_ids: form.talent_ids,
      batch_name: form.batch_name.trim() || null,
      started_at: started,
      deadline_at: deadline,
    })
    ElMessage.success('测评已发起')
    Object.assign(form, { paper_id: null, talent_ids: [], batch_name: '', started_at: '', deadline_at: '' })
    await load()
  } catch (error) {
    ElMessage.error(error?.message || '测评发起失败，请检查人才账号映射后重试')
  } finally {
    submitting.value = false
  }
}

function formatDate(value) { return value ? new Date(value).toLocaleString() : '—' }
onMounted(load)
</script>

<template>
  <div>
    <div v-if="errorMessage" class="error-state">
      <el-alert :title="errorMessage" type="error" show-icon :closable="false" />
      <el-button type="primary" plain :loading="loading" @click="load">重试</el-button>
    </div>
    <el-row :gutter="18">
      <el-col :xs="24" :lg="9">
        <el-card shadow="never" class="launch-card">
          <template #header><div class="card-head"><span>发起新测评</span><small>{{ eligibleTalentCount }} 份档案可用</small></div></template>
          <el-form label-position="top">
            <el-form-item label="试卷"><el-select v-model="form.paper_id" filterable style="width:100%" placeholder="选择已启用试卷"><el-option v-for="paper in papers" :key="paper.id" :label="`${paper.title}（${paper.total_score}分）`" :value="paper.id" /></el-select></el-form-item>
            <el-form-item label="批次名称"><el-input v-model="form.batch_name" maxlength="128" show-word-limit placeholder="可选，默认按试卷和时间生成" /></el-form-item>
            <el-form-item label="测试人员">
              <el-select v-model="form.talent_ids" multiple filterable clearable collapse-tags collapse-tags-tooltip :max-collapse-tags="2" :teleported="false" style="width:100%" placeholder="按姓名或账号搜索人才">
                <el-option v-for="talent in talents.filter((t) => t.user_id)" :key="talent.id" :label="talentOptionLabel(talent)" :value="talent.id">
                  <div class="talent-option"><strong>{{ talent.name || `人才#${talent.id}` }}</strong><small>账号：{{ talent.nickname || talent.username }} / {{ talent.username }} · 用户#{{ talent.user_id }}</small></div>
                </el-option>
              </el-select>
              <div class="field-tip">提交人才档案 ID；未关联有效员工账号的档案会显示但不可选。</div>
            </el-form-item>
            <el-form-item label="开始时间"><el-date-picker v-model="form.started_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="立即开始" style="width:100%" /></el-form-item>
            <el-form-item label="截止时间"><el-date-picker v-model="form.deadline_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="按试卷时长计算" style="width:100%" /></el-form-item>
            <el-button type="primary" :loading="submitting" :disabled="loading || !eligibleTalentCount" style="width:100%" @click="submit">发起测评</el-button>
          </el-form>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="15">
        <el-card shadow="never" class="records-card">
          <template #header><div class="card-head"><span>已发起记录</span><el-button link :loading="loading" @click="load">刷新</el-button></div></template>
          <div class="table-scroll"><el-table :data="records" v-loading="loading" stripe class="records-table"><el-table-column prop="id" label="ID" width="65" /><el-table-column prop="paper_title" label="试卷" min-width="150" show-overflow-tooltip /><el-table-column prop="talent_name" label="人员" width="110" /><el-table-column label="状态" width="110"><template #default="{ row }"><el-tag size="small" :type="assessmentStatusMeta(row.status).type">{{ assessmentStatusMeta(row.status).label }}</el-tag></template></el-table-column><el-table-column prop="score" label="得分" width="75" /><el-table-column label="截止时间" width="170"><template #default="{ row }">{{ formatDate(row.deadline_at) }}</template></el-table-column></el-table></div>
          <el-empty v-if="!records.length && !loading && !errorMessage" description="暂无发起记录" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.card-head { display: flex; justify-content: space-between; align-items: center; }
.card-head small { color: var(--el-text-color-secondary); font-weight: normal; }
.error-state { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.error-state :deep(.el-alert) { flex: 1; }
.table-scroll { max-width: 100%; overflow-x: auto; }
.records-table { min-width: 670px; }
.field-tip { margin-top: 6px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.talent-option { display: flex; flex-direction: column; gap: 3px; padding: 4px 0; line-height: 1.35; }
.talent-option strong { color: var(--el-text-color-primary); font-weight: 500; }
.talent-option small { color: var(--el-text-color-secondary); }
:deep(.el-select-dropdown__item) { height: auto; min-height: 34px; padding-top: 4px; padding-bottom: 4px; }
@media (max-width: 1199px) { .records-card { margin-top: 16px; } }
@media (max-width: 560px) { .error-state { align-items: stretch; flex-direction: column; } }
</style>
