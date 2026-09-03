<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { listMyResults, listMyTodos } from '@/api'
import UiState from '@/components/UiState.vue'

const loading = ref(true)
const refreshing = ref(false)
const activeTab = ref('todo')
const todos = ref([])
const results = ref([])
const errorMessage = ref('')

const pendingCount = computed(() => todos.value.length)
const completedResults = computed(() => results.value.filter((item) => item.status >= 2))
const completedCount = computed(() => completedResults.value.length)
const averageRate = computed(() => {
  if (!completedResults.value.length) return 0
  const total = completedResults.value.reduce((sum, item) => sum + scoreRate(item), 0)
  return Math.round(total / completedResults.value.length)
})

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
function statusText(status) { return status === 1 ? '进行中' : '待开始' }
function resultStatus(status) { return status === 3 ? '报告已生成' : '已交卷' }
function formatDate(value) { return value ? new Date(value).toLocaleString() : '暂无截止时间' }
function scoreRate(item) {
  const score = Number(item.score || 0)
  const total = Number(item.paper_total_score || 0)
  return total ? Math.round(score / total * 100) : 0
}
function isUrgent(item) {
  if (!item.deadline_at) return false
  const left = new Date(item.deadline_at).getTime() - Date.now()
  return left > 0 && left < 24 * 60 * 60 * 1000
}

onShow(() => load(!todos.value.length && !results.value.length))
</script>

<template>
  <view class="app-page assessment-page">
    <view class="hero surface">
      <view>
        <text class="eyebrow">发现能力</text>
        <text class="hero-title">在线测评</text>
        <text class="hero-sub">完成测评后，系统会生成能力诊断和提升建议。</text>
      </view>
      <button class="refresh" :class="{ spinning: refreshing }" :disabled="refreshing" @click="load(false)">
        刷新
      </button>
    </view>

    <view class="summary surface">
      <view class="summary-item">
        <text class="summary-num coral">{{ pendingCount }}</text>
        <text class="summary-label">待完成</text>
      </view>
      <view class="summary-divider"></view>
      <view class="summary-item">
        <text class="summary-num">{{ completedCount }}</text>
        <text class="summary-label">已完成</text>
      </view>
      <view class="summary-divider"></view>
      <view class="summary-item">
        <text class="summary-num">{{ averageRate }}%</text>
        <text class="summary-label">平均得分率</text>
      </view>
    </view>

    <UiState
      v-if="errorMessage"
      tone="error"
      title="测评数据加载失败"
      :hint="errorMessage"
      action-text="重新加载"
      @action="load()"
    />

    <template v-else>
      <view class="tabs">
        <view class="tab" :class="{ active: activeTab === 'todo' }" @click="activeTab = 'todo'">
          <text>待完成</text>
          <text v-if="pendingCount" class="badge">{{ pendingCount }}</text>
        </view>
        <view class="tab" :class="{ active: activeTab === 'result' }" @click="activeTab = 'result'">
          <text>测评记录</text>
        </view>
      </view>

      <UiState v-if="loading" tone="loading" title="正在加载测评" hint="请稍候，正在同步你的测评任务。" />

      <template v-else-if="activeTab === 'todo'">
        <view v-for="item in todos" :key="item.id" class="assessment-card surface" :class="{ urgent: isUrgent(item) }">
          <view class="card-main">
            <view class="paper-mark">测</view>
            <view class="card-copy">
              <text class="paper-title">{{ item.paper_title || '未命名试卷' }}</text>
              <text class="paper-meta">{{ item.question_count || 0 }} 题 · 总分 {{ item.paper_total_score || 0 }} 分</text>
              <text class="paper-meta">截止：{{ formatDate(item.deadline_at) }}</text>
            </view>
            <text class="status" :class="{ working: item.status === 1, urgent: isUrgent(item) }">
              {{ isUrgent(item) ? '即将截止' : statusText(item.status) }}
            </text>
          </view>
          <view class="card-foot">
            <text class="hint">{{ item.status === 1 ? '已保存作答进度，可继续答题。' : '先完成测评，才能生成能力诊断。' }}</text>
            <button class="action primary" @click="openQuiz(item)">{{ item.status === 1 ? '继续作答' : '开始测评' }}</button>
          </view>
        </view>
        <UiState
          v-if="!todos.length"
          title="暂无待完成测评"
          hint="新的测评任务会出现在这里。"
        />
      </template>

      <template v-else>
        <view v-for="item in completedResults" :key="item.id" class="assessment-card surface result-card">
          <view class="card-main">
            <view class="paper-mark done">诊</view>
            <view class="card-copy">
              <text class="paper-title">{{ item.paper_title || '未命名试卷' }}</text>
              <text class="paper-meta">{{ formatDate(item.end_at || item.updated_at) }} · {{ item.correct_count || 0 }}/{{ item.question_count || 0 }} 题正确</text>
              <view class="rate-line">
                <view class="rate-track"><view class="rate-fill" :style="{ width: scoreRate(item) + '%' }"></view></view>
                <text>{{ scoreRate(item) }}%</text>
              </view>
            </view>
            <view class="score">
              <text>{{ item.score || 0 }}</text>
              <small>/ {{ item.paper_total_score || 0 }}</small>
            </view>
          </view>
          <view class="card-foot">
            <text class="status completed">{{ resultStatus(item.status) }}</text>
            <button class="action" @click="openResult(item)">查看报告</button>
          </view>
        </view>
        <UiState
          v-if="!completedResults.length"
          title="暂无测评记录"
          hint="完成一次测评后，能力诊断会显示在这里。"
        />
      </template>
    </template>
  </view>
