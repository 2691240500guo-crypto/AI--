<script setup>
import { reactive } from 'vue'
import request from '@/utils/request'

const form = reactive({ username: '', password: '' })

async function login() {
  if (!form.username || !form.password) {
    uni.showToast({ title: '请输入账号密码', icon: 'none' })
    return
  }
  const res = await request({ url: '/auth/login', method: 'POST', data: form })
  uni.setStorageSync('token', res.data.access_token)
  uni.setStorageSync('refresh_token', res.data.refresh_token)
  uni.setStorageSync('user', res.data.user)
  uni.switchTab({ url: '/pages/index/index' })
}

// A03 微信登录：正式环境 wx.login 取 code 换 openid
function wechatLogin() {
  uni.showToast({ title: '微信登录待接入 code2session', icon: 'none' })
}
</script>

<template>
  <view class="wrap">
    <view class="title">AI 人才平台</view>
    <view class="card">
      <input v-model="form.username" class="ipt" placeholder="请输入账号" />
      <input v-model="form.password" class="ipt" password placeholder="请输入密码" />
      <button class="btn" @click="login">登 录</button>
      <view class="wechat" @click="wechatLogin">微信授权登录</view>
    </view>
    <view class="tip">默认账号 admin / admin123</view>
  </view>
</template>

<style lang="scss" scoped>
.wrap { padding: 120rpx 48rpx; }
.title { text-align: center; font-size: 44rpx; font-weight: 700; margin-bottom: 60rpx; color: #1e3a8a; }
.card { background: #fff; border-radius: 24rpx; padding: 40rpx; }
.ipt { height: 88rpx; border-bottom: 1px solid #eef1f5; margin-bottom: 30rpx; padding: 0 10rpx; }
.btn { background: #2563eb; color: #fff; border-radius: 44rpx; margin-top: 20rpx; }
.wechat { text-align: center; color: #2563eb; margin-top: 24rpx; font-size: 26rpx; }
.tip { text-align: center; color: #9ca3af; font-size: 24rpx; margin-top: 40rpx; }
</style>