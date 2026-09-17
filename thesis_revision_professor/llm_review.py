"""Optional LLM-assisted semantic review via an OpenAI-compatible chat API.

Core package stays dependency-free: this module only uses the standard library
and only runs when the operator explicitly sets THESIS_REVIEW_API_KEY. The
output is a semantic_findings.json payload with exactly the same schema as a
manual semantic review, so merge-semantic cannot tell the difference.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from .review_engine import partition_semantic_findings


API_BASE_ENV = "THESIS_REVIEW_API_BASE"
API_KEY_ENV = "THESIS_REVIEW_API_KEY"
MODEL_ENV = "THESIS_REVIEW_MODEL"
DEFAULT_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
REQUEST_TIMEOUT = 120


class LlmReviewError(RuntimeError):
    pass


SYSTEM_PROMPT = """你是一项中文学位论文审查工作流中的语义审查辅助角色。规则：
1. 只依据请求中给出的定位文本与材料审查；证据不足时必须弃权（少输出或空列表），不得虚构数据、引用或结论。
2. 输出必须是 JSON：一个 finding 对象数组，每个对象恰好包含 output_schema 中的字段。
3. 必填字段：rule_id、reviewer、locator、severity(P0/P1/P2)、confidence(0到1)、finding、rationale、counterevidence、recommended_action、acceptance_test；claim_ids 与 evidence_ids 为数组，requires_author_confirmation 为布尔。
4. locator 必须使用请求中给出的 word/document.xml#para=... 形式。
5. 不要重复确定性预检已覆盖的意见，除非你能提供更具体的语义依据。
6. 你的输出会被程序严格校验；格式不合法的 finding 会被整条拒收。除 JSON 外不要输出任何其他文字。"""


def load_request(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("reviewer_roles"), list):
        raise LlmReviewError(f"{path} 不是合法的 semantic_review_request.json(缺少 reviewer_roles)")
    return payload


def build_user_message(request: dict, role: str) -> str:
    slim = {
        "task": request.get("task"),
        "your_role": role,
        "instructions": request.get("instructions", []),
        "loop_rounds": request.get("loop_rounds", {}),
        "output_schema": request.get("output_schema", {}),
        "document": request.get("document", {}),
        "claim_graph": request.get("claim_graph", {}),
        "selected_strategy": request.get("selected_strategy", {}),
        "deterministic_review": request.get("deterministic_review", {}),
        "claim_evidence_ledger": request.get("claim_evidence_ledger", {}),
        "consistency_matrix": request.get("consistency_matrix", {}),
        "profile_audit": request.get("profile_audit", {}),
    }
    return json.dumps(slim, ensure_ascii=False)


def chat_completion(api_base: str, api_key: str, model: str, messages: list[dict]) -> dict:
    url = api_base.rstrip("/") + "/chat/completions"
    body = json.dumps({"model": model, "messages": messages, "temperature": 0.2}).encode("utf-8")
    http_request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(http_request, timeout=REQUEST_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
    raise LlmReviewError(f"调用 {url} 失败(已重试一次):{last_error}")


def extract_findings(text: str) -> list[dict]:
    """Tolerant JSON extraction: accept fenced or bare JSON arrays/objects."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    decoder = json.JSONDecoder()
    for candidate in (cleaned, cleaned[cleaned.find("[") :] if "[" in cleaned else cleaned):
        try:
            parsed, _end = decoder.raw_decode(candidate.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict) and isinstance(parsed.get("findings"), list):
            return [item for item in parsed["findings"] if isinstance(item, dict)]
    raise LlmReviewError("模型输出无法解析为 finding JSON 数组")


def run_llm_review(request_path: str | Path, out_path: str | Path) -> dict:
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    if not api_key:
        raise LlmReviewError(f"未设置 {API_KEY_ENV};llm-review 需要显式提供 API key,不联网时仍可按 references/semantic-review-protocol.md 手动产出 semantic_findings.json")
    api_base = os.environ.get(API_BASE_ENV, DEFAULT_API_BASE).strip() or DEFAULT_API_BASE
    model = os.environ.get(MODEL_ENV, DEFAULT_MODEL).strip() or DEFAULT_MODEL
    request = load_request(request_path)

    role_status = []
    raw_findings: list[dict] = []
    failures = []
    for role in request["reviewer_roles"]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(request, str(role))},
        ]
        try:
            completion = chat_completion(api_base, api_key, model, messages)
            content = completion["choices"][0]["message"]["content"]
            findings = extract_findings(content)
        except (LlmReviewError, KeyError, IndexError, TypeError) as error:
            failures.append({"role": str(role), "error": str(error)})
            role_status.append({"role": str(role), "status": "failed", "error": str(error)})
            continue
        for finding in findings:
            finding.setdefault("reviewer", str(role))
        raw_findings.extend(findings)
        role_status.append({"role": str(role), "status": "ok", "finding_count": len(findings)})

    accepted, rejected = partition_semantic_findings({"findings": raw_findings})
    if not role_status or all(entry["status"] == "failed" for entry in role_status):
        raise LlmReviewError(f"所有审查角色均调用失败,不产出不合格式文件:{failures}")

    payload = {
        "schema_version": "4.0",
        "task": "independent_semantic_professor_review",
        "generated_by": "thesis-review llm-review",
        "model": model,
        "api_base": api_base,
        "findings": accepted,
        "rejected_findings": rejected,
        "role_status": role_status,
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "semantic_findings": str(out),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "roles_ok": sum(entry["status"] == "ok" for entry in role_status),
        "roles_failed": sum(entry["status"] == "failed" for entry in role_status),
        "partial": bool(failures),
    }
