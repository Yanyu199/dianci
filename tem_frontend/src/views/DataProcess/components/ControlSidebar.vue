<template>
  <div class="sidebar-container">
    <el-collapse v-model="activePanels" class="custom-collapse">
      <el-collapse-item title="请输入X/Y分量参数及数据" name="x-params">
        <div class="panel-content">
          <el-tabs v-model="activeTab" class="xy-tabs">
            <el-tab-pane label="X分量参数" name="X">
              <div class="radio-group-container">
                <el-radio-group v-model="formX.dataType">
                  <el-radio value="mine">矿井瞬变数据</el-radio>
                  <el-radio value="borehole">钻孔瞬变数据</el-radio>
                </el-radio-group>
              </div>

              <el-form
                :model="formX"
                label-width="100px"
                label-position="right"
                class="parameter-form"
              >
                <div class="form-grid">
                  <div class="grid-column">
                    <el-form-item :label="txEdgeLabelX">
                      <el-input v-model="formX.txEdge" />
                    </el-form-item>
                    <el-form-item label="接收面积">
                      <el-input v-model="formX.rxArea" />
                    </el-form-item>
                    <el-form-item label="工作点介质">
                      <el-select v-model="formX.medium" placeholder="请选择">
                        <el-option label="煤层" value="coal" />
                        <el-option label="其 他" value="other" />
                      </el-select>
                    </el-form-item>
                  </div>
                  <div class="grid-column">
                    <el-form-item label="线圈匝数">
                      <el-input v-model="formX.turns" />
                    </el-form-item>
                    <el-form-item label="测道数目">
                      <el-input v-model="formX.channels" />
                    </el-form-item>
                    <el-form-item label="线 号">
                      <el-select v-model="formX.lineNo" placeholder="请选择">
                        <el-option label="1" :value="1" />
                        <el-option label="2" :value="2" />
                      </el-select>
                    </el-form-item>
                  </div>
                </div>
              </el-form>
            </el-tab-pane>

            <el-tab-pane label="Y分量参数" name="Y">
              <div class="radio-group-container">
                <el-radio-group v-model="formY.dataType">
                  <el-radio value="mine">矿井瞬变数据</el-radio>
                  <el-radio value="borehole">钻孔瞬变数据</el-radio>
                </el-radio-group>
              </div>

              <el-form
                :model="formY"
                label-width="100px"
                label-position="right"
                class="parameter-form"
              >
                <div class="form-grid">
                  <div class="grid-column">
                    <el-form-item :label="txEdgeLabelY">
                      <el-input v-model="formY.txEdge" />
                    </el-form-item>
                    <el-form-item label="接收面积">
                      <el-input v-model="formY.rxArea" />
                    </el-form-item>
                    <el-form-item label="工作点介质">
                      <el-select v-model="formY.medium" placeholder="请选择">
                        <el-option label="煤层" value="coal" />
                        <el-option label="其 他" value="other" />
                      </el-select>
                    </el-form-item>
                  </div>
                  <div class="grid-column">
                    <el-form-item label="线圈匝数">
                      <el-input v-model="formY.turns" />
                    </el-form-item>
                    <el-form-item label="测道数目">
                      <el-input v-model="formY.channels" />
                    </el-form-item>
                    <el-form-item label="线 号">
                      <el-select v-model="formY.lineNo" placeholder="请选择">
                        <el-option label="1" :value="1" />
                        <el-option label="2" :value="2" />
                      </el-select>
                    </el-form-item>
                  </div>
                </div>
              </el-form>
            </el-tab-pane>
          </el-tabs>

          <div class="section-title" style="margin-top: 5px">数据文件</div>
          <el-form label-width="100px" label-position="right">
            <el-form-item label="X分量文件">
              <input
                type="file"
                accept=".txt,.dat,.csv"
                @change="(e) => handleFileChange('X', e)"
              />
            </el-form-item>
            <el-form-item label="Y分量文件">
              <input
                type="file"
                accept=".txt,.dat,.csv"
                @change="(e) => handleFileChange('Y', e)"
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
const activeTab = ref('X') // 控制当前活动的 Tab

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

// 修改：分别管理 X 和 Y 独立的表单数据
const formX = reactive({ ...defaultValues })
const formY = reactive({ ...defaultValues })

// 修改：分别计算对应标签
const txEdgeLabelX = computed(() => (formX.dataType === 'mine' ? '发射边长' : '发射直径'))
const txEdgeLabelY = computed(() => (formY.dataType === 'mine' ? '发射边长' : '发射直径'))

const handleFileChange = (type: 'X' | 'Y', e: Event) => {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0] || null

  // 1. 将文件绑定到原有的 fileX 或 fileY 变量
  if (type === 'X') {
    fileX.value = file
  } else {
    fileY.value = file
  }

  // 2. 如果成功选择了文件，则利用 FileReader 分析数据行数
  if (file) {
    const reader = new FileReader()
    reader.onload = (event) => {
      const text = event.target?.result as string
      if (text) {
        // 按换行符分割文本，并过滤掉空行
        const lines = text.split(/\r\n|\n/).filter((line) => line.trim() !== '')

        // 由于你的后端读取数据时有一行表头 (skip_header=1)，这里我们将总行数减 1 得到有效数据行数
        const maxChannels = lines.length > 1 ? lines.length - 1 : 0

        // 3. 将计算出的行数自动回填到表单中
        if (type === 'X') {
          formX.channels = maxChannels.toString()
        } else {
          formY.channels = maxChannels.toString()
        }
      }
    }
    // 读取文件内容为文本
    reader.readAsText(file)
  }
}

const handleConfirm = () => {
  if (!fileX.value || !fileY.value) {
    ElMessage.warning('请先选择X分量和Y分量的数据文件！')
    return
  }

  const formData = new FormData()
  formData.append('fileX', fileX.value)
  formData.append('fileY', fileY.value)

  // 修改：分别将独立的 formX 和 formY 参数传给后端
  formData.append('paramsX', JSON.stringify(formX))
  formData.append('paramsY', JSON.stringify(formY))

  emit('submit', formData)
}

const handleCancel = () => {
  Object.assign(formX, defaultValues)
  Object.assign(formY, defaultValues)
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

.custom-collapse {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  overflow: hidden;
}

:deep(.el-collapse-item__header) {
  font-size: 14px;
  font-weight: bold;
  color: #303133;
  padding-left: 16px;
  background-color: #f8f9fa;
  border-bottom: 1px solid #ebeef5;
}

:deep(.el-collapse-item__content) {
  padding: 10px 16px 20px 16px;
}

.xy-tabs {
  margin-bottom: 15px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 16px;
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
  background-color: #409eff;
  border-radius: 2px;
}

.radio-group-container {
  margin-bottom: 22px;
}
:deep(.el-radio) {
  margin-right: 40px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0 24px;
}

.grid-column {
  display: flex;
  flex-direction: column;
}

:deep(.el-form-item) {
  margin-bottom: 18px;
}

:deep(.el-select) {
  width: 100%;
}

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
