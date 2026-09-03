<template>
  <view class="ai-page">
    <view class="assistant-head surface">
      <view class="mark">AI</view>
      <view class="head-copy">
        <text class="eyebrow">人才成长 AI 助手</text>
        <text class="head-title">围绕能力、学习和岗位给出建议</text>
      </view>
    </view>

    <scroll-view scroll-y class="msg-list" :scroll-into-view="scrollId">
      <view v-for="(m, i) in msgs" :key="i" :id="'msg-' + i" class="message-row" :class="m.role">
        <view class="bubble" :class="m.role === 'bot' ? 'bot' : 'me'">
          <text>{{ m.text }}</text>
          <text class="chart-note" v-if="m.chart">已生成图表数据</text>
          <view class="muted" v-if="m.type">{{ m.type === 'nl2sql' ? '数据问数' : m.type === 'error' ? '请求异常' : '知识检索' }}</view>
        </view>
      </view>
      <view class="message-row bot" v-if="loading">
        <view class="bubble bot"><text>正在分析...</text></view>
      </view>
    </scroll-view>

    <view class="tips">
      <text class="chip" v-for="t in recommends" :key="t" @click="ask(t)">{{ t }}</text>
    </view>
    <view class="ipt-row">
      <input class="ipt" v-model="q" placeholder="问我你的能力、学习或岗位建议" confirm-type="send" @confirm="ask(q)" />
      <view class="send" @click="ask(q)">发送</view>
    </view>
    <view class="note">回答基于内部数据与知识库，已做权限隔离与溯源。</view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { askAiAssistant } from '@/api'

const q = ref('')
const loading = ref(false)
const scrollId = ref('')
const recommends = ['我的能力短板是什么？', '我最近应该学什么？', '为什么推荐这个岗位？', '我的学习进度如何？']
const msgs = ref([
  { role: 'bot', text: '你好，我是你的人才成长 AI 助手。可以帮你分析能力短板、学习计划和岗位适配。' }
])

function push(role, text, extra = {}) {
  msgs.value.push({ role, text, ...extra })
  scrollId.value = 'msg-' + (msgs.value.length - 1)
}

async function ask(text) {
  const msg = (text ?? q.value ?? '').trim()
  if (!msg || loading.value) return
  q.value = ''
  push('me', msg)
  loading.value = true
  try {
    const res = await askAiAssistant(msg)
    const d = res.data || {}
    const answer = (d.answer || '抱歉，暂时没想好怎么回答。').replace(/\n/g, '\n')
    push('bot', answer, { chart: !!d.chart_json, type: d.type })
  } catch (e) {
    push('bot', '请求失败，请检查网络或稍后再试。', { type: 'error' })
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.ai-page {
  min-height: 100vh;
  padding: 24rpx 24rpx 40rpx;
  background:
    linear-gradient(180deg, rgba(63, 167, 214, .16) 0, rgba(247, 251, 253, 0) 340rpx),
    var(--color-bg);
  box-sizing: border-box;
}

.assistant-head {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 26rpx;
}

.mark {
  width: 74rpx;
  height: 74rpx;
  flex-shrink: 0;
  color: #fff;
  background: linear-gradient(135deg, var(--color-brand), var(--color-sky));
  border-radius: 22rpx;
  font-size: 26rpx;
  font-weight: 850;
  line-height: 74rpx;
  text-align: center;
}

.head-copy {
  min-width: 0;
}

.eyebrow,
.head-title {
  display: block;
}

.eyebrow {
  color: var(--color-coral);
  font-size: 22rpx;
  font-weight: 800;
}

.head-title {
  margin-top: 7rpx;
  color: var(--color-text);
  font-size: 30rpx;
  font-weight: 750;
  line-height: 1.35;
}

.msg-list {
  height: calc(100vh - 392rpx);
  margin-top: 20rpx;
  overflow: hidden;
}

.message-row {
  display: flex;
  margin-bottom: 18rpx;
}

.message-row.me {
  justify-content: flex-end;
}

.message-row.bot {
  justify-content: flex-start;
}

.bubble {
  max-width: 82%;
  padding: 20rpx 24rpx;
  border-radius: 22rpx;
  font-size: 27rpx;
  line-height: 1.7;
  white-space: pre-wrap;
  box-sizing: border-box;
}

.bubble.me {
  color: #fff;
  background: var(--color-brand);
  border-radius: 22rpx 22rpx 6rpx 22rpx;
}

.bubble.bot {
  color: var(--color-text);
  background: #fff;
  border: 1rpx solid var(--color-border);
  border-radius: 22rpx 22rpx 22rpx 6rpx;
}

.chart-note {
  display: block;
  margin-top: 8rpx;
  color: var(--color-brand);
  font-size: 22rpx;
}

.muted {
  margin-top: 8rpx;
  color: var(--color-muted);
  font-size: 22rpx;
}

.tips {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin: 12rpx 0;
}

.chip {
  padding: 8rpx 16rpx;
  color: var(--color-brand);
  background: var(--color-brand-soft);
  border-radius: var(--radius-sm);
  font-size: 22rpx;
}

.ipt-row {
  display: flex;
  align-items: center;
  gap: 14rpx;
  margin-top: 16rpx;
}

.ipt {
  flex: 1;
  height: 78rpx;
  padding: 0 24rpx;
  background: #fff;
  border: 2rpx solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 27rpx;
  box-sizing: border-box;
}

.send {
  height: 78rpx;
  padding: 0 30rpx;
  color: #fff;
  background: var(--color-coral);
  border-radius: var(--radius-md);
  font-size: 27rpx;
  font-weight: 700;
  line-height: 78rpx;
}

.note {
  margin-top: 16rpx;
  color: var(--color-muted);
  font-size: 22rpx;
  line-height: 1.45;
  text-align: center;
}
</style>
