#!/usr/bin/env python3
"""LLM 并发基准测试 — 测量实际吞吐和延迟分布。

用法：
  .venv/bin/python scripts/bench_llm_concurrency.py [--count 20] [--concurrency 10]
"""
import argparse
import asyncio
import base64
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from edu_cloud.config import settings


async def _call_gemini_ocr(client, image_bytes: bytes, idx: int) -> dict:
    """单次 Gemini OCR 调用（复用项目 GeminiClient.extract_text）。"""
    t0 = time.monotonic()
    try:
        result = await client.extract_text(image_bytes, "识别图片中的手写文字，只返回识别到的文字。如果空白返回'[空白]'。")
        elapsed = (time.monotonic() - t0) * 1000
        return {"idx": idx, "ms": elapsed, "status": "ok", "chars": len(str(result))}
    except Exception as e:
        elapsed = (time.monotonic() - t0) * 1000
        return {"idx": idx, "ms": elapsed, "status": "error", "error": str(e)[:100]}


async def _call_deepseek_grade(llm_client, image_b64: str, idx: int) -> dict:  # symbol-ok: renamed from _call_deepseek_text
    """单次 DeepSeek vision 评分调用（复用项目 LLMClient）。"""
    t0 = time.monotonic()
    try:
        prompt = ("学生答案见图片。\n"
                  "评分标准：满分3分。提到光能1分，提到CO2和H2O 1分，提到有机物和O2 1分。\n"
                  '请给出JSON格式：{"score": 分数, "confidence": 0.9, "feedback": "评语"}')
        result = await llm_client.grade_vision(image_b64, prompt, max_score=3.0)
        elapsed = (time.monotonic() - t0) * 1000
        return {"idx": idx, "ms": elapsed, "status": "ok", "chars": len(result.raw_content)}
    except Exception as e:
        elapsed = (time.monotonic() - t0) * 1000
        return {"idx": idx, "ms": elapsed, "status": "error", "error": str(e)[:100]}


def _get_sample_images(count: int) -> list[bytes]:
    """从实际扫描图获取样本（raw bytes）。"""
    import sqlite3
    db = Path(__file__).resolve().parent.parent / "edu_cloud.db"
    conn = sqlite3.connect(str(db))
    c = conn.cursor()
    c.execute("""SELECT image_path FROM student_answers
                 WHERE image_path IS NOT NULL AND image_path != ''
                 LIMIT ?""", (count * 2,))
    paths = [r[0] for r in c.fetchall()]
    conn.close()

    project = Path(__file__).resolve().parent.parent
    images = []
    for p in paths:
        full = project / p
        if full.exists() and full.stat().st_size > 0:
            with open(full, "rb") as f:
                images.append(f.read())
            if len(images) >= count:
                break
    return images


async def bench_gemini(count: int, concurrency: int):
    """Gemini OCR 并发基准（复用项目 GeminiClient）。"""
    from edu_cloud.modules.grading.gemini_client import GeminiClient

    print(f"\n{'='*60}")
    print(f"  Gemini OCR 并发测试 (count={count}, concurrency={concurrency})")
    print(f"{'='*60}")

    images = _get_sample_images(count)
    if not images:
        print("  没有可用的样本图片！")
        return
    print(f"  样本图片: {len(images)} 张 (平均 {sum(len(b) for b in images) / len(images) / 1024:.0f} KB)")

    if settings.VERTEX_AI_PROJECT:
        client = GeminiClient(
            vertex_project=settings.VERTEX_AI_PROJECT,
            vertex_location=settings.VERTEX_AI_LOCATION,
            model=settings.GEMINI_MODEL,
        )
    else:
        client = GeminiClient(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
        )

    sem = asyncio.Semaphore(concurrency)

    async def limited(img, idx):
        async with sem:
            return await _call_gemini_ocr(client, img, idx)

    wall_start = time.monotonic()
    tasks = [limited(images[i % len(images)], i) for i in range(count)]
    results = await asyncio.gather(*tasks)
    wall_elapsed = (time.monotonic() - wall_start) * 1000

    _print_results("Gemini", results, wall_elapsed, count)


