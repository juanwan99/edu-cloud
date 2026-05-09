import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router/index.js'
import App from './App.vue'
import clientLogger from './utils/clientLogger.js'
import './assets/styles/variables.css'
import './assets/styles/global.css'

if (typeof __BUILD_TIME__ !== 'undefined') {
  console.log(
    `[edu-cloud] id=${__BUILD_ID__} build=${__GIT_HASH__} time=${__BUILD_TIME__} dirty=${__SOURCE_DIRTY__}`
  )
}

const app = createApp(App)
app.use(createPinia())
app.use(router)

// Global error handlers → clientLogger
app.config.errorHandler = (err, instance, info) => {
  clientLogger.jsError(err, info)
}
window.onerror = (msg, src, line, col, err) => {
  clientLogger.jsError(err || { message: msg }, `${src}:${line}:${col}`)
}
window.onunhandledrejection = (event) => {
  clientLogger.jsError(event.reason, 'unhandledrejection')
}

app.mount('#app')
