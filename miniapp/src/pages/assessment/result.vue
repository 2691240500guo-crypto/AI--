<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getMyResult, getReport } from '@/api'
import GrowthPath from '@/components/GrowthPath.vue'
import UiState from '@/components/UiState.vue'

const loading = ref(true)
const reportLoading = ref(false)
const result = ref(null)
const report = ref(null)
const errorMessage = ref('')

const overallRate = computed(() => {
  if (report.value) return Number(report.value.overall_rate || 0)
  const score = Number(result.value?.result?.score || 0)
  const total = Number(result.value?.result?.paper_total_score || 0)
  return total ? score / total : 0
})

const diagnosisSteps = computed(() => [
  { label: '测评', mark: '测', status: 'done', caption: '已完成' },
  { label: '诊断', mark: '诊', status: report.value ? 'done' : 'current', caption: report.value ? '已生成' : '生成中' },
  { label: '建议', mark: '荐', status: report.value?.recommendations?.length ? 'current' : 'todo', caption: '提升方向' },
  { label: '学习', mark: '学', status: 'todo', caption: '下一节点' }
])

function percent(value) { return `${Math.round(Number(value || 0) * 100)}%` }
function barPercent(value) {
  const rate = Math.max(0, Math.min(1, Number(value || 0)))
  return `${Math.round(rate * 100)}%`
}
function formatDate(value) { return value ? new Date(value).toLocaleString() : '—' }
function answerText(value) { return Array.isArray(value) ? value.join('、') || '未作答' : (value ?? '未作答') }
function goBack() { uni.navigateBack() }
function goStudy() { uni.switchTab({ url: '/pages/study/study' }) }

onLoad(async (options) => {
  const resultId = options.id
  const cacheKey = `assessment-result-${resultId}`
  const cached = uni.getStorageSync(cacheKey)
  if (cached?.result) {
    result.value = cached
    loading.value = false
  }
  try {
    const resultResponse = await getMyResult(resultId)
    result.value = resultResponse.data
    uni.removeStorageSync(cacheKey)
  } catch (error) {
    if (!result.value) errorMessage.value = error?.message || '成绩明细加载失败'
  } finally {
    loading.value = false
  }
  reportLoading.value = true
  getReport(resultId).then((response) => { report.value = response.data }).catch(() => {}).finally(() => { reportLoading.value = false })
})
</script>

