#!/usr/bin/env python3
"""Loopback-only router that adds Mindlogic models to Claude Code.

Claude Code talks Anthropic Messages to this router. Requests whose model
starts with ``mindlogic/`` are translated to the Mindlogic Gateway Responses
API (the same endpoint the Codex setup uses). Every other request is relayed
unchanged to Anthropic with the caller's own credentials, so the existing
Claude login keeps working.
"""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.client import HTTPConnection, HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import socket
import ssl
import sys
from urllib.parse import urlsplit
import uuid


ANTHROPIC_UPSTREAM = os.environ.get("MINDLOGIC_ROUTER_ANTHROPIC_URL", "https://api.anthropic.com")
MINDLOGIC_UPSTREAM = os.environ.get("MINDLOGIC_ROUTER_GATEWAY_URL", "https://factchat-cloud.mindlogic.ai/v1/gateway")
MODEL_PREFIX = "mindlogic/"
MAX_REQUEST_BYTES = 32 * 1024 * 1024
LOCAL_TOKEN_HEADER = "X-Mindlogic-Router-Token"
HOP_HEADERS = {"host", "connection", "content-length", "accept-encoding", "transfer-encoding", "keep-alive",
               "proxy-authorization", "proxy-authenticate", "te", "trailer", "upgrade", LOCAL_TOKEN_HEADER.lower()}
KEY_FILES = [Path.home() / ".claude" / "mindlogic.env", Path.home() / ".codex" / ".env"]


def read_mindlogic_key() -> str:
    if os.environ.get("FACTCHAT_API_KEY"):
        return os.environ["FACTCHAT_API_KEY"].strip()
    for path in KEY_FILES:
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            match = re.match(r"^\s*(?:export\s+)?FACTCHAT_API_KEY\s*=\s*(.*?)\s*$", line)
            if match:
                value = match.group(1)
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                if value and "\r" not in value and "\n" not in value:
                    return value
    raise ValueError("FACTCHAT_API_KEY is not registered (~/.claude/mindlogic.env or ~/.codex/.env)")


def connect(base_url: str):
    parts = urlsplit(base_url)
    if parts.scheme == "http":
        return HTTPConnection(parts.hostname, parts.port or 80, timeout=600), parts.path.rstrip("/")
    system_ca = Path("/etc/ssl/cert.pem")
    context = ssl.create_default_context(cafile=str(system_ca) if system_ca.is_file() else None)
    return HTTPSConnection(parts.hostname, parts.port or 443, timeout=600, context=context), parts.path.rstrip("/")


# ---------------------------------------------------------------- request translation

def text_of(content) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif block.get("type") == "image":
            parts.append("[image omitted]")
    return "\n".join(parts)


def image_part(block: dict) -> dict | None:
    source = block.get("source") or {}
    if source.get("type") == "base64":
        return {"type": "input_image", "image_url": f"data:{source.get('media_type')};base64,{source.get('data')}"}
    if source.get("type") == "url":
        return {"type": "input_image", "image_url": source.get("url")}
    return None


