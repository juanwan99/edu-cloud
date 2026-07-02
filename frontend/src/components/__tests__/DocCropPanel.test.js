import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../DocCropPanel.vue')
const content = readFileSync(filePath, 'utf-8')

const mocks = vi.hoisted(() => ({
  getDocPages: vi.fn(),
  renderDocPages: vi.fn(),
  clientGet: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
  messageInfo: vi.fn(),
}))

vi.mock('../../api/cards', () => ({
  getDocPages: (...args) => mocks.getDocPages(...args),
  renderDocPages: (...args) => mocks.renderDocPages(...args),
}))

vi.mock('../../api/client', () => ({
  default: { get: (...args) => mocks.clientGet(...args) },
}))

vi.mock('naive-ui', () => {
  const passthrough = (name) => ({
    name,
    template: '<div><slot /><slot name="trigger" /></div>',
  })

  return {
    useMessage: () => ({
      error: mocks.messageError,
      success: mocks.messageSuccess,
      warning: mocks.messageWarning,
      info: mocks.messageInfo,
    }),
    NModal: {
      name: 'NModal',
      props: ['show'],
      emits: ['update:show'],
      template: '<div v-if="show"><slot /></div>',
    },
    NButton: {
      name: 'NButton',
      props: ['disabled', 'loading', 'quaternary', 'size', 'text', 'type'],
      emits: ['click'],
      template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
    },
    NButtonGroup: passthrough('NButtonGroup'),
    NDivider: passthrough('NDivider'),
    NInput: passthrough('NInput'),
    NInputNumber: passthrough('NInputNumber'),
    NSelect: passthrough('NSelect'),
    NUpload: passthrough('NUpload'),
  }
})

function resetMocks() {
  for (const mock of Object.values(mocks)) {
    mock.mockReset()
  }
  mocks.getDocPages.mockResolvedValue({ data: { pages: [] } })
  mocks.clientGet.mockResolvedValue({ data: new Blob(['image']) })
  mocks.renderDocPages.mockResolvedValue({ data: { pages: [] } })
}

async function mountPanel(props = {}) {
  const mod = await import('../DocCropPanel.vue')
  const wrapper = mount(mod.default, {
    props: {
      show: false,
      subjectId: 'subject-1',
      questions: [],
      ...props,
    },
  })
  await wrapper.setProps({ show: true })
  await flushPromises()
  await wrapper.vm.$nextTick()
  return wrapper
}

describe('DocCropPanel fail-visible behavior', () => {
  beforeEach(() => {
    resetMocks()
    localStorage.clear()
    global.URL.createObjectURL = vi.fn(() => 'blob:page')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows an error when existing document pages fail to load', async () => {
    mocks.getDocPages.mockRejectedValueOnce(new Error('pages down'))

    await mountPanel()

    expect(mocks.getDocPages).toHaveBeenCalledWith('subject-1')
    expect(mocks.messageError).toHaveBeenCalledWith(expect.stringContaining('pages down'))
  })

  it('keeps original page URLs and warns when a page preview image fails to load', async () => {
    mocks.getDocPages.mockResolvedValueOnce({
      data: { pages: [{ image_url: 'stored/page.png', width: 100, height: 100 }] },
    })
    mocks.clientGet.mockRejectedValueOnce(new Error('blob unavailable'))

    const wrapper = await mountPanel()

    expect(mocks.clientGet).toHaveBeenCalledWith('/card/doc-page-image', expect.objectContaining({
      params: { path: 'stored/page.png' },
      responseType: 'blob',
    }))
    expect(wrapper.vm.pages[0].image_url).toBe('stored/page.png')
    expect(mocks.messageWarning).toHaveBeenCalledWith(expect.stringContaining('previews could not be loaded'))
  })

  it('warns and clears corrupt saved crop drafts instead of silently ignoring them', async () => {
    localStorage.setItem('doc-crop-subject-1', '{bad json')
    const removeSpy = vi.spyOn(Storage.prototype, 'removeItem')

    await mountPanel()

    expect(removeSpy).toHaveBeenCalledWith('doc-crop-subject-1')
    expect(mocks.messageWarning).toHaveBeenCalledWith(expect.stringContaining('could not be restored'))
  })
})

describe('DocCropPanel source error handling', () => {
  it('does not leave document-page and local-draft failures as empty catches', () => {
    expect(content).not.toContain('catch {}')

    const loadExistingPages = content.slice(
      content.indexOf('async function loadExistingPages'),
      content.indexOf('const storageKey')
    )
    expect(loadExistingPages).toContain('message.error(withDetail(DOC_PAGES_LOAD_ERROR, e))')
    expect(loadExistingPages).toContain('message.warning(DOC_PAGE_IMAGE_WARNING)')

    const saveDraft = content.slice(
      content.indexOf('function saveCropsToStorage'),
      content.indexOf('function restoreCrops')
    )
    expect(saveDraft).toContain('message.warning(withDetail(DRAFT_SAVE_WARNING, e))')

    const restoreDraft = content.slice(
      content.indexOf('function restoreCrops'),
      content.indexOf('async function handleUpload')
    )
    expect(restoreDraft).toContain('localStorage.removeItem(storageKey.value)')
    expect(restoreDraft).toContain('message.warning(withDetail(DRAFT_RESTORE_WARNING, e))')

    const saveHandler = content.slice(
      content.indexOf('async function handleSave'),
      content.indexOf('</script>')
    )
    expect(saveHandler).toContain('message.warning(withDetail(DRAFT_CLEAR_WARNING, e))')
  })
})
