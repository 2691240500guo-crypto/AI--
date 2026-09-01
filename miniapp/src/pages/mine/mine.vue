<template>
  <view class="wrap">
    <view class="card" v-if="user">
      <view class="avatar">{{ (user.nickname || '')[0] }}</view>
      <view class="name">{{ user.nickname || user.username }}</view>
    </view>
    <view class="menu">
      <view class="mi" @click="logout">退出登录</view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
const user = ref(uni.getStorageSync('user') || null)
function logout() {
  uni.removeStorageSync('token')
  uni.removeStorageSync('user')
  uni.reLaunch({ url: '/pages/login/login' })
}
</script>

<style lang="scss" scoped>
.wrap { padding: 40rpx 32rpx; }
.card { display: flex; align-items: center; gap: 24rpx; background: linear-gradient(135deg,#1e3a8a,#2563eb);
  color: #fff; padding: 40rpx; border-radius: 24rpx; }
.avatar { width: 100rpx; height: 100rpx; border-radius: 50%; background: rgba(255,255,255,.2); display: flex;
  align-items: center; justify-content: center; font-size: 44rpx; }
.name { font-size: 32rpx; font-weight: 600; }
.menu { background: #fff; border-radius: 20rpx; margin-top: 30rpx; }
.mi { padding: 30rpx; border-bottom: 1px solid #f1f2f4; }
</style>