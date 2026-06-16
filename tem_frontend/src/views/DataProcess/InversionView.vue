<template>
  <div class="inversion-container">
    <h2>瞬变电磁 (TEM) 智能反演系统</h2>

    <el-tabs v-model="activeTab" class="custom-tabs">
      <el-tab-pane label="🚀 本地硬盘全自动批量反演 (生产模式)" name="batch">
        <div class="batch-panel">
          <el-alert
            title="请直接粘贴您电脑本地的绝对路径。后端将自动遍历子文件夹 (如 model_1, model_2) 并生成结果。"
            type="info"
            show-icon
            style="margin-bottom: 20px"
            :closable="false"
          />

          <el-form label-width="140px" label-position="left">
            <el-form-item label="📂 原始数据总目录:">
              <el-input
                v-model="inputDirPath"
                placeholder="例如: I:\shunbian\训练文件夹\原始数据"
                clearable
              >
              </el-input>
            </el-form-item>

            <el-form-item label="💾 结果保存总目录:">
              <el-input
                v-model="outputDirPath"
                placeholder="例如: I:\shunbian\训练文件夹\反演数据"
                clearable
              >
              </el-input>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                size="large"
                :loading="isBatching"
                @click="startLocalBatch"
                style="width: 200px"
              >
                {{ isBatching ? '正在计算中...' : '⚡ 全自动批量反演' }}
              </el-button>
            </el-form-item>
          </el-form>

          <div v-if="batchResultMsg" :class="['msg-box', batchStatus]">
            {{ batchResultMsg }}
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="📊 单文件在线预览 (测试模式)" name="single">
        <div class="control-panel">
          <input type="file" accept=".txt" @change="handleFileChange" />
          <button
            class="primary-btn"
            :disabled="!selectedFile || isProcessing"
            @click="startInversion"
          >
            {{ isProcessing ? '反演计算中...' : '开始反演并画图' }}
          </button>

          <span v-if="resultData.length > 0" class="success-msg">
            ✅ 成功完成 {{ resultData.length }} 个测点的反演！
          </span>

          <div v-if="resultData.length > 0" class="export-actions">
            <button class="export-btn csv-btn" @click="exportData('csv')">📥 下载 CSV</button>
            <button class="export-btn dat-btn" @click="exportData('dat')">📥 下载 DAT</button>
          </div>
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
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { invertTemData, batchInvertLocal } from '@/api/dataProcess'
import * as echarts from 'echarts'

const activeTab = ref('batch')

// --- 批量处理相关的状态 ---
const inputDirPath = ref('I:\\shunbian\\训练文件夹\\原始数据')
const outputDirPath = ref('I:\\shunbian\\训练文件夹\\反演数据')
const isBatching = ref(false)
const batchResultMsg = ref('')
const batchStatus = ref('info')

const startLocalBatch = async () => {
  if (!inputDirPath.value || !outputDirPath.value) {
    batchStatus.value = 'error'
    batchResultMsg.value = '❌ 请先填写输入和输出的文件夹路径！'
    return
  }

  isBatching.value = true
  batchResultMsg.value = ''

  try {
    const res = await batchInvertLocal(inputDirPath.value, outputDirPath.value)
    if (res.status === 'success') {
      batchStatus.value = 'success'
      batchResultMsg.value = `🎉 ${res.message} 结果已存入指定目录！`
    } else {
      batchStatus.value = 'error'
      batchResultMsg.value = `⚠️ 失败: ${res.message}`
    }
  } catch (error) {
    batchStatus.value = 'error'
    batchResultMsg.value = '❌ 请求后端失败，请确保后端服务器正常运行。'
  } finally {
    isBatching.value = false
  }
}

// --- 单文件测试相关的状态 ---
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
    alert('请求后端失败，请检查网络')
  } finally {
    isProcessing.value = false
  }
}

const exportData = (format: 'csv' | 'dat') => {
  if (resultData.value.length === 0) return
  const separator = format === 'csv' ? ',' : '\t'
  let content = `测点号${separator}层号${separator}顶面深度(m)${separator}地层电阻率(Ω·m)\n`

  resultData.value.forEach((item) => {
    for (let i = 0; i < item.resistivities.length; i++) {
      content += `${item.station}${separator}${i + 1}${separator}${item.depths[i].toFixed(2)}${separator}${item.resistivities[i].toFixed(2)}\n`
    }
  })

  const bom = format === 'csv' ? '\uFEFF' : ''
  const blob = new Blob([bom + content], { type: 'text/plain;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `TEM反演结果.${format}`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

const drawChart = () => {
  if (!chartRef.value || resultData.value.length === 0) return
  if (!myChart) myChart = echarts.init(chartRef.value)

  const currentData = resultData.value[currentStationIndex.value]
  const depths = currentData.depths
  const res = currentData.resistivities
  const stepData = []

  for (let i = 0; i < res.length; i++) {
    stepData.push([res[i], depths[i]])
    if (i < depths.length - 1) stepData.push([res[i], depths[i + 1]])
    else stepData.push([res[i], depths[i] + 50])
  }

  myChart.setOption({
    title: { text: `测点 #${currentData.station} - 深度-电阻率剖面图` },
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    xAxis: { type: 'value', name: '电阻率 (Ω·m)', scale: true },
    yAxis: { type: 'value', name: '深度 (m)', inverse: true },
    series: [
      {
        name: '地层电阻率',
        type: 'line',
        step: 'start',
        data: stepData,
        lineStyle: { width: 3, color: '#FF5722' },
        areaStyle: { opacity: 0.1, color: '#FF5722' }
      }
    ]
  })
}
</script>

<style scoped>
.inversion-container {
  padding: 20px;
  background: #fff;
  border-radius: 8px;
}
.custom-tabs {
  margin-top: 15px;
}
.batch-panel {
  padding: 30px;
  background: #fafafa;
  border-radius: 8px;
  border: 1px dashed #dcdfe6;
}
.control-panel {
  margin-bottom: 20px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
}
button {
  padding: 8px 16px;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin-left: 10px;
  font-weight: 500;
}
button:disabled {
  background: #a0cfff !important;
  cursor: not-allowed;
}
.primary-btn {
  background: #409eff;
}
.export-actions {
  display: inline-block;
  margin-left: 20px;
  border-left: 2px solid #e4e7ed;
  padding-left: 10px;
}
.csv-btn {
  background: #67c23a;
}
.dat-btn {
  background: #e6a23c;
}

.msg-box {
  margin-top: 20px;
  padding: 15px;
  border-radius: 4px;
  font-weight: bold;
}
.msg-box.success {
  background-color: #f0f9eb;
  color: #67c23a;
  border: 1px solid #e1f3d8;
}
.msg-box.error {
  background-color: #fef0f0;
  color: #f56c6c;
  border: 1px solid #fde2e2;
}
.msg-box.info {
  background-color: #f4f4f5;
  color: #909399;
  border: 1px solid #e9e9eb;
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
