<script setup>
defineProps({
  steps: {
    type: Array,
    default: () => []
  },
  compact: {
    type: Boolean,
    default: false
  }
})
</script>

<template>
  <view class="growth-path" :class="{ compact }">
    <view
      v-for="(step, index) in steps"
      :key="step.key || step.label || index"
      class="path-item"
      :class="step.status || 'todo'"
    >
      <view class="node">
        <view class="dot">{{ step.mark || index + 1 }}</view>
      </view>
      <text class="label">{{ step.label }}</text>
      <text v-if="step.caption && !compact" class="caption">{{ step.caption }}</text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.growth-path {
  display: flex;
  align-items: flex-start;
  gap: 10rpx;
  width: 100%;
}

.path-item {
  position: relative;
  flex: 1;
  min-width: 0;
  text-align: center;
}

.path-item::before {
  position: absolute;
  top: 23rpx;
  left: -50%;
  width: 100%;
  height: 2rpx;
  background: var(--color-border);
  content: '';
}

.path-item:first-child::before {
  display: none;
}

.path-item.done::before,
.path-item.current::before {
  background: linear-gradient(90deg, var(--color-brand), var(--color-coral));
}

.node {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: center;
}

.dot {
  width: 48rpx;
  height: 48rpx;
  color: var(--color-muted);
  background: #EFF6F9;
  border: 2rpx solid var(--color-border);
  border-radius: 50%;
  font-size: 21rpx;
  font-weight: 700;
  line-height: 46rpx;
  text-align: center;
  box-sizing: border-box;
}

.done .dot {
  color: #fff;
  background: var(--color-brand);
  border-color: var(--color-brand);
}

.current .dot {
  color: #fff;
  background: var(--color-coral);
  border-color: var(--color-coral);
  box-shadow: 0 0 0 8rpx rgba(255, 127, 120, .15);
}

.label {
  display: block;
  margin-top: 12rpx;
  color: var(--color-text);
  font-size: 22rpx;
  font-weight: 650;
  line-height: 1.25;
  white-space: normal;
}

.caption {
  display: block;
  margin-top: 6rpx;
  color: var(--color-muted);
  font-size: 19rpx;
  line-height: 1.35;
}

.compact .dot {
  width: 38rpx;
  height: 38rpx;
  font-size: 18rpx;
  line-height: 36rpx;
}

.compact .path-item::before {
  top: 18rpx;
}

.compact .label {
  font-size: 20rpx;
}
</style>
