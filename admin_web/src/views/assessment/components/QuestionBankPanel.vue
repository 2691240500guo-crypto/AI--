<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createBank, createQuestion, deleteBank, deleteQuestion, listBanks, listQuestions,
  updateBank, updateQuestion
} from '@/api/assessment'
import QuestionImportDialog from './QuestionImportDialog.vue'

const banks = ref([])
const selectedBank = ref(null)
const questions = ref([])
const loading = ref(false)
const totalQuestions = ref(0)
const filters = reactive({ type: '', dimension: '', difficulty: null, status: null })
const bankDialog = reactive({ visible: false, editing: false })
const questionDialog = reactive({ visible: false, editing: false })
const importVisible = ref(false)
const bankForm = reactive({ id: null, name: '', description: '', status: 1 })
const questionForm = reactive({
  id: null, bank_id: null, type: 'single', content: '', optionsText: '', answerText: '',
  dimension: '', difficulty: 1, score: 10, status: 1
})
const typeLabels = { single: '单选', multi: '多选', judge: '判断' }
const selectedQuestionCount = computed(() => totalQuestions.value)

async function loadBanks() {
  const res = await listBanks({ page: 1, page_size: 200 })
  banks.value = res.data.items
  if (!selectedBank.value && banks.value.length) selectBank(banks.value[0])
  if (selectedBank.value) {
    const fresh = banks.value.find((item) => item.id === selectedBank.value.id)
    if (fresh) selectBank(fresh)
  }
}
async function selectBank(bank) {
  selectedBank.value = bank
  await loadQuestions()
}
async function loadQuestions() {
  if (!selectedBank.value) return
  loading.value = true
  try {
    const res = await listQuestions({ bank_id: selectedBank.value.id, type: filters.type || undefined, dimension: filters.dimension.trim() || undefined, difficulty: filters.difficulty || undefined, status: filters.status === null ? undefined : filters.status, page: 1, page_size: 200 })
    questions.value = res.data.items || []
    totalQuestions.value = res.data.meta?.total || 0
  } finally { loading.value = false }
}
function resetFilters() {
  Object.assign(filters, { type: '', dimension: '', difficulty: null, status: null })
  loadQuestions()
}
function openBank(bank = null) {
  Object.assign(bankForm, bank ? bank : { id: null, name: '', description: '', status: 1 })
  bankDialog.editing = Boolean(bank)
  bankDialog.visible = true
}
async function saveBank() {
  if (!bankForm.name.trim()) return ElMessage.warning('请输入题库名称')
  if (bankForm.id) await updateBank(bankForm.id, bankForm)
  else await createBank(bankForm)
  ElMessage.success('题库已保存')
  bankDialog.visible = false
  await loadBanks()
}
async function removeBank(bank) {
  await ElMessageBox.confirm(`确定删除题库「${bank.name}」？`, '删除确认', { type: 'warning' })
  await deleteBank(bank.id)
  ElMessage.success('题库已删除')
  selectedBank.value = null
  questions.value = []
  totalQuestions.value = 0
  await loadBanks()
}
function openQuestion(question = null) {
  if (!selectedBank.value) return ElMessage.warning('请先选择题库')
  Object.assign(questionForm, question ? {
    id: question.id, bank_id: question.bank_id, type: question.type, content: question.content,
    optionsText: (question.options || []).join('\n'),
    answerText: Array.isArray(question.answer) ? question.answer.join(',') : (question.answer || ''),
    dimension: question.dimension, difficulty: question.difficulty, score: Number(question.score), status: question.status
  } : {
    id: null, bank_id: selectedBank.value.id, type: 'single', content: '', optionsText: '', answerText: '',
    dimension: '', difficulty: 1, score: 10, status: 1
  })
  questionDialog.editing = Boolean(question)
  questionDialog.visible = true
}
function questionPayload() {
  const options = questionForm.optionsText.split('\n').map((item) => item.trim()).filter(Boolean)
  const answers = questionForm.answerText.split(',').map((item) => item.trim()).filter(Boolean)
  return {
    bank_id: questionForm.bank_id, type: questionForm.type, content: questionForm.content,
    options: options.length ? options : null,
    answer: questionForm.type === 'multi' ? answers : (questionForm.type === 'single' ? answers : answers[0]),
    dimension: questionForm.dimension, difficulty: questionForm.difficulty,
    score: questionForm.score, status: questionForm.status
  }
}
async function saveQuestion() {
  if (!questionForm.content.trim() || !questionForm.dimension.trim() || !questionForm.answerText.trim()) {
    return ElMessage.warning('请填写题干、能力维度和标准答案')
  }
  const payload = questionPayload()
  if (questionForm.type !== 'judge' && !payload.options?.length) return ElMessage.warning('选择题必须填写选项')
  if (questionForm.id) await updateQuestion(questionForm.id, payload)
  else await createQuestion(payload)
  ElMessage.success('题目已保存')
  questionDialog.visible = false
  await selectBank(selectedBank.value)
}
async function removeQuestion(question) {
  await ElMessageBox.confirm('删除后不可恢复，确定删除这道题目？', '删除确认', { type: 'warning' })
  await deleteQuestion(question.id)
  ElMessage.success('题目已删除')
  await selectBank(selectedBank.value)
}
async function handleImported() {
  await selectBank(selectedBank.value)
}
onMounted(loadBanks)
</script>

