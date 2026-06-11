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
