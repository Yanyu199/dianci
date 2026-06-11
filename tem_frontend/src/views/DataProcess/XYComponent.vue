<template>
  <div class="xy-container">
    <el-row :gutter="20" style="height: 100%">
      <el-col :span="6" class="sidebar-scroll">
        <el-card class="control-card" shadow="never">
          <template #header>
            <div class="card-header-axis">
              <span class="axis-title x-color">● X 水平分量</span>
            </div>
          </template>

          <div class="file-action-area">
            <el-button type="primary" plain class="upload-btn-dash" @click="$refs.xInput.click()">
              <span v-if="!fileX">📁 1. 导入 X 轴数据文件</span>
              <span v-else>✅ 已导入: {{ fileX.name }}</span>
            </el-button>
            <input
              type="file"
              ref="xInput"
              style="display: none"
              @change="handleFileChange($event, 'X')"
              accept=".txt,.dat,.csv"
            />
          </div>

          <div v-if="fileX" class="param-summary">
            <div class="summary-title">
              <span>当前工程参数</span>
              <el-button type="primary" plain size="small" @click="openDialog('X')"
                >⚙️ 设置参数</el-button
              >
            </div>
            <el-descriptions :column="2" size="small" border>
              <el-descriptions-item label="边长">{{ formX.txEdge }}m</el-descriptions-item>
              <el-descriptions-item label="匝数">{{ formX.turns }}</el-descriptions-item>
              <el-descriptions-item label="测道">{{ formX.channels }}</el-descriptions-item>
              <el-descriptions-item label="面积">{{ formX.rxArea }}㎡</el-descriptions-item>
              <el-descriptions-item label="介质" :span="2">{{ formX.medium }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </el-card>

        <el-card class="control-card" shadow="never" style="margin-top: 15px">
          <template #header>
            <div class="card-header-axis">
              <span class="axis-title y-color">● Y 水平分量</span>
            </div>
          </template>

          <div class="file-action-area">
            <el-button type="danger" plain class="upload-btn-dash" @click="$refs.yInput.click()">
              <span v-if="!fileY">📁 2. 导入 Y 轴数据文件</span>
              <span v-else>✅ 已导入: {{ fileY.name }}</span>
            </el-button>
            <input
              type="file"
              ref="yInput"
              style="display: none"
              @change="handleFileChange($event, 'Y')"
              accept=".txt,.dat,.csv"
            />
          </div>

          <div v-if="fileY" class="param-summary">
            <div class="summary-title">
              <span>当前工程参数</span>
              <el-button type="danger" plain size="small" @click="openDialog('Y')"
                >⚙️ 设置参数</el-button
              >
            </div>
            <el-descriptions :column="2" size="small" border>
              <el-descriptions-item label="边长">{{ formY.txEdge }}m</el-descriptions-item>
              <el-descriptions-item label="匝数">{{ formY.turns }}</el-descriptions-item>
              <el-descriptions-item label="测道">{{ formY.channels }}</el-descriptions-item>
              <el-descriptions-item label="面积">{{ formY.rxArea }}㎡</el-descriptions-item>
              <el-descriptions-item label="介质" :span="2">{{ formY.medium }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </el-card>

        <el-button
          type="success"
          size="large"
          class="main-execute-btn"
          @click="submitData"
          :loading="loading"
          :disabled="!fileX || !fileY"
        >
          🚀 融合双分量解析并渲染
        </el-button>
      </el-col>

      <el-col
        :span="18"
        class="main-display-area"
        v-loading="loading"
        element-loading-text="物理矩阵分析中..."
      >
        <el-card class="display-card-graph" shadow="never">
          <div v-if="!hasData" class="unloaded-status">
            <el-empty description="请在左侧分别载入 X / Y 数据文件，并确认工程参量" />
          </div>
          <div v-else class="nine-grid-layout">
            <div v-for="idx in 9" :key="idx" class="grid-chart-item">
              <div :ref="(el) => (chartRefs[idx - 1] = el)" class="chart-dom-instance"></div>
            </div>
          </div>
        </el-card>

        <div class="display-collapsible-table" v-if="hasData">
          <el-collapse v-model="activeCollapsePanels">
            <el-collapse-item name="tableDetail">
              <template #title>
                <div class="table-collapse-title">
                  <span>📊 归一化二次场感应电动势明细数据表 (点击展开/收起)</span>
                </div>
              </template>
              <el-table
                :data="computedTableData"
                border
                max-height="350"
                size="small"
                style="width: 100%"
              >
                <el-table-column prop="time" label="采样时间 t (ms)" width="120" fixed />
                <el-table-column v-for="p in 9" :key="p" :label="`测点 ${p}`">
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
            </el-collapse-item>
          </el-collapse>
        </div>
      </el-col>
    </el-row>

    <el-dialog
      v-model="dialogVisible"
      :title="currentEditing === 'X' ? '⚙️ 请输入工程参数 (X分量)' : '⚙️ 请输入工程参数 (Y分量)'"
      width="450px"
      :close-on-click-modal="false"
      :append-to-body="true"
      destroy-on-close
    >
      <el-form :model="tempForm" label-width="120px" size="default">
        <el-form-item label="数据类型:">
          <el-select v-model="tempForm.dataType" style="width: 100%">
            <el-option label="瞬变电磁晚期道数据" value="late" />
            <el-option label="瞬变电磁全期道数据" value="full" />
          </el-select>
        </el-form-item>
        <el-form-item label="发射边长(m):">
          <el-input-number
            v-model="tempForm.txEdge"
            :min="1"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="线圈匝数:">
          <el-input-number
            v-model="tempForm.turns"
            :min="1"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="测道数目:">
          <el-input-number
            v-model="tempForm.channels"
            :min="1"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="接收面积(㎡):">
          <el-input-number
            v-model="tempForm.rxArea"
            :min="1"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="线号:">
          <el-input v-model="tempForm.lineNumber" />
        </el-form-item>
        <el-form-item label="工作点介质:">
          <el-input v-model="tempForm.medium" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取 消</el-button>
          <el-button type="primary" @click="saveParams">确 定</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, nextTick, markRaw } from 'vue'
import { ElMessage, vLoading } from 'element-plus'
import * as echarts from 'echarts'
import { uploadXYData } from '@/api/dataProcess'

const defaultParams = {
  dataType: 'late',
  txEdge: 2,
  turns: 1,
  channels: 40,
  rxArea: 100,
  lineNumber: 'L01',
  medium: '煤层'
}

const formX = reactive({ ...defaultParams, lineNumber: 'L01_X' })
const formY = reactive({ ...defaultParams, lineNumber: 'L01_Y' })

const fileX = ref<File | null>(null)
const fileY = ref<File | null>(null)
const loading = ref(false)
const hasData = ref(false)

// 弹窗控制逻辑
const dialogVisible = ref(false)
const currentEditing = ref<'X' | 'Y'>('X')
const tempForm = reactive({ ...defaultParams })

const activeCollapsePanels = ref([])
const chartRefs = ref<(HTMLElement | null)[]>([])
let chartInstances: echarts.ECharts[] = []
const computedTableData = ref([])

const handleResize = () => {
  chartInstances.forEach((chart) => chart.resize())
}
onMounted(() => {
  window.addEventListener('resize', handleResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstances.forEach((chart) => chart.dispose())
})

const handleFileChange = (e: Event, type: 'X' | 'Y') => {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    if (type === 'X') {
      fileX.value = target.files[0]
      openDialog('X')
    } else {
      fileY.value = target.files[0]
      openDialog('Y')
    }
    // 核心修复：清空 file input 的值，确保下次选同一个文件依然能触发 onChange
    target.value = ''
  }
}

const openDialog = (type: 'X' | 'Y') => {
  currentEditing.value = type
  const sourceForm = type === 'X' ? formX : formY
  Object.assign(tempForm, sourceForm)
  dialogVisible.value = true
}

const saveParams = () => {
  if (currentEditing.value === 'X') {
    Object.assign(formX, tempForm)
  } else {
    Object.assign(formY, tempForm)
  }
  dialogVisible.value = false
  ElMessage.success(`已保存 ${currentEditing.value} 分量参数配置`)
}

const formatScientific = (row: any, column: any, cellValue: number) => {
  if (cellValue === 0 || !cellValue) return '0.0'
  return cellValue.toExponential(4)
}

const submitData = async () => {
  if (!fileX.value || !fileY.value) {
    ElMessage.warning('请确保 X 轴与 Y 轴的数据文件均已选择！')
    return
  }
  loading.value = true
  try {
    const formData = new FormData()
    formData.append('fileX', fileX.value)
    formData.append('fileY', fileY.value)
    formData.append('paramsX', JSON.stringify(formX))
    formData.append('paramsY', JSON.stringify(formY))

    const res = await uploadXYData(formData)

    computedTableData.value = res.data.table_data
    hasData.value = true

    await nextTick()
    renderNineGridCharts(res.data)
    ElMessage.success('双分量解析并渲染成功！')
  } catch (error) {
    console.error(error)
    ElMessage.error('计算模块异常，请检查后端服务日志。')
  } finally {
    loading.value = false
  }
}

const renderNineGridCharts = (data: any) => {
  chartInstances.forEach((chart) => chart.dispose())
  chartInstances = []

  for (let i = 0; i < 9; i++) {
    const dom = chartRefs.value[i]
    if (!dom) continue

    const chart = markRaw(echarts.init(dom))
    chartInstances.push(chart)

    const option = {
      title: {
        text: `测点 点号: ${i + 1}.00`,
        left: 'left',
        top: 2,
        textStyle: { fontSize: 12, color: '#444', fontWeight: 'bold' }
      },
      tooltip: { trigger: 'axis', axisPointer: { type: 'line' } },
      legend: { right: 5, top: 2, itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 10 } },
      grid: { left: '16%', right: '5%', bottom: '18%', top: '22%' },
      xAxis: {
        type: 'log',
        name: 't(ms)',
        nameLocation: 'end',
        nameGap: -2,
        axisLabel: { fontSize: 9 },
        splitLine: { show: false }
      },
      yAxis: {
        type: 'log',
        name: 'V(μV)',
        axisLabel: { fontSize: 9 },
        splitLine: { show: true, lineStyle: { type: 'dashed', color: '#f0f0f0' } }
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
</script>

<style scoped>
.xy-container {
  height: calc(100vh - 100px);
}

.sidebar-scroll {
  height: 100%;
  overflow-y: auto;
  padding-right: 5px;
}

.control-card {
  border-radius: 6px;
  border: 1px solid #e4e7ed;
}

.card-header-axis {
  font-weight: bold;
}
.x-color {
  color: #409eff;
}
.y-color {
  color: #f56c6c;
}

.file-action-area {
  margin-bottom: 15px;
}

.upload-btn-dash {
  width: 100%;
  justify-content: flex-start;
  border-style: dashed;
}

.param-summary {
  background: #f8f9fa;
  padding: 10px;
  border-radius: 4px;
  border: 1px solid #ebeef5;
}

.summary-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: bold;
  color: #606266;
}

.main-execute-btn {
  width: 100%;
  margin-top: 15px;
  font-weight: bold;
}

.main-display-area {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 15px;
}

.display-card-graph {
  flex: 1;
  border-radius: 6px;
  min-height: 400px;
}

:deep(.el-card__body) {
  height: 100%;
  padding: 12px;
}

.unloaded-status {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nine-grid-layout {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: repeat(3, 1fr);
  gap: 12px;
  height: 100%;
}

.grid-chart-item {
  background: #fbfbfc;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.chart-dom-instance {
  width: 100%;
  height: 100%;
}

.display-collapsible-table {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 0 15px;
}

.table-collapse-title {
  font-weight: bold;
  color: #606266;
  font-size: 13px;
}
</style>
