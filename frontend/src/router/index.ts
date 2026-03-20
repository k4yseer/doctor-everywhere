import { createRouter, createWebHistory } from 'vue-router'
import LandingPage from '../views/LandingPage.vue'
import QueueStatus from '../views/QueueStatus.vue'
import PostConsultation from '../views/PostConsultation.vue'

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
    {
      path: '/post-consult',
      name: 'post-consult',
      component: PostConsultation,
    },
  ],
})

export default router
