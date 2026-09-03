<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getPaper,
  getAgentTask,
  getReport,
  getResult,
  getTrainingLink,
  linkTraining,
  retryTrainingLink,
} from '@/api/assessment'
import AssessmentRadar from './AssessmentRadar.vue'
import { assessmentStatusMeta, trainingStatusMeta } from '../status'

const props = defineProps({ modelValue: Boolean, resultId: { type: Number, default: null } })
const emit = defineEmits(['update:modelValue'])
const loading = ref(false)
const resultDetail = ref(null)
const paper = ref(null)
const report = ref(null)
const trainingLink = ref(null)
const agentTask = ref(null)
const activeTab = ref('detail')
const linking = ref(false)
const errorMessage = ref('')
const reportWarning = ref('')

const questionMap = computed(() => new Map((paper.value?.questions || []).map((question) => [question.question_id, question])))
const detailRows = computed(() => (resultDetail.value?.details || []).map((detail) => ({ ...detail, question: questionMap.value.get(detail.question_id) })))
const reportDimensions = computed(() => [...(report.value?.radar || [])].sort((a, b) => Number(b.rate || 0) - Number(a.rate || 0)))
const trainingStatus = computed(() => trainingStatusMeta(trainingLink.value?.status))
const canRetryTraining = computed(() => ['pending', 'failed'].includes(trainingLink.value?.status))

function close() { emit('update:modelValue', false) }
function formatDate(value) { return value ? new Date(value).toLocaleString() : '—' }
function answerText(value) { return Array.isArray(value) ? value.join('、') || '未作答' : (value ?? '未作答') }
function typeLabel(type) { return type === 'single' ? '单选' : type === 'multi' ? '多选' : '判断' }

async function load() {
  if (!props.resultId) return
  loading.value = true
  errorMessage.value = ''
  reportWarning.value = ''
  resultDetail.value = null
  report.value = null
  trainingLink.value = null
  agentTask.value = null
  activeTab.value = 'detail'
  try {
    const response = await getResult(props.resultId)
    resultDetail.value = response.data
    const result = response.data.result
    const paperResponse = await getPaper(result.paper_id)
    paper.value = paperResponse.data
    if (result.status >= 2) {
      try {
        report.value = (await getReport(props.resultId)).data
        if (result.status === 2) result.status = 3
      } catch (error) {
        report.value = null
        reportWarning.value = error?.message || '报告暂时无法加载'
      }
      if (report.value?.agent_task_id) {
        try { agentTask.value = (await getAgentTask(report.value.agent_task_id)).data } catch { agentTask.value = null }
      }
      if (report.value) {
        try { trainingLink.value = (await getTrainingLink(props.resultId)).data } catch { trainingLink.value = null }
      }
    }
  } catch (error) {
    errorMessage.value = error?.message || '测评详情加载失败，请重试'
  } finally {
    loading.value = false
  }
}

async function ensureTrainingLink() {
  if (!props.resultId || linking.value) return
  linking.value = true
  try {
    trainingLink.value = (await linkTraining(props.resultId)).data
    if (trainingLink.value.status === 'sent') ElMessage.success('培训联动已完成')
    else ElMessage.warning(trainingLink.value.error_message || '培训联动待处理，可稍后重试')
  } catch (error) {
    ElMessage.error(error?.message || '培训联动创建失败，请重试')
  } finally { linking.value = false }
}

async function retryLink() {
  if (!props.resultId || linking.value) return
  linking.value = true
  try {
    trainingLink.value = (await retryTrainingLink(props.resultId)).data
    if (trainingLink.value.status === 'sent') ElMessage.success('培训联动重试成功')
    else ElMessage.warning(trainingLink.value.error_message || '培训联动仍待处理')
  } catch (error) {
    ElMessage.error(error?.message || '培训联动重试失败')
  } finally { linking.value = false }
}

watch(() => [props.modelValue, props.resultId], ([visible]) => { if (visible) load() })
</script>

