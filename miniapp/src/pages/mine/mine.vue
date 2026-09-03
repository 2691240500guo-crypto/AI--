<script setup>
import { computed, onMounted, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getCurrentUser, getMyTalentProfile, getUnreadCount } from '@/api'
import GrowthPath from '@/components/GrowthPath.vue'

const loading = ref(false)
const user = ref(uni.getStorageSync('user') || {})
const profile = ref(null)
const unread = ref(0)

const displayName = computed(() => (
  profile.value?.name
  || user.value?.nickname
  || user.value?.username
  || '未命名用户'
))
const avatarText = computed(() => String(displayName.value || '用').slice(0, 1))
const titleText = computed(() => profile.value?.current_title || profile.value?.level || '企业员工')
const tags = computed(() => (profile.value?.tags || []).slice(0, 4))
const yearsText = computed(() => `${Number(profile.value?.years_experience || 0)} 年`)

const stats = computed(() => [
  { label: '未读消息', value: unread.value },
  { label: '画像标签', value: tags.value.length },
  { label: '从业年限', value: yearsText.value }
])

const growthSteps = computed(() => [
  { label: '档案', mark: '档', status: profile.value ? 'done' : 'current', caption: profile.value ? '已关联' : '待关联' },
  { label: '测评', mark: '测', status: 'current', caption: '能力诊断' },
  { label: '学习', mark: '学', status: 'todo', caption: '提升记录' },
  { label: '岗位', mark: '岗', status: 'todo', caption: '适配推荐' }
])

const menus = computed(() => [
  { title: '成长事件', desc: unread.value ? `${unread.value} 条未读` : '查看平台通知', mark: '息', url: '/pages/message/message', type: 'tab' },
  { title: '我的档案', desc: profile.value ? '查看个人画像' : '等待档案关联', mark: '档', url: '/pages/profile/profile' },
  { title: 'AI 助手', desc: '询问能力与学习建议', mark: 'AI', url: '/pages/ai/ai' },
  { title: '在线学习', desc: '查看学习计划与课程', mark: '学', url: '/pages/study/study', type: 'tab' }
])

onMounted(load)
onShow(refreshUnread)

async function load() {
  if (!uni.getStorageSync('token')) {
    uni.reLaunch({ url: '/pages/login/login' })
    return
  }

  loading.value = true
  try {
    const [userResult, profileResult, unreadResult] = await Promise.allSettled([
      getCurrentUser(),
      getMyTalentProfile(),
      getUnreadCount()
    ])

    if (userResult.status === 'fulfilled') {
      user.value = { ...user.value, ...(userResult.value.data || {}) }
      uni.setStorageSync('user', user.value)
    }
    if (profileResult.status === 'fulfilled') {
      profile.value = profileResult.value.data || null
    }
    if (unreadResult.status === 'fulfilled') {
      unread.value = Number(unreadResult.value.data?.unread || 0)
    }
  } finally {
    loading.value = false
  }
}

async function refreshUnread() {
  if (!uni.getStorageSync('token')) return
  try {
    const res = await getUnreadCount()
    unread.value = Number(res.data?.unread || 0)
  } catch (error) {
    unread.value = 0
  }
}

function go(item) {
  if (item.type === 'tab') {
    uni.switchTab({ url: item.url })
    return
  }
  uni.navigateTo({ url: item.url })
}

function logout() {
  uni.showModal({
    title: '退出登录',
    content: '确认退出当前账号？',
    success: (res) => {
      if (!res.confirm) return
      uni.removeStorageSync('token')
      uni.removeStorageSync('refresh_token')
      uni.removeStorageSync('user')
      uni.reLaunch({ url: '/pages/login/login' })
    }
  })
}
</script>

