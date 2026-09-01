<template>
  <view class="wrap">
    <view class="mk">AI 助手（本期 Mock 界面，接入 RAG/G 在二期）</view>
    <view class="chat">
      <input class="ipt" v-model="q" placeholder="问问人才平台…" confirm-type="send" @confirm="ask" />
    </view>
  </view>
</template>
<script setup>
import { ref } from 'vue'
const q = ref('')
function ask() {
  if (!q.value) return
  uni.showToast({ title: 'AI 能力二期接入', icon: 'none' })
  q.value = ''
}
</script>
<style scoped>.wrap{padding:40rpx 32rpx}.mk{color:#9ca3af;font-size:24rpx}.chat{margin-top:30rpx;background:#fff;border-radius:20rpx;padding:20rpx}.ipt{height:80rpx}</style>