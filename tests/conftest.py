"""Shared test configuration — sets AGENTFORGE_TESTING to skip config validation."""

import os

# Must be set BEFORE any agent imports
os.environ["AGENTFORGE_TESTING"] = "1"
