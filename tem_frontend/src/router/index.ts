import { createRouter, createWebHistory } from 'vue-router'
// 如果你不需要 HomeView 了，甚至可以把下面这行注释掉
// import HomeView from '../views/HomeView.vue'
import XYComponent from '../views/DataProcess/XYComponent.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      // 把原来的 component: HomeView 改成 redirect
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
    }
  ]
})

export default router
