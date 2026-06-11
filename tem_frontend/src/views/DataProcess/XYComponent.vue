<template>
  <div class="xy-layout">
    <div class="left-sidebar">
      <ControlSidebar
        :loading="loading"
        :has-data="hasData"
        :current-view="currentView"
        @submit="submitAndRender"
        @toggle-view="handleToggleView"
      />
    </div>

    <div class="right-content" v-loading="loading" element-loading-text="数据解析与图形渲染中...">
      <div v-if="!hasData" class="empty-status">
        <el-empty description="请在左侧上传X/Y分量数据、设置参数并生成图表" />
      </div>
      <template v-else>
        <ChartGrid v-if="currentView === 'chart'" :chart-data="graphData" />
        <DataTable v-else-if="currentView === 'table'" :table-data="tableData" />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadXYData } from '@/api/dataProcess'

// 引入拆分的子组件
import ControlSidebar from './components/ControlSidebar.vue'
import ChartGrid from './components/ChartGrid.vue'
import DataTable from './components/DataTable.vue'

const loading = ref(false)
const hasData = ref(false)
const currentView = ref<'chart' | 'table'>('chart') // 控制右侧显示图表还是表格

// 存储后端返回的数据
const graphData = ref<any>(null)
const tableData = ref<any[]>([])

// 处理从左侧面板发出的提交请求
const submitAndRender = async (formData: FormData) => {
  loading.value = true
  try {
    const res = await uploadXYData(formData)
    graphData.value = res.data
    tableData.value = res.data.table_data
    hasData.value = true
    currentView.value = 'chart' // 默认生成后切回图表视图
    ElMessage.success('配置已应用，图表解析并渲染成功！')
  } catch (error) {
    console.error(error)
    ElMessage.error('计算模块异常，请检查后端服务日志。')
  } finally {
    loading.value = false
  }
}

// 切换视图模式
const handleToggleView = (view: 'chart' | 'table') => {
  currentView.value = view
}
</script>

<style scoped>
.xy-layout {
  display: flex;
  height: calc(100vh - 100px);
  gap: 20px;
  padding: 10px;
}

.left-sidebar {
  width: 380px; /* 固定左侧宽度 */
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.right-content {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.empty-status {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
