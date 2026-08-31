<template>
  <view class="wrap">
    <view class="hero">AI 数字化人才平台</view>
    <view class="grid">
      <view class="cell" @click="go('/pages/profile/profile')">我的档案</view>
      <view class="cell" @click="go('/pages/assessment/assessment')">在线测评</view>
      <view class="cell" @click="go('/pages/study/study')">在线学习</view>
      <view class="cell" @click="go('/pages/ai/ai')">AI 助手</view>
    </view>
  </view>
</template>

<script setup>
function go(url) {
  if (url === '/pages/ai/ai') return uni.navigateTo({ url })
  uni.navigateTo({ url })
}
</script>

<style lang="scss" scoped>
.wrap { padding: 40rpx 32rpx; }
.hero { text-align: center; font-size: 36rpx; font-weight: 600; color: #1e3a8a; padding: 60rpx 0 40rpx; }
.grid { display: flex; flex-wrap: wrap; gap: 24rpx; }
.cell { width: calc(50% - 12rpx); background: #fff; border-radius: 20rpx; text-align: center;
  padding: 60rpx 0; color: #1f2937; box-shadow: 0 2rpx 8rpx rgba(0,0,0,.04); }
</style>