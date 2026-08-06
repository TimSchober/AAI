<script setup lang="ts">
import SideMenu from '@/components/SideMenu.vue'
</script>

<template>
  <div class="layout">
    <SideMenu />
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 15rem 1fr;
  height: 100vh;
}

.content {
  min-width: 0;
  overflow: hidden;
}

@media (max-width: 40rem) {
  .layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
  }
}
</style>