<template>
  <el-drawer :model-value="modelValue" title="测评结果详情" size="min(900px, 100%)" @close="close">
    <div v-loading="loading" class="drawer-content">
      <div v-if="errorMessage" class="error-state">
        <el-alert :title="errorMessage" type="error" show-icon :closable="false" />
        <el-button type="primary" plain :loading="loading" @click="load">重试加载</el-button>
      </div>
      <template v-if="resultDetail">
        <div class="description-scroll"><el-descriptions :column="2" border class="result-descriptions">
          <el-descriptions-item label="测评人员">{{ resultDetail.result.talent_name || resultDetail.result.talent_id }}</el-descriptions-item>
          <el-descriptions-item label="试卷">{{ resultDetail.result.paper_title || resultDetail.result.paper_id }}</el-descriptions-item>
          <el-descriptions-item label="状态"><el-tag size="small" :type="assessmentStatusMeta(resultDetail.result.status).type">{{ assessmentStatusMeta(resultDetail.result.status).label }}</el-tag></el-descriptions-item>
          <el-descriptions-item label="得分">{{ resultDetail.result.score }} 分</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatDate(resultDetail.result.started_at) }}</el-descriptions-item>
          <el-descriptions-item label="交卷时间">{{ formatDate(resultDetail.result.end_at) }}</el-descriptions-item>
        </el-descriptions></div>
        <div class="result-summary">
          <div class="result-summary__score"><span>本次得分</span><strong>{{ resultDetail.result.score }}</strong><small>/ {{ paper?.total_score || '—' }} 分</small></div>
          <div><span>答对题数</span><strong>{{ resultDetail.result.correct_count }}</strong><small>/ {{ paper?.questions?.length || '—' }} 题</small></div>
          <div><span>报告状态</span><el-tag :type="report ? 'success' : 'info'">{{ report ? '已生成' : '待生成' }}</el-tag></div>
        </div>
        <el-tabs v-model="activeTab" class="detail-tabs">
          <el-tab-pane label="逐题明细" name="detail">
            <div class="table-scroll"><el-table :data="detailRows" stripe class="detail-table">
              <el-table-column type="index" label="#" width="55" />
              <el-table-column label="题目" min-width="240" show-overflow-tooltip><template #default="{ row }">{{ row.question?.content_snapshot || `题目 #${row.question_id}` }}</template></el-table-column>
              <el-table-column label="题型" width="75"><template #default="{ row }">{{ typeLabel(row.question?.type_snapshot) }}</template></el-table-column>
              <el-table-column label="作答" min-width="120"><template #default="{ row }">{{ answerText(row.user_answer) }}</template></el-table-column>
              <el-table-column label="结果" width="75"><template #default="{ row }"><el-tag size="small" :type="row.is_correct ? 'success' : 'danger'">{{ row.is_correct ? '正确' : '错误' }}</el-tag></template></el-table-column>
              <el-table-column prop="score" label="得分" width="75" />
            </el-table></div>
            <el-empty v-if="!detailRows.length" description="暂无判分明细" />
          </el-tab-pane>
          <el-tab-pane label="能力报告" name="report">
            <el-alert v-if="reportWarning" :title="reportWarning" type="warning" show-icon :closable="false" class="report-warning" />
            <template v-if="report && resultDetail.result.status >= 2">
              <div class="report-summary"><span>综合得分率 {{ Math.round(report.overall_rate * 100) }}%</span><el-tag>{{ report.rating }}</el-tag><el-tag type="info">{{ report.source === 'siliconflow' ? '硅基流动分析' : '本地报告' }}</el-tag></div>
              <el-alert v-if="agentTask" :title="`Agent任务 #${agentTask.id}：${agentTask.status}，当前节点：${agentTask.current_node || '—'}`" type="info" :closable="false" />
              <el-alert v-if="report.level_sync_reason" :title="`人才等级同步：${report.level_sync_reason}`" type="warning" :closable="false" />
              <div class="report-analysis">
                <div class="report-radar"><AssessmentRadar :dimensions="report.radar" /></div>
                <div class="report-dimensions">
                  <div v-for="item in reportDimensions" :key="item.dimension" class="report-dimension">
                    <div class="report-dimension__head"><span>{{ item.dimension }}</span><strong>{{ Math.round(Number(item.rate || 0) * 100) }}%</strong></div>
                    <el-progress :percentage="Math.round(Number(item.rate || 0) * 100)" :show-text="false" :stroke-width="8" />
                    <small>{{ item.score }} / {{ item.total_score }} 分 · {{ item.level }}</small>
                  </div>
                </div>
              </div>
              <el-row :gutter="14" class="report-columns">
                <el-col :xs="24" :md="8"><h4>优势</h4><ul><li v-for="item in report.strengths" :key="item">{{ item }}</li></ul></el-col>
                <el-col :xs="24" :md="8"><h4>待提升</h4><ul><li v-for="item in report.weaknesses" :key="item">{{ item }}</li></ul></el-col>
                <el-col :xs="24" :md="8"><h4>建议</h4><ul><li v-for="item in report.recommendations" :key="item">{{ item }}</li></ul></el-col>
              </el-row>
              <el-alert v-if="report.fallback_reason" :title="report.fallback_reason" type="info" :closable="false" />
            </template>
            <el-empty v-else :description="resultDetail.result.status < 2 ? '测评交卷后才能生成报告' : '报告尚未生成'" />
          </el-tab-pane>
          <el-tab-pane label="培训联动" name="training">
            <template v-if="trainingLink && resultDetail.result.status >= 2">
              <el-descriptions :column="1" border>
                <el-descriptions-item label="状态"><el-tag :type="trainingStatus.type">{{ trainingStatus.label }}</el-tag></el-descriptions-item>
                <el-descriptions-item label="薄弱维度">{{ (trainingLink.weak_dimensions || []).join('、') || '—' }}</el-descriptions-item>
                <el-descriptions-item label="重试次数">{{ trainingLink.retry_count }}</el-descriptions-item>
                <el-descriptions-item v-if="trainingLink.error_message" label="错误信息">{{ trainingLink.error_message }}</el-descriptions-item>
              </el-descriptions>
              <div v-if="trainingLink.training_plan_json" class="training-plan">
                <h4>培训计划</h4>
                <p>{{ trainingLink.training_plan_json.title }}</p>
                <ul><li v-for="course in trainingLink.training_plan_json.courses || []" :key="`${course.dimension}-${course.title}`">{{ course.dimension }}：{{ course.title }}（{{ course.priority }}）</li></ul>
              </div>
              <el-button v-if="canRetryTraining" type="primary" :loading="linking" class="training-button" @click="retryLink">重试联动</el-button>
            </template>
            <template v-else-if="resultDetail.result.status >= 2"><el-empty description="尚未创建培训联动" /><el-button type="primary" :loading="linking" @click="ensureTrainingLink">创建培训联动</el-button></template>
            <el-empty v-else description="测评交卷并生成报告后才能联动培训" />
          </el-tab-pane>
        </el-tabs>
      </template>
    </div>
  </el-drawer>
