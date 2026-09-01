<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createQuestion, deleteQuestion, listBanks, listBankQuestions, updateQuestion } from '@/api/assessment'

const TYPE_MAP = { single: '单选', multi: '多选', judge: '判断' }
const DIFF_MAP = { 1: '简单', 2: '较易', 3: '中等', 4: '较难', 5: '困难' }

const banks = ref([])
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ bank_id: 0, type: '', keyword: '', page: 1, page_size: 10 })
const dialog = reactive({ visible: false, editing: false })
const form = reactive({ id: null, bank_id: null, type: 'single', content: '', options: [], answer: '', dimension: '', difficulty: 1, score: 10, status: 1 })

async function loadBanks() {
  const res = await listBanks({ page_size: 200 })
  banks.value = res.data.items
}

async function load() {
  loading.value = true
  try {
    const res = await listBankQuestions(query.bank_id || 0, { type: query.type || undefined, keyword: query.keyword || undefined, page: query.page, page_size: query.page_size })
    rows.value = res.data.items
    total.value = res.data.meta.total
  } finally { loading.value = false }
}

function openCreate() {
  Object.assign(form, { id: null, bank_id: query.bank_id || banks.value[0]?.id || null, type: 'single', content: '', options: [{ key: 'A', text: '' }, { key: 'B', text: '' }], answer: '', dimension: '', difficulty: 1, score: 10, status: 1 })
  dialog.editing = false
  dialog.visible = true
}

function openEdit(row) {
  const opts = (row.options || []).map(o => ({ key: o.key, text: o.text }))
  let answer = row.answer
  if (row.type === 'multi' && typeof answer === 'string') answer = answer.split(',').filter(Boolean)
  Object.assign(form, {
    id: row.id, bank_id: row.bank_id, type: row.type, content: row.content,
    options: opts, answer, dimension: row.dimension, difficulty: row.difficulty,
    score: row.score, status: row.status
  })
  dialog.editing = true
  dialog.visible = true
}

function onTypeChange() {
  if (form.type === 'judge') form.options = []
  else if (!form.options.length) form.options = [{ key: 'A', text: '' }, { key: 'B', text: '' }]
  form.answer = ''
}

function addOption() {
  const next = String.fromCharCode(65 + form.options.length)
  form.options.push({ key: next, text: '' })
}
function removeOption(i) { form.options.splice(i, 1) }

async function save() {
  if (!form.bank_id) return ElMessage.warning('请选择题库')
  if (!form.content) return ElMessage.warning('请输入题干')
  if (form.type !== 'judge') {
    if (form.options.length < 2) return ElMessage.warning('至少需要两个选项')
    if (form.options.some(o => !o.text)) return ElMessage.warning('选项文字不能为空')
  }
  if (!form.answer) return ElMessage.warning('请设置正确答案')
  const payload = { ...form }
  // 多选答案：前端数组 -> 后端逗号分隔字符串（按 key 排序）
  if (payload.type === 'multi' && Array.isArray(payload.answer)) {
    payload.answer = [...payload.answer].sort().join(',')
  }
  if (payload.type === 'judge') payload.options = null
  if (form.id) await updateQuestion(form.id, payload)
  else await createQuestion(payload)
  ElMessage.success('已保存')
  dialog.visible = false
  load()
}

async function del(row) {
  await ElMessageBox.confirm('确定删除该题目？', '提示', { type: 'warning' })
  await deleteQuestion(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(async () => { await loadBanks(); await load() })
</script>

<template>
  <el-card>
    <div class="bar">
      <el-select v-model="query.bank_id" placeholder="全部题库" style="width:180px" @change="query.page=1;load()">
        <el-option label="全部题库" :value="0" />
        <el-option v-for="b in banks" :key="b.id" :label="b.name" :value="b.id" />
      </el-select>
      <el-select v-model="query.type" placeholder="题型" clearable style="width:120px" @change="query.page=1;load()">
        <el-option label="单选" value="single" /><el-option label="多选" value="multi" /><el-option label="判断" value="judge" />
      </el-select>
      <el-input v-model="query.keyword" placeholder="按题干搜索" style="width:220px" clearable @keyup.enter="query.page=1;load()" />
      <el-button type="primary" @click="query.page=1;load()">查询</el-button>
      <el-button type="primary" plain @click="openCreate">新增题目</el-button>
    </div>
    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="content" label="题干" show-overflow-tooltip />
      <el-table-column label="题型" width="80">
        <template #default="{ row }">{{ TYPE_MAP[row.type] || row.type }}</template>
      </el-table-column>
      <el-table-column prop="dimension" label="维度" width="80" />
      <el-table-column label="难度" width="80">
        <template #default="{ row }">{{ DIFF_MAP[row.difficulty] || row.difficulty }}</template>
      </el-table-column>
      <el-table-column prop="score" label="分值" width="70" />
      <el-table-column prop="answer" label="答案" width="90" />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="del(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination style="margin-top:14px" layout="total, prev, pager, next" :total="total"
      v-model:current-page="query.page" :page-size="query.page_size" @current-change="load" />
  </el-card>

  <el-dialog v-model="dialog.visible" :title="dialog.editing ? '编辑题目' : '新增题目'" width="640px">
    <el-form :model="form" label-width="90px">
      <el-form-item label="所属题库">
        <el-select v-model="form.bank_id" style="width:100%">
          <el-option v-for="b in banks" :key="b.id" :label="b.name" :value="b.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="题型">
        <el-radio-group v-model="form.type" @change="onTypeChange">
          <el-radio-button value="single">单选</el-radio-button>
          <el-radio-button value="multi">多选</el-radio-button>
          <el-radio-button value="judge">判断</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="题干">
        <el-input v-model="form.content" type="textarea" :rows="2" placeholder="请输入题干内容" />
      </el-form-item>
      <el-form-item v-if="form.type !== 'judge'" label="选项">
        <div style="width:100%">
          <div v-for="(o, i) in form.options" :key="i" style="display:flex;gap:8px;margin-bottom:6px">
            <el-tag style="width:28px;text-align:center">{{ o.key }}</el-tag>
            <el-input v-model="o.text" placeholder="选项文字" />
            <el-button link type="danger" @click="removeOption(i)">删除</el-button>
          </div>
          <el-button link type="primary" @click="addOption">+ 添加选项</el-button>
        </div>
      </el-form-item>
      <el-form-item label="正确答案">
        <el-select v-if="form.type === 'single'" v-model="form.answer" style="width:200px">
          <el-option v-for="o in form.options" :key="o.key" :label="`${o.key}. ${o.text}`" :value="o.key" />
        </el-select>
        <el-select v-else-if="form.type === 'multi'" v-model="form.answer" multiple style="width:300px">
          <el-option v-for="o in form.options" :key="o.key" :label="`${o.key}. ${o.text}`" :value="o.key" />
        </el-select>
        <el-radio-group v-else v-model="form.answer">
          <el-radio value="true">正确</el-radio><el-radio value="false">错误</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="能力维度">
        <el-input v-model="form.dimension" placeholder="如：技术 / 沟通 / 逻辑" style="width:200px" />
      </el-form-item>
      <el-form-item label="难度 / 分值">
        <el-select v-model="form.difficulty" style="width:120px;margin-right:10px">
          <el-option v-for="(v,k) in DIFF_MAP" :key="k" :label="v" :value="Number(k)" />
        </el-select>
        <el-input-number v-model="form.score" :min="0" :max="100" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialog.visible=false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.bar { display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
</style>
