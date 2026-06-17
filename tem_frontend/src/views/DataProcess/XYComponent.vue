<template>
  <div class="integrated-layout">
    <div class="left-sidebar">
      <h3 class="sidebar-title">⚙️ 数据处理面板</h3>

      <div class="control-card x-card">
        <div class="card-header">🔴 X 分量 (横向)</div>
        <input
          type="file"
          class="file-input"
          accept=".txt,.csv"
          @change="(e) => handleFile(e, 'X')"
        />
        <el-button size="small" type="primary" plain @click="showXParams = true" class="param-btn">
          <el-icon><Setting /></el-icon> 设置 X 参量
        </el-button>
      </div>

      <div class="control-card y-card">
        <div class="card-header">🟢 Y 分量 (纵向)</div>
        <input
          type="file"
          class="file-input"
          accept=".txt,.csv"
          @change="(e) => handleFile(e, 'Y')"
        />
        <el-button size="small" type="success" plain @click="showYParams = true" class="param-btn">
          <el-icon><Setting /></el-icon> 设置 Y 参量
        </el-button>
      </div>

      <div class="control-card z-card">
        <div class="card-header">🔵 Z 分量 (孔轴)</div>
        <input
          type="file"
          class="file-input"
          accept=".txt,.csv"
          @change="(e) => handleFile(e, 'Z')"
        />
        <p class="z-tip">上传后将自动触发后台智能反演</p>
      </div>

      <div class="action-box">
        <el-button
          type="primary"
          :disabled="!canProcess"
          :loading="isProcessing"
          class="process-btn"
          @click="startProcess"
        >
          {{ isProcessing ? '融合计算中...' : '开始综合处理与反演' }}
        </el-button>

        <el-button
          v-if="hasResult"
          type="warning"
          class="next-btn"
          @click="$router.push('/3d-imaging')"
        >
          👉 探索 3D 成果
        </el-button>
      </div>
    </div>

    <div class="right-main">
      <div v-if="!hasResult && !isProcessing" class="empty-chart">
        <el-empty description="请在左侧上传 X、Y、Z 数据并点击处理" />
      </div>

      <div v-show="hasResult" class="chart-list-wrapper">
        <div class="toolbar">
          <span
            >💡 提示：以下是各测点的原始衰减曲线。Z 分量反演已在后台完成。向下滚动可查看全部。</span
          >
        </div>

        <div class="chart-grid">
          <div v-for="(item, index) in combinedData" :key="index" class="station-chart-wrapper">
            <div :id="'echarts-' + index" class="echarts-box"></div>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="showXParams" title="X 分量参数设置" width="450px" destroy-on-close>
      <el-form :model="xParams" label-width="110px" size="default">
        <el-form-item label="数据类型">
          <el-radio-group v-model="xParams.dataType">
            <el-radio label="mine">矿井瞬变数据</el-radio>
            <el-radio label="borehole">钻孔瞬变数据</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="线号">
          <el-input v-model="xParams.lineNumber" type="number"></el-input>
        </el-form-item>
        <el-form-item label="发射边长">
          <el-input v-model="xParams.txSideLength" type="number"
            ><template #append>m</template></el-input
          >
        </el-form-item>
        <el-form-item label="线圈匝数">
          <el-input v-model="xParams.coilTurns" type="number"
            ><template #append>匝</template></el-input
          >
        </el-form-item>
        <el-form-item label="接收面积">
          <el-input v-model="xParams.rxArea" type="number"
            ><template #append>m²</template></el-input
          >
        </el-form-item>
        <el-form-item label="测道数据">
          <el-input v-model="xParams.channelCount" type="number"
            ><template #append>道</template></el-input
          >
        </el-form-item>
        <el-form-item label="工作点介质">
          <el-input v-model="xParams.mediumRes" type="number"
            ><template #append>Ω·m</template></el-input
          >
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showXParams = false">取消</el-button>
        <el-button type="primary" @click="showXParams = false">确认应用</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showYParams" title="Y 分量参数设置" width="450px" destroy-on-close>
      <el-form :model="yParams" label-width="110px" size="default">
        <el-form-item label="数据类型">
          <el-radio-group v-model="yParams.dataType">
            <el-radio label="mine">矿井瞬变数据</el-radio>
            <el-radio label="borehole">钻孔瞬变数据</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="线号">
          <el-input v-model="yParams.lineNumber" type="number"></el-input>
        </el-form-item>
        <el-form-item label="发射边长">
          <el-input v-model="yParams.txSideLength" type="number"
            ><template #append>m</template></el-input
          >
        </el-form-item>
        <el-form-item label="线圈匝数">
          <el-input v-model="yParams.coilTurns" type="number"
            ><template #append>匝</template></el-input
          >
        </el-form-item>
        <el-form-item label="接收面积">
          <el-input v-model="yParams.rxArea" type="number"
            ><template #append>m²</template></el-input
          >
        </el-form-item>
        <el-form-item label="测道数据">
          <el-input v-model="yParams.channelCount" type="number"
            ><template #append>道</template></el-input
          >
        </el-form-item>
        <el-form-item label="工作点介质">
          <el-input v-model="yParams.mediumRes" type="number"
            ><template #append>Ω·m</template></el-input
          >
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showYParams = false">取消</el-button>
        <el-button type="primary" @click="showYParams = false">确认应用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { invertTemData } from '@/api/dataProcess'
