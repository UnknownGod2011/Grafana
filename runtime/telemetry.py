#!/usr/bin/env python3
"""Validated telemetry bindings for StageGuard's fixed semantic evidence contract."""
from __future__ import annotations

import re
from dataclasses import dataclass

_IDENTIFIER = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")
_LABEL = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _identifier(value: str, kind: str, pattern: re.Pattern[str]) -> str:
    value = value.strip()
    if not pattern.fullmatch(value):
        raise ValueError(f"unsafe {kind}: {value!r}")
    return value


def _label_value(value: str) -> str:
    """Escape a PromQL string-literal value; callers never supply raw matchers."""
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


@dataclass(frozen=True)
class TelemetryProfile:
    production_id: str = "broadcast-alpha"
    affected_feed: str = "cam-3"
    affected_uplink: str = "uplink-b"
    healthy_uplink: str = "uplink-a"
    healthy_peer_feeds: tuple[str, ...] = ("cam-1", "cam-2")
    dropped_frames_metric: str = "video_frames_dropped_total"
    packet_loss_metric: str = "network_packet_loss_percent"
    cpu_metric: str = "encoder_cpu_percent"
    gpu_metric: str = "encoder_gpu_percent"
    production_label: str = "production_id"
    feed_label: str = "feed_id"
    uplink_label: str = "uplink"

    def __post_init__(self) -> None:
        if not self.production_id.strip() or not self.affected_feed.strip() or not self.affected_uplink.strip():
            raise ValueError("production_id, affected_feed, and affected_uplink must be non-empty")
        if not self.healthy_uplink.strip() or not self.healthy_peer_feeds or any(not x.strip() for x in self.healthy_peer_feeds):
            raise ValueError("healthy peer bindings must be non-empty")
        for field in ("dropped_frames_metric", "packet_loss_metric", "cpu_metric", "gpu_metric"):
            _identifier(getattr(self, field), "metric identifier", _IDENTIFIER)
        for field in ("production_label", "feed_label", "uplink_label"):
            _identifier(getattr(self, field), "label identifier", _LABEL)


def investigation_queries(profile: TelemetryProfile) -> dict[str, tuple[str, str]]:
    p = _label_value(profile.production_id)
    feed = _label_value(profile.affected_feed)
    bad_uplink = _label_value(profile.affected_uplink)
    good_uplink = _label_value(profile.healthy_uplink)
    peer_regex = "|".join(re.escape(x) for x in profile.healthy_peer_feeds)
    peer_regex = _label_value(peer_regex)
    pl, fl, ul = profile.production_label, profile.feed_label, profile.uplink_label
    return {
        "symptom": (f'rate({profile.dropped_frames_metric}{{{pl}="{p}",{fl}="{feed}"}}[2m])', "> 1 dropped frame/s"),
        "causal": (f'{profile.packet_loss_metric}{{{pl}="{p}",{ul}="{bad_uplink}"}}', "> 5% packet loss"),
        "contradiction_cpu": (f'{profile.cpu_metric}{{{pl}="{p}",{fl}="{feed}"}}', "< 80% CPU"),
        "contradiction_gpu": (f'{profile.gpu_metric}{{{pl}="{p}",{fl}="{feed}"}}', "< 80% GPU"),
        "healthy_peer_loss": (f'{profile.packet_loss_metric}{{{pl}="{p}",{ul}="{good_uplink}"}}', "< 1% packet loss"),
        "healthy_peer_drop": (f'max(rate({profile.dropped_frames_metric}{{{pl}="{p}",{fl}=~"{peer_regex}"}}[2m]))', "< 1 dropped frame/s"),
    }


def recovery_queries(profile: TelemetryProfile) -> dict[str, tuple[str, float]]:
    p = _label_value(profile.production_id)
    feed = _label_value(profile.affected_feed)
    uplink = _label_value(profile.affected_uplink)
    pl, fl, ul = profile.production_label, profile.feed_label, profile.uplink_label
    return {
        "packet_loss": (f'{profile.packet_loss_metric}{{{pl}="{p}",{ul}="{uplink}"}}', 1.0),
        # Recovery needs a deliberately short observation window: a 2-minute
        # rate window can remain elevated long after a successful live-broadcast
        # remediation and exceed the bounded 25-second verification loop. The
        # 15-second window still requires multiple 2-second Prometheus scrapes
        # while allowing the post-action evidence to converge during the demo.
        "dropped_frames": (f'rate({profile.dropped_frames_metric}{{{pl}="{p}",{fl}="{feed}"}}[15s])', 1.0),
    }


DEFAULT_TELEMETRY_PROFILE = TelemetryProfile()
