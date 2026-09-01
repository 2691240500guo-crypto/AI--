<script setup>
import { onMounted, ref } from 'vue'
import request from '@/utils/request'

const list = ref([])
async function load() {
  const res = await request({ url: '/messages?page=1&page_size=20', method: 'GET' })
  list.value = res.data.items || []
}
async function read(item) {
  await request({ url: `/messages/${item.id}/read`, method: 'POST', data: {} })
  item.is_read = true
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