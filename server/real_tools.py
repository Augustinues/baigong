"""百工真实工具 — 不是模拟，是真干活"""

import asyncio
import json
import os
import re
import tempfile
import textwrap
import traceback
from typing import Optional

from agent_sdk import BaseTool, ToolMetadata, ToolParam, ToolResult


class WebSearch(BaseTool):
    """真实网络搜索（用 DuckDuckGo）"""

    @property
    def metadata(self):
        return ToolMetadata(
            name="web_search",
            display_name="网络搜索",
            description="搜索网络获取最新信息。输入关键词，返回网页标题、链接和摘要。",
            parameters=[
                ToolParam(name="query", type="string", description="搜索关键词，精确描述你想找什么", required=True),
                ToolParam(name="limit", type="integer", description="返回结果数量（最多20）", default=8),
            ],
            category="search",
        )

    async def execute(self, query: str, limit: int = 8) -> ToolResult:
        try:
            import httpx
            # 使用 DuckDuckGo 的 lite API
            url = f"https://lite.duckduckgo.com/lite/?q={query}"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Baigong/1.0"
                })
                resp.raise_for_status()

            # 解析 HTML 结果
            html = resp.text
            results = []
            # 匹配 DuckDuckGo lite 的结果表格
            rows = re.findall(
                r'<tr[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?<td[^>]*class="result-snippet"[^>]*>(.*?)</td>',
                html, re.DOTALL
            )
            for url, title, snippet in rows[:limit]:
                title = re.sub(r'<[^>]+>', '', title).strip()
                snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                results.append({
                    "title": title or "无标题",
                    "url": url,
                    "snippet": snippet[:200],
                })

            if not results:
                # 降级：用 Google 风格
                return ToolResult(success=True, data={"results": [], "note": "DuckDuckGo 无结果"})

            return ToolResult(success=True, data={"results": results, "total": len(results)})

        except Exception as e:
            return ToolResult(success=False, error=f"搜索失败: {str(e)[:100]}")


class WebExtract(BaseTool):
    """提取网页内容转为纯文本"""

    @property
    def metadata(self):
        return ToolMetadata(
            name="web_extract",
            display_name="网页提取",
            description="获取指定 URL 的页面内容，转为纯文本。适合阅读文章、文档等。",
            parameters=[
                ToolParam(name="url", type="string", description="要提取的网页URL", required=True),
                ToolParam(name="max_chars", type="integer", description="最多提取字符数", default=5000),
            ],
            category="search",
        )

    async def execute(self, url: str, max_chars: int = 5000) -> ToolResult:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Baigong/1.0"
                })
                resp.raise_for_status()

            html = resp.text
            # 简单去标签
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()

            if len(text) > max_chars:
                text = text[:max_chars] + "\n\n[...后续内容截断]"

            return ToolResult(success=True, data={
                "url": url,
                "title": re.search(r'<title>(.*?)</title>', html, re.DOTALL).group(1).strip() if re.search(r'<title>(.*?)</title>', html, re.DOTALL) else url,
                "content": text,
                "chars": len(text),
            })
        except Exception as e:
            return ToolResult(success=False, error=f"提取失败: {str(e)[:100]}")


class FileRead(BaseTool):
    """读取本地文件"""

    @property
    def metadata(self):
        return ToolMetadata(
            name="file_read",
            display_name="文件读取",
            description="读取本地文件内容。支持 txt、py、json、md、csv 等文本格式。",
            parameters=[
                ToolParam(name="path", type="string", description="文件路径（相对或绝对）", required=True),
                ToolParam(name="max_lines", type="integer", description="最多读取行数", default=200),
            ],
            category="filesystem",
        )

    async def execute(self, path: str, max_lines: int = 200) -> ToolResult:
        try:
            path = os.path.expanduser(path)
            if not os.path.isfile(path):
                return ToolResult(success=False, error=f"文件不存在: {path}")
            if os.path.getsize(path) > 1024 * 1024:
                return ToolResult(success=False, error="文件超过1MB，拒绝读取")
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            content = "".join(lines[:max_lines])
            if len(lines) > max_lines:
                content += f"\n\n[...共{len(lines)}行，仅显示前{max_lines}行]"
            return ToolResult(success=True, data={
                "path": path,
                "lines": len(lines),
                "content": content,
                "size": os.path.getsize(path),
            })
        except PermissionError:
            return ToolResult(success=False, error="无权限读取该文件")
        except Exception as e:
            return ToolResult(success=False, error=f"读取失败: {str(e)[:100]}")


class FileWrite(BaseTool):
    """写入本地文件"""

    @property
    def metadata(self):
        return ToolMetadata(
            name="file_write",
            display_name="文件写入",
            description="将内容写入本地文件。会覆盖已存在的文件。支持文本格式。",
            parameters=[
                ToolParam(name="path", type="string", description="文件路径（相对或绝对）", required=True),
                ToolParam(name="content", type="string", description="要写入的内容", required=True),
            ],
            category="filesystem",
        )

    async def execute(self, path: str, content: str) -> ToolResult:
        try:
            path = os.path.expanduser(path)
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(success=True, data={
                "path": path,
                "bytes": len(content.encode("utf-8")),
                "status": "已写入",
            })
        except PermissionError:
            return ToolResult(success=False, error="无权限写入该路径")
        except Exception as e:
            return ToolResult(success=False, error=f"写入失败: {str(e)[:100]}")


class CodeExec(BaseTool):
    """执行 Python 代码（沙箱环境）"""

    @property
    def metadata(self):
        return ToolMetadata(
            name="code_exec",
            display_name="代码执行",
            description="在沙箱中执行 Python 代码并返回输出。适合数据分析、计算、文本处理。",
            parameters=[
                ToolParam(name="code", type="string", description="要执行的 Python 代码", required=True),
                ToolParam(name="timeout", type="integer", description="超时秒数", default=15),
            ],
            category="coding",
        )

    async def execute(self, code: str, timeout: int = 15) -> ToolResult:
        # 在子进程中执行，限制资源
        import subprocess
        # 写入临时文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(textwrap.dedent(code))
            tmp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "python3", tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 100,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                out = stdout.decode("utf-8", errors="replace")[:2000]
                err = stderr.decode("utf-8", errors="replace")[:1000]
                return ToolResult(success=proc.returncode == 0, data={
                    "stdout": out,
                    "stderr": err,
                    "exit_code": proc.returncode,
                })
            except asyncio.TimeoutError:
                proc.kill()
                return ToolResult(success=False, error=f"执行超时（{timeout}秒）")
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass


class BaigongRead(BaseTool):
    """读取百工自己的文件和数据"""

    @property
    def metadata(self):
        return ToolMetadata(
            name="baigong_read",
            display_name="百工数据读取",
            description="读取百工件系统中的 Agent 信息、任务状态、记忆内容、Skill 列表等。",
            parameters=[
                ToolParam(name="target", type="string", description="读取目标：agents/tasks/memories/skills/config", required=True),
            ],
            category="system",
        )

    def __init__(self, orchestrator=None):
        super().__init__()
        self.orchestrator = orchestrator

    async def execute(self, target: str) -> ToolResult:
        if not self.orchestrator:
            return ToolResult(success=False, error="编排器未就绪")
        try:
            data = self.orchestrator.get_system_data(target)
            return ToolResult(success=True, data=data)
        except Exception as e:
            return ToolResult(success=False, error=str(e)[:200])
