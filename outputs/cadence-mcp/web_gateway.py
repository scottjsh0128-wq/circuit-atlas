"""Fixed-operation local web adapter; all circuit access goes through MCP."""
import asyncio
import json
import os
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def error_message(exc):
    if isinstance(exc, BaseExceptionGroup):
        return '; '.join(dict.fromkeys(error_message(e) for e in exc.exceptions))
    message = str(exc) or type(exc).__name__
    if 'Virtuoso export failed' in message:
        return 'Cadence 회로 읽기 실패: 가져올 schematic 창을 클릭해 활성화한 뒤 다시 읽어 주세요. 계속 실패하면 CIW 오류를 확인해 주세요.'
    return message

async def request(operation, arguments):
    name = {'status': 'cadence_status', 'snapshot': 'cadence_get_current_schematic', 'simulation-inspect': 'cadence_inspect_saved_simulation', 'simulation-run': 'cadence_run_saved_simulation'}[operation]
    params = StdioServerParameters(command=sys.executable,
        args=[str(Path(__file__).with_name('server.py'))], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            content = '\n'.join(item.text for item in result.content if item.type == 'text')
            if result.isError:
                raise RuntimeError(content)
            return result.structuredContent or json.loads(content)

if __name__ == '__main__':
    try:
        data = asyncio.run(asyncio.wait_for(request(sys.argv[1], json.loads(sys.stdin.read(32768) or '{}')), 90))
        print(json.dumps({'ok': True, 'data': data}, ensure_ascii=True))
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': error_message(exc)}, ensure_ascii=True))
        sys.exit(1)
