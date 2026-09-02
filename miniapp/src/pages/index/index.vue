<script setup>
import { ref, onMounted } from 'vue'
import request from '@/utils/request'

const user = ref({})
// 数据卡（来自 M 域实时接口：在招岗位/匹配记录/储备预警）
const stats = ref([
  { label: '在招岗位', value: '-', color: '#2563eb', icon: '💼' },
  { label: '匹配记录', value: '-', color: '#16a34a', icon: '🎯' },
  { label: '储备预警', value: '-', color: '#f59e0b', icon: '🔔' },
])
// 技能概览（T 域档案未交付前为静态占位）
const skills = ref([
  { name: 'AI', score: 85 },
  { name: 'Python', score: 92 },
  { name: 'Java', score: 78 },
])
const growth = ref(88)

// 快捷入口（对齐 design/app-prototype.html 基准）
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
  try {
    const [msg, todo, plans] = await Promise.all([
      request({ url: '/messages/unread-count' }),
      request({ url: '/assessment/todo', data: { talent_id: currentTalentId() } }),
      request({ url: '/training/plans', data: { talent_id: currentTalentId() } }),
    ])
    stats.value[0].value = msg.data?.unread ?? 0
    stats.value[1].value = Array.isArray(todo.data) ? todo.data.length : (todo.data?.items?.length ?? 0)
    stats.value[2].value = Array.isArray(plans.data) ? plans.data.length : (plans.data?.items?.length ?? 0)
  } catch (e) { /* 接口异常不阻塞页面 */ }
}

function go(url) {
  const tabPages = [
    '/pages/index/index',
    '/pages/assessment/assessment',
    '/pages/study/study',
    '/pages/message/message',
    '/pages/mine/mine'
  ]
  if (tabPages.includes(url)) {
    uni.switchTab({ url })
    return
  }
  uni.navigateTo({ url })
}

function goTab(url) {
  uni.switchTab({ url })
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
    <!-- 顶部品牌渐变 bar -->
    <view class="bar">
      <view class="hello">
        <text class="hi">你好，{{ user.nickname || user.username || '同学' }} 👋</text>
        <text class="role">{{ user.dept_id ? '部门 ' + user.dept_id : '欢迎使用人才平台' }}</text>
      </view>
      <view class="out" @click="logout">退出</view>
    </view>

    <!-- 技能概览 -->
    <view class="card">
      <view class="cap">技能概览</view>
      <view class="chips">
        <text v-for="s in skills" :key="s.name" class="chip">{{ s.name }} {{ s.score }}</text>
        <text class="chip chip-g">骨干人才</text>
      </view>
      <view class="progress"><view class="progress-i" :style="{ width: growth + '%' }" /></view>
      <view class="muted grow-row"><text>能力成长度</text><text>{{ growth }}%</text></view>
    </view>

    <!-- 数据卡片 -->
    <view class="stat-row">
      <view v-for="s in stats" :key="s.label" class="stat-card">
        <view class="stat-ico">{{ s.icon }}</view>
        <view class="stat-num" :style="{ color: s.color }">{{ s.value }}</view>
        <view class="stat-label">{{ s.label }}</view>
      </view>
    </view>

    <!-- 快捷入口 -->
    <view class="card">
      <view class="cap">快捷入口</view>
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
.wrap { padding-bottom: 40rpx; min-height: 100vh; background: #f6f7f9; }
/* 顶部品牌渐变 bar */
.bar { display: flex; justify-content: space-between; align-items: center;
  padding: 60rpx 32rpx 44rpx; background: linear-gradient(135deg, #2563eb, #4f8df9);
  border-radius: 0 0 24rpx 24rpx; }
.hello { display: flex; flex-direction: column; }
.hi { font-size: 34rpx; font-weight: 700; color: #fff; }
.role { font-size: 24rpx; color: rgba(255,255,255,.9); margin-top: 8rpx; }
.out { font-size: 24rpx; color: #fff; padding: 10rpx 24rpx; background: rgba(255,255,255,.18);
  border-radius: 28rpx; }
/* 卡片 */
.card { background: #fff; border-radius: 32rpx; padding: 28rpx; margin: 24rpx 24rpx 0;
  box-shadow: 0 2rpx 10rpx rgba(16,24,40,.04); }
.cap { font-size: 28rpx; font-weight: 600; color: #1f2937; margin-bottom: 20rpx; }
/* 技能概览 */
.chips { display: flex; gap: 12rpx; flex-wrap: wrap; }
.chip { font-size: 22rpx; padding: 6rpx 18rpx; border-radius: 40rpx; background: #eaf0ff;
  color: #2563eb; }
.chip-g { background: #e8f7ee; color: #1c8a4c; }
.progress { height: 14rpx; border-radius: 10rpx; background: #eef2f7; overflow: hidden; margin: 22rpx 0 12rpx; }
.progress-i { display: block; height: 100%; background: #2563eb; border-radius: 10rpx; }
.muted { font-size: 22rpx; color: #9ca3af; }
.grow-row { display: flex; justify-content: space-between; }
/* 数据卡 */
.stat-row { display: flex; gap: 18rpx; padding: 24rpx 24rpx 0; }
.stat-card { flex: 1; background: #fff; border-radius: 32rpx; padding: 26rpx 0; text-align: center;
  box-shadow: 0 2rpx 10rpx rgba(16,24,40,.04); }
.stat-ico { font-size: 40rpx; }
.stat-num { font-size: 48rpx; font-weight: 700; margin: 10rpx 0 4rpx; }
.stat-label { font-size: 22rpx; color: #9ca3af; }
/* 快捷入口 */
.grid { display: flex; flex-wrap: wrap; gap: 20rpx; }
.cell { width: calc(50% - 10rpx); text-align: center; padding: 30rpx 0; border-radius: 24rpx;
  background: #f6f7f9; }
.cell-icon { font-size: 44rpx; }
.cell-name { font-size: 26rpx; color: #1f2937; margin-top: 10rpx; }
/* Agent 横幅 */
.agent-banner { margin: 24rpx 24rpx 0; border-radius: 32rpx; padding: 28rpx 32rpx;
  background: linear-gradient(135deg, #2563eb, #4f8df9); display: flex; align-items: center;
  justify-content: space-between; }
.agent-left { display: flex; flex-direction: column; }
.agent-title { color: #fff; font-size: 30rpx; font-weight: 700; }
.agent-sub { color: rgba(255,255,255,.85); font-size: 22rpx; margin-top: 6rpx; }
.agent-arrow { color: #fff; font-size: 44rpx; }
.footer { text-align: center; color: #b1b5bd; font-size: 22rpx; margin-top: 36rpx; }
</style>
