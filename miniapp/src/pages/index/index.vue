<script setup>
import { ref, onMounted } from 'vue'
import request from '@/utils/request'

const user = ref({})
const stats = ref([
  { label: '在招岗位', value: '-', color: '#2563eb', icon: '💼' },
  { label: '匹配记录', value: '-', color: '#16a34a', icon: '🎯' },
  { label: '储备预警', value: '-', color: '#f59e0b', icon: '🔔' },
])

const entries = [
  { name: '我的档案', icon: '🧑‍💼', url: '/pages/profile/profile' },
  { name: '在线测评', icon: '📝', url: '/pages/assessment/assessment' },
  { name: '在线学习', icon: '🎓', url: '/pages/study/study' },
  { name: 'AI 助手', icon: '💬', url: '/pages/ai/ai' },
]

onMounted(async () => {
  // token 守卫：未登录跳登录页
  if (!uni.getStorageSync('token')) {
    uni.reLaunch({ url: '/pages/login/login' })
    return
  }
  user.value = uni.getStorageSync('user') || {}
  loadStats()
})

async function loadStats() {
  // 概览数据来自岗位匹配域（M 域）接口：在招岗位、匹配记录、储备预警
  try {
    const [pos, res, alert] = await Promise.all([
      request({ url: '/matching/positions', method: 'GET', data: { page: 1, page_size: 1 } }),
      request({ url: '/matching/results', method: 'GET', data: { page: 1, page_size: 1 } }),
      request({ url: '/matching/alerts', method: 'GET', data: {} }),
    ])
    stats.value[0].value = pos.data?.meta?.total ?? 0
    stats.value[1].value = res.data?.meta?.total ?? 0
    stats.value[2].value = Array.isArray(alert.data) ? alert.data.length : 0
  } catch (e) {
    // 接口异常不阻塞页面，保持 '-' 展示
  }
}

function go(url) {
  uni.navigateTo({ url })
}

function logout() {
  uni.removeStorageSync('token')
  uni.removeStorageSync('refresh_token')
  uni.removeStorageSync('user')
  uni.reLaunch({ url: '/pages/login/login' })
}
</script>

<template>
  <view class="wrap">
    <!-- 顶部问候 -->
    <view class="hero">
      <view class="hello">
        <text class="name">你好，{{ user.nickname || user.username || '同学' }} 👋</text>
        <text class="role">{{ user.dept_id ? '部门 ' + user.dept_id : '欢迎使用' }}</text>
      </view>
      <view class="out" @click="logout">退出</view>
    </view>

    <!-- 数据卡片 -->
    <view class="stat-row">
      <view v-for="s in stats" :key="s.label" class="stat-card">
        <view class="stat-icon">{{ s.icon }}</view>
        <view class="stat-num" :style="{ color: s.color }">{{ s.value }}</view>
        <view class="stat-label">{{ s.label }}</view>
      </view>
    </view>

    <!-- 快捷入口 -->
    <view class="card">
      <view class="card-title">快捷入口</view>
      <view class="grid">
        <view v-for="e in entries" :key="e.name" class="cell" @click="go(e.url)">
          <view class="cell-icon">{{ e.icon }}</view>
          <view class="cell-name">{{ e.name }}</view>
        </view>
      </view>
    </view>

    <view class="footer">岗位智能匹配 · 数据基于岗位匹配域实时接口</view>
  </view>
</template>

<style lang="scss" scoped>
.wrap { padding: 40rpx 32rpx 60rpx; min-height: 100vh; background: #f5f7fa; }
.hero { display: flex; justify-content: space-between; align-items: center; margin-bottom: 28rpx; }
.hello { display: flex; flex-direction: column; }
.name { font-size: 36rpx; font-weight: 700; color: #1e3a8a; }
.role { font-size: 24rpx; color: #9ca3af; margin-top: 6rpx; }
.out { font-size: 26rpx; color: #6b7280; padding: 8rpx 20rpx; background: #fff; border-radius: 28rpx; }
.stat-row { display: flex; gap: 18rpx; margin-bottom: 28rpx; }
.stat-card { flex: 1; background: #fff; border-radius: 20rpx; padding: 28rpx 0; text-align: center;
  box-shadow: 0 2rpx 10rpx rgba(16,24,40,.04); }
.stat-icon { font-size: 36rpx; }
.stat-num { font-size: 48rpx; font-weight: 700; margin: 8rpx 0 4rpx; }
.stat-label { font-size: 22rpx; color: #9ca3af; }
.card { background: #fff; border-radius: 20rpx; padding: 32rpx; box-shadow: 0 2rpx 10rpx rgba(16,24,40,.04); }
.card-title { font-size: 28rpx; font-weight: 600; color: #1f2937; margin-bottom: 24rpx; }
.grid { display: flex; flex-wrap: wrap; gap: 24rpx; }
.cell { width: calc(50% - 12rpx); text-align: center; padding: 36rpx 0; border-radius: 16rpx;
  background: #f5f7fa; }
.cell-icon { font-size: 44rpx; }
.cell-name { font-size: 26rpx; color: #1f2937; margin-top: 10rpx; }
.footer { text-align: center; color: #b1b5bd; font-size: 22rpx; margin-top: 40rpx; }
</style>
