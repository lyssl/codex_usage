
"""
Small local dashboard for Codex token usage.

It reads Codex session jsonl files, serves a tiny HTML dashboard, and exposes
fresh usage data at /api/usage. It intentionally uses only the Python standard
library so the source stays small and any future executable build is lean.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import webbrowser
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


TOKEN_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Codex 用量统计</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f5;
      --surface: #ffffff;
      --surface-2: #eef1ee;
      --ink: #191c1b;
      --muted: #65706b;
      --line: #d9ded9;
      --accent: #0f8b5f;
      --accent-2: #22577a;
      --warn: #b25f00;
      --danger: #b42318;
      --shadow: 0 1px 2px rgba(25, 28, 27, 0.06);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-width: 320px;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }

    header {
      border-bottom: 1px solid var(--line);
      background: rgba(246, 247, 245, 0.92);
      position: sticky;
      top: 0;
      z-index: 5;
      backdrop-filter: blur(14px);
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      max-width: 1240px;
      margin: 0 auto;
      padding: 18px 24px;
    }

    h1 {
      margin: 0;
      font-size: 20px;
      line-height: 1.2;
      font-weight: 720;
    }

    .meta {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px 16px;
      color: var(--muted);
      font-size: 13px;
    }

    main {
      max-width: 1240px;
      margin: 0 auto;
      padding: 24px;
    }

    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }

    .metric {
      min-width: 0;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 16px;
    }

    .metric label {
      display: block;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.2;
      margin-bottom: 10px;
    }

    .metric strong {
      display: block;
      font-size: 28px;
      line-height: 1;
      font-weight: 760;
      overflow-wrap: anywhere;
    }

    .metric span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-top: 9px;
      overflow-wrap: anywhere;
    }

    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
      gap: 18px;
      align-items: start;
    }

    section {
      min-width: 0;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      margin-bottom: 18px;
    }

    .section-head {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 16px;
      padding: 16px;
      border-bottom: 1px solid var(--line);
    }

    h2 {
      margin: 0;
      font-size: 14px;
      line-height: 1.3;
      font-weight: 700;
    }

    .section-note {
      color: var(--muted);
      font-size: 12px;
      text-align: right;
    }

    .split {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 1px;
      background: var(--line);
      border-bottom: 1px solid var(--line);
    }

    .token-part {
      background: var(--surface);
      padding: 14px 16px;
      min-width: 0;
    }

    .token-part label {
      display: block;
      color: var(--muted);
      font-size: 11px;
      margin-bottom: 7px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .token-part strong {
      font-size: 18px;
      line-height: 1.1;
      overflow-wrap: anywhere;
    }

    .rate-wrap {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      padding: 16px;
    }

    .rate {
      min-width: 0;
    }

    .rate-line {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
    }

    .bar {
      height: 10px;
      overflow: hidden;
      border-radius: 999px;
      background: var(--surface-2);
    }

    .bar > i {
      display: block;
      height: 100%;
      width: 0;
      border-radius: inherit;
      background: var(--accent);
      transition: width 280ms ease;
    }

    .bar > i.warn { background: var(--warn); }
    .bar > i.danger { background: var(--danger); }

    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }

    th, td {
      padding: 11px 16px;
      border-bottom: 1px solid var(--line);
      font-size: 13px;
      line-height: 1.35;
      vertical-align: middle;
    }

    th {
      color: var(--muted);
      text-align: left;
      font-weight: 650;
      background: #fbfcfb;
    }

    td {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    tbody tr {
      transition: background 160ms ease;
    }

    tbody tr:hover {
      background: #f8faf8;
    }

    .num {
      text-align: right;
      font-variant-numeric: tabular-nums;
    }

    .path {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }

    .empty {
      padding: 20px 16px;
      color: var(--muted);
      font-size: 13px;
    }

    .status-dot {
      display: inline-block;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent);
      margin-right: 7px;
      vertical-align: 1px;
    }

    .status-dot.error { background: var(--danger); }

    @media (max-width: 980px) {
      .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .grid { grid-template-columns: 1fr; }
      .split { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .token-part:last-child { grid-column: span 2; }
    }

    @media (max-width: 640px) {
      .topbar {
        align-items: flex-start;
        flex-direction: column;
        padding: 16px;
      }

      .meta { justify-content: flex-start; }
      main { padding: 16px; }
      .summary { grid-template-columns: 1fr; }
      .rate-wrap { grid-template-columns: 1fr; }
      th, td { padding: 10px 12px; }
      .hide-sm { display: none; }
    }
  </style>
</head>
<body>
  <header>
    <div class="topbar">
      <h1>Codex 用量统计</h1>
      <div class="meta">
        <span id="status"><i class="status-dot"></i>实时</span>
        <span id="updated">等待数据</span>
        <span>刷新间隔：5 秒</span>
      </div>
    </div>
  </header>

  <main>
    <div class="summary">
      <div class="metric"><label>总用量</label><strong id="lifeTotal">0</strong><span id="lifeSessions">0 个会话</span></div>
      <div class="metric"><label>今日用量</label><strong id="todayTotal">0</strong><span id="todayDate">本地日期</span></div>
      <div class="metric"><label>最近会话</label><strong id="latestTotal">0</strong><span id="latestName">暂无会话</span></div>
      <div class="metric"><label>最近请求</label><strong id="lastTotal">0</strong><span id="lastBreakdown">暂无请求</span></div>
    </div>

    <section>
      <div class="section-head">
        <h2>Token构成</h2>
        <div class="section-note">按会话最新累计值汇总</div>
      </div>
      <div class="split">
        <div class="token-part"><label>输入</label><strong id="splitInput">0</strong></div>
        <div class="token-part"><label>缓存输入</label><strong id="splitCached">0</strong></div>
        <div class="token-part"><label>输出</label><strong id="splitOutput">0</strong></div>
        <div class="token-part"><label>推理输出</label><strong id="splitReasoning">0</strong></div>
        <div class="token-part"><label>合计</label><strong id="splitTotal">0</strong></div>
      </div>
      <div class="rate-wrap">
        <div class="rate">
          <div class="rate-line"><span>5 小时额度</span><strong id="primaryText">无</strong></div>
          <div class="bar"><i id="primaryBar"></i></div>
        </div>
        <div class="rate">
          <div class="rate-line"><span>7 天额度</span><strong id="secondaryText">无</strong></div>
          <div class="bar"><i id="secondaryBar"></i></div>
        </div>
      </div>
    </section>

    <div class="grid">
      <div>
        <section>
          <div class="section-head">
            <h2>每日用量</h2>
            <div class="section-note">按最近请求用量汇总</div>
          </div>
          <table>
            <thead><tr><th>日期</th><th class="num">合计</th><th class="num hide-sm">输入</th><th class="num hide-sm">输出</th></tr></thead>
            <tbody id="dateRows"></tbody>
          </table>
        </section>

        <section>
          <div class="section-head">
            <h2>项目</h2>
            <div class="section-note">按会话最新累计值汇总</div>
          </div>
          <table>
            <thead><tr><th>工作区</th><th class="num">合计</th><th class="num hide-sm">会话数</th></tr></thead>
            <tbody id="projectRows"></tbody>
          </table>
        </section>
      </div>

      <section>
        <div class="section-head">
          <h2>最近会话</h2>
          <div class="section-note" id="scanNote">正在扫描文件</div>
        </div>
        <table>
          <thead><tr><th>会话</th><th class="num">合计</th><th class="hide-sm">更新时间</th></tr></thead>
          <tbody id="sessionRows"></tbody>
        </table>
      </section>
    </div>
  </main>

  <script>
    const nf = new Intl.NumberFormat();
    const ids = (name) => document.getElementById(name);

    function fmt(n) {
      return nf.format(Number(n || 0));
    }

    function shortPath(path) {
      if (!path) return "未知工作区";
      const parts = path.split(/[\\/]+/).filter(Boolean);
      if (parts.length <= 3) return path;
      return parts.slice(-3).join("/");
    }

    function barClass(percent) {
      if (percent >= 90) return "danger";
      if (percent >= 70) return "warn";
      return "";
    }

    function updateRate(kind, data) {
      const text = ids(kind + "Text");
      const bar = ids(kind + "Bar");
      if (!data || data.used_percent == null) {
        text.textContent = "无";
        bar.style.width = "0%";
        bar.className = "";
        return;
      }
      const pct = Math.max(0, Math.min(100, Number(data.used_percent)));
      const reset = data.resets_at_text ? `，${data.resets_at_text} 重置` : "";
      text.textContent = `${pct.toFixed(1)}%${reset}`;
      bar.style.width = `${pct}%`;
      bar.className = barClass(pct);
    }

    function rowsOrEmpty(target, rows, emptyText) {
      const tbody = ids(target);
      tbody.innerHTML = rows.length ? rows.join("") : `<tr><td colspan="4" class="empty">${emptyText}</td></tr>`;
    }

    function render(data) {
      const total = data.totals.lifetime || {};
      const today = data.totals.today || {};
      const latest = data.latest_session || {};
      const last = data.latest_request || {};

      ids("lifeTotal").textContent = fmt(total.total_tokens);
      ids("lifeSessions").textContent = `${fmt(data.session_count)} 个会话，${fmt(data.token_event_count)} 条Token事件`;
      ids("todayTotal").textContent = fmt(today.total_tokens);
      ids("todayDate").textContent = data.today;
      ids("latestTotal").textContent = fmt((latest.total_usage || {}).total_tokens);
      ids("latestName").textContent = latest.cwd ? shortPath(latest.cwd) : "暂无会话";
      ids("lastTotal").textContent = fmt((last.usage || {}).total_tokens);
      ids("lastBreakdown").textContent = last.timestamp_local || "暂无请求";

      ids("splitInput").textContent = fmt(total.input_tokens);
      ids("splitCached").textContent = fmt(total.cached_input_tokens);
      ids("splitOutput").textContent = fmt(total.output_tokens);
      ids("splitReasoning").textContent = fmt(total.reasoning_output_tokens);
      ids("splitTotal").textContent = fmt(total.total_tokens);

      updateRate("primary", data.rate_limits && data.rate_limits.primary);
      updateRate("secondary", data.rate_limits && data.rate_limits.secondary);

      rowsOrEmpty("dateRows", data.by_date.map((row) => `
        <tr>
          <td>${row.date}</td>
          <td class="num">${fmt(row.usage.total_tokens)}</td>
          <td class="num hide-sm">${fmt(row.usage.input_tokens)}</td>
          <td class="num hide-sm">${fmt(row.usage.output_tokens)}</td>
        </tr>`), "暂无每日用量。");

      rowsOrEmpty("projectRows", data.by_project.map((row) => `
        <tr>
          <td class="path" title="${row.cwd || ""}">${shortPath(row.cwd)}</td>
          <td class="num">${fmt(row.usage.total_tokens)}</td>
          <td class="num hide-sm">${fmt(row.sessions)}</td>
        </tr>`), "暂无项目用量。");

      rowsOrEmpty("sessionRows", data.sessions.slice(0, 18).map((row) => `
        <tr>
          <td title="${row.id || ""}">${shortPath(row.cwd) || row.id}</td>
          <td class="num">${fmt((row.total_usage || {}).total_tokens)}</td>
          <td class="hide-sm">${row.latest_token_at_local || ""}</td>
        </tr>`), "暂无Token会话。");

      ids("scanNote").textContent = `已扫描 ${fmt(data.scanned_files)} 个文件`;
      ids("updated").textContent = `更新于 ${data.generated_at_local}`;
      ids("status").innerHTML = '<i class="status-dot"></i>实时';
    }

    async function refresh() {
      try {
        const res = await fetch("/api/usage", { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        render(await res.json());
      } catch (err) {
        ids("status").innerHTML = '<i class="status-dot error"></i>离线';
        ids("updated").textContent = err.message || "刷新失败";
      }
    }

    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>
"""


