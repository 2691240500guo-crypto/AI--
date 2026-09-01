<template>
  <view class="wrap">
    <!-- 自然语言输入 -->
    <view class="card">
      <view class="card-title">Agent 智能匹配</view>
      <view class="card-sub">自然语言描述招聘/匹配需求，AI 自动拆解 → 向量语义检索 → 双重打分</view>
      <textarea
        class="ta"
        v-model="queryText"
        :disabled="loading"
        placeholder="例如：找一个 3年以上 Python 后端经验、本科的人才；招一个 AI 工程师，硕士，5年经验。"
        maxlength="500"
      />
      <view class="ta-count">{{ queryText.length }} / 500</view>
      <view class="examples">
        <view class="examples-label">试试：</view>
        <view v-for="(t, i) in examples" :key="i" class="example-chip" @click="setExample(t)">{{ t }}</view>
      </view>
      <button class="btn" :disabled="loading || !queryText.trim()" :loading="loading" @click="runMatch">
        🤖 开始 Agent 智能匹配
      </button>
    </view>

    <!-- AI 需求解析卡片 -->
    <view v-if="parsed" class="card parsed-card">
      <view class="card-title">🤖 AI 需求解析</view>
      <view class="req-row">
        <text class="req-key">核心职责</text>
        <view class="req-val">
          <text v-if="(parsed.core_duties || []).length">{{ parsed.core_duties.join('；') }}</text>
          <text v-else class="req-empty">—</text>
        </view>
      </view>
      <view class="req-row">
        <text class="req-key">必备技能</text>
        <view class="req-val">
          <text v-for="s in parsed.required_skills || []" :key="s" class="tag tag-blue">{{ s }}</text>
          <text v-if="!(parsed.required_skills || []).length" class="req-empty">—</text>
        </view>
      </view>
      <view v-if="(parsed.bonus_skills || []).length" class="req-row">
        <text class="req-key">加分技能</text>
        <view class="req-val">
          <text v-for="s in parsed.bonus_skills || []" :key="s" class="tag tag-green">{{ s }}</text>
        </view>
      </view>
      <view class="req-row">
        <text class="req-key">门槛条件</text>
        <view class="req-val">
          <text v-if="parsed.min_education" class="tag tag-orange">{{ parsed.min_education }}学历</text>
          <text v-if="parsed.min_years" class="tag tag-orange">{{ parsed.min_years }}年经验</text>
          <text v-if="!parsed.min_education && !parsed.min_years" class="req-empty">—</text>
        </view>
      </view>
      <view v-if="(parsed.soft_quality || []).length" class="req-row">
        <text class="req-key">软性素质</text>
        <view class="req-val">
          <text v-for="s in parsed.soft_quality || []" :key="s" class="tag tag-grey">{{ s }}</text>
        </view>
      </view>
    </view>

    <!-- 匹配结果 -->
    <view v-if="results.length" class="card">
      <view class="card-title">匹配结果（{{ results.length }} 人）</view>
      <view v-for="r in results" :key="r.talent_id" class="res" @click="toggle(r.talent_id)">
        <view class="res-head">
          <text class="rank">#{{ r.rank }}</text>
          <text class="talent">人才 {{ r.talent_id }}</text>
          <text class="score" :class="r.score >= 80 ? 'hi' : r.score >= 60 ? 'mid' : 'lo'">{{ r.score }}分</text>
        </view>
        <view v-if="openId === r.talent_id" class="res-detail">
          <view v-for="(v, k) in r.dims" :key="k" class="dim">
            <text class="dim-label">{{ DIM[k] || k }}</text>
            <view class="bar"><view class="bar-fill" :style="{ width: Math.min(v, 100) + '%' }" /></view>
            <text class="dim-val">{{ v }}</text>
          </view>
          <view class="explain">{{ r.explain || '暂无解释' }}</view>
        </view>
      </view>
    </view>
    <view v-else-if="done && !parsed" class="empty">
      <view class="empty-ico">🔍</view>
      <view>暂无结果</view>
      <view class="empty-tip">请在上方输入招聘/匹配需求后点击匹配</view>
    </view>
    <view v-else-if="done && parsed" class="empty">
      <view class="empty-ico">🔍</view>
      <view>未匹配到符合需求的人才</view>
      <view class="empty-tip">人才向量库当前为空，需 T 域先写入人才画像向量</view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import request from '@/utils/request'

const DIM = { skill: '技能', vector: '语义', years: '经验', quality: '素质' }

const queryText = ref('')
const loading = ref(false)
const done = ref(false)
const parsed = ref(null)
const results = ref([])
const openId = ref(null)

const examples = [
  '找一个 3年以上 Python 后端经验、本科的人才',
  '招 AI 算法工程师，硕士，5年以上经验',
  '高级前端工程师，3年 Vue3 经验',
  '数据分析师，硕士，3年经验，会 Python/SQL',
]

