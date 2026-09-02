<script setup>
import { computed, onMounted, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getCurrentUser, getMyTalentProfile, getUnreadCount } from '@/api'

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

const menus = computed(() => [
  { title: '消息通知', desc: unread.value ? `${unread.value} 条未读` : '查看平台通知', url: '/pages/message/message', type: 'tab' },
  { title: '我的档案', desc: profile.value ? '查看个人画像' : '等待档案关联', url: '/pages/profile/profile' },
  { title: 'AI 助手', desc: '问数与人才问答', url: '/pages/ai/ai' },
  { title: '在线学习', desc: '查看学习计划与课程', url: '/pages/study/study', type: 'tab' }
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
  <view class="wrap">
    <view class="profile-panel">
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

    <view class="stats">
      <view v-for="item in stats" :key="item.label" class="stat">
        <view class="stat-value">{{ item.value }}</view>
        <view class="stat-label">{{ item.label }}</view>
      </view>
    </view>

    <view class="section">
      <view class="section-title">常用入口</view>
      <view
        v-for="item in menus"
        :key="item.title"
        class="menu-item"
        @click="go(item)"
      >
        <view>
          <view class="menu-title">{{ item.title }}</view>
          <view class="menu-desc">{{ item.desc }}</view>
        </view>
        <view class="arrow">›</view>
      </view>
    </view>

    <view class="section">
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
.wrap {
  min-height: 100vh;
  padding: 24rpx 24rpx 48rpx;
  background: #f6f7f9;
  box-sizing: border-box;
}
.profile-panel {
  display: flex;
  gap: 24rpx;
  padding: 32rpx 30rpx;
  border-radius: 24rpx;
  background: #fff;
  box-shadow: 0 4rpx 16rpx rgba(16, 24, 40, 0.05);
}
.avatar {
  width: 112rpx;
  height: 112rpx;
  line-height: 112rpx;
  border-radius: 22rpx;
  background: #111827;
  color: #fff;
  text-align: center;
  font-size: 44rpx;
  font-weight: 700;
  flex-shrink: 0;
}
.profile-main {
  flex: 1;
  min-width: 0;
}
.name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.name {
  max-width: 250rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #111827;
  font-size: 34rpx;
  font-weight: 700;
}
.badge {
  max-width: 188rpx;
  height: 38rpx;
  line-height: 38rpx;
  padding: 0 14rpx;
  border-radius: 10rpx;
  background: #e0e7ff;
  color: #3730a3;
  font-size: 20rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sub {
  margin-top: 8rpx;
  color: #6b7280;
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
  line-height: 40rpx;
  padding: 0 14rpx;
  border-radius: 10rpx;
  background: #dcfce7;
  color: #15803d;
  font-size: 20rpx;
}
.muted-tag {
  background: #e5e7eb;
  color: #6b7280;
}
.stats {
  display: flex;
  gap: 18rpx;
  margin-top: 20rpx;
}
.stat {
  flex: 1;
  padding: 24rpx 8rpx;
  border-radius: 18rpx;
  background: #fff;
  text-align: center;
  box-shadow: 0 4rpx 16rpx rgba(16, 24, 40, 0.04);
}
.stat-value {
  color: #111827;
  font-size: 34rpx;
  font-weight: 700;
}
.stat-label {
  margin-top: 8rpx;
  color: #8b93a1;
  font-size: 22rpx;
}
.section {
  margin-top: 22rpx;
  padding: 26rpx 28rpx 8rpx;
  border-radius: 20rpx;
  background: #fff;
  box-shadow: 0 4rpx 16rpx rgba(16, 24, 40, 0.04);
}
.section-title {
  margin-bottom: 8rpx;
  color: #111827;
  font-size: 28rpx;
  font-weight: 650;
}
.menu-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  padding: 24rpx 0;
  border-bottom: 2rpx solid #eef0f3;
}
.menu-item:last-child {
  border-bottom: none;
}
.menu-title {
  color: #111827;
  font-size: 28rpx;
  font-weight: 600;
}
.menu-desc {
  margin-top: 6rpx;
  color: #9ca3af;
  font-size: 22rpx;
}
.arrow {
  color: #c3c8d0;
  font-size: 38rpx;
}
.info-row {
  display: flex;
  justify-content: space-between;
  gap: 24rpx;
  padding: 22rpx 0;
  border-bottom: 2rpx solid #eef0f3;
  color: #6b7280;
  font-size: 25rpx;
}
.info-row:last-child {
  border-bottom: none;
}
.info-row text:last-child {
  flex: 1;
  color: #111827;
  text-align: right;
  overflow-wrap: break-word;
}
.logout {
  height: 82rpx;
  line-height: 82rpx;
  margin: 28rpx 0 0;
  border-radius: 16rpx;
  background: #fff;
  color: #ef4444;
  font-size: 28rpx;
}
</style>
