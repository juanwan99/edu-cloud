"""HTML 答题卡 → PDF 导出 + skeleton JSON 提取（playwright）。"""
from __future__ import annotations

import logging

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


async def html_to_pdf(html_content: str, paper_size: str = "A3") -> bytes:
    """将答题卡 HTML 渲染为 PDF。

    A3 横向 = 420mm × 297mm = 1587 × 1123 px (96dpi)
    """
    # A3 横向的像素尺寸（96dpi）
    if paper_size == "A3":
        width_px, height_px = 1587, 1123
    else:
        width_px, height_px = 794, 1123  # A4 纵向

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": width_px, "height": height_px})
        await page.set_content(html_content, wait_until="networkidle")
        # 等待字体和布局稳定
        await page.wait_for_timeout(500)
        pdf_bytes = await page.pdf(
            width=f"{420 if paper_size == 'A3' else 210}mm",
            height=f"{297 if paper_size == 'A3' else 297}mm",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        await browser.close()
        logger.info("html_to_pdf: paper=%s, viewport=%dx%d, pdf=%d bytes",
                     paper_size, width_px, height_px, len(pdf_bytes))
        return pdf_bytes


async def extract_skeleton(html_content: str) -> dict:
    """从 HTML DOM 提取各区域坐标，生成 skeleton JSON。"""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html_content, wait_until="networkidle")
        skeleton = await page.evaluate(
            """() => {
            const regions = [];
            document.querySelectorAll('[data-region-id]').forEach(el => {
                const rect = el.getBoundingClientRect();
                regions.push({
                    id: el.dataset.regionId,
                    type: el.dataset.regionType,
                    qno: parseInt(el.dataset.qno) || 0,
                    rect: {
                        x1: Math.round(rect.left),
                        y1: Math.round(rect.top),
                        x2: Math.round(rect.right),
                        y2: Math.round(rect.bottom),
                    },
                    side: el.closest('[data-side]')?.dataset.side || 'A',
                });
            });
            return {
                regions,
                pageWidth: document.body.scrollWidth,
                pageHeight: document.body.scrollHeight,
            };
        }"""
        )
        await browser.close()
        logger.info(
            "extract_skeleton: regions=%d, page=%dx%d",
            len(skeleton.get("regions", [])),
            skeleton.get("pageWidth", 0),
            skeleton.get("pageHeight", 0),
        )
        return skeleton
