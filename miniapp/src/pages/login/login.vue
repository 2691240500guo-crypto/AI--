<script setup>
import { reactive, ref, onMounted } from 'vue'
import request from '@/utils/request'

const form = reactive({ username: '', password: '' })
const loading = ref(false)

onMounted(() => {
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
    const res = await request({ url: '/auth/employee-login', method: 'POST', data: form })
    uni.setStorageSync('token', res.data.access_token)
    uni.setStorageSync('refresh_token', res.data.refresh_token)
    uni.setStorageSync('user', res.data.user)
    uni.showToast({ title: '登录成功', icon: 'success' })
    setTimeout(() => uni.switchTab({ url: '/pages/index/index' }), 300)
  } catch (e) {
  } finally {
    loading.value = false
  }
}

function wechatLogin() {
  uni.showToast({ title: '微信登录待接入 code2session', icon: 'none' })
}
</script>

<template>
  <view class="login-page">
    <view class="brand">
      <view class="logo">智</view>
      <view class="title">智链成长</view>
      <view class="sub">AI 人才成长工作台</view>
    </view>
    <view class="card surface">
      <view class="field">
        <text class="label">账号</text>
        <input v-model="form.username" class="ipt" placeholder="请输入账号" @confirm="login" />
      </view>
      <view class="field">
        <text class="label">密码</text>
        <input v-model="form.password" class="ipt" type="password" password placeholder="请输入密码" @confirm="login" />
      </view>
      <button class="btn" :loading="loading" @click="login">登录</button>
      <view class="wechat" @click="wechatLogin">微信授权登录</view>
    </view>
    <view class="tip">请使用员工端账号登录</view>
  </view>
</template>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  padding: 120rpx 48rpx 48rpx;
  background:
    linear-gradient(180deg, rgba(124, 206, 242, .2) 0, rgba(247, 251, 253, 0) 420rpx),
    var(--color-bg);
  box-sizing: border-box;
}

.brand {
  margin-bottom: 60rpx;
  text-align: center;
}

.logo {
  width: 100rpx;
  height: 100rpx;
  margin: 0 auto 18rpx;
  color: #fff;
  background: linear-gradient(135deg, var(--color-brand), var(--color-coral));
  border-radius: 28rpx;
  font-size: 42rpx;
  font-weight: 850;
  line-height: 100rpx;
}

.title {
  color: var(--color-text);
  font-size: 42rpx;
  font-weight: 850;
}

.sub {
  margin-top: 10rpx;
  color: var(--color-muted);
  font-size: 24rpx;
}

.card {
  padding: 40rpx 32rpx;
}

.field {
  margin-bottom: 32rpx;
}

.label {
  display: block;
  margin-bottom: 12rpx;
  color: var(--color-muted);
  font-size: 26rpx;
}

.ipt {
  height: 88rpx;
  padding: 0 20rpx;
  background: #F9FCFD;
  border: 1rpx solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 28rpx;
  box-sizing: border-box;
}

.btn {
  height: 88rpx;
  margin-top: 16rpx;
  color: #fff;
  background: var(--color-brand);
  border-radius: var(--radius-md);
  font-size: 30rpx;
  font-weight: 700;
  line-height: 88rpx;
}

.wechat {
  margin-top: 28rpx;
  color: var(--color-brand);
  font-size: 26rpx;
  text-align: center;
}

.tip {
  margin-top: 40rpx;
  color: var(--color-muted);
  font-size: 24rpx;
  text-align: center;
}
</style>
