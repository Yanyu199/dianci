import axios from 'axios'

// 假设后端运行在 8000 端口
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'
})

export const uploadXYData = (formData: FormData) => {
  return apiClient.post('/upload_xy', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}
// 新增：调用反演接口
export const invertTemData = async (file: File) => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await apiClient.post('/tem/invert', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
  return response.data
}
// 新增：调用本地硬盘批量反演接口
export const batchInvertLocal = async (inputDir: string, outputDir: string) => {
  const response = await apiClient.post('/tem/batch_local', {
    input_dir: inputDir,
    output_dir: outputDir
  })
  return response.data
}
// 新增：调用 3D 成像接口
export const generate3DModel = async (fileX: File, fileY: File, fileZ: File) => {
  const formData = new FormData()
  formData.append('file_x', fileX)
  formData.append('file_y', fileY)
  formData.append('file_z', fileZ)

  const response = await apiClient.post('/tem/generate_3d', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return response.data
}

export const generateBoreholeImage = async (
  fileX: File,
  fileY: File,
  fileZ: File,
  trajectoryFile: File
) => {
  const formData = new FormData()
  formData.append('file_x', fileX)
  formData.append('file_y', fileY)
  formData.append('file_z', fileZ)
  formData.append('trajectory_file', trajectoryFile)

  const response = await apiClient.post('/tem/borehole_image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return response.data
}

export const generateResultDat = async (
  fileX: File,
  fileY: File,
  fileZ: File,
  trajectoryFile?: File | null,
  options?: { xRange?: [number, number]; yRange?: [number, number]; gridSize?: number }
) => {
  const formData = new FormData()
  formData.append('file_x', fileX)
  formData.append('file_y', fileY)
  formData.append('file_z', fileZ)
  if (trajectoryFile) formData.append('trajectory_file', trajectoryFile)
  if (options?.xRange) formData.append('x_range', options.xRange.join(','))
  if (options?.yRange) formData.append('y_range', options.yRange.join(','))
  if (options?.gridSize) formData.append('grid_size', String(options.gridSize))

  const response = await apiClient.post('/tem/generate_result_dat', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return response.data
}
