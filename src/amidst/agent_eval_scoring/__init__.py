"""Isolated scoring package for Agent evaluation (WP4, Gate 4).

Must NEVER be imported by decision-side modules (amidst.q1q5, amidst.agent_eval, scripts/agent_decision).
Executed only via subprocess in evaluation workflows.
"""
from __future__ import annotations
