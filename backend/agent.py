"""DEPRECATED — TechLens agent definitions have moved to agents/ package.

This file exists only for backwards compatibility during transition.
Import from agents.live_agent instead.
"""

# Re-export for any code that still imports from here
from agents.live_agent import create_live_agent  # noqa: F401
