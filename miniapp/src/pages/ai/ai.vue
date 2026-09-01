<template>
  <view class="wrap chat-box">
    <view class="bubble bot">你好，我是 AI 人才助手 🤖 可以帮你查制度、做人才解析、问数据。试试问我？</view>
    <view class="bubble me">我目前的技能短板是什么？</view>
    <view class="bubble bot">
      <text>结合最近测评，你在「项目管理」维度较弱，建议学习：</text>
      <text class="chip">研发项目管理</text>
      <view class="muted">↗ 依据：2026-08 测评报告 · 可追溯</view>
    </view>
    <view class="tips">
      <text class="chip">推荐问题</text>
      <text class="chip chip-o">本科含AI骨干人数?</text>
      <text class="chip chip-g">查制度</text>
    </view>
    <view class="ipt-row">
      <input class="ipt" v-model="q" placeholder="输入问题…" confirm-type="send" @confirm="ask" />
      <view class="send" @click="ask">发送</view>
    </view>
    <view class="note">回答基于内部知识库，已做权限隔离与溯源</view>
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
<style lang="scss" scoped>
.wrap { padding: 24rpx 24rpx 40rpx; min-height: 100vh; background: #f6f7f9; }
.chat-box { display: flex; flex-direction: column; }
.bubble { max-width: 78%; padding: 20rpx 24rpx; border-radius: 28rpx; font-size: 28rpx; margin-bottom: 20rpx; line-height: 1.7; }
.me { align-self: flex-end; background: #2563eb; color: #fff; border-radius: 28rpx 28rpx 6rpx 28rpx; }
.bot { align-self: flex-start; background: #fff; border: 2rpx solid #eef0f3; border-radius: 28rpx 28rpx 28rpx 6rpx; }
.chip { display: inline-block; font-size: 22rpx; padding: 4rpx 16rpx; border-radius: 40rpx;
  background: #eaf0ff; color: #2563eb; margin: 8rpx 8rpx 0 0; }
.chip-o { background: #fff1f0; color: #e5533c; }
.chip-g { background: #e8f7ee; color: #1c8a4c; }
.muted { font-size: 22rpx; color: #9ca3af; margin-top: 12rpx; }
.tips { display: flex; flex-wrap: wrap; gap: 12rpx; margin: 16rpx 0; }
.ipt-row { display: flex; align-items: center; gap: 16rpx; margin-top: 8rpx; }
.ipt { flex: 1; background: #fff; border: 2rpx solid #eef0f3; border-radius: 24rpx; height: 84rpx; padding: 0 24rpx; font-size: 28rpx; }
.send { background: #2563eb; color: #fff; border-radius: 44rpx; padding: 20rpx 40rpx; font-size: 28rpx; }
.note { font-size: 22rpx; color: #9ca3af; line-height: 1.8; margin-top: 20rpx; text-align: center; }
</style>