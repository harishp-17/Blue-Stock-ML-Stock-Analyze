import requests
import pandas as pd
from typing import Dict, Any, List, Optional

from config import (
    COMPANY_EXCEL_PATH,
    COMPANY_ID_COLUMN,
    BASE_URL,
    API_KEY,
    TEST_LIMIT,
)


def load_company_ids(path: str, column: str, limit: Optional[int] = None) -> List[str]:
    df = pd.read_excel(path)  # uses first sheet by default [web:63]
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in Excel. Available: {list(df.columns)}")
    ids = (
        df[column]
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .tolist()
    )
    if limit is not None:
        ids = ids[:limit]
    return ids


def fetch_company_data(company_id: str) -> Dict[str, Any]:
    params = {
        "id": company_id,
        "api_key": API_KEY,
    }
    resp = requests.get(BASE_URL, params=params, timeout=20)  # [web:80]
    resp.raise_for_status()
    return resp.json()  


def main():
    print("=== Loading company IDs from Excel ===")
    company_ids = load_company_ids(COMPANY_EXCEL_PATH, COMPANY_ID_COLUMN, TEST_LIMIT)
    print(f"Total company IDs loaded: {len(company_ids)}")

    for idx, cid in enumerate(company_ids, start=1):
        print(f"\n[{idx}/{len(company_ids)}] Fetching data for: {cid}")
        try:
            data = fetch_company_data(cid)
            if isinstance(data, dict):
                top_keys = list(data.keys())[:10]
                print(f"  Success. Top-level keys: {top_keys}")
            elif isinstance(data, list):
                print(f"  Success. JSON is a list with length: {len(data)}")
            else:
                print(f"  Success. Response type: {type(data)}")
        except requests.HTTPError as e:
            print(f"  HTTP error for {cid}: {e}")
        except Exception as e:
            print(f"  General error for {cid}: {e}")


if __name__ == "__main__":
    main()
