import math
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy.orm import Session

from db_config import get_engine
from models import Base, ProsAndCons
from api_client import load_company_ids, fetch_company_data
from ml_engine import generate_pros_cons
from config import COMPANY_EXCEL_PATH, COMPANY_ID_COLUMN, TEST_LIMIT


# ---------- helper functions for metrics ----------

def _parse_year_label(label: str) -> int | None:
    """
    Convert 'Mar 2014', 'Mar-14', 'Dec 2012', 'TTM' to numeric year.
    Returns None for 'TTM' or invalid.
    """
    if not label:
        return None
    s = str(label).strip()
    if s.upper() == "TTM":
        return None

    # fallback: use last 4 digits if they look like a year
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) >= 4:
        try:
            return int(digits[-4:])
        except Exception:
            return None
    return None


def _compute_cagr(start_val: float, end_val: float, years: float) -> float | None:
    """CAGR = (end / start)^(1/years) - 1  -> percentage."""
    if start_val <= 0 or end_val <= 0 or years <= 0:
        return None
    try:
        return (math.pow(end_val / start_val, 1.0 / years) - 1.0) * 100.0
    except Exception:
        return None


def _compute_cagr_from_series(year_to_value: Dict[int, float], span_years: int) -> float | None:
    """
    Compute CAGR over approx span_years (3, 5, 10) using earliest and latest
    years that are at least span_years-1 apart; if not enough data, None.
    """
    years = sorted(year_to_value.keys())
    if len(years) < 2:
        return None
    best = None
    for i in range(len(years)):
        for j in range(i + 1, len(years)):
            y0, y1 = years[i], years[j]
            diff = y1 - y0
            if diff < span_years - 1:
                continue
            cagr = _compute_cagr(year_to_value[y0], year_to_value[y1], diff)
            if cagr is not None:
                best = cagr
    return best


def _avg_over_years(values: Dict[int, float], span_years: int) -> float | None:
    """Average of last span_years values (by year); if fewer years, None."""
    years = sorted(values.keys())
    if not years:
        return None
    last_year = years[-1]
    sel = [y for y in years if y >= last_year - span_years + 1]
    if not sel:
        return None
    vals = [values[y] for y in sel if values[y] is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def map_api_to_metrics(api_json: Dict[str, Any]) -> Dict[str, str]:
    """
    Build metrics using raw profitandloss + balancesheet for ALL companies.
    """
    data = api_json.get("data", {})

    # --- 1) Build year->sales, year->profit, year->networth dicts ---

    sales_by_year: Dict[int, float] = {}
    profit_by_year: Dict[int, float] = {}
    networth_by_year: Dict[int, float] = {}  # equity_capital + reserves

    # profit and loss
    for row in data.get("profitandloss", []) or []:
        y = _parse_year_label(row.get("year", ""))
        if y is None:
            continue
        try:
            sales = float(row.get("sales", 0) or 0)
            profit = float(row.get("net_profit", 0) or 0)
        except Exception:
            continue
        if sales > 0:
            sales_by_year[y] = sales
        if profit != 0:
            profit_by_year[y] = profit

    # balance sheet for net worth
    for row in data.get("balancesheet", []) or []:
        y = _parse_year_label(row.get("year", ""))
        if y is None:
            continue
        try:
            equity = float(row.get("equity_capital", 0) or 0)
            reserves = float(row.get("reserves", 0) or 0)
            networth = equity + reserves
        except Exception:
            continue
        if networth > 0:
            networth_by_year[y] = networth

    # --- 2) Compute CAGRs ---

    sales_cagr_3 = _compute_cagr_from_series(sales_by_year, 3)
    sales_cagr_5 = _compute_cagr_from_series(sales_by_year, 5)
    sales_cagr_10 = _compute_cagr_from_series(sales_by_year, 10)

    profit_cagr_3 = _compute_cagr_from_series(profit_by_year, 3)
    profit_cagr_5 = _compute_cagr_from_series(profit_by_year, 5)
    profit_cagr_10 = _compute_cagr_from_series(profit_by_year, 10)

    def fmt(label: str, val) -> str:
        return f"{label}: {val:.1f}%" if isinstance(val, (int, float)) else ""

    sales_3_str = fmt("3 Years", sales_cagr_3)
    sales_5_str = fmt("5 Years", sales_cagr_5)
    sales_10_str = fmt("10 Years", sales_cagr_10)

    profit_3_str = fmt("3 Years", profit_cagr_3)
    profit_5_str = fmt("5 Years", profit_cagr_5)
    profit_10_str = fmt("10 Years", profit_cagr_10)

    # --- 3) Compute ROE (Net profit / Net worth) ---

    roe_by_year: Dict[int, float] = {}
    for y in profit_by_year.keys():
        if y in networth_by_year and networth_by_year[y] > 0:
            roe_by_year[y] = profit_by_year[y] / networth_by_year[y] * 100.0

    roe_3 = _avg_over_years(roe_by_year, 3)
    roe_5 = _avg_over_years(roe_by_year, 5)
    roe_10 = _avg_over_years(roe_by_year, 10)

    roe_3_str = fmt("3 Years", roe_3)
    roe_5_str = fmt("5 Years", roe_5)
    roe_10_str = fmt("10 Years", roe_10)

    # --- 4) Dividend payout from latest PL row ---

    pl_list = data.get("profitandloss", []) or []
    dividend_payout = ""
    if pl_list:
        last_pl = pl_list[-1]
        dividend_payout = str(last_pl.get("dividend_payout", "") or "")

    metrics = {
        "sales_cagr_3y":  sales_3_str,
        "sales_cagr_5y":  sales_5_str,
        "sales_cagr_10y": sales_10_str,
        "profit_cagr_3y": profit_3_str,
        "profit_cagr_5y": profit_5_str,
        "profit_cagr_10y": profit_10_str,
        "roe_3y":  roe_3_str,
        "roe_5y":  roe_5_str,
        "roe_10y": roe_10_str,
        "dividend_payout": dividend_payout,
        "debt_ratio": None,
    }

    return metrics


# ---------- main pipeline ----------

def main():
    print("Starting ML pros/cons generation...")
    engine = get_engine()
    Base.metadata.create_all(engine)

    from config import TEST_LIMIT  # ensure latest value
    company_ids = load_company_ids(COMPANY_EXCEL_PATH, COMPANY_ID_COLUMN, TEST_LIMIT)
    print(f"Total companies: {len(company_ids)}")

    with Session(engine) as session:
        for idx, cid in enumerate(company_ids, start=1):
            print(f"[{idx}/{len(company_ids)}] Processing {cid}")
            try:
                api_json = fetch_company_data(cid)
                metrics = map_api_to_metrics(api_json)

                pros, cons = generate_pros_cons(cid, metrics)

                session.query(ProsAndCons).filter_by(company_id=cid).delete()

                rows: List[ProsAndCons] = []
                for p in pros:
                    rows.append(ProsAndCons(company_id=cid, pros=p, cons=None))
                for c in cons:
                    rows.append(ProsAndCons(company_id=cid, pros=None, cons=c))

                session.add_all(rows)
                session.commit()
                print(f"  Saved {len(rows)} rows for {cid} to prosandcons table")

            except Exception as e:
                session.rollback()
                print(f"  Error for {cid}: {e}")


if __name__ == "__main__":
    main()
