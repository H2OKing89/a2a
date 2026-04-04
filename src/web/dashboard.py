"""
HTML dashboard generation and deployment for quality upgrades.

Generates a self-contained HTML dashboard from quality upgrade JSON data
and deploys it to a web server via SCP.
"""

import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from jinja2 import Environment, FileSystemLoader

from src.config import WebSettings

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent
TEMPLATE_FILE = "template.html"
SAFE_SSH_HOST_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?$")
SAFE_SSH_USER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9._-]*$")
SAFE_REMOTE_PATH_RE = re.compile(r"^(?:/|~/)[A-Za-z0-9._~/-]*$")


class DashboardError(Exception):
    """Base exception for dashboard operations."""


class DeploymentError(DashboardError):
    """SCP deployment failure."""


def _validate_remote_deployment_target(settings: WebSettings) -> tuple[str, str, str]:
    """Validate SSH deployment settings before building subprocess arguments."""
    ssh_host = (settings.ssh_host or "").strip()
    ssh_user = (settings.ssh_user or "").strip()
    remote_path = (settings.path or "").strip().rstrip("/")

    if not ssh_host or not ssh_user or not remote_path:
        raise DeploymentError(
            "Web server not fully configured. "
            "Set WEB_SERVER_SSH_HOST, WEB_SERVER_SSH_USER, and WEB_SERVER_PATH in .env"
        )

    if not SAFE_SSH_HOST_RE.fullmatch(ssh_host):
        raise DeploymentError("WEB_SERVER_SSH_HOST contains unsupported characters")

    if not SAFE_SSH_USER_RE.fullmatch(ssh_user):
        raise DeploymentError("WEB_SERVER_SSH_USER contains unsupported characters")

    if not SAFE_REMOTE_PATH_RE.fullmatch(remote_path):
        raise DeploymentError("WEB_SERVER_PATH must be an absolute or ~/ POSIX path using only safe characters")

    if ".." in PurePosixPath(remote_path).parts:
        raise DeploymentError("WEB_SERVER_PATH must not contain parent-directory traversal")

    return ssh_host, ssh_user, remote_path


