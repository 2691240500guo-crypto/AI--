<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createPaper, createPaperAuto, deletePaper, listPapers, listBankQuestions, updatePaper } from '@/api/assessment'

const TYPE_MAP = { single: '单选', multi: '多选', judge: '判断' }
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, page_size: 10, keyword: '', gen_method: '' })

const dialog = reactive({ visible: false })
const allQuestions = ref([])
const qLoading = ref(false)
const form = reactive({ id: null, title: '', description: '', question_ids: [], duration_min: 60, difficulty: 1, gen_method: 'manual' })

// AI 智能组卷
const autoDialog = reactive({ visible: false, loading: false })
const autoForm = reactive({ title: '', dimension: '', difficulty: null, question_count: 10, duration_min: 60 })
const DIMENSIONS = ['技术', '沟通', '逻辑', '管理', '英语', '综合']

async function load() {
  loading.value = true
  try {
    const res = await listPapers(query)
    rows.value = res.data.items
    total.value = res.data.meta.total
  } finally { loading.value = false }
}

async function openCreate() {
  Object.assign(form, { title: '', description: '', question_ids: [], duration_min: 60, difficulty: 1, gen_method: 'manual' })
  qLoading.value = true
  dialog.visible = true
  try {
    const res = await listBankQuestions(0, { page_size: 200 })
    allQuestions.value = res.data.items
  } finally { qLoading.value = false }
}

async function save() {
  if (!form.title) return ElMessage.warning('请输入试卷标题')
  if (!form.question_ids.length) return ElMessage.warning('请至少选择一道题目')
  if (form.id) await updatePaper(form.id, form)
  else await createPaper(form)
  ElMessage.success('已保存')
  dialog.visible = false
  load()
}

async function openEdit(row) {
  Object.assign(form, { id: row.id, title: row.title, description: row.description, question_ids: row.question_ids || [], duration_min: row.duration_min, difficulty: row.difficulty, gen_method: row.gen_method || 'manual' })
  qLoading.value = true
  dialog.visible = true
  try {
    const res = await listBankQuestions(0, { page_size: 200 })
    allQuestions.value = res.data.items
  } finally { qLoading.value = false }
}

async function del(row) {
  await ElMessageBox.confirm(`确定删除试卷「${row.title}」？`, '提示', { type: 'warning' })
  await deletePaper(row.id)
  ElMessage.success('已删除')
  load()
}

async function autoCreate() {
  if (!autoForm.title) return ElMessage.warning('请输入试卷标题')
  if (autoForm.question_count < 1) return ElMessage.warning('请输入题数')
  autoDialog.loading = true
  try {
    const payload = {
      title: autoForm.title,
      description: autoForm.dimension ? `智能抽题 · ${autoForm.dimension}维度` : '智能抽题 · 全维度',
      dimension: autoForm.dimension || null,
      difficulty: autoForm.difficulty || null,
      question_count: autoForm.question_count,
      duration_min: autoForm.duration_min,
    }
    const res = await createPaperAuto(payload)
    ElMessage.success(`智能组卷成功：${res.data.title}（${res.data.question_count}题 / ${res.data.total_score}分）`)
    autoDialog.visible = false
    load()
  } catch (e) {
    ElMessage.error(e?.message || '智能组卷失败')
  } finally { autoDialog.loading = false }
}

const selectedScore = () => allQuestions.value.filter(q => form.question_ids.includes(q.id)).reduce((s, q) => s + q.score, 0)

onMounted(load)
</script>

