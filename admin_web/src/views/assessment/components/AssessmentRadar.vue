<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ dimensions: { type: Array, default: () => [] } })
const chartElement = ref(null)
let chart = null
let resizeObserver = null

function renderChart() {
  if (!chartElement.value) return
  if (!chartElement.value.clientWidth || !chartElement.value.clientHeight) return
  if (!chart) chart = echarts.init(chartElement.value)
  const dimensions = (props.dimensions || []).filter((item) => item?.dimension)
  const indicators = dimensions.map((item) => ({
    name: item.dimension,
    max: 100,
  }))
  const values = dimensions.map((item) => Math.round(Number(item.rate || 0) * 100))
  chart.setOption({
    animationDuration: 350,
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const valuesByDimension = new Map(dimensions.map((item) => [item.dimension, item]))
        const lines = dimensions.map((item) => {
          const value = valuesByDimension.get(item.dimension)
          return `${item.dimension}：${Math.round(Number(value?.rate || 0) * 100)}%`
        })
        return `<strong>${params.seriesName || '能力得分率'}</strong><br/>${lines.join('<br/>')}`
      },
    },
    radar: {
      center: ['50%', '52%'],
      radius: '66%',
      shape: 'polygon',
      splitNumber: 5,
      indicator: indicators,
      axisName: { color: '#344054', fontSize: 13, lineHeight: 18 },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
      splitLine: { lineStyle: { color: '#dbe3ef' } },
      splitArea: { areaStyle: { color: ['#fff', '#f8fbff'] } },
    },
    series: [{
      name: '能力得分率',
      type: 'radar',
      symbol: 'circle',
      symbolSize: 7,
      lineStyle: { width: 2, color: '#2563eb' },
      itemStyle: { color: '#2563eb', borderColor: '#fff', borderWidth: 2 },
      areaStyle: { color: '#60a5fa', opacity: 0.28 },
      data: [{ value: values }],
    }],
  })
  chart.resize()
}

function resize() { chart?.resize() }

watch(() => props.dimensions, () => nextTick(renderChart), { deep: true })
onMounted(() => {
  nextTick(renderChart)
  window.addEventListener('resize', resize)
  resizeObserver = new ResizeObserver(resize)
  if (chartElement.value) resizeObserver.observe(chartElement.value)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  resizeObserver?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<template><div v-if="dimensions.length" ref="chartElement" class="radar-chart" /><el-empty v-else description="暂无维度数据" /></template>

<style scoped>
.radar-chart { width: 100%; height: clamp(340px, 34vw, 460px); min-height: 320px; }
</style>
