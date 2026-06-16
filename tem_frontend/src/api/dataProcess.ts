import axios from 'axios'

// 假设后端运行在 8000 端口
const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api'
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
