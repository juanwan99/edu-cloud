import client from './client'

export const uploadScanFolder = (examId, files, onProgress) => {
  const BATCH = 50
  let uploaded = 0
  const total = files.length

  return (async () => {
    let dirPath = null
    for (let i = 0; i < files.length; i += BATCH) {
      const batch = files.slice(i, i + BATCH)
      const form = new FormData()
      form.append('exam_id', examId)
      for (const f of batch) {
        form.append('files', f, f.webkitRelativePath || f.name)
      }
      const res = await client.post('/scan/pipeline/upload-folder', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000,
      })
      dirPath = res.data.dir_path
      uploaded += batch.length
      if (onProgress) onProgress(uploaded, total)
    }
    return { data: { dir_path: dirPath, total: uploaded } }
  })()
}

export const scanDirectory = (dirPath) =>
  client.post('/scan/pipeline/scan-dir', { dir_path: dirPath })

export const startPipeline = (subjectId, side, imageDir, tplPath = null) =>
  client.post('/scan/pipeline/start', {
    subject_id: subjectId,
    side,
    image_dir: imageDir,
    tpl_path: tplPath,
  })

export const getPipelineProgress = () =>
  client.get('/scan/pipeline/progress')

export const stopPipeline = () =>
  client.post('/scan/pipeline/stop')

export const previewScan = (imagePath, imageDir, subjectId, side) =>
  client.post('/scan/pipeline/preview', {
    image_path: imagePath,
    image_dir: imageDir,
    subject_id: subjectId,
    side,
  })

export const importTpl = (tplPath, subjectId, side) =>
  client.post('/scan/pipeline/import-tpl', {
    tpl_path: tplPath,
    subject_id: subjectId,
    side,
  })

export const autoDetectCV = (imagePath, { minAreaRatio = 0.008, skipLlm = false, priorRegions = null } = {}) =>
  client.post('/scan/pipeline/auto-detect-cv', {
    image_path: imagePath,
    min_area_ratio: minAreaRatio,
    skip_llm: skipLlm,
    ...(priorRegions ? { prior_regions: priorRegions } : {}),
  }, { timeout: 180000 })

export const fetchScanImageBlob = (path) =>
  client.get('/scan/pipeline/scan-image', {
    params: { path },
    responseType: 'blob',
    timeout: 30000,
  }).then(res => URL.createObjectURL(res.data))

export const saveCVTemplate = (subjectId, side, regions, width, height) =>
  client.post('/scan/pipeline/save-cv-template', {
    subject_id: subjectId,
    side,
    regions,
    width,
    height,
  })
