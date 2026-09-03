<template>
  <view class="app-page match-page">
    <view class="hero surface">
      <text class="eyebrow">岗位适配</text>
      <text class="hero-title">Agent 智能匹配</text>
      <text class="hero-sub">用自然语言描述需求，系统拆解条件并给出人才匹配结果。</text>
    </view>

    <view class="card surface">
      <view class="card-title">匹配需求</view>
      <textarea
        class="ta"
        v-model="queryText"
        :disabled="loading"
        placeholder="例如：找一个 3 年以上 Python 后端经验、本科的人才。"
        maxlength="500"
      />
      <view class="ta-count">{{ queryText.length }} / 500</view>
      <view class="examples">
        <view class="examples-label">快速填入</view>
        <view v-for="(t, i) in examples" :key="i" class="example-chip" @click="setExample(t)">{{ t }}</view>
      </view>
      <button class="btn" :disabled="loading || !queryText.trim()" :loading="loading" @click="runMatch">
        开始智能匹配
      </button>
    </view>

    <view v-if="parsed" class="card parsed-card surface">
      <view class="card-title">AI 需求解析</view>
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
          <text v-if="parsed.min_education" class="tag tag-coral">{{ parsed.min_education }}学历</text>
          <text v-if="parsed.min_years" class="tag tag-coral">{{ parsed.min_years }}年经验</text>
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

    <view v-if="results.length" class="card surface">
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

    <view v-else-if="done && !parsed" class="empty surface">
      <view class="empty-mark">查</view>
      <view>暂无结果</view>
      <view class="empty-tip">请在上方输入招聘或匹配需求后点击匹配。</view>
    </view>
    <view v-else-if="done && parsed" class="empty surface">
      <view class="empty-mark">空</view>
      <view>未匹配到符合需求的人才</view>
      <view class="empty-tip">人才向量库当前为空，需 T 域先写入人才画像向量。</view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import request from '@/utils/request'

const DIM = { skill: '技能', degree: '学历', vector: '语义', years: '经验', quality: '素质' }

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
  '数据分析师，硕士，3年经验，会 Python/SQL'
]

function setExample(t) { queryText.value = t }

onLoad(() => {})

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
.match-page {
  padding-bottom: 72rpx;
}

.hero,
.card {
  padding: 30rpx;
  margin-bottom: 22rpx;
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
  font-size: 42rpx;
  font-weight: 800;
}

.hero-sub {
  margin-top: 10rpx;
  color: var(--color-muted);
  font-size: 24rpx;
  line-height: 1.55;
}

.card-title {
  color: var(--color-text);
  font-size: 30rpx;
  font-weight: 750;
}

.ta {
  width: 100%;
  min-height: 184rpx;
  margin-top: 24rpx;
  padding: 20rpx;
  background: #F9FCFD;
  border: 1rpx solid var(--color-border);
  border-radius: var(--radius-md);
  box-sizing: border-box;
  color: var(--color-text);
  font-size: 28rpx;
}

.ta-count {
  margin-top: 8rpx;
  color: var(--color-muted);
  font-size: 22rpx;
  text-align: right;
}

.examples {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 14rpx;
  margin-top: 20rpx;
}

.examples-label {
  color: var(--color-muted);
  font-size: 24rpx;
}

.example-chip {
  padding: 8rpx 16rpx;
  color: var(--color-brand);
  background: var(--color-brand-soft);
  border-radius: var(--radius-sm);
  font-size: 22rpx;
}

.btn {
  height: 88rpx;
  margin-top: 28rpx;
  color: #fff;
  background: var(--color-brand);
  border-radius: var(--radius-md);
  font-size: 30rpx;
  font-weight: 700;
  line-height: 88rpx;
}

.btn[disabled] {
  color: #A7B7C0;
  background: #EAF2F6;
}

.parsed-card {
  background: linear-gradient(135deg, #FFFFFF, #F1FAFD);
}

.req-row {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  margin-top: 18rpx;
}

.req-key {
  width: 130rpx;
  flex-shrink: 0;
  padding-top: 4rpx;
  color: var(--color-muted);
  font-size: 26rpx;
}

.req-val {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
  gap: 12rpx;
  color: var(--color-text);
  font-size: 26rpx;
  line-height: 1.7;
}

.req-empty {
  color: var(--color-muted);
}

.tag {
  display: inline-block;
  padding: 6rpx 16rpx;
  border-radius: var(--radius-sm);
  font-size: 24rpx;
}

.tag-blue {
  color: var(--color-brand);
  background: var(--color-brand-soft);
}

.tag-green {
  color: var(--color-success);
  background: #E9F8F3;
}

.tag-coral {
  color: var(--color-coral);
  background: var(--color-coral-soft);
}

.tag-grey {
  color: var(--color-muted);
  background: #EEF4F7;
}

.res {
  padding: 24rpx 0;
  border-top: 1rpx solid var(--color-border);
}

.res:first-of-type {
  border-top: 0;
}

.res-head {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.rank {
  color: var(--color-muted);
  font-size: 24rpx;
}

.talent {
  flex: 1;
  color: var(--color-text);
  font-size: 28rpx;
  font-weight: 700;
}

.score {
  font-size: 28rpx;
  font-weight: 800;
}

.hi {
  color: var(--color-success);
}

.mid {
  color: var(--color-warning);
}

.lo {
  color: var(--color-danger);
}

.res-detail {
  margin-top: 20rpx;
  padding: 24rpx;
  background: #F9FCFD;
  border: 1rpx solid var(--color-border);
  border-radius: var(--radius-md);
}

.dim {
  display: flex;
  align-items: center;
  gap: 14rpx;
  margin-bottom: 14rpx;
}

.dim-label {
  width: 80rpx;
  color: var(--color-muted);
  font-size: 24rpx;
}

.bar {
  height: 16rpx;
  flex: 1;
  overflow: hidden;
  background: #ECF4F7;
  border-radius: 8rpx;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-brand), var(--color-coral));
  border-radius: 8rpx;
}

.dim-val {
  width: 70rpx;
  color: var(--color-text);
  font-size: 24rpx;
  text-align: right;
}

.explain {
  margin-top: 16rpx;
  color: var(--color-text);
  font-size: 26rpx;
  line-height: 1.7;
}

.empty {
  padding: 72rpx 24rpx;
  color: var(--color-muted);
  text-align: center;
}

.empty-mark {
  width: 64rpx;
  height: 64rpx;
  margin: 0 auto 16rpx;
  color: var(--color-coral);
  background: var(--color-coral-soft);
  border-radius: 50%;
  font-size: 24rpx;
  font-weight: 800;
  line-height: 64rpx;
}

.empty-tip {
  margin-top: 10rpx;
  font-size: 22rpx;
  line-height: 1.45;
}
</style>
