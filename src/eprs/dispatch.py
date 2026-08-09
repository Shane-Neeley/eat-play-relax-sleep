"""Safe queue dispatch preparation for external agent runners."""

from __future__ import annotations

from pathlib import Path

from .context import build_agent_context
from .system import load_song_manifest, utc_now
from .work import claim_next_work_item, load_work_item, release_work_item


DISPATCH_SCHEMA = "eprs.agent-dispatch/v1"
MAX_RELEASE_REASON_CHARS = 2_000


def _release_reason(prefix: str, details: str) -> str:
    clean = " ".join(details.split())
    reason = f"Agent dispatch preparation failed: {prefix}"
    if clean:
        reason += f": {clean}"
    return reason[:MAX_RELEASE_REASON_CHARS]


def _response_contract(
    song: Path, item: dict, run_number: int, agent: str
) -> dict:
    result_contract = item.get("result_contract")
    required_roles = (
        list(result_contract.get("required_roles", []))
        if isinstance(result_contract, dict)
        else []
    )
    return {
        "work_item": item["id"],
        "run_number": run_number,
        "agent": agent,
        "finish": {
            "command": "work finish",
            "required": ["summary", "decision", "one or more role-labeled result files"],
            "decisions": ["complete", "needs-followup", "stop"],
            "required_result_roles": required_roles,
            "required_result_roles_apply_to_decision": "complete",
            "additional_result_roles_allowed": True,
        },
        "release": {
            "command": "work release",
            "required": ["same agent name", "non-empty reason"],
        },
        "song": str(song),
    }


def _authority() -> dict:
    return {
        "statement": (
            "This bundle claims and prepares local work only; it does not launch an agent "
            "or expand the current user's authorization."
        ),
        "does_not_authorize": [
            "network access or browsing",
            "uploading, publishing, sending, or remote control",
            "audio processing not explicitly requested by the work item",
            "creative approval, consent, rights, listening, technical, upload, or publication gates",
        ],
        "raw_recordings_immutable": True,
    }


def dispatch_next_work(
    song: str | Path,
    agent: str,
    *,
    kind: str | None = None,
    now: str | None = None,
    max_text_bytes: int = 65_536,
    toolchain_extensions: list[str | Path] | None = None,
    adapter_profile_directories: list[str | Path] | None = None,
) -> dict:
    """Claim due work and return verified context, or release a failed preparation."""
    song_path = Path(song)
    load_song_manifest(song_path)
    claim = claim_next_work_item(song_path, agent, kind=kind, now=now)
    claimed = claim["claimed"]
    base = {
        "schema": DISPATCH_SCHEMA,
        "generated_at": utc_now(),
        "agent": claim["agent"],
        "kind_filter": claim["kind_filter"],
        "authority": _authority(),
        "claim": claim,
    }
    if claimed is None:
        return {
            **base,
            "status": "idle",
            "context": None,
            "release": None,
            "response_contract": None,
        }

    item_id = claimed["id"]
    run_number = claimed["run_number"]
    try:
        context = build_agent_context(
            song_path,
            purpose=f"Execute only claimed work item {item_id}, run {run_number}.",
            work=item_id,
            work_run=run_number,
            verify=True,
            max_text_bytes=max_text_bytes,
            toolchain_extensions=toolchain_extensions,
            adapter_profile_directories=adapter_profile_directories,
        )
        attention = context.get("attention")
        if not isinstance(attention, list):
            raise ValueError("verified agent context has an invalid attention field")
        fit = context.get("adapter_fit")
        if fit is not None:
            if not isinstance(fit, dict) or not isinstance(fit.get("ready"), bool):
                raise ValueError("verified agent context has an invalid adapter fit")
            if not fit["ready"]:
                unavailable = [
                    *fit.get("missing_capabilities", []),
                    *fit.get("unknown_capabilities", []),
                ]
                reason = _release_reason(
                    "required software capabilities unavailable",
                    ", ".join(map(str, unavailable)),
                )
                release_work_item(song_path, item_id, claim["agent"], reason)
                _, released_item = load_work_item(song_path, item_id)
                return {
                    **base,
                    "status": "released",
                    "context": context,
                    "release": {
                        "reason": reason,
                        "work_status": released_item["status"],
                        "run_number": run_number,
                    },
                    "response_contract": None,
                }
        if attention:
            reason = _release_reason("verified context requires attention", "; ".join(map(str, attention)))
            release_work_item(song_path, item_id, claim["agent"], reason)
            _, released_item = load_work_item(song_path, item_id)
            return {
                **base,
                "status": "released",
                "context": context,
                "release": {
                    "reason": reason,
                    "work_status": released_item["status"],
                    "run_number": run_number,
                },
                "response_contract": None,
            }
    except Exception as exc:
        reason = _release_reason(type(exc).__name__, str(exc))
        try:
            release_work_item(song_path, item_id, claim["agent"], reason)
            _, released_item = load_work_item(song_path, item_id)
        except Exception as release_exc:
            raise RuntimeError(
                f"dispatch preparation failed for {item_id}, and its claim could not be released: "
                f"{release_exc}"
            ) from release_exc
        return {
            **base,
            "status": "released",
            "context": None,
            "release": {
                "reason": reason,
                "work_status": released_item["status"],
                "run_number": run_number,
            },
            "response_contract": None,
        }

    return {
        **base,
        "status": "ready",
        "context": context,
        "release": None,
        "response_contract": _response_contract(
            song_path,
            load_work_item(song_path, item_id)[1],
            run_number,
            claim["agent"],
        ),
    }
