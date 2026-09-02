<template>
  <el-dialog v-model="visible" title="保温跟进" width="540px" append-to-body>
    <template v-if="row">
      <el-descriptions :column="2" border size="small" style="margin-bottom:12px">
        <el-descriptions-item label="人才ID">{{ row.talent_id }}</el-descriptions-item>
        <el-descriptions-item label="匹配度">
          {{ row.score != null ? Number(row.score).toFixed(1) : '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="当前保温状态">
          <el-tag :type="warmState(row).type" size="small" effect="dark">{{ warmState(row).label }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="跟进时间">{{ fmtTime(row.last_follow_up) || '—' }}</el-descriptions-item>
      </el-descriptions>

      <div class="fw-title">快捷话术模板（点击填入）</div>
      <div class="fw-tpl">
        <el-button v-for="t in TEMPLATES" :key="t.key" type="primary" plain size="small"
          @click="fill(t)">{{ t.label }}</el-button>
      </div>

      <div class="fw-title">跟进记录（可编辑）</div>
      <el-input v-model="note" type="textarea" :rows="4"
        placeholder="记录本次互动内容，如：候选人表示下周一有空面试…" />
    </template>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">
        提交并加热（刷新跟进时间）
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { updateWarm } from '@/api/matching'
import { warmState, fmtTime } from '@/utils/matchingWarm'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  row: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'success'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
const note = ref('')
const submitting = ref(false)

const TEMPLATES = [
  { key: 'holiday', label: '发送节日问候', text: '[姓名] 您好！节日将至，提前祝您节日快乐！也期待未来有机会与您进一步交流～' },
  { key: 'news', label: '推送公司动态', text: '[姓名] 您好！跟您同步个好消息：公司最近在您关注的领域有了新进展，有空欢迎聊聊～' },
  { key: 'greet', label: '询问近况', text: '[姓名] 您好！最近还好吗？想跟您聊聊近况，也看看您是否还有新的想法～' },
]

watch(() => props.modelValue, (v) => {
  if (v) note.value = ''
})

function fill(t) {
  note.value = String(t.text)
  ElMessage.success(`已填入话术：${t.label}`)
}

async function submit() {
  const row = props.row
  if (!row) return
  submitting.value = true
  try {
    // 提交 = 一次真实跟进：等级提到 ≥ 中(2)，后端刷新 last_follow_up=now → 状态立即回火热
    const level = Math.max(row.warm_level || 0, 2)
    const res = await updateWarm(row.id, level)
    const data = res.data || {}
    emit('success', {
      id: row.id,
      warm_level: data.warm_level ?? level,
      last_follow_up: data.last_follow_up || null,
    })
    ElMessage.success('已记录保温跟进，状态已加热')
    visible.value = false
  } catch { /* error shown by interceptor */ } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.fw-title { font-weight: 600; margin: 14px 0 8px; color: #1f2937; font-size: 13px; }
.fw-tpl { display: flex; gap: 8px; flex-wrap: wrap; }
</style>
