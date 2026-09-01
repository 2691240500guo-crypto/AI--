<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createCourse,
  deleteCourse,
  getTrainingDictionaries,
  listCourses,
  updateCourse
} from '@/api/training'

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const formRef = ref()
const dictionaries = getTrainingDictionaries()

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  category: '',
  status: ''
})

const dialog = reactive({ visible: false, editing: false })
const form = reactive(blankCourse())

const rules = {
  title: [{ required: true, message: '请输入课程名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择课程分类', trigger: 'change' }],
  score: [{ required: true, message: '请输入课程学时', trigger: 'blur' }]
}

function blankCourse() {
  return {
    id: null,
    title: '',
    category: '技术',
    score: 1,
    status: 'draft',
    allow_tags: '',
    intro: '',
    lessons: [{ title: '', duration: 30, file_url: '' }]
  }
}

function statusType(status) {
  return { published: 'success', draft: 'warning', offline: 'info' }[status] || ''
}

async function load() {
  loading.value = true
  try {
    const res = await listCourses(query)
    rows.value = res.data.items
    total.value = res.data.meta.total
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  Object.assign(query, { page: 1, keyword: '', category: '', status: '' })
  load()
}

function openCreate() {
  Object.assign(form, blankCourse())
  dialog.editing = false
  dialog.visible = true
}

function openEdit(row) {
  Object.assign(form, {
    ...row,
    allow_tags: (row.allow_tags || []).join('，'),
    lessons: row.lessons?.length ? row.lessons.map((lesson) => ({ ...lesson })) : []
  })
  dialog.editing = true
  dialog.visible = true
}

function addLesson() {
  form.lessons.push({ title: '', duration: 30, file_url: '' })
}

function removeLesson(index) {
  if (form.lessons.length === 1) {
    Object.assign(form.lessons[0], { title: '', duration: 30, file_url: '' })
    return
  }
  form.lessons.splice(index, 1)
}

async function save() {
  await formRef.value.validate()
  const payload = {
    ...form,
    lessons: form.lessons.filter((lesson) => lesson.title)
  }
  if (form.id) await updateCourse(form.id, payload)
  else await createCourse(payload)
  ElMessage.success('课程已保存')
  dialog.visible = false
  load()
}

async function del(row) {
  await ElMessageBox.confirm(`确定删除课程「${row.title}」？相关学习计划会同步移除该课程。`, '提示', { type: 'warning' })
  await deleteCourse(row.id)
  ElMessage.success('课程已删除')
  load()
}

onMounted(load)
</script>

<template>
  <el-card>
    <div class="toolbar">
      <el-input
        v-model="query.keyword"
        placeholder="按课程/短板标签搜索"
        style="width:260px"
        clearable
        @keyup.enter="query.page=1;load()"
      />
      <el-select v-model="query.category" placeholder="课程分类" clearable style="width:140px" @change="query.page=1;load()">
        <el-option v-for="item in dictionaries.categories" :key="item" :label="item" :value="item" />
      </el-select>
      <el-select v-model="query.status" placeholder="课程状态" clearable style="width:140px" @change="query.page=1;load()">
        <el-option v-for="(label, value) in dictionaries.courseStatus" :key="value" :label="label" :value="value" />
      </el-select>
      <el-button type="primary" @click="query.page=1;load()">查询</el-button>
      <el-button @click="resetQuery">重置</el-button>
      <el-button type="primary" plain @click="openCreate">新增课程</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="title" label="课程名称" min-width="190" show-overflow-tooltip />
      <el-table-column label="分类" width="90">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ row.category }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="score" label="学时" width="80" />
      <el-table-column prop="lesson_count" label="课件" width="80" />
      <el-table-column label="适用短板" min-width="210">
        <template #default="{ row }">
          <el-tag v-for="tag in row.allow_tags" :key="tag" size="small" class="tag" type="info">{{ tag }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ row.status_label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="updated_at" label="更新日期" width="120" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="del(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      style="margin-top:14px;justify-content:flex-end"
      layout="total, prev, pager, next"
      :total="total"
      v-model:current-page="query.page"
      :page-size="query.page_size"
      @current-change="load"
    />
  </el-card>

  <el-dialog v-model="dialog.visible" :title="dialog.editing ? '编辑课程' : '新增课程'" width="760px">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
      <el-row :gutter="14">
        <el-col :span="12">
          <el-form-item label="课程名称" prop="title">
            <el-input v-model="form.title" />
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="分类" prop="category">
            <el-select v-model="form.category" style="width:100%">
              <el-option v-for="item in dictionaries.categories" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="14">
        <el-col :span="8">
          <el-form-item label="学时" prop="score">
            <el-input-number v-model="form.score" :min="0.5" :step="0.5" style="width:100%" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="状态">
            <el-select v-model="form.status" style="width:100%">
              <el-option v-for="(label, value) in dictionaries.courseStatus" :key="value" :label="label" :value="value" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="适用短板">
        <el-input v-model="form.allow_tags" placeholder="多个标签用逗号分隔，如 AI工具，数据分析" />
      </el-form-item>
      <el-form-item label="课程简介">
        <el-input v-model="form.intro" type="textarea" :rows="3" maxlength="180" show-word-limit />
      </el-form-item>

      <el-form-item label="课件课节">
        <div class="lesson-list">
          <div v-for="(lesson, index) in form.lessons" :key="index" class="lesson-row">
            <el-input v-model="lesson.title" placeholder="课节名称" />
            <el-input-number v-model="lesson.duration" :min="0" :step="5" controls-position="right" />
            <el-input v-model="lesson.file_url" placeholder="课件/视频地址" />
            <el-button type="danger" plain @click="removeLesson(index)">移除</el-button>
          </div>
          <el-button type="primary" plain @click="addLesson">添加课件</el-button>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialog.visible=false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 14px;
}
.tag {
  margin: 2px 4px 2px 0;
}
.lesson-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}
.lesson-row {
  display: grid;
  grid-template-columns: minmax(140px, 1.2fr) 120px minmax(180px, 1.5fr) 74px;
  gap: 8px;
  width: 100%;
}
@media (max-width: 900px) {
  .lesson-row {
    grid-template-columns: 1fr;
  }
}
</style>
