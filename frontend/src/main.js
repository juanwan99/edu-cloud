import { createApp } from 'vue'
import { createPinia } from 'pinia'
import naive from 'naive-ui'
import router from './router/index.js'
import App from './App.vue'

if (typeof __BUILD_TIME__ !== 'undefined') {
  console.log(
    `[edu-cloud] id=${__BUILD_ID__} build=${__GIT_HASH__} time=${__BUILD_TIME__} dirty=${__SOURCE_DIRTY__}`
  )
}

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(naive)
app.mount('#app')
