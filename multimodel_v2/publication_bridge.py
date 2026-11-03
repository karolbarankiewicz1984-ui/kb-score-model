"""Forward-only callback for an authentic native KB21/Consensus publisher.

No authentic publisher is configured in this repository. Research/diagnostic
KB engines and historical spreadsheets are explicitly not publishers.
"""
from .formal_freeze import record_forward_freeze

SYSTEMS = frozenset({"kb21", "consensus"})


class ForwardPublicationObserver:
    def __init__(self, system, output_root, *, publisher_reference=None, enabled=False, clock=None):
        if system not in SYSTEMS:
            raise ValueError("unsupported_formal_system")
        self.system, self.root = system, output_root
        self.publisher_reference, self.enabled, self.clock = publisher_reference, enabled, clock
        self.last_result = {"status": "DISABLED", "n_effect": 0}

    def after_publish(self, original_return):
        """Called by the authenticated publisher AFTER its original commit.

        The publisher must already supply the full native-freeze contract and
        original IDs. No ID, time, price, source reference or period is added.
        Recorder failure cannot change the publisher's return value.
        """
        if not self.enabled:
            return original_return
        publication = original_return.get("publication", {}) if isinstance(original_return, dict) else {}
        if (not isinstance(self.publisher_reference, str) or not self.publisher_reference.strip()
                or not isinstance(original_return, dict) or original_return.get("system") != self.system
                or not isinstance(publication, dict)
                or publication.get("source_reference") != self.publisher_reference):
            self.last_result = {"status": "SOURCE_BLOCKED", "reason": "authentic_native_publisher_not_bound", "n_effect": 0}
            return original_return
        try:
            path = record_forward_freeze(original_return, self.root, clock=self.clock)
            self.last_result = {"status": "RECORDED", "path": str(path), "n_effect": 0}
        except Exception:
            self.last_result = {"status": "SOURCE_BLOCKED", "reason": "native_formal_contract_or_freshness_failed", "n_effect": 0}
        return original_return
