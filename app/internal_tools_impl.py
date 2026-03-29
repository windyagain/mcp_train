import base64
from pathlib import Path
from typing import Optional

import httpx

async def tool_get_weather(city: str, date: Optional[str] = None) -> str:
    """
    基于 wttr.in 的实时天气查询，忽略具体日期，只按城市查当前天气。
    等价于: curl "https://wttr.in/Beijing?format=3"
    """
    city = city or "Beijing"
    url = f"https://wttr.in/{city}?format=3"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text.strip()
    if date:
        return f"{date} {city} 天气（wttr.in）：{text}"
    return f"{city} 当前天气（wttr.in）：{text}"


async def tool_http_get_text(url: str, max_chars: int = 2000) -> str:
    """
    通用 HTTP GET 文本工具：抓取 URL 文本内容，并按 max_chars 截断。
    """
    if not url:
        return "缺少必填参数 url"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text
    if len(text) > max_chars:
        text = text[:max_chars] + f"... (截断，原始长度 {len(text)} 字符)"
    return text


async def tool_browser_screenshot(
    url: str, width: int = 1280, height: int = 720
) -> str:
    """
    使用 Playwright 截图并将 PNG 保存到 static/screenshots，返回相对 URL。
    """
    if not url:
        return "缺少必填参数 url"

    try:
        from playwright.async_api import async_playwright
    except Exception:
        return "browser_screenshot 依赖 Playwright，请先安装 playwright 并执行 python -m playwright install"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": width, "height": height})
            await page.goto(url, wait_until="networkidle", timeout=30000)
            png_bytes = await page.screenshot(full_page=True)
        finally:
            await browser.close()

    base_dir = Path(__file__).resolve().parent.parent
    screenshots_dir = base_dir / "static" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # 用简单的 hash+长度 生成文件名，避免额外依赖
    digest = base64.urlsafe_b64encode(png_bytes[:16]).decode("ascii").rstrip("=")
    filename = f"{digest}.png"
    file_path = screenshots_dir / filename
    file_path.write_bytes(png_bytes)

    return f"/static/screenshots/{filename}"



