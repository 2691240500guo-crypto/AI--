<script setup>
import { computed, onMounted, ref } from 'vue'
import { currentTalentId } from '@/api'
import GrowthPath from '@/components/GrowthPath.vue'
import request from '@/utils/request'

const user = ref({})
const growth = ref(72)
const stats = ref([
  { key: 'messages', label: '未读消息', value: '-', mark: '息', tone: 'blue' },
  { key: 'assessment', label: '待完成测评', value: '-', mark: '测', tone: 'coral' },
  { key: 'study', label: '学习计划', value: '-', mark: '学', tone: 'green' }
])

const skills = ref([
  { name: 'AI 应用', score: 85 },
  { name: 'Python', score: 92 },
  { name: '项目协同', score: 78 }
])

const entries = [
  { name: '我的档案', desc: '查看数字人才画像', mark: '档', url: '/pages/profile/profile' },
  { name: '在线测评', desc: '发现能力短板', mark: '测', url: '/pages/assessment/assessment' },
  { name: '在线学习', desc: '继续提升能力', mark: '学', url: '/pages/study/study' },
  { name: 'AI 助手', desc: '询问成长建议', mark: 'AI', url: '/pages/ai/ai' }
]

const unreadCount = computed(() => numberOf(stats.value[0].value))
const todoCount = computed(() => numberOf(stats.value[1].value))
const planCount = computed(() => numberOf(stats.value[2].value))

const nextAction = computed(() => {
  if (todoCount.value > 0) {
    return {
      title: '完成待测评',
      desc: `还有 ${todoCount.value} 项测评等待完成，先诊断能力现状。`,
      button: '去测评',
      url: '/pages/assessment/assessment'
    }
  }
  if (planCount.value > 0) {
    return {
      title: '继续学习计划',
      desc: `已有 ${planCount.value} 个学习计划，可继续推进成长节点。`,
      button: '继续学习',
      url: '/pages/study/study'
    }
  }
  if (unreadCount.value > 0) {
    return {
      title: '查看成长事件',
      desc: `${unreadCount.value} 条消息可能包含测评、学习或岗位提醒。`,
      button: '看消息',
      url: '/pages/message/message'
    }
  }
  return {
    title: '完善数字人才画像',
    desc: '查看档案、技能标签和成长记录，让推荐更准确。',
    button: '看画像',
    url: '/pages/profile/profile'
  }
})

const growthSteps = computed(() => [
  { label: '档案', mark: '档', status: 'done', caption: '画像已建立' },
  { label: '测评', mark: '测', status: todoCount.value > 0 ? 'current' : 'done', caption: todoCount.value > 0 ? '等待完成' : '能力已诊断' },
  { label: '诊断', mark: '诊', status: todoCount.value > 0 ? 'todo' : 'done', caption: '识别优势短板' },
  { label: '学习', mark: '学', status: planCount.value > 0 ? 'current' : 'todo', caption: '推进提升计划' },
  { label: '适配', mark: '岗', status: 'todo', caption: '岗位匹配推荐' }
])

onMounted(async () => {
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
      request({ url: '/training/plans', data: { talent_id: currentTalentId() } })
    ])
    stats.value[0].value = msg.data?.unread ?? 0
    stats.value[1].value = Array.isArray(todo.data) ? todo.data.length : (todo.data?.items?.length ?? 0)
    stats.value[2].value = Array.isArray(plans.data) ? plans.data.length : (plans.data?.items?.length ?? 0)
  } catch (e) {
    stats.value = stats.value.map((item) => ({ ...item, value: item.value === '-' ? 0 : item.value }))
  }
}

