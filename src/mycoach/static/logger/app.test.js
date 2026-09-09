const test = require("node:test");
const assert = require("node:assert/strict");
const { repRangeLowerBound, numOrNull, toPayload, pruneEmptySets } = require("./app.js");

test("repRangeLowerBound reads the lower bound of a range like '8-10'", () => {
    assert.equal(repRangeLowerBound("8-10"), 8);
});

test("repRangeLowerBound reads a bare number as its own lower bound", () => {
    assert.equal(repRangeLowerBound("12"), 12);
});

test("repRangeLowerBound returns null for empty or unparseable input", () => {
    assert.equal(repRangeLowerBound(""), null);
    assert.equal(repRangeLowerBound(null), null);
    assert.equal(repRangeLowerBound("failure"), null);
});

test("numOrNull parses a numeric string with the given parser", () => {
    assert.equal(numOrNull("82.5", parseFloat), 82.5);
});

test("numOrNull treats an empty string as null, not NaN", () => {
    assert.equal(numOrNull("", parseFloat), null);
});

test("numOrNull treats unparseable input as null", () => {
    assert.equal(numOrNull("abc", parseFloat), null);
});

test("toPayload flattens a session's exercises into one flat sets array", () => {
    const session = {
        id: "s1",
        title: "Push day",
        start_time: "2026-09-01T10:00:00Z",
        end_time: "2026-09-01T11:00:00Z",
        notes: null,
        exercises: [
            {
                title: "Bench Press",
                notes: null,
                superset_group: null,
                sets: [
                    { weight_kg: 80, reps: 5, rpe: 8, set_type: "normal", prescribed_weight_kg: 80, prescribed_reps: 5 },
                    { weight_kg: 82.5, reps: 4, rpe: null, set_type: "normal" },
                ],
            },
        ],
    };

    const payload = toPayload(session);

    assert.equal(payload.external_id, "s1");
    assert.equal(payload.sport, "gym");
    assert.equal(payload.sets.length, 2);
    assert.deepEqual(payload.sets[0], {
        exercise_title: "Bench Press",
        exercise_notes: null,
        set_index: 1,
        set_type: "normal",
        superset_id: null,
        weight_kg: 80,
        reps: 5,
        rpe: 8,
        prescribed_weight_kg: 80,
        prescribed_reps: 5,
    });
    assert.equal(payload.sets[1].set_index, 2);
    assert.equal(payload.sets[1].prescribed_weight_kg, null);
});

test("pruneEmptySets drops sets with neither weight nor reps", () => {
    const exercises = [
        {
            title: "Squat",
            sets: [
                { weight_kg: 100, reps: 5 },
                { weight_kg: null, reps: null },
                { weight_kg: null, reps: 3 },
            ],
        },
    ];

    pruneEmptySets(exercises);

    assert.equal(exercises[0].sets.length, 2);
    assert.deepEqual(exercises[0].sets.map((s) => s.reps), [5, 3]);
});
