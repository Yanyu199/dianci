<template>
  <div class="nine-grid-wrapper">
    <div v-for="idx in 9" :key="idx" class="grid-chart-item">
      <div :ref="(el) => (chartRefs[idx - 1] = el as HTMLElement)" class="chart-dom-instance"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick, markRaw } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  chartData: any
}>()

const chartRefs = ref<HTMLElement[]>([])
let chartInstances: echarts.ECharts[] = []

const renderCharts = () => {
  if (!props.chartData) return
  const data = props.chartData

  // 销毁旧实例
  chartInstances.forEach((chart) => chart.dispose())
  chartInstances = []

  for (let i = 0; i < 9; i++) {
    const dom = chartRefs.value[i]
    if (!dom) continue

    const chart = markRaw(echarts.init(dom))
    chartInstances.push(chart)

    const option = {
      title: { text: `测点: ${i + 1}`, left: 'left', top: 5, textStyle: { fontSize: 12 } },
      tooltip: { trigger: 'axis' },
      legend: { right: 5, top: 5, itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 10 } },
      grid: { left: '16%', right: '5%', bottom: '15%', top: '25%' },
      xAxis: { type: 'log', name: 't(ms)', axisLabel: { fontSize: 9 } },
      yAxis: {
        type: 'log', // 【非常重要：必须保持为 log，千万别改成 value】
        name: 'V(μV)',
        axisLabel: {
          fontSize: 9,
          // 在保留 log 轴的基础上，加上科学计数法格式化
          formatter: function (value: number) {
            if (!value) return '0'
            return value.toExponential(2) // 保留两位小数的科学计数法，如 1.23e-5
          }
        },
        splitLine: { show: true, lineStyle: { type: 'dashed' } }
      },
      series: [
        {
          name: 'X分量',
          type: 'line',
          data: data.x_series[i].map((v: number, idx: number) => [data.time[idx], v]),
          symbol: 'none',
          lineStyle: { width: 1.5, color: '#409EFF' }
        },
        {
          name: 'Y分量',
          type: 'line',
          data: data.y_series[i].map((v: number, idx: number) => [data.time[idx], v]),
          symbol: 'none',
          lineStyle: { width: 1.5, type: 'dashed', color: '#F56C6C' }
        }
      ]
    }
    chart.setOption(option)
  }
}

watch(
  () => props.chartData,
  async () => {
    await nextTick()
    renderCharts()
  },
  { immediate: true }
)

// 窗口大小适配
const handleResize = () => chartInstances.forEach((c) => c.resize())
onMounted(() => window.addEventListener('resize', handleResize))
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstances.forEach((chart) => chart.dispose())
})
</script>

<style scoped>
.nine-grid-wrapper {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: repeat(3, 1fr);
  gap: 10px;
  height: 100%;
  padding: 10px;
  background-color: #f5f7fa;
}

.grid-chart-item {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}

.chart-dom-instance {
  width: 100%;
  height: 100%;
}
</style>
