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
import UiState from '@/components/UiState.vue'

const loading = ref(false)
const failed = ref(false)
const activeTab = ref('all')
const messages = ref([])
const total = ref(0)
const unread = ref(0)
const selected = ref(null)
const readingId = ref(0)
const readingAll = ref(false)

const tabs = computed(() => [
  { key: 'all', text: '全部', count: total.value },
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
    if (activeTab.value === 'all') {
      total.value = Number(listResult.value.data?.meta?.total ?? messages.value.length)
    }
    unread.value = countResult.status === 'fulfilled'
      ? Number(countResult.value.data?.unread || 0)
      : messages.value.filter((item) => !item.is_read).length
  } catch (error) {
    failed.value = true
    messages.value = []
    if (activeTab.value === 'all') total.value = 0
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
    system: '系统',
    assess: '测评',
    assessment: '测评',
    train: '培训',
    training: '培训',
    approve: '审批',
    recommend: 'AI 推荐',
    matching: '岗位',
    match: '岗位'
  }
  return dict[type] || '平台'
}

function typeClass(type) {
  if (type === 'assess' || type === 'assessment') return 'tag-assessment'
  if (type === 'train' || type === 'training') return 'tag-training'
  if (type === 'matching' || type === 'match' || type === 'recommend') return 'tag-matching'
  if (type === 'approve') return 'tag-approve'
  return 'tag-system'
}

function actionFor(item) {
  const type = item?.type_code
  if (type === 'assess' || type === 'assessment') return { text: '去测评', url: '/pages/assessment/assessment', tab: true }
  if (type === 'train' || type === 'training') return { text: '继续学习', url: '/pages/study/study', tab: true }
  if (type === 'matching' || type === 'match' || type === 'recommend') return { text: '看岗位', url: '/pages/matching/agent' }
  return null
}

function goAction(item) {
  const action = actionFor(item)
  if (!action) return
  closeDetail()
  if (action.tab) {
    uni.switchTab({ url: action.url })
    return
  }
  uni.navigateTo({ url: action.url })
}

function formatTime(value) {
  if (!value) return ''
  const text = String(value).replace('T', ' ')
  return text.length > 16 ? text.slice(0, 16) : text
}
</script>

<template>
  <view class="app-page message-page">
    <view class="hero surface">
      <view>
        <text class="eyebrow">成长事件</text>
        <text class="hero-title">消息中心</text>
        <text class="hero-sub">{{ unread ? `${unread} 条未读消息等待处理` : '当前没有未读成长事件' }}</text>
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

    <UiState v-if="loading" tone="loading" title="正在加载消息" hint="正在同步测评、学习和岗位事件。" />
    <UiState v-else-if="failed" tone="error" title="消息加载失败" hint="请检查网络或稍后重试。" action-text="重试" @action="load" />
    <UiState
      v-else-if="!messages.length"
      :title="activeTab === 'unread' ? '暂无未读消息' : '暂无消息'"
      hint="测评、学习、培训和岗位相关事件会显示在这里。"
    />

    <view v-else class="list">
      <view
        v-for="item in messages"
        :key="item.id"
        class="message surface"
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
        <view class="message-side">
          <view class="tag" :class="typeClass(item.type_code)">{{ typeText(item.type_code) }}</view>
          <view v-if="actionFor(item)" class="next" @click.stop="goAction(item)">{{ actionFor(item).text }}</view>
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
        <view class="detail-tag" :class="typeClass(selected.type_code)">{{ typeText(selected.type_code) }}</view>
        <view class="detail-content">{{ selected.content || '暂无消息内容' }}</view>
        <button v-if="actionFor(selected)" class="detail-action" @click="goAction(selected)">{{ actionFor(selected).text }}</button>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.message-page {
  padding-bottom: 72rpx;
}

.hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24rpx;
  padding: 30rpx;
}

.eyebrow,
.hero-title,
.hero-sub {
  display: block;
}

.eyebrow {
  color: var(--color-coral);
  font-size: 22rpx;
  font-weight: 800;
}

.hero-title {
  margin-top: 8rpx;
  color: var(--color-text);
  font-size: 42rpx;
  font-weight: 800;
  line-height: 1.2;
}

