<template>
  <div class="sidebar-container">
    <el-collapse v-model="activePanels" class="custom-collapse">
      <el-collapse-item title="请输入X/Y分量参数及数据" name="x-params">
        <div class="panel-content">
          <div class="section-title">工程参数</div>

          <div class="radio-group-container">
            <el-radio-group v-model="form.dataType">
              <el-radio value="mine">矿井瞬变数据</el-radio>
              <el-radio value="borehole">钻孔瞬变数据</el-radio>
            </el-radio-group>
          </div>

          <el-form :model="form" label-width="100px" label-position="right" class="parameter-form">
            <div class="form-grid">
              <div class="grid-column">
                <el-form-item :label="txEdgeLabel">
                  <el-input v-model="form.txEdge" />
                </el-form-item>
                <el-form-item label="接收面积">
                  <el-input v-model="form.rxArea" />
                </el-form-item>
                <el-form-item label="工作点介质">
                  <el-select v-model="form.medium" placeholder="请选择">
                    <el-option label="煤层" value="coal" />
                    <el-option label="其 他" value="other" />
                  </el-select>
                </el-form-item>
              </div>

              <div class="grid-column">
                <el-form-item label="线圈匝数">
                  <el-input v-model="form.turns" />
                </el-form-item>
                <el-form-item label="测道数目">
                  <el-input v-model="form.channels" />
                </el-form-item>
                <el-form-item label="线 号">
                  <el-select v-model="form.lineNo" placeholder="请选择">
                    <el-option label="1" :value="1" />
                    <el-option label="2" :value="2" />
                  </el-select>
                </el-form-item>
              </div>
            </div>

            <div class="section-title" style="margin-top: 10px">数据文件</div>
            <el-form-item label="X分量文件">
              <input
                type="file"
                accept=".txt,.dat,.csv"
                @change="(e) => (fileX = (e.target as HTMLInputElement).files?.[0] || null)"
              />
            </el-form-item>
            <el-form-item label="Y分量文件">
              <input
                type="file"
                accept=".txt,.dat,.csv"
                @change="(e) => (fileY = (e.target as HTMLInputElement).files?.[0] || null)"
              />
            </el-form-item>

            <div class="form-actions">
              <el-button type="primary" @click="handleConfirm">生成处理</el-button>
              <el-button @click="handleCancel">重置参数</el-button>
            </div>
          </el-form>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'

const emit = defineEmits(['submit', 'toggle-view'])
const activePanels = ref(['x-params'])

const fileX = ref<File | null>(null)
const fileY = ref<File | null>(null)

const defaultValues = {
  dataType: 'borehole',
  txEdge: '2',
  rxArea: '450',
  medium: 'other',
  turns: '10',
  channels: '100',
  lineNo: 1
}

const form = reactive({ ...defaultValues })

// 动态计算 Label：如果是矿井则是边长，钻孔则是直径
const txEdgeLabel = computed(() => {
  return form.dataType === 'mine' ? '发射边长' : '发射直径'
})

const handleConfirm = () => {
  if (!fileX.value || !fileY.value) {
    ElMessage.warning('请先选择X分量和Y分量的数据文件！')
    return
  }

  // 3. 构建 FormData，触发父组件(XYComponent)真正的 API 请求
  const formData = new FormData()
  formData.append('fileX', fileX.value)
  formData.append('fileY', fileY.value)
  // 假设XY分量使用同一套物理参数
  formData.append('paramsX', JSON.stringify(form))
  formData.append('paramsY', JSON.stringify(form))

  emit('submit', formData)
}

const handleCancel = () => {
  Object.assign(form, defaultValues)
  fileX.value = null
  fileY.value = null
}
</script>

<style scoped>
.sidebar-container {
  width: 100%;
  background-color: #ffffff;
  box-sizing: border-box;
}

/* 完美还原 Element Plus 折叠面板的基础样式调整 */
.custom-collapse {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  overflow: hidden;
}

/* 深度重写面板标题栏的字体加粗与内边距 */
:deep(.el-collapse-item__header) {
  font-size: 14px;
  font-weight: bold;
  color: #303133;
  padding-left: 16px;
  background-color: #f8f9fa;
  border-bottom: 1px solid #ebeef5;
}

:deep(.el-collapse-item__content) {
  padding: 20px 16px;
}

/* 区域标题 "工程参数" 样式细化 */
.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 16px; /* 与单选按钮保持 16px 间距 */
  position: relative;
  padding-left: 8px;
}
.section-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 3px;
  width: 3px;
  height: 14px;
  background-color: #409eff; /* 规整的左侧装饰条，使UI更协调 */
  border-radius: 2px;
}

/* 单选框间距微调 */
.radio-group-container {
  margin-bottom: 22px;
}
:deep(.el-radio) {
  margin-right: 40px; /* 两个选项间距严格限制为 40px */
}

/* 核心两列等宽表单网格布局 */
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr); /* 严格的两列等宽划分 */
  gap: 0 24px; /* 列间距 24px */
}

.grid-column {
  display: flex;
  flex-direction: column;
}

/* 统一输入框与下拉选择框的纵向饱满度 */
:deep(.el-form-item) {
  margin-bottom: 18px;
}

:deep(.el-select) {
  width: 100%; /* 下拉框铺满当前列单元格宽度 */
}

/* 底部操作按钮水平居中 */
.form-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 14px;
  padding-top: 10px;
}

.form-actions .el-button {
  min-width: 80px;
}
</style>
