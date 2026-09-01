<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createCapabilityModel, createPaper, deleteCapabilityModel, deletePaper, getPaper,
  listAssessmentPositions, listBanks, listCapabilityModels, listQuestions, listPapers,
  updateCapabilityModel, updatePaper
} from '@/api/assessment'

const papers = ref([])
const questions = ref([])
const banks = ref([])
const capabilityModels = ref([])
const positions = ref([])
const loading = ref(false)
const dialog = reactive({ visible: false, editing: false, preview: false, models: false, modelForm: false })
const form = reactive({ id: null, title: '', description: '', duration: 60, mode: 'manual', question_ids: [], count: 3, bank_ids: [], types: [], dimensions: '', capability_model_id: null })
const modelForm = reactive({ id: null, name: '', description: '', position_id: null, position_level: null, rules: [] })
const modelEditing = ref(false)
const preview = ref(null)
const typeLabels = { single: '单选', multi: '多选', judge: '判断' }

async function load() {
  loading.value = true
  try {
    const [paperRes, questionRes] = await Promise.all([
      listPapers({ page: 1, page_size: 200 }),
      listQuestions({ page: 1, page_size: 200, status: 1 })
    ])
    papers.value = paperRes.data.items
    questions.value = questionRes.data.items
    await loadModels()
  } finally { loading.value = false }
}
async function loadModels() {
  const [modelRes, positionRes, bankRes] = await Promise.all([
    listCapabilityModels({ page: 1, page_size: 200 }),
    listAssessmentPositions(),
    listBanks({ page: 1, page_size: 200, status: 1 })
  ])
  capabilityModels.value = modelRes.data.items || []
  positions.value = positionRes.data || []
  banks.value = bankRes.data.items || []
}
function openCreate() {
  Object.assign(form, { id: null, title: '', description: '', duration: 60, mode: 'manual', question_ids: [], count: 3, bank_ids: [], types: [], dimensions: '', capability_model_id: null })
  dialog.editing = false
  dialog.visible = true
}
function openEdit(row) {
  Object.assign(form, { id: row.id, title: row.title, description: row.description, duration: row.duration, mode: 'manual', question_ids: [], count: 3, bank_ids: [], types: [], dimensions: '', capability_model_id: null })
  dialog.editing = true
  dialog.visible = true
}
function payload() {
  if (form.mode === 'manual') return { title: form.title, description: form.description, duration: form.duration, question_ids: form.question_ids }
  if (form.mode === 'capability') return { title: form.title, description: form.description, duration: form.duration, capability_model_id: form.capability_model_id }
  return {
    title: form.title, description: form.description, duration: form.duration, question_ids: [],
    random_rule: { count: form.count, bank_ids: form.bank_ids, types: form.types, dimensions: form.dimensions.split(',').map((item) => item.trim()).filter(Boolean) }
  }
}
async function save() {
  if (!form.title.trim()) return ElMessage.warning('请输入试卷标题')
  if (dialog.editing) {
    await updatePaper(form.id, { title: form.title, description: form.description, duration: form.duration })
  } else {
    if (form.mode === 'manual' && !form.question_ids.length) return ElMessage.warning('请至少选择一道题目')
    if (form.mode === 'random' && form.count < 1) return ElMessage.warning('随机题量必须大于 0')
    if (form.mode === 'capability' && !form.capability_model_id) return ElMessage.warning('请选择能力模型')
    await createPaper(payload())
  }
  ElMessage.success('试卷已保存')
  dialog.visible = false
  await load()
}
async function remove(row) {
  await ElMessageBox.confirm(`确定删除试卷「${row.title}」？`, '删除确认', { type: 'warning' })
  await deletePaper(row.id)
  ElMessage.success('试卷已删除')
  await load()
}
async function toggle(row) {
  await updatePaper(row.id, { status: row.status ? 0 : 1 })
  ElMessage.success(row.status ? '试卷已停用' : '试卷已启用')
  await load()
}
async function showPreview(row) {
  preview.value = (await getPaper(row.id)).data
  dialog.preview = true
}
function questionLabel(question) { return `${question.id} · ${typeLabels[question.type]} · ${question.dimension} · ${question.content}` }
function emptyRule() { return { dimension: '', count: 1, bank_ids: [], types: [], difficulties: [] } }
function openModel(model = null) {
  Object.assign(modelForm, model ? {
    id: model.id, name: model.name, description: model.description, position_id: model.position_id,
    position_level: model.position_level, rules: (model.rules || []).map((rule) => ({ ...rule, bank_ids: [...(rule.bank_ids || [])], types: [...(rule.types || [])], difficulties: [...(rule.difficulties || [])] }))
  } : { id: null, name: '', description: '', position_id: null, position_level: null, rules: [emptyRule()] })
  modelEditing.value = Boolean(model)
  dialog.modelForm = true
}
function openModelManager() { dialog.models = true }
function addRule() { modelForm.rules.push(emptyRule()) }
function removeRule(index) {
  if (modelForm.rules.length <= 1) return ElMessage.warning('至少保留一条能力维度规则')
  modelForm.rules.splice(index, 1)
}
async function saveModel() {
  if (!modelForm.name.trim()) return ElMessage.warning('请输入能力模型名称')
  if (modelForm.rules.some((rule) => !rule.dimension.trim() || rule.count < 1)) return ElMessage.warning('请完整填写维度规则')
  const payload = { ...modelForm, rules: modelForm.rules.map((rule) => ({ ...rule, dimension: rule.dimension.trim() })) }
  if (modelEditing.value) await updateCapabilityModel(modelForm.id, payload)
  else await createCapabilityModel(payload)
  ElMessage.success('能力模型已保存')
  dialog.modelForm = false
  await loadModels()
}
async function removeModel(model) {
  await ElMessageBox.confirm(`确定删除能力模型「${model.name}」？`, '删除确认', { type: 'warning' })
  await deleteCapabilityModel(model.id)
  ElMessage.success('能力模型已删除')
  await loadModels()
}
async function toggleModel(model) {
  await updateCapabilityModel(model.id, { status: model.status ? 0 : 1 })
  ElMessage.success(model.status ? '能力模型已停用' : '能力模型已启用')
  await loadModels()
}
onMounted(load)
</script>

