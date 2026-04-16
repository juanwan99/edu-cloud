import client from './client'

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
