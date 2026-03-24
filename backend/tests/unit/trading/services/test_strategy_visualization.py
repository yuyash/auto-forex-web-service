"""Unit tests for StrategyVisualizationService._split_display_cycles().

Covers: trend-only groups, counter-only groups, mixed groups, and empty groups.
Requirements: 1.2, 1.3, 1.4, 2.1, 2.2
"""

from __future__ import annotations

from typing import Any

import hypothesis.strategies as st
from hypothesis import given, settings

from apps.trading.services.strategy_visualization import StrategyVisualizationService


# ── Helper factories ────────────────────────────────────────────────


def _make_step(
    *,
    kind: str = "open_position",
    event_type: str = "open_position",
    entry_id: int | None = None,
    basket: str = "trend",
    timestamp: str | None = "2026-03-20T10:00:00Z",
    direction: str | None = "long",
    **extra: Any,
) -> dict[str, Any]:
    """Build a minimal step dict for testing."""
    step: dict[str, Any] = {
        "kind": kind,
        "event_type": event_type,
        "entry_id": entry_id,
        "parent_entry_id": extra.get("parent_entry_id"),
        "timestamp": timestamp,
        "basket": basket,
        "direction": direction,
        "step": extra.get("step"),
        "entry_price": extra.get("entry_price"),
        "exit_price": extra.get("exit_price"),
        "units": extra.get("units"),
        "layer_number": extra.get("layer_number"),
        "retracement_count": extra.get("retracement_count"),
        "description": extra.get("description", ""),
        "expected_interval_pips": extra.get("expected_interval_pips"),
        "actual_interval_pips": extra.get("actual_interval_pips"),
        "expected_tp_pips": extra.get("expected_tp_pips"),
        "actual_tp_pips": extra.get("actual_tp_pips"),
        "expected_exit_price": extra.get("expected_exit_price"),
        "actual_exit_price": extra.get("actual_exit_price"),
        "validation_status": extra.get("validation_status", "not_applicable"),
    }
    return step


def _make_group(
    *,
    group_id: str = "1",
    status: str = "active",
    steps: list[dict[str, Any]] | None = None,
    root_entry_id: int | None = 1001,
    root_direction: str | None = "long",
) -> dict[str, Any]:
    """Build a minimal parent group dict for testing."""
    return {
        "group_id": group_id,
        "status": status,
        "steps": steps or [],
        "root_entry_id": root_entry_id,
        "root_direction": root_direction,
    }


def _make_service() -> StrategyVisualizationService:
    """Create a StrategyVisualizationService instance for unit testing."""
    return StrategyVisualizationService()


# ── Test: Trend-only groups (順行のみ) ─────────────────────────────


class TestSplitDisplayCyclesTrendOnly:
    """Groups containing only trend steps produce a single trend cycle."""

    def test_single_trend_open_and_close(self) -> None:
        """A group with one trend open + one trend_tp close yields one trend cycle."""
        svc = _make_service()
        group = _make_group(
            group_id="G1",
            status="completed",
            steps=[
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=101,
                    basket="trend",
                    timestamp="2026-03-20T10:00:00Z",
                ),
                _make_step(
                    kind="trend_tp",
                    event_type="close_position",
                    entry_id=101,
                    basket="trend",
                    timestamp="2026-03-20T14:00:00Z",
                ),
            ],
        )

        result = svc._split_display_cycles([group])

        assert len(result) == 1
        cycle = result[0]
        assert cycle["cycle_type"] == "trend"
        assert cycle["cycle_id"] == "G1:trend:1"
        assert cycle["parent_group_id"] == "G1"
        assert cycle["status"] == "completed"
        assert cycle["started_at"] == "2026-03-20T10:00:00Z"
        assert cycle["ended_at"] == "2026-03-20T14:00:00Z"
        assert len(cycle["steps"]) == 2

    def test_trend_steps_filtered_by_basket(self) -> None:
        """Only basket='trend' steps are included in the trend cycle."""
        svc = _make_service()
        group = _make_group(
            group_id="G2",
            status="active",
            steps=[
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=201,
                    basket="trend",
                    timestamp="2026-03-20T09:00:00Z",
                ),
            ],
        )

        result = svc._split_display_cycles([group])

        assert len(result) == 1
        cycle = result[0]
        assert cycle["cycle_type"] == "trend"
        assert all(s["basket"] == "trend" or s["kind"] == "trend_tp" for s in cycle["steps"])

    def test_trend_tp_kind_included(self) -> None:
        """Steps with kind='trend_tp' are included in the trend cycle
        even if basket is not explicitly 'trend'."""
        svc = _make_service()
        group = _make_group(
            group_id="G3",
            status="completed",
            steps=[
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=301,
                    basket="trend",
                    timestamp="2026-03-20T10:00:00Z",
                ),
                _make_step(
                    kind="trend_tp",
                    event_type="close_position",
                    entry_id=301,
                    basket="trend",
                    timestamp="2026-03-20T12:00:00Z",
                ),
            ],
        )

        result = svc._split_display_cycles([group])

        assert len(result) == 1
        assert result[0]["cycle_type"] == "trend"
        assert len(result[0]["steps"]) == 2


