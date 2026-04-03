// export.js — PDF 和 skeleton JSON 导出

function getAuthHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  const token = localStorage.getItem('token');
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

function getCurrentPaperSize() {
  return window._getValues?.()?.paperSize || 'A3';
}

export function initExport() {
  const btnPdf = document.getElementById('btnExportPdf');
  const btnSkeleton = document.getElementById('btnExportSkeleton');
  const status = document.getElementById('status');

  if (btnPdf) {
    btnPdf.onclick = async () => {
      btnPdf.disabled = true;
      btnPdf.textContent = '导出中...';
      try {
        const html = await getCleanHTML();
        const resp = await fetch('/api/v1/card/export/pdf', {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({ html, paper_size: getCurrentPaperSize() }),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const blob = await resp.blob();
        downloadBlob(blob, '答题卡.pdf');
        status.textContent = 'PDF 导出成功';
        status.className = 'status';
      } catch (e) {
        status.textContent = '导出失败: ' + e.message;
        status.className = 'status error';
      } finally {
        btnPdf.disabled = false;
        btnPdf.textContent = '导出 PDF';
      }
    };
  }

  if (btnSkeleton) {
    btnSkeleton.onclick = async () => {
      btnSkeleton.disabled = true;
      btnSkeleton.textContent = '提取中...';
      try {
        const html = await getCleanHTML();
        const resp = await fetch('/api/v1/card/export/skeleton', {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({ html, paper_size: getCurrentPaperSize() }),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();
        const blob = new Blob([JSON.stringify(json, null, 2)], { type: 'application/json' });
        downloadBlob(blob, 'skeleton.json');
        status.textContent = 'Skeleton 导出成功';
        status.className = 'status';
      } catch (e) {
        status.textContent = '导出失败: ' + e.message;
        status.className = 'status error';
      } finally {
        btnSkeleton.disabled = false;
        btnSkeleton.textContent = '导出 Skeleton JSON';
      }
    };
  }
}

let _cachedStyleCSS = null;

async function fetchStyleCSS() {
  if (_cachedStyleCSS) return _cachedStyleCSS;
  try {
    const resp = await fetch('/card-editor/styles.css');
    if (resp.ok) {
      _cachedStyleCSS = await resp.text();
      return _cachedStyleCSS;
    }
  } catch { /* fetch 失败，降级 */ }
  // fallback: 运行时扫描 document.styleSheets
  for (const sheet of document.styleSheets) {
    try {
      if (sheet.href && sheet.href.includes('styles.css')) {
        return Array.from(sheet.cssRules).map(r => r.cssText).join('\n');
      }
    } catch { /* 跨域 */ }
  }
  return '';
}

async function getCleanHTML() {
  const pages = document.querySelectorAll('.page');
  let pagesHTML = '';

  for (let pi = 0; pi < pages.length; pi++) {
    const page = pages[pi];
    const clone = page.cloneNode(true);

    // 移除交互层 + 编辑器占位元素
    clone.querySelectorAll('.divider-handle, .divider-gap, .ctx-menu, .empty-col-slot, .sub-del-btn, .cut-del-btn, .add-sub-hint, .img-del-btn').forEach(el => el.remove());
    clone.querySelectorAll('.region-selected').forEach(el => el.classList.remove('region-selected'));

    // 移除编辑器 transform 缩放和 marginBottom
    clone.style.transform = '';
    clone.style.marginBottom = '';

    // 复制 CSS 变量（从原始 page 元素的 style）
    const computed = page.style;
    for (let i = 0; i < computed.length; i++) {
      const prop = computed[i];
      if (prop.startsWith('--')) {
        clone.style.setProperty(prop, computed.getPropertyValue(prop));
      }
    }

    // 每个 page 用分页标记包裹
    if (pi > 0) {
      pagesHTML += '<div style="page-break-before:always;"></div>';
    }
    pagesHTML += clone.outerHTML;
  }

  // CSS 获取：优先 fetch，fallback 到 document.styleSheets
  const styleContent = await fetchStyleCSS();

  // 导出 HTML：覆盖 body 样式为打印友好
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
${styleContent}
/* 导出覆盖：去除编辑器 UI 样式 */
body {
  font-family: SimSun, "宋体", "Noto Serif CJK SC", serif;
  background: white !important;
  color: #000 !important;
  display: block !important;
  height: auto !important;
  overflow: visible !important;
  margin: 0; padding: 0;
}
.panel, .preview-wrap, .status, .page-label, .ctx-menu,
.divider-handle, .divider-gap, .empty-col-slot,
.sub-del-btn, .cut-del-btn, .add-sub-hint, .img-del-btn { display: none !important; }
.page {
  background: white !important;
  box-shadow: none !important;
  margin: 0 !important;
}
@page { margin: 0; }
</style>
</head>
<body>${pagesHTML}</body>
</html>`;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * 发布答题卡：导出 PDF + 提取 skeleton + 写入 Template 表
 * @param {string} subjectId - 科目 ID
 * @param {string} filename - PDF 文件名
 * @returns {Promise<{pdf: Blob, skeleton: object}>}
 */
export async function publishCard(subjectId, filename = '答题卡.pdf') {
  const html = await getCleanHTML();
  const paperSize = getCurrentPaperSize();
  const headers = getAuthHeaders();

  // Step 1: Export PDF
  const pdfResp = await fetch('/api/v1/card/export/pdf', {
    method: 'POST', headers,
    body: JSON.stringify({ html, paper_size: paperSize }),
  });
  if (!pdfResp.ok) throw new Error(`PDF 导出失败: HTTP ${pdfResp.status}`);
  const pdfBlob = await pdfResp.blob();

  // Step 2: Extract skeleton
  const skelResp = await fetch('/api/v1/card/export/skeleton', {
    method: 'POST', headers,
    body: JSON.stringify({ html, paper_size: paperSize }),
  });
  if (!skelResp.ok) throw new Error(`Skeleton 提取失败: HTTP ${skelResp.status}`);
  const skeleton = await skelResp.json();

  // Step 3: Write Template (A side and B side)
  const templateData = {
    image_width: skeleton.image_width || 4960,
    image_height: skeleton.image_height || 3508,
    anchors: skeleton.anchors || [],
    regions: skeleton.regions || [],
  };
  const tplResp = await fetch(`/api/v1/templates/${subjectId}/A`, {
    method: 'PUT', headers,
    body: JSON.stringify(templateData),
  });
  if (!tplResp.ok) throw new Error(`Template 写入失败: HTTP ${tplResp.status}`);

  // Download PDF
  downloadBlob(pdfBlob, filename);

  return { pdf: pdfBlob, skeleton };
}

// Expose getCleanHTML for external use
export { getCleanHTML };

/**
 * 批量导出所有科目的答题卡 PDF。
 * 在隐藏容器中逐科渲染布局 → 生成 HTML → 调用后端 PDF 接口 → 触发下载。
 * @param {Array} subjects - [{id, name, code}, ...]
 * @param {string} examTitle - 考试名称（用于答题卡标题）
 * @param {function} onProgress - (current, total, subjectName) => void
 */
export async function batchExportPdf(subjects, examTitle = '', onProgress = null) {
  const { renderFromLayout, applyCSSToPage } = await import('@/card-editor/render.js')
  const headers = getAuthHeaders()

  // 创建隐藏渲染容器（宽度按科目纸型动态设置）
  const container = document.createElement('div')
  container.style.cssText = 'position:fixed;left:-9999px;top:0;'
  document.body.appendChild(container)

  // 确保 styles.css 已加载
  if (!document.getElementById('card-editor-styles')) {
    const link = document.createElement('link')
    link.id = 'card-editor-styles'
    link.rel = 'stylesheet'
    link.href = '/card-editor/styles.css'
    document.head.appendChild(link)
    await new Promise(r => { link.onload = r; setTimeout(r, 1000) })
  }

  const results = []

  for (let i = 0; i < subjects.length; i++) {
    const subj = subjects[i]
    if (onProgress) onProgress(i + 1, subjects.length, subj.name)

    try {
      // 1. 加载科目布局
      const resp = await fetch(`/api/v1/card/editor-layout/${subj.id}`, { headers })
      if (!resp.ok) { results.push({ name: subj.name, error: `HTTP ${resp.status}` }); continue }
      const data = await resp.json()
      if (!data.found || !data.layout) { results.push({ name: subj.name, error: '无布局数据' }); continue }

      const layout = data.layout
      const config = { ...layout.config, ...(data.config || {}), examTitle, subjectTitle: subj.name }
      layout.config = config
      const paperSize = layout.paper || config.paperSize || 'A3'

      // 2. 在隐藏容器中渲染（宽度匹配纸型）
      container.style.width = paperSize === 'A4' ? '210mm' : '420mm'
      const previewWrap = document.createElement('div')
      container.appendChild(previewWrap)
      renderFromLayout(previewWrap, layout, config)

      // 3. 提取干净 HTML（复用 getCleanHTML 逻辑）
      const pages = previewWrap.querySelectorAll('.page')
      let pagesHTML = ''
      for (let pi = 0; pi < pages.length; pi++) {
        const clone = pages[pi].cloneNode(true)
        clone.querySelectorAll('.divider-handle, .divider-gap, .ctx-menu, .empty-col-slot, .sub-del-btn, .cut-del-btn, .add-sub-hint, .img-del-btn').forEach(el => el.remove())
        clone.querySelectorAll('.region-selected').forEach(el => el.classList.remove('region-selected'))
        clone.style.transform = ''
        clone.style.marginBottom = ''
        // 复制 CSS 变量
        const orig = pages[pi]
        for (let si = 0; si < orig.style.length; si++) {
          const prop = orig.style[si]
          if (prop.startsWith('--')) clone.style.setProperty(prop, orig.style.getPropertyValue(prop))
        }
        if (pi > 0) pagesHTML += '<div style="page-break-before:always;"></div>'
        pagesHTML += clone.outerHTML
      }

      // 提取样式表（复用 fetchStyleCSS）
      const styleContent = await fetchStyleCSS()

      const fullHTML = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><style>
${styleContent}
body { font-family: SimSun, "宋体", "Noto Serif CJK SC", serif; background: white !important; color: #000 !important; margin: 0; padding: 0; }
.panel, .preview-wrap, .status, .page-label, .ctx-menu, .divider-handle, .divider-gap, .empty-col-slot, .sub-del-btn, .cut-del-btn, .add-sub-hint, .img-del-btn { display: none !important; }
.page { background: white !important; box-shadow: none !important; margin: 0 !important; }
@page { margin: 0; }
</style></head><body>${pagesHTML}</body></html>`

      // 4. 调用后端 PDF 接口
      const pdfResp = await fetch('/api/v1/card/export/pdf', {
        method: 'POST', headers,
        body: JSON.stringify({ html: fullHTML, paper_size: paperSize }),
      })
      if (!pdfResp.ok) { results.push({ name: subj.name, error: `PDF 导出失败 HTTP ${pdfResp.status}` }); continue }

      const blob = await pdfResp.blob()
      downloadBlob(blob, `答题卡_${subj.name}.pdf`)
      results.push({ name: subj.name, ok: true })

      // 清理渲染容器
      container.removeChild(previewWrap)

      // 间隔 300ms 避免浏览器下载限制
      await new Promise(r => setTimeout(r, 300))
    } catch (e) {
      results.push({ name: subj.name, error: e.message })
    }
  }

  document.body.removeChild(container)
  return results
}
