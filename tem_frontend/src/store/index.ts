import { reactive } from 'vue'

// 全局响应式状态：用于跨页面传递上传的原始文件和反演结果
export const globalData = reactive({
  fileX: null as File | null,
  fileY: null as File | null,
  fileZ: null as File | null,
  trajectoryFile: null as File | null,
  inversionResult: null as any[] | null
})

// 清理缓存
export const clearGlobalData = () => {
  globalData.fileX = null
  globalData.fileY = null
  globalData.fileZ = null
  globalData.trajectoryFile = null
  globalData.inversionResult = null
}