@dataclass
class TokenEvent:
    timestamp: datetime
    usage: dict[str, int]


@dataclass
class TurnEvent:
    started_at: datetime
    latest_token_at: datetime | None = None
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class SessionRecord:
    id: str
    file: str
    cwd: str = ""
    started_at: datetime | None = None
    latest_token_at: datetime | None = None
    total_usage: dict[str, int] = field(default_factory=dict)
    last_usage: dict[str, int] = field(default_factory=dict)
    rate_limits: dict[str, Any] = field(default_factory=dict)
    token_events: list[TokenEvent] = field(default_factory=list)
    turn_events: list[TurnEvent] = field(default_factory=list)


def empty_usage() -> dict[str, int]:
    return {key: 0 for key in TOKEN_KEYS}


def normalize_usage(raw: Any) -> dict[str, int]:
    usage = empty_usage()
    if isinstance(raw, dict):
        for key in TOKEN_KEYS:
            try:
                usage[key] = int(raw.get(key) or 0)
            except (TypeError, ValueError):
                usage[key] = 0
    return usage


def add_usage(target: dict[str, int], usage: dict[str, int]) -> None:
    for key in TOKEN_KEYS:
        target[key] = int(target.get(key, 0)) + int(usage.get(key, 0))


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def local_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone()


