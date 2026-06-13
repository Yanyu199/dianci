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