</template>

<style lang="scss" scoped>
.assessment-page {
  padding-bottom: 72rpx;
}

.hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24rpx;
  padding: 32rpx 30rpx;
}

.eyebrow,
.hero-title,
.hero-sub {
  display: block;
}

.eyebrow {
  color: var(--color-coral);
  font-size: 22rpx;
  font-weight: 800;
}

.hero-title {
  margin-top: 8rpx;
  color: var(--color-text);
  font-size: 44rpx;
  font-weight: 800;
  line-height: 1.2;
}

.hero-sub {
  margin-top: 10rpx;
  color: var(--color-muted);
  font-size: 24rpx;
  line-height: 1.5;
}

.refresh {
  flex-shrink: 0;
  width: 116rpx;
  height: 58rpx;
  margin: 0;
  color: var(--color-brand);
  background: var(--color-brand-soft);
  border-radius: var(--radius-sm);
  font-size: 23rpx;
  line-height: 58rpx;
}

.refresh[disabled] {
  color: var(--color-muted);
}

.summary {
  display: flex;
  align-items: center;
  justify-content: space-around;
  margin-top: 18rpx;
  padding: 26rpx 10rpx;
}

.summary-item {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
}

.summary-num {
  color: var(--color-brand);
  font-size: 37rpx;
  font-weight: 800;
}

.summary-num.coral {
  color: var(--color-coral);
}

.summary-label {
  margin-top: 8rpx;
  color: var(--color-muted);
  font-size: 22rpx;
}

.summary-divider {
  width: 1rpx;
  height: 48rpx;
  background: var(--color-border);
}

.tabs {
  display: flex;
  gap: 16rpx;
  margin: 28rpx 4rpx 22rpx;
}

.tab {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  min-width: 158rpx;
  height: 64rpx;
  padding: 0 24rpx;
  color: var(--color-muted);
  background: #EEF7FA;
  border: 1rpx solid transparent;
  border-radius: var(--radius-sm);
  font-size: 25rpx;
  box-sizing: border-box;
}

.tab.active {
  color: var(--color-brand);
  background: #fff;
  border-color: rgba(23, 126, 173, .25);
  font-weight: 700;
}

.badge {
  min-width: 32rpx;
  height: 32rpx;
  padding: 0 8rpx;
  color: #fff;
  background: var(--color-coral);
  border-radius: 16rpx;
  font-size: 19rpx;
  line-height: 32rpx;
  text-align: center;
}

.assessment-card {
  margin-bottom: 18rpx;
  padding: 26rpx;
}

.assessment-card.urgent {
  border-color: rgba(255, 127, 120, .38);
}

.card-main,
.card-foot,
.rate-line {
  display: flex;
  align-items: center;
}

.card-main {
  align-items: flex-start;
  gap: 18rpx;
}

.paper-mark {
  width: 68rpx;
  height: 68rpx;
  flex: none;
  color: var(--color-brand);
  background: var(--color-brand-soft);
  border-radius: 18rpx;
  font-size: 24rpx;
  font-weight: 800;
  line-height: 68rpx;
  text-align: center;
}

.paper-mark.done {
  color: var(--color-coral);
  background: var(--color-coral-soft);
}

.card-copy {
  min-width: 0;
  flex: 1;
}

.paper-title,
.paper-meta {
  display: block;
}

.paper-title {
  overflow: hidden;
  color: var(--color-text);
  font-size: 29rpx;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.paper-meta {
  margin-top: 9rpx;
  color: var(--color-muted);
  font-size: 22rpx;
}

.status {
  flex: none;
  min-height: 40rpx;
  padding: 0 12rpx;
  color: var(--color-warning);
  background: #FFF7E8;
  border-radius: var(--radius-sm);
  font-size: 20rpx;
  line-height: 40rpx;
}

.status.working,
.status.completed {
  color: var(--color-brand);
  background: var(--color-brand-soft);
}

.status.urgent {
  color: var(--color-coral);
  background: var(--color-coral-soft);
}

.status.completed {
  color: var(--color-success);
  background: #E9F8F3;
}

.card-foot {
  justify-content: space-between;
  gap: 16rpx;
  margin-top: 24rpx;
  padding-top: 20rpx;
  border-top: 1rpx solid var(--color-border);
}

.hint {
  flex: 1;
  color: var(--color-muted);
  font-size: 22rpx;
  line-height: 1.45;
}

.action {
  min-width: 152rpx;
  height: 62rpx;
  margin: 0;
  padding: 0 20rpx;
  color: var(--color-brand);
  background: #fff;
  border: 1rpx solid rgba(23, 126, 173, .32);
  border-radius: var(--radius-sm);
  font-size: 24rpx;
  line-height: 62rpx;
}

.action.primary {
  color: #fff;
  background: var(--color-coral);
  border-color: var(--color-coral);
  font-weight: 700;
}

.score {
  flex: none;
  color: var(--color-brand);
  text-align: right;
}

.score text {
  font-size: 38rpx;
  font-weight: 800;
}

.score small {
  color: var(--color-muted);
  font-size: 20rpx;
}

.rate-line {
  gap: 12rpx;
  margin-top: 12rpx;
  color: var(--color-brand);
  font-size: 22rpx;
}

.rate-track {
  flex: 1;
  height: 10rpx;
  overflow: hidden;
  background: #ECF4F7;
  border-radius: 8rpx;
}

.rate-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-brand), var(--color-coral));
  border-radius: 8rpx;
}
</style>
