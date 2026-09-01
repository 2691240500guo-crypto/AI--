<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createPlan,
  deletePlan,
  getTrainingDictionaries,
  listCourseOptions,
  listPlans,
  updatePlan,
  updatePlanRecords
} from '@/api/training'

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const courses = ref([])
const dictionaries = getTrainingDictionaries()
const formRef = ref()

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  status: '',
  source: ''
})

const dialog = reactive({ visible: false, editing: false })
const progressDialog = reactive({ visible: false })
const form = reactive(blankPlan())
const progressForm = reactive({ id: null, title: '', status: 'in_progress', records: [] })

const rules = {
  title: [{ required: true, message: '请输入计划名称', trigger: 'blur' }],
  talent_name: [{ required: true, message: '请输入学习人员', trigger: 'blur' }],
  course_ids: [{ required: true, message: '请选择课程', trigger: 'change' }]
}

const selectedHours = computed(() => {
  return courses.value
    .filter((course) => form.course_ids.includes(course.id))
    .reduce((sum, course) => sum + Number(course.score || 0), 0)
})

function blankPlan() {
  return {
    id: null,
    title: '',
    talent_name: '',
    dept: '',
    target_role: '',
    weakness_tags: '',
    course_ids: [],
    source: 'manual',
    status: 'not_started',
    deadline: '',
    generated_by: '管理员',
    improvement: 0
  }
}

function statusType(status) {
  return { done: 'success', in_progress: 'primary', not_started: 'info', overdue: 'danger' }[status] || ''
}

function sourceType(source) {
  return source === 'agent' ? 'success' : 'info'
}

function courseTitle(id) {
  return courses.value.find((course) => course.id === id)?.title || `课程#${id}`
}

async function load() {
  loading.value = true
  try {
    const res = await listPlans(query)
    rows.value = res.data.items
    total.value = res.data.meta.total
  } finally {
    loading.value = false
  }
}

async function loadCourses() {
  const res = await listCourseOptions()
  courses.value = res.data
}

function resetQuery() {
  Object.assign(query, { page: 1, keyword: '', status: '', source: '' })
  load()
}

function openCreate() {
  Object.assign(form, blankPlan())
  dialog.editing = false
  dialog.visible = true
}

function openEdit(row) {
  Object.assign(form, {
    id: row.id,
    title: row.title,
    talent_name: row.talent_name,
    dept: row.dept,
    target_role: row.target_role,
    weakness_tags: (row.weakness_tags || []).join('，'),
    course_ids: [...row.course_ids],
    source: row.source,
    status: row.status,
    deadline: row.deadline,
    generated_by: row.generated_by,
    improvement: row.improvement
  })
  dialog.editing = true
  dialog.visible = true
}

async function save() {
  await formRef.value.validate()
  if (form.id) await updatePlan(form.id, form)
  else await createPlan(form)
  ElMessage.success('学习计划已保存')
  dialog.visible = false
  load()
}

function openProgress(row) {
  Object.assign(progressForm, {
    id: row.id,
    title: row.title,
    status: row.status,
    records: row.course_ids.map((courseId) => {
      const hit = (row.records || []).find((record) => record.course_id === courseId)
      return hit
        ? { ...hit, exam_score: hit.exam_score ?? null }
        : { course_id: courseId, progress: 0, exam_score: null, last_lesson: '' }
    })
  })
  progressDialog.visible = true
}

async function saveProgress() {
  await updatePlanRecords(progressForm.id, progressForm.records, progressForm.status)
  ElMessage.success('进度已更新')
  progressDialog.visible = false
  load()
}

async function del(row) {
  await ElMessageBox.confirm(`确定删除学习计划「${row.title}」？`, '提示', { type: 'warning' })
  await deletePlan(row.id)
  ElMessage.success('学习计划已删除')
  load()
}

onMounted(async () => {
  await loadCourses()
  load()
})
</script>

