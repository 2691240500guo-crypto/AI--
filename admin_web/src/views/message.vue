<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMessageDetail, getUnreadCount, listMyMessages, markMessageRead, pushMessageReminder, sendMessage } from '@/api/message'

const rows = ref([])
const total = ref(0)
const unread = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, page_size: 20, unread_only: false })

const dialog = reactive({ visible: false })
const detail = reactive({ visible: false, row: null, loading: false })
const form = reactive({ type_code: 'system', title: '', content: '', receiver_ids: [], push_miniapp: 0 })
const typeMap = { system: '系统', assess: '测评', train: '培训', approve: '审批', recommend: '推荐' }

async function load() {
  loading.value = true
  try {
    const res = await listMyMessages(query)
    rows.value = res.data.items
    total.value = res.data.meta.total
  } finally {
    loading.value = false
  }
}

async function loadUnread() {
  const res = await getUnreadCount()
  unread.value = res.data.unread
}

async function read(row) {
  if (!row.is_read) {
    await markMessageRead(row.id)
    row.is_read = true
    loadUnread()
  }
}

async function openDetail(row) {
  detail.loading = true
  try {
    detail.row = (await getMessageDetail(row.id)).data
    detail.visible = true
  } finally {
    detail.loading = false
  }
}

async function doPush(row) {
  await pushMessageReminder(row.id)
  ElMessage.success('已触发补推')
  load()
}

function openSend() {
  Object.assign(form, { type_code: 'system', title: '', content: '', receiver_ids: [], push_miniapp: 0 })
  dialog.visible = true
}

async function send() {
  if (!form.title) {
    ElMessage.warning('请填写标题')
    return
  }
  await sendMessage(form)
  ElMessage.success('已发送')
  dialog.visible = false
  load(); loadUnread()
}

onMounted(() => { load(); loadUnread() })
</script>

<template>
  <el-card>
    <div class="bar">
      <el-button type="primary" @click="openSend">发送消息</el-button>
      <el-switch v-model="query.unread_only" active-text="只看未读" @change="query.page=1;load()" />
      <span class="tip">未读 {{ unread }} 条</span>
    </div>

    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="类型" width="90">
        <template #default="{ row }">
          <el-tag size="small">{{ typeMap[row.type_code] || row.type_code }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="160">
        <template #default="{ row }">
          <span :style="{ fontWeight: row.is_read ? 400 : 600 }">{{ row.title }}</span>
          <el-tag v-if="!row.is_read" type="danger" size="small" style="margin-left:6px">未读</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="content" label="内容" min-width="240" show-overflow-tooltip />
      <el-table-column prop="sender_id" label="发送人ID" width="100" />
      <el-table-column label="推送" width="90">
        <template #default="{ row }">
          <el-tag :type="row.push_miniapp === 1 ? 'success' : 'info'" size="small">{{ row.push_miniapp === 1 ? '已推' : '未推' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="180" />
      <el-table-column label="操作" width="210">
        <template #default="{ row }">
          <el-button link type="primary" @click="read(row)">{{ row.is_read ? '已读' : '标记已读' }}</el-button>
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button link type="warning" :disabled="row.push_miniapp === 1" @click="doPush(row)">补推</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination style="margin-top:14px;justify-content:flex-end" layout="total, prev, pager, next" :total="total"
      v-model:current-page="query.page" :page-size="query.page_size" @current-change="load" />
  </el-card>

  <el-dialog v-model="dialog.visible" title="发送消息" width="520px">
    <el-form label-width="90px">
      <el-form-item label="类型">
        <el-select v-model="form.type_code">
          <el-option label="系统" value="system" />
          <el-option label="测评" value="assess" />
          <el-option label="培训" value="train" />
          <el-option label="审批" value="approve" />
          <el-option label="推荐" value="recommend" />
        </el-select>
      </el-form-item>
      <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
      <el-form-item label="内容"><el-input v-model="form.content" type="textarea" :rows="4" /></el-form-item>
      <el-form-item label="接收人">
        <el-input v-model="form.receiver_ids" placeholder="用户ID，逗号分隔；留空=全员" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialog.visible=false">取消</el-button>
      <el-button type="primary" @click="send">发送</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="detail.visible" title="消息详情" width="560px">
    <el-descriptions v-if="detail.row" :column="1" border>
      <el-descriptions-item label="标题">{{ detail.row.title }}</el-descriptions-item>
      <el-descriptions-item label="类型">{{ typeMap[detail.row.type_code] || detail.row.type_code }}</el-descriptions-item>
      <el-descriptions-item label="内容">{{ detail.row.content }}</el-descriptions-item>
      <el-descriptions-item label="发送人ID">{{ detail.row.sender_id ?? '—' }}</el-descriptions-item>
      <el-descriptions-item label="推送状态">{{ detail.row.push_miniapp === 1 ? '已推' : '未推' }}</el-descriptions-item>
      <el-descriptions-item label="已读状态">{{ detail.row.is_read ? '已读' : '未读' }}</el-descriptions-item>
      <el-descriptions-item label="时间">{{ detail.row.created_at }}</el-descriptions-item>
    </el-descriptions>
  </el-dialog>
</template>

<style scoped>
.bar { display: flex; gap: 14px; margin-bottom: 14px; align-items: center; }
.tip { color: #2563eb; font-size: 13px; }
</style>
