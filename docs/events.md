# Simulation events (draft)

**Status: draft. Frozen at milestone M4 (R2-P4).** The catalogue, envelope, SSE framing and
state machine are specified in roadmap §9.5.

Implementation notes are added in R2-P4. Every event is persisted before it is published, and
replay uses `Last-Event-ID`.
