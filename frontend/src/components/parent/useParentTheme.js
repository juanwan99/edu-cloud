import { ref, computed } from 'vue'
import { darkTheme } from 'naive-ui'

const darkOverrides = {
  common: {
    primaryColor: '#F4DA4C', primaryColorHover: '#E8CF40', primaryColorPressed: '#D4B830', primaryColorSuppl: '#F4DA4C',
    bodyColor: '#09061B', cardColor: '#181433', textColor1: '#F6F3FF', textColor2: '#C9C2DD', textColor3: '#9B93B5',
    borderColor: 'rgba(255,255,255,0.08)', inputColor: '#121026',
  },
}

const lightOverrides = {
  common: {
    primaryColor: '#644CF0', primaryColorHover: '#5340D4', primaryColorPressed: '#4535B8', primaryColorSuppl: '#644CF0',
    bodyColor: '#F7F7FB', cardColor: '#FFFFFF', textColor1: '#17142A', textColor2: '#5F587A', textColor3: '#8E87A5',
    borderColor: '#E5E1F2', inputColor: '#FFFFFF',
  },
}

export function useParentTheme() {
  const pref = localStorage.getItem('parent_theme') || 'dark'
  const systemDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? true

  const effectiveTheme = computed(() => {
    if (pref === 'system') return systemDark ? 'dark' : 'light'
    return pref
  })

  const naiveTheme = computed(() => effectiveTheme.value === 'dark' ? darkTheme : null)
  const themeOverrides = computed(() => effectiveTheme.value === 'dark' ? darkOverrides : lightOverrides)

  return { effectiveTheme, naiveTheme, themeOverrides }
}
