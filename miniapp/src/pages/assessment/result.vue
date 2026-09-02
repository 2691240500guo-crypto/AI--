<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getMyResult, getReport } from '@/api'

const loading = ref(true)
const reportLoading = ref(false)
const result = ref(null)
const report = ref(null)
const errorMessage = ref('')

function percent(value) { return `${Math.round(Number(value || 0) * 100)}%` }
function formatDate(value) { return value ? new Date(value).toLocaleString() : '—' }
function answerText(value) { return Array.isArray(value) ? value.join('、') || '未作答' : (value ?? '未作答') }
function goBack() { uni.navigateBack() }

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
  <view class="page">
    <view v-if="loading" class="state">正在生成成绩报告...</view>
    <view v-else-if="errorMessage" class="state error">{{ errorMessage }}<text @click="goBack">返回测评</text></view>
    <template v-else-if="result?.result">
      <view class="hero"><text class="hero-label">测评完成</text><text class="hero-title">{{ result.result.paper_title }}</text><text class="hero-date">交卷时间：{{ formatDate(result.result.end_at) }}</text><view class="score"><text>{{ result.result.score || 0 }}</text><small>/ {{ result.result.paper_total_score || 0 }} 分</small></view><view class="rating">{{ report?.rating || '已完成' }} · 得分率 {{ report ? percent(report.overall_rate) : percent(result.result.paper_total_score ? Number(result.result.score) / Number(result.result.paper_total_score) : 0) }}</view></view>
      <view class="section"><view class="section-title">答题概况</view><view class="facts"><view><strong>{{ result.result.correct_count || 0 }}</strong><text>答对题数</text></view><view><strong>{{ result.result.question_count || 0 }}</strong><text>题目总数</text></view><view><strong>{{ report?.radar?.length || 0 }}</strong><text>能力维度</text></view></view></view>
      <view v-if="result.details?.length" class="section"><view class="section-title">逐题答案与得分</view><view v-for="(item, index) in result.details" :key="item.question_id" class="answer-item"><view class="answer-head"><text class="answer-title">{{ index + 1 }}. {{ item.question_content || `题目 #${item.question_id}` }}</text><text :class="item.is_correct ? 'correct' : 'wrong'">{{ item.is_correct ? '答对' : '答错' }}</text></view><text v-if="item.dimension" class="answer-dimension">{{ item.dimension }}</text><view class="answer-line"><text>你的答案：{{ answerText(item.user_answer) }}</text><text>正确答案：{{ answerText(item.correct_answer) }}</text><text class="answer-score">得分：{{ item.score || 0 }} / {{ item.question_score || 0 }} 分</text></view></view></view>
      <view v-if="reportLoading" class="report-loading">能力报告生成中，成绩和逐题答案已显示</view><view v-if="report?.radar?.length" class="section"><view class="section-title">能力维度</view><view v-for="item in report.radar" :key="item.dimension" class="dimension"><view class="dimension-head"><text>{{ item.dimension }}</text><text>{{ percent(item.rate) }} · {{ item.level }}</text></view><view class="bar"><view class="bar-fill" :style="{ width: percent(item.rate) }"></view></view><text class="dimension-score">{{ item.score }} / {{ item.total_score }} 分</text></view></view>
      <view v-if="report?.strengths?.length" class="section"><view class="section-title">优势维度</view><view class="tags"><text v-for="item in report.strengths" :key="item" class="tag green">{{ item }}</text></view></view>
      <view v-if="report?.weaknesses?.length" class="section"><view class="section-title">待提升维度</view><view class="tags"><text v-for="item in report.weaknesses" :key="item" class="tag orange">{{ item }}</text></view></view>
      <view v-if="report?.recommendations?.length" class="section"><view class="section-title">提升建议</view><view v-for="(item, index) in report.recommendations" :key="item" class="recommend"><text class="recommend-no">{{ index + 1 }}</text><text>{{ item }}</text></view></view>
      <button class="back-button" @click="goBack">返回测评记录</button>
    </template>
  </view>
</template>