<template>
  <el-card>
    <div class="toolbar">
      <el-input
        v-model="query.keyword"
        placeholder="按人员/部门/计划/课程搜索"
        style="width:270px"
        clearable
        @keyup.enter="query.page=1;load()"
      />
      <el-select v-model="query.status" placeholder="计划状态" clearable style="width:140px" @change="query.page=1;load()">
        <el-option v-for="(label, value) in dictionaries.planStatus" :key="value" :label="label" :value="value" />
      </el-select>
      <el-select v-model="query.source" placeholder="来源" clearable style="width:140px" @change="query.page=1;load()">
        <el-option label="Agent 生成" value="agent" />
        <el-option label="手动创建" value="manual" />
      </el-select>
      <el-button type="primary" @click="query.page=1;load()">查询</el-button>
      <el-button @click="resetQuery">重置</el-button>
      <el-button type="primary" plain @click="openCreate">新增计划</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="title" label="计划名称" min-width="190" show-overflow-tooltip />
      <el-table-column label="学习人员" width="150">
        <template #default="{ row }">
          <div class="person">{{ row.talent_name }}</div>
          <div class="muted">{{ row.dept || '-' }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="target_role" label="目标岗位" width="130" show-overflow-tooltip />
      <el-table-column label="短板标签" min-width="160">
        <template #default="{ row }">
          <el-tag v-for="tag in row.weakness_tags" :key="tag" size="small" class="tag" type="info">{{ tag }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="课程" min-width="220">
        <template #default="{ row }">
          <div v-for="name in row.course_names" :key="name" class="course-line">{{ name }}</div>
        </template>
      </el-table-column>
      <el-table-column label="来源" width="110">
        <template #default="{ row }">
          <el-tag :type="sourceType(row.source)" size="small">{{ row.source_label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="进度" width="150">
        <template #default="{ row }">
          <el-progress :percentage="row.progress" :stroke-width="8" />
        </template>
      </el-table-column>
      <el-table-column label="考核" width="86">
        <template #default="{ row }">{{ row.exam_avg === null ? '-' : `${row.exam_avg}分` }}</template>
      </el-table-column>
      <el-table-column prop="deadline" label="截止日期" width="120" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ row.status_label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="190" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openProgress(row)">进度</el-button>
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

  <el-dialog v-model="dialog.visible" :title="dialog.editing ? '编辑学习计划' : '新增学习计划'" width="720px">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
      <el-row :gutter="14">
        <el-col :span="12">
          <el-form-item label="计划名称" prop="title">
            <el-input v-model="form.title" />
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="来源">
            <el-select v-model="form.source" style="width:100%">
              <el-option label="Agent 生成" value="agent" />
              <el-option label="手动创建" value="manual" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="状态">
            <el-select v-model="form.status" style="width:100%">
              <el-option v-for="(label, value) in dictionaries.planStatus" :key="value" :label="label" :value="value" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="14">
        <el-col :span="8">
          <el-form-item label="学习人员" prop="talent_name">
            <el-input v-model="form.talent_name" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="部门">
            <el-input v-model="form.dept" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="目标岗位">
            <el-input v-model="form.target_role" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="短板标签">
        <el-input v-model="form.weakness_tags" placeholder="多个标签用逗号分隔，如 数据分析，AI工具" />
      </el-form-item>
      <el-form-item label="推荐课程" prop="course_ids">
        <el-select v-model="form.course_ids" multiple filterable style="width:100%" placeholder="选择课程">
          <el-option
            v-for="course in courses"
            :key="course.id"
            :label="`${course.title}（${course.category} / ${course.score}学时）`"
            :value="course.id"
          />
        </el-select>
      </el-form-item>
      <el-row :gutter="14">
        <el-col :span="8">
          <el-form-item label="总学时">
            <el-input :model-value="`${selectedHours} 学时`" disabled />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="截止日期">
            <el-date-picker v-model="form.deadline" value-format="YYYY-MM-DD" type="date" style="width:100%" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="生成人">
            <el-input v-model="form.generated_by" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="能力提升">
        <el-input-number v-model="form.improvement" :min="0" :max="100" style="width:180px" />
        <span class="suffix">分</span>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialog.visible=false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="progressDialog.visible" :title="`进度打卡 · ${progressForm.title}`" width="760px">
    <div class="progress-head">
      <span>计划状态</span>
      <el-select v-model="progressForm.status" style="width:150px">
        <el-option v-for="(label, value) in dictionaries.planStatus" :key="value" :label="label" :value="value" />
      </el-select>
    </div>
    <el-table :data="progressForm.records" border>
      <el-table-column label="课程" min-width="190">
        <template #default="{ row }">{{ courseTitle(row.course_id) }}</template>
      </el-table-column>
      <el-table-column label="进度" width="240">
        <template #default="{ row }">
          <el-slider v-model="row.progress" :min="0" :max="100" />
        </template>
      </el-table-column>
      <el-table-column label="最近课节" min-width="180">
        <template #default="{ row }">
          <el-input v-model="row.last_lesson" placeholder="最近学习到的课节" />
        </template>
      </el-table-column>
      <el-table-column label="考核分" width="130">
        <template #default="{ row }">
          <el-input-number v-model="row.exam_score" :min="0" :max="100" controls-position="right" style="width:100%" />
        </template>
      </el-table-column>
    </el-table>
    <template #footer>
      <el-button @click="progressDialog.visible=false">取消</el-button>
      <el-button type="primary" @click="saveProgress">保存进度</el-button>
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
.person {
  color: #1f2937;
  font-weight: 600;
}
.muted {
  color: #909399;
  font-size: 12px;
  line-height: 18px;
}
.tag {
  margin: 2px 4px 2px 0;
}
.course-line {
  line-height: 22px;
}
.suffix {
  margin-left: 8px;
  color: #606266;
}
.progress-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  color: #606266;
}
</style>
