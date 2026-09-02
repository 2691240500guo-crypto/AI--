<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { listMyResults, listMyTodos } from '@/api'

const loading = ref(true)
const refreshing = ref(false)
const activeTab = ref('todo')
const todos = ref([])
const results = ref([])
const errorMessage = ref('')

const pendingCount = computed(() => todos.value.length)
const completedResults = computed(() => results.value.filter((item) => item.status >= 2))
const completedCount = computed(() => completedResults.value.length)

async function load(showLoading = true) {
  if (showLoading) loading.value = true
  refreshing.value = !showLoading
  errorMessage.value = ''
  try {
    const [todoResponse, resultResponse] = await Promise.all([listMyTodos(), listMyResults()])
    todos.value = todoResponse.data || []
    results.value = resultResponse.data || []
  } catch (error) {
    errorMessage.value = error?.message || '测评数据加载失败，请重试'
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function openQuiz(item) { uni.navigateTo({ url: `/pages/assessment/quiz?id=${item.id}` }) }
function openResult(item) { uni.navigateTo({ url: `/pages/assessment/result?id=${item.id}` }) }
function statusText(status) { return status === 0 ? '待开始' : '答题中' }
function resultStatus(status) { return status === 3 ? '报告已生成' : '已交卷' }
function formatDate(value) { return value ? new Date(value).toLocaleString() : '—' }
function scoreRate(item) {
  const score = Number(item.score || 0)
  const total = Number(item.paper_total_score || 0)
  return total ? Math.round(score / total * 100) : 0
}

onShow(() => load(!todos.value.length && !results.value.length))
</script>

<template>
  <view class="page">
    <view class="hero"><view><text class="hero-title">在线测评</text><text class="hero-sub">完成测评，查看你的能力结果与提升建议</text></view><view class="refresh" :class="{ spinning: refreshing }" @click="load(false)">↻</view></view>
    <view class="summary"><view class="summary-item"><text class="summary-num">{{ pendingCount }}</text><text class="summary-label">待完成</text></view><view class="summary-line"></view><view class="summary-item"><text class="summary-num">{{ completedCount }}</text><text class="summary-label">已完成</text></view><view class="summary-line"></view><view class="summary-item"><text class="summary-num">{{ completedResults.length ? Math.round(completedResults.reduce((sum, item) => sum + scoreRate(item), 0) / completedResults.length) : 0 }}%</text><text class="summary-label">平均得分率</text></view></view>
    <view v-if="errorMessage" class="error">{{ errorMessage }} <text @click="load()">重新加载</text></view>
    <view class="tabs"><view class="tab" :class="{ active: activeTab === 'todo' }" @click="activeTab = 'todo'">待完成 <text v-if="pendingCount" class="badge">{{ pendingCount }}</text></view><view class="tab" :class="{ active: activeTab === 'result' }" @click="activeTab = 'result'">测评记录</view></view>
    <view v-if="loading" class="state">正在加载测评...</view>

    <template v-else-if="activeTab === 'todo'"><view v-for="item in todos" :key="item.id" class="assessment-card"><view class="card-main"><view class="paper-icon">▤</view><view class="card-copy"><text class="paper-title">{{ item.paper_title || '未命名试卷' }}</text><text class="paper-meta">{{ item.question_count || 0 }} 题 · 总分 {{ item.paper_total_score || 0 }} 分</text><text class="paper-meta">截止：{{ formatDate(item.deadline_at) }}</text></view><text class="status pending">{{ statusText(item.status) }}</text></view><view class="card-foot"><text class="hint">{{ item.status === 1 ? '已保存作答进度，可继续答题' : '请在截止时间前完成' }}</text><button class="action primary" @click="openQuiz(item)">{{ item.status === 1 ? '继续作答' : '开始测评' }}</button></view></view><view v-if="!todos.length" class="empty"><text class="empty-icon">✓</text><text>暂无待完成测评</text><text class="empty-sub">管理员发起测评后会显示在这里</text></view></template>

    <template v-else><view v-for="item in completedResults" :key="item.id" class="assessment-card result-card"><view class="card-main"><view class="paper-icon done">✓</view><view class="card-copy"><text class="paper-title">{{ item.paper_title || '未命名试卷' }}</text><text class="paper-meta">{{ formatDate(item.end_at || item.updated_at) }} · {{ item.correct_count || 0 }}/{{ item.question_count || 0 }} 题正确</text><text class="paper-meta">得分率 {{ scoreRate(item) }}%</text></view><view class="score"><text>{{ item.score || 0 }}</text><small>/ {{ item.paper_total_score || 0 }}</small></view></view><view class="card-foot"><text class="status completed">{{ resultStatus(item.status) }}</text><button class="action" @click="openResult(item)">查看报告 ›</button></view></view><view v-if="!completedResults.length" class="empty"><text class="empty-icon">▤</text><text>暂无测评记录</text><text class="empty-sub">完成一次测评后，成绩会显示在这里</text></view></template>
  </view>
</template>

<style lang="scss" scoped>
.page { min-height: 100vh; padding: 0 24rpx 48rpx; background: #f5f7fa; }
.hero { display: flex; align-items: center; justify-content: space-between; margin: 0 -24rpx; padding: 46rpx 32rpx 38rpx; color: #fff; background: linear-gradient(135deg, #2563eb, #4f8df9); }
.hero-title { display: block; font-size: 40rpx; font-weight: 700; }.hero-sub { display: block; margin-top: 10rpx; color: rgba(255,255,255,.82); font-size: 23rpx; }
.refresh { width: 64rpx; height: 64rpx; border: 1rpx solid rgba(255,255,255,.45); border-radius: 50%; line-height: 60rpx; text-align: center; font-size: 38rpx; }.refresh.spinning { opacity: .6; transform: rotate(180deg); }
.summary { display: flex; align-items: center; justify-content: space-around; margin-bottom: 24rpx; padding: 28rpx 10rpx; background: #fff; border-radius: 0 0 20rpx 20rpx; box-shadow: 0 4rpx 14rpx rgba(16,24,40,.05); }.summary-item { display: flex; flex: 1; flex-direction: column; align-items: center; }.summary-num { color: #2563eb; font-size: 36rpx; font-weight: 700; }.summary-label { margin-top: 8rpx; color: #8a94a6; font-size: 22rpx; }.summary-line { width: 1rpx; height: 44rpx; background: #e8ebf0; }
.error { margin-bottom: 20rpx; padding: 20rpx; color: #b42318; background: #fef3f2; border-radius: 12rpx; font-size: 24rpx; }.error text { float: right; color: #2563eb; }
.tabs { display: flex; gap: 42rpx; margin: 0 4rpx 20rpx; border-bottom: 1rpx solid #e5e9f0; }.tab { position: relative; padding: 14rpx 4rpx 20rpx; color: #8490a3; font-size: 28rpx; }.tab.active { color: #2563eb; font-weight: 600; }.tab.active::after { position: absolute; right: 0; bottom: -1rpx; left: 0; height: 5rpx; background: #2563eb; border-radius: 5rpx; content: ''; }.badge { display: inline-block; min-width: 30rpx; margin-left: 6rpx; padding: 2rpx 8rpx; color: #fff; background: #ef4444; border-radius: 20rpx; font-size: 20rpx; text-align: center; }
.assessment-card { margin-bottom: 20rpx; padding: 26rpx; background: #fff; border: 1rpx solid #edf0f5; border-radius: 18rpx; box-shadow: 0 3rpx 12rpx rgba(16,24,40,.04); }.card-main { display: flex; align-items: flex-start; gap: 18rpx; }.paper-icon { width: 68rpx; height: 68rpx; flex: none; color: #2563eb; background: #eaf0ff; border-radius: 16rpx; line-height: 68rpx; text-align: center; font-size: 38rpx; }.paper-icon.done { color: #159447; background: #e7f7ed; }.card-copy { min-width: 0; flex: 1; }.paper-title { display: block; overflow: hidden; color: #1f2937; font-size: 29rpx; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }.paper-meta { display: block; margin-top: 9rpx; color: #8a94a6; font-size: 22rpx; }.status { flex: none; padding: 6rpx 12rpx; border-radius: 8rpx; font-size: 20rpx; }.status.pending { color: #b54708; background: #fff4e5; }.status.completed { color: #16804a; background: #eaf8ef; }
.card-foot { display: flex; align-items: center; justify-content: space-between; gap: 14rpx; margin-top: 24rpx; padding-top: 20rpx; border-top: 1rpx solid #f0f2f5; }.hint { flex: 1; color: #98a2b3; font-size: 21rpx; }.action { min-width: 164rpx; height: 64rpx; margin: 0; padding: 0 22rpx; color: #2563eb; background: #fff; border: 1rpx solid #b9d0ff; border-radius: 32rpx; font-size: 24rpx; line-height: 62rpx; }.action::after { border: 0; }.action.primary { color: #fff; background: #2563eb; border-color: #2563eb; }.score { flex: none; color: #2563eb; text-align: right; }.score text { font-size: 36rpx; font-weight: 700; }.score small { color: #98a2b3; font-size: 20rpx; }
.state, .empty { padding: 110rpx 20rpx; color: #98a2b3; text-align: center; font-size: 25rpx; }.empty-icon { display: block; margin-bottom: 18rpx; color: #2aa866; font-size: 70rpx; }.empty-sub { display: block; margin-top: 12rpx; color: #b1b8c4; font-size: 22rpx; }
</style>
