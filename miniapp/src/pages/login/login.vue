<script setup>
import { reactive, ref, onMounted } from 'vue'
import request from '@/utils/request'

const form = reactive({ username: '', password: '' })
const loading = ref(false)

onMounted(() => {
  // 已登录直接进首页
  if (uni.getStorageSync('token')) {
    uni.switchTab({ url: '/pages/index/index' })
  }
})

async function login() {
  if (!form.username || !form.password) {
    uni.showToast({ title: '请输入账号密码', icon: 'none' })
    return
  }
  loading.value = true
  try {
    const res = await request({ url: '/auth/login', method: 'POST', data: form })
    uni.setStorageSync('token', res.data.access_token)
    uni.setStorageSync('refresh_token', res.data.refresh_token)
    uni.setStorageSync('user', res.data.user)
    uni.showToast({ title: '登录成功', icon: 'success' })
    setTimeout(() => uni.switchTab({ url: '/pages/index/index' }), 300)
  } catch (e) {
    // request 已统一弹错误提示，这里无需重复
  } finally {
    loading.value = false
  }
}

// 微信登录：正式环境 wx.login 取 code 换 openid（暂未接入）
function wechatLogin() {
  uni.showToast({ title: '微信登录待接入 code2session', icon: 'none' })
}
</script>

<template>
  <view class="wrap">
    <view class="brand">
      <view class="logo">AI</view>
      <view class="title">AI 数字化人才平台</view>
      <view class="sub">岗位智能匹配 · 人才精准画像</view>
    </view>
    <view class="card">
      <view class="field">
        <text class="label">账号</text>
        <input v-model="form.username" class="ipt" placeholder="请输入账号" @confirm="login" />
      </view>
      <view class="field">
        <text class="label">密码</text>
        <input v-model="form.password" class="ipt" type="password" password placeholder="请输入密码" @confirm="login" />
      </view>
      <button class="btn" :loading="loading" @click="login">登 录</button>
      <view class="wechat" @click="wechatLogin">微信授权登录</view>
    </view>
    <view class="tip">默认账号 admin / admin123</view>
  </view>
</template>

<style lang="scss" scoped>
.wrap { padding: 120rpx 48rpx; min-height: 100vh; background: #f5f7fa; }
.brand { text-align: center; margin-bottom: 60rpx; }
.logo { width: 96rpx; height: 96rpx; line-height: 96rpx; margin: 0 auto 18rpx; border-radius: 24rpx;
  background: #2563eb; color: #fff; font-size: 40rpx; font-weight: 700; }
.title { font-size: 40rpx; font-weight: 700; color: #1e3a8a; }
.sub { font-size: 24rpx; color: #9ca3af; margin-top: 10rpx; }
.card { background: #fff; border-radius: 24rpx; padding: 40rpx 32rpx; box-shadow: 0 4rpx 16rpx rgba(16,24,40,.04); }
.field { margin-bottom: 32rpx; }
.label { font-size: 26rpx; color: #6b7280; display: block; margin-bottom: 12rpx; }
.ipt { height: 88rpx; border: 1px solid #eef1f5; border-radius: 14rpx; padding: 0 20rpx; font-size: 28rpx; background: #fafbfc; }
.btn { background: #2563eb; color: #fff; border-radius: 44rpx; height: 88rpx; line-height: 88rpx; margin-top: 16rpx; font-size: 30rpx; font-weight: 600; }
.wechat { text-align: center; color: #2563eb; margin-top: 28rpx; font-size: 26rpx; }
.tip { text-align: center; color: #9ca3af; font-size: 24rpx; margin-top: 40rpx; }
</style>