function numberOf(value) {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
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

function logout() {
  uni.removeStorageSync('token')
  uni.removeStorageSync('refresh_token')
  uni.removeStorageSync('user')
  uni.reLaunch({ url: '/pages/login/login' })
}
</script>

<template>
  <view class="app-page home-page">
    <view class="hero surface">
      <view class="hero-top">
        <view>
          <text class="brand">智链成长</text>
          <text class="hello">你好，{{ user.nickname || user.username || '同学' }}</text>
        </view>
        <view class="logout" @click="logout">退出</view>
      </view>
      <text class="hero-title">我的人才成长工作台</text>
      <text class="hero-sub">看见当前位置，明确下一步行动。</text>

      <view class="progress-panel">
        <view>
          <text class="stage-label">当前成长完成度</text>
          <text class="stage-value">{{ growth }}%</text>
        </view>
        <view class="ring">
          <text>{{ todoCount > 0 ? '待测' : '成长' }}</text>
        </view>
      </view>
      <GrowthPath :steps="growthSteps" />
    </view>

    <view class="next-action surface" @click="go(nextAction.url)">
      <view class="action-copy">
        <text class="action-kicker">下一步建议</text>
        <text class="action-title">{{ nextAction.title }}</text>
        <text class="action-desc">{{ nextAction.desc }}</text>
      </view>
      <view class="action-button">{{ nextAction.button }}</view>
    </view>

    <view class="stat-grid">
      <view v-for="item in stats" :key="item.key" class="stat surface" :class="item.tone">
        <text class="stat-mark">{{ item.mark }}</text>
        <text class="stat-value">{{ item.value }}</text>
        <text class="stat-label">{{ item.label }}</text>
      </view>
    </view>

    <view class="section-head">
      <text class="section-title">能力画像</text>
      <text class="section-note">本阶段概览</text>
    </view>
    <view class="skill-card surface">
      <view v-for="skill in skills" :key="skill.name" class="skill-row">
        <view class="skill-head">
          <text>{{ skill.name }}</text>
          <text>{{ skill.score }}</text>
        </view>
        <view class="skill-track">
          <view class="skill-fill" :style="{ width: skill.score + '%' }"></view>
        </view>
      </view>
    </view>

    <view class="section-head">
      <text class="section-title">常用入口</text>
      <text class="section-note">围绕成长闭环</text>
    </view>
    <view class="entry-grid">
      <view v-for="entry in entries" :key="entry.name" class="entry surface" @click="go(entry.url)">
        <view class="entry-mark">{{ entry.mark }}</view>
        <view class="entry-copy">
          <text class="entry-name">{{ entry.name }}</text>
          <text class="entry-desc">{{ entry.desc }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.home-page {
  padding-bottom: 72rpx;
}

.hero {
  position: relative;
  overflow: hidden;
  padding: 34rpx 30rpx 30rpx;
  border-color: rgba(85, 188, 235, .16);
}

.hero::after {
  position: absolute;
  top: -80rpx;
  right: -88rpx;
  width: 240rpx;
  height: 240rpx;
  border: 28rpx solid rgba(255, 127, 120, .12);
  border-radius: 50%;
  content: '';
}

.hero-top,
.progress-panel,
.stat,
.entry {
  display: flex;
  align-items: center;
}

.hero-top {
  position: relative;
  z-index: 1;
  justify-content: space-between;
  gap: 24rpx;
}

.brand,
.hello,
.hero-title,
.hero-sub,
.stage-label,
.stage-value {
  display: block;
}

.brand {
  color: var(--color-brand);
  font-size: 23rpx;
  font-weight: 700;
}

.hello {
  margin-top: 8rpx;
  color: var(--color-muted);
  font-size: 24rpx;
}

.logout {
  flex-shrink: 0;
  padding: 10rpx 18rpx;
  color: var(--color-muted);
  background: #F2F8FB;
  border-radius: var(--radius-sm);
  font-size: 22rpx;
}

.hero-title {
  position: relative;
  z-index: 1;
  margin-top: 36rpx;
  color: var(--color-text);
  font-size: 46rpx;
  font-weight: 800;
  line-height: 1.18;
}

.hero-sub {
  position: relative;
  z-index: 1;
  margin-top: 12rpx;
  color: var(--color-muted);
  font-size: 25rpx;
}

.progress-panel {
  position: relative;
  z-index: 1;
  justify-content: space-between;
  margin: 34rpx 0 30rpx;
  padding: 24rpx;
  background: linear-gradient(135deg, #F0FAFD, #FFF5F3);
  border: 1rpx solid rgba(221, 236, 242, .9);
  border-radius: var(--radius-md);
}

.stage-label {
  color: var(--color-muted);
  font-size: 22rpx;
}

.stage-value {
  margin-top: 4rpx;
  color: var(--color-brand);
  font-size: 52rpx;
  font-weight: 800;
  line-height: 1.1;
}

.ring {
  width: 110rpx;
  height: 110rpx;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-coral);
  border: 12rpx solid rgba(255, 127, 120, .24);
  border-top-color: var(--color-coral);
  border-radius: 50%;
  font-size: 24rpx;
  font-weight: 700;
}

.next-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  margin-top: 22rpx;
  padding: 26rpx;
  border-color: rgba(255, 127, 120, .28);
}

.action-copy {
  min-width: 0;
  flex: 1;
}

.action-kicker,
.action-title,
.action-desc {
  display: block;
}

.action-kicker {
  color: var(--color-coral);
  font-size: 21rpx;
  font-weight: 700;
}

.action-title {
  margin-top: 7rpx;
  color: var(--color-text);
  font-size: 31rpx;
  font-weight: 750;
}

.action-desc {
  margin-top: 8rpx;
  color: var(--color-muted);
  font-size: 23rpx;
  line-height: 1.45;
}

.action-button {
  flex-shrink: 0;
  min-width: 132rpx;
  height: 62rpx;
  padding: 0 18rpx;
  color: #fff;
  background: var(--color-coral);
  border-radius: var(--radius-sm);
  font-size: 24rpx;
  font-weight: 700;
  line-height: 62rpx;
  text-align: center;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14rpx;
  margin-top: 22rpx;
}

.stat {
  min-width: 0;
  flex-direction: column;
  padding: 22rpx 8rpx;
}

.stat-mark {
  width: 48rpx;
  height: 48rpx;
  color: var(--color-brand);
  background: var(--color-brand-soft);
  border-radius: 16rpx;
  font-size: 21rpx;
  font-weight: 800;
  line-height: 48rpx;
  text-align: center;
}

.stat.coral .stat-mark {
  color: var(--color-coral);
  background: var(--color-coral-soft);
}

.stat.green .stat-mark {
  color: var(--color-success);
  background: #E9F8F3;
}

.stat-value {
  margin-top: 14rpx;
  color: var(--color-text);
  font-size: 38rpx;
  font-weight: 800;
  line-height: 1;
}

.stat-label {
  margin-top: 9rpx;
  color: var(--color-muted);
  font-size: 21rpx;
}

.skill-card {
  padding: 26rpx;
}

.skill-row + .skill-row {
  margin-top: 22rpx;
}

.skill-head {
  display: flex;
  justify-content: space-between;
  color: var(--color-text);
  font-size: 24rpx;
  font-weight: 650;
}

.skill-head text:last-child {
  color: var(--color-brand);
}

.skill-track {
  height: 12rpx;
  margin-top: 12rpx;
  overflow: hidden;
  background: #ECF4F7;
  border-radius: 8rpx;
}

.skill-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-brand), var(--color-coral));
  border-radius: 8rpx;
}

.entry-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16rpx;
}

.entry {
  gap: 18rpx;
  min-height: 126rpx;
  padding: 22rpx;
}

.entry-mark {
  width: 58rpx;
  height: 58rpx;
  flex-shrink: 0;
  color: var(--color-brand);
  background: var(--color-brand-soft);
  border-radius: 18rpx;
  font-size: 22rpx;
  font-weight: 800;
  line-height: 58rpx;
  text-align: center;
}

.entry-copy {
  min-width: 0;
}

.entry-name,
.entry-desc {
  display: block;
}

.entry-name {
  color: var(--color-text);
  font-size: 27rpx;
  font-weight: 700;
}

.entry-desc {
  margin-top: 6rpx;
  color: var(--color-muted);
  font-size: 21rpx;
  line-height: 1.35;
}
</style>
