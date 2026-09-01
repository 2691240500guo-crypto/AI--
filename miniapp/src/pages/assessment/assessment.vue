<script setup>
import { onMounted, ref } from 'vue'
import { onPullDownRefresh } from '@dcloudio/uni-app'
import { listMyTodos } from '@/api'

const loading = ref(false)
const todos = ref([])

async function load() {
  loading.value = true
  try {
    const res = await listMyTodos()
    todos.value = res.data || []
  } finally { loading.value = false }
}

const statusText = (s) => ({ 0: '未开始', 1: '进行中', 2: '已交卷', 3: '已出报告' }[s] || '-')
const statusColor = (s) => ({ 0: '#9ca3af', 1: '#f59e0b', 2: '#3b82f6', 3: '#10b981' }[s] || '#9ca3af')
const fmtMin = (sec) => Math.round(sec / 60) + ' 分钟'

function startQuiz(id) {
  uni.navigateTo({ url: `/pages/assessment/quiz?id=${id}` })
}

onMounted(load)
onPullDownRefresh(async () => {
  await load()
  uni.stopPullDownRefresh()
})
</script>

<template>
  <view class="wrap">
    <view class="header">
      <text class="title">我的测评</text>
      <text class="sub">{{ todos.length }} 项待测 / 已完成</text>
    </view>

    <view v-if="loading" class="loading">加载中...</view>
    <view v-else-if="!todos.length" class="empty">
      <text>暂无待测任务</text>
      <text class="hint">让管理员在管理端给你发起测评</text>
    </view>

    <view v-else class="list">
      <view v-for="t in todos" :key="t.result_id" class="card" @click="startQuiz(t.result_id)">
        <view class="card-row">
          <text class="card-title">{{ t.paper_title }}</text>
          <view class="status" :style="{ background: statusColor(t.status) }">{{ statusText(t.status) }}</view>
        </view>
        <view class="card-meta">
          <text>题数 {{ t.question_count }} · 时限 {{ fmtMin(t.duration * 60) }} · 总分 {{ t.total_score }}</text>
        </view>
        <view class="card-foot">点击进入答题 →</view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.wrap { padding: 32rpx 32rpx 80rpx; min-height: 100vh; background: #f5f7fa; }
.header { padding: 16rpx 0 32rpx; }
.title { font-size: 44rpx; font-weight: 600; color: #1f2937; display: block; }
.sub { font-size: 26rpx; color: #6b7280; display: block; margin-top: 8rpx; }
.loading, .empty { text-align: center; padding: 80rpx 0; color: #9ca3af; }
.empty .hint { display: block; font-size: 24rpx; margin-top: 12rpx; }
.list { display: flex; flex-direction: column; gap: 20rpx; }
.card { background: #fff; border-radius: 16rpx; padding: 28rpx; box-shadow: 0 2rpx 8rpx rgba(0,0,0,.04); }
.card-row { display: flex; justify-content: space-between; align-items: center; }
.card-title { font-size: 32rpx; font-weight: 500; color: #1f2937; flex: 1; padding-right: 16rpx; }
.status { color: #fff; font-size: 22rpx; padding: 4rpx 14rpx; border-radius: 20rpx; }
.card-meta { margin-top: 16rpx; color: #6b7280; font-size: 26rpx; }
.card-foot { margin-top: 16rpx; color: #2563eb; font-size: 24rpx; text-align: right; }
</style>