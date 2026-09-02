<script setup>
import { computed, onMounted, ref } from 'vue'
import request from '@/utils/request'

const list = ref([])
const total = ref(0)
const unread = ref(0)
const activeTab = ref('all')

const tabs = computed(() => [
  { key: 'all', text: '全部', count: total.value },
  { key: 'unread', text: '未读', count: unread.value }
])

async function load() {
  const [itemsResult, listResult, unreadResult] = await Promise.all([
    request({
      url: `/messages?page=1&page_size=20&unread_only=${activeTab.value === 'unread'}`,
      method: 'GET'
    }),
    request({ url: '/messages?page=1&page_size=1', method: 'GET' }),
    request({ url: '/messages/unread-count', method: 'GET' })
  ])
  list.value = itemsResult.data?.items || []
  // 全部数量取后端分页元数据，不能用当前页已加载的 items 数量代替。
  total.value = Number(listResult.data?.meta?.total ?? listResult.data?.total ?? list.value.length)
  unread.value = Number(unreadResult.data?.unread ?? list.value.filter((item) => !item.is_read).length)
}
async function read(item) {
  await request({ url: `/messages/${item.id}/read`, method: 'POST', data: {} })
  if (!item.is_read) {
    item.is_read = true
    unread.value = Math.max(0, unread.value - 1)
  }
}
async function changeTab(key) {
  if (activeTab.value === key) return
  activeTab.value = key
  await load()
}
onMounted(load)

// 消息类型 chip 样式（对齐 design/app-prototype.html：未读/新计划/荣誉/公告）
function chipClass(it) {
  if (!it.is_read) return 'chip-o'
  const t = it.msg_type || it.type || ''
  if (t === 'matching' || t === 'match') return 'chip-g'
  if (t === 'system') return 'chip'
  return 'chip'
}
function chipText(it) {
  if (!it.is_read) return '未读'
  const t = it.msg_type || it.type || ''
  if (t === 'matching' || t === 'match') return '预警'
  if (t === 'system') return '公告'
  return '消息'
}
</script>

<template>
  <view class="wrap">
    <view class="title">消息中心</view>
    <view class="tabs">
      <view v-for="tab in tabs" :key="tab.key" class="tab" :class="{ active: activeTab === tab.key }" @click="changeTab(tab.key)">
        <text>{{ tab.text }}</text>
        <text class="tab-count">{{ tab.count }}</text>
      </view>
    </view>
    <view v-if="list.length" class="card">
      <view v-for="it in list" :key="it.id" class="item" :class="{ read: it.is_read }" @click="read(it)">
        <view class="it-left">
          <view class="it-title">{{ it.title }}<text v-if="!it.is_read" class="dot">●</text></view>
          <view class="it-content">{{ it.content }}</view>
        </view>
        <text class="chip" :class="chipClass(it)">{{ chipText(it) }}</text>
      </view>
    </view>
    <view v-else class="empty">
      <view class="empty-ico">📭</view>
      <view class="empty-txt">暂无消息</view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.wrap { padding: 24rpx 24rpx 40rpx; min-height: 100vh; background: #f6f7f9; }
.title { color: #1f2937; font-size: 36rpx; font-weight: 700; margin-bottom: 20rpx; }
.tabs { display: flex; gap: 14rpx; margin-bottom: 20rpx; }
.tab { min-width: 150rpx; height: 64rpx; padding: 0 24rpx; border-radius: 12rpx; background: #fff; color: #6b7280;
  font-size: 24rpx; display: flex; align-items: center; justify-content: center; gap: 10rpx; }
.tab.active { background: #111827; color: #fff; }
.tab-count { min-width: 34rpx; height: 34rpx; line-height: 34rpx; border-radius: 17rpx; text-align: center;
  font-size: 20rpx; background: rgba(148, 163, 184, .18); }
.card { background: #fff; border-radius: 32rpx; padding: 8rpx 28rpx; box-shadow: 0 2rpx 10rpx rgba(16,24,40,.04); }
.item { display: flex; align-items: center; justify-content: space-between; gap: 20rpx;
  padding: 26rpx 0; border-bottom: 2rpx solid #eef0f3; }
.item:last-child { border-bottom: none; }
.it-left { flex: 1; min-width: 0; }
.it-title { font-size: 28rpx; color: #1f2937; font-weight: 600; line-height: 1.5; }
.it-title .dot { color: #ef4444; font-size: 20rpx; margin-left: 6rpx; }
.it-content { font-size: 24rpx; color: #9ca3af; margin-top: 8rpx; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; }
.chip { font-size: 20rpx; padding: 4rpx 16rpx; border-radius: 40rpx; background: #eaf0ff; color: #2563eb; flex-shrink: 0; }
.chip-o { background: #fff1f0; color: #e5533c; }
.chip-g { background: #e8f7ee; color: #1c8a4c; }
.read { opacity: .75; }
.empty { text-align: center; padding: 140rpx 0; color: #9ca3af; }
.empty-ico { font-size: 72rpx; margin-bottom: 20rpx; }
.empty-txt { font-size: 26rpx; }
</style>
