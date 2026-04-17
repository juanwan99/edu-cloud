"""HTML 答题卡 → PDF 导出 + skeleton JSON 提取（playwright sync API + 线程池）。

Windows + uvicorn --reload 会把事件循环切为 SelectorEventLoop（不支持 subprocess）。
解决方案：使用 playwright sync API 在线程池中执行，启动前确保 ProactorEventLoopPolicy。
浏览器实例在进程生命周期内复用，避免每次请求冷启动 Chromium。
"""
from __future__ import annotations

import asyncio
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

from playwright.sync_api import sync_playwright, Playwright, Browser

logger = logging.getLogger(__name__)

# 进程级浏览器单例（线程安全）
_playwright: Playwright | None = None
_browser: Browser | None = None
_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pw")


def _get_browser() -> Browser:
    """获取或创建共享浏览器实例（同步，线程安全）。"""
    global _playwright, _browser
    with _lock:
        if _browser and _browser.is_connected():
            return _browser
        if _playwright is None:
            # uvicorn --reload 在 Windows 上设置 WindowsSelectorEventLoopPolicy，
            # playwright 内部需要 ProactorEventLoop 来创建子进程。
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                asyncio.set_event_loop(asyncio.ProactorEventLoop())
            _playwright = sync_playwright().start()
        # headless Linux/WSL/容器标准参数组：禁 GPU + 禁 sandbox + 禁 /dev/shm 依赖
        # --single-process：合并所有子进程，避免 WSL 某些内核下 zygote/GPU 子进程 spawn 失败
        # （答题卡只做一次性 HTML→PDF 渲染，无持久会话，单进程影响可接受）
        _browser = _playwright.chromium.launch(args=[
            "--disable-gpu",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-software-rasterizer",
            "--single-process",
        ])
        logger.info("playwright browser launched (shared instance)")
        return _browser


def _html_to_pdf_sync(html_content: str, paper_size: str) -> bytes:
    """同步版本，在线程池中执行。"""
    if paper_size == "A3":
        width_px, height_px = 1587, 1123
    else:
        width_px, height_px = 794, 1123

    browser = _get_browser()
    page = browser.new_page(viewport={"width": width_px, "height": height_px})
    try:
        page.set_content(html_content, wait_until="networkidle")
        page.wait_for_timeout(300)
        pdf_bytes = page.pdf(
            width=f"{420 if paper_size == 'A3' else 210}mm",
            height="297mm",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        logger.info("html_to_pdf: paper=%s, viewport=%dx%d, pdf=%d bytes",
                     paper_size, width_px, height_px, len(pdf_bytes))
        return pdf_bytes
    finally:
        page.close()


async def html_to_pdf(html_content: str, paper_size: str = "A3") -> bytes:
    """将答题卡 HTML 渲染为 PDF。

    A3 横向 = 420mm × 297mm = 1587 × 1123 px (96dpi)
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, _html_to_pdf_sync, html_content, paper_size
    )


def _extract_skeleton_sync(html_content: str) -> dict:
    """同步版本，在线程池中执行。"""
    browser = _get_browser()
    page = browser.new_page()
    try:
        page.set_content(html_content, wait_until="networkidle")
        skeleton = page.evaluate(
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
        logger.info(
            "extract_skeleton: regions=%d, page=%dx%d",
            len(skeleton.get("regions", [])),
            skeleton.get("pageWidth", 0),
            skeleton.get("pageHeight", 0),
        )
        return skeleton
    finally:
        page.close()


async def extract_skeleton(html_content: str) -> dict:
    """从 HTML DOM 提取各区域坐标，生成 skeleton JSON。"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, _extract_skeleton_sync, html_content
    )