.hero-sub {
  margin-top: 10rpx;
  color: var(--color-muted);
  font-size: 24rpx;
}

.read-all {
  flex-shrink: 0;
  width: 172rpx;
  height: 62rpx;
  margin: 0;
  color: #fff;
  background: var(--color-brand);
  border-radius: var(--radius-sm);
  font-size: 24rpx;
  line-height: 62rpx;
}

.read-all[disabled] {
  color: #A7B7C0;
  background: #EAF2F6;
}

.tabs {
  display: flex;
  gap: 14rpx;
  margin: 24rpx 0;
}

.tab {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  min-width: 154rpx;
  height: 64rpx;
  padding: 0 24rpx;
  color: var(--color-muted);
  background: #EEF7FA;
  border: 1rpx solid transparent;
  border-radius: var(--radius-sm);
  font-size: 24rpx;
  box-sizing: border-box;
}

.tab.active {
  color: var(--color-brand);
  background: #fff;
  border-color: rgba(85, 188, 235, .25);
  font-weight: 700;
}

.tab-count {
  min-width: 34rpx;
  height: 34rpx;
  padding: 0 8rpx;
  color: inherit;
  background: rgba(85, 188, 235, .1);
  border-radius: 17rpx;
  font-size: 20rpx;
  line-height: 34rpx;
  text-align: center;
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
  padding: 24rpx;
}

.message.read {
  opacity: .74;
}

.message-main {
  min-width: 0;
  flex: 1;
}

.message-title {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.title-text {
  max-width: 420rpx;
  overflow: hidden;
  color: var(--color-text);
  font-size: 29rpx;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dot {
  width: 12rpx;
  height: 12rpx;
  flex-shrink: 0;
  background: var(--color-coral);
  border-radius: 50%;
}

.message-content {
  margin-top: 10rpx;
  overflow: hidden;
  color: var(--color-muted);
  font-size: 24rpx;
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.message-meta {
  display: flex;
  gap: 18rpx;
  margin-top: 14rpx;
  color: #9AAAB2;
  font-size: 21rpx;
}

.message-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12rpx;
  flex-shrink: 0;
}

.tag,
.detail-tag {
  min-width: 92rpx;
  height: 42rpx;
  padding: 0 12rpx;
  border-radius: var(--radius-sm);
  font-size: 21rpx;
  line-height: 42rpx;
  text-align: center;
  box-sizing: border-box;
}

.tag-assessment {
  color: var(--color-coral);
  background: var(--color-coral-soft);
}

.tag-training {
  color: var(--color-success);
  background: #E9F8F3;
}

.tag-matching {
  color: var(--color-brand);
  background: var(--color-brand-soft);
}

.tag-approve {
  color: var(--color-danger);
  background: #FFF1EF;
}

.tag-system {
  color: var(--color-muted);
  background: #EEF4F7;
}

.next {
  color: var(--color-brand);
  font-size: 22rpx;
  font-weight: 700;
}

.detail-mask {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32rpx;
  background: rgba(32, 49, 60, .38);
  box-sizing: border-box;
}

.detail {
  width: 100%;
  max-width: 680rpx;
  max-height: 72vh;
  padding: 32rpx 30rpx;
  overflow-y: auto;
  background: #fff;
  border-radius: var(--radius-lg);
  box-sizing: border-box;
}

.detail-head {
  display: flex;
  justify-content: space-between;
  gap: 24rpx;
}

.detail-title {
  color: var(--color-text);
  font-size: 32rpx;
  font-weight: 750;
  line-height: 1.35;
}

.detail-time {
  margin-top: 8rpx;
  color: var(--color-muted);
  font-size: 22rpx;
}

.close {
  width: 96rpx;
  color: var(--color-brand);
  font-size: 24rpx;
  text-align: right;
}

.detail-tag {
  display: inline-block;
  margin-top: 24rpx;
}

.detail-content {
  margin-top: 22rpx;
  color: var(--color-text);
  font-size: 27rpx;
  line-height: 1.75;
  white-space: pre-wrap;
}

.detail-action {
  height: 76rpx;
  margin-top: 28rpx;
  color: #fff;
  background: var(--color-coral);
  border-radius: var(--radius-md);
  font-size: 26rpx;
  line-height: 76rpx;
}
</style>