# ── Test: Counter-only groups (逆行のみ) ───────────────────────────


class TestSplitDisplayCyclesCounterOnly:
    """Groups containing only counter steps produce counter sub-cycles."""

    def test_single_counter_sub_cycle(self) -> None:
        """A group with one counter open + close yields one counter cycle."""
        svc = _make_service()
        group = _make_group(
            group_id="G4",
            status="completed",
            steps=[
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=401,
                    basket="counter",
                    timestamp="2026-03-20T11:00:00Z",
                ),
                _make_step(
                    kind="counter_tp",
                    event_type="close_position",
                    entry_id=401,
                    basket="counter",
                    timestamp="2026-03-20T13:00:00Z",
                ),
            ],
        )

        result = svc._split_display_cycles([group])

        assert len(result) == 1
        cycle = result[0]
        assert cycle["cycle_type"] == "counter"
        assert cycle["cycle_id"] == "G4:counter:1"
        assert cycle["status"] == "completed"
        assert len(cycle["steps"]) == 2

    def test_multiple_counter_sub_cycles(self) -> None:
        """Counter steps split into multiple sub-cycles at boundary points."""
        svc = _make_service()
        group = _make_group(
            group_id="G5",
            status="completed",
            steps=[
                # Sub-cycle 1: open 501, close 501
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=501,
                    basket="counter",
                    timestamp="2026-03-20T11:00:00Z",
                ),
                _make_step(
                    kind="counter_tp",
                    event_type="close_position",
                    entry_id=501,
                    basket="counter",
                    timestamp="2026-03-20T12:00:00Z",
                ),
                # Sub-cycle 2: open 502, close 502
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=502,
                    basket="counter",
                    timestamp="2026-03-20T13:00:00Z",
                ),
                _make_step(
                    kind="counter_tp",
                    event_type="close_position",
                    entry_id=502,
                    basket="counter",
                    timestamp="2026-03-20T14:00:00Z",
                ),
            ],
        )

        result = svc._split_display_cycles([group])

        assert len(result) == 2
        assert result[0]["cycle_id"] == "G5:counter:1"
        assert result[1]["cycle_id"] == "G5:counter:2"
        assert len(result[0]["steps"]) == 2
        assert len(result[1]["steps"]) == 2

    def test_counter_steps_filtered_by_basket(self) -> None:
        """Only basket='counter' or kind='counter_tp' steps are in counter cycles."""
        svc = _make_service()
        group = _make_group(
            group_id="G6",
            status="active",
            steps=[
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=601,
                    basket="counter",
                    timestamp="2026-03-20T11:00:00Z",
                ),
            ],
        )

        result = svc._split_display_cycles([group])

        assert len(result) == 1
        assert result[0]["cycle_type"] == "counter"
        assert all(
            s["basket"] == "counter" or s["kind"] == "counter_tp" for s in result[0]["steps"]
        )


# ── Test: Mixed groups (混合) ──────────────────────────────────────