<template>
  <view class="app-page mine-page">
    <view class="profile-panel surface">
      <view class="avatar">{{ avatarText }}</view>
      <view class="profile-main">
        <view class="name-row">
          <text class="name">{{ displayName }}</text>
          <text class="badge">{{ titleText }}</text>
        </view>
        <view class="sub">
          {{ user.username || 'employee' }} · {{ user.dept_id ? `部门 ${user.dept_id}` : '员工自助端' }}
        </view>
        <view class="tag-row">
          <text v-for="tag in tags" :key="tag.id || tag.name" class="tag">{{ tag.name }}</text>
          <text v-if="!tags.length" class="tag muted-tag">暂无画像标签</text>
        </view>
      </view>
    </view>

    <view class="growth-panel surface">
      <view class="section-title">我的数字人才画像</view>
      <GrowthPath :steps="growthSteps" compact />
    </view>

    <view class="stats surface">
      <view v-for="item in stats" :key="item.label" class="stat">
        <view class="stat-value">{{ item.value }}</view>
        <view class="stat-label">{{ item.label }}</view>
      </view>
    </view>

    <view class="section surface">
      <view class="section-title">常用入口</view>
      <view
        v-for="item in menus"
        :key="item.title"
        class="menu-item"
        @click="go(item)"
      >
        <view class="menu-mark">{{ item.mark }}</view>
        <view class="menu-copy">
          <view class="menu-title">{{ item.title }}</view>
          <view class="menu-desc">{{ item.desc }}</view>
        </view>
        <view class="arrow">›</view>
      </view>
    </view>

    <view class="section surface">
      <view class="section-title">账号信息</view>
      <view class="info-row">
        <text>手机号</text>
        <text>{{ profile?.phone_masked || user.phone || '-' }}</text>
      </view>
      <view class="info-row">
        <text>邮箱</text>
        <text>{{ profile?.email || user.email || '-' }}</text>
      </view>
      <view class="info-row">
        <text>人才档案</text>
        <text>{{ profile?.id ? `#${profile.id}` : '未关联' }}</text>
      </view>
    </view>

    <button class="logout" :loading="loading" @click="logout">退出登录</button>
  </view>
</template>

<style lang="scss" scoped>
.mine-page {
  padding-bottom: 72rpx;
}

.profile-panel {
  display: flex;
  gap: 24rpx;
  padding: 32rpx 30rpx;
}

.avatar {
  width: 112rpx;
  height: 112rpx;
  flex-shrink: 0;
  color: #fff;
  background: linear-gradient(135deg, var(--color-brand), var(--color-sky));
  border-radius: 26rpx;
  font-size: 44rpx;
  font-weight: 800;
  line-height: 112rpx;
  text-align: center;
}

.profile-main {
  min-width: 0;
  flex: 1;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.name {
  max-width: 250rpx;
  overflow: hidden;
  color: var(--color-text);
  font-size: 34rpx;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.badge {
  max-width: 188rpx;
  height: 38rpx;
  padding: 0 14rpx;
  overflow: hidden;
  color: var(--color-coral);
  background: var(--color-coral-soft);
  border-radius: var(--radius-sm);
  font-size: 20rpx;
  line-height: 38rpx;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sub {
  margin-top: 8rpx;
  color: var(--color-muted);
  font-size: 23rpx;
  line-height: 1.5;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-top: 16rpx;
}

.tag {
  height: 40rpx;
  padding: 0 14rpx;
  color: var(--color-brand);
  background: var(--color-brand-soft);
  border-radius: var(--radius-sm);
  font-size: 20rpx;
  line-height: 40rpx;
}

.muted-tag {
  color: var(--color-muted);
  background: #EEF4F7;
}

.growth-panel,
.section,
.stats {
  margin-top: 20rpx;
  padding: 26rpx;
}

.stats {
  display: flex;
  gap: 18rpx;
}

.stat {
  flex: 1;
  min-width: 0;
  text-align: center;
}

.stat-value {
  overflow: hidden;
  color: var(--color-brand);
  font-size: 34rpx;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stat-label {
  margin-top: 8rpx;
  color: var(--color-muted);
  font-size: 22rpx;
}

.section-title {
  margin-bottom: 18rpx;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 18rpx;
  padding: 22rpx 0;
  border-bottom: 1rpx solid var(--color-border);
}

.menu-item:last-child {
  border-bottom: none;
}

.menu-mark {
  width: 54rpx;
  height: 54rpx;
  flex-shrink: 0;
  color: var(--color-brand);
  background: var(--color-brand-soft);
  border-radius: 16rpx;
  font-size: 20rpx;
  font-weight: 800;
  line-height: 54rpx;
  text-align: center;
}

.menu-copy {
  min-width: 0;
  flex: 1;
}

.menu-title {
  color: var(--color-text);
  font-size: 28rpx;
  font-weight: 700;
}

.menu-desc {
  margin-top: 6rpx;
  color: var(--color-muted);
  font-size: 22rpx;
}

.arrow {
  flex-shrink: 0;
  color: #B6C7CF;
  font-size: 38rpx;
}

.info-row {
  display: flex;
  justify-content: space-between;
  gap: 24rpx;
  padding: 22rpx 0;
  border-bottom: 1rpx solid var(--color-border);
  color: var(--color-muted);
  font-size: 25rpx;
}

.info-row:last-child {
  border-bottom: none;
}

.info-row text:last-child {
  flex: 1;
  overflow-wrap: break-word;
  color: var(--color-text);
  text-align: right;
}

.logout {
  height: 82rpx;
  margin: 28rpx 0 0;
  color: var(--color-danger);
  background: #fff;
  border: 1rpx solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 28rpx;
  line-height: 82rpx;
}
</style>