def to_responses(payload: dict, upstream_model: str) -> dict:
    items: list[dict] = []
    for message in payload.get("messages", []):
        role, content = message.get("role"), message.get("content")
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        pending: list[dict] = []

        def flush():
            if pending:
                items.append({"role": role, "content": list(pending)})
                pending.clear()

        for block in content or []:
            kind = block.get("type")
            if kind == "text" and block.get("text"):
                pending.append({"type": "output_text" if role == "assistant" else "input_text", "text": block["text"]})
            elif kind == "image" and role == "user":
                part = image_part(block)
                if part:
                    pending.append(part)
            elif kind == "tool_use":
                flush()
                items.append({"type": "function_call", "call_id": block["id"], "name": block["name"],
                              "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False)})
            elif kind == "tool_result":
                flush()
                output = text_of(block.get("content"))
                if block.get("is_error"):
                    output = "[tool error] " + output
                items.append({"type": "function_call_output", "call_id": block["tool_use_id"], "output": output})
            # thinking / redacted_thinking / cache hints are Anthropic-only and dropped.
        flush()

    body: dict = {"model": upstream_model, "input": items, "store": False,
                  "stream": bool(payload.get("stream"))}
    system = payload.get("system")
    if system:
        body["instructions"] = text_of(system)
    if payload.get("max_tokens"):
        body["max_output_tokens"] = payload["max_tokens"]
    tools = [{"type": "function", "name": tool["name"], "description": tool.get("description", ""),
              "parameters": tool.get("input_schema") or {"type": "object", "properties": {}}, "strict": False}
             for tool in payload.get("tools") or [] if tool.get("name") and not tool.get("type", "").startswith(("web_search", "computer", "bash_", "text_editor"))]
    if tools:
        body["tools"] = tools
        choice = payload.get("tool_choice") or {}
        if choice.get("type") == "any":
            body["tool_choice"] = "required"
        elif choice.get("type") == "tool":
            body["tool_choice"] = {"type": "function", "name": choice.get("name")}
        elif choice.get("type") == "none":
            body["tool_choice"] = "none"
        if choice.get("disable_parallel_tool_use"):
            body["parallel_tool_calls"] = False
    return body


# ---------------------------------------------------------------- response translation

def sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()


def iter_sse(response):
    event, data = None, []
    while True:
        raw = response.readline()
        if not raw:
            break
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if not line:
            if data:
                yield event, "\n".join(data)
            event, data = None, []
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    if data:
        yield event, "\n".join(data)


def stop_reason(response: dict, used_tool: bool) -> str:
    if used_tool:
        return "tool_use"
    details = response.get("incomplete_details") or {}
    if response.get("status") == "incomplete" and details.get("reason") == "max_output_tokens":
        return "max_tokens"
    return "end_turn"


def usage_of(response: dict) -> dict:
    usage = response.get("usage") or {}
    return {"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0)}


class StreamTranslator:
    """Turns Responses SSE events into Anthropic Messages SSE events."""

    def __init__(self, alias: str):
        self.alias = alias
        self.blocks: dict[int, int] = {}  # Responses output_index -> Anthropic content index
        self.open: set[int] = set()
        self.used_tool = False
        self.started = False

    def start(self) -> bytes:
        self.started = True
        message = {"id": "msg_" + uuid.uuid4().hex, "type": "message", "role": "assistant", "model": self.alias,
                   "content": [], "stop_reason": None, "stop_sequence": None,
                   "usage": {"input_tokens": 0, "output_tokens": 0}}
        return sse("message_start", {"type": "message_start", "message": message})

    def open_block(self, output_index: int, block: dict) -> bytes:
        index = len(self.blocks)
        self.blocks[output_index] = index
        self.open.add(index)
        return sse("content_block_start", {"type": "content_block_start", "index": index, "content_block": block})

    def close_block(self, output_index: int) -> bytes:
        index = self.blocks.get(output_index)
        if index is None or index not in self.open:
            return b""
        self.open.discard(index)
        return sse("content_block_stop", {"type": "content_block_stop", "index": index})

    def handle(self, event: dict) -> bytes:
        kind = event.get("type", "")
        out = b""
        if kind == "response.output_item.added":
            item = event.get("item") or {}
            if item.get("type") == "function_call":
                self.used_tool = True
                out += self.open_block(event["output_index"], {"type": "tool_use", "id": item.get("call_id") or item.get("id"),
                                                              "name": item.get("name"), "input": {}})
                if item.get("arguments"):
                    out += self.delta(event["output_index"], {"type": "input_json_delta", "partial_json": item["arguments"]})
        elif kind == "response.output_text.delta":
            if event["output_index"] not in self.blocks:
                out += self.open_block(event["output_index"], {"type": "text", "text": ""})
            out += self.delta(event["output_index"], {"type": "text_delta", "text": event.get("delta", "")})
        elif kind == "response.function_call_arguments.delta":
            out += self.delta(event["output_index"], {"type": "input_json_delta", "partial_json": event.get("delta", "")})
        elif kind == "response.output_item.done":
            out += self.close_block(event.get("output_index"))
        elif kind in ("response.completed", "response.incomplete"):
            out += self.finish(event.get("response") or {})
        elif kind in ("response.failed", "error"):
            error = (event.get("response") or {}).get("error") or event.get("error") or event
            message = error.get("message") if isinstance(error, dict) else str(error)
            out += sse("error", {"type": "error", "error": {"type": "api_error", "message": f"Mindlogic: {message}"}})
        return out

    def delta(self, output_index: int, delta: dict) -> bytes:
        index = self.blocks.get(output_index)
        if index is None:
            return b""
        return sse("content_block_delta", {"type": "content_block_delta", "index": index, "delta": delta})

    def finish(self, response: dict) -> bytes:
        out = b"".join(sse("content_block_stop", {"type": "content_block_stop", "index": index})
                       for index in sorted(self.open))
        self.open.clear()
        out += sse("message_delta", {"type": "message_delta",
                                     "delta": {"stop_reason": stop_reason(response, self.used_tool), "stop_sequence": None},
                                     "usage": usage_of(response)})
        return out + sse("message_stop", {"type": "message_stop"})


def to_message(response: dict, alias: str) -> dict:
    content, used_tool = [], False
    for item in response.get("output") or []:
        if item.get("type") == "message":
            for part in item.get("content") or []:
                if part.get("type") == "output_text":
                    content.append({"type": "text", "text": part.get("text", "")})
        elif item.get("type") == "function_call":
            used_tool = True
            try:
                arguments = json.loads(item.get("arguments") or "{}")
            except ValueError:
                arguments = {}
            content.append({"type": "tool_use", "id": item.get("call_id") or item.get("id"),
                            "name": item.get("name"), "input": arguments})
    return {"id": "msg_" + uuid.uuid4().hex, "type": "message", "role": "assistant", "model": alias,
            "content": content, "stop_reason": stop_reason(response, used_tool), "stop_sequence": None,
            "usage": usage_of(response)}


# ---------------------------------------------------------------- HTTP server

class Router(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, *, local_token: str):
        super().__init__(address, Handler)
        self.local_token = local_token


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def reply_json(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def reply_error(self, status: HTTPStatus, message: str) -> None:
        kind = "authentication_error" if status == HTTPStatus.UNAUTHORIZED else "api_error"
        self.reply_json(status, {"type": "error", "error": {"type": kind, "message": message}})

    def start_chunked(self, status: int, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

    def chunk(self, data: bytes) -> None:
        if data:
            self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
            self.wfile.flush()

    def end_chunked(self) -> None:
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()

    def do_GET(self):
        if self.path == "/health":
            self.reply_json(200, {"status": "ok"})
        else:
            self.handle_any()

    def do_POST(self):
        self.handle_any()

    def handle_any(self):
        if self.headers.get(LOCAL_TOKEN_HEADER) != self.server.local_token:
            self.reply_error(HTTPStatus.UNAUTHORIZED, "Local router token missing; start Claude Code with claude-ml")
            return
        size = int(self.headers.get("Content-Length") or 0)
        if not 0 <= size <= MAX_REQUEST_BYTES:
            self.reply_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request too large")
            return
        body = self.rfile.read(size) if size else b""
        model = ""
        if body and self.command == "POST":
            try:
                model = str(json.loads(body).get("model") or "")
            except (ValueError, AttributeError):
                model = ""
        path = urlsplit(self.path).path
        if model.startswith(MODEL_PREFIX) and path.startswith("/v1/messages"):
            self.mindlogic(path, json.loads(body), model)
        else:
            self.passthrough(body)

    def passthrough(self, body: bytes) -> None:
        connection, prefix = connect(ANTHROPIC_UPSTREAM)
        headers = {name: value for name, value in self.headers.items() if name.lower() not in HOP_HEADERS}
        headers["Content-Length"] = str(len(body))
        started = False
        try:
            connection.request(self.command, prefix + self.path, body=body, headers=headers)
            response = connection.getresponse()
            self.send_response(response.status)
            for name, value in response.getheaders():
                if name.lower() not in HOP_HEADERS and name.lower() != "content-encoding":
                    self.send_header(name, value)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            started = True
            while data := response.read1(65536):
                self.chunk(data)
            self.end_chunked()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (OSError, socket.timeout) as error:
            if not started:
                self.reply_error(HTTPStatus.BAD_GATEWAY, f"Anthropic upstream error: {type(error).__name__}")
        finally:
            connection.close()

    def mindlogic(self, path: str, payload: dict, alias: str) -> None:
        upstream_model = alias[len(MODEL_PREFIX):]
        if path.endswith("/count_tokens"):
            chars = len(json.dumps(payload, ensure_ascii=False))
            self.reply_json(200, {"input_tokens": max(1, chars // 4)})
            return
        try:
            key = read_mindlogic_key()
        except ValueError as error:
            self.reply_error(HTTPStatus.UNAUTHORIZED, str(error))
            return
        request = to_responses(payload, upstream_model)
        data = json.dumps(request, ensure_ascii=False).encode()
        connection, prefix = connect(MINDLOGIC_UPSTREAM)
        headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json",
                   "Accept": "text/event-stream" if request["stream"] else "application/json",
                   "Content-Length": str(len(data))}
        started = False
        log = {"id": uuid.uuid4().hex[:8], "alias": alias, "stream": request["stream"]}
        try:
            connection.request("POST", prefix + "/responses", body=data, headers=headers)
            response = connection.getresponse()
            log["http_status"] = response.status
            if response.status >= 400:
                detail = response.read().decode("utf-8", "replace")[:2000]
                try:
                    error = json.loads(detail).get("error") or {}
                    detail = error.get("message", detail) if isinstance(error, dict) else str(error)
                except (ValueError, AttributeError):
                    pass
                status = response.status if response.status in (400, 401, 402, 403, 404, 429) else 502
                self.reply_json(status, {"type": "error", "error": {
                    "type": "api_error", "message": f"Mindlogic HTTP {response.status}: {detail}"}})
                return
            if not request["stream"]:
                if "event-stream" in (response.getheader("Content-Type") or ""):
                    final = {}
                    for _event, raw in iter_sse(response):
                        try:
                            event = json.loads(raw)
                        except ValueError:
                            continue
                        if event.get("type") in ("response.completed", "response.incomplete"):
                            final = event.get("response") or {}
                            break
                else:
                    final = json.loads(response.read())
                self.reply_json(200, to_message(final, alias))
                return
            translator = StreamTranslator(alias)
            self.start_chunked(200, "text/event-stream")
            started = True
            self.chunk(translator.start())
            finished = False
            for _event, raw in iter_sse(response):
                if raw == "[DONE]":
                    break
                try:
                    event = json.loads(raw)
                except ValueError:
                    continue
                self.chunk(translator.handle(event))
                if event.get("type") in ("response.completed", "response.incomplete", "response.failed", "error"):
                    finished = True
                    break
            if not finished:
                self.chunk(translator.finish({}))
            self.end_chunked()
        except (BrokenPipeError, ConnectionResetError):
            log["client_cancelled"] = True
        except (OSError, socket.timeout) as error:
            log["error"] = type(error).__name__
            if not started:
                self.reply_error(HTTPStatus.BAD_GATEWAY, f"Mindlogic upstream error: {type(error).__name__}")
        finally:
            connection.close()
            print(json.dumps(log), flush=True)  # never logs the key or conversation text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18763)
    parser.add_argument("--token-file", type=Path, default=Path.home() / ".claude" / "mindlogic-router.token")
    args = parser.parse_args()
    if sys.stdout is None:  # started by pythonw at login without redirection
        log = open(Path.home() / ".claude" / "mindlogic-router.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log
    token = args.token_file.read_text().strip()
    if not token:
        raise SystemExit("Router token file is empty")
    server = Router(("127.0.0.1", args.port), local_token=token)
    print(json.dumps({"event": "listening", "port": args.port}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
