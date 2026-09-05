"""Report composition defaults.

`default_options(project, location)` yields the "exhaustive overview" a report shows when the
caller specifies no explicit toggles. It is the SINGLE source of the scope-follows-view default
state shared by the CLI, the portal POST, and the print wizard's initial controls.
"""
from __future__ import annotations

from typing import Optional

from ..models import Project, ReportOptions


def default_options(project: Project, location: Optional[str] = None) -> ReportOptions:
    """Overview defaults for a project/scope. Sponsored jobs have no switches/derails/worksites,
    so those default off; company lines default everything on. Downtime is a line-level log, so it
    is suppressed when a single worksite is in scope. The tie table self-suppresses its Relay
    column when there is no relay, so `both` reproduces today's behavior."""
    is_company = project.project.kind == "company"
    return ReportOptions(
        ties_mode="both",
        switches=is_company,
        derails=is_company,
        downtime=location is None,
        charts=True,
    )