def local_text(value: datetime | None) -> str:
    local = local_dt(value)
    if local is None:
        return ""
    return local.strftime("%Y-%m-%d %H:%M:%S")


def local_date(value: datetime | None) -> str:
    local = local_dt(value)
    if local is None:
        return ""
    return local.strftime("%Y-%m-%d")


def timestamp_text(value: Any) -> str:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(seconds, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")


def iter_session_files(codex_home: Path) -> list[Path]:
    files: list[Path] = []
    sessions = codex_home / "sessions"
    archived = codex_home / "archived_sessions"
    if sessions.exists():
        files.extend(sessions.rglob("*.jsonl"))
    if archived.exists():
        files.extend(archived.glob("*.jsonl"))
    return sorted(files, key=lambda p: str(p).lower())


def fallback_session_id(path: Path) -> str:
    stem = path.stem
    if stem.startswith("rollout-") and len(stem) > 36:
        return stem[-36:]
    return stem


def parse_session_file(path: Path) -> SessionRecord | None:
    record = SessionRecord(id=fallback_session_id(path), file=str(path))
    current_turn: TurnEvent | None = None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue

                item_type = item.get("type")
                payload = item.get("payload")
                timestamp = parse_dt(item.get("timestamp"))

                if item_type == "session_meta" and isinstance(payload, dict):
                    record.id = str(payload.get("id") or record.id)
                    record.cwd = str(payload.get("cwd") or record.cwd)
                    record.started_at = parse_dt(payload.get("timestamp")) or record.started_at
                    continue

                if item_type != "event_msg" or not isinstance(payload, dict):
                    continue
                if payload.get("type") == "user_message":
                    if current_turn is not None and current_turn.latest_token_at is not None:
                        record.turn_events.append(current_turn)
                    turn_time = timestamp or record.latest_token_at or record.started_at or datetime.now(timezone.utc)
                    current_turn = TurnEvent(started_at=turn_time, usage=empty_usage())
                    continue
                if payload.get("type") != "token_count":
                    continue

                info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
                total_usage = normalize_usage(info.get("total_token_usage"))
                last_usage = normalize_usage(info.get("last_token_usage"))
                token_time = timestamp or record.latest_token_at or record.started_at
                if token_time is not None:
                    record.token_events.append(TokenEvent(token_time, last_usage))
                    if current_turn is None:
                        current_turn = TurnEvent(started_at=token_time, usage=empty_usage())
                    add_usage(current_turn.usage, last_usage)
                    current_turn.latest_token_at = token_time

                if record.latest_token_at is None or (token_time and token_time >= record.latest_token_at):
                    record.latest_token_at = token_time
                    record.total_usage = total_usage
                    record.last_usage = last_usage
                    rate_limits = payload.get("rate_limits")
                    record.rate_limits = rate_limits if isinstance(rate_limits, dict) else {}
    except OSError:
        return None

    if current_turn is not None and current_turn.latest_token_at is not None:
        record.turn_events.append(current_turn)

    if record.latest_token_at is None and not record.token_events:
        return None
    return record


def collect_usage(codex_home: Path) -> dict[str, Any]:
    files = iter_session_files(codex_home)
    records_by_id: dict[str, SessionRecord] = {}

    for path in files:
        record = parse_session_file(path)
        if record is None:
            continue
        existing = records_by_id.get(record.id)
        if existing is None:
            records_by_id[record.id] = record
            continue
        existing_time = existing.latest_token_at or existing.started_at or datetime.min.replace(tzinfo=timezone.utc)
        record_time = record.latest_token_at or record.started_at or datetime.min.replace(tzinfo=timezone.utc)
        if record_time >= existing_time:
            records_by_id[record.id] = record

    records = sorted(
        records_by_id.values(),
        key=lambda item: item.latest_token_at or item.started_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    lifetime = empty_usage()
    by_date: dict[str, dict[str, int]] = defaultdict(empty_usage)
    project_usage: dict[str, dict[str, int]] = defaultdict(empty_usage)
    project_sessions: dict[str, int] = defaultdict(int)
    latest_request: dict[str, Any] = {}
    latest_turn: dict[str, Any] = {}
    token_event_count = 0
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    today_usage = empty_usage()

    for record in records:
        add_usage(lifetime, record.total_usage)
        project_key = record.cwd or "未知工作区"
        add_usage(project_usage[project_key], record.total_usage)
        project_sessions[project_key] += 1

        for event in record.token_events:
            token_event_count += 1
            date_key = local_date(event.timestamp)
            if date_key:
                add_usage(by_date[date_key], event.usage)
                if date_key == today:
                    add_usage(today_usage, event.usage)

            if not latest_request or event.timestamp > latest_request["timestamp"]:
                latest_request = {
                    "timestamp": event.timestamp,
                    "usage": event.usage,
                    "session_id": record.id,
                    "cwd": record.cwd,
                }

        for turn in record.turn_events:
            if turn.latest_token_at is None:
                continue
            if not latest_turn or turn.latest_token_at > latest_turn["timestamp"]:
                latest_turn = {
                    "timestamp": turn.latest_token_at,
                    "started_at": turn.started_at,
                    "usage": turn.usage,
                    "session_id": record.id,
                    "cwd": record.cwd,
                }

    latest_session = records[0] if records else None
    latest_rate_record = next((record for record in records if record.rate_limits), None)
    rate_limits = latest_rate_record.rate_limits if latest_rate_record else {}

    generated_at = datetime.now().astimezone()

    return {
        "generated_at": generated_at.isoformat(),
        "generated_at_local": generated_at.strftime("%Y-%m-%d %H:%M:%S"),
        "codex_home": str(codex_home),
        "today": today,
        "scanned_files": len(files),
        "session_count": len(records),
        "token_event_count": token_event_count,
        "totals": {
            "lifetime": lifetime,
            "today": today_usage,
        },
        "rate_limits": decorate_rate_limits(rate_limits),
        "latest_session": serialize_session(latest_session),
        "latest_request": serialize_latest_request(latest_request),
        "latest_turn": serialize_latest_turn(latest_turn),
        "by_date": [
            {"date": date_key, "usage": usage}
            for date_key, usage in sorted(by_date.items(), reverse=True)
        ],
        "by_project": sorted(
            (
                {"cwd": cwd, "usage": usage, "sessions": project_sessions[cwd]}
                for cwd, usage in project_usage.items()
            ),
            key=lambda row: row["usage"]["total_tokens"],
            reverse=True,
        ),
        "sessions": [serialize_session(record) for record in records],
    }


def decorate_rate_limits(rate_limits: dict[str, Any]) -> dict[str, Any]:
    decorated: dict[str, Any] = {}
    for key in ("primary", "secondary"):
        raw = rate_limits.get(key)
        if not isinstance(raw, dict):
            decorated[key] = None
            continue
        item = dict(raw)
        item["resets_at_text"] = timestamp_text(raw.get("resets_at"))
        item["remaining_percent"] = remaining_percent(item)
        remaining = remaining_tokens(item)
        if remaining is not None:
            item["remaining_tokens"] = remaining
        decorated[key] = item
    decorated["plan_type"] = rate_limits.get("plan_type")
    decorated["limit_id"] = rate_limits.get("limit_id")
    return decorated


def remaining_percent(rate_limit: dict[str, Any]) -> float | None:
    raw_remaining = rate_limit.get("remaining_percent")
    if raw_remaining is not None:
        try:
            return max(0.0, min(100.0, float(raw_remaining)))
        except (TypeError, ValueError):
            pass
    try:
        used = float(rate_limit.get("used_percent"))
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, 100.0 - used))