import { globalData } from '@/store'
import * as echarts from 'echarts'
import { Setting } from '@element-plus/icons-vue'

const router = useRouter()
const fileX = ref<File | null>(null)
const fileY = ref<File | null>(null)
const fileZ = ref<File | null>(null)

const showXParams = ref(false)
const showYParams = ref(false)

const defaultParams = {
  dataType: 'borehole',
  lineNumber: 1,
  txSideLength: 2.0,
  coilTurns: 4,
  rxArea: 100,
  channelCount: 40,
  mediumRes: 100
}
const xParams = ref({ ...defaultParams })
const yParams = ref({ ...defaultParams })

const canProcess = computed(() => fileX.value && fileY.value && fileZ.value)
const isProcessing = ref(false)
const hasResult = ref(false)

const combinedData = ref<any[]>([])
let chartInstances: echarts.ECharts[] = []

// 🌟 1. 修复测道识别：严格模拟后端的 skip_header=1 (跳过第一行表头)
const detectChannelCount = async (file: File) => {
  try {
    const text = await file.text()
    const lines = text.trim().split('\n')
    let count = 0
    let isFirstLine = true // 用于跳过表头

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim()
      if (!line) continue

      if (isFirstLine) {
        isFirstLine = false
        continue
      }

      const parts = line.split(/[\s,]+/)
      if (parts.length >= 2) {
        const time = parseFloat(parts[0])
        if (!isNaN(time)) count++
      }
    }
    return count > 0 ? count : 40
  } catch (error) {
    return 40
  }
}

const handleFile = async (e: Event, type: 'X' | 'Y' | 'Z') => {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0] || null
  if (!file) return

  if (type === 'X') {
    fileX.value = file
    xParams.value.channelCount = await detectChannelCount(file)
  } else if (type === 'Y') {
    fileY.value = file
    yParams.value.channelCount = await detectChannelCount(file)
  } else if (type === 'Z') {
    fileZ.value = file
  }
}

