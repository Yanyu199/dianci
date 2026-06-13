import { createRouter, createWebHistory } from 'vue-router'
import XYComponent from '../views/DataProcess/XYComponent.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      // 默认重定向到数据预处理页面
      redirect: '/data-process/xy'
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('../views/AboutView.vue')
    },
    {
      path: '/data-process/xy',
      name: 'XYComponent',
      component: XYComponent
    },
    // ==========================================
    // 🌟 这里就是解决你问题的关键：把反演页面注册进来
    // ==========================================
    {
      path: '/inversion',
      name: 'inversion',
      component: () => import('../views/DataProcess/InversionView.vue')
    }
  ]
})

export default router