class DashboardGenerator:
    """Generates a self-contained HTML dashboard from upgrade data."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.candidates: list[dict[str, Any]] = data.get("upgrade_candidates", [])
        self.summary: dict[str, Any] = data.get("summary", {})

    def _compute_tier_distribution(self) -> dict[str, int]:
        """Count candidates per quality tier for chart data."""
        counts: dict[str, int] = {
            "Excellent": 0,
            "Better": 0,
            "Good": 0,
            "Low": 0,
            "Poor": 0,
        }
        for item in self.candidates:
            tier = item.get("tier", "Unknown")
            if tier in counts:
                counts[tier] += 1
        return counts

    def _compute_format_distribution(self) -> dict[str, int]:
        """Count candidates per audio format."""
        counts: dict[str, int] = {}
        for item in self.candidates:
            fmt = item.get("format", "Unknown")
            counts[fmt] = counts.get(fmt, 0) + 1
        return counts

    def _compute_recommendation_counts(self) -> dict[str, int]:
        """Count candidates per acquisition recommendation."""
        counts: dict[str, int] = {}
        for item in self.candidates:
            rec = item.get("acquisition_recommendation", "N/A") or "N/A"
            counts[rec] = counts.get(rec, 0) + 1
        return counts

    def _compute_signal_counts(self) -> dict[str, int]:
        """Count higher-order metadata signals used by the dashboard."""
        return {
            "series_linked_count": sum(1 for item in self.candidates if item.get("series_label")),
            "narrated_count": sum(1 for item in self.candidates if item.get("primary_narrator")),
            "multi_file_count": sum(1 for item in self.candidates if (item.get("file_count") or 0) > 1),
            "epic_count": sum(1 for item in self.candidates if (item.get("duration_hours") or 0) >= 15),
            "legacy_mp3_count": sum(1 for item in self.candidates if item.get("format") == "MP3"),
            "mixed_codec_count": sum(1 for item in self.candidates if len(item.get("codec_mix") or []) > 1),
        }

    def _compute_series_clusters(self, limit: int = 8) -> list[dict[str, Any]]:
        """Group candidates by series label for spotlight views."""
        grouped: dict[str, dict[str, Any]] = {}
        for item in self.candidates:
            primary_series = (item.get("series") or [None])[0]
            if isinstance(primary_series, dict):
                label = primary_series.get("name") or item.get("series_label")
            else:
                label = item.get("series_label")
            if not label:
                continue

            cluster = grouped.setdefault(
                label,
                {
                    "label": label,
                    "count": 0,
                    "max_priority": 0,
                    "free_count": 0,
                    "deal_count": 0,
                    "total_delta": 0,
                    "titles": [],
                },
            )
            cluster["count"] += 1
            cluster["max_priority"] = max(cluster["max_priority"], item.get("upgrade_priority") or 0)
            if item.get("is_plus_catalog"):
                cluster["free_count"] += 1
            if item.get("is_good_deal") or item.get("is_monthly_deal"):
                cluster["deal_count"] += 1
            cluster["total_delta"] += item.get("delta_kbps") or 0
            if len(cluster["titles"]) < 4:
                cluster["titles"].append(item.get("title") or "Unknown")

        clusters = []
        for cluster in grouped.values():
            count = max(cluster["count"], 1)
            clusters.append(
                {
                    **cluster,
                    "avg_delta": round(cluster["total_delta"] / count, 1),
                }
            )

        clusters.sort(
            key=lambda cluster: (cluster["count"], cluster["max_priority"], cluster["avg_delta"]), reverse=True
        )
        return clusters[:limit]

    def _compute_narrator_leaders(self, limit: int = 8) -> list[dict[str, Any]]:
        """Group candidates by narrator for leaderboard views."""
        grouped: dict[str, dict[str, Any]] = {}
        for item in self.candidates:
            narrator = item.get("primary_narrator")
            if not narrator:
                continue

            bucket = grouped.setdefault(
                narrator,
                {
                    "name": narrator,
                    "count": 0,
                    "free_count": 0,
                    "deal_count": 0,
                    "avg_priority_total": 0,
                },
            )
            bucket["count"] += 1
            bucket["avg_priority_total"] += item.get("upgrade_priority") or 0
            if item.get("is_plus_catalog"):
                bucket["free_count"] += 1
            if item.get("is_good_deal") or item.get("is_monthly_deal"):
                bucket["deal_count"] += 1

        leaders = []
        for bucket in grouped.values():
            leaders.append(
                {
                    **bucket,
                    "avg_priority": round(bucket["avg_priority_total"] / max(bucket["count"], 1), 1),
                }
            )

        leaders.sort(key=lambda leader: (leader["count"], leader["avg_priority"]), reverse=True)
        return leaders[:limit]

    def _get_top_ranked(self, predicate, limit: int = 6) -> list[dict[str, Any]]:
        """Return top-ranked candidates matching a predicate."""
        matching = [item for item in self.candidates if predicate(item)]
        matching.sort(
            key=lambda item: (
                item.get("upgrade_priority") or 0,
                item.get("delta_kbps") or 0,
                item.get("duration_hours") or 0,
            ),
            reverse=True,
        )
        return matching[:limit]

    def _get_top_items(self, key: str, value: Any, limit: int = 5) -> list[dict[str, Any]]:
        """Get top items matching a filter, sorted by upgrade priority."""
        matching = [item for item in self.candidates if item.get(key) == value]
        matching.sort(key=lambda x: x.get("upgrade_priority", 0), reverse=True)
        return matching[:limit]

    def _compute_max_delta(self) -> float:
        """Get maximum delta kbps for bar scaling."""
        deltas = [item.get("delta_kbps") or 0 for item in self.candidates]
        return max(deltas) if deltas else 1.0

    def _compute_template_context(self) -> dict[str, Any]:
        """Build the full Jinja2 template context."""
        from src import __version__

        tier_dist = self._compute_tier_distribution()
        format_dist = self._compute_format_distribution()
        rec_counts = self._compute_recommendation_counts()
        signal_counts = self._compute_signal_counts()
        series_clusters = self._compute_series_clusters()
        narrator_leaders = self._compute_narrator_leaders()
        max_delta = self._compute_max_delta()

        free_items = [c for c in self.candidates if c.get("is_plus_catalog")]
        deal_items = [c for c in self.candidates if c.get("is_good_deal") or c.get("is_monthly_deal")]
        owned_items = [c for c in self.candidates if c.get("owned_on_audible")]
        top_priority_items = self._get_top_ranked(lambda item: True, limit=8)
        legacy_rescue_items = self._get_top_ranked(lambda item: item.get("format") == "MP3")
        epic_items = self._get_top_ranked(lambda item: (item.get("duration_hours") or 0) >= 15)

        return {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "version": __version__,
            "summary": self.summary,
            "candidates": self.candidates,
            "candidates_json": json.dumps(self.candidates),
            "tier_distribution": tier_dist,
            "tier_distribution_json": json.dumps(tier_dist),
            "format_distribution": format_dist,
            "recommendation_counts": rec_counts,
            "signal_counts": signal_counts,
            "series_clusters": series_clusters,
            "narrator_leaders": narrator_leaders,
            "max_delta": max_delta,
            "free_items": free_items,
            "deal_items": deal_items,
            "owned_items": owned_items,
            "top_priority_items": top_priority_items,
            "legacy_rescue_items": legacy_rescue_items,
            "epic_items": epic_items,
            "total_candidates": len(self.candidates),
        }

    def render(self) -> str:
        """Render the HTML dashboard string."""
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=True,
        )
        template = env.get_template(TEMPLATE_FILE)
        context = self._compute_template_context()
        return template.render(**context)

    def save(self, output_path: Path) -> Path:
        """Write rendered HTML to file, return the path."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        html = self.render()
        output_path.write_text(html, encoding="utf-8")
        logger.info("Dashboard saved to %s (%d bytes)", output_path, len(html))
        return output_path