const parseRawFileGrouped = async (file: File, params: any) => {
  const text = await file.text()
  const lines = text.trim().split('\n')

  // 从弹窗设置中提取物理参量
  const { channelCount, dataType, txSideLength, rxArea, coilTurns } = params

  // 完美复刻 Python 后端的面积与等效磁矩计算
  let txArea = 0
  if (dataType === 'mine') {
    txArea = txSideLength * txSideLength
  } else {
    txArea = Math.PI * Math.pow(txSideLength / 2.0, 2)
  }
  const txMoment = txArea * coilTurns
  const normalizeFactor = txMoment * rxArea // 归一化分母

  const times: number[] = []
  const stationVoltages: number[][] = [] // 存放各列(各测点)的电压

  let validRowCount = 0
  let isFirstLine = true

  for (let i = 0; i < lines.length; i++) {
    // 超过设定的测道数则停止读取
    if (validRowCount >= channelCount) break

    const line = lines[i].trim()
    if (!line) continue

    // 完美复刻 skip_header=1
    if (isFirstLine) {
      isFirstLine = false
      continue
    }

    const parts = line.split(/[\s,]+/)
    const rawTime = parseFloat(parts[0])

    if (!isNaN(rawTime)) {
      // 完美复刻：秒(s)换算为毫秒(ms)
      times.push(rawTime * 1000.0)

      // 🚨 核心逻辑：从第 1 列开始横向读取，每一列代表一个测点！
      for (let j = 1; j < parts.length; j++) {
        const rawVoltage = parseFloat(parts[j])
        if (!isNaN(rawVoltage)) {
          const stationIdx = j - 1
          if (!stationVoltages[stationIdx]) {
            stationVoltages[stationIdx] = []
          }
          // 完美复刻：取绝对值，防溢出平移，并除以(发射磁矩*接收面积)
          const normalizedV = ((Math.abs(rawVoltage) + 1e-16) / normalizeFactor) * 1e6
          stationVoltages[stationIdx].push(normalizedV)
        }
      }
      validRowCount++
    }
  }

  // 将 [测点][测道] 的矩阵重组为 ECharts 支持的序列
  const stations: { station: number; data: number[][] }[] = []
  for (let s = 0; s < stationVoltages.length; s++) {
    const dataArr: number[][] = []
    for (let t = 0; t < times.length; t++) {
      if (stationVoltages[s][t] !== undefined) {
        dataArr.push([times[t], stationVoltages[s][t]])
      }
    }
    if (dataArr.length > 0) {
      stations.push({ station: s + 1, data: dataArr })
    }
  }

  return stations
}

const startProcess = async () => {
  if (!canProcess.value) return
  isProcessing.value = true

  try {
    globalData.fileX = fileX.value
    globalData.fileY = fileY.value
    globalData.fileZ = fileZ.value

    // 将用户设置的真实物理参量传入解析器
    const resX = await parseRawFileGrouped(fileX.value!, xParams.value)
    const resY = await parseRawFileGrouped(fileY.value!, yParams.value)
    // Z 分量一般与 X 使用同一套配置
    const resZ = await parseRawFileGrouped(fileZ.value!, xParams.value)

    const invRes = await invertTemData(fileZ.value!)
    if (invRes.status === 'success') {
      globalData.inversionResult = invRes.data
      combinedData.value = []

      // 找出最大的测点数目（有多少列，就有多少个测点）
      const maxStations = Math.max(resX.length, resY.length, resZ.length)

      for (let i = 0; i < maxStations; i++) {
        // 安全提取数据矩阵
        const xData = resX[i] ? resX[i].data : []
        const yData = resY[i] ? resY[i].data : []
        const zData = resZ[i] ? resZ[i].data : []

        combinedData.value.push({
          station: i + 1,
          xRaw: xData,
          yRaw: yData,
          zRaw: zData
        })
      }

      hasResult.value = true
      await nextTick()
      drawAllCharts()
    } else {
      alert('Z分量反演失败: ' + invRes.message)
    }
  } catch (error) {
    console.error(error)
    alert('处理异常，请检查网络或文件格式！')
  } finally {
    isProcessing.value = false
  }
}

