<script setup>
import { computed, onMounted, ref } from 'vue'
import { onPullDownRefresh } from '@dcloudio/uni-app'
import { getMyTalentProfile } from '@/api'
import GrowthPath from '@/components/GrowthPath.vue'
import UiState from '@/components/UiState.vue'

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
const growthSteps = computed(() => [
  { label: '档案', mark: '档', status: profile.value ? 'done' : 'current', caption: '基础画像' },
  { label: '技能', mark: '技', status: tags.value.length ? 'current' : 'todo', caption: `${tags.value.length} 个标签` },
  { label: '经历', mark: '历', status: works.value.length || projects.value.length ? 'done' : 'todo', caption: '成长台账' },
  { label: '认证', mark: '证', status: certificates.value.length ? 'current' : 'todo', caption: '资质记录' }
])

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
  <view class="app-page profile-page">
    <UiState v-if="loading" tone="loading" title="正在加载档案" hint="正在同步你的数字人才画像。" />

    <UiState
      v-else-if="failed"
      tone="error"
      title="档案加载失败"
      hint="请检查网络或稍后重试。"
      action-text="重试"
      @action="load"
    />

    <template v-else-if="profile">
      <view class="header surface">
        <view class="avatar">{{ String(profile.name || '用').slice(0, 1) }}</view>
        <view class="title-block">
          <text class="eyebrow">我的数字人才画像</text>
          <view class="name">{{ profile.name }}</view>
          <view class="sub">{{ profile.current_title || profile.level || '个人档案' }}</view>
        </view>
      </view>

      <view class="growth-panel surface">
        <view class="section-title">成长台账</view>
        <GrowthPath :steps="growthSteps" compact />
      </view>

      <view class="section surface">
        <view class="section-title">基础信息</view>
        <view v-for="row in baseRows" :key="row.label" class="info-row">
          <text>{{ row.label }}</text>
          <text>{{ row.value || '-' }}</text>
        </view>
      </view>

      <view class="section surface">
        <view class="section-title">画像标签</view>
        <view v-if="tags.length" class="tags">
          <text v-for="tag in tags" :key="tag.id || tag.name" class="tag">{{ tag.name }}</text>
        </view>
        <view v-else class="empty-line">暂无标签</view>
      </view>

      <view class="section surface">
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

      <view class="section surface">
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

      <view class="section surface">
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

      <view class="section surface">
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

    <UiState v-else title="当前账号未关联人才档案" hint="关联后可查看完整数字人才画像。" />
  </view>
</template>

<style lang="scss" scoped>
.profile-page {
  padding-bottom: 72rpx;
}

.header {
  display: flex;
  align-items: center;
  gap: 24rpx;
  padding: 30rpx;
}

.avatar {
  width: 104rpx;
  height: 104rpx;
  flex-shrink: 0;
  color: #fff;
  background: linear-gradient(135deg, var(--color-brand), var(--color-sky));
  border-radius: 26rpx;
  font-size: 42rpx;
  font-weight: 800;
  line-height: 104rpx;
  text-align: center;
}

.title-block {
  min-width: 0;
  flex: 1;
}

.eyebrow,
.sub {
  display: block;
}

.eyebrow {
  color: var(--color-coral);
  font-size: 22rpx;
  font-weight: 800;
}

.name {
  margin-top: 8rpx;
  overflow: hidden;
  color: var(--color-text);
  font-size: 36rpx;
  font-weight: 800;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sub {
  margin-top: 8rpx;
  color: var(--color-muted);
  font-size: 24rpx;
}

.growth-panel,
.section {
  margin-top: 20rpx;
  padding: 26rpx 28rpx;
}

.section-title {
  margin-bottom: 18rpx;
}

.info-row {
  display: flex;
  justify-content: space-between;
  gap: 30rpx;
  padding: 18rpx 0;
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

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.tag {
  min-height: 42rpx;
  padding: 0 16rpx;
  color: var(--color-brand);
  background: var(--color-brand-soft);
  border-radius: var(--radius-sm);
  font-size: 21rpx;
  line-height: 42rpx;
}

.text-block {
  padding: 16rpx 0;
  border-bottom: 1rpx solid var(--color-border);
}

.text-block:last-child {
  border-bottom: none;
}

.text-label {
  color: var(--color-muted);
  font-size: 23rpx;
}

.text-content {
  margin-top: 8rpx;
  color: var(--color-text);
  font-size: 26rpx;
  line-height: 1.65;
  white-space: pre-wrap;
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.timeline-item {
  position: relative;
  padding: 20rpx 20rpx 20rpx 30rpx;
  background: #F8FCFD;
  border: 1rpx solid var(--color-border);
  border-radius: var(--radius-md);
}

.timeline-item::before {
  position: absolute;
  top: 24rpx;
  left: 14rpx;
  width: 8rpx;
  height: 8rpx;
  background: var(--color-coral);
  border-radius: 50%;
  content: '';
}

.timeline-title {
  color: var(--color-text);
  font-size: 27rpx;
  font-weight: 700;
}

.timeline-sub {
  margin-top: 6rpx;
  color: var(--color-muted);
  font-size: 23rpx;
  line-height: 1.5;
}

.timeline-desc {
  margin-top: 8rpx;
  color: var(--color-text);
  font-size: 24rpx;
  line-height: 1.55;
}

.empty-line {
  padding: 24rpx 0 6rpx;
  color: var(--color-muted);
  font-size: 24rpx;
}
</style>