async def bench_deepseek(count: int, concurrency: int):
    """DeepSeek 评分并发基准（复用 LLMClient）。"""
    from edu_cloud.modules.grading.llm_client import LLMClient

    print(f"\n{'='*60}")
    print(f"  DeepSeek 评分并发测试 (count={count}, concurrency={concurrency})")
    print(f"{'='*60}")

    if not settings.LLM_API_URL:
        print("  LLM_API_URL 未配置，跳过")
        return

    images = _get_sample_images(min(count, 10))
    if not images:
        print("  没有可用的样本图片！")
        return

    llm = LLMClient(
        api_url=settings.LLM_API_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        timeout=settings.LLM_TIMEOUT,
        max_retries=settings.LLM_MAX_RETRIES,
        slot=settings.LLM_SLOT,
    )

    sem = asyncio.Semaphore(concurrency)

    async def limited(idx):
        async with sem:
            img_b64 = base64.b64encode(images[idx % len(images)]).decode()
            return await _call_deepseek_grade(llm, img_b64, idx)

    wall_start = time.monotonic()
    tasks = [limited(i) for i in range(count)]
    results = await asyncio.gather(*tasks)
    wall_elapsed = (time.monotonic() - wall_start) * 1000

    _print_results("DeepSeek", results, wall_elapsed, count)


def _print_results(name: str, results: list[dict], wall_ms: float, count: int):
    ok = [r for r in results if r["status"] == "ok"]
    err = [r for r in results if r["status"] == "error"]
    latencies = [r["ms"] for r in ok]

    print(f"\n  [{name} 结果]")
    print(f"    成功: {len(ok)}/{count}  失败: {len(err)}/{count}")

    if err:
        print(f"    错误样本: {err[0].get('error', '?')}")

    if latencies:
        latencies.sort()
        print(f"    延迟 (ms):")
        print(f"      P50:  {latencies[len(latencies)//2]:.0f}")
        print(f"      P90:  {latencies[int(len(latencies)*0.9)]:.0f}")
        print(f"      P99:  {latencies[int(len(latencies)*0.99)]:.0f}")
        print(f"      Min:  {min(latencies):.0f}")
        print(f"      Max:  {max(latencies):.0f}")
        print(f"      Mean: {statistics.mean(latencies):.0f}")
        if len(latencies) > 1:
            print(f"      Stdev: {statistics.stdev(latencies):.0f}")
    print(f"    墙钟时间: {wall_ms:.0f}ms ({wall_ms/1000:.1f}s)")
    serial = sum(latencies) if latencies else 0
    print(f"    串行总计: {serial:.0f}ms ({serial/1000:.1f}s)")
    if wall_ms > 0:
        print(f"    有效并发: {serial / wall_ms:.1f}x")
        print(f"    吞吐量:   {len(ok) / (wall_ms/1000):.1f} req/s")

    if latencies and len(latencies) >= 5:
        print(f"\n    完成时间线 (前10个):")
        sorted_results = sorted(ok, key=lambda r: r["ms"])
        for r in sorted_results[:10]:
            bar = "█" * int(r["ms"] / max(latencies) * 40)
            print(f"      #{r['idx']:3d}: {r['ms']:7.0f}ms {bar}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=20, help="总请求数")
    parser.add_argument("--concurrency", type=int, default=10, help="并发数")
    parser.add_argument("--target", choices=["gemini", "deepseek", "both"], default="gemini")
    args = parser.parse_args()

    print(f"LLM 并发基准测试")
    print(f"  Gemini model: {settings.GEMINI_MODEL}")
    print(f"  Vertex AI: {settings.VERTEX_AI_PROJECT or 'N/A'}")
    print(f"  DeepSeek: {settings.LLM_API_URL or 'N/A'}")
    print(f"  当前 GRADING_BATCH_SIZE: {settings.GRADING_BATCH_SIZE}")

    if args.target in ("gemini", "both"):
        await bench_gemini(args.count, args.concurrency)
    if args.target in ("deepseek", "both"):
        await bench_deepseek(args.count, args.concurrency)


if __name__ == "__main__":
    asyncio.run(main())