class TestSplitDisplayCyclesMixed:
    """Groups with both trend and counter steps produce multiple cycles."""

    def test_mixed_group_produces_trend_and_counter_cycles(self) -> None:
        """A group with trend + counter steps yields both cycle types."""
        svc = _make_service()
        group = _make_group(
            group_id="G7",
            status="completed",
            steps=[
                # Trend step
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=701,
                    basket="trend",
                    timestamp="2026-03-20T10:00:00Z",
                ),
                _make_step(
                    kind="trend_tp",
                    event_type="close_position",
                    entry_id=701,
                    basket="trend",
                    timestamp="2026-03-20T14:00:00Z",
                ),
                # Counter step
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=702,
                    basket="counter",
                    timestamp="2026-03-20T11:00:00Z",
                ),
                _make_step(
                    kind="counter_tp",
                    event_type="close_position",
                    entry_id=702,
                    basket="counter",
                    timestamp="2026-03-20T13:00:00Z",
                ),
            ],
        )

        result = svc._split_display_cycles([group])

        assert len(result) == 2
        cycle_types = {c["cycle_type"] for c in result}
        assert cycle_types == {"trend", "counter"}

    def test_mixed_group_no_step_overlap(self) -> None:
        """Each step appears in exactly one cycle (no duplication)."""
        svc = _make_service()
        group = _make_group(
            group_id="G8",
            status="active",
            steps=[
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=801,
                    basket="trend",
                    timestamp="2026-03-20T10:00:00Z",
                ),
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=802,
                    basket="counter",
                    timestamp="2026-03-20T11:00:00Z",
                ),
                _make_step(
                    kind="counter_tp",
                    event_type="close_position",
                    entry_id=802,
                    basket="counter",
                    timestamp="2026-03-20T12:00:00Z",
                ),
            ],
        )

        result = svc._split_display_cycles([group])

        all_step_ids = []
        for cycle in result:
            all_step_ids.extend(s["entry_id"] for s in cycle["steps"])

        # No duplicates
        assert len(all_step_ids) == len(group["steps"])

    def test_mixed_group_all_steps_covered(self) -> None:
        """All original steps are present across the output cycles (no loss)."""
        svc = _make_service()
        group = _make_group(
            group_id="G9",
            status="completed",
            steps=[
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=901,
                    basket="trend",
                    timestamp="2026-03-20T10:00:00Z",
                ),
                _make_step(
                    kind="trend_tp",
                    event_type="close_position",
                    entry_id=901,
                    basket="trend",
                    timestamp="2026-03-20T14:00:00Z",
                ),
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=902,
                    basket="counter",
                    timestamp="2026-03-20T11:00:00Z",
                ),
                _make_step(
                    kind="counter_tp",
                    event_type="close_position",
                    entry_id=902,
                    basket="counter",
                    timestamp="2026-03-20T13:00:00Z",
                ),
            ],
        )

        result = svc._split_display_cycles([group])

        total_steps = sum(len(c["steps"]) for c in result)
        assert total_steps == len(group["steps"])

    def test_mixed_cycles_sorted_by_started_at(self) -> None:
        """Output cycles are sorted by started_at ascending."""
        svc = _make_service()
        group = _make_group(
            group_id="G10",
            status="completed",
            steps=[
                # Trend starts later
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=1001,
                    basket="trend",
                    timestamp="2026-03-20T12:00:00Z",
                ),
                _make_step(
                    kind="trend_tp",
                    event_type="close_position",
                    entry_id=1001,
                    basket="trend",
                    timestamp="2026-03-20T15:00:00Z",
                ),
                # Counter starts earlier
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=1002,
                    basket="counter",
                    timestamp="2026-03-20T10:00:00Z",
                ),
                _make_step(
                    kind="counter_tp",
                    event_type="close_position",
                    entry_id=1002,
                    basket="counter",
                    timestamp="2026-03-20T11:00:00Z",
                ),
            ],
        )

        result = svc._split_display_cycles([group])

        started_ats = [c["started_at"] for c in result]
        assert started_ats == sorted(started_ats)
        # Counter cycle should come first since it starts earlier
        assert result[0]["cycle_type"] == "counter"
        assert result[1]["cycle_type"] == "trend"

    def test_multiple_groups_produce_merged_sorted_cycles(self) -> None:
        """Cycles from multiple groups are merged and sorted by started_at."""
        svc = _make_service()
        group1 = _make_group(
            group_id="GA",
            status="completed",
            steps=[
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=1101,
                    basket="trend",
                    timestamp="2026-03-20T14:00:00Z",
                ),
                _make_step(
                    kind="trend_tp",
                    event_type="close_position",
                    entry_id=1101,
                    basket="trend",
                    timestamp="2026-03-20T16:00:00Z",
                ),
            ],
        )
        group2 = _make_group(
            group_id="GB",
            status="completed",
            steps=[
                _make_step(
                    kind="open_position",
                    event_type="open_position",
                    entry_id=1201,
                    basket="trend",
                    timestamp="2026-03-20T10:00:00Z",
                ),
                _make_step(
                    kind="trend_tp",
                    event_type="close_position",
                    entry_id=1201,
                    basket="trend",
                    timestamp="2026-03-20T12:00:00Z",
                ),
            ],
        )

        result = svc._split_display_cycles([group1, group2])

        assert len(result) == 2
        # GB's cycle starts earlier, so it should come first
        assert result[0]["parent_group_id"] == "GB"
        assert result[1]["parent_group_id"] == "GA"