</template>

<style scoped>
.detail-tabs { margin-top: 22px; }
.error-state { display: flex; align-items: center; gap: 12px; }
.error-state :deep(.el-alert) { flex: 1; }
.description-scroll, .table-scroll { max-width: 100%; overflow-x: auto; }
.result-descriptions { min-width: 620px; }
.detail-table { min-width: 680px; }
.report-warning { margin-bottom: 12px; }
.result-summary { display: grid; grid-template-columns: 1.4fr 1fr 1fr; gap: 12px; margin-top: 16px; padding: 16px; background: #f8fafc; border: 1px solid #e4e7ed; border-radius: 6px; }
.result-summary > div { display: flex; align-items: baseline; gap: 7px; color: #667085; }
.result-summary strong { color: #172033; font-size: 21px; }
.result-summary__score strong { color: #2563eb; font-size: 28px; }
.result-summary small { color: #98a2b3; }
.report-analysis { display: grid; grid-template-columns: minmax(380px, 1.2fr) minmax(230px, .8fr); gap: 20px; align-items: center; margin-top: 12px; }
.report-radar { min-width: 0; }
.report-dimensions { display: flex; flex-direction: column; gap: 14px; }
.report-dimension__head { display: flex; justify-content: space-between; color: #344054; margin-bottom: 6px; }
.report-dimension__head strong { color: #2563eb; }
.report-dimension small { color: #98a2b3; font-size: 12px; }
.report-summary { display: flex; align-items: center; gap: 10px; font-size: 16px; font-weight: 600; color: #172033; }
.report-columns h4 { margin: 8px 0; color: #172033; }
.report-columns ul { margin: 0; padding-left: 20px; color: #5d6678; line-height: 2; }
.training-button { margin-top: 18px; }
.training-plan { margin-top: 18px; color: #5d6678; }
.training-plan h4 { margin: 0 0 8px; color: #172033; }
.training-plan p { margin: 0 0 6px; color: #172033; font-weight: 600; }
.training-plan ul { margin: 0; padding-left: 20px; line-height: 1.8; }
@media (max-width: 680px) { .error-state { align-items: stretch; flex-direction: column; }.result-summary, .report-analysis { grid-template-columns: 1fr; }.result-summary > div { justify-content: space-between; }.report-summary { align-items: flex-start; flex-wrap: wrap; } }
</style>
