"""Local OTLP/exporter/dashboard smoke; contains no personal input."""

import json
import os
import re
import time
from urllib.request import urlopen

os.environ["PLANNER_OTLP_ENDPOINT"] = "http://127.0.0.1:24318"
from planner.db.session import create_db_engine
from planner.observability.runtime import Telemetry, span, use
from planner.settings import Settings

telemetry = Telemetry(sample_ratio=1)
engine = create_db_engine(Settings())
try:
    telemetry.observe_database(engine)
    with use(telemetry), span("incident.recovery", reason_code="SYNTHETIC_SMOKE"):
        telemetry.measure(
            "planner.api.requests", 1, route="/synthetic-smoke", method="GET", status="2xx"
        )
    telemetry.meter_provider.force_flush(timeout_millis=3000)
    telemetry.provider.force_flush(timeout_millis=3000)
    for _attempt in range(30):
        with urlopen("http://127.0.0.1:28889/metrics", timeout=3) as response:
            body = response.read().decode()
        if re.search(r"^planner_db_reachable\{[^\n]*\} 1$", body, re.M):
            break
        time.sleep(0.2)
    assert re.search(r"^planner_db_reachable\{[^\n]*\} 1$", body, re.M), "Database gauge missing"
    assert "planner_api_requests_count" in body
    assert "owner_id" not in body and "plan_id" not in body
    with urlopen("http://127.0.0.1:23000/api/health", timeout=3) as response:
        grafana = json.load(response)
    assert grafana["database"] == "ok"
    print(
        json.dumps(
            {
                "collector": "OTLP/HTTP",
                "database_gauge": 1,
                "api_histogram": True,
                "grafana_version": grafana["version"],
            }
        )
    )
finally:
    telemetry.shutdown()
    engine.dispose()
