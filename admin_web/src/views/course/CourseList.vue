<!-- hq新增内容 - 在线学习批次3 [CourseList.vue]
     「在线学习 / 课程列表」页：
     - 课程卡片网格（标题/简介/我的进度条/继续学习）
     - 点击学习 → 弹播放器（video Range 流）→ 播放中每 5s 上报进度、
       暂停/结束时也上报 → 进度实时更新到进度条与进度页
     后端：app/routers/course.py -->
<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { listCourses, reportCourseProgress, videoStreamUrl } from '@/api/course'

const route = useRoute()
const rows = ref([])
const loading = ref(false)
const keyword = ref('')

async function load() {
  loading.value = true
  try {
    const res = await listCourses({ keyword: keyword.value || undefined })
    rows.value = res.data.items
    // hq+  从学习进度页跳过来：自动打开指定课程
    const openId = Number(route.query.open_course || 0)
    if (openId) {
      const target = rows.value.find((r) => r.id === openId)
      if (target) openLearn(target)
    }
  } finally {
    loading.value = false
  }
}

// 学习播放器
const player = reactive({ visible: false, src: '', course: null })
let videoEl = null
let reportTimer = null
let lastReport = 0

function openLearn(row) {
  player.course = row
  player.src = videoStreamUrl(row.video_id)
  player.visible = true
}

function onVideoReady(e) {
  videoEl = e.target
  // 续播：跳回上次位置
  const p = player.course?.progress
  if (p && p.position > 0 && videoEl && videoEl.duration) {
    try { videoEl.currentTime = Math.min(p.position, videoEl.duration - 1) } catch (_) {}
  }
  startReporter()
}

function startReporter() {
  stopReporter()
  // 每 5 秒上报一次进度（节流）
  reportTimer = setInterval(() => {
    if (videoEl && player.course) {
      report(videoEl.currentTime || 0)
    }
  }, 5000)
}
function stopReporter() {
  if (reportTimer) { clearInterval(reportTimer); reportTimer = null }
}
function onPause() {
  if (videoEl && player.course) report(videoEl.currentTime || 0)
}
function onEnded() {
  if (videoEl && player.course) {
    report(videoEl.duration || 0)
    ElMessage.success('🎉 恭喜完成本课程学习！')
  }
  stopReporter()
}
async function report(position) {
  const c = player.course
  const duration = Math.round(videoEl?.duration || c.duration || 0)
  // 节流：1 秒内不重复报
  const now = Date.now()
  if (now - lastReport < 1000) return
  lastReport = now
  try {
    await reportCourseProgress(c.id, Math.round(position), duration)
    // 更新本地进度条
    if (duration > 0) {
      c.progress = {
        ...c.progress,
        position: Math.round(position),
        duration,
        percent: Math.min(100, Math.round(position * 100 / duration)),
        completed: Math.round(position * 100 / duration) >= 95 ? 1 : 0,
      }
    }
  } catch (_) { /* 静默，避免影响播放 */ }
}

function closePlayer() {
  stopReporter()
  player.visible = false
  player.course = null
}

function fmtDate(s) { return s ? String(s).slice(0, 16).replace('T', ' ') : '—' }

onMounted(load)
</script>

<template>
  <el-card>
    <template #header>
      <div class="head">
        <span class="title">课程列表</span>
        <div class="actions">
          <el-input v-model="keyword" placeholder="按课程名搜索" style="width:200px" clearable
            @keyup.enter="load" />
          <el-button @click="load">查询</el-button>
          <el-button @click="load">刷新进度</el-button>
        </div>
      </div>
    </template>

    <div v-loading="loading" class="grid">
      <div v-for="c in rows" :key="c.id" class="card">
        <div class="top">
          <div class="name" :title="c.title">{{ c.title }}</div>
          <el-tag v-if="c.progress.completed" type="success" size="small">已完成</el-tag>
          <el-tag v-else-if="c.progress.percent > 0" type="warning" size="small">学习中</el-tag>
          <el-tag v-else size="small" type="info">未开始</el-tag>
        </div>
        <div class="desc">{{ c.description || '暂无简介' }}</div>
        <div class="meta">
          <span>时长 {{ c.duration || '—' }}s</span>
          <span>{{ fmtDate(c.created_at) }}</span>
        </div>
        <el-progress :percentage="c.progress.percent || 0" :stroke-width="8" style="margin:10px 0" />
        <div class="foot">
          <span class="hint">
            {{ c.progress.completed ? '已完成' : (c.progress.percent > 0 ? `已学至 ${Math.round(c.progress.position)}s` : '尚未学习') }}
          </span>
          <el-button type="primary" size="small" :disabled="!c.video_ready" @click="openLearn(c)">
            {{ c.progress.percent > 0 ? '继续学习' : '开始学习' }}
          </el-button>
        </div>
      </div>
      <el-empty v-if="!loading && !rows.length" description="暂无课程，请先到「视频管理」生成课程" style="grid-column:1/-1" />
    </div>
  </el-card>

  <!-- 学习播放器（进度自动上报） -->
  <el-dialog v-model="player.visible" :title="player.course?.title || '课程学习'" width="70%" top="4vh"
    destroy-on-close @closed="closePlayer">
    <video v-if="player.src" :src="player.src" controls autoplay
      @loadedmetadata="onVideoReady" @pause="onPause" @ended="onEnded"
      style="width:100%;max-height:72vh;background:#000;border-radius:6px" />
    <div v-else style="color:#9ca3af;text-align:center;padding:40px">加载中…</div>
  </el-dialog>
</template>

<style scoped>
.head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
.title { font-size: 16px; font-weight: 600; }
.actions { display: flex; gap: 8px; align-items: center; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 18px; margin-top: 6px; }
.card { border: 1px solid #eef1f5; border-radius: 10px; padding: 14px; background: #fff; }
.name { font-weight: 600; color: #1f2937; }
.desc { font-size: 12px; color: #9ca3af; margin-top: 6px; min-height: 32px; }
.meta { display: flex; justify-content: space-between; font-size: 12px; color: #9ca3af; margin-top: 8px; }
.foot { display: flex; align-items: center; justify-content: space-between; }
.hint { font-size: 12px; color: #6b7280; }
</style>
