import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'

export default [
  {
    ignores: [
      'dist/**',
      'node_modules/**',
      'coverage/**',
      '.vite/**',
      '.vitest-cache/**',
      'public/**',
      'card-editor/_bak/**',
    ],
  },
  ...pluginVue.configs['flat/base'],
  {
    files: ['**/*.{js,mjs,cjs,vue}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.node,
        defineProps: 'readonly',
        defineEmits: 'readonly',
        defineExpose: 'readonly',
        defineModel: 'readonly',
        defineOptions: 'readonly',
        defineSlots: 'readonly',
        withDefaults: 'readonly',
      },
    },
    rules: {
      'no-undef': 'error',
    },
  },
  {
    files: ['**/*.test.{js,mjs}', '**/__tests__/**/*.{js,mjs,vue}'],
    languageOptions: {
      globals: {
        vi: 'readonly',
        describe: 'readonly',
        it: 'readonly',
        test: 'readonly',
        expect: 'readonly',
        beforeEach: 'readonly',
        afterEach: 'readonly',
        beforeAll: 'readonly',
        afterAll: 'readonly',
        suite: 'readonly',
      },
    },
  },
]
