# MyCoach

MyCoach turns an athlete's health and training data into an evolving plan, then learns from what the athlete actually performs.

## Gym coaching

**Exercise**:
A gym movement whose identity stays stable even when its displayed wording changes.
_Avoid_: Movement, lift

**Exercise ID**:
The stable identity of a catalogue exercise. An exercise without one is custom and cannot be compared across sessions automatically.
_Avoid_: Exercise name, exercise title

**Exercise title**:
The human-readable label shown for an exercise and retained with a workout as display history; it is never identity.
_Avoid_: Exercise name

**Catalogue exercise**:
An exercise with an Exercise ID that can participate in prescriptions, history comparison, and progressive-overload reasoning.

**Local catalogue exercise**:
A Catalogue exercise owned by MyCoach because the upstream catalogue does not represent the athlete's movement precisely enough.

**Custom exercise**:
A freely entered exercise with no Exercise ID. It remains visible in workout history but is excluded from cross-session reasoning until promoted or mapped.
