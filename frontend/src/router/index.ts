import { createRouter, createWebHistory } from 'vue-router'
import LandingPage from '../views/LandingPage.vue'
import QueueStatus from '../views/QueueStatus.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'landing',
      component: LandingPage,
    },
    {
      path: '/queue',
      name: 'queue',
      component: QueueStatus,
    },
  ],
})

export default router
