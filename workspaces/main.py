import json
import pandas as pd
from pathlib import Path

manifest = json.loads(Path("data/manifest.json").read_text())
print("Dataset:", manifest["meta"])

# Load first symbol
sym = manifest["symbols"][0]["symbol"]
path = manifest["symbols"][0]["path"]
df = pd.read_parquet(path)

print(sym, df.head())

# Write an artifact
Path("artifacts").mkdir(exist_ok=True)
(df.head(50)).to_csv("artifacts/sample.csv", index=False)
print("Wrote artifacts/sample.csv")