<template>
  <div class="toolbar"><el-button type="primary" @click="openCreate">新建试卷</el-button><el-button @click="openModelManager">能力模型</el-button><span class="tip">试卷题目在创建时固化快照，后续修改题库不影响历史结果</span></div>
  <el-table :data="papers" v-loading="loading" stripe>
    <el-table-column prop="id" label="ID" width="70" /><el-table-column prop="title" label="试卷名称" min-width="180" /><el-table-column label="组卷方式" width="100"><template #default="{ row }"><el-tag size="small">{{ { manual: '手动', random: '随机', capability: '能力模型' }[row.generation_mode] || row.generation_mode }}</el-tag></template></el-table-column><el-table-column prop="duration" label="时长（分钟）" width="110" /><el-table-column prop="total_score" label="总分" width="80" /><el-table-column prop="created_at" label="创建时间" width="180" /><el-table-column label="状态" width="80"><template #default="{ row }"><el-tag size="small" :type="row.status ? 'success' : 'info'">{{ row.status ? '启用' : '停用' }}</el-tag></template></el-table-column>
    <el-table-column label="操作" width="230" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="showPreview(row)">预览</el-button><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-button link @click="toggle(row)">{{ row.status ? '停用' : '启用' }}</el-button><el-button link type="danger" @click="remove(row)">删除</el-button></template></el-table-column>
  </el-table>
  <el-empty v-if="!papers.length && !loading" description="暂无试卷" />

  <el-dialog v-model="dialog.visible" :title="dialog.editing ? '编辑试卷' : '新建试卷'" width="720px">
    <el-form label-width="100px"><el-form-item label="试卷名称"><el-input v-model="form.title" /></el-form-item><el-form-item label="说明"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item><el-form-item label="答题时长"><el-input-number v-model="form.duration" :min="1" :max="1440" /> 分钟</el-form-item>
      <template v-if="!dialog.editing"><el-form-item label="组卷方式"><el-radio-group v-model="form.mode"><el-radio-button label="manual">手动选题</el-radio-button><el-radio-button label="random">随机组卷</el-radio-button><el-radio-button label="capability">能力模型</el-radio-button></el-radio-group></el-form-item><el-form-item v-if="form.mode === 'manual'" label="选择题目"><el-select v-model="form.question_ids" multiple filterable style="width:100%" placeholder="可多选题目"><el-option v-for="question in questions" :key="question.id" :label="questionLabel(question)" :value="question.id" /></el-select></el-form-item><el-form-item v-else-if="form.mode === 'capability'" label="能力模型"><el-select v-model="form.capability_model_id" filterable style="width:100%" placeholder="选择已启用的能力模型"><el-option v-for="model in capabilityModels.filter((item) => item.status)" :key="model.id" :label="`${model.name}（${(model.rules || []).map((rule) => `${rule.dimension}×${rule.count}`).join('、')}）`" :value="model.id" /></el-select></el-form-item><template v-else><el-form-item label="随机题量"><el-input-number v-model="form.count" :min="1" :max="200" /></el-form-item><el-form-item label="题型"><el-checkbox-group v-model="form.types"><el-checkbox label="single">单选</el-checkbox><el-checkbox label="multi">多选</el-checkbox><el-checkbox label="judge">判断</el-checkbox></el-checkbox-group></el-form-item><el-form-item label="能力维度"><el-input v-model="form.dimensions" placeholder="多个维度用英文逗号分隔，可留空" /></el-form-item></template></template>
    </el-form>
    <template #footer><el-button @click="dialog.visible=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
  </el-dialog>
  <el-dialog v-model="dialog.models" title="能力模型管理" width="860px">
    <div class="model-toolbar"><el-button type="primary" size="small" @click="openModel()">新增模型</el-button></div>
    <el-table :data="capabilityModels" stripe>
      <el-table-column prop="name" label="模型名称" min-width="180" />
      <el-table-column label="关联范围" min-width="150"><template #default="{ row }">{{ row.position_id ? `岗位 #${row.position_id}` : '通用' }}{{ row.position_level ? ` / L${row.position_level}` : '' }}</template></el-table-column>
      <el-table-column label="规则" min-width="240"><template #default="{ row }">{{ (row.rules || []).map((rule) => `${rule.dimension} × ${rule.count}`).join('；') }}</template></el-table-column>
      <el-table-column label="状态" width="80"><template #default="{ row }"><el-tag size="small" :type="row.status ? 'success' : 'info'">{{ row.status ? '启用' : '停用' }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="170"><template #default="{ row }"><el-button link type="primary" @click="openModel(row)">编辑</el-button><el-button link @click="toggleModel(row)">{{ row.status ? '停用' : '启用' }}</el-button><el-button link type="danger" @click="removeModel(row)">删除</el-button></template></el-table-column>
    </el-table>
    <el-empty v-if="!capabilityModels.length" description="暂无能力模型" />
  </el-dialog>
  <el-dialog v-model="dialog.modelForm" :title="modelEditing ? '编辑能力模型' : '新增能力模型'" width="900px">
    <el-form label-width="100px"><el-form-item label="模型名称"><el-input v-model="modelForm.name" /></el-form-item><el-form-item label="说明"><el-input v-model="modelForm.description" type="textarea" :rows="2" /></el-form-item><el-form-item label="关联岗位"><el-select v-model="modelForm.position_id" clearable filterable placeholder="可选"><el-option v-for="position in positions" :key="position.id" :label="`${position.name}（L${position.level}）`" :value="position.id" /></el-select><el-input-number v-model="modelForm.position_level" :min="1" :max="20" placeholder="职级" class="level-input" /></el-form-item></el-form>
    <div class="rule-head"><strong>能力维度规则</strong><el-button size="small" @click="addRule">新增维度</el-button></div>
    <el-table :data="modelForm.rules" border><el-table-column label="维度" min-width="150"><template #default="{ row }"><el-input v-model="row.dimension" placeholder="如：数据分析" /></template></el-table-column><el-table-column label="题量" width="120"><template #default="{ row }"><el-input-number v-model="row.count" :min="1" :max="500" /></template></el-table-column><el-table-column label="题型限制" min-width="180"><template #default="{ row }"><el-checkbox-group v-model="row.types"><el-checkbox label="single">单选</el-checkbox><el-checkbox label="multi">多选</el-checkbox><el-checkbox label="judge">判断</el-checkbox></el-checkbox-group></template></el-table-column><el-table-column label="难度限制" width="180"><template #default="{ row }"><el-checkbox-group v-model="row.difficulties"><el-checkbox v-for="level in 5" :key="level" :label="level">{{ level }}</el-checkbox></el-checkbox-group></template></el-table-column><el-table-column label="题库限制" min-width="180"><template #default="{ row }"><el-select v-model="row.bank_ids" multiple collapse-tags clearable placeholder="全部题库"><el-option v-for="bank in banks" :key="bank.id" :label="bank.name" :value="bank.id" /></el-select></template></el-table-column><el-table-column label="操作" width="70"><template #default="{ $index }"><el-button link type="danger" @click="removeRule($index)">删除</el-button></template></el-table-column></el-table>
    <template #footer><el-button @click="dialog.modelForm=false">取消</el-button><el-button type="primary" @click="saveModel">保存模型</el-button></template>
  </el-dialog>
  <el-dialog v-model="dialog.preview" title="试卷预览" width="720px"><div v-if="preview"><div class="preview-head"><strong>{{ preview.title }}</strong><span>{{ preview.duration }} 分钟 · {{ preview.total_score }} 分</span></div><el-card v-for="question in preview.questions" :key="`${question.paper_id}-${question.question_id}`" shadow="never" class="preview-question"><div><el-tag size="small">{{ typeLabels[question.type_snapshot] }}</el-tag><span class="dimension">{{ question.dimension_snapshot }}</span><span>{{ question.sort }}. {{ question.content_snapshot }}</span></div><div v-if="question.options_snapshot?.length" class="options">{{ question.options_snapshot.join(' / ') }}</div></el-card></div></el-dialog>
</template>

<style scoped>
.toolbar { display: flex; gap: 14px; align-items: center; margin-bottom: 14px; }.tip { color: #98a2b3; font-size: 12px; }.preview-head { display: flex; justify-content: space-between; margin-bottom: 14px; }.preview-question { margin-bottom: 10px; }.dimension { color: #2563eb; margin: 0 12px; font-size: 12px; }.options { color: #667085; font-size: 13px; margin: 10px 0 0 46px; }.model-toolbar { display: flex; justify-content: flex-end; margin-bottom: 12px; }.rule-head { display: flex; justify-content: space-between; align-items: center; margin: 4px 0 12px; }.level-input { margin-left: 12px; }
</style>
