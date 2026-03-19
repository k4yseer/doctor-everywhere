<script setup lang="ts">
import AppointmentList from './domains/appointment/components/AppointmentList.vue';
</script>

<template>
  <div class="min-h-screen bg-gray-50 p-8">
    <AppointmentList :appointment-ids="[1, 2, 3]" />
  </div>
</template>