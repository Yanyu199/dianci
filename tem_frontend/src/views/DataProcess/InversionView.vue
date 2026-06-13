<template>
  <div class="inversion-container">
    <h2>瞬变电磁 (TEM) 智能反演系统</h2>

    <div class="control-panel">
      <input type="file" accept=".txt" @change="handleFileChange" />
      <button :disabled="!selectedFile || isProcessing" @click="startInversion">
        {{ isProcessing ? '反演计算中...' : '开始批量反演' }}
      </button>
      <span v-if="resultData.length > 0" class="success-msg">
        ✅ 成功完成 {{ resultData.length }} 个测点的反演！
      </span>
    </div>

    <div v-if="resultData.length > 0" class="result-panel">
      <div class="selector">
        <label>选择测点查看地电剖面图: </label>
        <select v-model="currentStationIndex" @change="drawChart">
          <option v-for="(item, index) in resultData" :key="index" :value="index">
            测点 #{{ item.station }}
          </option>
        </select>
      </div>

      <div ref="chartRef" class="echarts-box"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, shallowRef, nextTick } from 'vue'
import { invertTemData } from '@/api/dataProcess'
import * as echarts from 'echarts'

const selectedFile = ref<File | null>(null)
const isProcessing = ref(false)
const resultData = ref<any[]>([])
const currentStationIndex = ref(0)
const chartRef = ref<HTMLElement | null>(null)
let myChart: echarts.ECharts | null = null

const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    selectedFile.value = target.files[0]
  }
}

const startInversion = async () => {
  if (!selectedFile.value) return
  isProcessing.value = true
  try {
    const res = await invertTemData(selectedFile.value)
    if (res.status === 'success') {
      resultData.value = res.data
      currentStationIndex.value = 0
      await nextTick()
      drawChart()
    } else {
      alert('反演失败: ' + res.message)
    }
  } catch (error) {
    console.error(error)
    alert('请求后端失败，请检查网络')
  } finally {
    isProcessing.value = false
  }
}

const drawChart = () => {
  if (!chartRef.value || resultData.value.length === 0) return

  if (!myChart) {
    myChart = echarts.init(chartRef.value)
  }

  const currentData = resultData.value[currentStationIndex.value]
  const depths = currentData.depths
  const res = currentData.resistivities

  // 构造阶梯图的数据 [电阻率, 深度]
  const stepData = []
  for (let i = 0; i < res.length; i++) {
    stepData.push([res[i], depths[i]])
    // 构造阶梯状，连接下一层的顶面
    if (i < depths.length - 1) {
      stepData.push([res[i], depths[i + 1]])
    } else {
      // 最后一层向下无限延伸（画个示意深度）
      stepData.push([res[i], depths[i] + 50])
    }
  }

  const option = {
    title: { text: `测点 #${currentData.station} - 深度-电阻率剖面图` },
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    xAxis: {
      type: 'value',
      name: '电阻率 (Ω·m)',
      scale: true // 使用对数或自适应缩放更好
    },
    yAxis: {
      type: 'value',
      name: '深度 (m)',
      inverse: true // 深度越深，Y轴越往下
    },
    series: [
      {
        name: '地层电阻率',
        type: 'line',
        step: 'start', // 阶梯线
        data: stepData,
        lineStyle: { width: 3, color: '#FF5722' },
        areaStyle: { opacity: 0.1, color: '#FF5722' }
      }
    ]
  }

  myChart.setOption(option)
}
</script>

<style scoped>
.inversion-container {
  padding: 20px;
  background: #fff;
  border-radius: 8px;
}
.control-panel {
  margin-bottom: 20px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
}
button {
  padding: 8px 16px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin-left: 10px;
}
button:disabled {
  background: #a0cfff;
  cursor: not-allowed;
}
.success-msg {
  color: #67c23a;
  margin-left: 15px;
  font-weight: bold;
}
.selector {
  margin-bottom: 15px;
}
.echarts-box {
  width: 100%;
  height: 500px;
  border: 1px solid #ebeef5;
}
</style>
