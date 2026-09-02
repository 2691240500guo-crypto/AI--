<script setup>
import { computed, onMounted, ref } from 'vue'
import { onPullDownRefresh } from '@dcloudio/uni-app'
import { getMyTalentProfile } from '@/api'

const loading = ref(false)
const failed = ref(false)
const profile = ref(null)

const baseRows = computed(() => {
  const item = profile.value || {}
  return [
    { label: '姓名', value: item.name },
    { label: '性别', value: item.gender },
    { label: '手机号', value: item.phone_masked || item.phone },
    { label: '邮箱', value: item.email },
    { label: '最高学历', value: item.highest_education || item.degree },
    { label: '毕业院校', value: item.school },
    { label: '专业', value: item.major },
    { label: '当前职位', value: item.current_title },
    { label: '能力等级', value: item.level },
    { label: '从业年限', value: Number(item.years_experience || 0) ? `${item.years_experience} 年` : '' }
  ]
})

const tags = computed(() => profile.value?.tags || [])
const educations = computed(() => profile.value?.educations || [])
const works = computed(() => profile.value?.works || [])
const projects = computed(() => profile.value?.projects || [])
const certificates = computed(() => profile.value?.certificates || [])

onMounted(load)
onPullDownRefresh(async () => {
  await load()
  uni.stopPullDownRefresh()
})

async function load() {
  loading.value = true
  failed.value = false
  try {
    const res = await getMyTalentProfile()
    profile.value = res.data || null
  } catch (error) {
    failed.value = true
    profile.value = null
  } finally {
    loading.value = false
  }
}

function formatYear(start, end) {
  if (!start && !end) return ''
  return `${start || '-'} - ${end || '至今'}`
}
</script>

<template>
  <view class="wrap">
    <view v-if="loading" class="state">加载中...</view>

    <view v-else-if="failed" class="state failed">
      <text>档案加载失败</text>
      <button class="retry" @click="load">重试</button>
    </view>

    <template v-else-if="profile">
      <view class="header">
        <view class="avatar">{{ String(profile.name || '用').slice(0, 1) }}</view>
        <view class="title-block">
          <view class="name">{{ profile.name }}</view>
          <view class="sub">{{ profile.current_title || profile.level || '个人档案' }}</view>
        </view>
      </view>

      <view class="section">
        <view class="section-title">基础信息</view>
        <view v-for="row in baseRows" :key="row.label" class="info-row">
          <text>{{ row.label }}</text>
          <text>{{ row.value || '-' }}</text>
        </view>
      </view>

      <view class="section">
        <view class="section-title">画像标签</view>
        <view v-if="tags.length" class="tags">
          <text v-for="tag in tags" :key="tag.id || tag.name" class="tag">{{ tag.name }}</text>
        </view>
        <view v-else class="empty-line">暂无标签</view>
      </view>

      <view class="section">
        <view class="section-title">技能与经历</view>
        <view class="text-block">
          <view class="text-label">核心技能</view>
          <view class="text-content">{{ profile.skills || '-' }}</view>
        </view>
        <view class="text-block">
          <view class="text-label">工作经历</view>
          <view class="text-content">{{ profile.work_experience || '-' }}</view>
        </view>
        <view class="text-block">
          <view class="text-label">项目经验</view>
          <view class="text-content">{{ profile.project_experience || '-' }}</view>
        </view>
        <view class="text-block">
          <view class="text-label">荣誉资质</view>
          <view class="text-content">{{ profile.honors || '-' }}</view>
        </view>
      </view>

      <view class="section">
        <view class="section-title">教育经历</view>
        <view v-if="educations.length" class="timeline">
          <view v-for="edu in educations" :key="edu.id" class="timeline-item">
            <view class="timeline-title">{{ edu.school || '-' }}</view>
            <view class="timeline-sub">
              {{ edu.degree || '-' }} · {{ edu.major || '-' }} · {{ formatYear(edu.start_year, edu.end_year) }}
            </view>
          </view>
        </view>
        <view v-else class="empty-line">暂无教育经历</view>
      </view>

      <view class="section">
        <view class="section-title">工作与项目</view>
        <view v-if="works.length || projects.length" class="timeline">
          <view v-for="work in works" :key="'work-' + work.id" class="timeline-item">
            <view class="timeline-title">{{ work.company || '-' }}</view>
            <view class="timeline-sub">{{ work.title || '-' }}</view>
            <view class="timeline-desc">{{ work.description || '' }}</view>
          </view>
          <view v-for="project in projects" :key="'project-' + project.id" class="timeline-item">
            <view class="timeline-title">{{ project.name || '-' }}</view>
            <view class="timeline-sub">{{ project.role || '项目经历' }}</view>
            <view class="timeline-desc">{{ project.description || '' }}</view>
          </view>
        </view>
        <view v-else class="empty-line">暂无工作或项目经历</view>
      </view>

      <view class="section">
        <view class="section-title">技能证书</view>
        <view v-if="certificates.length" class="timeline">
          <view v-for="cert in certificates" :key="cert.id" class="timeline-item">
            <view class="timeline-title">{{ cert.name || '-' }}</view>
            <view class="timeline-sub">{{ cert.issuer || '-' }} · {{ cert.level || '-' }}</view>
            <view class="timeline-desc">{{ cert.description || '' }}</view>
          </view>
        </view>
        <view v-else class="empty-line">暂无证书</view>
      </view>
    </template>

    <view v-else class="state">当前账号未关联人才档案</view>
  </view>
