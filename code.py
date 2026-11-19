import json
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
dash = w.lakeview.get("01f1dfc589f217e6b9155a2e5a8cd34b")   # the ID from your dashboard URL
spec = json.loads(dash.serialized_dashboard)

print("Dashboard:", dash.display_name)
print("Datasets found:", len(spec.get("datasets", [])))
for d in spec.get("datasets", []):
    q = d.get("query") or " ".join(d.get("queryLines", []))
    print("-", d.get("displayName"), "|", len(q), "characters of SQL")