# ── Test: Empty groups (空グループ) ────────────────────────────────


class TestSplitDisplayCyclesEmptyGroups:
    """Groups with no steps or empty group lists produce no cycles."""

    def test_empty_groups_list(self) -> None:
        """An empty groups list returns an empty cycles list."""
        svc = _make_service()

        result = svc._split_display_cycles([])

        assert result == []

    def test_group_with_no_steps(self) -> None:
        """A group with an empty steps list produces no cycles."""
        svc = _make_service()
        group = _make_group(group_id="GE1", status="active", steps=[])

        result = svc._split_display_cycles([group])

        assert result == []

    def test_group_with_unclassifiable_steps(self) -> None:
        """Steps that are neither trend nor counter produce no cycles."""
        svc = _make_service()
        group = _make_group(
            group_id="GE2",
            status="active",
            steps=[
                _make_step(
                    kind="shrink",
                    event_type="close_position",
                    entry_id=9901,
                    basket="protection",
                    timestamp="2026-03-20T10:00:00Z",
                ),
            ],
        )

        result = svc._split_display_cycles([group])

        assert result == []

    def test_multiple_empty_groups(self) -> None:
        """Multiple groups with no steps produce no cycles."""
        svc = _make_service()
        groups = [
            _make_group(group_id="GE3", status="active", steps=[]),
            _make_group(group_id="GE4", status="active", steps=[]),
        ]

        result = svc._split_display_cycles(groups)

        assert result == []


# ── Property-based tests (プロパティベーステスト) ──────────────────


def _is_classifiable(step: dict) -> bool:
    """Return True if a step would be classified into a trend or counter cycle."""
    return step["basket"] in ("trend", "counter") or step["kind"] in ("trend_tp", "counter_tp")


# ── Hypothesis strategies ──────────────────────────────────────────

_entry_id_st = st.integers(min_value=1, max_value=100_000)


@st.composite
def _realistic_step_st(draw: st.DrawFn) -> dict:
    """Generate a step with consistent basket/kind combinations.

    In real data, basket and kind are correlated:
    - basket="trend"   → kind ∈ {"open_position", "trend_tp"}
    - basket="counter" → kind ∈ {"open_position", "counter_tp"}
    This avoids impossible combinations like basket="trend" + kind="counter_tp"
    that would match both trend and counter filters.
    """
    basket = draw(st.sampled_from(["trend", "counter"]))
    if basket == "trend":
        kind = draw(st.sampled_from(["open_position", "trend_tp"]))
    else:
        kind = draw(st.sampled_from(["open_position", "counter_tp"]))

    event_type = "close_position" if kind in ("trend_tp", "counter_tp") else "open_position"

    return {
        "basket": basket,
        "kind": kind,
        "event_type": event_type,
        "entry_id": draw(_entry_id_st),
        "parent_entry_id": None,
        "timestamp": draw(
            st.from_regex(r"2026-03-2[0-9]T[01][0-9]:[0-5][0-9]:00Z", fullmatch=True)
        ),
        "direction": draw(st.sampled_from(["long", "short"])),
        "step": None,
        "entry_price": None,
        "exit_price": None,
        "units": None,
        "layer_number": None,
        "retracement_count": None,
        "description": "",
        "expected_interval_pips": None,
        "actual_interval_pips": None,
        "expected_tp_pips": None,
        "actual_tp_pips": None,
        "expected_exit_price": None,
        "actual_exit_price": None,
        "validation_status": "not_applicable",
    }


_group_st = st.fixed_dictionaries(
    {
        "group_id": st.from_regex(r"G[0-9]{1,4}", fullmatch=True),
        "status": st.sampled_from(["active", "completed"]),
        "steps": st.lists(_realistic_step_st(), min_size=0, max_size=12),
        "root_entry_id": st.just(1001),
        "root_direction": st.sampled_from(["long", "short"]),
    }
)

_groups_st = st.lists(_group_st, min_size=0, max_size=5)


