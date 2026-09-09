#!/usr/bin/env python3
"""Render a short submission cut from real StageGuard/Grafana captures.

The input screenshots are produced by the running application. This renderer
only adds captions, timing, and title/architecture cards; it does not invent
incident states or telemetry.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "submission" / "StageGuard-demo.mp4"
WORK = ROOT / ".stageguard" / "video_segments"
FONT = r"C\:/Windows/Fonts/segoeui.ttf"


def run(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def text_filter(text: str, *, size: int, x: str, y: str, color: str = "white") -> str:
    safe = (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("%", "\\%")
        .replace("'", "\\'")
    )
    return f"drawtext=fontfile='{FONT}':text='{safe}':fontcolor={color}:fontsize={size}:x={x}:y={y}"


def still_segment(source: Path, name: str, duration: int, caption: str, detail: str) -> Path:
    output = WORK / f"{name}.mp4"
    vf = ",".join(
        [
            "scale=1920:1080:force_original_aspect_ratio=decrease",
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x090d12",
            "drawbox=x=0:y=980:w=iw:h=100:color=0x090d12@0.92:t=fill",
            text_filter(caption, size=38, x="64", y="1000"),
            text_filter(detail, size=24, x="64", y="1048", color="0xb9c5d6"),
        ]
    )
    run(
        "-loop",
        "1",
        "-i",
        str(source),
        "-t",
        str(duration),
        "-vf",
        vf,
        "-r",
        "30",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        str(output),
    )
    return output


def card(name: str, duration: int, lines: list[tuple[str, int, str, str]]) -> Path:
    output = WORK / f"{name}.mp4"
    filters = ["format=yuv420p"]
    for value, size, x, y in lines:
        filters.append(text_filter(value, size=size, x=x, y=y))
    run(
        "-f",
        "lavfi",
        "-i",
        f"color=c=0x090d12:s=1920x1080:d={duration}",
        "-vf",
        ",".join(filters),
        "-r",
        "30",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        str(output),
    )
    return output


def main() -> int:
    required = {
        name: ROOT / name
        for name in (
            "stageguard-diagnosed-hero.png",
            "grafana-explore-prometheus-recovery.png",
            "stageguard-approved-hero.png",
            "stageguard-verifying-hero.png",
            "stageguard-recovered-final-hero.png",
        )
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise SystemExit("Missing real capture(s): " + ", ".join(missing))

    WORK.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    for old in WORK.glob("*.mp4"):
        old.unlink()

    segments = [
        card(
            "01-title",
            8,
            [
                ("STAGEGUARD", 104, "(w-text_w)/2", "380"),
                ("Agentic incident commander for live media production", 42, "(w-text_w)/2", "520"),
                ("OBSERVE   >   DIAGNOSE   >   APPROVE   >   ACT   >   VERIFY", 30, "(w-text_w)/2", "650"),
            ],
        ),
        still_segment(
            required["stageguard-diagnosed-hero.png"],
            "02-diagnosis",
            24,
            "GRAFANA MCP INVESTIGATION",
            "Camera 3 degraded | uplink-b packet loss | CPU/GPU normal | peers healthy",
        ),
        still_segment(
            required["grafana-explore-prometheus-recovery.png"],
            "03-grafana",
            20,
            "GRAFANA TELEMETRY",
            "Prometheus datasource | packet loss rises to 18 pct, then returns to 0.3 pct",
        ),
        still_segment(
            required["stageguard-approved-hero.png"],
            "04-approval",
            18,
            "EXACT HUMAN APPROVAL",
            "Approval is bound to the exact evidence revision shown to the operator",
        ),
        still_segment(
            required["stageguard-verifying-hero.png"],
            "05-verification",
            20,
            "ACTION ACCEPTED != INCIDENT RESOLVED",
            "StageGuard checks fresh Grafana MCP telemetry before closing the incident",
        ),
        still_segment(
            required["stageguard-recovered-final-hero.png"],
            "06-recovered",
            24,
            "RECOVERY VERIFIED",
            "Five bounded samples | two consecutive healthy samples | verified by Grafana",
        ),
        card(
            "07-closing",
            12,
            [
                ("LIVE PRODUCTION SIMULATOR", 42, "(w-text_w)/2", "210"),
                ("PROMETHEUS  >  GRAFANA  >  OFFICIAL GRAFANA MCP", 40, "(w-text_w)/2", "340"),
                ("STAGEGUARD  >  HUMAN APPROVAL  >  BOUNDED REMEDIATION", 36, "(w-text_w)/2", "470"),
                ("GRAFANA RECOVERY VERIFICATION", 42, "(w-text_w)/2", "600"),
                ("StageGuard doesn't generate the show. It keeps the show on air.", 34, "(w-text_w)/2", "820"),
            ],
        ),
    ]

    concat_file = WORK / "concat.txt"
    concat_file.write_text("".join(f"file '{segment.as_posix()}'\n" for segment in segments), encoding="utf-8")
    run(
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(OUTPUT),
    )
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
