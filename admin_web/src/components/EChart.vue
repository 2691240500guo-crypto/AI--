<template>
  <v-chart :option="option" autoresize :style="{ height }" />
</template>

<script setup>
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart, RadarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, BarChart, LineChart, PieChart, RadarChart,
     GridComponent, TooltipComponent, LegendComponent, TitleComponent])

defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '320px' }
})
</script>
