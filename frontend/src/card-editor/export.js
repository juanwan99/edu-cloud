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
        const html = getCleanHTML();
        const resp = await fetch('/api/card/export/pdf', {
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
        const html = getCleanHTML();
        const resp = await fetch('/api/card/export/skeleton', {
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

function getCleanHTML() {
  const pages = document.querySelectorAll('.page');
  let pagesHTML = '';

  for (let pi = 0; pi < pages.length; pi++) {
    const page = pages[pi];
    const clone = page.cloneNode(true);

    // 移除交互层元素
    clone.querySelectorAll('.divider-handle, .divider-gap, .ctx-menu').forEach(el => el.remove());
    clone.querySelectorAll('.region-selected').forEach(el => el.classList.remove('region-selected'));

    // 移除编辑器 transform 缩放
    clone.style.transform = '';

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

  // 提取样式表内容（只要答题卡相关的，排除编辑器 UI）
  let styleContent = '';
  for (const sheet of document.styleSheets) {
    try {
      if (sheet.href && sheet.href.includes('styles.css')) {
        const rules = Array.from(sheet.cssRules).map(r => r.cssText).join('\n');
        styleContent = rules;
      }
    } catch (e) { /* 跨域 */ }
  }

  // 导出 HTML：覆盖 body 样式为打印友好
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
${styleContent}
/* 导出覆盖：去除编辑器 UI 样式 */
body {
  font-family: SimSun, "宋体", serif;
  background: white !important;
  color: #000 !important;
  display: block !important;
  height: auto !important;
  overflow: visible !important;
  margin: 0; padding: 0;
}
.panel, .preview-wrap, .status, .page-label, .ctx-menu,
.divider-handle, .divider-gap { display: none !important; }
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
  const html = getCleanHTML();
  const paperSize = getCurrentPaperSize();
  const headers = getAuthHeaders();

  // Step 1: Export PDF
  const pdfResp = await fetch('/api/card/export/pdf', {
    method: 'POST', headers,
    body: JSON.stringify({ html, paper_size: paperSize }),
  });
  if (!pdfResp.ok) throw new Error(`PDF 导出失败: HTTP ${pdfResp.status}`);
  const pdfBlob = await pdfResp.blob();

  // Step 2: Extract skeleton
  const skelResp = await fetch('/api/card/export/skeleton', {
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
  const tplResp = await fetch(`/api/templates/${subjectId}/A`, {
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
