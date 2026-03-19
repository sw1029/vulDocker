from __future__ import annotations

from tests.e2e.case_matrix import ALLOWED_AXIS_VALUES, active_case_names, load_case_matrix, raw_case_matrix_entries


def test_case_matrix_covers_all_active_cases() -> None:
    matrix = load_case_matrix()
    covered = set(matrix.keys())
    active = set(active_case_names())
    missing = sorted(active - covered)
    unexpected = sorted(covered - active)

    assert missing == []
    assert unexpected == []


def test_case_matrix_axes_use_known_enums() -> None:
    matrix = load_case_matrix()
    for case_name, entry in matrix.items():
        axes = entry.get("axes")
        assert isinstance(axes, dict), case_name
        for axis_name, allowed_values in ALLOWED_AXIS_VALUES.items():
            assert axis_name in axes, f"{case_name}: missing axis {axis_name}"
            assert axes[axis_name] in allowed_values, f"{case_name}: invalid {axis_name}={axes[axis_name]!r}"


def test_case_matrix_has_no_duplicate_case_entries() -> None:
    entries = raw_case_matrix_entries()
    case_names = [str(entry.get("case") or "").strip() for entry in entries if str(entry.get("case") or "").strip()]
    assert len(case_names) == len(set(case_names))