</template>

<style lang="scss" scoped>
.wrap {
  min-height: 100vh;
  padding: 24rpx 24rpx 48rpx;
  background: #f6f7f9;
  box-sizing: border-box;
}
.header {
  display: flex;
  align-items: center;
  gap: 24rpx;
  padding: 30rpx;
  border-radius: 24rpx;
  background: #111827;
  color: #fff;
}
.avatar {
  width: 104rpx;
  height: 104rpx;
  line-height: 104rpx;
  border-radius: 22rpx;
  background: rgba(255, 255, 255, 0.14);
  text-align: center;
  font-size: 42rpx;
  font-weight: 700;
  flex-shrink: 0;
}
.title-block {
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 36rpx;
  font-weight: 700;
  line-height: 1.35;
}
.sub {
  margin-top: 8rpx;
  color: rgba(255, 255, 255, 0.72);
  font-size: 24rpx;
}
.section {
  margin-top: 22rpx;
  padding: 26rpx 28rpx;
  border-radius: 20rpx;
  background: #fff;
  box-shadow: 0 4rpx 16rpx rgba(16, 24, 40, 0.04);
}
.section-title {
  margin-bottom: 16rpx;
  color: #111827;
  font-size: 28rpx;
  font-weight: 650;
}
.info-row {
  display: flex;
  justify-content: space-between;
  gap: 30rpx;
  padding: 18rpx 0;
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
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}
.tag {
  height: 42rpx;
  line-height: 42rpx;
  padding: 0 16rpx;
  border-radius: 10rpx;
  background: #e0e7ff;
  color: #3730a3;
  font-size: 21rpx;
}
.text-block {
  padding: 16rpx 0;
  border-bottom: 2rpx solid #eef0f3;
}
.text-block:last-child {
  border-bottom: none;
}
.text-label {
  color: #6b7280;
  font-size: 23rpx;
}
.text-content {
  margin-top: 8rpx;
  color: #111827;
  font-size: 26rpx;
  line-height: 1.65;
  white-space: pre-wrap;
}
.timeline {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}
.timeline-item {
  padding: 20rpx;
  border-radius: 16rpx;
  background: #f8fafc;
}
.timeline-title {
  color: #111827;
  font-size: 27rpx;
  font-weight: 650;
}
.timeline-sub {
  margin-top: 6rpx;
  color: #6b7280;
  font-size: 23rpx;
  line-height: 1.5;
}
.timeline-desc {
  margin-top: 8rpx;
  color: #374151;
  font-size: 24rpx;
  line-height: 1.55;
}
.empty-line {
  padding: 24rpx 0 6rpx;
  color: #9ca3af;
  font-size: 24rpx;
}
.state {
  min-height: 520rpx;
  padding-top: 160rpx;
  color: #9ca3af;
  text-align: center;
  font-size: 26rpx;
  box-sizing: border-box;
}
.failed {
  color: #ef4444;
}
.retry {
  width: 168rpx;
  height: 64rpx;
  line-height: 64rpx;
  margin-top: 22rpx;
  border-radius: 12rpx;
  background: #111827;
  color: #fff;
  font-size: 24rpx;
}
</style>
