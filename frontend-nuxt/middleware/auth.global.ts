export default defineNuxtRouteMiddleware((to) => {
  const token = useCookie('edu_token')
  const publicPaths = ['/login', '/']

  if (!token.value && !publicPaths.includes(to.path)) {
    return navigateTo('/login')
  }
})