class TestSplitDisplayCyclesProperty:
    """Property-based tests for _split_display_cycles() completeness.

    **Validates: Requirements 2.1, 2.2**
    """

    @given(groups=_groups_st)
    @settings(max_examples=200, deadline=None)
    def test_all_classifiable_steps_present_in_output(self, groups: list[dict]) -> None:
        """Property 1: サイクルステップ分割の完全性

        For any list of groups, every classifiable step (trend/counter basket
        or trend_tp/counter_tp kind) from the input appears in exactly one
        output DisplayCycle — no step is missing and no step is duplicated.

        **Validates: Requirements 2.1, 2.2**
        """
        svc = _make_service()
        result = svc._split_display_cycles(groups)

        # Collect all classifiable input steps (as identity via id())
        input_steps = []
        for g in groups:
            for s in g["steps"]:
                if _is_classifiable(s):
                    input_steps.append(id(s))

        # Collect all output steps
        output_steps = []
        for cycle in result:
            for s in cycle["steps"]:
                output_steps.append(id(s))

        # 1) Total count matches — no step lost, no step added
        assert len(output_steps) == len(input_steps), (
            f"Step count mismatch: input has {len(input_steps)} classifiable "
            f"steps but output has {len(output_steps)}"
        )

        # 2) No duplicates in output
        assert len(output_steps) == len(set(output_steps)), "Duplicate steps found in output cycles"

        # 3) Every input step appears in output
        assert set(input_steps) == set(output_steps), "Input/output step identity sets differ"

    @given(groups=_groups_st)
    @settings(max_examples=200, deadline=None)
    def test_cycle_classification_accuracy(self, groups: list[dict]) -> None:
        """Property 2: サイクル分類の正確性

        For any DisplayCycle in the output, trend cycles contain only
        trend-classified steps and counter cycles contain only
        counter-classified steps.

        - cycle_type="trend"  → every step has basket="trend" OR kind="trend_tp"
        - cycle_type="counter" → every step has basket="counter" OR kind="counter_tp"

        **Validates: Requirements 1.3, 1.4**
        """
        svc = _make_service()
        result = svc._split_display_cycles(groups)

        for cycle in result:
            cycle_type = cycle["cycle_type"]
            for step in cycle["steps"]:
                if cycle_type == "trend":
                    assert step["basket"] == "trend" or step["kind"] == "trend_tp", (
                        f"Trend cycle {cycle['cycle_id']} contains a non-trend step: "
                        f"basket={step['basket']!r}, kind={step['kind']!r}"
                    )
                elif cycle_type == "counter":
                    assert step["basket"] == "counter" or step["kind"] == "counter_tp", (
                        f"Counter cycle {cycle['cycle_id']} contains a non-counter step: "
                        f"basket={step['basket']!r}, kind={step['kind']!r}"
                    )

    @given(groups=_groups_st)
    @settings(max_examples=200, deadline=None)
    def test_completed_counter_sub_cycle_boundary_correctness(self, groups: list[dict]) -> None:
        """Property 3: 逆行サブサイクル境界の正確性

        For any completed counter sub-cycle (cycle_type="counter" AND
        status="completed"), the set of entry_ids from open_position steps
        must be a subset of the set of entry_ids from close_position steps.
        In other words, all opened entries within a completed counter
        sub-cycle must have been closed.

        **Validates: Requirements 1.5, 3.2**
        """
        svc = _make_service()
        result = svc._split_display_cycles(groups)

        for cycle in result:
            if cycle["cycle_type"] != "counter" or cycle["status"] != "completed":
                continue

            opened_ids = {
                s["entry_id"]
                for s in cycle["steps"]
                if s["event_type"] == "open_position" and s["entry_id"] is not None
            }
            closed_ids = {
                s["entry_id"]
                for s in cycle["steps"]
                if s["event_type"] == "close_position" and s["entry_id"] is not None
            }

            assert opened_ids <= closed_ids, (
                f"Completed counter cycle {cycle['cycle_id']} has unclosed entries: "
                f"opened={opened_ids!r}, closed={closed_ids!r}, "
                f"unclosed={opened_ids - closed_ids!r}"
            )

    # ── Strategy for groups with unique IDs and intervened status ─

    @given(
        groups=st.lists(
            st.fixed_dictionaries(
                {
                    "status": st.sampled_from(["active", "completed", "intervened"]),
                    "steps": st.lists(_realistic_step_st(), min_size=0, max_size=12),
                    "root_entry_id": st.just(1001),
                    "root_direction": st.sampled_from(["long", "short"]),
                }
            ),
            min_size=0,
            max_size=5,
        )
    )
    @settings(max_examples=200, deadline=None)
    def test_status_and_ended_at_consistency(self, groups: list[dict]) -> None:
        """Property 4: ステータス算出とended_atの整合性

        For any DisplayCycle in the output of ``_split_display_cycles()``:

        (a) If the parent group status is "intervened", the cycle status
            must be "intervened".
        (b) If the parent group is NOT "intervened" AND no protection events
            exist in the cycle steps AND all opened entries are closed,
            the cycle status must be "completed".
        (c) If the parent group is NOT "intervened" AND no protection events
            exist AND open entries remain, the cycle status must be "active".
        (d) If status is "completed" or "intervened", ended_at must be
            non-null.
        (e) If status is "active", ended_at must be null.

        **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
        """
        # Assign unique group_ids to avoid collisions in the lookup map
        for idx, g in enumerate(groups):
            g["group_id"] = f"GP{idx}"

        svc = _make_service()
        result = svc._split_display_cycles(groups)

        # Build a lookup from group_id → parent group status
        parent_status_map: dict[str, str] = {g["group_id"]: g["status"] for g in groups}

        for cycle in result:
            status = cycle["status"]
            ended_at = cycle["ended_at"]
            parent_gid = cycle["parent_group_id"]
            parent_status = parent_status_map[parent_gid]
            steps = cycle["steps"]

            # Independently compute expected status
            has_protection = any(
                s["kind"] in ("shrink", "rebalance", "lock_hedge_neutralize") for s in steps
            )

            if has_protection or parent_status == "intervened":
                expected_status = "intervened"
            else:
                opened = {
                    s["entry_id"]
                    for s in steps
                    if s["event_type"] == "open_position" and s["entry_id"] is not None
                }
                closed = {
                    s["entry_id"]
                    for s in steps
                    if s["event_type"] == "close_position" and s["entry_id"] is not None
                }
                has_open_left = bool(opened - closed)
                expected_status = "active" if has_open_left else "completed"

            # (a)/(b)/(c) — status matches independent computation
            assert status == expected_status, (
                f"Cycle {cycle['cycle_id']}: expected status "
                f"{expected_status!r} but got {status!r} "
                f"(parent_status={parent_status!r}, "
                f"has_protection={has_protection})"
            )

            # (d) — completed/intervened → ended_at is non-null
            if status in ("completed", "intervened"):
                assert ended_at is not None, (
                    f"Cycle {cycle['cycle_id']} has status={status!r} but ended_at is None"
                )

            # (e) — active → ended_at is null
            if status == "active":
                assert ended_at is None, (
                    f"Cycle {cycle['cycle_id']} has status='active' "
                    f"but ended_at={ended_at!r} (should be None)"
                )

    @given(groups=_groups_st)
    @settings(max_examples=200, deadline=None)
    def test_chronological_order_preserved(self, groups: list[dict]) -> None:
        """Property 5: 時系列順序の保持

        For any list of groups, the output ``display_cycles`` list is sorted
        by ``started_at`` in ascending order, and within each DisplayCycle
        the ``steps`` list is sorted by ``timestamp`` in ascending order.

        None timestamps sort before non-None values (via the empty-string
        fallback used in the implementation).

        Precondition: each group's steps are pre-sorted by timestamp
        (as guaranteed by ``_build_groups_from_parent_chain()``).

        **Validates: Requirements 4.1, 4.2**
        """
        # Satisfy the documented precondition: steps within each group
        # are sorted chronologically before being passed to the function.
        for g in groups:
            g["steps"].sort(key=lambda s: s.get("timestamp") or "")

        svc = _make_service()
        result = svc._split_display_cycles(groups)

        # (a) display_cycles sorted by started_at ascending
        started_ats = [c["started_at"] or "" for c in result]
        assert started_ats == sorted(started_ats), (
            f"display_cycles not sorted by started_at: {started_ats}"
        )

        # (b) Within each cycle, steps sorted by timestamp ascending
        for cycle in result:
            timestamps = [s.get("timestamp") or "" for s in cycle["steps"]]
            assert timestamps == sorted(timestamps), (
                f"Steps in cycle {cycle['cycle_id']} not sorted by timestamp: {timestamps}"
            )

    @given(groups=_groups_st)
    @settings(max_examples=200, deadline=None)
    def test_cycle_summary_accuracy(self, groups: list[dict]) -> None:
        """Property 6: サイクルサマリーの正確性

        For any DisplayCycle in the output of ``_split_display_cycles()``:

        - ``cycle_summary["step_count"]`` equals ``len(steps)``
        - ``cycle_summary["open_count"]`` equals the number of steps
          where ``event_type == "open_position"``
        - ``cycle_summary["close_count"]`` equals the number of steps
          where ``event_type == "close_position"``
        - ``cycle_summary["validation_fail_count"]`` equals the number
          of steps where ``validation_status == "fail"``

        **Validates: Requirements 5.1, 5.2, 5.3**
        """
        svc = _make_service()
        result = svc._split_display_cycles(groups)

        for cycle in result:
            steps = cycle["steps"]
            summary = cycle["cycle_summary"]

            # step_count
            assert summary["step_count"] == len(steps), (
                f"Cycle {cycle['cycle_id']}: step_count={summary['step_count']} "
                f"but len(steps)={len(steps)}"
            )

            # open_count
            expected_open = sum(1 for s in steps if s["event_type"] == "open_position")
            assert summary["open_count"] == expected_open, (
                f"Cycle {cycle['cycle_id']}: open_count={summary['open_count']} "
                f"but expected {expected_open}"
            )

            # close_count
            expected_close = sum(1 for s in steps if s["event_type"] == "close_position")
            assert summary["close_count"] == expected_close, (
                f"Cycle {cycle['cycle_id']}: close_count={summary['close_count']} "
                f"but expected {expected_close}"
            )

            # validation_fail_count
            expected_fail = sum(1 for s in steps if s.get("validation_status") == "fail")
            assert summary["validation_fail_count"] == expected_fail, (
                f"Cycle {cycle['cycle_id']}: validation_fail_count="
                f"{summary['validation_fail_count']} but expected {expected_fail}"
            )

    @given(groups=_groups_st)
    @settings(max_examples=200, deadline=None)
    def test_cycle_id_uniqueness_and_format(self, groups: list[dict]) -> None:
        """Property 7: サイクルIDの一意性とフォーマット

        For any output of ``_split_display_cycles()``:

        (a) All ``cycle_id`` values are unique (no duplicates).
        (b) Each ``cycle_id`` matches the format
            ``"{parent_group_id}:{cycle_type}:{sequential_index}"`` where:
            - The parsed ``parent_group_id`` matches the cycle's
              ``parent_group_id`` field.
            - ``cycle_type`` is either ``"trend"`` or ``"counter"``.
            - ``sequential_index`` is a positive integer.

        **Validates: Requirement 2.3**
        """
        import re

        # Ensure unique group_ids (real data guarantees this)
        for idx, g in enumerate(groups):
            g["group_id"] = f"GP{idx}"

        svc = _make_service()
        result = svc._split_display_cycles(groups)

        # (a) All cycle_ids are unique
        cycle_ids = [c["cycle_id"] for c in result]
        assert len(cycle_ids) == len(set(cycle_ids)), f"Duplicate cycle_ids found: {cycle_ids}"

        # (b) Each cycle_id matches the expected format
        pattern = re.compile(r"^(.+):(trend|counter):(\d+)$")

        for cycle in result:
            cycle_id = cycle["cycle_id"]
            match = pattern.match(cycle_id)

            assert match is not None, (
                f"cycle_id {cycle_id!r} does not match format "
                f"'{{parent_group_id}}:{{cycle_type}}:{{sequential_index}}'"
            )

            parsed_group_id = match.group(1)
            parsed_cycle_type = match.group(2)
            parsed_index = int(match.group(3))

            # parent_group_id matches
            assert parsed_group_id == cycle["parent_group_id"], (
                f"cycle_id {cycle_id!r}: parsed parent_group_id "
                f"{parsed_group_id!r} != cycle parent_group_id "
                f"{cycle['parent_group_id']!r}"
            )

            # cycle_type matches
            assert parsed_cycle_type == cycle["cycle_type"], (
                f"cycle_id {cycle_id!r}: parsed cycle_type "
                f"{parsed_cycle_type!r} != cycle cycle_type "
                f"{cycle['cycle_type']!r}"
            )

            # sequential_index is a positive integer
            assert parsed_index > 0, (
                f"cycle_id {cycle_id!r}: sequential_index {parsed_index} is not a positive integer"
            )
