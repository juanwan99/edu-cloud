import client from './client'

export const generateBarcode = (file, barcodeColumn = '准考证号', nameColumn = '姓名') => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('barcode_column', barcodeColumn)
  formData.append('name_column', nameColumn)
  return client.post('/card/barcode', formData, {
    responseType: 'blob',
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// --- 解析答案（返回 JSON，不生成 PDF）---
export const parseAnswers = (file, subjectId, examId, options = {}) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('subject_id', subjectId)
  formData.append('exam_id', examId)
  if (options.total_score) formData.append('total_score', options.total_score)
  if (options.paper_size) formData.append('paper_size', options.paper_size)
  if (options.sides) formData.append('sides', options.sides)
  return client.post('/card/parse-answers', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })
}

// --- 权重预览（返回 PDF）---
export const previewByWeights = (data) =>
  client.post('/card/preview-by-weights', data, { responseType: 'blob' })

export const generateCardV2 = (data) =>
  client.post('/card/generate/v2', data, { responseType: 'blob' })
export const renderDocPages = (formData) =>
  client.post('/card/render-doc-pages', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
