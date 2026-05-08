#!/usr/bin/env python3
"""Export a FineBI public directory dashboard tab to Excel.

This script uses only Python's standard library. It reads FineBI connection
details from .env in the project root.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def find_project_root() -> pathlib.Path:
    cwd = pathlib.Path.cwd()
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".env").exists():
            return candidate
    return cwd


PROJECT_ROOT = find_project_root()
DEFAULT_CONFIG = PROJECT_ROOT / ".env"
DEFAULT_OUT_DIR = PROJECT_ROOT / "exports"


def load_config(path: pathlib.Path, profile: str | None = None) -> dict[str, str]:
    config: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        config[key.strip()] = value.strip()

    selected_profile = profile or config.get("finebi_profile") or config.get("FINEBI_PROFILE")
    if selected_profile:
        config = resolve_profile_config(config, selected_profile)

    required = ["host", "fine_username", "fine_password"]
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise SystemExit(f".env missing required keys: {', '.join(missing)}")
    return config


def resolve_profile_config(config: dict[str, str], profile: str) -> dict[str, str]:
    """Overlay profile-specific keys while preserving the legacy flat format."""
    normalized_profile = normalize_profile(profile)
    if not normalized_profile:
        return config

    key_aliases = {
        "host": ("host", "HOST"),
        "fine_username": ("fine_username", "FINE_USERNAME", "USERNAME"),
        "fine_password": ("fine_password", "FINE_PASSWORD", "PASSWORD"),
    }
    profile_prefixes = (
        normalized_profile,
        normalized_profile.lower(),
        normalized_profile.upper(),
        f"finebi_{normalized_profile}".lower(),
        f"FINEBI_{normalized_profile}".upper(),
    )

    resolved = dict(config)
    for target_key, aliases in key_aliases.items():
        matched_value = None
        for prefix in profile_prefixes:
            for alias in aliases:
                candidate_keys = (
                    f"{prefix}.{alias}",
                    f"{prefix}_{alias}",
                    f"{prefix}-{alias}",
                )
                for candidate_key in candidate_keys:
                    if candidate_key in config and config[candidate_key]:
                        matched_value = config[candidate_key]
                        break
                if matched_value is not None:
                    break
            if matched_value is not None:
                break
        if matched_value is not None:
            resolved[target_key] = matched_value

    return resolved


def normalize_profile(profile: str) -> str:
    profile_aliases = {
        "中国": "cn",
        "中國": "cn",
        "china": "cn",
        "zh": "cn",
        "cn": "cn",
        "日本": "jp",
        "japan": "jp",
        "ja": "jp",
        "jp": "jp",
    }
    normalized = profile.strip().lower()
    return profile_aliases.get(normalized, normalized)


def parse_json_or_callback(body: bytes | str) -> Any:
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
    text = text.strip()
    match = re.match(r"^[\w$]+\((.*)\)\s*$", text, re.S)
    if match:
        text = match.group(1)
    return json.loads(text)


def safe_filename(value: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", value).strip("_") or "export"


def node_label(node: dict[str, Any]) -> str:
    return node.get("text") or node.get("name") or node.get("entryName") or node.get("id") or ""


def tree_children(node: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("children", "childNodes", "nodes", "items"):
        value = node.get(key)
        if isinstance(value, list):
            return value
    return []


def walk_any_tree(node: Any, ancestors: tuple[str, ...] = ()):
    if isinstance(node, list):
        for item in node:
            yield from walk_any_tree(item, ancestors)
        return
    if not isinstance(node, dict):
        return
    label = node_label(node)
    yield node, ancestors
    for child in tree_children(node):
        yield from walk_any_tree(child, ancestors + ((label,) if label else ()))


def walk_report_tree(node: Any, ancestors: tuple[str, ...] = ()):
    if isinstance(node, list):
        for item in node:
            yield from walk_report_tree(item, ancestors)
        return
    if not isinstance(node, dict):
        return
    name = node.get("name") or node.get("text") or ""
    yield node, ancestors
    children = node.get("children")
    if isinstance(children, list):
        for child in children:
            yield from walk_report_tree(child, ancestors + ((name,) if name else ()))


class FineBIClient:
    def __init__(self, config: dict[str, str]) -> None:
        self.host = config["host"].rstrip("/")
        self.username = config["fine_username"]
        self.password = config["fine_password"]
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.token = self._login()

    def _login(self) -> str:
        url = self.host + "/webroot/decision/login/cross/domain?" + urllib.parse.urlencode(
            {
                "fine_username": self.username,
                "fine_password": self.password,
                "validity": "-2",
                "callback": "",
            }
        )
        with self.opener.open(url, timeout=30) as response:
            payload = parse_json_or_callback(response.read())
        token = payload.get("accessToken")
        if not token:
            raise SystemExit(f"login did not return accessToken: {payload}")
        return token

    def _request(self, path: str, params: dict[str, str] | None = None, timeout: int = 60):
        url = self.host + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={"Authorization": "Bearer " + self.token})
        return self.opener.open(request, timeout=timeout)

    def get_json(self, path: str, params: dict[str, str] | None = None, timeout: int = 60) -> Any:
        with self._request(path, params, timeout) as response:
            return parse_json_or_callback(response.read())

    def get_bytes(self, path: str, params: dict[str, str] | None = None, timeout: int = 180):
        try:
            with self._request(path, params, timeout) as response:
                return response.status, response.headers.get("Content-Type", ""), response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.headers.get("Content-Type", ""), error.read()


def source_segments(source_path: str) -> list[str]:
    if not source_path:
        return []
    if "的分析/" in source_path:
        source_path = source_path.split("的分析/", 1)[1]
    return [part for part in source_path.split("/") if part]


def source_owner_hint(source_path: str) -> str:
    if "的分析" in source_path:
        return source_path.split("的分析", 1)[0]
    return ""


def locate_public_entry(public_tree: Any, entry_name: str) -> tuple[dict[str, Any], tuple[str, ...]]:
    matches = [
        (node, ancestors)
        for node, ancestors in walk_any_tree(public_tree)
        if isinstance(node, dict) and node_label(node) == entry_name
    ]
    if not matches:
        raise SystemExit(f"public directory entry not found: {entry_name}")
    if len(matches) > 1:
        print(f"warning: found {len(matches)} public entries named {entry_name}; using first match", file=sys.stderr)
    return matches[0]


def locate_subject(report_tree: Any, entry_name: str, public_source_path: str):
    expected_suffix = source_segments(public_source_path) or [entry_name]
    owner_hint = source_owner_hint(public_source_path)
    candidates = []
    for node, ancestors in walk_report_tree(report_tree):
        name = node.get("name") or node.get("text") or ""
        path_parts = [part for part in ancestors if part] + ([name] if name else [])
        if path_parts[-len(expected_suffix) :] == expected_suffix:
            candidates.append((node, ancestors, path_parts))

    if owner_hint:
        owner_matches = [
            candidate
            for candidate in candidates
            if owner_hint in "/".join(candidate[2])
        ]
        if owner_matches:
            candidates = owner_matches

    if not candidates:
        raise SystemExit(
            f"BI report tree subject not found for entry={entry_name!r}, source_path={public_source_path!r}"
        )
    if len(candidates) > 1:
        print("warning: multiple subject candidates found; using first match", file=sys.stderr)
        for node, _ancestors, path_parts in candidates[:10]:
            print(f"candidate: {'/'.join(path_parts)} id={node.get('id')}", file=sys.stderr)
    return candidates[0]


def list_reports(subject_node: dict[str, Any]) -> list[dict[str, Any]]:
    children = subject_node.get("children")
    if not isinstance(children, list):
        return []
    return [
        child
        for child in children
        if isinstance(child, dict) and (child.get("id") or child.get("reportId") or child.get("templateId"))
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export FineBI public directory dashboard tab to Excel.")
    parser.add_argument("--entry", required=True, help="FineBI public directory display name, e.g. 月度复盘表")
    parser.add_argument("--report", help="Dashboard tab name under the public entry, e.g. 总表")
    parser.add_argument("--list", action="store_true", help="List candidate dashboard tabs without exporting")
    parser.add_argument("--config", type=pathlib.Path, default=DEFAULT_CONFIG, help="Path to .env config file")
    parser.add_argument("--profile", help="FineBI config profile in .env, e.g. cn or jp")
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT_DIR, help="Directory for exported files")
    args = parser.parse_args()

    config = load_config(args.config, args.profile)
    client = FineBIClient(config)

    public_tree_payload = client.get_json("/webroot/decision/v10/view/entry/tree")
    public_tree = public_tree_payload.get("data") if isinstance(public_tree_payload, dict) else public_tree_payload
    entry_node, _entry_ancestors = locate_public_entry(public_tree, args.entry)
    public_source_path = entry_node.get("path") or ""

    report_tree_payload = client.get_json("/webroot/decision/v5/platform/dashboard/reports/tree")
    report_tree = report_tree_payload.get("data") if isinstance(report_tree_payload, dict) else report_tree_payload
    subject_node, subject_ancestors, subject_path_parts = locate_subject(report_tree, args.entry, public_source_path)
    reports = list_reports(subject_node)

    print(f"public_entry={args.entry}")
    print(f"public_entry_id={entry_node.get('id')}")
    print(f"public_template_id={entry_node.get('templateId') or ''}")
    print(f"source_path={public_source_path}")
    print(f"subject_id={subject_node.get('id')}")
    print(f"subject_path={'/'.join(subject_path_parts)}")

    if args.list:
        print("reports:")
        for report in reports:
            report_id = report.get("id") or report.get("reportId") or report.get("templateId")
            print(f"- {report.get('name') or report.get('text')}: {report_id}")
        return 0

    if not args.report:
        raise SystemExit("missing --report; use --list to inspect available dashboard tabs")

    target = None
    for report in reports:
        if (report.get("name") or report.get("text")) == args.report:
            target = report
            break
    if target is None:
        available = ", ".join(str(report.get("name") or report.get("text")) for report in reports)
        raise SystemExit(f"dashboard tab not found: {args.report}. Available: {available}")

    report_id = target.get("id") or target.get("reportId") or target.get("templateId")
    report_name = target.get("name") or target.get("text") or args.report
    if not report_id:
        raise SystemExit("target dashboard tab does not contain reportId")

    status, content_type, body = client.get_bytes(
        "/webroot/decision/v5/api/dashboard/report/export/excel",
        {"reportId": str(report_id)},
    )
    is_xlsx = body[:4] == b"PK\x03\x04"
    print(f"report_name={report_name}")
    print(f"report_id={report_id}")
    print(f"export_status={status}")
    print(f"content_type={content_type}")
    print(f"bytes={len(body)}")
    print(f"xlsx={is_xlsx}")
    if not is_xlsx:
        preview = body[:500].decode("utf-8", "replace").replace("\n", " ")
        raise SystemExit(f"export failed or did not return xlsx: {preview}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.out_dir / (
        safe_filename(args.entry) + "_" + safe_filename(report_name) + "_" + str(report_id) + "_export.xlsx"
    )
    output_path.write_bytes(body)
    print(f"saved={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
