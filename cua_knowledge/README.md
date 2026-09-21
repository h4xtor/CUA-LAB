# Curated CUA knowledge

Runtime writes are restricted to validated Learning JSON records under global/learned/<id>.json or machines/<machine-hash>/<id>.json. IDs are derived from fixed enum values; no model-controlled path or free text is accepted. The runtime cannot write this README, application source, workflows or scripts.

No seeded record is presented as an empirical observation. This bank starts empty. Local candidates become eligible after a verified success and confidence >= 0.6; automatic sync requires >= 0.8. Counter-based confidence is a smoothed success ratio, not a calibrated probability. Current observations always override knowledge. Current-machine records are not applied to other machines.

Global knowledge can be curated by the developer after cross-machine validation. Runtime detections conservatively start machine-scoped. A separate CUA_LAB_GITHUB_TOKEN with repository Contents permission is needed for optional sync; application code restricts its use to the closed knowledge schema and paths.