<style lang="scss" scoped>
.page { min-height: 100vh; padding-bottom: 48rpx; background: #f5f7fa; }.state { padding: 120rpx 30rpx; color: #98a2b3; text-align: center; font-size: 26rpx; }.state.error { color: #b42318; }.state text { display: block; margin-top: 20rpx; color: #2563eb; }
.hero { padding: 48rpx 32rpx 42rpx; color: #fff; background: linear-gradient(135deg, #174ea6, #2563eb); text-align: center; }.hero-label { display: block; color: rgba(255,255,255,.78); font-size: 23rpx; }.hero-title { display: block; margin-top: 12rpx; font-size: 34rpx; font-weight: 700; }.hero-date { display: block; margin-top: 12rpx; color: rgba(255,255,255,.72); font-size: 21rpx; }.score { margin-top: 30rpx; }.score text { font-size: 72rpx; font-weight: 700; }.score small { margin-left: 8rpx; color: rgba(255,255,255,.78); font-size: 23rpx; }.rating { display: inline-block; margin-top: 14rpx; padding: 8rpx 18rpx; color: #eaf2ff; background: rgba(255,255,255,.16); border-radius: 24rpx; font-size: 22rpx; }
.section { margin: 20rpx 24rpx 0; padding: 26rpx; background: #fff; border-radius: 18rpx; }.section-title { margin-bottom: 22rpx; color: #1f2937; font-size: 28rpx; font-weight: 700; }.facts { display: flex; justify-content: space-around; text-align: center; }.facts view { display: flex; flex: 1; flex-direction: column; }.facts strong { color: #2563eb; font-size: 38rpx; }.facts text { margin-top: 8rpx; color: #98a2b3; font-size: 21rpx; }
.report-loading { margin: 20rpx 24rpx 0; padding: 20rpx 26rpx; color: #667085; background: #fff; border-radius: 18rpx; font-size: 23rpx; }.answer-item { padding: 20rpx 0; border-bottom: 1rpx solid #eef1f5; }.answer-item:last-child { border-bottom: 0; }.answer-head { display: flex; align-items: flex-start; gap: 14rpx; justify-content: space-between; }.answer-title { flex: 1; color: #344054; font-size: 25rpx; line-height: 1.55; }.correct, .wrong { flex: none; font-size: 22rpx; }.correct { color: #16804a; }.wrong { color: #d92d20; }.answer-dimension { display: inline-block; margin-top: 10rpx; padding: 5rpx 10rpx; color: #2563eb; background: #edf3ff; border-radius: 6rpx; font-size: 20rpx; }.answer-line { display: flex; flex-direction: column; gap: 8rpx; margin-top: 12rpx; color: #667085; font-size: 22rpx; line-height: 1.45; }.answer-score { color: #2563eb; }
.dimension { margin-bottom: 22rpx; }.dimension:last-child { margin-bottom: 0; }.dimension-head { display: flex; justify-content: space-between; color: #475467; font-size: 23rpx; }.dimension-head text:last-child { color: #2563eb; }.bar { height: 14rpx; margin-top: 12rpx; overflow: hidden; background: #edf1f6; border-radius: 10rpx; }.bar-fill { height: 100%; background: #3b82f6; border-radius: 10rpx; }.dimension-score { display: block; margin-top: 8rpx; color: #98a2b3; font-size: 20rpx; }.tags { display: flex; flex-wrap: wrap; gap: 12rpx; }.tag { padding: 8rpx 16rpx; border-radius: 20rpx; font-size: 22rpx; }.tag.green { color: #16804a; background: #e8f7ee; }.tag.orange { color: #b54708; background: #fff4e5; }.recommend { display: flex; align-items: flex-start; gap: 12rpx; margin-top: 16rpx; color: #667085; font-size: 23rpx; line-height: 1.6; }.recommend-no { width: 34rpx; height: 34rpx; flex: none; color: #2563eb; background: #edf3ff; border-radius: 50%; line-height: 34rpx; text-align: center; font-size: 19rpx; }.back-button { height: 82rpx; margin: 28rpx 24rpx 0; color: #2563eb; background: #fff; border: 2rpx solid #b9d0ff; border-radius: 41rpx; font-size: 27rpx; line-height: 78rpx; }.back-button::after { border: 0; }
</style>
