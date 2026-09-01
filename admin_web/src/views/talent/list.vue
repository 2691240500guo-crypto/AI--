<!-- hq新增内容 - 人才档案批次1 [list.vue]
     结构与 system/user.vue 同款，方便联调 + 后期维护时风格一致。
     后端接口：GET /api/v1/talent（见 app/routers/talent.py）。

     hq+  批次 2.3a：右上「导入/解析简历」按钮接通：选文件 → 上传到
     /api/v1/resume/upload → 弹 success → 跳转编辑页让用户补字段。 -->
<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteTalent,
  downloadResume,        // hq+
  listTalents,
  previewResume,         // hq+
  semanticSearchTalent,
} from '@/api/talent'

const router = useRouter()
const route = useRoute()  // hq+ 批次A tag 筛选
const rows = ref([])
const total = ref(0)
const loading = ref(false)

// hq+  附件简历预览
const preview = reactive({ visible: false, url: '', name: '', busy: false })
async function openPreview(row) {
  if (!row.object_key && !row.resume_file) { ElMessage.warning('该档案没有附件简历'); return }
  preview.busy = true
  preview.visible = true
  preview.name = `${row.name || '未命名'}-简历`
  try {
    const blobUrl = await previewResume(row.id)
    preview.url = blobUrl
  } catch (e) {
    ElMessage.error('预览失败：' + (e.message || ''))
    preview.visible = false
  } finally {
    preview.busy = false
  }
}
function closePreview() {
  if (preview.url) URL.revokeObjectURL(preview.url)
  preview.url = ''
  preview.visible = false
}
async function doDownload(row) {
  if (!row.object_key && !row.resume_file) { ElMessage.warning('该档案没有附件简历'); return }
  try {
    await downloadResume(row.id, `${row.name || '未命名'}-简历`)
    ElMessage.success('已开始下载')
  } catch (e) {
    ElMessage.error('下载失败：' + (e.message || ''))
  }
}

// 查询条件（与后端 TalentQuery 对齐）
// hq+  批次A：支持 ?tag= 查询参数（标签管理页点「N 人」跳转筛选；route 已在顶部声明）
const query = reactive({
  page: 1, page_size: 10, keyword: '', status: null, source: null, tag: route.query.tag || '',
})

async function load() {
  loading.value = true
  try {
    const res = await listTalents(query)
    rows.value = res.data.items
    total.value = res.data.meta.total
  } finally {
    loading.value = false
  }
}

function openDetail(row) {
  // hq+  跳转到详情页（静态路由，不依赖菜单种子，刷新不丢）
  router.push(`/talent/detail/${row.id}`)
}

function openEdit(_row) {
  // hq+  批次2.2 已实现：跳到编辑页（列表里点「编辑」时带 id，点顶部「新增/解析」时无参）
  if (_row) router.push(`/talent/edit/${_row.id}`)
  else router.push('/talent/new')
}

// hq+  段A：原 list.vue 内嵌的上传 dialog 已被迁移到独立页 /talent/upload（ResumeImport.vue）。
//      上传入口改为路由跳转，避免功能重复。

async function del(row) {
  await ElMessageBox.confirm(`确定删除人才「${row.name}」？该操作为软删除。`, '提示', { type: 'warning' })
  await deleteTalent(row.id)
  ElMessage.success('已删除')
  // 列表可能在最后一页最后一行的删除后变成空页，自动回退
  if (rows.value.length === 1 && query.page > 1) query.page -= 1
  load()
}

function resetQuery() {
  Object.assign(query, { page: 1, page_size: 10, keyword: '', status: null, source: null, tag: '' })
  load()
}

// hq+  批次A：清除 tag 筛选（重新加载全量）
function clearTag() { query.tag = ''; query.page = 1; load() }

// hq+  批次2.3c：语义搜索模式
const semanticOpen = ref(false)
const semanticQ = ref('')
const semanticHits = ref([])
const semanticBusy = ref(false)
async function doSemanticSearch() {
  const q = semanticQ.value.trim()
  if (!q) { ElMessage.warning('请输入问题'); return }
  semanticBusy.value = true
  try {
    const res = await semanticSearchTalent(q, 10)
    // 袁文武返回数组 [{talent_id, name, score, match_reason, snippet}]
    const arr = Array.isArray(res.data) ? res.data : (res.data?.hits || [])
    semanticHits.value = arr
    if (!semanticHits.value.length) ElMessage.info('没有召回结果，试试更宽泛的描述')
  } catch (e) {
    ElMessage.error('语义搜索失败：' + (e.message || ''))
  } finally {
    semanticBusy.value = false
  }
}
function toggleSemantic() {
  semanticOpen.value = !semanticOpen.value
  if (!semanticOpen.value) { semanticHits.value = []; semanticQ.value = '' }
}
function jumpToTalent(tid) {
  if (tid) router.push(`/talent/detail/${tid}`)
}

const sourceLabel = (s) => ({ manual: '人工', import: '导入', agent_parsed: 'AI 解析' }[s] || s)
const sourceTag = (s) => ({ manual: 'info', import: 'success', agent_parsed: 'primary' }[s] || '')

onMounted(load)
</script>

