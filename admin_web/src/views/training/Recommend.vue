<template>
  <div class="page">
    <div class="toolbar">
      <div class="title">智能推荐计划</div>
      <div class="sub">基于人才研判短板 + 适配岗位要求，Agent 自动生成培训计划（先预览，确认后再推送）</div>
    </div>

    <el-card shadow="never" style="margin-bottom: 12px">
      <el-form label-width="100px" :inline="false">
        <el-form-item label="选择人才">
          <el-select v-model="selectedTalentIds" multiple filterable remote
                     :remote-method="searchTalents" :loading="talentLoading"
                     placeholder="支持多选（输入姓名搜索）" style="width: 480px">
            <el-option v-for="t in talentOptions" :key="t.id" :value="t.id"
                       :label="`${t.name}（${t.current_title || '—'}）`" />
          </el-select>
          <el-button style="margin-left: 8px" @click="selectAllInFilter">选择当前筛选</el-button>
          <el-button @click="clearSelected">清空</el-button>
        </el-form-item>
        <el-form-item label="计划标题">
          <el-input v-model="title" style="width: 480px" placeholder="留空则使用默认标题" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="generating" :disabled="!selectedTalentIds.length"
                     @click="onBatchGenerate">
            <el-icon style="margin-right:4px"><MagicStick /></el-icon>
            生成计划（不推送）
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="card-head">
          <span>本次生成结果</span>
          <el-tag size="small" type="info">共 {{ generatedPlans.length }} 条</el-tag>
        </div>
      </template>
      <el-table :data="generatedPlans" v-loading="generating" empty-text="尚无结果，请先选择人才并点击生成">
        <el-table-column label="人才" prop="talent_name" min-width="140" />
        <el-table-column label="适配岗位" min-width="160">
          <template #default="{ row }">
            <span v-if="row.positions?.length">
              {{ row.positions.map(p => p.name).join('、') }}
            </span>
            <span v-else style="color:#9ca3af">—</span>
          </template>
        </el-table-column>
        <el-table-column label="短板标签" min-width="220">
          <template #default="{ row }">
            <el-tag v-for="t in row.shortage_tags" :key="t" size="small" type="danger" effect="plain" style="margin-right:4px">{{ t }}</el-tag>
            <span v-if="!row.shortage_tags?.length" style="color:#9ca3af">—</span>
          </template>
        </el-table-column>
        <el-table-column label="岗位需求" min-width="200">
          <template #default="{ row }">
            <el-tag v-for="t in row.position_tags" :key="t" size="small" type="success" effect="plain" style="margin-right:4px">{{ t }}</el-tag>
            <span v-if="!row.position_tags?.length" style="color:#9ca3af">—</span>
          </template>
        </el-table-column>
        <el-table-column label="推荐课程" min-width="260">
  <template #default="{ row }">
    <el-tag v-for="c in row.courses" :key="c.id" size="small" effect="plain" style="margin-right:4px">{{ c.title }}</el-tag>
    <span v-if="!row.courses?.length" style="color:#9ca3af">—</span>
  </template>
</el-table-column>
        <el-table-column label="选课数" prop="course_ids.length" width="80" align="center" />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button v-if="!row.pushed" type="primary" size="small"
                       :loading="row.pushing" @click="onPush(row)">
              推送
            </el-button>
            <el-tag v-else type="success" size="small">已推送</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import http from '@/utils/request'
import { listTalentOptions } from '@/api/training'

const selectedTalentIds = ref([])
const title = ref('')
const generating = ref(false)
const generatedPlans = ref([])

const talentOptions = ref([])
const talentLoading = ref(false)
async function searchTalents(kw) {
  if (!kw) return
  talentLoading.value = true
  try {
    const res = await listTalentOptions(kw)
    talentOptions.value = res.data || []
  } finally { talentLoading.value = false }
}
function selectAllInFilter() {
  selectedTalentIds.value = talentOptions.value.map(t => t.id)
}
function clearSelected() {
  selectedTalentIds.value = []
}

// 1. 生成（预览）：只调 /agent/preview，不落库
async function onBatchGenerate() {
  if (!selectedTalentIds.value.length) return ElMessage.warning('请至少选择 1 位人才')
  generating.value = true
  generatedPlans.value = []
  const nameMap = new Map(talentOptions.value.map(t => [t.id, t.name]))
  const failed = []
  for (const tid of selectedTalentIds.value) {
    try {
      const res = await http.post('/training/agent/preview', { talent_id: tid })
      generatedPlans.value.push({
        ...res.data,                 // 含 course_ids, shortage_tags, position_tags, positions, courses
        talent_id: tid,
        talent_name: nameMap.get(tid) || `人才#${tid}`,
        pushed: false,
        pushing: false,
      })
    } catch (e) {
      failed.push({ id: tid, name: nameMap.get(tid) || `人才#${tid}`, msg: e.message })
    }
  }
  generating.value = false
  if (failed.length) {
    ElMessageBox.alert(failed.map(f => `${f.name}: ${f.msg}`).join('\n'), `${failed.length} 位人才预览失败`, { type: 'warning' })
  } else {
    ElMessage.success(`已为 ${selectedTalentIds.value.length} 位人才生成预览（未落库）`)
  }
}

// 2. 推送（确认）：调 /agent/recommend，真正建计划 + 发消息
async function onPush(row) {
  try {
    await ElMessageBox.confirm(`确认推送「${row.talent_name}」的学习计划吗？推送后将正式创建计划并通知本人。`, '提示', { type: 'info' })
  } catch { return }
  row.pushing = true
  try {
    await http.post('/training/agent/recommend', {
      talent_id: row.talent_id,
      course_ids: row.course_ids,
      shortages: row.shortage_tags || [],
      title: title.value || '个性化培训计划',
      push: true,   // 推送时建计划 + 发消息
    })
    row.pushed = true
    ElMessage.success('已推送（计划已创建）')
  } catch (e) {
    ElMessage.error('推送失败：' + e.message)
  } finally {
    row.pushing = false
  }
}
</script>

<style scoped>
.page { padding: 4px 2px; }
.toolbar { margin-bottom: 16px; }
.title { font-size: 16px; font-weight: 600; color: #1f2937; }
.sub { font-size: 12px; color: #9ca3af; margin-top: 4px; }
.card-head { display: flex; align-items: center; gap: 10px; }
</style>
