<!-- hq新增内容 - 人才档案批次后续 [ResumeImport.vue]
     「AI 智能档案 / 简历智能解析」分模块页面（对应 T-P2-07）。
     - 上半部分：上传组件（直接从 dialog 抽出来，作为页面主元素）
     - 下半部分：最近 10 条 import 来源的人才（带 AI 解析状态 + 跳转编辑页）
-->
<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteTalent, listTalents, mergeOverwrite, uploadResume,
} from '@/api/talent'

const router = useRouter()
const ACCEPT = '.pdf,.docx,.txt,.md,.jpg,.jpeg,.png,.bmp,.webp'

// 上传相关
const uploading = ref(false)
const percent = ref(0)
const pickedFile = ref(null)

// 最近上传列表
const recent = ref([])
const loadingRecent = ref(false)

const sourceLabel = (s) => ({ manual: '人工', import: '导入', agent_parsed: 'AI 解析' }[s] || s)
const sourceTag = (s) => ({ manual: 'info', import: 'success', agent_parsed: 'primary' }[s] || '')

function onPickFile(file) {
  // Element Plus 在 auto-upload=false 时**不**触发 before-upload，只触发 on-change；
  // 这里同样用 .raw 拿原生 File（与 list.vue 一致）。
  pickedFile.value = file.raw || file
  return false
}

async function doUpload() {
  if (!pickedFile.value) { ElMessage.warning('请先选择文件'); return }
  uploading.value = true
  percent.value = 0
  phase.value = 'uploading'
  try {
    const res = await uploadResume(pickedFile.value, onProgress)
    const data = res.data || {}
    const newId = data?.talent?.id
    phase.value = 'done'

    // hq+  批次C：去重处理 —— 无论 double 还是 单条件(name/phone)，统一弹确认框人工确认
    const dup = data?.duplicate
    if (dup && dup.matched) {
      const typeText = dup.type === 'double' ? '姓名+电话' : (dup.type === 'name' ? '姓名' : '电话')
      const oldInfo = `${dup.old_name || '未知'}` + (dup.old_company ? `（${dup.old_company}）` : '')
      try {
        await ElMessageBox.confirm(
          `检测到新简历与库内「${oldInfo}」的${typeText}匹配，可能是同一人。` +
          `是否用新简历覆盖旧档案？选择「保留两份」则新简历单独入库。`,
          '检测到可能重复的档案',
          { type: 'warning', confirmButtonText: '覆盖旧档案', cancelButtonText: '保留两份' },
        )
        // 用户确认覆盖
        await mergeOverwrite(newId, dup.old_talent_id)
        ElMessage.success('已用新简历覆盖旧档案')
      } catch (e) {
        if (e !== 'cancel' && e?.message) ElMessage.error('覆盖失败：' + e.message)
        // 用户选「保留两份」：什么都不做，新档案已在库中
      }
    } else {
      ElMessage.success(data?.message || '上传成功')
    }

    pickedFile.value = null
    percent.value = 0
    loadRecent()
    // 跳到编辑页让用户补字段 / 看 AI 自动填的内容
    if (newId) router.push(`/talent/edit/${newId}`)
  } catch (e) {
    // request.js 拦截器已弹 ElMessage，这里不重复
  } finally {
    uploading.value = false
    phase.value = ''
  }
}

// hq+  阶段提示：progress>=100 表示上传完成但 LLM 仍在解析，需提示用户等待
const phase = ref('')  // '' | 'uploading' | 'parsing'
function onProgress(p) {
  percent.value = p
  phase.value = p >= 100 ? 'parsing' : 'uploading'
}

async function loadRecent() {
  loadingRecent.value = true
  try {
    const res = await listTalents({ source: 'import', page: 1, page_size: 10 })
    recent.value = res.data?.items || []
  } finally {
    loadingRecent.value = false
  }
}

async function removeRow(row) {
  await ElMessageBox.confirm(`确定删除人才「${row.name}」？该操作为软删除。`, '提示', { type: 'warning' })
  await deleteTalent(row.id)
  ElMessage.success('已删除')
  loadRecent()
}

onMounted(loadRecent)
</script>

<template>
  <div class="page">
    <!-- 上传卡片 -->
    <el-card class="upload-card">
      <template #header>
        <div class="head">
          <span class="title">上传简历</span>
          <span class="hint">上传后会自动落 MinIO、抽文本、调 LLM 抽取 8 字段并入库；大文件/LLM 推理可能耗时 1-3 分钟</span>
        </div>
      </template>

      <el-alert type="info" :closable="false" style="margin-bottom:14px">
        支持 PDF / Word (.docx) / 图片 (.jpg .png 等，需本机装 tesseract) / TXT / MD
      </el-alert>

      <el-upload
        :accept="ACCEPT"
        :auto-upload="false"
        :show-file-list="false"
        :on-change="onPickFile"
      >
        <el-button>选择文件</el-button>
        <template #tip>
          <div class="el-upload__tip" style="margin-top:6px">
            {{ pickedFile ? '已选择：' + pickedFile.name : '单个文件 ≤ 20MB' }}
          </div>
        </template>
      </el-upload>

      <div v-if="pickedFile" class="picked">
        <span>{{ pickedFile.name }}</span>
        <span style="color:#9ca3af;font-size:12px">
          {{ (pickedFile.size / 1024).toFixed(1) }} KB
        </span>
      </div>

      <el-progress v-if="uploading" :percentage="percent" style="margin-top:10px" />
      <el-alert v-if="uploading && phase === 'parsing'" type="warning" :closable="false" style="margin-top:10px">
        文件已上传完成，正在调用本地大模型（Ollama）抽取简历字段，约需 1 分钟，请勿关闭页面…
      </el-alert>

      <div class="actions">
        <el-button type="primary" :loading="uploading" :disabled="!pickedFile" @click="doUpload">
          上传并解析
        </el-button>
      </div>
    </el-card>

    <!-- 最近导入列表 -->
    <el-card class="recent-card">
      <template #header>
        <div class="head">
          <span class="title">最近导入的人才（source=import）</span>
          <el-button size="small" @click="loadRecent">刷新</el-button>
        </div>
      </template>

      <el-table :data="recent" v-loading="loadingRecent" stripe size="small">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="姓名" min-width="120">
          <template #default="{ row }">
            <el-link type="primary" :underline="false" @click="router.push(`/talent/edit/${row.id}`)">
              {{ row.name || '未命名' }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="职称" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.current_title || '—' }}</template>
        </el-table-column>
        <el-table-column label="公司" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.current_company || '—' }}</template>
        </el-table-column>
        <el-table-column label="来源" width="100">
          <template #default="{ row }">
            <el-tag :type="sourceTag(row.source)" size="small">{{ sourceLabel(row.source) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? '在档' : '失效' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button link type="primary" @click="router.push(`/talent/edit/${row.id}`)">查看</el-button>
            <el-button link type="danger" @click="removeRow(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.page { display: flex; flex-direction: column; gap: 14px; }
.upload-card, .recent-card { background: #fff; }
.head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.title { font-weight: 600; color: #1f2937; }
.hint { color: #9ca3af; font-size: 12px; }
.picked { margin-top: 8px; display: flex; gap: 10px; align-items: center; font-size: 13px; }
.actions { margin-top: 14px; text-align: right; }
</style>
