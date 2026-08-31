<script setup>
import { onMounted, ref } from 'vue'
import request from '@/utils/request'

const list = ref([])

async function load() {
  const res = await request({ url: '/messages?page=1&page_size=20', method: 'GET' })
  list.value = res.data.items
}
async function read(item) {
  await request({ url: `/messages/${item.id}/read`, method: 'POST', data: {} })
  item.is_read = true
}
onMounted(load)
</script>

<template>
  <view class="wrap">
    <view v-for="it in list" :key="it.id" class="item" :class="{ read: it.is_read }" @click="read(it)">
      <view class="t">{{ it.title }}<text v-if="!it.is_read" class="dot">●</text></view>
      <view class="c">{{ it.content }}</view>
      <view class="time">{{ it.created_at }}</view>
    </view>
    <view v-if="!list.length" class="empty">暂无消息</view>
  </view>
</template>

<style lang="scss" scoped>
.wrap { padding: 24rpx 32rpx; }
.item { background: #fff; border-radius: 20rpx; padding: 28rpx; margin-bottom: 20rpx; }
.item.read { opacity: .6; }
.t { font-weight: 600; }
.dot { color: #f23c3c; margin-left: 10rpx; }
.c { color: #6b7280; margin-top: 10rpx; font-size: 26rpx; }
.time { color: #9ca3af; font-size: 24rpx; margin-top: 12rpx; }
.empty { text-align: center; color: #9ca3af; padding: 120rpx 0; }
</style>