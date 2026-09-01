<template>
  <view class="wrap">
    <view class="card profile">
      <view class="avatar">{{ (user.nickname || user.username || '用')[0] }}</view>
      <view class="name">{{ user.nickname || user.username || '未命名' }}</view>
      <view class="muted">{{ user.dept_id ? '部门 ' + user.dept_id : 'AI 数字化人才平台' }}</view>
    </view>
    <view class="card">
      <view class="mi" @click="go('/pages/matching/agent')">
        <text>🤖 Agent 智能匹配</text><text class="arr">›</text>
      </view>
      <view class="mi" @click="go('/pages/profile/profile')">
        <text>🧑‍💼 我的档案</text><text class="arr">›</text>
      </view>
      <view class="mi" @click="go('/pages/ai/ai')">
        <text>💬 AI 助手</text><text class="arr">›</text>
      </view>
      <view class="mi" @click="logout">
        <text class="danger">退出登录</text><text class="arr">›</text>
      </view>
    </view>
  </view>
</template>
<script setup>
import { ref } from 'vue'
const user = ref(uni.getStorageSync('user') || null)
function go(url) { uni.navigateTo({ url }) }
function logout() {
  uni.removeStorageSync('token')
  uni.removeStorageSync('refresh_token')
  uni.removeStorageSync('user')
  uni.reLaunch({ url: '/pages/login/login' })
}
</script>
<style lang="scss" scoped>
.wrap { padding: 24rpx 24rpx 40rpx; min-height: 100vh; background: #f6f7f9; }
.card { background: #fff; border-radius: 32rpx; padding: 28rpx; margin-bottom: 24rpx;
  box-shadow: 0 2rpx 10rpx rgba(16,24,40,.04); }
.profile { text-align: center; padding-top: 48rpx; padding-bottom: 40rpx; }
.avatar { width: 112rpx; height: 112rpx; border-radius: 50%; background: #eaf0ff; color: #2563eb;
  display: flex; align-items: center; justify-content: center; font-size: 44rpx; font-weight: 700;
  margin: 0 auto; }
.name { font-size: 34rpx; font-weight: 700; color: #1f2937; margin: 16rpx 0 6rpx; }
.muted { font-size: 24rpx; color: #9ca3af; }
.mi { display: flex; justify-content: space-between; align-items: center; padding: 26rpx 4rpx;
  font-size: 28rpx; color: #1f2937; border-bottom: 2rpx solid #eef0f3; }
.mi:last-child { border-bottom: none; }
.mi .arr { color: #c3c8d0; font-size: 32rpx; }
.danger { color: #ef4444; }
</style>