<template>
  <view class="app-page result-page">
    <UiState v-if="loading" tone="loading" title="正在生成成绩报告" hint="成绩明细和能力诊断同步中。" />
    <UiState v-else-if="errorMessage" tone="error" title="成绩明细加载失败" :hint="errorMessage" action-text="返回测评" @action="goBack" />

    <template v-else-if="result?.result">
      <view class="hero surface">
        <text class="eyebrow">能力成长诊断</text>
        <text class="hero-title">{{ result.result.paper_title }}</text>
        <text class="hero-date">交卷时间：{{ formatDate(result.result.end_at) }}</text>
        <view class="score-row">
          <view>
            <text class="score">{{ result.result.score || 0 }}</text>
            <text class="score-total">/ {{ result.result.paper_total_score || 0 }} 分</text>
          </view>
          <view class="rate-ring">
            <text>{{ percent(overallRate) }}</text>
          </view>
        </view>
        <view class="rating">{{ report?.rating || '已完成' }} · 综合表现</view>
        <GrowthPath class="diagnosis-path" :steps="diagnosisSteps" compact />
      </view>

      <view class="section surface">
        <view class="section-title">答题概况</view>
        <view class="facts">
          <view>
            <strong>{{ result.result.correct_count || 0 }}</strong>
            <text>答对题数</text>
          </view>
          <view>
            <strong>{{ result.result.question_count || 0 }}</strong>
            <text>题目总数</text>
          </view>
          <view>
            <strong>{{ report?.radar?.length || 0 }}</strong>
            <text>能力维度</text>
          </view>
        </view>
      </view>

      <view v-if="reportLoading" class="report-loading surface">能力报告生成中，成绩和逐题答案已显示。</view>

      <view v-if="report?.radar?.length" class="section surface">
        <view class="section-title">能力维度</view>
        <view v-for="item in report.radar" :key="item.dimension" class="dimension">
          <view class="dimension-head">
            <text>{{ item.dimension }}</text>
            <text>{{ percent(item.rate) }} · {{ item.level }}</text>
          </view>
          <view class="bar"><view class="bar-fill" :style="{ width: barPercent(item.rate) }"></view></view>
          <text class="dimension-score">{{ item.score }} / {{ item.total_score }} 分</text>
        </view>
      </view>

      <view v-if="report?.strengths?.length || report?.weaknesses?.length" class="insight-grid">
        <view v-if="report?.strengths?.length" class="insight surface">
          <view class="section-title">优势能力</view>
          <view class="tags"><text v-for="item in report.strengths" :key="item" class="tag brand">{{ item }}</text></view>
        </view>
        <view v-if="report?.weaknesses?.length" class="insight surface">
          <view class="section-title">待提升维度</view>
          <view class="tags"><text v-for="item in report.weaknesses" :key="item" class="tag coral">{{ item }}</text></view>
        </view>
      </view>

      <view v-if="report?.recommendations?.length" class="section surface">
        <view class="section-title">下一步提升建议</view>
        <view v-for="(item, index) in report.recommendations" :key="item" class="recommend">
          <text class="recommend-no">{{ index + 1 }}</text>
          <text>{{ item }}</text>
        </view>
        <button class="study-button" @click="goStudy">去学习</button>
      </view>

      <view v-if="result.details?.length" class="section surface">
        <view class="section-title">逐题答案与得分</view>
        <view v-for="(item, index) in result.details" :key="item.question_id" class="answer-item">
          <view class="answer-head">
            <text class="answer-title">{{ index + 1 }}. {{ item.question_content || `题目 #${item.question_id}` }}</text>
            <text :class="item.is_correct ? 'correct' : 'wrong'">{{ item.is_correct ? '答对' : '答错' }}</text>
          </view>
          <text v-if="item.dimension" class="answer-dimension">{{ item.dimension }}</text>
          <view class="answer-line">
            <text>你的答案：{{ answerText(item.user_answer) }}</text>
            <text>正确答案：{{ answerText(item.correct_answer) }}</text>
            <text class="answer-score">得分：{{ item.score || 0 }} / {{ item.question_score || 0 }} 分</text>
          </view>
        </view>
      </view>

      <button class="back-button" @click="goBack">返回测评记录</button>
    </template>
  </view>
</template>

<style lang="scss" scoped>
.result-page {
  padding-bottom: 72rpx;
}

.hero {
  padding: 32rpx 30rpx 30rpx;
}

.eyebrow,
.hero-title,
.hero-date {
  display: block;
}

.eyebrow {
  color: var(--color-coral);
  font-size: 22rpx;
  font-weight: 800;
}

.hero-title {
  margin-top: 10rpx;
  color: var(--color-text);
  font-size: 38rpx;
  font-weight: 800;
  line-height: 1.28;
}

.hero-date {
  margin-top: 10rpx;
  color: var(--color-muted);
  font-size: 22rpx;
}

.score-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  margin-top: 30rpx;
}

.score {
  color: var(--color-brand);
  font-size: 74rpx;
  font-weight: 850;
  line-height: 1;
}

.score-total {
  margin-left: 8rpx;
  color: var(--color-muted);
  font-size: 23rpx;
}

.rate-ring {
  width: 116rpx;
  height: 116rpx;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-coral);
  border: 12rpx solid rgba(255, 127, 120, .2);
  border-top-color: var(--color-coral);
  border-radius: 50%;
  font-size: 26rpx;
  font-weight: 800;
}

