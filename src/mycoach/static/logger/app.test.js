const test = require("node:test");
const assert = require("node:assert/strict");
const {
    repRangeLowerBound,
    numOrNull,
    toPayload,
    pruneEmptySets,
    topSetForExercise,
    resolveExerciseChoice,
    sessionExerciseFromRoutine,
} = require("./app.js");

test("resolveExerciseChoice turns a cached catalogue name into its stable id", () => {
    const choice = resolveExerciseChoice("barbell squat", [
        { id: "Barbell_Squat", name: "Barbell Squat" },
    ]);

    assert.deepEqual(choice, {
        exercise_id: "Barbell_Squat",
        title: "Barbell Squat",
    });
});

test("sessionExerciseFromRoutine carries stable identity into offline state", () => {
    const exercise = sessionExerciseFromRoutine({
        exercise_id: "Barbell_Squat",
        exercise_name: "Barbell Squat",
        notes: null,
        sets: 3,
        rep_range: "8-10",
        superset_group: null,
    });

    assert.equal(exercise.exercise_id, "Barbell_Squat");
    assert.equal(exercise.title, "Barbell Squat");
});

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
                exercise_id: "Barbell_Bench_Press_-_Medium_Grip",
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
        exercise_id: "Barbell_Bench_Press_-_Medium_Grip",
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

test("topSetForExercise picks the heaviest working set", () => {
    const ex = {
        sets: [
            { weight_kg: 80, reps: 8, set_type: "normal" },
            { weight_kg: 100, reps: 3, set_type: "normal" },
            { weight_kg: 90, reps: 5, set_type: "normal" },
        ],
    };
    assert.equal(topSetForExercise(ex), ex.sets[1]);
});

test("topSetForExercise breaks ties in favour of the first set reached", () => {
    const ex = {
        sets: [
            { weight_kg: 100, reps: 5, set_type: "normal" },
            { weight_kg: 100, reps: 4, set_type: "normal" },
        ],
    };
    assert.equal(topSetForExercise(ex), ex.sets[0]);
});

test("topSetForExercise never picks a warmup set", () => {
    const ex = {
        sets: [
            { weight_kg: 120, reps: 5, set_type: "warmup" },
            { weight_kg: 100, reps: 5, set_type: "normal" },
        ],
    };
    assert.equal(topSetForExercise(ex), ex.sets[1]);
});

test("topSetForExercise returns null when every set is a warmup", () => {
    const ex = { sets: [{ weight_kg: 60, reps: 8, set_type: "warmup" }] };
    assert.equal(topSetForExercise(ex), null);
});

test("topSetForExercise returns null with no sets at all", () => {
    assert.equal(topSetForExercise({ sets: [] }), null);
});

test("topSetForExercise treats a bodyweight exercise's first working set as top", () => {
    const ex = {
        sets: [
            { weight_kg: null, reps: 12, set_type: "normal" },
            { weight_kg: null, reps: 10, set_type: "normal" },
        ],
    };
    assert.equal(topSetForExercise(ex), ex.sets[0]);
});
