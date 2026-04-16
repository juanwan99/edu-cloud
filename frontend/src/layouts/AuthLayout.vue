<template>
  <div class="auth-layout">
    <div class="auth-decos">
      <div class="deco deco-mint"></div>
      <div class="deco deco-yellow"></div>
      <div class="deco deco-coral"></div>
      <div class="deco deco-purple"></div>
    </div>
    <div class="auth-content">
      <router-view />
    </div>
  </div>
</template>

<style scoped>
.auth-layout {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg);
  position: relative;
  overflow: hidden;
}

.auth-decos {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.deco {
  position: absolute;
  border-radius: 50%;
  opacity: 0.6;
  animation: floatSlow 12s ease-in-out infinite;
}

.deco-mint {
  top: 10%;
  right: 15%;
  width: 400px;
  height: 400px;
  background: var(--macaron-mint-light);
}

.deco-yellow {
  bottom: 15%;
  left: 10%;
  width: 300px;
  height: 300px;
  background: var(--macaron-yellow-light);
  animation-delay: -4s;
}

.deco-coral {
  top: 60%;
  right: 8%;
  width: 60px;
  height: 60px;
  border: 3px solid var(--macaron-coral);
  background: none;
  animation-duration: 15s;
}

.deco-purple {
  top: 20%;
  left: 8%;
  width: 40px;
  height: 40px;
  background: var(--macaron-purple);
  border-radius: 10px;
  transform: rotate(45deg);
  animation-direction: reverse;
}

.auth-content {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  padding: 0 24px;
}
</style>
