# Research: `hasaneyldrm/exercises-dataset` — licence, provenance, ID stability

**Issue:** #47 (part of #44) · **Date:** 2026-08-24 · **Method:** primary sources only (repo contents, git history, upstream OpenAPI spec, rights-holder terms, live APIs). No downstream READMEs, badges or blog posts were relied on.

---

## Verdict

**Do not adopt `hasaneyldrm/exercises-dataset`.** It fails on licence.

The repo's own `LICENSE` says MIT, and that is genuine — but the maintainer does not hold the rights he is granting. The content traces to **ExerciseDB v1 / AscendAPI**, whose own published terms say commercial use is **not allowed** without a paid plan, and to **Gym visual**, whose terms **prohibit redistribution entirely**. MyCoach is proprietary and commercial. An MIT grant from a party without title conveys nothing.

**Recommended alternative: `yuhonas/free-exercise-db` (Unlicense / public domain).** Verified clean, 873 records, upstream also public domain. Its one real weakness — name-derived slug IDs — is manageable and quantified below.

---

## 1. Licence

### What the repo actually carries

`LICENSE` (verified identical at the root commit `6990c56` and at `HEAD` `7455efa`) is the MIT text plus a hand-written exception:

> ```
> MIT License
> Copyright (c) 2026 Hasan Emir Yıldırım
> ...
> ------------------------------------------------------------------------------
> MEDIA EXCEPTION
> ------------------------------------------------------------------------------
> The MIT license above covers ONLY the code, tooling, dataset structure, and
> instruction text/translations in this repository.
>
> It DOES NOT cover the exercise media in the `images/` and `videos/`
> directories. That media is © Gym visual (https://gymvisual.com/) and is
> included here with the rights holder's written permission, at 180×180
> resolution... Cloning this repository does not grant you any license to the
> media; obtain your own from Gym visual.
> ```

`NOTICE.md` repeats this and adds:

> "The exercise **data** (names, categories, body parts, equipment, targets, muscle groups, and multilingual instructions) is separate from the media and is released under the MIT License"

**In the data itself:** there is no licence field. Every one of the 1,324 records carries exactly one rights string — `"attribution": "© Gym visual — https://gymvisual.com/"` (verified: the set of distinct `attribution` values across the file has cardinality 1).

**Repo metadata:** GitHub's licence detector returns

> `"license": {"key": "other", "name": "Other", "spdx_id": "NOASSERTION", "url": null}`

i.e. the custom media exception defeats automatic SPDX classification. Anything downstream reporting this repo as plain "MIT" is reading the badge, not the file.

### Why the MIT grant does not hold

Two independent problems, both verified against the rights holders' own words.

**(a) The upstream forbids commercial use.** The real source is ExerciseDB v1 by AscendAPI (see §2). Its OpenAPI description — fetched from `https://oss.exercisedb.dev/swagger`, the API's own machine-readable spec — states:

> | ✅ Allowed | Personal projects, prototypes, educational tools, non-commercial apps, community-driven fitness platforms |
> | ❌ Not allowed | **Commercial products, SaaS platforms, or any monetised use without a paid plan via RapidAPI** |
> | 🖼️ Media | Limited to 180p GIF format only |
> | 📝 Attribution | Credit to [AscendAPI](https://ascendapi.com) is required when using this dataset in any project |

The spec's `info` object contains **no `license` field**. The site footer at `https://oss.exercisedb.dev/` reads "© 2026 AscendAPI. All rights reserved."

This is a **non-commercial** restriction on the base exercise data and instructions — squarely disqualifying under the criterion in this ticket. Note the 180p media limit and the attribution requirement are AscendAPI's terms, reproduced in this repo's `NOTICE.md` but re-attributed to Gym visual.

**(b) Gym visual's terms forbid the redistribution this repo performs.** From `https://gymvisual.com/content/3-terms-and-conditions-of-use`:

> "None of our Media may be resold or redistributed by any means, or made available for redistribution or resale by a third party"

> "Buying the high-resolution Media (purchasing the license) does not transfer the copyright"

The repo publicly redistributes 1,324 GIFs and 1,324 JPEGs. `NOTICE.md` asserts this is covered by "separate written permission", which is precisely the mechanism such terms would require — but that permission is a private claim we cannot verify, and the public terms contain **no** 180×180 carve-out and **no** attribution requirement, contradicting the specific terms `NOTICE.md` attributes to Gym visual. The 180p limit and attribution requirement appear verbatim in AscendAPI's terms instead, which is the more parsimonious explanation of where they came from.

**Confidence: high** that the media is unusable. **Confidence: high** that the base data carries a non-commercial restriction. **Confidence: medium-high** that this defeats the MIT grant on the *instruction text* specifically (expressive prose, clearly protectable). **Lower confidence** on the bare factual columns — exercise name, body part, equipment, target — which attract thin-to-no copyright protection in most jurisdictions; a lawyer might well say those specific fields are free for the taking regardless of what any of these licences say. That is a legal judgement, not an engineering one, and I am not making it.

---

## 2. Provenance

The chain, established from the repo's own issue tracker and verified independently:

```
Gym visual (media rights holder, all rights reserved)
  └─> ExerciseDB v1 / AscendAPI  (non-commercial free tier; paid commercial plans)
        └─> Kaggle re-host: omarxadel/fitness-exercises-dataset   [UNVERIFIED — see below]
              └─> hasaneyldrm/exercises-dataset  (adds 10-language translations, browser UI, MIT LICENSE)
```

**Issue #5** on the upstream repo — *"Dataset scraped from ASCENDAPI (ascendapi.com) without attribution"*, opened by `shinkaidev`, now CLOSED — is the key primary document. The reporter observed that media filenames follow `{numeric}-{exerciseId}.gif` where the second segment is the literal ExerciseDB v1 `exerciseId`. The maintainer's closing comment:

> "Verified — the `exerciseId`s embedded in our media filenames resolve directly on `static.exercisedb.dev` (e.g. `static.exercisedb.dev/media/EIeI8Vf.gif`), and the asset is byte-for-byte identical (same SHA-256) to this repo's `videos/0025-EIeI8Vf.gif`. So the media and base exercise data are indeed from ExerciseDB v1."

**I reproduced this independently rather than taking his word for it:**

```
https://static.exercisedb.dev/media/EIeI8Vf.gif                              124389 bytes
https://raw.githubusercontent.com/hasaneyldrm/.../videos/0025-EIeI8Vf.gif    124389 bytes
sha256 (both) = 2de66afbc9229d7c23b888b39b3c6a917ce950b429082050be29bd8f96c85d75
```

Byte-identical. Provenance confirmed at the artefact level, not merely asserted.

### The attribution the maintainer promised is not in the repo

This is the part that should weigh most heavily on the decision. In closing #5 the maintainer wrote:

> "I've updated the README with clear attribution to **[ExerciseDB v1 by AscendAPI](https://oss.exercisedb.dev)** as the source of the media and base exercise data, noted that the Kaggle dataset was an intermediary re-host... **(see commit 92e2704)**"

Checking the repository as it stands today:

- `git cat-file -t 92e2704` → `fatal: Not a valid object name`. **The cited commit does not exist.**
- The entire history is 12 commits rooted at `6990c56` (2026-07-08) — but the repo was created **2026-03-18**, and every record in `exercises.json` has `created_at: "2026-03-18T..."`. The history has been squashed or force-pushed.
- I grepped **all seven** historical revisions of `README.md` for `exercisedb|ascendapi|kaggle|scrape`. **Zero hits in every revision.** The only provenance story present at any point in the surviving history is the Gym visual one.

So the public record is: a well-evidenced scraping report, a maintainer commitment to attribute AscendAPI, and then a repository whose history no longer contains that commit and whose README instead tells a different story — one asserting private written permission from a different party. Whether that was deliberate or an artefact of a history rewrite, the repo's own account of where its data comes from is not reliable, which is exactly the failure mode this ticket was opened to guard against.

Separately, **issue #3** ("Copyright issues?", still open) has a commenter stating:

> "if you include this repo as-is in your project, you might receive a letter from a lawyer regarding a copyright infringement... As this is currently handled, this looks like a 'copyright trap' to me"

and another:

> "You can't declare something as 'open source' when you are not the owner."

**Where the trail goes cold:** the Kaggle intermediary. `kaggle.com/datasets/omarxadel/fitness-exercises-dataset` returned no usable content to automated fetching, and `dub.sh/exercisedb-api-tos` (AscendAPI's full ToS) returned HTTP 403/429. I therefore **could not verify** the Kaggle dataset's stated licence, nor read AscendAPI's complete terms — only the usage-restriction table embedded in their OpenAPI spec, which is itself first-party and unambiguous. In issue #5 a third party reports the Kaggle author "mentioned he bought each for 1 dollar" and did not say from whom; the maintainer replied that this "does not seem to clearly match AscendAPI's current pricing/licensing". That link in the chain is unresolved and, on the evidence, was unresolved when the issue was closed.

---

## 3. ID stability

**Structurally sound; empirically untested.** This is the one dimension on which the dataset does well.

Verified by extracting `data/exercises.json` at the root commit and at `HEAD` and diffing:

- 1,324 records at both ends; 1,324 distinct `id` values; **zero** additions, removals or reorderings.
- The `(id, name)` pair set is **identical** across the entire history — `diff` output empty.
- IDs are **not array indices**: they are zero-padded 4-char strings, sparse, ranging `0001`–`5201`. Only 3 of 1,324 records happen to sit at the array position matching their ID. The array is not sorted by ID.
- IDs are **not name-derived slugs** — `id` and `name` are independent, so renaming an exercise cannot change its ID.
- Each record additionally carries `media_id` (e.g. `"2gPfomN"`), the opaque upstream ExerciseDB `exerciseId`. This is the more durable key of the two, since it is the upstream's own identifier rather than this repo's renumbering.

**Caveat, and it matters:** all seven commits touching `data/` after the root import add *translations only*. No exercise has ever been added, removed or renamed in the visible history, so ID stability under mutation has **never actually been exercised**. Combined with the fact that the history was rewritten (§2), "the IDs never changed" is weaker evidence than it looks. There are no git tags and no GitHub releases, so there is no versioning contract to rely on either.

**Assessment:** the ID *scheme* is well-formed and would be safe to use as a join key. The *repo* offers no stability guarantee. Since the sparse `0001`–`5201` numbering and the `media_id` both originate upstream, the durable key here is really AscendAPI's — which is only available to us on AscendAPI's terms.

---

## 4. Coverage and shape

| Property | Value |
|---|---|
| Records | 1,324 |
| Format | Single JSON array, `data/exercises.json` (17.4 MB) |
| Schema | `data/exercises.schema.json`, JSON Schema 2020-12 |
| Media | 1,324 GIFs + 1,324 JPEGs, 180×180 — **not licensed to us** |

Fields: `id`, `name`, `category`, `body_part`, `equipment`, `target`, `muscle_group`, `secondary_muscles[]`, `instructions.{en,es,it,tr,ru,zh,hi,pl,ko,fr}`, `instruction_steps.<lang>[]`, `media_id`, `image`, `gif_url`, `attribution`, `created_at`.

Equipment and muscle-group metadata is present and rich (`category` and `body_part` are redundant duplicates). Coverage by body part: upper arms 292, upper legs 227, back 203, waist 169, chest 163, shoulders 143, lower legs 59, lower arms 37, cardio 29, neck 2. By equipment: body weight 325, dumbbell 294, cable 157, barbell 154, leverage machine 81, band 54, smith machine 48, kettlebell 41.

**Variations are flat, not hierarchical.** There is no parent/variant relationship — every variation is an independent top-level record, named equipment-first and lowercased. "Incline Dumbbell Bench Press" does not exist as such; the dataset has `dumbbell incline bench press` as its own record, alongside 32 other `*bench press*` records (`barbell incline bench press`, `barbell close-grip bench press`, `barbell decline bench press`, `barbell guillotine bench press`, …). For MyCoach this is arguably the right shape — each thing a user logs is one row — but it means no free grouping of "all bench press variants" without building that layer yourself.

### Mapping onto MyCoach's names

`GymWorkoutDetail.exercise_title` originates from Hevy CSV import (`src/mycoach/sources/hevy/csv_parser.py`), and `RoutineExercise.exercise_name` is free text (`String(200)`). Hevy names exercises `"Bench Press (Barbell)"`; this dataset names them `"barbell bench press"`. I tested 10 representative Hevy-style titles:

- **Raw case-insensitive match: 0/10.**
- After a naive normalisation (move the parenthesised equipment to the front, lowercase): **5/10**. Failures were `Squat (Barbell)` → dataset has `barbell full squat`; `Lat Pulldown (Cable)` → `cable pulldown`; `Bicep Curl (Dumbbell)` → `dumbbell biceps curl` (bicep/biceps); `Overhead Press (Barbell)`; `Leg Press (Machine)` → `leverage machine` naming.

So roughly half of a routine would need a hand-built crosswalk regardless of which dataset is chosen. **This cost is not specific to this dataset and should not drive the choice** — but it does mean adopting stable IDs is a larger job than a join, and the crosswalk is the real deliverable.

---

## 5. Alternatives

### ✅ `yuhonas/free-exercise-db` — **recommended**

**Licence: The Unlicense (public domain).** GitHub metadata reports `"spdx_id": "Unlicense"`, and `LICENSE.md` contains the full canonical text:

> "This is free and unencumbered software released into the public domain. Anyone is free to copy, modify, publish, use, compile, sell, or distribute this software... **for any purpose, commercial or non-commercial**, and by any means."

**Provenance is clean and traceable to a public-domain root.** Its README states it derives from `wrkout/exercises.json`:

> "I stumbled upon [exercises.json](https://github.com/wrkout/exercises.json) which was amazing though the data wasn't structured the way I wanted it... so I restructured the data and built a simple frontend to it"

I checked that upstream directly: `wrkout/exercises.json` is **also Unlicense** (`"spdx_id": "Unlicense"`, full text in its `LICENSE.md`), and its README states the intent explicitly — *"a complete and extensive open dataset of exercises that sits within the public domain"*. Notably, the same author sells a larger commercial dataset at `wrkout.xyz`, which is a good sign: the free/paid boundary is deliberate and stated, so the public-domain dedication on the free tier is a considered act rather than a careless badge. **This is the strongest licence position of any candidate, and unlike the Gym visual/AscendAPI chain there is no rights holder further upstream with a contrary claim.**

**Shape:** 873 records (verified by fetching `dist/exercises.json` and counting). Fields: `id`, `name`, `force`, `level`, `mechanic`, `equipment`, `primaryMuscles[]`, `secondaryMuscles[]`, `instructions[]`, `category`, `images[]`. Includes two JPEG photos per exercise, **covered by the same public-domain dedication** — a material advantage over the alternative, where media is the whole problem. Richer training metadata than the other candidate (`force`, `level`, `mechanic` have no equivalent there); no multilingual instructions, English only.

**ID stability — the one real weakness, and it is a genuine one.** IDs are name-derived slugs (`3_4_Sit-Up`, `Alternate_Incline_Dumbbell_Curl`), so an ID is only as stable as the exercise's name. This has **demonstrably broken before**. From the git history:

- `7c9a656` (2023-04-20) — *"Add unique exercise ID's, cleanup non id conforming exercise id's, names & directories"*
- `7811853` (2023-04-20) — *"fix broken image dirs as exercise id has changed"*

and the renames are visible in the tree: `Band_Good_Morning_(Pull_Through).json` → `Band_Good_Morning_Pull_Through.json`, `Bicycling,_Stationary.json` → `Bicycling_Stationary.json`, `Child's_Pose.json` → `Childs_Pose.json` — a punctuation-stripping sweep that changed IDs wholesale.

**But that was a one-off normalisation, and the scheme has been stable since.** I diffed the ID set from `7c9a656` to `HEAD`: **873 → 873, zero removed, zero changed**, across ~3 years and the whole subsequent history (last data change `5197c05`, Jan 2024). The slugs are now all punctuation-free and conform to a linted schema enforced in CI, so the class of change that broke them has already been applied and cannot recur in the same form.

The residual risk — a future typo fix silently changing a join key — is real but small and, decisively, **it is mitigable on our side**: it is public domain, so we can vendor `dist/exercises.json` at a pinned commit into our own repo and own the IDs outright. We cannot do that with the other dataset at any price, because there the blocker is rights, not mechanics. **A mitigable ID risk beats an unmitigable licence risk.**

### ⚠️ wger — usable only in a 21-record slice

**Licence: copyleft. Disqualifying for our purposes.** The repo README states the split precisely:

> ```
> * Application Code: AGPL-3.0-or-later
> * Exercise/Ingredient Data: Creative Commons (see individual entries)
> * Documentation: CC-BY-SA-4.0
> ```

Crucially the data licence is **per-entry**, not repo-wide, so no single answer exists — you must check each record. I queried the live API (`https://wger.de/api/v2/exerciseinfo/?limit=900`) and tallied the actual distribution across all 861 exercises:

| Licence | Count |
|---|---|
| CC-BY-SA 4 | 712 |
| CC-BY-SA 3 | 128 |
| CC0 | 21 |

**97.6% is ShareAlike.** CC-BY-SA is copyleft: incorporating it into MyCoach's exercise catalogue would arguably require releasing that adapted database under CC-BY-SA. That is exactly the outcome this ticket was written to prevent. Only the 21 CC0 records are unencumbered — far too few to build on.

Worth recording that wger has **the best ID design of the three**: every exercise carries a stable `uuid` (e.g. `1b020b3a-3732-4c7e-92fd-a0cec90ed69b`) alongside its numeric `id`, which is genuinely opaque and rename-proof. It is the right answer on ID stability and the wrong one on licence. If the licence position ever changes, revisit it.

### ❌ ExerciseDB / AscendAPI direct

The actual upstream. Non-commercial free tier (quoted in §1); commercial use requires a paid RapidAPI plan. `ExerciseDB/exercisedb-api` on GitHub is AGPL-3.0, but that covers the **API server code**, not the data — and AGPL would be its own problem for a proprietary service. **If the 1,324-exercise catalogue with GIFs is genuinely wanted, the honest route is to buy a commercial licence from AscendAPI**, not to take it via an MIT-relabelled mirror. That is a product/budget decision, not a technical one, and worth putting in front of whoever owns the spec — the media quality is the actual draw here, and it is purchasable.

---

## Recommendation

1. **Do not use `hasaneyldrm/exercises-dataset`.** Not the media (redistribution prohibited by Gym visual's terms), and not the data (non-commercial restriction upstream, plus a maintainer whose stated provenance is contradicted by his own repository's history).
2. **Adopt `yuhonas/free-exercise-db`** — Unlicense, public-domain upstream, 873 exercises with usable images.
3. **Vendor it at a pinned commit** rather than joining against it live. Public domain makes this unambiguously legal, and it converts the slug-ID risk from "upstream might rename something" into "we control our own key." Assign MyCoach's own surrogate IDs on import and keep the upstream slug as a lookup column, not as the primary key.
4. **Budget for the name crosswalk** — measured at ~50% exact-match after normalisation against Hevy-style titles. This is unavoidable and is the bulk of the work; it is not a reason to prefer one dataset over another.
5. **If the GIF media is the real requirement**, price a commercial AscendAPI licence and decide deliberately. Do not route around it.

## What I could not verify

- The Kaggle intermediary's stated licence (`omarxadel/fitness-exercises-dataset`) — page not retrievable by automated fetch.
- AscendAPI's **full** terms of service — `dub.sh/exercisedb-api-tos` returned 403/429. I relied on the usage-restriction table embedded in their own OpenAPI spec, which is first-party and explicit, but is a summary.
- Whether Gym visual did in fact grant `hasaneyldrm` written permission. Unfalsifiable from outside; the published terms and the missing AscendAPI attribution both cut against it.
- Whether the bare factual fields (name/body part/equipment) attract copyright at all. A genuine legal question, deliberately not answered here.
- The exact `exercise_title` values in production. I tested against representative Hevy-format names, not real user data; the real match rate could differ in either direction.
