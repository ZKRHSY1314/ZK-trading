"""Apply future pure metadata gate to retained host identity and endpoint metadata.

No HTTP, credentials, config.json, services, production imports or database access.
The current project remains pinned to the D-drive home; a reference pass elsewhere
does not select that home or authorize a request.
"""
from pathlib import Path
from datetime import datetime, timezone
import json
from endpoint_identity_guard import validate_endpoint_identity

HERE = Path(__file__).resolve().parent
retained = json.loads((HERE / "endpoint_identity_diagnosis.json").read_text(encoding="utf-8"))
host = retained["host"]
observations = []
for path in (
    Path(r"D:\TonghuasunCodex\runtime\endpoint.json"),
    Path(r"C:\Users\Administrator\AppData\Local\TonghuasunCodex\runtime\endpoint.json"),
):
    endpoint = json.loads(path.read_bytes())
    mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    observations.append({
        "endpoint_path": str(path),
        "metadata": {key: endpoint.get(key) for key in (
            "baseUrl", "port", "processId", "startedAtUtc", "listenAddresses", "lanBaseUrls")},
        "file_mtime_utc": mtime.isoformat(),
        "gate": validate_endpoint_identity(endpoint, current_pid=host["Id"],
            host_created_at=host["StartTime"], endpoint_mtime=mtime),
    })
receipt = {
    "at_utc": datetime.now(timezone.utc).isoformat(),
    "host_metadata_source": "endpoint_identity_diagnosis.json",
    "host_pid": host["Id"], "host_creation": host["StartTime"],
    "project_home_unchanged": r"D:\TonghuasunCodex",
    "market_requests": 0, "configuration_tokens_read": False,
    "observations": observations,
    "captured_request_used_this_guard": False, "retry_authorized_by_gate": False,
}
destination = HERE / "endpoint_identity_guard_observation.json"
with destination.open("x", encoding="utf-8", newline="\n") as handle:
    json.dump(receipt, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
print(json.dumps(receipt, ensure_ascii=False, indent=2))