def deploy_dashboard(html_path: Path, settings: WebSettings) -> str:
    """
    SCP the HTML file to the web server.

    Returns the public URL.
    Raises DeploymentError if SCP fails.
    """
    if not html_path.is_file():
        raise DeploymentError(f"Dashboard file not found: {html_path}")

    ssh_host, ssh_user, remote_path = _validate_remote_deployment_target(settings)
    remote_target = f"{ssh_user}@{ssh_host}:{remote_path}/index.html"
    ssh_host_str = f"{ssh_user}@{ssh_host}"

    logger.info("Deploying dashboard: scp %s -> %s", html_path, remote_target)

    try:
        # Ensure remote directory exists
        mkdir_cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=accept-new",
            ssh_host_str,
            f"mkdir -p -- {remote_path}",
        ]
        # Inputs are validated by _validate_remote_deployment_target before invoking ssh.
        subprocess.run(  # nosec B603
            mkdir_cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )

        cmd = [
            "scp",
            "-o",
            "StrictHostKeyChecking=accept-new",
            str(html_path),
            remote_target,
        ]
        # Inputs are validated by _validate_remote_deployment_target before invoking scp.
        result = subprocess.run(  # nosec B603
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        logger.info("SCP completed successfully")
        if result.stdout:
            logger.debug("SCP stdout: %s", result.stdout)
    except subprocess.CalledProcessError as e:
        raise DeploymentError(f"SCP failed: {e.stderr or e.stdout or str(e)}") from e
    except subprocess.TimeoutExpired as e:
        raise DeploymentError(f"SCP timed out after 30s: {e}") from e

    public_url = f"https://{settings.host}" if settings.host else remote_target
    return public_url


def generate_and_deploy(
    data: dict[str, Any],
    output_dir: Path,
    settings: WebSettings,
    deploy: bool = True,
) -> tuple[Path, str | None]:
    """
    Generate HTML dashboard and optionally deploy via SCP.

    Returns (html_path, public_url_or_None).
    """
    generator = DashboardGenerator(data)
    html_path = generator.save(output_dir / "dashboard.html")

    url = None
    if deploy:
        url = deploy_dashboard(html_path, settings)

    return html_path, url