<template>
  <el-card>
    <!-- 顶部筛选条 -->
    <div class="bar">
      <el-input v-model="query.keyword" placeholder="按姓名/手机/邮箱" style="width:220px"
        clearable @keyup.enter="query.page=1;load()" />
      <el-select v-model="query.status" placeholder="状态" clearable style="width:120px">
        <el-option label="在档" :value="1" />
        <el-option label="失效" :value="0" />
      </el-select>
      <el-select v-model="query.source" placeholder="来源" clearable style="width:120px">
        <el-option label="人工录入" value="manual" />
        <el-option label="批量导入" value="import" />
        <el-option label="AI 解析" value="agent_parsed" />
      </el-select>
      <el-button type="primary" @click="query.page=1;load()">查询</el-button>
      <el-button @click="resetQuery">重置</el-button>
      <!-- hq+  批次A：按标签筛选徽标 -->
      <el-tag v-if="query.tag" type="warning" closable @close="clearTag">
        标签筛选：{{ query.tag }}
      </el-tag>
      <!-- hq+  批次2.3c：语义搜索切换 -->
      <el-button :type="semanticOpen ? 'success' : 'warning'" plain @click="toggleSemantic">
        {{ semanticOpen ? '关闭语义搜索' : '🔍 语义搜索' }}
      </el-button>
      <div style="flex:1" />
      <!-- hq+  段A：跳转到独立「简历智能解析」分模块页面 -->
      <el-button type="primary" plain @click="router.push('/talent/upload')">导入/解析简历</el-button>
      <el-button type="success" plain @click="router.push('/talent/new')">新增人才</el-button>
    </div>

    <!-- hq+  批次2.3c：语义搜索面板 -->
    <div v-if="semanticOpen" class="semantic">
      <el-input
        v-model="semanticQ"
        type="textarea"
        :rows="2"
        placeholder="例如：擅长数字化转型、有3年以上AI项目经验的骨干人才"
        @keydown.ctrl.enter.prevent="doSemanticSearch"
      />
      <div class="semantic-actions">
        <el-button type="primary" :loading="semanticBusy" :disabled="!semanticQ.trim()" @click="doSemanticSearch">
          语义召回
        </el-button>
        <span class="hint">Ctrl + Enter 提交；基于 Milvus 向量召回 + 候选人画像</span>
      </div>
      <el-table v-if="semanticHits.length" :data="semanticHits" stripe size="small" style="margin-top:10px">
        <el-table-column label="姓名" min-width="120">
          <template #default="{ row }">
            <el-link v-if="row.talent_id" type="primary" :underline="false" @click="jumpToTalent(row.talent_id)">
              {{ row.name || row.talent?.name || `#${row.talent_id}` }}
            </el-link>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="相似度" width="120">
          <template #default="{ row }">
            <el-progress :percentage="Math.min(100, Math.round((row.score || 0) * 100))" />
          </template>
        </el-table-column>
        <el-table-column label="命中说明" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">{{ row.match_reason || row.snippet || row.preview || '—' }}</template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 列表 -->
    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="64" />
      <el-table-column prop="name" label="姓名" min-width="100" />
      <el-table-column prop="current_title" label="现职称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="current_company" label="当前公司" min-width="140" show-overflow-tooltip />
      <el-table-column prop="years_experience" label="年限" width="70" />
      <el-table-column prop="highest_education" label="学历" width="100" />
      <!-- hq+  附件简历列：有 object_key 或 resume_file 才显示操作 -->
      <el-table-column label="附件简历" width="150">
        <template #default="{ row }">
          <template v-if="row.object_key || row.resume_file">
            <el-button link type="primary" @click="openPreview(row)">预览</el-button>
            <el-button link type="success" @click="doDownload(row)">下载</el-button>
          </template>
          <span v-else style="color:#9ca3af;font-size:12px">—</span>
        </template>
      </el-table-column>
      <el-table-column label="来源" width="100">
        <template #default="{ row }">
          <el-tag :type="sourceTag(row.resume_source)" size="small">{{ sourceLabel(row.resume_source) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '在档' : '失效' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">查看</el-button>
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="del(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      style="margin-top:14px"
      layout="total, prev, pager, next, jumper"
      :total="total"
      v-model:current-page="query.page"
      :page-size="query.page_size"
      @current-change="load"
    />
  </el-card>
  <!-- hq+  段A：原内嵌的上传 dialog 已迁移到独立页 /talent/upload（ResumeImport.vue） -->

  <!-- hq+  附件简历预览 dialog -->
  <el-dialog v-model="preview.visible" :title="`附件预览 · ${preview.name}`" width="70%" top="4vh"
    destroy-on-close @closed="closePreview">
    <div v-loading="preview.busy" class="preview-box">
      <iframe v-if="preview.url && !preview.busy" :src="preview.url" class="preview-frame"
        title="简历预览" />
    </div>
    <template #footer>
      <el-button @click="preview.visible=false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.bar { display: flex; gap: 10px; margin-bottom: 14px; align-items: center; flex-wrap: wrap; }

/* hq+  附件预览 */
.preview-box { min-height: 70vh; }
.preview-frame { width: 100%; height: 70vh; border: 1px solid #eef1f5; border-radius: 6px; background: #fff; }

/* hq+  语义搜索面板 */
.semantic { background: #fffbe6; border: 1px solid #fde58e; border-radius: 6px; padding: 12px 14px; margin-bottom: 14px; }
.semantic-actions { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.semantic-actions .hint { color: #9ca3af; font-size: 12px; }
</style>
