<script setup>
import { computed, onMounted, ref } from 'vue'
import { onPullDownRefresh, onShow } from '@dcloudio/uni-app'
import {
  getMessageDetail,
  getUnreadCount,
  listMessages,
  markAllMessagesRead,
  markMessageRead
} from '@/api'

const loading = ref(false)
const failed = ref(false)
const activeTab = ref('all')
const messages = ref([])
const unread = ref(0)
const selected = ref(null)
const readingId = ref(0)
const readingAll = ref(false)

const tabs = computed(() => [
  { key: 'all', text: '全部', count: messages.value.length },
  { key: 'unread', text: '未读', count: unread.value }
])
const hasUnread = computed(() => unread.value > 0)

onMounted(load)
onShow(refreshUnread)

onPullDownRefresh(async () => {
  await load()
  uni.stopPullDownRefresh()
})

async function load() {
  loading.value = true
  failed.value = false
  try {
    const [listResult, countResult] = await Promise.allSettled([
      listMessages({
        page: 1,
        page_size: 30,
        unread_only: activeTab.value === 'unread'
      }),
      getUnreadCount()
    ])
    if (listResult.status === 'rejected') throw listResult.reason
    messages.value = (listResult.value.data?.items || []).map(normalizeMessage)
    unread.value = countResult.status === 'fulfilled'
      ? Number(countResult.value.data?.unread || 0)
      : messages.value.filter((item) => !item.is_read).length
  } catch (error) {
    failed.value = true
    messages.value = []
  } finally {
    loading.value = false
  }
}

async function refreshUnread() {
  try {
    const res = await getUnreadCount()
    unread.value = Number(res.data?.unread || 0)
  } catch (error) {
    unread.value = messages.value.filter((item) => !item.is_read).length
  }
}

async function changeTab(key) {
  if (activeTab.value === key || loading.value) return
  activeTab.value = key
  selected.value = null
  await load()
}

async function openMessage(item) {
  if (!item?.id || readingId.value) return
  readingId.value = item.id
  selected.value = item
  try {
    if (!item.is_read) {
      await markMessageRead(item.id)
      patchRead(item.id)
    }
    const res = await getMessageDetail(item.id)
    selected.value = normalizeMessage({ ...item, ...(res.data || {}), is_read: true })
  } catch (error) {
    selected.value = { ...item, is_read: true }
  } finally {
    readingId.value = 0
  }
}

async function readAll() {
  if (!hasUnread.value || readingAll.value) return
  readingAll.value = true
  try {
    const res = await markAllMessagesRead()
    messages.value = messages.value.map((item) => ({ ...item, is_read: true }))
    unread.value = 0
    uni.showToast({
      title: `已读 ${Number(res.data?.updated || 0)} 条`,
      icon: 'success'
    })
    if (activeTab.value === 'unread') await load()
  } finally {
    readingAll.value = false
  }
}

function closeDetail() {
  selected.value = null
}

function patchRead(id) {
  let changed = false
  messages.value = messages.value.map((item) => {
    if (Number(item.id) !== Number(id) || item.is_read) return item
    changed = true
    return { ...item, is_read: true }
  })
  if (changed) unread.value = Math.max(0, unread.value - 1)
}

function normalizeMessage(row = {}) {
  const type = row.type_code || row.msg_type || row.type || 'system'
  return {
    id: Number(row.id),
    title: row.title || typeText(type),
    content: row.content || '',
    type_code: type,
    biz_type: row.biz_type || '',
    biz_id: row.biz_id || null,
    status: Number(row.status ?? 1),
    is_read: Boolean(row.is_read),
    created_at: row.created_at || ''
  }
}

function typeText(type) {
  const dict = {
    system: '系统公告',
    assess: '测评提醒',
    assessment: '测评提醒',
    train: '培训通知',
    training: '培训通知',
    approve: '审批消息',
    recommend: '推荐消息',
    matching: '岗位匹配',
    match: '岗位匹配'
  }
  return dict[type] || '平台消息'
}

function typeClass(type) {
  if (type === 'assess' || type === 'assessment') return 'tag-assessment'
  if (type === 'train' || type === 'training') return 'tag-training'
  if (type === 'matching' || type === 'match' || type === 'recommend') return 'tag-matching'
  if (type === 'approve') return 'tag-approve'
  return 'tag-system'
}

function formatTime(value) {
  if (!value) return ''
  const text = String(value).replace('T', ' ')
  return text.length > 16 ? text.slice(0, 16) : text
}
</script>

