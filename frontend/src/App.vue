<template>
  <n-config-provider :theme-overrides="themeOverrides" :locale="zhCN" :date-locale="dateZhCN">
    <n-loading-bar-provider>
      <n-message-provider>
        <n-dialog-provider>
          <LoadingBarController />
          <router-view />
        </n-dialog-provider>
      </n-message-provider>
    </n-loading-bar-provider>
  </n-config-provider>
</template>

<script setup>
import { h, defineComponent } from 'vue'
import { zhCN, dateZhCN, useLoadingBar } from 'naive-ui'
import { useRouter } from 'vue-router'
import { themeOverrides } from './theme.js'

const LoadingBarController = defineComponent({
  setup() {
    const loadingBar = useLoadingBar()
    const router = useRouter()

    router.beforeEach(() => {
      loadingBar.start()
    })
    router.afterEach(() => {
      loadingBar.finish()
    })
    router.onError(() => {
      loadingBar.error()
    })

    return () => null
  }
})
</script>