<template>
  <el-card>
    <div class="bar">
      <el-input v-model="query.keyword" placeholder="按试卷标题搜索" style="width:220px" clearable @keyup.enter="query.page=1;load()" />
      <el-select v-model="query.gen_method" placeholder="组卷方式" clearable style="width:140px" @change="query.page=1;load()">
        <el-option label="手动组卷" value="manual" />
        <el-option label="智能抽题" value="auto" />
      </el-select>
      <el-button type="primary" @click="query.page=1;load()">查询</el-button>
      <el-button type="primary" plain @click="openCreate">手动组卷</el-button>
      <el-button type="warning" plain @click="() => { Object.assign(autoForm, { title: '', dimension: '', difficulty: null, question_count: 10, duration_min: 60 }); autoDialog.visible = true }">
        ⚡ AI 智能组卷
      </el-button>
    </div>
    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="试卷标题" min-width="200" show-overflow-tooltip />
      <el-table-column label="组卷方式" width="100">
        <template #default="{ row }">
          <el-tag :type="row.gen_method === 'auto' ? 'warning' : 'info'" size="small">
            {{ row.gen_method === 'auto' ? '智能抽题' : '手动组卷' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="question_count" label="题数" width="70" />
      <el-table-column prop="total_score" label="总分" width="70" />
      <el-table-column prop="duration_min" label="时限(分)" width="80" />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button link type="primary" @click="$router.push(`/assessment/launch?paper_id=${row.id}`)">发起</el-button>
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="del(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination style="margin-top:14px" layout="total, prev, pager, next" :total="total"
      v-model:current-page="query.page" :page-size="query.page_size" @current-change="load" />
  </el-card>

  <el-dialog v-model="dialog.visible" :title="form.id ? '编辑试卷' : '新建试卷'" width="760px" top="6vh">
    <el-form :model="form" label-width="80px">
      <el-form-item label="试卷标题"><el-input v-model="form.title" placeholder="如：技术能力测试卷" /></el-form-item>
      <el-form-item label="组卷方式">
        <el-radio-group v-model="form.gen_method">
          <el-radio-button value="manual">手动组卷</el-radio-button>
          <el-radio-button value="auto">智能抽题</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
      <el-form-item label="时限">
        <el-input-number v-model="form.duration_min" :min="1" :max="600" style="margin-right:10px" /> 分钟
      </el-form-item>
      <el-form-item label="选择题目">
        <div style="width:100%" v-loading="qLoading">
          <div style="margin-bottom:8px;color:#888">
            已选 <b>{{ form.question_ids.length }}</b> 题 / 合计 <b>{{ selectedScore() }}</b> 分
          </div>
          <el-table :data="allQuestions" max-height="360" border @selection-change="(sel) => (form.question_ids = sel.map(s => s.id))">
            <el-table-column type="selection" width="44" />
            <el-table-column prop="id" label="ID" width="56" />
            <el-table-column prop="content" label="题干" show-overflow-tooltip />
            <el-table-column label="题型" width="70">
              <template #default="{ row }">{{ TYPE_MAP[row.type] }}</template>
            </el-table-column>
            <el-table-column prop="score" label="分值" width="60" />
          </el-table>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialog.visible=false">取消</el-button>
      <el-button type="primary" @click="save">{{ form.id ? '保存修改' : '创建试卷' }}</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="autoDialog.visible" title="AI 智能组卷" width="480px">
    <el-alert title="按条件从题库自动抽题，维度均衡优先；手动组卷则是自己勾选题目。" type="info" :closable="false" style="margin-bottom:16px" />
    <el-form :model="autoForm" label-width="90px">
      <el-form-item label="试卷标题"><el-input v-model="autoForm.title" placeholder="如：技术专项测评-06" /></el-form-item>
      <el-form-item label="能力维度">
        <el-select v-model="autoForm.dimension" placeholder="全部维度" clearable style="width:100%">
          <el-option v-for="d in DIMENSIONS" :key="d" :label="d" :value="d" />
        </el-select>
      </el-form-item>
      <el-form-item label="难度">
        <el-select v-model="autoForm.difficulty" placeholder="不限" clearable style="width:100%">
          <el-option label="简单" :value="1" /><el-option label="较易" :value="2" /><el-option label="中等" :value="3" /><el-option label="较难" :value="4" /><el-option label="困难" :value="5" />
        </el-select>
      </el-form-item>
      <el-form-item label="题数">
        <el-input-number v-model="autoForm.question_count" :min="1" :max="100" style="margin-right:10px" /> 道
      </el-form-item>
      <el-form-item label="时限">
        <el-input-number v-model="autoForm.duration_min" :min="1" :max="600" style="margin-right:10px" /> 分钟
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="autoDialog.visible=false">取消</el-button>
      <el-button type="warning" :loading="autoDialog.loading" @click="autoCreate">⚡ 智能抽题组卷</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.bar { display: flex; gap: 10px; margin-bottom: 14px; }
</style>
