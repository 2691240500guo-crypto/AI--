<template>
  <div class="progress-overview">
    <el-card shadow="never" class="stat-card">
      <div class="stats">
        <div class="stat-item">
          <div class="stat-num">{{ stats.course_total || 0 }}</div>
          <div class="stat-label">课程总数</div>
        </div>
        <div class="stat-item">
          <div class="stat-num">{{ stats.employee_total || 0 }}</div>
          <div class="stat-label">学员总数</div>
        </div>
        <div class="stat-item">
          <div class="stat-num">{{ stats.has_progress || 0 }}</div>
          <div class="stat-label">有学习记录</div>
        </div>
        <div class="stat-item">
          <div class="stat-num">{{ stats.avg_percent_all || 0 }}%</div>
          <div class="stat-label">人均进度</div>
        </div>
        <div class="stat-item">
          <div class="stat-num">{{ stats.completed_employees || 0 }}</div>
          <div class="stat-label">已全完成</div>
        </div>
        <div class="stat-item">
          <div class="stat-num">{{ stats.learning_employees || 0 }}</div>
          <div class="stat-label">学习中</div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="table-card">
      <div class="toolbar">
        <el-input
          v-model="query.keyword" placeholder="姓名 / 工号 / 登录名" clearable
          style="width: 220px" @keyup.enter="query.page = 1; load()" @clear="query.page = 1; load()"
        />
        <el-select v-model="query.status" placeholder="学习状态" clearable style="width: 140px" @change="query.page = 1; load()">
          <el-option label="全部学员" value="" />
          <el-option label="学习中" value="learning" />
          <el-option label="已全部完成" value="completed" />
          <el-option label="未开始" value="not_started" />
        </el-select>
        <el-button type="primary" @click="query.page = 1; load()">查询</el-button>
        <el-button @click="load()">刷新</el-button>
      </div>

      <el-table v-loading="loading" :data="rows" stripe style="width: 100%">
        <el-table-column label="员工" min-width="130">
          <template #default="{ row }">
            <div class="emp-name">{{ row.nickname }}</div>
            <div class="emp-sub">{{ row.username }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="emp_no" label="工号" width="100" />
        <el-table-column prop="dept_name" label="部门" min-width="110" show-overflow-tooltip />
        <el-table-column label="总进度" width="180">
          <template #default="{ row }">
            <el-progress :percentage="row.avg_percent" :stroke-width="10" :color="progressColor(row.avg_percent)" />
          </template>
        </el-table-column>
        <el-table-column label="课程完成情况" width="170">
          <template #default="{ row }">
            <el-tag v-if="row.avg_percent >= 100 && row.learning === 0" type="success" size="small">已全部完成</el-tag>
            <el-tag v-else-if="row.avg_percent > 0" type="warning" size="small">
              完成 {{ row.completed }}/{{ row.course_total }} · 学中 {{ row.learning }}
            </el-tag>
            <el-tag v-else type="info" size="small">未开始</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近学习" width="160">
          <template #default="{ row }">{{ row.last_watch_at || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无学员学习数据" />
        </template>
      </el-table>

      <el-pagination
        v-model:current-page="query.page" v-model:page-size="query.page_size"
        :total="meta.total" layout="total, prev, pager, next" background
        style="margin-top: 14px; justify-content: flex-end"
        @current-change="load"
      />
    </el-card>

    <!-- 学员逐课进度详情 -->
    <el-dialog v-model="detailVisible" :title="`${detailEmp?.nickname || ''} · 逐课程学习进度`" width="760px">
      <el-table v-loading="detailLoading" :data="detailItems" size="small" stripe>
        <el-table-column prop="course_title" label="课程" min-width="200" show-overflow-tooltip />
        <el-table-column label="进度" width="180">
          <template #default="{ row }">
            <el-progress :percentage="row.percent" :stroke-width="8" :color="progressColor(row.percent)" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.completed" type="success" size="small">已完成</el-tag>
            <el-tag v-else-if="row.percent > 0" type="warning" size="small">学习中</el-tag>
            <el-tag v-else type="info" size="small">未学习</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近学习" width="160">
          <template #default="{ row }">{{ row.last_watch_at || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button v-if="row.percent > 0" link type="primary" @click="goCourse(row)">继续学习</el-button>
            <span v-else>—</span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getCourseProgressOverview, getUserCourseProgress } from '@/api/course'

const router = useRouter()
const loading = ref(false)
const rows = ref([])
const meta = reactive({ total: 0 })
const stats = reactive({})
const query = reactive({ keyword: '', status: '', page: 1, page_size: 20 })

const detailVisible = ref(false)
const detailLoading = ref(false)
const detailItems = ref([])
const detailEmp = ref(null)

function progressColor(p) {
  if (p >= 100) return '#3B6D11'
  if (p > 0) return '#185FA5'
  return '#B4B2A9'
}

async function load() {
  loading.value = true
  try {
    const res = await getCourseProgressOverview({
      keyword: query.keyword || undefined,
      status: query.status || undefined,
      page: query.page,
      page_size: query.page_size,
    })
    rows.value = res.data.items || []
    meta.total = res.data.meta?.total || 0
    Object.assign(stats, res.data.stats || {})
  } catch (e) {
    ElMessage.error(`加载失败：${e?.message || e}`)
  } finally {
    loading.value = false
  }
}

async function openDetail(row) {
  detailEmp.value = row
  detailVisible.value = true
  detailLoading.value = true
  detailItems.value = []
  try {
    const res = await getUserCourseProgress(row.user_id)
    detailItems.value = res.data.items || []
  } catch (e) {
    ElMessage.error(`详情加载失败：${e?.message || e}`)
  } finally {
    detailLoading.value = false
  }
}

function goCourse(row) {
  detailVisible.value = false
  router.push({ path: '/course/list', query: { open_course: row.course_id } })
}

onMounted(load)
</script>

<style scoped>
.stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.stat-item {
  flex: 1;
  min-width: 110px;
  text-align: center;
  padding: 6px 0;
  border-right: 1px solid var(--el-border-color-lighter);
}
.stat-item:last-child { border-right: none; }
.stat-num {
  font-size: 22px;
  font-weight: 500;
  color: var(--el-color-primary);
}
.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
.table-card { margin-top: 14px; }
.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}
.emp-name { font-weight: 500; }
.emp-sub { font-size: 12px; color: var(--el-text-color-secondary); }
</style>
