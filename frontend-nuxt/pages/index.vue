<template>
  <div />
</template>
<script setup lang="ts">
const token = useCookie('edu_token')
if (token.value) {
  navigateTo('/home')
} else {
  navigateTo('/login')
}
</script>
