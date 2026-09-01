<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createDictItem, createDictType, deleteDictItem, listDictItems, listDictTypes } from '@/api/dict'

const types = ref([])
const currentType = ref(null)
const items = ref([])
const loading = ref(false)

// 类型对话框
const typeDialog = reactive({ visible: false })
const typeForm = reactive({ code: '', name: '', remark: '' })

// 条目对话框
const itemDialog = reactive({ visible: false })
const itemForm = reactive({ id: null, type_code: '', label: '', value: '', sort: 0, status: 1 })

async function loadTypes() {
  const res = await listDictTypes()
  types.value = res.data
  if (!currentType.value && types.value.length) selectType(types.value[0])
}

async function selectType(t) {
  currentType.value = t
  await loadItems(t.code)
}

async function loadItems(typeCode) {
  loading.value = true
  try {
    const res = await listDictItems(typeCode)
    items.value = res.data
  } finally {
    loading.value = false
  }
}

async function saveType() {
  if (!typeForm.code || !typeForm.name) {
    ElMessage.warning('请填写编码和名称')
    return
  }
  await createDictType(typeForm)
  ElMessage.success('已创建字典类型')
  typeDialog.visible = false
  Object.assign(typeForm, { code: '', name: '', remark: '' })
  loadTypes()
}

function openItem() {
  if (!currentType.value) {
    ElMessage.warning('请先选择左侧字典类型')
    return
  }
  Object.assign(itemForm, { id: null, type_code: currentType.value.code, label: '', value: '', sort: 0, status: 1 })
  itemDialog.visible = true
}

async function saveItem() {
  if (!itemForm.label || !itemForm.value) {
    ElMessage.warning('请填写标签和值')
    return
  }
  await createDictItem(itemForm)
  ElMessage.success('已添加字典项')
  itemDialog.visible = false
  loadItems(currentType.value.code)
}

async function delItem(row) {
  await ElMessageBox.confirm(`确定删除字典项「${row.label}」？`, '提示', { type: 'warning' })
  await deleteDictItem(row.id)
  ElMessage.success('已删除')
  loadItems(currentType.value.code)
}

onMounted(loadTypes)
</script>

<template>
  <el-row :gutter="16">
    <el-col :span="8">
      <el-card>
        <template #header>
          <div class="card-head">
            <span>字典类型</span>
            <el-button size="small" type="primary" @click="typeDialog.visible=true">新增类型</el-button>
          </div>
        </template>
        <div v-for="t in types" :key="t.id" class="type-item" :class="{ on: currentType?.id === t.id }" @click="selectType(t)">
          <div class="t-name">{{ t.name }}</div>
          <div class="t-code">{{ t.code }}</div>
        </div>
        <el-empty v-if="!types.length" description="暂无字典类型" :image-size="60" />
      </el-card>
    </el-col>

    <el-col :span="16">
      <el-card>
        <template #header>
          <div class="card-head">
            <span>字典项 · {{ currentType?.name || '未选择' }}</span>
            <el-button size="small" type="primary" @click="openItem">新增字典项</el-button>
          </div>
        </template>
        <el-table :data="items" v-loading="loading" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="label" label="显示名" min-width="140" />
          <el-table-column prop="value" label="存储值" min-width="140" />
          <el-table-column prop="sort" label="排序" width="80" />
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.status === 1 ? 'success' : 'info'">{{ row.status === 1 ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90">
            <template #default="{ row }">
              <el-button link type="danger" @click="delItem(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-col>
  </el-row>

  <el-dialog v-model="typeDialog.visible" title="新增字典类型" width="440px">
    <el-form label-width="70px">
      <el-form-item label="编码"><el-input v-model="typeForm.code" placeholder="如 degree / gender" /></el-form-item>
      <el-form-item label="名称"><el-input v-model="typeForm.name" placeholder="如 学历" /></el-form-item>
      <el-form-item label="备注"><el-input v-model="typeForm.remark" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="typeDialog.visible=false">取消</el-button>
      <el-button type="primary" @click="saveType">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="itemDialog.visible" title="新增字典项" width="440px">
    <el-form label-width="70px">
      <el-form-item label="显示名"><el-input v-model="itemForm.label" placeholder="如 本科" /></el-form-item>
      <el-form-item label="存储值"><el-input v-model="itemForm.value" placeholder="如 bachelor" /></el-form-item>
      <el-form-item label="排序"><el-input-number v-model="itemForm.sort" :min="0" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="itemDialog.visible=false">取消</el-button>
      <el-button type="primary" @click="saveItem">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.card-head { display: flex; justify-content: space-between; align-items: center; }
.type-item { padding: 10px 12px; border-radius: 8px; cursor: pointer; margin-bottom: 6px; border: 1px solid #eef1f5; }
.type-item:hover { background: #f5f7fa; }
.type-item.on { background: #eaf0ff; border-color: #2563eb; }
.t-name { font-size: 14px; color: #1f2937; }
.t-code { font-size: 12px; color: #9ca3af; margin-top: 2px; }
</style>
