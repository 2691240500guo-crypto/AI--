<script setup>
defineProps({
  title: {
    type: String,
    default: ''
  },
  hint: {
    type: String,
    default: ''
  },
  actionText: {
    type: String,
    default: ''
  },
  tone: {
    type: String,
    default: 'default'
  }
})

const emit = defineEmits(['action'])
</script>

<template>
  <view class="ui-state" :class="tone">
    <view class="state-mark">{{ tone === 'error' ? '!' : tone === 'loading' ? '…' : '·' }}</view>
    <text v-if="title" class="state-title">{{ title }}</text>
    <text v-if="hint" class="state-hint">{{ hint }}</text>
    <button v-if="actionText" class="state-action" @click="emit('action')">{{ actionText }}</button>
  </view>
</template>

<style lang="scss" scoped>
.ui-state {
  min-height: 360rpx;
  padding: 96rpx 36rpx;
  color: var(--color-muted);
  text-align: center;
  box-sizing: border-box;
}

.state-mark {
  width: 64rpx;
  height: 64rpx;
  margin: 0 auto 18rpx;
  color: var(--color-brand);
  background: var(--color-brand-soft);
  border-radius: 50%;
  font-size: 34rpx;
  font-weight: 700;
  line-height: 60rpx;
}

.error .state-mark {
  color: var(--color-danger);
  background: #FFF1EF;
}

.state-title,
.state-hint {
  display: block;
}

.state-title {
  color: var(--color-text);
  font-size: 28rpx;
  font-weight: 700;
}

.state-hint {
  margin-top: 10rpx;
  font-size: 23rpx;
  line-height: 1.55;
}

.state-action {
  width: 180rpx;
  height: 64rpx;
  margin-top: 24rpx;
  color: #fff;
  background: var(--color-brand);
  border-radius: var(--radius-sm);
  font-size: 24rpx;
  line-height: 64rpx;
}
</style>