def remaining_tokens(rate_limit: dict[str, Any]) -> int | None:
    for key in ("remaining_tokens", "remaining"):
        raw = rate_limit.get(key)
        if raw is not None:
            try:
                return max(0, int(raw))
            except (TypeError, ValueError):
                pass

    limit = first_int(rate_limit, ("token_limit", "limit", "max_tokens"))
    used = first_int(rate_limit, ("used_tokens", "used", "tokens_used"))
    if limit is None or used is None:
        return None
    return max(0, limit - used)


def first_int(source: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        raw = source.get(key)
        if raw is None:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def serialize_session(record: SessionRecord | None) -> dict[str, Any]:
    if record is None:
        return {}
    return {
        "id": record.id,
        "file": record.file,
        "cwd": record.cwd,
        "started_at": record.started_at.isoformat() if record.started_at else "",
        "started_at_local": local_text(record.started_at),
        "latest_token_at": record.latest_token_at.isoformat() if record.latest_token_at else "",
        "latest_token_at_local": local_text(record.latest_token_at),
        "total_usage": record.total_usage,
        "last_usage": record.last_usage,
    }


def serialize_latest_request(latest_request: dict[str, Any]) -> dict[str, Any]:
    if not latest_request:
        return {}
    timestamp = latest_request["timestamp"]
    return {
        "timestamp": timestamp.isoformat(),
        "timestamp_local": local_text(timestamp),
        "usage": latest_request["usage"],
        "session_id": latest_request["session_id"],
        "cwd": latest_request["cwd"],
    }


def serialize_latest_turn(latest_turn: dict[str, Any]) -> dict[str, Any]:
    if not latest_turn:
        return {}
    timestamp = latest_turn["timestamp"]
    started_at = latest_turn.get("started_at")
    return {
        "timestamp": timestamp.isoformat(),
        "timestamp_local": local_text(timestamp),
        "started_at": started_at.isoformat() if isinstance(started_at, datetime) else "",
        "started_at_local": local_text(started_at) if isinstance(started_at, datetime) else "",
        "usage": latest_turn["usage"],
        "session_id": latest_turn["session_id"],
        "cwd": latest_turn["cwd"],
    }


class UsageHandler(BaseHTTPRequestHandler):
    codex_home: Path
    frontend_file: Path

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html", "/codex_usage.html"):
            self.send_frontend()
            return
        if parsed.path == "/api/usage":
            started = time.perf_counter()
            try:
                payload = collect_usage(self.codex_home)
                payload["scan_ms"] = round((time.perf_counter() - started) * 1000, 2)
                self.send_json(200, payload)
            except Exception as exc:  # Keep the page debuggable without crashing the server.
                self.send_json(500, {"error": str(exc)})
            return
        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        self.send_json(404, {"error": "not found"})

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), format % args))

    def send_frontend(self) -> None:
        try:
            body = self.frontend_file.read_text(encoding="utf-8")
        except OSError:
            body = HTML
        self.send_text(200, body, "text/html; charset=utf-8")

    def send_text(self, status: int, body: str, content_type: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def default_codex_home() -> Path:
    value = os.environ.get("CODEX_HOME")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".codex"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a local Codex token usage dashboard.")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host to bind.")
    parser.add_argument("--port", default=8765, type=int, help="HTTP port to bind.")
    parser.add_argument("--codex-home", default=str(default_codex_home()), help="Path to the Codex home directory.")
    parser.add_argument(
        "--frontend",
        default=str(Path(__file__).with_name("codex_usage.html")),
        help="Path to the dashboard HTML file.",
    )
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser automatically.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    codex_home = Path(args.codex_home).expanduser().resolve()
    frontend_file = Path(args.frontend).expanduser().resolve()
    handler = type(
        "BoundUsageHandler",
        (UsageHandler,),
        {"codex_home": codex_home, "frontend_file": frontend_file},
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}"
    safe_print(f"Codex token usage dashboard: {url}")
    safe_print(f"Reading Codex data from: {codex_home}")
    safe_print(f"Serving frontend from: {frontend_file}")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        safe_print("\nStopping dashboard.")
    finally:
        server.server_close()
    return 0


def safe_print(message: str) -> None:
    if sys.stdout is None:
        return
    print(message)


if __name__ == "__main__":
    raise SystemExit(main())
