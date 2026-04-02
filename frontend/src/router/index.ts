import { createRouter, createWebHistory } from 'vue-router'
import LandingPage from '../views/LandingPage.vue'
import QueueStatus from '../views/QueueStatus.vue'
import AppointmentSelection from '../views/AppointmentSelection.vue'
import PostConsultation from '../views/PostConsultation.vue'
import DoctorDashboard from "../views/DoctorDashboard.vue"

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
      path: '/appointments',
      name: 'appointments',
      component: AppointmentSelection,
    },
    {
      path: '/post-consult',
      name: 'post-consult',
      component: PostConsultation,
    },
    {
      path: '/doctor/dashboard',
      name: 'doctor-dashboard',
      component: DoctorDashboard
    }
  ],
})

export default router
