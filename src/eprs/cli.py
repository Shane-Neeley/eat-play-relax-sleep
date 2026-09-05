"""Command-line interface for Eat Play Relax Sleep."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .adapters import adapter_catalog, adapter_guide
from .audio import render
from .autotune import PRESETS as AUTOTUNE_PRESETS, render_autotune, settings_for
from .beat import dumps, load, mutate
from .bioacoustic_detector import (
    BEHAVIORS,
    DEFAULT_PULSE_MAX_GAP_SECONDS,
    DEFAULT_PULSE_MIN_COUNT,
    DEFAULT_PULSE_MIN_FLUX_Z,
    DEFAULT_PULSE_MIN_GAP_SECONDS,
    DEFAULT_SUSTAINED_MIN_SNR_DB,
    DEFAULT_MAX_DURATION_SECONDS,
    detect_audio,
    write_detection_report,
)
from .bioacoustic_models import bioacoustic_model_catalog
from .context import build_agent_context, render_agent_context_markdown, write_agent_context
from .clearance import create_recording_clearance, load_recording_clearance
from .chatcut import prepare_chatcut_handoff
from .comp import render_comp, review_comp
from .delivery import approve_youtube_video, render_youtube
from .distribution import package_distribution
from .dispatch import (
    accept_agent_response,
    dispatch_next_work,
    initialize_agent_response,
    write_dispatch_packet,
)
from .daw_return import capture_daw_return
from .frontdoor import expose_current_media
from .frontier import load_frontier_watch
from .groove import create_groove_development, review_groove, verify_groove_development
from .harness import create_song_run
from .interchange import prepare_daw_interchange, verify_daw_interchange
from .inaturalist_audio import download_inaturalist_sound
from .inaturalist_photo import download_inaturalist_photo
from .inaturalist_study import study_inaturalist_sound
from .source_audit import (
    audit_inaturalist_sound,
    record_source_verification,
    write_source_audit_report,
)
from .master import approve_master, render_master
from .manifest import (
    add_manifest_note,
    add_method_record,
    build_song_method_manifest,
    command_path as manifest_command_path,
    compare_song_method_manifests,
    record_cli_event,
    resolve_song_from_args,
    should_record_command,
    snapshot_song,
    verify_song_method_manifest,
)
from .mix import render_mix, review_mix
from .musical_observation import observe_musical_performance
from .lyrics import create_lyric_development, load_lyric_development, review_lyric_variant
from .performance import compare_performances, review_comparison
from .phase import observe_phase_relationship
from .pedalboard_fx import render_pedalboard, review_pedalboard
from .picture import capture_picture, review_picture, verify_picture
from .plan import create_production_plan, load_production_plan
from .plan_progress import production_plan_progress, queue_next_plan_step
from .planning import (
    accept_plan_work_result,
    list_plan_acceptances,
    verify_plan_acceptance,
)
from .process import render_process, review_processed_stem
from .production_map import write_production_map
from .publication import prepare_publication_handoff, record_publication_receipt
from .quality import approve_creative_quality, write_quality_report
from .release import package_release
from .research import create_research_record, load_research_record
from .runtime import format_performance_report, performance_report
from .runner import load_runner_profile, run_agent_profile, verify_runner_receipt
from .request import (
    DEFAULT_RIGHTS_NOTE,
    capture_production_request,
    create_production_request,
    load_production_request,
)
from .selection import select_audio
from .rhythm import observe_rhythm
from .session import create_recording_session, load_recording_session
from .shotcut import (
    compile_shotcut_project,
    open_shotcut_project,
    prepare_shotcut_project,
    render_shotcut_project,
)
from .source_sketch import create_source_sketch
from .system import (
    analyze,
    create_experiment,
    doctor,
    finish_experiment,
    format_song_status,
    ingest,
    new_song,
    song_status,
)
from .visualize import svg
from .video_quality import write_video_quality_report
from .visuals import render_visual, write_prompt_score
from .vgpu import render_vgpu
from .work import (
    claim_next_work_item,
    create_work_item,
    finish_work_item,
    list_work_items,
    load_work_item,
    promote_work_run,
    release_work_item,
    start_work_item,
)
from .youtube_assets import (
    create_youtube_asset_bundle,
    review_youtube_asset_bundle,
    verify_youtube_asset_bundle,
)


def source_spec(value: str) -> tuple[str, str]:
    """Parse a repeatable ROLE=PATH source argument."""
    role, separator, path = value.partition("=")
    if not separator or not role.strip() or not path.strip():
        raise argparse.ArgumentTypeError("source must use ROLE=PATH, for example 'family voices=take.wav'")
    return role.strip(), path.strip()


def json_object(value: str) -> dict:
    """Parse one repeatable JSON object used by structured CLI handoffs."""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"expected JSON object: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("expected a JSON object")
    return parsed


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="eprs", description="Local-first code + music production system")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    from .producer import add_parser
    add_parser(commands)
    doctor_cmd = commands.add_parser("doctor", help="Inspect required and optional creative tools")
    doctor_cmd.add_argument(
        "--strict",
        action="store_true",
        help="Exit nonzero when core or requested workflow requirements are unavailable",
    )
    doctor_cmd.add_argument(
        "--workflow",
        action="append",
        default=[],
        help="Require one named workflow profile; repeat to combine profiles",
    )
    doctor_cmd.add_argument(
        "--capability",
        action="append",
        default=[],
        help="Require one exact capability; repeat to compose an ad hoc workflow",
    )
    doctor_cmd.add_argument(
        "--extension",
        action="append",
        help="Add one private eprs.toolchain-extension/v1 file; repeat as needed",
    )

    adapter = commands.add_parser(
        "adapter",
        help="Discover safe handoff guides for detected creative software",
    )
    adapter_commands = adapter.add_subparsers(dest="adapter_command", required=True)
    adapter_list = adapter_commands.add_parser(
        "list",
        help="List validated software adapters and provider availability",
    )
    adapter_list.add_argument(
        "--available",
        action="store_true",
        help="Show only adapters whose provider is detected on this machine",
    )
    adapter_list.add_argument(
        "--capability",
        action="append",
        default=[],
        help="Require one capability from the same adapter; repeat to narrow",
    )
    adapter_list.add_argument(
        "--workflow",
        action="append",
        default=[],
        help="Show adapters that contribute at least one capability to a named workflow",
    )
    adapter_list.add_argument(
        "--toolchain-extension",
        action="append",
        help="Add one private toolchain extension; repeat as needed",
    )
    adapter_list.add_argument(
        "--profile-dir",
        action="append",
        help="Add one private adapter-profile directory; repeat as needed",
    )
    adapter_show = adapter_commands.add_parser(
        "show",
        help="Show one complete adapter guide without starting or controlling the tool",
    )
    adapter_show.add_argument("adapter")
    adapter_show.add_argument(
        "--handoff",
        help="Return one exact handoff from the adapter profile",
    )
    adapter_show.add_argument(
        "--toolchain-extension",
        action="append",
        help="Add one private toolchain extension; repeat as needed",
    )
    adapter_show.add_argument(
        "--profile-dir",
        action="append",
        help="Add one private adapter-profile directory; repeat as needed",
    )

    chatcut = commands.add_parser(
        "chatcut",
        help="Prepare a local disposable handoff for an explicitly operated ChatCut visual pass",
    )
    chatcut_commands = chatcut.add_subparsers(dest="chatcut_command", required=True)
    chatcut_prepare = chatcut_commands.add_parser(
        "prepare",
        help="Create a derived preview, guide assets, and a reviewable ChatCut manifest",
    )
    chatcut_prepare.add_argument("song", help="EPRS song workspace containing song.json")
    chatcut_prepare.add_argument("--video", required=True, help="Song-relative video candidate")
    chatcut_prepare.add_argument("--audio", help="Optional song-relative guide/master audio")
    chatcut_prepare.add_argument("--captions", help="Optional song-relative captions file")
    chatcut_prepare.add_argument("--thumbnail", help="Optional song-relative thumbnail")
    chatcut_prepare.add_argument("--prompt", help="Exact visual-editing prompt for the operator")
    chatcut_prepare.add_argument("--seconds", type=int, default=30)
    chatcut_prepare.add_argument("--resolution", type=int, choices=(480, 720, 1080), default=720)
    chatcut_prepare.add_argument("--out", help="Optional output directory inside the song workspace")

    shotcut = commands.add_parser(
        "shotcut",
        help="Create a local, editable Shotcut/MLT project from derived EPRS media",
    )
    shotcut_commands = shotcut.add_subparsers(dest="shotcut_command", required=True)
    shotcut_prepare = shotcut_commands.add_parser(
        "prepare",
        help="Create a beat-mapped MLT project, title layer, asset package, and timeline record",
    )
    shotcut_prepare.add_argument("song", help="EPRS song workspace")
    shotcut_prepare.add_argument("--title", required=True, help="Project title")
    shotcut_prepare.add_argument(
        "--segment", action="append", type=json_object, required=True,
        help='Video segment JSON, e.g. \'{"video":"video/candidate.mp4","start_seconds":0,"duration_seconds":4}\'',
    )
    shotcut_prepare.add_argument("--audio", required=True, help="Guide/master WAV inside the repository")
    shotcut_prepare.add_argument(
        "--title-cue", action="append", type=json_object, default=[],
        help='Optional title cue JSON, e.g. \'{"start_seconds":0,"duration_seconds":2,"text":"HOOK"}\'',
    )
    shotcut_prepare.add_argument(
        "--marker", action="append", type=json_object, default=[],
        help='Optional musical marker JSON, e.g. \'{"time_seconds":0,"label":"INTRO"}\'',
    )
    shotcut_prepare.add_argument("--out", help="Optional output directory inside the song workspace")
    shotcut_compile = shotcut_commands.add_parser(
        "compile",
        help="Compile an eprs.shotcut-project/v1 score into validated editable MLT XML",
    )
    shotcut_compile.add_argument("spec")
    shotcut_compile.add_argument("--song", required=True)
    shotcut_render = shotcut_commands.add_parser(
        "render",
        help="Render one prepared MLT project through Shotcut's bundled melt",
    )
    shotcut_render.add_argument("project")
    shotcut_render.add_argument("--song", required=True)
    shotcut_render.add_argument("--out", required=True)
    shotcut_render.add_argument("--quality", choices=("draft", "full"), default="full")
    shotcut_open = shotcut_commands.add_parser(
        "open",
        help="Open one prepared MLT project in isolated local Shotcut app data",
    )
    shotcut_open.add_argument("project")
    shotcut_open.add_argument("--song", required=True)

    new = commands.add_parser("new", help="Create a safe local song workspace (Git-ignored by default)")
    new.add_argument("title")
    new.add_argument("--root", default="songs")

    make_song = commands.add_parser(
        "make-song",
        help="Start an agent-led song from a prompt and explicitly classified local material",
    )
    make_song.add_argument("title", nargs="?", help="New song title; omit when using --song")
    make_song.add_argument("--song", help="Add a new run to an existing song workspace")
    make_song.add_argument("--root", default="songs", help="Parent directory for a new song")
    make_song.add_argument("--prompt", required=True, help="Plain-English musical direction")
    make_song.add_argument("--seed", type=int, help="Explicit seed for an exact diagnostic replay")
    make_song.add_argument(
        "--recording", action="append", type=source_spec, default=[], metavar="ROLE=PATH",
        help="Immutable supplied audio/video performance; repeat as needed",
    )
    make_song.add_argument(
        "--evidence", action="append", type=source_spec, default=[], metavar="ROLE=PATH",
        help="Frozen supporting file such as lyrics, an image, or a downloaded reference; repeat as needed",
    )
    make_song.add_argument("--reference", action="append", default=[], help="URL or creative lead; repeat as needed")
    make_song.add_argument("--preserve", action="append", default=[], help="What the agent must protect; repeat as needed")
    make_song.add_argument("--avoid", action="append", default=[], help="What the agent must avoid; repeat as needed")
    make_song.add_argument("--question", action="append", default=[], help="Open musical question; repeat as needed")
    make_song.add_argument("--rights-note", default=DEFAULT_RIGHTS_NOTE)
    make_song.add_argument("--no-visual", action="store_true", help="Skip the optional local visual preview")
    make_song.add_argument("--visual-seconds", type=float, default=8.0, help="Length of the optional visual preview")

    source_sketch = commands.add_parser(
        "source-sketch",
        help="Make a fresh reversible arrangement from recordings captured by make-song",
    )
    source_sketch.add_argument("song")
    source_sketch.add_argument("--run", help="Run id or song-relative run.json; defaults to latest")
    source_sketch.add_argument("--intent", required=True, help="Player-facing relationship this pass should test")
    source_sketch.add_argument("--seed", type=int, help="Explicit seed for exact diagnostic replay")
    source_sketch.add_argument(
        "--shape", choices=("one-pass", "call-response", "loop"), default="one-pass",
        help="Explicit occurrence shape; repeats/excerpts are never inferred from prompt text",
    )
    source_sketch.add_argument("--no-bed", action="store_true", help="Arrange supplied recordings without the synthetic starter underneath")
    source_sketch.add_argument(
        "--observation", action="append", default=[],
        help="Exact song-local eprs observe artifact to use for phrase boundaries; repeat as needed",
    )
    source_sketch.add_argument("--no-visual", action="store_true", help="Skip the optional source-synced visual preview")
    source_sketch.add_argument("--visual-seconds", type=float, default=8.0, help="Length of the optional source-synced visual preview")

    status = commands.add_parser("status", help="Summarize a song workspace and its next safe actions")
    status.add_argument("song")
    status.add_argument("--json", action="store_true", help="Emit the versioned machine-readable status")
    status.add_argument("--verify", action="store_true", help="Hash raw, input, and result evidence to detect drift")

    performance = commands.add_parser(
        "performance",
        help="Inspect EPRS renderer workers and recent visual timing without changing state",
    )
    performance.add_argument("--song", help="Include recent visual-render timing for one song")
    performance.add_argument(
        "--stale-seconds", type=int, default=900,
        help="Age at which an orphaned browser root needs attention (default: 900)",
    )
    performance.add_argument("--json", action="store_true", help="Emit the versioned machine-readable report")

    production_map = commands.add_parser(
        "map",
        help="Draw an inspectable request-to-output map for an agent-led song run",
    )
    production_map.add_argument("song")
    production_map.add_argument("--run", help="Run id or song-relative run.json; defaults to latest")
    production_map.add_argument("--out", help="Song-relative .dot output; defaults beside the run manifest")
    production_map.add_argument("--no-svg", action="store_true", help="Write portable DOT without invoking Graphviz")

    context = commands.add_parser(
        "context",
        help="Build a bounded local context packet for a person, agent, or automation",
    )
    context.add_argument("song")
    context.add_argument("--purpose", default="", help="Current handoff purpose or request")
    context.add_argument("--request", help="Focus one captured production-request id or path")
    context.add_argument("--work", help="Focus one work-item id or path")
    context.add_argument("--work-run", type=int, help="Focused work run number; defaults to current")
    context.add_argument("--experiment", help="Focus one experiment id or path")
    context.add_argument("--verify", action="store_true", help="Hash referenced evidence and report drift")
    context.add_argument("--max-text-bytes", type=int, default=65_536)
    context.add_argument("--format", choices=("json", "markdown"), default="json")
    context.add_argument("--out", help="Write a new packet instead of printing to stdout")
    context.add_argument(
        "--toolchain-extension",
        action="append",
        help="Add one private toolchain extension to context discovery",
    )
    context.add_argument(
        "--profile-dir",
        action="append",
        help="Add one private adapter-profile directory to context discovery",
    )

    dispatch = commands.add_parser(
        "dispatch",
        help="Claim due work and prepare a verified agent-ready context bundle",
    )
    dispatch_commands = dispatch.add_subparsers(dest="dispatch_command", required=True)
    dispatch_next = dispatch_commands.add_parser(
        "next",
        help="Return idle, ready, or explicitly released eprs.agent-dispatch/v1 JSON",
    )
    dispatch_next.add_argument("--song", required=True)
    dispatch_next.add_argument("--agent", required=True)
    dispatch_next.add_argument("--kind", help="Claim only an exact case-insensitive work kind")
    dispatch_next.add_argument("--now", help="Evaluate due state at an explicit ISO 8601 time")
    dispatch_next.add_argument("--max-text-bytes", type=int, default=65_536)
    dispatch_next.add_argument(
        "--allow-network-research",
        action="store_true",
        help="Explicitly permit read-only browsing for this claimed task; never permits remote mutation or publication",
    )
    dispatch_next.add_argument(
        "--out",
        help="Write a ready packet to a new JSON file; idle or released responses remain on stdout",
    )
    dispatch_next.add_argument(
        "--toolchain-extension",
        action="append",
        help="Add one private toolchain extension to dispatched context",
    )
    dispatch_next.add_argument(
        "--profile-dir",
        action="append",
        help="Add one private adapter-profile directory to dispatched context",
    )
    dispatch_accept = dispatch_commands.add_parser(
        "accept",
        help="Validate an eprs.agent-response/v1 and freeze its packet, response, and results",
    )
    dispatch_accept.add_argument("response")
    dispatch_accept.add_argument("--packet", required=True)
    dispatch_accept.add_argument("--song", required=True)
    dispatch_response_init = dispatch_commands.add_parser(
        "response-init",
        help="Create a new response skeleton bound to one exact ready packet",
    )
    dispatch_response_init.add_argument("--packet", required=True)
    dispatch_response_init.add_argument("--out", required=True)

    runner = commands.add_parser(
        "runner",
        help="Validate or execute an explicit packet/response agent profile in a mandatory OS sandbox",
    )
    runner_commands = runner.add_subparsers(dest="runner_command", required=True)
    runner_validate = runner_commands.add_parser(
        "validate", help="Validate a shell-free eprs.runner-profile/v1"
    )
    runner_validate.add_argument("profile")
    runner_run = runner_commands.add_parser(
        "run", help="Run one ready dispatch packet with network and host writes denied"
    )
    runner_run.add_argument("profile")
    runner_run.add_argument("--packet", required=True)
    runner_run.add_argument("--song", required=True)
    runner_show = runner_commands.add_parser(
        "show", help="Verify and show one preserved agent-runner receipt"
    )
    runner_show.add_argument("receipt")
    runner_show.add_argument("--song", required=True)

    check = commands.add_parser("check", help="Parse and validate a .beat file")
    check.add_argument("beat")

    quality = commands.add_parser(
        "quality",
        help="Run the deterministic creative-form and publication-risk preflight",
    )
    quality.add_argument("beat")
    quality.add_argument("--song", required=True)
    quality.add_argument("--out", required=True, help="Song-relative quality report path")

    video_quality = commands.add_parser(
        "video-quality",
        help="Sample a video with optional OpenCV focus, contrast, motion, crop, and thumbnail evidence",
    )
    video_quality.add_argument("video")
    video_quality.add_argument("--out", required=True, help="JSON report path")
    video_quality.add_argument("--max-frames", type=int, default=18)
    video_quality.add_argument("--min-sharpness", type=float, default=2.0)
    video_quality.add_argument("--min-contrast", type=float, default=18.0)
    video_quality.add_argument("--target-width", type=int)
    video_quality.add_argument("--target-height", type=int)
    video_quality.add_argument("--max-crop-fraction", type=float, default=0.40)

    quality_approve = commands.add_parser(
        "quality-approve",
        help="Record explicit human approval for a held creative-quality report",
    )
    quality_approve.add_argument("report")
    quality_approve.add_argument("--song", required=True)
    quality_approve.add_argument("--approval-note", required=True)

    render_cmd = commands.add_parser("render", help="Render a .beat prototype to 48 kHz stereo WAV")
    render_cmd.add_argument("beat")
    render_cmd.add_argument("--out", required=True)

    view = commands.add_parser("visualize", help="Render a rhythm map to SVG")
    view.add_argument("beat")
    view.add_argument("--out", required=True)

    variation = commands.add_parser("mutate", help="Create a deterministic, restrained rhythm variation")
    variation.add_argument("beat")
    variation.add_argument("--seed", type=int, required=True)
    variation.add_argument("--amount", type=float, default=0.08)
    variation.add_argument("--out", required=True)

    intake = commands.add_parser("ingest", help="Copy an irreplaceable source into immutable raw intake with provenance")
    intake.add_argument("source")
    intake.add_argument("--song", required=True)
    intake.add_argument(
        "--role", "--instrument", dest="role", required=True,
        help="Musical role or source kind, such as guitar, family voice, boom-clap idea, chimes, or room sound",
    )
    intake.add_argument("--note", default="")
    intake.add_argument(
        "--rights-note",
        default="rights and performer permissions not yet confirmed; do not publish",
        help="Known ownership/permission context; uncertainty should remain explicit",
    )

    inaturalist = commands.add_parser(
        "inaturalist",
        help="Freeze iNaturalist media as attributed song-local reference evidence",
    )
    inaturalist_commands = inaturalist.add_subparsers(dest="inaturalist_command", required=True)
    inaturalist_sound = inaturalist_commands.add_parser(
        "sound",
        help="Download one public iNaturalist observation sound without treating it as permission",
    )
    inaturalist_sound.add_argument("observation_id", type=int)
    inaturalist_sound.add_argument("--song", required=True)
    inaturalist_sound.add_argument("--role", required=True, help="Reference role, such as forest call")
    inaturalist_sound.add_argument("--sound-id", type=int, help="Required when the observation has multiple sounds")
    inaturalist_sound.add_argument("--note", default="")
    inaturalist_sound.add_argument("--user-agent", default=None)
    inaturalist_photo = inaturalist_commands.add_parser(
        "photo",
        help="Download one reusable observation photo with license and attribution evidence",
    )
    inaturalist_photo.add_argument("observation_id", type=int)
    inaturalist_photo.add_argument("--song", required=True)
    inaturalist_photo.add_argument("--role", required=True, help="Visual role, such as marsh texture")
    inaturalist_photo.add_argument("--photo-id", type=int, help="Required when the observation has multiple photos")
    inaturalist_photo.add_argument(
        "--size", choices=("small", "medium", "large", "original"), default="large"
    )
    inaturalist_photo.add_argument("--note", default="")
    inaturalist_photo.add_argument("--user-agent", default=None)
    inaturalist_study = inaturalist_commands.add_parser(
        "study",
        help="Measure a frozen iNaturalist sound and map it to creative cues",
    )
    inaturalist_study.add_argument("source", help="Frozen sound path, usually under references/inaturalist-audio")
    inaturalist_study.add_argument("--song", required=True)
    inaturalist_study.add_argument("--role", required=True, help="Study role, such as frog rhythm reference")
    inaturalist_study.add_argument("--key", default="C")
    inaturalist_study.add_argument("--scale", default="minor-pentatonic")
    inaturalist_study.add_argument("--tempo-bpm", type=float)
    inaturalist_study.add_argument("--note", default="")
    inaturalist_audit = inaturalist_commands.add_parser(
        "audit",
        help="Rank bounded raw-audio windows before a human verifies the named call",
    )
    inaturalist_audit.add_argument(
        "source",
        help="Frozen sound path, usually under references/inaturalist-audio",
    )
    inaturalist_audit.add_argument("--song", required=True)
    inaturalist_audit.add_argument(
        "--out",
        help="Optional JSON report destination; existing files are never overwritten",
    )
    inaturalist_audit.add_argument("--max-candidates", type=int, default=6)
    inaturalist_verify = inaturalist_commands.add_parser(
        "verify-window",
        help="Record a human listening attestation for one ranked raw-audio window",
    )
    inaturalist_verify.add_argument("audit_report")
    inaturalist_verify.add_argument("--out", required=True)
    inaturalist_verify.add_argument("--start", type=float, required=True)
    inaturalist_verify.add_argument("--end", type=float, required=True)
    inaturalist_verify.add_argument("--what-was-heard", required=True)
    inaturalist_verify.add_argument("--reviewer", required=True)
    inaturalist_commands.add_parser(
        "models",
        help="List current optional bioacoustic AI models and their boundaries",
    )

    bioacoustic = commands.add_parser(
        "bioacoustic",
        help="Rank reviewable animal-sound regions in a field recording",
    )
    bioacoustic_commands = bioacoustic.add_subparsers(
        dest="bioacoustic_command", required=True
    )
    bioacoustic_detect = bioacoustic_commands.add_parser(
        "detect",
        help="Fuse acoustic shape with optional species/reference evidence",
    )
    bioacoustic_detect.add_argument("source", help="Audio file to analyze; source is never modified")
    bioacoustic_detect.add_argument("--out", help="Optional JSON report destination")
    bioacoustic_detect.add_argument(
        "--species-table",
        help="Time-aligned species table used as a required target interval",
    )
    bioacoustic_detect.add_argument(
        "--reference",
        help="Optional same-taxon recording for nearest-event similarity",
    )
    bioacoustic_detect.add_argument("--species", default="Dryocopus pileatus")
    bioacoustic_detect.add_argument("--species-model", default="selection-table")
    bioacoustic_detect.add_argument(
        "--behavior",
        choices=BEHAVIORS,
        default="transient",
        help="Target an isolated sound, repeated pulses, or a sustained call",
    )
    bioacoustic_detect.add_argument(
        "--pulse-min-count", type=int, default=DEFAULT_PULSE_MIN_COUNT
    )
    bioacoustic_detect.add_argument(
        "--pulse-min-gap", type=float, default=DEFAULT_PULSE_MIN_GAP_SECONDS,
        help="Minimum seconds between pulse peaks",
    )
    bioacoustic_detect.add_argument(
        "--pulse-max-gap", type=float, default=DEFAULT_PULSE_MAX_GAP_SECONDS,
        help="Maximum seconds between pulse peaks",
    )
    bioacoustic_detect.add_argument(
        "--pulse-min-flux-z", type=float, default=DEFAULT_PULSE_MIN_FLUX_Z,
        help="Minimum robust spectral-flux score for each pulse",
    )
    bioacoustic_detect.add_argument(
        "--sustained-min-snr-db", type=float, default=DEFAULT_SUSTAINED_MIN_SNR_DB,
        help="Minimum call energy above the recording's noise floor",
    )
    bioacoustic_detect.add_argument(
        "--max-duration-seconds", type=float, default=DEFAULT_MAX_DURATION_SECONDS,
        help="Hard analysis bound; trim a lossless region before analyzing longer files",
    )
    bioacoustic_detect.add_argument("--max-events", type=int, default=100)

    request = commands.add_parser(
        "request",
        help="Capture a creative prompt and batch supplied recordings/evidence",
    )
    request_commands = request.add_subparsers(dest="request_command", required=True)
    request_add = request_commands.add_parser("add", help="Create an eprs.production-request-record/v1")
    request_add.add_argument("spec", help="eprs.production-request/v1 JSON intake")
    request_add.add_argument("--song", required=True)
    request_capture = request_commands.add_parser(
        "capture",
        help="Capture a prompt and classified files without first writing JSON",
    )
    request_capture.add_argument("--song", required=True)
    request_capture.add_argument("--title", required=True)
    request_capture.add_argument("--prompt", required=True)
    request_capture.add_argument(
        "--experience",
        help="Intended listener/player experience; defaults exactly to --prompt",
    )
    for flag, destination, help_text in (
        ("--preserve", "preserve", "Moment, feel, sound, or uncertainty to preserve"),
        ("--avoid", "avoid", "Transformation, style, privacy, or workflow choice to avoid"),
        ("--question", "questions", "Open musical or production question"),
        ("--deliverable", "deliverables", "Requested output or review artifact"),
        ("--reference", "references", "Creative or research lead, never a copying instruction"),
    ):
        request_capture.add_argument(
            flag,
            dest=destination,
            action="append",
            default=[],
            help=f"{help_text}; repeat as needed",
        )
    request_capture.add_argument(
        "--recording",
        action="append",
        type=source_spec,
        default=[],
        metavar="ROLE=PATH",
        help="Irreplaceable audio/video to copy into immutable raw intake; repeat as needed",
    )
    request_capture.add_argument(
        "--evidence",
        action="append",
        type=source_spec,
        default=[],
        metavar="ROLE=PATH",
        help="Lyrics, notes, MIDI, images, or other evidence to freeze; repeat as needed",
    )
    request_capture.add_argument(
        "--rights-note",
        default=DEFAULT_RIGHTS_NOTE,
        help="Permission context applied to every supplied file; use JSON intake for per-file notes",
    )
    request_show = request_commands.add_parser("show", help="Show one captured production request")
    request_show.add_argument("item")
    request_show.add_argument("--song", required=True)

    plan = commands.add_parser(
        "plan",
        help="Freeze a request-bound production roadmap without executing its steps",
    )
    plan_commands = plan.add_subparsers(dest="plan_command", required=True)
    plan_add = plan_commands.add_parser(
        "add", help="Create an eprs.production-plan-record/v1 or /v2"
    )
    plan_add.add_argument("spec", help="eprs.production-plan/v1 or /v2 JSON roadmap")
    plan_add.add_argument("--song", required=True)
    plan_show = plan_commands.add_parser("show", help="Show and verify one production plan")
    plan_show.add_argument("item")
    plan_show.add_argument("--song", required=True)
    plan_progress = plan_commands.add_parser("progress", help="Derive dependency progress from plan-linked work")
    plan_progress.add_argument("item")
    plan_progress.add_argument("--song", required=True)
    plan_queue = plan_commands.add_parser(
        "queue-next",
        help="Atomically queue one unstarted dependency-ready plan step",
    )
    plan_queue.add_argument("item")
    plan_queue.add_argument("--song", required=True)
    plan_queue.add_argument("--step", help="Queue this exact step only if it is unstarted and actionable")
    plan_queue.add_argument("--priority", type=int, default=50, help="Work priority from 0 to 100")
    plan_queue.add_argument("--due-at", help="ISO 8601 due time with timezone; defaults to now")
    plan_accept = plan_commands.add_parser(
        "accept-work",
        help="Validate one completed request-origin work result as a v2 plan",
    )
    plan_accept.add_argument("work", help="Completed request-origin work id or path")
    plan_accept.add_argument("--song", required=True)
    plan_accept.add_argument("--run", type=int, help="Completed run; defaults to latest")
    plan_accept.add_argument(
        "--result",
        help="Role-derived result id; required only when the run has multiple results",
    )
    plan_acceptances = plan_commands.add_parser(
        "acceptances",
        help="List verified agent-work acceptance receipts for one plan",
    )
    plan_acceptances.add_argument("item", help="Production plan id or path")
    plan_acceptances.add_argument("--song", required=True)
    plan_acceptance_show = plan_commands.add_parser(
        "acceptance-show",
        help="Verify and show one production-plan acceptance receipt",
    )
    plan_acceptance_show.add_argument("acceptance", help="Acceptance id or path")
    plan_acceptance_show.add_argument("--song", required=True)

    session = commands.add_parser(
        "session",
        help="Capture a recording day with takes, performers, setups, consent, and provenance",
    )
    session_commands = session.add_subparsers(dest="session_command", required=True)
    session_add = session_commands.add_parser("add", help="Create an eprs.recording-session-record/v1")
    session_add.add_argument("spec", help="eprs.recording-session/v1 JSON intake")
    session_add.add_argument("--song", required=True)
    session_show = session_commands.add_parser("show", help="Show and verify one recording session")
    session_show.add_argument("item")
    session_show.add_argument("--song", required=True)

    clearance = commands.add_parser(
        "clearance",
        help="Record take, participant, credit, and visibility permission evidence",
    )
    clearance_commands = clearance.add_subparsers(dest="clearance_command", required=True)
    clearance_add = clearance_commands.add_parser("add", help="Create an eprs.recording-clearance-record/v1")
    clearance_add.add_argument("spec", help="eprs.recording-clearance/v1 JSON decision record")
    clearance_add.add_argument("--song", required=True)
    clearance_show = clearance_commands.add_parser("show", help="Show and verify one recording clearance")
    clearance_show.add_argument("item")
    clearance_show.add_argument("--song", required=True)

    research = commands.add_parser(
        "research",
        help="Freeze attributed research, interpretation, and small musical experiment ideas",
    )
    research_commands = research.add_subparsers(dest="research_command", required=True)
    research_add = research_commands.add_parser("add", help="Create an eprs.research-record/v1")
    research_add.add_argument("spec", help="eprs.research/v1 JSON research record")
    research_add.add_argument("--song", required=True)
    research_show = research_commands.add_parser("show", help="Show and verify one research record")
    research_show.add_argument("item")
    research_show.add_argument("--song", required=True)

    frontier = commands.add_parser(
        "frontier",
        help="Validate portable, dated frontier-research scouting packets",
    )
    frontier_commands = frontier.add_subparsers(dest="frontier_command", required=True)
    frontier_validate = frontier_commands.add_parser(
        "validate",
        help="Validate an eprs.frontier-watch/v1 packet without browsing or changing it",
    )
    frontier_validate.add_argument("spec")

    lyrics = commands.add_parser(
        "lyrics",
        help="Freeze source-bound lyric variants and record explicit variant reviews",
    )
    lyrics_commands = lyrics.add_subparsers(dest="lyrics_command", required=True)
    lyrics_add = lyrics_commands.add_parser("add", help="Create an eprs.lyric-development/v1")
    lyrics_add.add_argument("spec", help="eprs.lyrics/v1 JSON development record")
    lyrics_add.add_argument("--song", required=True)
    lyrics_show = lyrics_commands.add_parser("show", help="Show and verify one lyric development")
    lyrics_show.add_argument("item")
    lyrics_show.add_argument("--song", required=True)
    lyrics_review = lyrics_commands.add_parser("review", help="Record keep/alternate/stop for one variant")
    lyrics_review.add_argument("item")
    lyrics_review.add_argument("--song", required=True)
    lyrics_review.add_argument("--variant", required=True)
    lyrics_review.add_argument("--decision", choices=("keep", "alternate", "stop"), required=True)
    lyrics_review.add_argument("--listening-note", required=True)

    select = commands.add_parser(
        "select",
        help="Select and optionally loop a take into reversible lossless working audio",
    )
    select.add_argument("source")
    select.add_argument("--song", required=True)
    select.add_argument("--role", required=True, help="Purpose of the selected phrase, such as guitar loop")
    select.add_argument("--start", type=float, default=0, help="Selection start in seconds")
    select.add_argument("--duration", type=float, required=True, help="Selected phrase duration in seconds")
    select.add_argument("--repeat", type=int, default=1, help="Number of exact phrase repetitions")
    select.add_argument(
        "--crossfade-ms", type=float, default=0,
        help="Optional triangular overlap between repetitions; zero keeps hard boundaries",
    )
    select.add_argument("--note", default="", help="Player-facing intent or landmark note")

    rhythm = commands.add_parser(
        "rhythm",
        help="Observe performed attacks and pulse hints without quantizing or assigning drum roles",
    )
    rhythm.add_argument("source")
    rhythm.add_argument("--song", required=True)
    rhythm.add_argument("--role", required=True, help="Purpose of the performance, such as spoken pocket")
    rhythm.add_argument("--start", type=float, default=0, help="Listening-region start in seconds")
    rhythm.add_argument("--duration", type=float, help="Listening-region duration; required only for unknown/long media")
    rhythm.add_argument(
        "--sensitivity", type=float, default=0.5,
        help="Onset selectivity from 0 to 1; higher values report fewer, clearer attacks",
    )
    rhythm.add_argument(
        "--min-gap-ms", type=float, default=150,
        help="Minimum separation between reported attacks",
    )
    rhythm.add_argument("--note", default="", help="Performer context or what the agent should listen for")

    observe = commands.add_parser(
        "observe",
        help="Observe phrase regions, pitch evidence, and pulse ambiguity without correcting a performance",
    )
    observe.add_argument("source")
    observe.add_argument("--song", required=True)
    observe.add_argument("--role", required=True, help="Purpose of the performance, such as family answer")
    observe.add_argument("--start", type=float, default=0, help="Listening-region start in seconds")
    observe.add_argument("--duration", type=float, help="Listening-region duration; required only for unknown/long media")
    observe.add_argument("--note", default="", help="Performer context and the arranger's listening question")

    groove = commands.add_parser(
        "groove",
        help="Author and audition one drummer-facing interpretation of verified rhythm evidence",
    )
    groove_commands = groove.add_subparsers(dest="groove_command", required=True)
    groove_add = groove_commands.add_parser(
        "add", help="Create an eprs.groove-development/v1 and synthesized BeatScript audition"
    )
    groove_add.add_argument("spec", help="eprs.groove/v1 JSON interpretation")
    groove_add.add_argument("--song", required=True)
    groove_show = groove_commands.add_parser("show", help="Show and verify one groove development")
    groove_show.add_argument("item")
    groove_show.add_argument("--song", required=True)
    groove_review = groove_commands.add_parser(
        "review", help="Record a complete-listen keep/change/stop decision"
    )
    groove_review.add_argument("item")
    groove_review.add_argument("--song", required=True)
    groove_review.add_argument("--decision", choices=("keep", "change", "stop"), required=True)
    groove_review.add_argument("--listening-note", required=True)

    phase = commands.add_parser(
        "phase",
        help="Observe one two-microphone timing, polarity, and mono relationship without changing audio",
    )
    phase.add_argument("source_a", help="First song-local microphone recording")
    phase.add_argument("source_b", help="Second song-local microphone recording")
    phase.add_argument("--song", required=True)
    phase.add_argument("--role-a", required=True, help="Player-facing role for microphone A")
    phase.add_argument("--role-b", required=True, help="Player-facing role for microphone B")
    phase.add_argument("--intent", required=True, help="What relationship should be listened for")
    phase.add_argument("--start-a", type=float, default=0, help="Region start in microphone A, in seconds")
    phase.add_argument("--start-b", type=float, default=0, help="Region start in microphone B, in seconds")
    phase.add_argument("--duration", type=float, required=True, help="Shared analysis-region duration, at most 30 seconds")
    phase.add_argument("--max-shift-ms", type=float, default=20, help="Bounded offset scan in either direction")
    phase.add_argument("--step-ms", type=float, default=0.5, help="Offset scan resolution")

    process = commands.add_parser(
        "process",
        help="Render an explicit, reversible processing recipe to a float working stem",
    )
    process.add_argument("spec", help="eprs.process/v1 JSON recipe")
    process.add_argument("--song", required=True)

    process_review = commands.add_parser(
        "process-review",
        help="Record a listening decision for a processed stem without changing its audio",
    )
    process_review.add_argument("stem")
    process_review.add_argument("--song", required=True)
    process_review.add_argument("--listening-note", required=True)
    process_review.add_argument("--decision", choices=("keep", "change", "stop"), required=True)

    pedalboard = commands.add_parser(
        "pedalboard",
        help="Render a pinned, checksum-bound Pedalboard effects recipe to a float working stem",
    )
    pedalboard.add_argument("spec", help="eprs.pedalboard/v1 JSON recipe")
    pedalboard.add_argument("--song", required=True)

    pedalboard_review = commands.add_parser(
        "pedalboard-review",
        help="Record a listening decision for a Pedalboard stem without changing its audio",
    )
    pedalboard_review.add_argument("stem")
    pedalboard_review.add_argument("--song", required=True)
    pedalboard_review.add_argument("--listening-note", required=True)
    pedalboard_review.add_argument("--decision", choices=("keep", "change", "stop"), required=True)

    autotune = commands.add_parser(
        "autotune",
        help="Render explicit formant-aware pitch correction for a monophonic voice WAV",
        description="Render explicit formant-aware pitch correction for a monophonic voice WAV.",
    )
    autotune.add_argument("source", help="Source mono/stereo voice audio; never overwritten")
    autotune.add_argument("--out", required=True, help="New lossless WAV destination")
    autotune.add_argument("--intent", required=True, help="Player-facing reason for this vocal treatment")
    autotune.add_argument("--preset", choices=tuple(AUTOTUNE_PRESETS), default="tight")
    autotune.add_argument("--key", default="C")
    autotune.add_argument("--scale", default="chromatic")
    autotune.add_argument("--strength", type=float, help="Pitch-correction amount from 0 to 1")
    autotune.add_argument("--retune-ms", type=float, help="Correction response time; zero makes hard steps")
    autotune.add_argument("--switch-hysteresis-cents", type=float)
    autotune.add_argument("--minimum-note-ms", type=float)
    autotune.add_argument("--wet", type=float, help="Processed balance from 0 to 1")
    autotune.add_argument("--formant-shift-semitones", type=float)
    autotune.add_argument("--melody", help="JSON array of start_seconds/end_seconds/midi notes; overrides scale targets")
    autotune.add_argument("--output-gain-db", type=float)
    autotune.add_argument("--f0-floor-hz", type=float)
    autotune.add_argument("--f0-ceil-hz", type=float)

    compare = commands.add_parser(
        "compare",
        help="Compare performance evidence without ranking takes or aligning waveforms",
    )
    compare.add_argument("spec", help="eprs.performance-compare/v1 JSON worksheet")
    compare.add_argument("--song", required=True)

    compare_review = commands.add_parser(
        "compare-review",
        help="Record one take's listening role in a performance comparison",
    )
    compare_review.add_argument("comparison")
    compare_review.add_argument("--song", required=True)
    compare_review.add_argument("--take", required=True)
    compare_review.add_argument("--decision", choices=("keep", "alternate", "stop"), required=True)
    compare_review.add_argument("--listening-note", required=True)

    comp = commands.add_parser(
        "comp",
        help="Assemble intentional regions from performances into a reversible float stem",
    )
    comp.add_argument("spec", help="eprs.comp/v1 JSON edit score")
    comp.add_argument("--song", required=True)

    comp_review = commands.add_parser(
        "comp-review",
        help="Record a listening decision for a performance comp",
    )
    comp_review.add_argument("stem")
    comp_review.add_argument("--song", required=True)
    comp_review.add_argument("--decision", choices=("keep", "change", "stop"), required=True)
    comp_review.add_argument("--listening-note", required=True)

    experiment = commands.add_parser("experiment", help="Freeze role-labeled creative inputs for one hypothesis")
    experiment.add_argument("--song", required=True)
    experiment.add_argument("--beat", help="BeatScript convenience input; equivalent to a beat source")
    experiment.add_argument("--brief", help="Creative brief convenience input")
    experiment.add_argument(
        "--source", action="append", type=source_spec, default=[], metavar="ROLE=PATH",
        help="Creative source to freeze; repeat for recordings, lyrics, MIDI, research, images, or other files",
    )
    experiment.add_argument("--hypothesis", default="")
    experiment.add_argument("--seed", type=int, default=1)

    mix = commands.add_parser(
        "mix",
        help="Render a versioned declarative arrangement to a float working mix",
    )
    mix.add_argument("spec", help="eprs.mix/v1 JSON score")
    mix.add_argument("--song", required=True)

    mix_review = commands.add_parser(
        "mix-review",
        help="Record a complete balance and headroom listen for a working mix",
    )
    mix_review.add_argument("mix")
    mix_review.add_argument("--song", required=True)
    mix_review.add_argument("--decision", choices=("keep", "change", "stop"), required=True)
    mix_review.add_argument("--listening-note", required=True)

    interchange = commands.add_parser(
        "interchange",
        help="Prepare or verify a DAW-neutral common-start stem package",
    )
    interchange_commands = interchange.add_subparsers(
        dest="interchange_command", required=True
    )
    interchange_prepare = interchange_commands.add_parser(
        "prepare",
        help="Render aligned float stems that reconstruct one verified working mix",
    )
    interchange_prepare.add_argument("mix")
    interchange_prepare.add_argument("--song", required=True)
    interchange_verify = interchange_commands.add_parser(
        "verify",
        help="Verify package structure, checksums, media format, and reconstruction evidence",
    )
    interchange_verify.add_argument("package")
    interchange_verify.add_argument("--song", required=True)
    interchange_return = interchange_commands.add_parser(
        "return",
        help="Capture a lossless external DAW bounce with explicit round-trip provenance",
    )
    interchange_return.add_argument("spec", help="eprs.daw-return/v1 JSON declaration")
    interchange_return.add_argument("--song", required=True)

    master = commands.add_parser(
        "master",
        help="Render an explicit-gain 24-bit lossless master with a refusal-only peak ceiling",
    )
    master.add_argument("spec", help="eprs.master/v1 JSON recipe")
    master.add_argument("--song", required=True)

    master_approve = commands.add_parser(
        "master-approve",
        help="Record approval only after a complete creative listen-through",
    )
    master_approve.add_argument("master")
    master_approve.add_argument("--song", required=True)
    master_approve.add_argument("--listening-note", required=True)

    finish = commands.add_parser("finish", help="Attach a result and listening decision to an experiment")
    finish.add_argument("experiment")
    finish.add_argument("--result", required=True)
    finish.add_argument("--listening-note", required=True)
    finish.add_argument("--decision", choices=("keep", "change", "stop"), required=True)

    inspect = commands.add_parser("analyze", help="Probe levels, streams, duration, and checksum")
    inspect.add_argument("media")

    youtube = commands.add_parser(
        "youtube",
        help="Render a versioned YouTube listening video from an approved master",
    )
    youtube.add_argument("spec", help="eprs.youtube/v1 JSON delivery recipe")
    youtube.add_argument("--song", required=True)

    youtube_approve = commands.add_parser(
        "youtube-approve",
        help="Record approval after reviewing the complete picture and sync",
    )
    youtube_approve.add_argument("video")
    youtube_approve.add_argument("--song", required=True)
    youtube_approve.add_argument("--review-note", required=True)

    picture = commands.add_parser(
        "picture",
        help="Capture, inspect, and review renderer-neutral picture candidates",
    )
    picture_commands = picture.add_subparsers(dest="picture_command", required=True)
    picture_add = picture_commands.add_parser(
        "add", help="Preserve one rendered picture and its external-tool disclosure"
    )
    picture_add.add_argument("spec", help="eprs.picture/v1 JSON capture recipe")
    picture_add.add_argument("--song", required=True)
    picture_show = picture_commands.add_parser(
        "show", help="Verify and print one captured picture candidate"
    )
    picture_show.add_argument("picture")
    picture_show.add_argument("--song", required=True)
    picture_review = picture_commands.add_parser(
        "review", help="Record a complete-picture keep, change, or stop decision"
    )
    picture_review.add_argument("picture")
    picture_review.add_argument("--song", required=True)
    picture_review.add_argument("--decision", choices=("keep", "change", "stop"), required=True)
    picture_review.add_argument("--review-note", required=True)

    youtube_assets = commands.add_parser(
        "youtube-assets",
        help="Create, inspect, and review thumbnail, caption, and chapter bundles",
    )
    youtube_asset_commands = youtube_assets.add_subparsers(
        dest="youtube_assets_command", required=True
    )
    youtube_assets_add = youtube_asset_commands.add_parser(
        "add", help="Create an unreviewed eprs.youtube-assets-bundle/v1"
    )
    youtube_assets_add.add_argument("spec", help="eprs.youtube-assets/v1 JSON recipe")
    youtube_assets_add.add_argument("--song", required=True)
    youtube_assets_show = youtube_asset_commands.add_parser(
        "show", help="Verify and print one YouTube asset bundle"
    )
    youtube_assets_show.add_argument("bundle")
    youtube_assets_show.add_argument("--song", required=True)
    youtube_assets_review = youtube_asset_commands.add_parser(
        "review", help="Approve thumbnail, captions, chapters, and accessibility context"
    )
    youtube_assets_review.add_argument("bundle")
    youtube_assets_review.add_argument("--song", required=True)
    youtube_assets_review.add_argument("--review-note", required=True)

    release = commands.add_parser(
        "release",
        help="Package approved master, video, credits, and metadata into FINAL without publishing",
    )
    release.add_argument("spec", help="eprs.release/v1 JSON handoff recipe")
    release.add_argument("--song", required=True)

    distribution = commands.add_parser(
        "distribution",
        help="Package an approved master, artwork, rights, and metadata for a distributor",
    )
    distribution.add_argument("spec", help="eprs.distribution/v1 JSON handoff recipe")
    distribution.add_argument("--song", required=True)

    expose = commands.add_parser(
        "expose",
        help="Put top-sorted _LISTEN/_WATCH pointers to the current review media at song root",
    )
    expose.add_argument("--song", required=True)
    expose.add_argument("--audio", required=True, help="Song-relative current audio")
    expose.add_argument("--video", help="Song-relative current video")
    expose.add_argument("--label", required=True)
    expose.add_argument("--status", choices=("diagnostic", "review", "approved"), default="review")
    expose.add_argument("--note", default="")

    publication = commands.add_parser(
        "publication",
        help="Prepare offline uploader inputs and record append-only external receipts",
    )
    publication_commands = publication.add_subparsers(
        dest="publication_command", required=True
    )
    publication_prepare = publication_commands.add_parser(
        "prepare",
        help="Verify one FINAL package and create an unauthorized YouTube handoff",
    )
    publication_prepare.add_argument("release")
    publication_prepare.add_argument("--song", required=True)
    publication_receipt = publication_commands.add_parser(
        "receipt",
        help="Record caller-declared YouTube state after a separately authorized upload",
    )
    publication_receipt.add_argument("spec", help="eprs.youtube-publication-receipt/v1 JSON")
    publication_receipt.add_argument("--song", required=True)

    work = commands.add_parser(
        "work",
        help="Queue and record song-scoped agent research, writing, and recurring work",
    )
    work_commands = work.add_subparsers(dest="work_command", required=True)

    work_add = work_commands.add_parser("add", help="Create a versioned queued work item")
    work_add.add_argument("--song", required=True)
    work_add.add_argument(
        "--title", help="Required unless --request or --plan/--plan-step supplies a default"
    )
    work_add.add_argument(
        "--kind",
        help="Open musical purpose; required unless a request or plan step supplies it",
    )
    work_add.add_argument(
        "--prompt", help="Required unless a request or plan step supplies a bounded prompt"
    )
    work_add.add_argument(
        "--request",
        help="Captured production-request id or path to bind with every supplied input",
    )
    work_add.add_argument("--plan", help="Production plan id or path to bind as immutable work origin")
    work_add.add_argument("--plan-step", help="Step id from --plan; both options are required together")
    work_add.add_argument("--priority", type=int, default=50, help="Priority from 0 to 100")
    work_add.add_argument("--cadence", choices=("once", "daily", "weekly"), default="once")
    work_add.add_argument("--due-at", help="ISO 8601 due time with timezone; defaults to now")
    work_add.add_argument(
        "--reference",
        action="append",
        default=[],
        help="A name, URL, philosophy, or other research lead; repeat as needed",
    )
    work_add.add_argument(
        "--source",
        action="append",
        type=source_spec,
        default=[],
        metavar="ROLE=PATH",
        help="Local evidence to freeze with the request; repeat as needed",
    )
    work_add.add_argument(
        "--require-result",
        action="append",
        default=[],
        metavar="ROLE",
        help="Portable result-role slug required when decision is complete; repeat as needed",
    )

    work_list = work_commands.add_parser("list", help="List work items for humans or automation")
    work_list.add_argument("--song", required=True)
    work_list.add_argument("--due", action="store_true", help="Return only queued items due now")
    work_list.add_argument("--status", choices=("queued", "in_progress", "completed", "stopped"))
    work_list.add_argument("--now", help="Evaluate due state at an explicit ISO 8601 time")

    work_show = work_commands.add_parser("show", help="Show one complete work-item record")
    work_show.add_argument("item")
    work_show.add_argument("--song", required=True)

    work_start = work_commands.add_parser("start", help="Claim one queued work item")
    work_start.add_argument("item")
    work_start.add_argument("--song", required=True)
    work_start.add_argument("--agent", required=True)

    work_claim = work_commands.add_parser(
        "claim-next",
        help="Atomically claim the next due work item for an agent",
    )
    work_claim.add_argument("--song", required=True)
    work_claim.add_argument("--agent", required=True)
    work_claim.add_argument("--kind", help="Claim only an exact case-insensitive work kind")
    work_claim.add_argument("--now", help="Evaluate due state at an explicit ISO 8601 time")

    work_release = work_commands.add_parser(
        "release",
        help="Return an owned run to the queue with a preserved reason",
    )
    work_release.add_argument("item")
    work_release.add_argument("--song", required=True)
    work_release.add_argument("--agent", required=True)
    work_release.add_argument("--note", required=True)

    work_finish = work_commands.add_parser("finish", help="Freeze results and close or requeue a work run")
    work_finish.add_argument("item")
    work_finish.add_argument("--song", required=True)
    work_finish.add_argument("--summary", required=True)
    work_finish.add_argument("--decision", choices=("complete", "needs-followup", "stop"), required=True)
    work_finish.add_argument(
        "--result",
        action="append",
        type=source_spec,
        required=True,
        metavar="ROLE=PATH",
        help="Result evidence to freeze; repeat for notes, lyrics, citations, media, or code",
    )

    work_promote = work_commands.add_parser(
        "promote",
        help="Freeze one completed work run into a new musical experiment",
    )
    work_promote.add_argument("item")
    work_promote.add_argument("--song", required=True)
    work_promote.add_argument("--hypothesis", required=True)
    work_promote.add_argument("--run", type=int, help="Completed run number; defaults to latest")
    work_promote.add_argument("--seed", type=int, default=1)
    work_promote.add_argument("--beat", help="Optional BeatScript evidence for the experiment")
    work_promote.add_argument("--brief", help="Optional creative brief for the experiment")
    work_promote.add_argument(
        "--source",
        action="append",
        type=source_spec,
        default=[],
        metavar="ROLE=PATH",
        help="Additional experiment evidence; repeat as needed",
    )

    manifest = commands.add_parser(
        "manifest",
        help="Build and extend a song-level ledger of methods, reasons, prompts, settings, and evidence",
    )
    manifest_commands = manifest.add_subparsers(dest="manifest_command", required=True)
    manifest_build = manifest_commands.add_parser(
        "build", help="Rebuild song-manifest.json from append-only records and song-local evidence",
    )
    manifest_build.add_argument("song")
    manifest_build.add_argument(
        "--probe-tools", action="store_true",
        help="Record current tool availability and versions in this catalog snapshot",
    )
    manifest_show = manifest_commands.add_parser("show", help="Print the current generated manifest")
    manifest_show.add_argument("song")
    manifest_compare = manifest_commands.add_parser(
        "compare", help="Compare evidenced method sets for two or more songs without making a taste judgment",
    )
    manifest_compare.add_argument("songs", nargs="+")
    manifest_verify = manifest_commands.add_parser(
        "verify", help="Verify checksums of evidence indexed by the current generated manifest",
    )
    manifest_verify.add_argument("song")
    manifest_record = manifest_commands.add_parser(
        "record", help="Append a method use, consideration, rejection, failure, or supersession",
    )
    manifest_record.add_argument("--song", required=True)
    manifest_record.add_argument("--method", required=True, help="Tool, technique, workflow, or method name")
    manifest_record.add_argument("--kind", default="creative", help="Open category such as composition, performance, mix, visual, research, or delivery")
    manifest_record.add_argument(
        "--status", choices=("used", "considered", "rejected", "failed", "superseded"), default="used",
    )
    manifest_record.add_argument("--reason", required=True, help="Why this method or status belonged in the song")
    manifest_record.add_argument("--software-version", help="Exact version or revision when known")
    manifest_record.add_argument("--prompt", help="Exact prompt or player-facing direction")
    manifest_record.add_argument(
        "--setting", action="append", type=json_object, default=[],
        help='Repeatable JSON settings object, e.g. \'{"swing":0.54,"seed":23}\'',
    )
    manifest_record.add_argument("--input", action="append", type=source_spec, default=[], metavar="ROLE=PATH")
    manifest_record.add_argument("--output", action="append", type=source_spec, default=[], metavar="ROLE=PATH")
    manifest_record.add_argument("--note", action="append", default=[])
    manifest_record.add_argument("--alternative", action="append", default=[])
    manifest_record.add_argument("--tag", action="append", default=[])
    manifest_note = manifest_commands.add_parser(
        "note", help="Append free-form context under any section name without constraining future schemas",
    )
    manifest_note.add_argument("--song", required=True)
    manifest_note.add_argument("--section", required=True, help="Any useful heading, such as prompts, ideas, thoughts, or notes")
    manifest_note.add_argument("--text", required=True)
    manifest_note.add_argument("--tag", action="append", default=[])

    visual_prompt = commands.add_parser("visual-prompt", help="Compile a natural-language idea into a versioned visual score")
    visual_prompt.add_argument("prompt")
    visual_prompt.add_argument("--title", required=True)
    visual_prompt.add_argument("--seed", type=int, default=1)
    visual_prompt.add_argument("--out", required=True)

    visual_render = commands.add_parser(
        "visual-render",
        help="Render an audio-reactive prompt visual with Remotion or headless vgpu",
    )
    visual_render.add_argument("spec")
    visual_render.add_argument("--audio", required=True)
    visual_render.add_argument("--out", required=True)
    visual_render.add_argument("--seconds", type=float)
    visual_render.add_argument("--quality", choices=("draft", "full"), default="draft")
    visual_render.add_argument(
        "--renderer", choices=("remotion", "vgpu"), default="remotion",
        help="Visual backend (vgpu renders headlessly through WebGPU and FFmpeg)",
    )
    visual_render.add_argument(
        "--orientation", choices=("landscape", "portrait"), default="landscape",
        help="vgpu output orientation; portrait is suitable for Shorts",
    )
    visual_render.add_argument(
        "--timeout-seconds", type=float, default=1_800.0,
        help="Stop the render and its browser workers after this time (default: 1800)",
    )
    return root


def _run_main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "produce":
            from .producer import run
            print(json.dumps(run(args), indent=2))
        elif args.command == "doctor":
            report = doctor(
                extensions=args.extension,
                workflows=args.workflow,
                required_capabilities=args.capability,
            )
            print(json.dumps(report, indent=2))
            if args.strict and not report["ok"]:
                return 2
        elif args.command == "adapter":
            if args.adapter_command == "list":
                print(json.dumps(adapter_catalog(
                    available_only=args.available,
                    capabilities=args.capability,
                    workflows=args.workflow,
                    additional_directories=args.profile_dir,
                    toolchain_extensions=args.toolchain_extension,
                ), indent=2))
            elif args.adapter_command == "show":
                print(json.dumps(adapter_guide(
                    args.adapter,
                    handoff_id=args.handoff,
                    additional_directories=args.profile_dir,
                    toolchain_extensions=args.toolchain_extension,
                ), indent=2))
        elif args.command == "chatcut":
            if args.chatcut_command == "prepare":
                print(json.dumps(prepare_chatcut_handoff(
                    args.song,
                    video=args.video,
                    audio=args.audio,
                    captions=args.captions,
                    thumbnail=args.thumbnail,
                    prompt=args.prompt,
                    seconds=args.seconds,
                    resolution=args.resolution,
                    out=args.out,
                ), indent=2))
        elif args.command == "shotcut":
            if args.shotcut_command == "prepare":
                print(json.dumps(prepare_shotcut_project(
                    args.song,
                    title=args.title,
                    video_segments=args.segment,
                    audio=args.audio,
                    title_cues=args.title_cue,
                    markers=args.marker,
                    out=args.out,
                ), indent=2))
            elif args.shotcut_command == "compile":
                print(json.dumps(compile_shotcut_project(args.spec, args.song), indent=2))
            elif args.shotcut_command == "render":
                print(json.dumps(render_shotcut_project(
                    args.project,
                    args.song,
                    out=args.out,
                    quality=args.quality,
                ), indent=2))
            elif args.shotcut_command == "open":
                print(json.dumps(open_shotcut_project(args.project, args.song), indent=2))
        elif args.command == "new":
            print(new_song(args.root, args.title))
        elif args.command == "make-song":
            if args.song is None and args.title is None:
                raise ValueError("make-song needs a title unless --song points at an existing workspace")
            if args.song is not None and args.title is not None and not args.title.strip():
                raise ValueError("make-song title cannot be blank")
            run_path, manifest = create_song_run(
                args.title,
                args.prompt,
                root=args.root,
                song=args.song,
                seed=args.seed,
                recordings=args.recording,
                evidence=args.evidence,
                references=args.reference,
                preserve=args.preserve,
                avoid=args.avoid,
                questions=args.question,
                rights_note=args.rights_note,
                render_visual_preview=not args.no_visual,
                visual_seconds=args.visual_seconds,
            )
            print(json.dumps({"song": str(run_path.parents[3]), "run": str(run_path), **manifest}, indent=2))
        elif args.command == "source-sketch":
            manifest_path, record = create_source_sketch(
                args.song,
                args.intent,
                run=args.run,
                seed=args.seed,
                include_bed=not args.no_bed,
                shape=args.shape,
                render_visual_preview=not args.no_visual,
                visual_seconds=args.visual_seconds,
                observations=args.observation,
            )
            print(json.dumps({"source_sketch": str(manifest_path), **record}, indent=2))
        elif args.command == "status":
            report = song_status(args.song, verify=args.verify)
            print(json.dumps(report, indent=2) if args.json else format_song_status(report))
        elif args.command == "performance":
            report = performance_report(args.song, stale_seconds=args.stale_seconds)
            print(json.dumps(report, indent=2) if args.json else format_performance_report(report))
        elif args.command == "map":
            print(json.dumps(write_production_map(
                args.song,
                args.run,
                out=args.out,
                render_svg=not args.no_svg,
            ), indent=2))
        elif args.command == "context":
            packet = build_agent_context(
                args.song,
                purpose=args.purpose,
                request=args.request,
                work=args.work,
                work_run=args.work_run,
                experiment=args.experiment,
                verify=args.verify,
                max_text_bytes=args.max_text_bytes,
                toolchain_extensions=args.toolchain_extension,
                adapter_profile_directories=args.profile_dir,
            )
            if args.out:
                print(write_agent_context(packet, args.out, args.format))
            elif args.format == "json":
                print(json.dumps(packet, indent=2))
            else:
                print(render_agent_context_markdown(packet), end="")
        elif args.command == "dispatch":
            if args.dispatch_command == "next":
                bundle = dispatch_next_work(
                    args.song,
                    args.agent,
                    kind=args.kind,
                    now=args.now,
                    max_text_bytes=args.max_text_bytes,
                    allow_network_research=args.allow_network_research,
                    toolchain_extensions=args.toolchain_extension,
                    adapter_profile_directories=args.profile_dir,
                )
                if args.out and bundle["status"] == "ready":
                    print(write_dispatch_packet(bundle, args.out))
                else:
                    print(json.dumps(bundle, indent=2))
            elif args.dispatch_command == "accept":
                print(accept_agent_response(args.song, args.packet, args.response))
            elif args.dispatch_command == "response-init":
                print(initialize_agent_response(args.packet, args.out))
        elif args.command == "runner":
            if args.runner_command == "validate":
                path, profile, digest = load_runner_profile(args.profile)
                print(json.dumps({
                    "path": str(path),
                    "sha256": digest,
                    "profile": profile,
                    "network_hard_denied": True,
                    "host_write_scope": "runner workspace only",
                }, indent=2))
            elif args.runner_command == "run":
                path, receipt = run_agent_profile(
                    args.song, args.profile, args.packet
                )
                print(json.dumps({"path": str(path), **receipt}, indent=2))
                if receipt["status"] != "completed":
                    return 2
            elif args.runner_command == "show":
                path, receipt = verify_runner_receipt(args.song, args.receipt)
                print(json.dumps({"path": str(path), **receipt}, indent=2))
        elif args.command == "check":
            beat = load(args.beat)
            print(f"OK: {beat.title} — {beat.bars} bars, {len(beat.tracks)} tracks, {beat.duration:.2f}s")
        elif args.command == "quality":
            report = write_quality_report(args.beat, args.song, args.out)
            print(report)
            record = json.loads(report.read_text(encoding="utf-8"))
            if record["decision"] != "pass":
                return 2
        elif args.command == "quality-approve":
            print(approve_creative_quality(args.song, args.report, args.approval_note))
        elif args.command == "video-quality":
            if (args.target_width is None) != (args.target_height is None):
                raise ValueError("video-quality target width and height must be provided together")
            target_aspect = (
                args.target_width / args.target_height
                if args.target_width is not None and args.target_height is not None
                else None
            )
            report_path = write_video_quality_report(
                args.video,
                args.out,
                max_frames=args.max_frames,
                min_sharpness=args.min_sharpness,
                min_contrast=args.min_contrast,
                target_aspect=target_aspect,
                max_crop_fraction=args.max_crop_fraction,
            )
            record = json.loads(report_path.read_text(encoding="utf-8"))
            print(json.dumps({"report": str(report_path), **record}, indent=2))
            if record["decision"] != "pass":
                return 2
        elif args.command == "render":
            print(render(load(args.beat), args.out))
        elif args.command == "visualize":
            print(svg(load(args.beat), args.out))
        elif args.command == "mutate":
            destination = Path(args.out)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(dumps(mutate(load(args.beat), args.seed, args.amount)))
            print(destination)
        elif args.command == "ingest":
            destination, metadata = ingest(
                args.source,
                args.song,
                args.role,
                args.note,
                rights_note=args.rights_note,
            )
            print(json.dumps({"recording": str(destination), "metadata": str(metadata)}, indent=2))
        elif args.command == "inaturalist":
            if args.inaturalist_command == "sound":
                destination, metadata, record = download_inaturalist_sound(
                    args.observation_id,
                    args.song,
                    args.role,
                    sound_id=args.sound_id,
                    note=args.note,
                    **({"user_agent": args.user_agent} if args.user_agent else {}),
                )
                print(json.dumps({
                    "reference": str(destination),
                    "metadata": str(metadata),
                    "observation_url": record["source"]["url"],
                    "sound_id": record["sound"]["id"],
                    "license_code": record["sound"]["license_code"],
                    "publication_status": record["rights"]["publication_status"],
                }, indent=2))
            elif args.inaturalist_command == "photo":
                destination, metadata, record = download_inaturalist_photo(
                    args.observation_id,
                    args.song,
                    args.role,
                    photo_id=args.photo_id,
                    size=args.size,
                    note=args.note,
                    **({"user_agent": args.user_agent} if args.user_agent else {}),
                )
                print(json.dumps({
                    "reference": str(destination),
                    "metadata": str(metadata),
                    "observation_url": record["source"]["url"],
                    "photo_id": record["photo"]["id"],
                    "license_code": record["photo"]["license_code"],
                    "publication_status": record["rights"]["publication_status"],
                }, indent=2))
            elif args.inaturalist_command == "study":
                manifest, record = study_inaturalist_sound(
                    args.source,
                    args.song,
                    args.role,
                    key=args.key,
                    scale=args.scale,
                    note=args.note,
                    tempo_bpm=args.tempo_bpm,
                )
                print(json.dumps({
                    "study": str(manifest),
                    "study_id": record["study_id"],
                    "observation_id": record["source"]["iNaturalist"].get("observation_id"),
                    "sound_id": record["source"]["iNaturalist"].get("sound_id"),
                    "creative_domains": sorted(record["creative_map"]),
                }, indent=2))
            elif args.inaturalist_command == "audit":
                report = audit_inaturalist_sound(
                    args.source,
                    args.song,
                    max_candidates=args.max_candidates,
                )
                if args.out:
                    report_path = write_source_audit_report(
                        report,
                        args.out,
                        protected_paths=[args.source],
                    )
                    report["report_path"] = str(report_path)
                print(json.dumps(report, indent=2))
            elif args.inaturalist_command == "verify-window":
                verification_path = record_source_verification(
                    args.audit_report,
                    args.out,
                    start_seconds=args.start,
                    end_seconds=args.end,
                    what_was_heard=args.what_was_heard,
                    reviewer=args.reviewer,
                )
                print(json.dumps({
                    "verification": str(verification_path),
                    "source_use_eligible": True,
                    "verified_by_human": True,
                }, indent=2))
            elif args.inaturalist_command == "models":
                print(json.dumps(bioacoustic_model_catalog(), indent=2))
        elif args.command == "bioacoustic":
            if args.bioacoustic_command == "detect":
                report = detect_audio(
                    args.source,
                    species_selection_table=args.species_table,
                    reference=args.reference,
                    species=args.species,
                    species_model=args.species_model,
                    behavior=args.behavior,
                    pulse_minimum_count=args.pulse_min_count,
                    pulse_minimum_gap_seconds=args.pulse_min_gap,
                    pulse_maximum_gap_seconds=args.pulse_max_gap,
                    pulse_minimum_flux_z=args.pulse_min_flux_z,
                    sustained_minimum_snr_db=args.sustained_min_snr_db,
                    max_duration_seconds=args.max_duration_seconds,
                    max_events=args.max_events,
                )
                if args.out:
                    write_detection_report(
                        report, args.out,
                        protected_paths=[args.source, args.reference, args.species_table],
                    )
                print(json.dumps(report, indent=2))
        elif args.command == "request":
            if args.request_command == "add":
                print(create_production_request(args.spec, args.song))
            elif args.request_command == "capture":
                print(capture_production_request(
                    args.song,
                    args.title,
                    args.prompt,
                    intended_experience=args.experience,
                    preserve=args.preserve,
                    avoid=args.avoid,
                    questions=args.questions,
                    deliverables=args.deliverables,
                    references=args.references,
                    recordings=args.recording,
                    evidence=args.evidence,
                    rights_note=args.rights_note,
                ))
            elif args.request_command == "show":
                _, request_record = load_production_request(args.song, args.item)
                print(json.dumps(request_record, indent=2))
        elif args.command == "plan":
            if args.plan_command == "add":
                print(create_production_plan(args.spec, args.song))
            elif args.plan_command == "show":
                _, plan_record = load_production_plan(args.song, args.item)
                print(json.dumps(plan_record, indent=2))
            elif args.plan_command == "progress":
                print(json.dumps(production_plan_progress(args.song, args.item), indent=2))
            elif args.plan_command == "queue-next":
                print(json.dumps(queue_next_plan_step(
                    args.song,
                    args.item,
                    step_id=args.step,
                    priority=args.priority,
                    due_at=args.due_at,
                ), indent=2))
            elif args.plan_command == "accept-work":
                path, acceptance = accept_plan_work_result(
                    args.song,
                    args.work,
                    run_number=args.run,
                    result_id=args.result,
                )
                print(json.dumps({"path": str(path), **acceptance}, indent=2))
            elif args.plan_command == "acceptances":
                print(json.dumps(
                    list_plan_acceptances(args.song, args.item, verify=True), indent=2
                ))
            elif args.plan_command == "acceptance-show":
                path, acceptance = verify_plan_acceptance(args.song, args.acceptance)
                print(json.dumps({"path": str(path), **acceptance}, indent=2))
        elif args.command == "session":
            if args.session_command == "add":
                print(create_recording_session(args.spec, args.song))
            elif args.session_command == "show":
                _, session_record = load_recording_session(args.song, args.item)
                print(json.dumps(session_record, indent=2))
        elif args.command == "clearance":
            if args.clearance_command == "add":
                print(create_recording_clearance(args.spec, args.song))
            elif args.clearance_command == "show":
                _, clearance_record = load_recording_clearance(args.song, args.item)
                print(json.dumps(clearance_record, indent=2))
        elif args.command == "research":
            if args.research_command == "add":
                print(create_research_record(args.spec, args.song))
            elif args.research_command == "show":
                _, research_record = load_research_record(args.song, args.item)
                print(json.dumps(research_record, indent=2))
        elif args.command == "frontier":
            if args.frontier_command == "validate":
                path, record = load_frontier_watch(args.spec)
                print(json.dumps({
                    "path": str(path),
                    "schema": record["schema"],
                    "date": record["date"],
                    "sources": len(record["sources"]),
                    "candidates": len(record["candidates"]),
                    "selected_candidate_ids": record["selection"]["selected_candidate_ids"],
                    "status": "valid",
                }, indent=2))
        elif args.command == "lyrics":
            if args.lyrics_command == "add":
                print(create_lyric_development(args.spec, args.song))
            elif args.lyrics_command == "show":
                _, lyrics_record = load_lyric_development(args.song, args.item)
                print(json.dumps(lyrics_record, indent=2))
            elif args.lyrics_command == "review":
                print(review_lyric_variant(
                    args.song,
                    args.item,
                    args.variant,
                    args.decision,
                    args.listening_note,
                ))
        elif args.command == "select":
            destination, metadata = select_audio(
                args.source,
                args.song,
                args.role,
                args.start,
                args.duration,
                args.repeat,
                args.crossfade_ms,
                args.note,
            )
            print(json.dumps({"selection": str(destination), "metadata": str(metadata)}, indent=2))
        elif args.command == "rhythm":
            destination, report = observe_rhythm(
                args.source,
                args.song,
                args.role,
                args.start,
                args.duration,
                args.sensitivity,
                args.min_gap_ms,
                args.note,
            )
            print(json.dumps({
                "observation": str(destination),
                "player_language": report["player_language"],
                "timing_observation": report["timing_observation"],
                "events": report["events"],
                "interpretation_limits": report["interpretation_limits"],
            }, indent=2))
        elif args.command == "observe":
            destination, report = observe_musical_performance(
                args.source,
                args.song,
                args.role,
                args.start,
                args.duration,
                args.note,
            )
            print(json.dumps({
                "observation": str(destination),
                "player_language": report["player_language"],
                "phrase_observation": report["phrase_observation"],
                "pitch_observation": report["pitch_observation"],
                "pulse_observation": report["pulse_observation"],
                "interpretation_limits": report["interpretation_limits"],
            }, indent=2))
        elif args.command == "groove":
            if args.groove_command == "add":
                manifest, record = create_groove_development(args.spec, args.song)
                print(json.dumps({
                    "groove": str(manifest),
                    "beatscript": record["outputs"]["beatscript"]["path"],
                    "audio_prototype": record["outputs"]["audio_prototype"]["path"],
                    "player_brief": record["recipe"]["player_brief"],
                    "event_interpretations": record["recipe"]["event_interpretations"],
                    "warnings": record["warnings"],
                    "review": record["review"],
                    "authority": record["authority"],
                }, indent=2))
            elif args.groove_command == "show":
                _, record = verify_groove_development(args.song, args.item)
                print(json.dumps(record, indent=2))
            elif args.groove_command == "review":
                print(review_groove(
                    args.song,
                    args.item,
                    args.listening_note,
                    args.decision,
                ))
        elif args.command == "phase":
            destination, report = observe_phase_relationship(
                args.song,
                args.source_a,
                args.source_b,
                args.role_a,
                args.role_b,
                args.intent,
                start_a=args.start_a,
                start_b=args.start_b,
                duration=args.duration,
                max_shift_ms=args.max_shift_ms,
                step_ms=args.step_ms,
            )
            print(json.dumps({
                "observation": str(destination),
                "player_language": report["player_language"],
                "measurement": report["measurement"],
                "actions_performed": report["actions_performed"],
            }, indent=2))
        elif args.command == "process":
            destination, metadata_path = render_process(args.spec, args.song)
            metadata = json.loads(metadata_path.read_text())
            print(json.dumps({
                "stem": str(destination),
                "metadata": str(metadata_path),
                "analysis": metadata["output"]["analysis"],
                "warnings": metadata["warnings"],
                "review": metadata["review"],
            }, indent=2))
        elif args.command == "process-review":
            print(review_processed_stem(
                args.song,
                args.stem,
                args.listening_note,
                args.decision,
            ))
        elif args.command == "pedalboard":
            destination, metadata_path = render_pedalboard(args.spec, args.song)
            metadata = json.loads(metadata_path.read_text())
            print(json.dumps({
                "stem": str(destination),
                "metadata": str(metadata_path),
                "pedalboard": metadata["pedalboard"],
                "plugins": metadata["recipe"]["plugins"],
                "analysis": metadata["output"]["analysis"],
                "warnings": metadata["warnings"],
                "review": metadata["review"],
            }, indent=2))
        elif args.command == "pedalboard-review":
            print(review_pedalboard(
                args.song,
                args.stem,
                args.listening_note,
                args.decision,
            ))
        elif args.command == "autotune":
            settings = settings_for(
                args.preset,
                key=args.key,
                scale=args.scale,
                overrides={
                    "correction_strength": args.strength,
                    "retune_ms": args.retune_ms,
                    "switch_hysteresis_cents": args.switch_hysteresis_cents,
                    "minimum_note_ms": args.minimum_note_ms,
                    "wet": args.wet,
                    "formant_shift_semitones": args.formant_shift_semitones,
                    "output_gain_db": args.output_gain_db,
                    "f0_floor_hz": args.f0_floor_hz,
                    "f0_ceil_hz": args.f0_ceil_hz,
                },
            )
            destination, sidecar, metadata = render_autotune(
                args.source, args.out, settings, intent=args.intent,
                melody=json.loads(Path(args.melody).read_text()) if args.melody else None,
            )
            print(json.dumps({
                "audio": str(destination),
                "metadata": str(sidecar),
                "settings": metadata["settings"],
                "analysis": metadata["analysis"],
                "review": metadata["review"],
            }, indent=2))
        elif args.command == "compare":
            destination, report = compare_performances(args.spec, args.song)
            print(json.dumps({
                "comparison": str(destination),
                "takes": [take["id"] for take in report["takes"]],
                "audition": report["audition"],
                "review_state": report["review_state"],
            }, indent=2))
        elif args.command == "compare-review":
            print(review_comparison(
                args.song,
                args.comparison,
                args.take,
                args.decision,
                args.listening_note,
            ))
        elif args.command == "comp":
            destination, metadata_path = render_comp(args.spec, args.song)
            metadata = json.loads(metadata_path.read_text())
            print(json.dumps({
                "comp": str(destination),
                "metadata": str(metadata_path),
                "analysis": metadata["output"]["analysis"],
                "warnings": metadata["warnings"],
                "review": metadata["review"],
            }, indent=2))
        elif args.command == "comp-review":
            print(review_comp(
                args.song,
                args.stem,
                args.listening_note,
                args.decision,
            ))
        elif args.command == "experiment":
            print(create_experiment(args.song, args.beat, args.brief, args.hypothesis, args.seed, args.source))
        elif args.command == "mix":
            destination, metadata_path = render_mix(args.spec, args.song)
            metadata = json.loads(metadata_path.read_text())
            print(json.dumps({
                "mix": str(destination),
                "metadata": str(metadata_path),
                "analysis": metadata["output"]["analysis"],
                "warnings": metadata["warnings"],
                "review": metadata["review"],
            }, indent=2))
        elif args.command == "mix-review":
            print(review_mix(args.song, args.mix, args.listening_note, args.decision))
        elif args.command == "interchange":
            if args.interchange_command == "prepare":
                package, manifest, report = prepare_daw_interchange(args.song, args.mix)
                print(json.dumps({
                    "package": str(package),
                    "manifest": str(manifest),
                    "tracks": len(report["tracks"]),
                    "reconstruction_verification": report["reconstruction_verification"],
                    "authority": report["authority"],
                }, indent=2))
            elif args.interchange_command == "verify":
                package, report = verify_daw_interchange(
                    args.song,
                    args.package,
                    verify_checksums=True,
                    verify_media=True,
                )
                print(json.dumps({
                    "package": str(package),
                    "package_id": report["package_id"],
                    "tracks": len(report["tracks"]),
                    "reconstruction_verification": report["reconstruction_verification"],
                    "authority": report["authority"],
                }, indent=2))
            elif args.interchange_command == "return":
                mix, sidecar, report = capture_daw_return(args.spec, args.song)
                print(json.dumps({
                    "mix": str(mix),
                    "metadata": str(sidecar),
                    "tool": report["external_render"]["tool"],
                    "changes": report["external_render"]["changes"],
                    "unknowns": report["external_render"]["unknowns"],
                    "warnings": report["warnings"],
                    "review": report["review"],
                    "authority": report["authority"],
                }, indent=2))
        elif args.command == "master":
            destination, metadata_path = render_master(args.spec, args.song)
            metadata = json.loads(metadata_path.read_text())
            print(json.dumps({
                "master": str(destination),
                "metadata": str(metadata_path),
                "analysis": metadata["output"]["analysis"],
                "approval": metadata["approval"],
            }, indent=2))
        elif args.command == "master-approve":
            print(approve_master(args.song, args.master, args.listening_note))
        elif args.command == "finish":
            print(finish_experiment(args.experiment, args.result, args.listening_note, args.decision))
        elif args.command == "analyze":
            print(json.dumps(analyze(args.media), indent=2))
        elif args.command == "youtube":
            video, metadata_path = render_youtube(args.spec, args.song)
            metadata = json.loads(metadata_path.read_text())
            print(json.dumps({
                "video": str(video),
                "metadata": str(metadata_path),
                "verification": metadata["verification"],
                "approval": metadata["approval"],
                "publication": metadata["publication"],
            }, indent=2))
        elif args.command == "youtube-approve":
            print(approve_youtube_video(args.song, args.video, args.review_note))
        elif args.command == "picture":
            if args.picture_command == "add":
                video, provenance, record = capture_picture(args.spec, args.song)
                print(json.dumps({
                    "picture": str(video),
                    "provenance": str(provenance),
                    "recipe_id": record["recipe_id"],
                    "review": record["review"],
                    "warnings": record["warnings"],
                    "authority": record["authority"],
                }, indent=2))
            elif args.picture_command == "show":
                path, sidecar, record = verify_picture(
                    args.song, args.picture, require_keep=False
                )
                print(json.dumps({
                    "picture": str(path), "provenance": str(sidecar), **record
                }, indent=2))
            elif args.picture_command == "review":
                print(review_picture(
                    args.song, args.picture, args.decision, args.review_note
                ))
        elif args.command == "youtube-assets":
            if args.youtube_assets_command == "add":
                destination, manifest = create_youtube_asset_bundle(args.spec, args.song)
                record = json.loads(manifest.read_text())
                print(json.dumps({
                    "bundle": str(destination),
                    "manifest": str(manifest),
                    "bundle_id": record["bundle_id"],
                    "review": record["review"],
                    "authority": record["authority"],
                }, indent=2))
            elif args.youtube_assets_command == "show":
                path, record = verify_youtube_asset_bundle(
                    args.song, args.bundle, require_approval=False
                )
                print(json.dumps({"path": str(path), **record}, indent=2))
            elif args.youtube_assets_command == "review":
                print(review_youtube_asset_bundle(
                    args.song, args.bundle, args.review_note
                ))
        elif args.command == "release":
            destination, manifest = package_release(args.spec, args.song)
            print(json.dumps({
                "release": str(destination),
                "manifest": str(manifest),
                "uploaded": False,
                "published": False,
            }, indent=2))
        elif args.command == "distribution":
            destination, manifest = package_distribution(args.spec, args.song)
            print(json.dumps({
                "distribution_package": str(destination),
                "manifest": str(manifest),
                "submitted": False,
                "distributed": False,
            }, indent=2))
        elif args.command == "expose":
            print(expose_current_media(
                args.song,
                args.audio,
                video=args.video,
                label=args.label,
                status=args.status,
                note=args.note,
            ))
        elif args.command == "publication":
            if args.publication_command == "prepare":
                print(prepare_publication_handoff(args.song, args.release))
            elif args.publication_command == "receipt":
                print(record_publication_receipt(args.spec, args.song))
        elif args.command == "work":
            if args.work_command == "add":
                print(create_work_item(
                    args.song,
                    args.title,
                    args.kind,
                    args.prompt,
                    priority=args.priority,
                    cadence=args.cadence,
                    due_at=args.due_at,
                    references=args.reference,
                    sources=args.source,
                    request=args.request,
                    plan=args.plan,
                    plan_step=args.plan_step,
                    required_result_roles=args.require_result,
                ))
            elif args.work_command == "list":
                print(json.dumps(list_work_items(
                    args.song,
                    due_only=args.due,
                    status=args.status,
                    now=args.now,
                ), indent=2))
            elif args.work_command == "show":
                _, item = load_work_item(args.song, args.item)
                print(json.dumps(item, indent=2))
            elif args.work_command == "start":
                print(start_work_item(args.song, args.item, args.agent))
            elif args.work_command == "claim-next":
                print(json.dumps(claim_next_work_item(
                    args.song,
                    args.agent,
                    kind=args.kind,
                    now=args.now,
                ), indent=2))
            elif args.work_command == "release":
                print(release_work_item(args.song, args.item, args.agent, args.note))
            elif args.work_command == "finish":
                print(finish_work_item(
                    args.song,
                    args.item,
                    args.summary,
                    args.decision,
                    args.result,
                ))
            elif args.work_command == "promote":
                print(promote_work_run(
                    args.song,
                    args.item,
                    args.hypothesis,
                    seed=args.seed,
                    run_number=args.run,
                    beat=args.beat,
                    brief=args.brief,
                    sources=args.source,
                ))
        elif args.command == "manifest":
            if args.manifest_command == "build":
                tool_report = doctor(extensions=[]) if args.probe_tools else None
                print(build_song_method_manifest(args.song, parser(), tool_report=tool_report))
            elif args.manifest_command == "show":
                path = Path(args.song) / "song-manifest.json"
                if not path.is_file():
                    raise FileNotFoundError(f"song method manifest not found: {path}")
                print(path.read_text(encoding="utf-8"), end="")
            elif args.manifest_command == "compare":
                print(json.dumps(compare_song_method_manifests(args.songs), indent=2))
            elif args.manifest_command == "verify":
                report = verify_song_method_manifest(args.song)
                print(json.dumps(report, indent=2))
                if not report["valid"]:
                    return 2
            elif args.manifest_command == "record":
                path = add_method_record(
                    args.song, args.method, args.reason, kind=args.kind,
                    status=args.status, software_version=args.software_version,
                    prompt=args.prompt, settings=args.setting, inputs=args.input,
                    outputs=args.output, notes=args.note,
                    alternatives=args.alternative, tags=args.tag,
                )
                build_song_method_manifest(args.song, parser())
                print(path)
            elif args.manifest_command == "note":
                path = add_manifest_note(args.song, args.section, args.text, args.tag)
                build_song_method_manifest(args.song, parser())
                print(path)
        elif args.command == "visual-prompt":
            print(write_prompt_score(args.prompt, args.title, args.seed, args.out))
        elif args.command == "visual-render":
            renderer = render_vgpu if args.renderer == "vgpu" else render_visual
            render_options = {"timeout_seconds": args.timeout_seconds}
            if args.renderer == "vgpu":
                render_options["orientation"] = args.orientation
            video, provenance = renderer(
                args.spec,
                args.audio,
                args.out,
                args.seconds,
                args.quality,
                **render_options,
            )
            print(json.dumps({"video": str(video), "provenance": str(provenance)}, indent=2))
        return 0
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    """Run one command and ledger song-mutating attempts and outcomes."""
    argv_list = list(sys.argv[1:] if argv is None else argv)
    parsed = parser().parse_args(argv_list)
    method = manifest_command_path(parsed)
    record_attempt = should_record_command(method)
    song_before = resolve_song_from_args(parsed) if record_attempt else None
    before = snapshot_song(song_before) if song_before is not None else {}
    result = _run_main(argv_list)
    if record_attempt:
        song_after = resolve_song_from_args(parsed)
        if song_after is not None:
            try:
                record_cli_event(
                    song_after, parsed, argv_list, before,
                    outcome="completed" if result == 0 else "nonzero",
                )
                build_song_method_manifest(song_after, parser())
            except (FileNotFoundError, FileExistsError, RuntimeError, ValueError, OSError) as exc:
                print(f"error: command completed but manifest recording failed: {exc}", file=sys.stderr)
                return 2
    return result


if __name__ == "__main__":
    raise SystemExit(main())
