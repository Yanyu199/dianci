<template>
  <div class="nine-grid-wrapper">
    <div v-for="idx in 9" :key="idx" class="grid-chart-item">
      <div :ref="(el) => (chartRefs[idx - 1] = el as HTMLElement)" class="chart-dom-instance"></div>
      <el-button
        class="chart-zoom-btn"
        circle
        size="small"
        type="primary"
        :icon="ZoomIn"
        @click.stop="openPreview(idx - 1)"
      />
    </div>
  </div>

  <div v-if="activeIndex !== null" class="chart-preview-mask" @click.self="closePreview">
    <div class="chart-preview-panel">
      <div class="chart-preview-header">
        <div class="chart-preview-title">测点 {{ activeIndex + 1 }}</div>
        <div class="chart-preview-actions">
          <el-button size="small" @click="zoomOut">缩小</el-button>
          <el-button size="small" @click="resetZoom">重置</el-button>
          <el-button size="small" type="primary" @click="zoomIn">放大</el-button>
          <el-button size="small" type="danger" plain @click="closePreview">关闭</el-button>
        </div>
      </div>

      <div class="chart-preview-body">
        <div class="chart-preview-viewport" :style="previewViewportStyle">
          <div ref="previewChartRef" class="chart-preview-dom"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ZoomIn } from '@element-plus/icons-vue'
import { computed, nextTick, onMounted, onUnmounted, markRaw, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  chartData: any
}>()

const chartRefs = ref<Array<HTMLElement | null>>([])
const previewChartRef = ref<HTMLElement | null>(null)
const activeIndex = ref<number | null>(null)
const zoomScale = ref(1)

let chartInstances: echarts.ECharts[] = []
let previewChartInstance: echarts.ECharts | null = null

const waitForNextFrame = () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))

const previewViewportStyle = computed(() => ({
  width: `${zoomScale.value * 100}%`,
  height: `${zoomScale.value * 100}%`
}))

const getSeriesData = (index: number) => {
  const data = props.chartData
  if (!data) return null

  const time = data.time ?? []
  const xSeries = data.x_series?.[index] ?? []
  const ySeries = data.y_series?.[index] ?? []

  return { time, xSeries, ySeries }
}

const buildChartOption = (index: number): echarts.EChartsOption | null => {
  const seriesData = getSeriesData(index)
  if (!seriesData) return null

  const { time, xSeries, ySeries } = seriesData

  return {
    title: { text: `测点: ${index + 1}`, left: 'left', top: 5, textStyle: { fontSize: 12 } },
    tooltip: { trigger: 'axis' },
    legend: { right: 5, top: 5, itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 10 } },
    grid: { left: '16%', right: '5%', bottom: '15%', top: '25%' },
    xAxis: { type: 'log', name: 't(ms)', axisLabel: { fontSize: 9 } },
    yAxis: {
      type: 'log',
      name: 'V(μV)',
      axisLabel: {
        fontSize: 9,
        formatter: (value: number) => {
          if (!value) return '0'
          return value.toExponential(2)
        }
      },
      splitLine: { show: true, lineStyle: { type: 'dashed' } }
    },
    series: [
      {
        name: 'X分量',
        type: 'line',
        data: xSeries.map((v: number, idx: number) => [time[idx], v]),
        symbol: 'none',
        lineStyle: { width: 1.5, color: '#409EFF' }
      },
      {
        name: 'Y分量',
        type: 'line',
        data: ySeries.map((v: number, idx: number) => [time[idx], v]),
        symbol: 'none',
        lineStyle: { width: 1.5, type: 'dashed', color: '#F56C6C' }
      }
    ]
  }
}

const renderCharts = () => {
  if (!props.chartData) return

  chartInstances.forEach((chart) => chart.dispose())
  chartInstances = []

  for (let i = 0; i < 9; i++) {
    const dom = chartRefs.value[i]
    if (!dom || dom.clientWidth === 0 || dom.clientHeight === 0) continue

    const chart = markRaw(echarts.init(dom))
    chartInstances.push(chart)

    const option = buildChartOption(i)
    if (option) chart.setOption(option)
  }
}

const disposePreviewChart = () => {
  if (previewChartInstance) {
    previewChartInstance.dispose()
    previewChartInstance = null
  }
}

const renderPreviewChart = async () => {
  await nextTick()
  await waitForNextFrame()
  disposePreviewChart()

  const index = activeIndex.value
  if (index === null || !previewChartRef.value) return
  if (previewChartRef.value.clientWidth === 0 || previewChartRef.value.clientHeight === 0) return

  const option = buildChartOption(index)
  if (!option) return

  previewChartInstance = markRaw(echarts.init(previewChartRef.value))
  previewChartInstance.setOption(option)
  previewChartInstance.resize()
}

const openPreview = (index: number) => {
  activeIndex.value = index
  zoomScale.value = 1
}

const closePreview = () => {
  activeIndex.value = null
  zoomScale.value = 1
  disposePreviewChart()
}

const zoomIn = () => {
  zoomScale.value = Math.min(2.5, Number((zoomScale.value + 0.2).toFixed(1)))
  nextTick(() => previewChartInstance?.resize())
}

const zoomOut = () => {
  zoomScale.value = Math.max(0.6, Number((zoomScale.value - 0.2).toFixed(1)))
  nextTick(() => previewChartInstance?.resize())
}

const resetZoom = () => {
  zoomScale.value = 1
  nextTick(() => previewChartInstance?.resize())
}

watch(
  () => props.chartData,
  async () => {
    await nextTick()
    await waitForNextFrame()
    renderCharts()
    if (activeIndex.value !== null) {
      renderPreviewChart()
    }
  },
  { immediate: true }
)

watch(
  () => activeIndex.value,
  (index) => {
    if (index === null) {
      disposePreviewChart()
      return
    }
    renderPreviewChart()
  }
)

const handleResize = () => {
  chartInstances.forEach((chart) => chart.resize())
  if (previewChartInstance && previewChartRef.value?.clientWidth && previewChartRef.value?.clientHeight) {
    previewChartInstance.resize()
  }
}

onMounted(() => window.addEventListener('resize', handleResize))

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstances.forEach((chart) => chart.dispose())
  disposePreviewChart()
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
  position: relative;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
  overflow: hidden;
}

.chart-dom-instance {
  width: 100%;
  height: 100%;
}

.chart-zoom-btn {
  position: absolute;
  right: 8px;
  top: 8px;
  z-index: 2;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

.chart-preview-mask {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.chart-preview-panel {
  width: min(96vw, 1400px);
  height: min(92vh, 920px);
  background: #fff;
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
}

.chart-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
}

.chart-preview-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.chart-preview-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.chart-preview-body {
  flex: 1;
  overflow: auto;
  background: #f5f7fa;
  padding: 16px;
}

.chart-preview-viewport {
  min-width: 100%;
  min-height: 100%;
  background: #fff;
  border-radius: 8px;
  transition: width 0.2s ease, height 0.2s ease;
}

.chart-preview-dom {
  width: 100%;
  height: 100%;
  min-height: 700px;
}
</style>
