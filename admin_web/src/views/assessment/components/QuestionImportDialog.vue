<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { downloadQuestionImportTemplate, importQuestions } from '@/api/assessment'

const props = defineProps({
  modelValue: Boolean,
  bank: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'imported'])

const selectedFile = ref(null)
const fileList = ref([])
const importing = ref(false)
const downloading = ref(false)
const result = ref(null)

function close() {
  emit('update:modelValue', false)
}

function handleChange(file) {
  selectedFile.value = file.raw || null
  result.value = null
}

function handleRemove() {
  selectedFile.value = null
  result.value = null
}

function handleExceed() {
  ElMessage.warning('每次只能选择一个文件')
}

async function downloadTemplate() {
  downloading.value = true
  try {
    const blob = await downloadQuestionImportTemplate()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '智能测评题目导入模板.xlsx'
    link.click()
    URL.revokeObjectURL(url)
  } finally {
    downloading.value = false
  }
}

async function submit() {
  if (!props.bank?.id) return ElMessage.warning('请先选择题库')
  if (!selectedFile.value) return ElMessage.warning('请选择导入文件')
  importing.value = true
  try {
    const response = await importQuestions(props.bank.id, selectedFile.value)
    result.value = response.data
    if (response.data.failed_count) {
      ElMessage.warning(`发现 ${response.data.failed_count} 行错误，本次未写入数据`)
      return
    }
    ElMessage.success(`成功导入 ${response.data.imported_count} 道题目`)
    emit('imported')
    close()
  } finally {
    importing.value = false
  }
}

watch(() => props.modelValue, (visible) => {
  if (!visible) return
  selectedFile.value = null
  fileList.value = []
  result.value = null
})
</script>

<template>
  <el-dialog :model-value="modelValue" title="批量导入题目" width="680px" @close="close">
    <el-descriptions :column="1" border class="import-target">
      <el-descriptions-item label="目标题库">{{ bank?.name || '未选择' }}</el-descriptions-item>
    </el-descriptions>
    <div class="import-toolbar">
      <el-button :loading="downloading" @click="downloadTemplate">下载 Excel 模板</el-button>
    </div>
    <el-upload
      v-model:file-list="fileList"
      drag
      action=""
      accept=".xlsx,.csv"
      :auto-upload="false"
      :limit="1"
      :on-change="handleChange"
      :on-remove="handleRemove"
      :on-exceed="handleExceed"
    >
      <div class="upload-title">选择或拖入 .xlsx / .csv 文件</div>
      <template #tip><div class="el-upload__tip">单次最多 1000 道题，文件不超过 5 MB</div></template>
    </el-upload>
    <el-alert
      v-if="result?.failed_count"
      :title="`校验未通过：${result.failed_count} 行错误，本次未导入`"
      type="error"
      :closable="false"
      class="result-alert"
    />
    <el-table v-if="result?.errors?.length" :data="result.errors" max-height="260" stripe>
      <el-table-column prop="row" label="行号" width="70" />
      <el-table-column prop="content" label="题干" min-width="180" show-overflow-tooltip />
      <el-table-column prop="message" label="错误原因" min-width="240" />
    </el-table>
    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="importing" @click="submit">开始导入</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.import-target { margin-bottom: 14px; }
.import-toolbar { display: flex; justify-content: flex-end; margin-bottom: 12px; }
.upload-title { color: #303b50; line-height: 1.8; }
.result-alert { margin: 16px 0 10px; }
</style>
