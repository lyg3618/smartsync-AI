<template>
  <router-view v-slot="{ Component, route }">
    <Transition name="route-shell" mode="out-in">
      <component :is="Component" :key="route.fullPath" />
    </Transition>
  </router-view>
</template>

<script setup></script>

<style scoped>
.route-shell-enter-active,
.route-shell-leave-active {
  transition: opacity 0.26s ease, transform 0.26s ease;
}

.route-shell-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.route-shell-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
