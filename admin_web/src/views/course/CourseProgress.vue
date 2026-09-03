<!-- 2026-09-03：本组件(个人学习进度,员工维度)已从管理端路由下线；管理端「学习进度」现为全员监控页 ProgressOverview.vue。员工个人进度应置于员工端。 -->
<!-- hq新增内容 - 在线学习批次3 [CourseProgress.vue]
     「在线学习 / 学习进度」页：
     - 汇总我的所有课程学习进度（进度条 + 最近学习时间）
     - 顶部统计卡：总课程 / 学习中 / 已完成
     - 「继续学习」按钮 → 跳到课程列表页并打开该课程（通过路由参数自动打开）
     后端：GET /course/progress -->
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getMyCourseProgress } from '@/api/course'

const router = useRouter()
const items = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await getMyCourseProgress()
    items.value = res.data.items
  } finally {
    loading.value = false
  }
}

const stats = computed(() => {
  const total = items.value.length
  const completed = items.value.filter((i) => i.completed).length
  const learning = items.value.filter((i) => !i.completed && i.percent > 0).length
  const notStarted = items.value.filter((i) => i.percent === 0).length
  return { total, completed, learning, notStarted }
})
const avgPercent = computed(() => {
  if (!items.value.length) return 0
  return Math.round(items.value.reduce((s, i) => s + i.percent, 0) / items.value.length)
})

function continueLearn(row) {
  // 跳到课程列表，带 open_course 参数（CourseList 读取后自动打开播放器）
  router.push({ path: '/course/list', query: { open_course: row.course_id } })
}

function fmtTime(s) { return s ? String(s).slice(0, 16).replace('T', ' ') : '—' }

onMounted(load)
</script>

<template>
  <el-card>
    <template #header>
      <div class="head">
        <span class="title">学习进度</span>
        <el-button size="small" @click="load">刷新</el-button>
      </div>
    </template>

    <!-- 统计卡：课程总数 = 未学习 + 学习中 + 已完成 -->
    <div class="stats">
      <div class="stat main"><div class="num">{{ stats.total }}</div><div class="lbl">课程总数</div></div>
      <div class="stat"><div class="num" style="color:#9ca3af">{{ stats.notStarted }}</div><div class="lbl">未学习</div></div>
      <div class="stat"><div class="num" style="color:#d97706">{{ stats.learning }}</div><div class="lbl">学习中</div></div>
      <div class="stat"><div class="num" style="color:#16a34a">{{ stats.completed }}</div><div class="lbl">已完成</div></div>
      <div class="stat"><div class="num" style="color:#185fa5">{{ avgPercent }}%</div><div class="lbl">平均进度</div></div>
    </div>

    <!-- 进度明细 -->
    <div v-loading="loading">
      <el-empty v-if="!loading && !items.length" description="暂无学习记录，去课程列表开始学习吧" />
      <div v-for="i in items" :key="i.course_id" class="prog-row">
        <div class="left">
          <div class="name">
            {{ i.course_title }}
            <el-tag v-if="i.completed" type="success" size="small" style="margin-left:8px">已完成</el-tag>
            <el-tag v-else-if="i.percent > 0" type="warning" size="small" style="margin-left:8px">学习中</el-tag>
            <el-tag v-else size="small" type="info" style="margin-left:8px">未学习</el-tag>
          </div>
          <div class="meta">
            <template v-if="i.percent > 0">
              已学 {{ Math.round(i.position) }}s / {{ i.duration || '—' }}s ·
              最近学习 {{ fmtTime(i.last_watch_at) }}
            </template>
            <template v-else>
              尚未开始学习
            </template>
          </div>
        </div>
        <div class="mid">
          <el-progress :percentage="i.percent || 0" :stroke-width="10" />
        </div>
        <div class="right">
          <el-button type="primary" size="small" :disabled="!i.video_ready" @click="continueLearn(i)">
            {{ i.completed ? '再学一遍' : (i.percent > 0 ? '继续学习' : '开始学习') }}
          </el-button>
        </div>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.head { display: flex; align-items: center; justify-content: space-between; }
.title { font-size: 16px; font-weight: 600; }

.stats { display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; margin-bottom: 18px; }
.stat { border: 1px solid #eef1f5; border-radius: 10px; text-align: center; padding: 16px 0; background: #fcfcfd; }
.stat.main { background: #e6f1fb; border-color: #b5d4f4; }
.num { font-size: 22px; font-weight: 600; color: #374151; }
.lbl { font-size: 12px; color: #9ca3af; margin-top: 4px; }

.prog-row { display: flex; align-items: center; gap: 16px; padding: 14px 4px; border-bottom: 1px dashed #eef1f5; }
.left { flex: 0 0 36%; min-width: 220px; }
.name { font-weight: 600; color: #1f2937; }
.meta { font-size: 12px; color: #9ca3af; margin-top: 4px; }
.mid { flex: 1; }
.right { flex: 0 0 auto; }
</style>
