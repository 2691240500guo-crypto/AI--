<!-- hq新增内容 - 在线学习批次3 [VideoManage.vue]
     「在线学习 / 视频管理」页：
     - 顶部：上传按钮（大文件）
     - 主体：腾讯视频风格网格概览（封面位 + 标题 + 时长 + 大小）
     - 点视频卡片 → 弹出播放器（video 标签 + Range 流 + 进度上报）
     - 每张卡片有「生成课程」按钮 → 调用后端 → 跳到课程列表
     后端：app/routers/course.py -->
<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  generateCourseFromVideo,
  listCourseVideos,
  uploadCourseVideo,
  videoStreamUrl,
} from '@/api/course'

const router = useRouter()
const rows = ref([])
const loading = ref(false)
const keyword = ref('')

// 上传
const uploadVisible = ref(false)
const pickedFile = ref(null)
const uploading = ref(false)
const percent = ref(0)

function onPickFile(file) {
  // auto-upload=false 时用 on-change + .raw（与简历上传同坑）
  pickedFile.value = file.raw || file
  return false
}

async function doUpload() {
  if (!pickedFile.value) { ElMessage.warning('请先选择视频文件'); return }
  uploading.value = true
  percent.value = 0
  try {
    const res = await uploadCourseVideo(pickedFile.value, (p) => { percent.value = p })
    ElMessage.success(res.data?.message || '上传成功')
    uploadVisible.value = false
    pickedFile.value = null
    load()
  } catch (e) {
    // request.js 已弹错误
  } finally {
    uploading.value = false
  }
}

// 列表
async function load() {
  loading.value = true
  try {
    const res = await listCourseVideos({ keyword: keyword.value || undefined })
    rows.value = res.data.items
  } finally {
    loading.value = false
  }
}

// 播放
const player = reactive({ visible: false, src: '', title: '' })
function openPlayer(row) {
  player.title = row.title
  player.src = videoStreamUrl(row.id)
  player.visible = true
}

// 生成课程
async function genCourse(row) {
  await ElMessageBox.confirm(
    `确定用视频「${row.title}」生成课程吗？生成后可进入课程列表学习。`,
    '生成课程',
    { type: 'info', confirmButtonText: '生成课程', cancelButtonText: '取消' },
  )
  try {
    const res = await generateCourseFromVideo(row.id)
    ElMessage.success(res.data?.message || '课程已生成')
    await load()
    // 自动进入课程列表界面
    router.push('/course/list')
  } catch (e) {
    // request.js 已弹错误
  }
}

function fmtSize(n) {
  if (!n) return '—'
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB'
  return (n / 1024 / 1024).toFixed(1) + ' MB'
}
function fmtDate(s) { return s ? String(s).slice(0, 16).replace('T', ' ') : '—' }

onMounted(load)
</script>

<template>
  <el-card>
    <template #header>
      <div class="head">
        <span class="title">视频管理</span>
        <div class="actions">
          <el-input v-model="keyword" placeholder="按标题搜索" style="width:200px" clearable
            @keyup.enter="load" />
          <el-button @click="load">查询</el-button>
          <el-button type="primary" @click="uploadVisible = true">上传视频</el-button>
        </div>
      </div>
    </template>

    <!-- 腾讯视频风格网格 -->
    <div v-loading="loading" class="grid">
      <div v-for="v in rows" :key="v.id" class="card" @click="openPlayer(v)">
        <div class="cover">
          <div class="cover-play">
            <span class="play-icon" />
          </div>
          <div class="cover-meta">
            <span v-if="v.duration" class="meta-item">时长 {{ v.duration }}s</span>
            <span class="meta-item">{{ fmtSize(v.size) }}</span>
          </div>
          <div v-if="v.has_course" class="tag-done">已生成课程</div>
        </div>
        <div class="info">
          <div class="name" :title="v.title">{{ v.title }}</div>
          <div class="desc">{{ v.description || '暂无简介' }}</div>
          <div class="row">
            <span class="date">{{ fmtDate(v.created_at) }}</span>
            <el-button
              size="small" type="primary" plain
              :disabled="v.has_course"
              @click.stop="genCourse(v)"
            >
              {{ v.has_course ? '已生成课程' : '生成课程' }}
            </el-button>
          </div>
        </div>
      </div>
      <el-empty v-if="!loading && !rows.length" description="暂无视频，点击右上角「上传视频」开始" style="grid-column:1/-1" />
    </div>
  </el-card>

  <!-- 上传对话框 -->
  <el-dialog v-model="uploadVisible" title="上传视频" width="480px">
    <el-upload drag :auto-upload="false" :on-change="onPickFile" accept=".mp4,.webm,.mov,.m4v,.avi,.mkv,.flv"
      :limit="1" style="width:100%">
      <div>拖拽或点击选择视频（mp4/webm/mov/m4v/avi/mkv/flv）</div>
    </el-upload>
    <el-progress v-if="uploading" :percentage="percent" style="margin-top:12px" />
    <template #footer>
      <el-button @click="uploadVisible = false">取消</el-button>
      <el-button type="primary" :loading="uploading" @click="doUpload">上传</el-button>
    </template>
  </el-dialog>

  <!-- 视频播放器 -->
  <el-dialog v-model="player.visible" :title="player.title" width="70%" top="5vh" destroy-on-close>
    <video v-if="player.src" :src="player.src" controls autoplay style="width:100%;max-height:70vh;background:#000;border-radius:6px" />
    <div v-else style="color:#9ca3af;text-align:center;padding:40px">加载中…</div>
  </el-dialog>
</template>

<style scoped>
.head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
.title { font-size: 16px; font-weight: 600; }
.actions { display: flex; gap: 8px; align-items: center; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 18px; margin-top: 6px; }
.card { border: 1px solid #eef1f5; border-radius: 10px; overflow: hidden; cursor: pointer; transition: box-shadow .2s; background: #fff; }
.card:hover { box-shadow: 0 4px 14px rgba(0,0,0,.08); }
.cover { position: relative; aspect-ratio: 16/9; background: #0f172a; display: flex; align-items: center; justify-content: center; }
.cover-play { width: 48px; height: 48px; border-radius: 50%; background: rgba(255,255,255,.15); display: flex; align-items: center; justify-content: center; }
.play-icon { width: 0; height: 0; border-left: 18px solid #fff; border-top: 11px solid transparent; border-bottom: 11px solid transparent; margin-left: 4px; }
.cover-meta { position: absolute; right: 8px; bottom: 8px; display: flex; gap: 6px; }
.meta-item { background: rgba(0,0,0,.55); color: #fff; font-size: 11px; padding: 2px 6px; border-radius: 4px; }
.tag-done { position: absolute; left: 8px; top: 8px; background: #16a34a; color: #fff; font-size: 11px; padding: 2px 8px; border-radius: 4px; }
.info { padding: 10px 12px; }
.name { font-weight: 600; color: #1f2937; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.desc { font-size: 12px; color: #9ca3af; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.row { display: flex; align-items: center; justify-content: space-between; margin-top: 8px; }
.date { font-size: 12px; color: #9ca3af; }
</style>