<template>
  <div class="bank-layout">
    <aside class="bank-list">
      <div class="section-head"><span>题库</span><el-button size="small" type="primary" @click="openBank()">新增</el-button></div>
      <button v-for="bank in banks" :key="bank.id" class="bank-item" :class="{ active: selectedBank?.id === bank.id }" @click="selectBank(bank)">
        <span>{{ bank.name }}</span><el-tag size="small" :type="bank.status ? 'success' : 'info'">{{ bank.status ? '启用' : '停用' }}</el-tag>
      </button>
      <el-empty v-if="!banks.length" description="暂无题库" :image-size="70" />
    </aside>
    <section class="question-area">
      <div class="section-head">
        <div><strong>{{ selectedBank?.name || '请选择题库' }}</strong><span class="muted">{{ selectedQuestionCount }} 道题目</span></div>
        <div class="actions">
          <el-button v-if="selectedBank" size="small" @click="openBank(selectedBank)">编辑题库</el-button>
          <el-button v-if="selectedBank" size="small" type="danger" plain @click="removeBank(selectedBank)">删除题库</el-button>
          <el-button size="small" :disabled="!selectedBank" @click="importVisible = true">批量导入</el-button>
          <el-button size="small" type="primary" :disabled="!selectedBank" @click="openQuestion()">新增题目</el-button>
        </div>
      </div>
      <div v-if="selectedBank" class="question-filters">
        <el-select v-model="filters.type" clearable placeholder="全部题型" style="width:120px" @change="loadQuestions"><el-option label="单选" value="single" /><el-option label="多选" value="multi" /><el-option label="判断" value="judge" /></el-select>
        <el-input v-model="filters.dimension" clearable placeholder="能力维度" style="width:160px" @keyup.enter="loadQuestions" />
        <el-select v-model="filters.difficulty" clearable placeholder="全部难度" style="width:120px" @change="loadQuestions"><el-option v-for="level in 5" :key="level" :label="`难度 ${level}`" :value="level" /></el-select>
        <el-select v-model="filters.status" clearable placeholder="全部状态" style="width:120px" @change="loadQuestions"><el-option label="启用" :value="1" /><el-option label="停用" :value="0" /></el-select>
        <el-button @click="loadQuestions">筛选</el-button><el-button @click="resetFilters">重置</el-button>
      </div>
      <el-table :data="questions" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="content" label="题干" min-width="260" show-overflow-tooltip />
        <el-table-column label="题型" width="90"><template #default="{ row }"><el-tag size="small">{{ typeLabels[row.type] }}</el-tag></template></el-table-column>
        <el-table-column prop="dimension" label="能力维度" width="120" />
        <el-table-column prop="difficulty" label="难度" width="80" />
        <el-table-column prop="score" label="分值" width="80" />
        <el-table-column label="状态" width="80"><template #default="{ row }"><el-tag size="small" :type="row.status ? 'success' : 'info'">{{ row.status ? '启用' : '停用' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="130" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openQuestion(row)">编辑</el-button><el-button link type="danger" @click="removeQuestion(row)">删除</el-button></template></el-table-column>
      </el-table>
      <el-empty v-if="selectedBank && !questions.length && !loading" description="题库暂无题目" />
    </section>
  </div>

  <el-dialog v-model="bankDialog.visible" :title="bankDialog.editing ? '编辑题库' : '新增题库'" width="480px">
    <el-form label-width="80px"><el-form-item label="名称"><el-input v-model="bankForm.name" /></el-form-item><el-form-item label="描述"><el-input v-model="bankForm.description" type="textarea" :rows="3" /></el-form-item><el-form-item v-if="bankDialog.editing" label="状态"><el-switch v-model="bankForm.status" :active-value="1" :inactive-value="0" /></el-form-item></el-form>
    <template #footer><el-button @click="bankDialog.visible=false">取消</el-button><el-button type="primary" @click="saveBank">保存</el-button></template>
  </el-dialog>
  <el-dialog v-model="questionDialog.visible" :title="questionDialog.editing ? '编辑题目' : '新增题目'" width="620px">
    <el-form label-width="90px"><el-form-item label="题型"><el-radio-group v-model="questionForm.type"><el-radio-button label="single">单选</el-radio-button><el-radio-button label="multi">多选</el-radio-button><el-radio-button label="judge">判断</el-radio-button></el-radio-group></el-form-item><el-form-item label="题干"><el-input v-model="questionForm.content" type="textarea" :rows="3" /></el-form-item><el-form-item v-if="questionForm.type !== 'judge'" label="选项"><el-input v-model="questionForm.optionsText" type="textarea" :rows="4" placeholder="每行一个选项" /></el-form-item><el-form-item label="标准答案"><el-input v-model="questionForm.answerText" :placeholder="questionForm.type === 'multi' ? '多个答案用英文逗号分隔' : '填写完整答案文本'" /></el-form-item><el-form-item label="能力维度"><el-input v-model="questionForm.dimension" placeholder="如：项目管理" /></el-form-item><el-form-item label="难度/分值"><el-input-number v-model="questionForm.difficulty" :min="1" :max="5" /><el-input-number v-model="questionForm.score" :min="0.01" :precision="2" style="margin-left:12px" /></el-form-item><el-form-item label="状态"><el-switch v-model="questionForm.status" :active-value="1" :inactive-value="0" /></el-form-item></el-form>
    <template #footer><el-button @click="questionDialog.visible=false">取消</el-button><el-button type="primary" @click="saveQuestion">保存</el-button></template>
  </el-dialog>
  <QuestionImportDialog v-model="importVisible" :bank="selectedBank" @imported="handleImported" />
</template>

<style scoped>
.bank-layout { display: grid; grid-template-columns: 230px minmax(0, 1fr); gap: 20px; }
.bank-list { border-right: 1px solid #edf0f5; padding-right: 16px; }
.section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.bank-item { width: 100%; display: flex; justify-content: space-between; align-items: center; border: 1px solid transparent; background: transparent; color: #303b50; padding: 10px; border-radius: 6px; cursor: pointer; text-align: left; margin-bottom: 6px; }
.bank-item:hover { background: #f5f7fa; }.bank-item.active { color: #2563eb; background: #eef4ff; border-color: #cfe0ff; }
.question-area { min-width: 0; }.question-filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }.actions { display: flex; gap: 8px; }.muted { color: #98a2b3; margin-left: 10px; font-size: 12px; }
@media (max-width: 760px) { .bank-layout { grid-template-columns: 1fr; }.bank-list { border-right: 0; border-bottom: 1px solid #edf0f5; padding: 0 0 12px; }.bank-item { display: inline-flex; width: auto; margin-right: 6px; gap: 10px; } .actions { flex-wrap: wrap; } }
</style>
