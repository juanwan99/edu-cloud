// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: true },

  modules: [
    '@element-plus/nuxt',
    '@pinia/nuxt',
  ],

  css: ['~/assets/css/main.scss'],

  runtimeConfig: {
    public: {
      apiBase: 'http://localhost:9000',
    },
  },

  vite: {
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:9000',
          changeOrigin: true,
        },
      },
    },
  },

  devServer: {
    port: 3000,
  },

  compatibilityDate: '2026-04-12',
})