// 🌟 只渲染原始衰减曲线 (不再画反演地层了)
const drawAllCharts = () => {
  chartInstances.forEach((inst) => inst.dispose())
  chartInstances = []

  combinedData.value.forEach((item, index) => {
    const dom = document.getElementById('echarts-' + index)
    if (!dom) return

    const myChart = echarts.init(dom)
    chartInstances.push(myChart)

    const option = {
      title: {
        text: `📍 测点 #${item.station}`,
        left: 'center',
        textStyle: { color: '#303133', fontSize: 14 } // 字号缩小以适配 3 列网格
      },
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      legend: {
        data: ['X原始响应', 'Y原始响应', 'Z原始响应'], // 移除了反演图例
        top: '10%',
        textStyle: { fontSize: 12, fontWeight: 'bold' }
      },
      // 🌟 改为单网格，占满整个画布
      grid: { top: '25%', bottom: '15%', left: '15%', right: '8%' },

      // 👇 就在这里：把 '衰减时间 (s)' 改成了 '衰减时间 (ms)' 👇
      xAxis: { type: 'log', name: '衰减时间 (ms)', nameLocation: 'middle', nameGap: 25 },

      yAxis: {
        type: 'log',
        name: '衰减电压 (μV/A)',
        nameLocation: 'middle',
        nameGap: 45, // 标题向外偏移，防止和数字重叠
        axisLabel: {
          formatter: (value: number) => value.toExponential(1).toUpperCase()
        }
      },
      series: [
        {
          name: 'X原始响应',
          type: 'line',
          data: item.xRaw,
          itemStyle: { color: '#ff4d4f' },
          symbol: 'none'
        },
        {
          name: 'Y原始响应',
          type: 'line',
          data: item.yRaw,
          itemStyle: { color: '#52c41a' },
          symbol: 'none'
        },
        {
          name: 'Z原始响应',
          type: 'line',
          data: item.zRaw,
          itemStyle: { color: '#1890ff' },
          symbol: 'none'
        }
      ]
    }
    myChart.setOption(option)
  })
}

onMounted(() => {
  window.addEventListener('resize', () => {
    chartInstances.forEach((inst) => inst.resize())
  })
})
onBeforeUnmount(() => {
  chartInstances.forEach((inst) => inst.dispose())
})
</script>

<style scoped>
.integrated-layout {
  display: flex;
  gap: 20px;
  height: calc(100vh - 100px);
  width: 100%;
}

.left-sidebar {
  width: 320px;
  background: #fdfdfd;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 15px;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.02);
  overflow-y: auto;
}

.right-main {
  flex: 1;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 15px;
  display: flex;
  flex-direction: column;
  overflow: hidden; /* 让内部列表自行滚动 */
}

.sidebar-title {
  margin: 0 0 10px 0;
  font-size: 16px;
  color: #303133;
  border-bottom: 2px solid #ebeef5;
  padding-bottom: 10px;
}

.control-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 12px;
}
.control-card.x-card {
  border-left: 4px solid #ff4d4f;
}
.control-card.y-card {
  border-left: 4px solid #52c41a;
}
.control-card.z-card {
  border-left: 4px solid #1890ff;
}

.card-header {
  font-weight: bold;
  margin-bottom: 10px;
  font-size: 14px;
}
.file-input {
  width: 100%;
  font-size: 12px;
  margin-bottom: 10px;
}
.param-btn {
  width: 100%;
}
.z-tip {
  font-size: 12px;
  color: #909399;
  margin: 0;
}

.action-box {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 15px;
}
.process-btn {
  width: 100%;
  height: 40px;
  font-weight: bold;
}
.next-btn {
  width: 100%;
  height: 45px;
  font-weight: bold;
  animation: pulse 2s infinite;
  font-size: 16px;
}

@keyframes pulse {
  0% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.02);
  }
  100% {
    transform: scale(1);
  }
}

.empty-chart {
  display: flex;
  justify-content: center;
  align-items: center;
  flex: 1;
}

/* 🌟 右侧滚动容器 */
.chart-list-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.toolbar {
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  color: #606266;
  margin-bottom: 15px;
}

/* 🌟 一行 3 个的超级网格系统 */
.chart-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr); /* 核心：分为均等的 3 列 */
  gap: 15px; /* 间距 */
  overflow-y: auto; /* 超出则上下滚动 */
  padding-right: 5px;
  flex: 1;
  align-content: start; /* 从顶部开始对齐 */
}

/* 每一个测点的独立边框容器 */
.station-chart-wrapper {
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 10px 0;
  width: 100%;
}

/* 里面的绘图画布 (高度缩小以适应一行三列的比例) */
.echarts-box {
  width: 100%;
  height: 350px;
}
</style>
