<template>
  <div class="table-wrapper">
    <div class="table-header">
      <h3>📋 归一化二次场感应电动势明细数据</h3>
    </div>

    <el-table :data="tableData" border height="100%" stripe style="width: 100%">
      <el-table-column prop="time" label="采样时间 t (ms)" width="130" fixed />
      <el-table-column v-for="p in 9" :key="p" :label="`测点 ${p}`" align="center">
        <template #header>
          <div class="col-header">
            <span>测点 {{ p }}</span>
            <el-button type="text" size="mini" @click.stop="expandPoint(p)">放大</el-button>
          </div>
        </template>
        <el-table-column
          :prop="`x_p${p}`"
          label="X分量(μV)"
          width="110"
          :formatter="formatScientific"
        />
        <el-table-column
          :prop="`y_p${p}`"
          label="Y分量(μV)"
          width="110"
          :formatter="formatScientific"
        />
      </el-table-column>
    </el-table>

    <!-- 放大模态视图 -->
    <div v-if="expandedP !== null" class="dt-modal" @click.self="closeExpand">
      <div class="dt-modal-content">
        <div class="dt-modal-header">
          <h4>放大视图 - 测点 {{ expandedP }}</h4>
          <el-button type="text" @click="closeExpand">关闭 ✕</el-button>
        </div>
        <div class="dt-modal-body">
          <div ref="chartDom" class="dt-chart-container"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  tableData: any[]
}>()

// 当前放大的测点索引（1-9），null 表示未放大
const expandedP = ref<number | null>(null)

const expandPoint = (p: number) => {
  expandedP.value = p
}

const closeExpand = () => {
  expandedP.value = null
  // chart 会在 watch 中被销毁
}

const onKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && expandedP.value !== null) {
    expandedP.value = null
  }
}

onMounted(() => window.addEventListener('keydown', onKeyDown))
onUnmounted(() => window.removeEventListener('keydown', onKeyDown))

// ECharts for expanded point
const chartDom = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const disposeChart = () => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
}

const renderPointChart = async (p: number) => {
  await nextTick()
  disposeChart()
  if (!chartDom.value) return
  const data = props.tableData || []
  const times = data.map((r: any) => Number(r.time))
  const xSeries = data.map((r: any) => Number(r[`x_p${p}`]))
  const ySeries = data.map((r: any) => Number(r[`y_p${p}`]))

  chartInstance = echarts.init(chartDom.value)

  const option: echarts.EChartsOption = {
    title: { text: `测点 ${p}` },
    tooltip: { trigger: 'axis' },
    legend: { right: 10 },
    grid: { left: '10%', right: '10%', bottom: '12%' },
    xAxis: { type: 'value', name: 't(ms)' },
    yAxis: {
      type: 'log',
      name: 'V(μV)',
      axisLabel: {
        formatter: (value: number) => {
          if (!value) return '0'
          try {
            return (value as number).toExponential(2)
          } catch (e) {
            return String(value)
          }
        }
      }
    },
    series: [
      {
        name: 'X分量',
        type: 'line',
        data: times.map((t, i) => [t, xSeries[i]]),
        showSymbol: false
      },
      { name: 'Y分量', type: 'line', data: times.map((t, i) => [t, ySeries[i]]), showSymbol: false }
    ]
  }

  chartInstance.setOption(option)
  chartInstance.resize()
}

watch(
  () => expandedP.value,
  (p) => {
    if (p === null) {
      disposeChart()
    } else {
      renderPointChart(p)
    }
  }
)

// 窗口大小时调整图表
window.addEventListener('resize', () => chartInstance?.resize())

const formatScientific = (row: any, column: any, cellValue: number) => {
  if (cellValue === 0 || !cellValue) return '0.0000e+0'
  return cellValue.toExponential(4)
}
</script>

<style scoped>
.table-wrapper {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 10px;
}
.table-header {
  margin-bottom: 10px;
  color: #303133;
}
.table-header h3 {
  margin: 0;
  font-size: 16px;
  border-left: 4px solid #67c23a;
  padding-left: 8px;
}

.header-actions {
  margin-left: auto;
}

.col-header {
  display: flex;
  align-items: center;
  gap: 6px;
  justify-content: center;
}

/* 模态放大样式 */
.dt-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}
.dt-modal-content {
  width: 95%;
  height: 90%;
  background: #fff;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.dt-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid #ebeef5;
}
.dt-modal-body {
  padding: 12px;
  flex: 1 1 auto;
  overflow: auto;
}

.dt-chart-container {
  width: 100%;
  height: 100%;
  min-height: 320px;
}
</style>
