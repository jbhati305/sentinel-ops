# Detection Strategy

The detector is designed to produce useful operator incidents rather than raw alarm
spam.

Rules are layered and implemented as small classes:

1. `TelemetryValidator` catches bad units, implausible values, future timestamps,
   and abrupt discontinuities before storage.
2. `AnomalyDetector` catches missing metrics, full-device silence, sensor faults,
   sudden failures, flatlines, and persistent threshold breaches.
3. `TrendDetector` finds gradual deterioration and correlated multivariate
   patterns before a hard threshold is crossed.
4. `AlertEngine` suppresses duplicate incident spam and resolves alerts only after
   hysteresis conditions are met.
5. `HealthScorer` turns active incidents into a compact state for triage.

Why not a black-box ML model?

The project uses simulated data and has no labelled failure history. A black-box
model would be hard to defend and hard for operators to trust. The prototype uses
deterministic, explainable rules that could later be combined with learned models
once real history exists.

The most important design choice is event-level noise versus incident-level alerts:
many bad readings can update one open alert, and healthy readings resolve it only
after a short hysteresis window.