function setExample(t) { queryText.value = t }

onLoad(() => {
  // 无需加载岗位列表：用户用自然语言描述需求，由 LLM 解析
})

async function runMatch() {
  const q = queryText.value.trim()
  if (!q) {
    uni.showToast({ title: '请输入需求描述', icon: 'none' })
    return
  }
  loading.value = true
  done.value = false
  results.value = []
  parsed.value = null
  openId.value = null
  try {
    const res = await request({ url: '/matching/agent-match', method: 'POST', data: { query_text: q, top_k: 10 } })
    const d = res.data || {}
    results.value = d.results || []
    parsed.value = d.query_requirement || null
  } catch (e) {
    // request 已统一 toast 错误信息
  } finally {
    loading.value = false
    done.value = true
  }
}

function toggle(id) {
  openId.value = openId.value === id ? null : id
}
</script>

<style lang="scss" scoped>
.wrap { padding: 32rpx 32rpx 60rpx; min-height: 100vh; background: #f5f7fa; }
.card { background: #fff; border-radius: 20rpx; padding: 32rpx; margin-bottom: 24rpx;
  box-shadow: 0 2rpx 10rpx rgba(16,24,40,.04); }
.parsed-card { background: #f0f7ff; border: 2rpx solid #d4e6fb; }
.card-title { font-size: 30rpx; font-weight: 600; color: #1f2937; }
.card-sub { font-size: 24rpx; color: #6b7280; margin-top: 8rpx; line-height: 1.6; }
.ta { width: 100%; min-height: 180rpx; margin-top: 24rpx; padding: 20rpx; font-size: 28rpx;
  background: #f5f7fa; border-radius: 14rpx; box-sizing: border-box; }
.ta-count { text-align: right; color: #9ca3af; font-size: 22rpx; margin-top: 8rpx; }
.examples { margin-top: 20rpx; display: flex; flex-wrap: wrap; gap: 14rpx; align-items: center; }
.examples-label { font-size: 24rpx; color: #6b7280; }
.example-chip { font-size: 22rpx; color: #2563eb; background: #e6f1fb; padding: 8rpx 20rpx;
  border-radius: 999rpx; }
.btn { margin-top: 28rpx; background: #2563eb; color: #fff; border-radius: 14rpx; font-size: 30rpx;
  height: 88rpx; line-height: 88rpx; }
.btn[disabled] { opacity: .6; background: #93c5fd; }
.req-row { display: flex; gap: 16rpx; margin-top: 18rpx; align-items: flex-start; }
.req-key { flex-shrink: 0; width: 130rpx; color: #6b7280; font-size: 26rpx; padding-top: 4rpx; }
.req-val { flex: 1; display: flex; flex-wrap: wrap; gap: 12rpx; line-height: 1.7; font-size: 26rpx; color: #1f2937; }
.req-empty { color: #9ca3af; }
.tag { display: inline-block; padding: 6rpx 20rpx; border-radius: 999rpx; font-size: 24rpx; }
.tag-blue { background: #e6f1fb; color: #185fa5; }
.tag-green { background: #eaf3de; color: #3b6d11; }
.tag-orange { background: #faeeda; color: #854f0b; }
.tag-grey { background: #f1efe8; color: #444441; }
.res { border-top: 2rpx solid #f0f2f5; padding: 24rpx 0; }
.res-head { display: flex; align-items: center; gap: 16rpx; }
.rank { color: #9ca3af; font-size: 24rpx; }
.talent { flex: 1; color: #1f2937; font-size: 28rpx; }
.score { font-size: 28rpx; font-weight: 700; }
.hi { color: #16a34a; }
.mid { color: #f59e0b; }
.lo { color: #ef4444; }
.res-detail { margin-top: 20rpx; background: #fff; border-radius: 14rpx; padding: 24rpx; }
.dim { display: flex; align-items: center; gap: 14rpx; margin-bottom: 14rpx; }
.dim-label { width: 80rpx; color: #6b7280; font-size: 24rpx; }
.bar { flex: 1; height: 16rpx; background: #e5e7eb; border-radius: 8rpx; overflow: hidden; }
.bar-fill { height: 100%; background: #2563eb; border-radius: 8rpx; }
.dim-val { width: 70rpx; text-align: right; color: #1f2937; font-size: 24rpx; }
.explain { color: #374151; font-size: 26rpx; line-height: 1.7; margin-top: 16rpx; }
.empty { text-align: center; color: #9ca3af; padding: 80rpx 0; }
.empty-ico { font-size: 64rpx; margin-bottom: 16rpx; }
.empty-tip { font-size: 22rpx; margin-top: 10rpx; }
</style>