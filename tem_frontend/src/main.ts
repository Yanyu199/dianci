import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

// 1. 引入 Element Plus 和它的核心样式文件
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// 2. 全局挂载 Element Plus
app.use(ElementPlus)

app.mount('#app')