.rating {
  display: inline-block;
  margin-top: 18rpx;
  padding: 8rpx 16rpx;
  color: var(--color-brand);
  background: var(--color-brand-soft);
  border-radius: var(--radius-sm);
  font-size: 22rpx;
  font-weight: 700;
}

.diagnosis-path {
  margin-top: 30rpx;
}

.section,
.insight {
  margin-top: 20rpx;
  padding: 26rpx;
}

.facts {
  display: flex;
  justify-content: space-around;
  text-align: center;
}

.facts view {
  display: flex;
  flex: 1;
  flex-direction: column;
}

.facts strong {
  color: var(--color-brand);
  font-size: 38rpx;
}

.facts text {
  margin-top: 8rpx;
  color: var(--color-muted);
  font-size: 21rpx;
}

.report-loading {
  margin-top: 20rpx;
  padding: 20rpx 26rpx;
  color: var(--color-muted);
  font-size: 23rpx;
}

.dimension {
  margin-bottom: 22rpx;
}

.dimension:last-child {
  margin-bottom: 0;
}

.dimension-head {
  display: flex;
  justify-content: space-between;
  gap: 20rpx;
  color: var(--color-text);
  font-size: 23rpx;
  font-weight: 650;
}

.dimension-head text:last-child {
  flex-shrink: 0;
  color: var(--color-brand);
}

.bar {
  height: 14rpx;
  margin-top: 12rpx;
  overflow: hidden;
  background: #ECF4F7;
  border-radius: 10rpx;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-brand), var(--color-coral));
  border-radius: 10rpx;
}

.dimension-score {
  display: block;
  margin-top: 8rpx;
  color: var(--color-muted);
  font-size: 20rpx;
}

.insight-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16rpx;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.tag {
  min-height: 42rpx;
  padding: 0 16rpx;
  border-radius: var(--radius-sm);
  font-size: 22rpx;
  line-height: 42rpx;
}

.tag.brand {
  color: var(--color-brand);
  background: var(--color-brand-soft);
}

.tag.coral {
  color: var(--color-coral);
  background: var(--color-coral-soft);
}

.recommend {
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
  margin-top: 16rpx;
  color: var(--color-muted);
  font-size: 23rpx;
  line-height: 1.6;
}

.recommend-no {
  width: 34rpx;
  height: 34rpx;
  flex: none;
  color: #fff;
  background: var(--color-coral);
  border-radius: 50%;
  font-size: 19rpx;
  line-height: 34rpx;
  text-align: center;
}

.study-button,
.back-button {
  height: 82rpx;
  margin: 28rpx 0 0;
  border-radius: var(--radius-md);
  font-size: 27rpx;
  line-height: 82rpx;
}

.study-button {
  color: #fff;
  background: var(--color-brand);
}

.back-button {
  color: var(--color-brand);
  background: #fff;
  border: 2rpx solid rgba(85, 188, 235, .28);
}

.answer-item {
  padding: 20rpx 0;
  border-bottom: 1rpx solid var(--color-border);
}

.answer-item:last-child {
  border-bottom: 0;
}

.answer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14rpx;
}

.answer-title {
  flex: 1;
  color: var(--color-text);
  font-size: 25rpx;
  line-height: 1.55;
}

.correct,
.wrong {
  flex: none;
  font-size: 22rpx;
  font-weight: 700;
}

.correct {
  color: var(--color-success);
}

.wrong {
  color: var(--color-danger);
}

.answer-dimension {
  display: inline-block;
  margin-top: 10rpx;
  padding: 5rpx 10rpx;
  color: var(--color-brand);
  background: var(--color-brand-soft);
  border-radius: 8rpx;
  font-size: 20rpx;
}

.answer-line {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  margin-top: 12rpx;
  color: var(--color-muted);
  font-size: 22rpx;
  line-height: 1.45;
}

.answer-score {
  color: var(--color-brand);
}
</style>