<template>
  <view class="wrap">
    <view class="hero">
      <view>
        <view class="hero-title">消息中心</view>
        <view class="hero-sub">{{ unread ? `${unread} 条未读消息` : '消息已全部读完' }}</view>
      </view>
      <button class="read-all" :disabled="!hasUnread || readingAll" :loading="readingAll" @click="readAll">
        全部已读
      </button>
    </view>

    <view class="tabs">
      <view
        v-for="tab in tabs"
        :key="tab.key"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        @click="changeTab(tab.key)"
      >
        <text>{{ tab.text }}</text>
        <text class="tab-count">{{ tab.count }}</text>
      </view>
    </view>

    <view v-if="loading" class="state">加载中...</view>
    <view v-else-if="failed" class="state failed">
      <text>消息加载失败</text>
      <button class="retry" @click="load">重试</button>
    </view>
    <view v-else-if="!messages.length" class="state">
      <text>{{ activeTab === 'unread' ? '暂无未读消息' : '暂无消息' }}</text>
    </view>

    <view v-else class="list">
      <view
        v-for="item in messages"
        :key="item.id"
        class="message"
        :class="{ read: item.is_read }"
        @click="openMessage(item)"
      >
        <view class="message-main">
          <view class="message-title">
            <text class="title-text">{{ item.title }}</text>
            <text v-if="!item.is_read" class="dot" />
          </view>
          <view class="message-content">{{ item.content || '暂无消息内容' }}</view>
          <view class="message-meta">
            <text>{{ formatTime(item.created_at) }}</text>
            <text v-if="item.biz_type">{{ item.biz_type }}</text>
          </view>
        </view>
        <view class="tag" :class="typeClass(item.type_code)">
          {{ typeText(item.type_code) }}
        </view>
      </view>
    </view>

    <view v-if="selected" class="detail-mask" @click="closeDetail">
      <view class="detail" @click.stop>
        <view class="detail-head">
          <view>
            <view class="detail-title">{{ selected.title }}</view>
            <view class="detail-time">{{ formatTime(selected.created_at) }}</view>
          </view>
          <view class="close" @click="closeDetail">关闭</view>
        </view>
        <view class="detail-tag" :class="typeClass(selected.type_code)">
          {{ typeText(selected.type_code) }}
        </view>
        <view class="detail-content">{{ selected.content || '暂无消息内容' }}</view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.wrap {
  min-height: 100vh;
  padding: 24rpx 24rpx 48rpx;
  background: #f6f7f9;
  box-sizing: border-box;
}
.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  padding: 30rpx;
  border-radius: 24rpx;
  background: #fff;
  box-shadow: 0 4rpx 16rpx rgba(16, 24, 40, 0.05);
}
.hero-title {
  color: #111827;
  font-size: 36rpx;
  font-weight: 700;
  line-height: 1.3;
}
.hero-sub {
  margin-top: 8rpx;
  color: #6b7280;
  font-size: 24rpx;
}
.read-all {
  width: 172rpx;
  height: 64rpx;
  line-height: 64rpx;
  margin: 0;
  padding: 0;
  border-radius: 12rpx;
  background: #2563eb;
  color: #fff;
  font-size: 24rpx;
}
.read-all[disabled] {
  background: #d7dce4;
}
.tabs {
  display: flex;
  gap: 14rpx;
  margin: 24rpx 0;
}
.tab {
  min-width: 154rpx;
  height: 64rpx;
  padding: 0 24rpx;
  border-radius: 12rpx;
  background: #fff;
  color: #6b7280;
  font-size: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
}
.tab.active {
  background: #111827;
  color: #fff;
}
.tab-count {
  min-width: 34rpx;
  height: 34rpx;
  line-height: 34rpx;
  border-radius: 17rpx;
  text-align: center;
  font-size: 20rpx;
  background: rgba(148, 163, 184, 0.18);
}
.list {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}
.message {
  display: flex;
  align-items: flex-start;
  gap: 20rpx;
  padding: 26rpx;
  border-radius: 18rpx;
  background: #fff;
  box-shadow: 0 4rpx 16rpx rgba(16, 24, 40, 0.04);
}
.message.read {
  opacity: 0.78;
}
.message-main {
  flex: 1;
  min-width: 0;
}
.message-title {
  display: flex;
  align-items: center;
  gap: 10rpx;
}
.title-text {
  max-width: 430rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #111827;
  font-size: 29rpx;
  font-weight: 650;
}
.dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
  background: #ef4444;
  flex-shrink: 0;
}
.message-content {
  margin-top: 10rpx;
  color: #6b7280;
  font-size: 24rpx;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.message-meta {
  display: flex;
  gap: 18rpx;
  margin-top: 14rpx;
  color: #a1a7b3;
  font-size: 21rpx;
}
.tag,
.detail-tag {
  min-width: 104rpx;
  height: 42rpx;
  line-height: 42rpx;
  border-radius: 10rpx;
  text-align: center;
  font-size: 21rpx;
  flex-shrink: 0;
}
.tag-assessment {
  background: #fef3c7;
  color: #a16207;
}
.tag-training {
  background: #dcfce7;
  color: #15803d;
}
.tag-matching {
  background: #e0e7ff;
  color: #3730a3;
}
.tag-approve {
  background: #fee2e2;
  color: #b91c1c;
}
.tag-system {
  background: #e5e7eb;
  color: #374151;
}
.state {
  min-height: 360rpx;
  padding-top: 120rpx;
  color: #9ca3af;
  text-align: center;
  font-size: 26rpx;
  box-sizing: border-box;
}
.failed {
  color: #ef4444;
}
.retry {
  width: 168rpx;
  height: 64rpx;
  line-height: 64rpx;
  margin-top: 22rpx;
  border-radius: 12rpx;
  background: #111827;
  color: #fff;
  font-size: 24rpx;
}
.detail-mask {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  z-index: 20;
  display: flex;
  align-items: flex-end;
  background: rgba(17, 24, 39, 0.38);
}
.detail {
  width: 100%;
  max-height: 70vh;
  padding: 32rpx 30rpx 48rpx;
  border-radius: 28rpx 28rpx 0 0;
  background: #fff;
  box-sizing: border-box;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  gap: 24rpx;
}
.detail-title {
  color: #111827;
  font-size: 32rpx;
  font-weight: 700;
  line-height: 1.35;
}
.detail-time {
  margin-top: 8rpx;
  color: #9ca3af;
  font-size: 22rpx;
}
.close {
  width: 96rpx;
  color: #2563eb;
  font-size: 24rpx;
  text-align: right;
}
.detail-tag {
  margin-top: 24rpx;
}
.detail-content {
  margin-top: 22rpx;
  color: #374151;
  font-size: 27rpx;
  line-height: 1.75;
  white-space: pre-wrap;
}
</style>
