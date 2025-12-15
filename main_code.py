import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any
import requests
import pandas as pd

# API
os.environ["BLS_API_KEY"] = "a156a9f565764275a445393d51cd4bed"
BLS_URL: str = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
START_YEAR: int = 2006
END_YEAR: int = datetime.now(timezone.utc).year 

# Series
SERIES = [
    ("LNS12000000", "Employment", "Civilian Employment (Thousands of Persons, SA)", "M"),
    ("CES0000000001", "Employment", "Total Nonfarm Employment (Thousands of Persons, SA)", "M"),
    ("LNS14000000", "Employment", "Unemployment Rate (%, SA)", "M"),
    ("CES0500000002", "Employment", "Avg Weekly Working Hours, Total Private (Hours, SA)", "M"),
    ("CES0500000003", "Employment", "Avg Hourly Earnings, Total Private ($USD, SA)", "M"),
    ("PRS85006092", "Productivity", "Output per Hour, Nonfarm Business (% Change from previous quarter, SA)", "Q"),
    ("CUUR0000SA0", "Price Index", "CPI-U, All Items (Basis: 1982–84, NSA)", "M"),
    ("CIU1010000000000A", "Compensation", "Employment Cost Index, All Civilian Workers (12m % change, NSA)", "Q"),
]

# Path
REPO_DIR: Path = Path(r"C:/Users/jungm/Documents/GitHub/semester-project")
DATA_DIR: Path = REPO_DIR / "data"
CSV_PATH: Path = DATA_DIR / "bls_timeseries.csv"
META_PATH: Path = DATA_DIR / "meta.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Fetching
def bls_timeseries(series_ids: List[str], start_year: int, end_year: int) -> Dict[str, Any]:
    payload = {"seriesid": series_ids, "startyear": str(start_year), "endyear": str(end_year)}
    key = os.getenv("BLS_API_KEY")
    if key:
        payload["registrationkey"] = key
    r = requests.post(BLS_URL, json=payload)
    r.raise_for_status() 
    data = r.json()
    return data

# Parsing 
def payload_to_rows(series_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    sid = series_json["seriesID"]
    rows = []
    for item in series_json.get("data", []):
        period = item.get("period")
        if not period or period == "M13":
            continue
        year = int(item["year"])
        if period.startswith("M"):
            month = int(period[1:])
        elif period.startswith("Q"):
            month = {1: 3, 2: 6, 3: 9, 4: 12}[int(period[1:])]
        else:
            continue
        dt = pd.Timestamp(year=year, month=month, day=1)
        val = float(item["value"])
        rows.append({"series_id": sid, "date": dt, "value": val})
    return rows

# CSV loading 
def load_existing() -> pd.DataFrame:
    if CSV_PATH.exists():
        return pd.read_csv(CSV_PATH, parse_dates=["date"])
    return pd.DataFrame(columns=["series_id", "date", "value"])

def unifying(df_old: pd.DataFrame, df_new: pd.DataFrame) -> pd.DataFrame:
    df = pd.concat([df_old, df_new], ignore_index=True)
    df = df.drop_duplicates(subset=["series_id", "date"], keep="last")
    return df.sort_values(["series_id", "date"]).reset_index(drop=True)

# Updating
def updating() -> pd.DataFrame:
    df_old = load_existing()
    series_ids = [sid for sid, *_ in SERIES]
    api = bls_timeseries(series_ids, START_YEAR, END_YEAR)
    rows = [r for s in api["Results"]["series"] for r in payload_to_rows(s)]
    df_new = pd.DataFrame(rows)
    df_out = unifying(df_old, df_new)
    df_out = df_out[df_out["series_id"].isin(series_ids)].reset_index(drop=True)
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(CSV_PATH, index=False)
    META_PATH.write_text(json.dumps({"last_updated_utc": datetime.now(timezone.utc).isoformat()}, indent=2))
    return df_out

if __name__ == "__main__":
    df_out = updating()

# Printing 
    print(df_out.groupby("series_id")["date"].agg(["min", "max", "count"]))