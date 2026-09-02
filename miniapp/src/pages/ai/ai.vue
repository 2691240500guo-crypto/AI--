<template>
  <view class="wrap chat-box">
    <scroll-view scroll-y class="msg-list" :scroll-into-view="scrollId">
      <view v-for="(m, i) in msgs" :key="i" :id="'msg-' + i">
        <view class="bubble bot" v-if="m.role === 'bot'">
          <text>{{ m.text }}</text>
          <text class="chart-note" v-if="m.chart">（已生成图表数据）</text>
          <view class="muted" v-if="m.type">↗ {{ m.type === 'nl2sql' ? '数据问数' : '知识检索' }}</view>
        </view>
        <view class="bubble me" v-else>{{ m.text }}</view>
      </view>
      <view class="bubble bot" v-if="loading"><text>思考中…</text></view>
    </scroll-view>

    <view class="tips">
      <text class="chip" v-for="t in recommends" :key="t" @click="ask(t)">{{ t }}</text>
    </view>
    <view class="ipt-row">
      <input class="ipt" v-model="q" placeholder="问我：统计各部门人数 / 分析人才库…" confirm-type="send" @confirm="ask(q)" />
      <view class="send" @click="ask(q)">发送</view>
    </view>
    <view class="note">回答基于内部数据与知识库，已做权限隔离与溯源</view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { askAiAssistant } from '@/api'

const q = ref('')
const loading = ref(false)
const scrollId = ref('')
const recommends = ['统计各部门的人才数量', '本科含AI骨干人数?', '帮我分析人才库整体情况']
const msgs = ref([
  { role: 'bot', text: '你好，我是 AI 人才助手 🤖 可以帮你查数据、分析人才库。试试问我？' },
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
.wrap { padding: 24rpx 24rpx 40rpx; min-height: 100vh; background: #f6f7f9; }
.msg-list { height: calc(100vh - 320rpx); overflow: hidden; }
.chat-box { display: flex; flex-direction: column; }
.bubble { max-width: 80%; padding: 20rpx 24rpx; border-radius: 28rpx; font-size: 28rpx; margin-bottom: 20rpx; line-height: 1.7; white-space: pre-wrap; }
.me { align-self: flex-end; background: #2563eb; color: #fff; border-radius: 28rpx 28rpx 6rpx 28rpx; }
.bot { align-self: flex-start; background: #fff; border: 2rpx solid #eef0f3; border-radius: 28rpx 28rpx 28rpx 6rpx; }
.chart-note { display: block; margin-top: 8rpx; font-size: 22rpx; color: #2563eb; }
.muted { font-size: 22rpx; color: #9ca3af; margin-top: 8rpx; }
.tips { margin: 12rpx 0; display: flex; flex-wrap: wrap; gap: 12rpx; }
.chip { font-size: 22rpx; padding: 6rpx 18rpx; border-radius: 40rpx; background: #eaf0ff; color: #2563eb; }
.ipt-row { display: flex; align-items: center; gap: 16rpx; margin-top: 16rpx; }
.ipt { flex: 1; background: #fff; border: 2rpx solid #e5e7eb; border-radius: 40rpx; padding: 16rpx 28rpx; font-size: 28rpx; }
.send { background: #2563eb; color: #fff; padding: 16rpx 36rpx; border-radius: 40rpx; font-size: 28rpx; }
.note { margin-top: 16rpx; font-size: 22rpx; color: #9ca3af; text-align: center; }
</style>
