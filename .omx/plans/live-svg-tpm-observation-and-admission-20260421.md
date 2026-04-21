## Requirements Summary

Add live Qwen CLI usage observation for running SVG turns, expose rolling TPM evidence in logs and metrics, and use that live signal to reduce the over-conservative SVG completion/admission behavior seen in `projects/421_4`.

## Acceptance Criteria

- Running SVG CLI turns emit periodic live usage/rolling TPM logs without waiting for turn completion.
- Live SVG token observations are written to Redis when Redis is available.
- API metrics expose a live SVG rolling TPM snapshot.
- SVG admission can use live rolling TPM plus a bounded startup reserve.
- The existing estimated lease path remains available as a fallback via config.
- The code passes targeted syntax checks.

## Implementation Steps

1. Add live usage extraction/monitoring helpers in `skills/ppt-master/scripts/qwen_ppt_runner.py`.
2. Start a background monitor for each CLI Qwen turn and emit periodic live usage snapshots/logs.
3. Persist live SVG token events into Redis and add helpers to read rolling window usage.
4. Update SVG budget lease logic to prefer live rolling TPM admission and optionally bypass the completion bucket guard.
5. Surface live rolling TPM data in `api_service/app.py` metrics payload.
6. Document the new behavior and config in `api_service/README.md` and `.env.api.example`.

## Risks And Mitigations

- Chat recording may appear late: keep the monitor tolerant and perform a final drain after the subprocess exits.
- Live admission could become too permissive: keep bounded startup reserve and a config switch back to the old completion guard.
- Redis growth from live events: trim rolling windows aggressively and keep event members compact.

## Verification Steps

1. Run Python syntax checks on `skills/ppt-master/scripts/qwen_ppt_runner.py` and `api_service/app.py`.
2. Inspect generated metrics payload keys and ensure live fields are present.
3. Confirm the new env vars are documented.
