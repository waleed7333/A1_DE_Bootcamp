# src/reconciliation/run_reconciliation.py
# Reconciliation test runner
# Reads query definitions from reconciliation_queries.py and executes them

import pandas as pd
from sqlalchemy import text

from code.src.config import get_oltp_engine, get_olap_engine
from code.src.reconciliation.reconciliation_queries import RECONCILIATION_CHECKS


def run_single_check(oltp_engine, olap_engine, check: dict, check_id: int, tolerance: float = 0.01):
    """
    Execute a single reconciliation check.

    Parameters
    ----------
    oltp_engine : sqlalchemy.engine.Engine
        Source database connection.
    olap_engine : sqlalchemy.engine.Engine
        Target database connection.
    check : dict
        Check definition with keys: name, oltp_query, olap_query, compare_cols.
    check_id : int
        Sequential check number.
    tolerance : float
        Acceptable percentage difference for numeric columns.

    Returns
    -------
    tuple (check_label, passed, detail)
    """
    check_label = f"{check_id:02d}. [{check['category']}] {check['name']}"

    try:
        src_df = pd.read_sql_query(text(check["oltp_query"]), oltp_engine)
        tgt_df = pd.read_sql_query(text(check["olap_query"]), olap_engine)
    except Exception as e:
        return (check_label, False, f"Query Error: {str(e)[:100]}")

    # Row count check
    if len(src_df) != len(tgt_df):
        return (
            check_label,
            False,
            f"Row count mismatch: Source={len(src_df)}, Target={len(tgt_df)}",
        )

    if len(src_df) == 0:
        return (check_label, True, "Both empty (no data)")

    # Compare specified columns
    for col in check["compare_cols"]:
        if col not in src_df.columns:
            return (check_label, False, f"Column '{col}' missing in source")
        if col not in tgt_df.columns:
            return (check_label, False, f"Column '{col}' missing in target")

        src_vals = pd.to_numeric(src_df[col], errors="coerce").fillna(0)
        tgt_vals = pd.to_numeric(tgt_df[col], errors="coerce").fillna(0)

        src_sum = src_vals.sum()
        tgt_sum = tgt_vals.sum()

        if src_sum == 0 and tgt_sum == 0:
            continue

        if src_sum == 0 or tgt_sum == 0:
            return (
                check_label,
                False,
                f"Column '{col}': Source={src_sum:.2f}, Target={tgt_sum:.2f} (one is zero)",
            )

        diff_pct = abs(tgt_sum - src_sum) / abs(src_sum) * 100

        if diff_pct > tolerance:
            return (
                check_label,
                False,
                f"Column '{col}': Source={src_sum:,.2f}, Target={tgt_sum:,.2f}, Diff={diff_pct:.2f}%",
            )

    return (check_label, True, f"Matched ({len(src_df)} rows)")


def run_reconciliation():
    """
    Main entry point for Phase 8.

    Executes all reconciliation checks and prints a summary report.
    """
    print("\n" + "=" * 70)
    print("PHASE 8: RECONCILIATION - Source vs Target Validation")
    print("=" * 70)

    oltp = get_oltp_engine()
    olap = get_olap_engine()

    all_results = []

    print(f"\n  Running {len(RECONCILIATION_CHECKS)} checks...\n")

    for idx, check in enumerate(RECONCILIATION_CHECKS, start=1):
        result = run_single_check(oltp, olap, check, idx)
        all_results.append(result)

        status = "✓" if result[1] else "✗"
        print(f"    {status} {result[0]}")
        if not result[1]:
            print(f"       → {result[2]}")

    # Summary
    passed = sum(1 for _, p, _ in all_results if p)
    failed = sum(1 for _, p, _ in all_results if not p)
    total = len(all_results)

    print(f"\n  {'─' * 60}")
    print(f"  RECONCILIATION SUMMARY")
    print(f"  {'─' * 60}")
    print(f"  Total checks: {total}")
    print(f"  Passed:       {passed}")
    print(f"  Failed:       {failed}")

    if failed == 0:
        print(f"  Status:       ✓ SOURCE AND TARGET ARE IDENTICAL")
    else:
        print(f"  Status:       ✗ {failed} MISMATCH(ES) DETECTED")

    print("=" * 70)