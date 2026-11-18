"""Adapt the Q3 parser to the fixed LIVE person/color vocabulary."""
from __future__ import annotations

import re

from amidst.q1q5.api_budget import GuardedNlClient
from amidst.q1q5.nl_query_parse import NlVocabulary, clients_from_environment, parse_nl_query

from .candidates import COLORS, TrackRequestError

# Canonical red/blue and 紅/紅色/藍/藍色 follow configs/q1q5/class_alias_v1.json.
# The LIVE UI adds the literal chip labels as aliases.
LIVE_VOCABULARY = NlVocabulary(
    ("person",), COLORS, (),
    {"person": "person", "人": "person", "人物": "person"},
    {"red": "red", "紅": "red", "紅色": "red", "紅衣": "red",
     "blue": "blue", "藍": "blue", "藍色": "blue", "藍衣": "blue"},
    {},
)
_LOCATION_CUE = re.compile(r"在\s*[^\s，。！？]+|地點\s*[:：]|\b(?:at|in)\s+\w+", re.IGNORECASE)


class TrackSentenceParser:
    def __init__(self, *, guard=None, client_factory=clients_from_environment):
        self.guard = guard
        self.client_factory = client_factory

    def parse(self, chip, sentence, effective):
        if sentence is None:
            return self._feature(chip, ()), None

        clients = {}
        approved = (
            effective in ("review", "lead") and self.guard is not None
            and self.guard.config.enabled and self.guard.config.max_usd_total > 0
        )
        if approved:
            clients = self.client_factory(guard=self.guard)
            api = clients.get("API")
            if not isinstance(api, GuardedNlClient) or api.guard is not self.guard:
                clients = {}
        parsed = parse_nl_query(
            sentence, LIVE_VOCABULARY, mode="API" if clients else "RULES",
            api=clients.get("API"), local=clients.get("LOCAL"),
        )
        colors = tuple(color for color in COLORS if color in parsed["target"])
        ignored = []
        if parsed["action"] == "查找":
            ignored.append("action")
        if parsed["location"] or _LOCATION_CUE.search(sentence):
            ignored.append("location")
        if parsed["time"] is not None:
            ignored.append("time")
        receipt = {
            "parser": parsed["parser"], "ignored": ignored,
            "unrecognized_count": len(parsed["unrecognized"]),
        }
        if chip and colors and set(colors) != {chip}:
            receipt["note"] = "CHIP_OVERRIDES_SENTENCE"
        return self._feature(chip, colors), receipt

    @staticmethod
    def _feature(chip, colors):
        if chip:
            return chip
        if len(colors) > 1:
            raise TrackRequestError(400, "FEATURE_AMBIGUOUS")
        if not colors:
            raise TrackRequestError(400, "FEATURE_REQUIRED")
        return colors[0]
