import re
from typing import Optional, Dict, List, Tuple


# ---------- 1) Helper: convert strings like "3 Years: 56%" to float 56.0 ----------

def parse_percent(value: str) -> Optional[float]:
    """
    Converts strings like '3 Years: 56%' or '-4%' to float.
    Returns None if it can't find a number.
    """
    if value is None:
        return None
    s = str(value)

    # 1) Prefer the number that is directly followed by '%'
    match = re.search(r"(-?\d+(\.\d+)?)\s*%", s)
    if match:
        return float(match.group(1))

    # 2) Fallback: first number in the string
    match = re.search(r"-?\d+(\.\d+)?", s)
    if match:
        return float(match.group(0))

    return None


# ---------- 2) Main function: build pros & cons for ONE company ----------

def generate_pros_cons(company_id: str, metrics: Dict[str, str]) -> Tuple[List[str], List[str]]:
    """
    Given one company's metric strings, return up to 3 pros and 3 cons sentences.

    metrics EXPECTED KEYS:
        sales_cagr_3y, sales_cagr_5y, sales_cagr_10y
        profit_cagr_3y, profit_cagr_5y, profit_cagr_10y
        roe_3y, roe_5y, roe_10y
        dividend_payout
        debt_ratio  (optional, if available)
    """

    pros: List[str] = []
    cons: List[str] = []

    # ---- convert all strings to numbers ----
    sales_3  = parse_percent(metrics.get("sales_cagr_3y", ""))
    sales_5  = parse_percent(metrics.get("sales_cagr_5y", ""))
    sales_10 = parse_percent(metrics.get("sales_cagr_10y", ""))

    profit_3  = parse_percent(metrics.get("profit_cagr_3y", ""))
    profit_5  = parse_percent(metrics.get("profit_cagr_5y", ""))
    profit_10 = parse_percent(metrics.get("profit_cagr_10y", ""))

    roe_3  = parse_percent(metrics.get("roe_3y", ""))
    roe_5  = parse_percent(metrics.get("roe_5y", ""))
    roe_10 = parse_percent(metrics.get("roe_10y", ""))

    div_payout = parse_percent(metrics.get("dividend_payout", ""))
    debt_ratio = parse_percent(metrics.get("debt_ratio", ""))  # optional

    # ---------- thresholds (tuned) ----------
    SALES_POOR_THRESHOLD = 8.0   # was 10.0
    ROE_LOW_THRESHOLD    = 8.0   # was 10.0

    # ---------- PROS: values > 10% ----------

    # Debt-related pros
    if debt_ratio is not None:
        if debt_ratio <= 0:
            pros.append("Company is almost debt-free.")
        elif debt_ratio < 10:
            pros.append("Company has reduced debt.")

    # ROE pros
    if roe_3 is not None and roe_3 > 10:
        pros.append(
            f"Company has a good return on equity (ROE) track record: 3 Years ROE {roe_3:.1f}%."
        )
    elif roe_5 is not None and roe_5 > 10:
        pros.append(
            f"Company has a good return on equity (ROE) track record: 5 Years ROE {roe_5:.1f}%."
        )

    # Dividend payout pros
    if div_payout is not None and div_payout > 10:
        pros.append(
            f"Company has been maintaining a healthy dividend payout of {div_payout:.1f}%."
        )

    # Profit growth pros (prefer longer period)
    profit_for_msg = profit_10 or profit_5 or profit_3
    if profit_for_msg is not None and profit_for_msg > 10:
        pros.append(
            f"Company has delivered good profit growth of {profit_for_msg:.1f}%."
        )

    # Sales growth pros (prefer 10y, then 5y, then 3y)
    sales_for_msg = sales_10 or sales_5 or sales_3
    if sales_for_msg is not None and sales_for_msg > 10:
        pros.append(
            f"Company's median sales growth is {sales_for_msg:.1f}% of last 10 years."
        )

    # limit pros to max 3
    pros = pros[:3]

    # ---------- CONS: values under relaxed thresholds ----------

    # Poor 5-year sales growth
    if sales_5 is not None and sales_5 < SALES_POOR_THRESHOLD:
        cons.append(
            f"The company has delivered a poor sales growth of {sales_5:.2f}% over past five years."
        )

    # Poor 10-year sales growth
    if sales_10 is not None and sales_10 < SALES_POOR_THRESHOLD:
        cons.append(
            f"The company has delivered poor sales growth of {sales_10:.2f}% over the past 10 years."
        )

    # Low ROE
    if roe_3 is not None and roe_3 < ROE_LOW_THRESHOLD:
        cons.append(
            f"Company has a low return on equity of {roe_3:.2f}% over last 3 years."
        )

    # Dividend-related cons
    if div_payout is not None:
        if div_payout == 0:
            cons.append("Company is not paying out dividend.")
        elif div_payout < 10:
            cons.append(
                f"Dividend payout has been low at {div_payout:.1f}% of profits over last 3 years."
            )

    # limit cons to max 3
    cons = cons[:3]

    return pros, cons
