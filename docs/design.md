# Dirty data generation package — design document

## Philosophy and boundaries of concern

### What this package is

This package generates synthetic, structured, dirty data for testing entity resolution pipelines. It produces data that is perturbed in known, trackable ways, and provides a correctness oracle that can answer questions about the true state of the data at any point in the pipeline.

The core value proposition is that the package knows the full provenance of every record it generates. This makes it possible to answer not just "did my algorithm get the right answer?" but "why did it get the wrong answer, and which perturbation types caused failures?"

### What this package is not

This package is not:

- An entity resolution algorithm or pipeline
- A statistical benchmarking framework — it provides the raw materials for metrics, not the metrics themselves
- A general synthetic data generator — it generates data specifically shaped for entity resolution problems
- A graph database or storage layer — it produces outputs that can be projected into whatever representation the user needs

The clustering step — converting a scored edge list into resolved clusters — is out of scope. Users bring their own clustering logic and present the results in the common resolved format this package accepts.

### Declarative design

The API is declarative. Users describe the *properties* they want their data to have — how many entities, which sources, what overlap between them, what perturbation rules apply — and the package works out how to generate data satisfying those properties exactly. Users never specify generation procedures.

This is deliberate. Test data should describe the shape of the problem being tested, not the procedure used to produce it. A declarative API also makes constraint conflicts visible and reportable, because all constraints are first-class objects that can be reasoned about before any data is generated.

### Scale

The package is designed to work correctly at small scale first. The current generation internals — Faker-per-record with a uniqueness proxy — are known to be slow at large scale. This is an accepted limitation for MVP and a known refactor target. The data structures and constraint system are designed so that swapping in a vectorised generation backend does not require API changes.

---

## Assumptions about usage

These assumptions are drawn from the design conversation and inform tradeoffs throughout.

**Users are testing entity resolution logic, not data pipelines.** The primary use case is a developer or data scientist building matching rules or evaluating a linkage algorithm. The package is used in test suites and Jupyter notebooks, not in production pipelines.

**Users want exact properties, not approximate ones.** Because a test might assert "there are exactly 60 entities in source A", the constraint system must satisfy declared constraints exactly or raise an informative error. Approximate satisfaction with a report of what was achieved is not acceptable for count constraints.

**Users will drill down on failures.** The correctness oracle is not just for pass/fail. Users will inspect specific clusters, specific records, and specific perturbation types to understand why their algorithm failed. The oracle API is designed around this exploratory workflow.

**The downstream representation is unknown.** Users may project the generated data into SQL tables, Polars DataFrames, NetworkX graphs, knowledge graphs, or other formats. The package exports a minimal set of maximally flexible outputs — datasets, nodes, and edges — and makes no assumptions about the downstream representation.

**Some users are not testing cleaning rules.** Perturbation absence is a valid and common configuration. The package does not warn or error when a feature has no perturbations applied.

**Key namespaces are independent across sources.** A core property of entity resolution problems is that the same real-world entity has a different identifier in each source system. The package enforces this: keys are generated independently per source, and the same entity will never share a key value across sources.

---

## Decision log

### Declarative over imperative API

**Decision:** the top-level API is declarative. Users declare properties; the solver generates data satisfying them.

**Reason:** test data should describe the problem being tested, not the procedure used to produce it. Declarative APIs also make constraint conflicts visible and reportable.

### Two output bundles, one container

**Decision:** `generate()` returns a single `Bundle` object with two aspects: `.data` and `.correctness`.

**Reason:** raw data and correctness information serve different consumers but belong to the same generation run. Separating them into two objects would require users to keep them in sync. Provenance is part of the correctness bundle, not a third top-level object, because it is the explanation of why the correct answer is what it is — the same intellectual operation as correctness checking, at a different level of detail.

### Sources are first-class concepts

**Decision:** `Source` is a first-class type in the package API.

**Reason:** entity resolution is fundamentally about reconciling data from different source systems. The key clash problem — the same entity having different primary keys in different systems — is the core difficulty the package is designed to generate. Sources cannot be implicit.

### Keys are a constrained subclass of Feature

**Decision:** `Key` subclasses `Feature` with two additional enforced constraints: uniqueness within source, and independent namespace per source. Keys do not accept perturbation rules.

**Reason:** keys don't drift — they are simply different across sources. This is what distinguishes a key from a regular feature with a uniqueness constraint. Allowing perturbations on keys would conflate two distinct concepts.

### Perturbations belong at the (feature, source) pairing

**Decision:** perturbation rules are declared on the source, scoped to a specific feature, not on the feature itself.

**Reason:** what goes wrong with a field is a property of the source system, not the field. OCR errors happen because a document was scanned; suffix variations happen because one system normalises legal entity types and another does not. The feature describes what the data *is*; the source describes what goes wrong with it *in that system*.

### Shared feature universe, disjoint subsets per source

**Decision:** features exist in a shared universe. Each source declares which features it exposes. Two sources may have entirely disjoint feature sets.

**Reason:** this is the natural model of real-world data. Different systems expose different attributes of the same underlying entity. The feature namespace is shared so that the correctness bundle can reason about feature-level provenance across sources.

### Typed entities

**Decision:** entities in the pool have types. The entity pool is typed from the outset, even in MVP which exercises only one type.

**Reason:** entity resolution over typed graphs — where, for example, company records and corporate group records are distinct entity types — is the same problem as single-type resolution with typed inputs. Constraining to a single type now would require a breaking change to add types later. The data model accommodates types naturally at negligible cost.

### Connected components is out of scope

**Decision:** the package does not perform clustering. The resolved cluster format — `(cluster_id, entity_type, source, key)` — is the accepted input to the correctness oracle.

**Reason:** the choice of clustering algorithm is a meaningful decision that affects results. Deduplication algorithms may use connected components, voting, probabilistic models, or trained classifiers. Owning this step would mean either mandating a specific algorithm or maintaining multiple. Neither is appropriate for a package whose purpose is evaluation.

### Stochastic perturbations excluded from MVP

**Decision:** MVP includes only deterministic perturbation rules. Stochastic perturbations (random character transpositions, OCR error simulation) are out of scope for MVP.

**Reason:** stochastic perturbations require the perturbation rule to have access to the RNG, which changes the rule interface and complicates the constraint solver. The value for MVP is low relative to the complexity introduced. The rule interface is designed to accommodate stochastic rules later without breaking changes.

### Two-phase constraint solver

**Decision:** constraint validation runs in two phases. Phase one checks count constraints as a system of linear integer equations. Phase two checks value constraints — generator cardinality, uniqueness preservation under perturbation rules — statically where possible.

**Reason:** count constraints and value constraints are structurally different problems. Count constraints are a small linear integer system, tractable to solve exactly. Value constraints depend on the generated values themselves and cannot always be checked symbolically, but a static pre-check catches most failure modes before generation is attempted.

### Implicit vs explicit boundary values

**Decision:** the solver distinguishes between boundary values that were explicitly declared by the user and those that emerged implicitly from solving other constraints. Implicit boundary values — for example, zero overlap between two sources that the user never declared should have zero overlap — surface as warnings. Explicit boundary values are honoured silently.

**Reason:** an implicit zero almost always indicates an unintended consequence of constraint interaction. An explicit zero is a deliberate edge case test. The distinction matters for usability.

### Reasonableness defaults

**Decision:** the solver applies implicit reasonableness checks: every source has overlap with at least one other source; every entity type appears in at least two sources. Violating these implicitly surfaces as a warning; violating them explicitly is permitted.

**Reason:** data with no cross-source overlap cannot be used to test entity resolution. Generating it silently would waste the user's time.

### Provenance is deterministic only for MVP

**Decision:** the provenance log records only deterministic perturbations for MVP.

**Reason:** stochastic perturbations require RNG access in the rule interface. Deferring stochastic perturbations defers this complexity entirely.

### Scale strategy deferred

**Decision:** the generation algorithm is not redesigned for scale in MVP. The constraint system, data structures, and API are designed so that a vectorised generation backend can be substituted without API changes.

**Reason:** the package is designed to work correctly at small scale first. The Faker-per-record approach is the correct thing to validate the design against. Premature optimisation of the generation internals risks building the wrong abstraction.

---

## Module overview

### `entities`

The abstract ground truth layer. Contains the data structures that represent real-world entities independently of any source system or output format.

**Core types:**
- `EntityPool` — the set of all true entities, typed. The authoritative source of ground truth.
- `EntityType` — a named type label for entities in the pool.
- `SourceEntity` — a single true entity with its base feature values and a record of which keys it maps to in which sources. Equality is based on base values.
- `ClusterEntity` — a derived view of one or more entities as seen from a subset of sources. Supports set algebra: addition merges two cluster entities; subtraction diffs them; containment checks subset relationships.
- `EntityReference` — a mapping from source name to set of primary keys. Immutable and hashable. Supports union and subset operations.

**Key design decisions:** `ClusterEntity` algebra is the foundation of the correctness oracle. The `+`, `-`, and `__contains__` operations make diffing natural and composable. `SourceEntity.to_cluster_entity(*sources)` is the bridge between ground truth and the correctness check.

**Open implementation questions:** whether `EntityPool` is lazy or eager — whether entities are generated on construction or on `generate()`. Likely eager for MVP given small scale assumption.

---

### `features`

Declarations of data shape, type, and the perturbation rules that can be applied.

**Core types:**
- `Feature` — a named field with a generator configuration and a datatype. Does not own perturbation rules — those are declared at the source level.
- `Key` — subclass of `Feature`. Enforces uniqueness within source and independent namespace per source. Does not accept perturbation rules.
- `FeatureConfig` — frozen configuration object for a feature, including generator name, parameters, and whether the generator enforces uniqueness.

**Perturbation rules:**
- `VariationRule` — abstract base. Implements `apply(value) -> value` and exposes `type` for the Python type it operates on.
- `SuffixRule`, `PrefixRule`, `ReplaceRule` — deterministic string rules. MVP scope.
- Stochastic rules (character transposition, OCR simulation) — post-MVP. Interface is designed to accommodate them: rules need access to the RNG, which will be injected at generation time.

**Open implementation questions:** whether `drop_base` — the option to omit the unperturbed base value from a source — belongs on the feature config or the source declaration. Logically it belongs on the source since it describes how the source presents the feature, not the feature itself.

---

### `sources`

Declarations of source systems and how they present entities.

**Core types:**
- `Source` — a named source with a `Key` and a set of `(Feature, [VariationRule])` pairings. Stateless declaration — it does not reference the pool at construction time.
- `SourceTestkit` — the materialised output of a source after generation: the data table, the entity-to-key mapping, and the cluster entities that were generated.

**Key design decisions:** sources are stateless declarations. The relationship between a source and the pool is established at `generate()` time, not at construction. This makes sources reusable across multiple generation runs and avoids implicit shared state.

**Open implementation questions:** whether `repetition` — the number of times an entity can appear as multiple distinct rows within a source — is a source-level property or a constraint. Architecturally it is a constraint, but it is so common that a convenience parameter on `Source` may be warranted.

---

### `constraints`

The constraint system. All constraints expose a common interface to the solver.

**Common interface:**
```python
constraint.variables()    # set of solver variables this constraint touches
constraint.expression()   # the equation or inequality
constraint.exact()        # bool — equality or bound
constraint.kind()         # "count" or "value"
```

**Count constraints** (phase one solver):
- `Overlap(source_a, source_b, ratio)` — proportion of pool entities appearing in both sources
- `Coverage(source, min, max)` — proportion of pool entities appearing in this source
- `Duplicates(source, rate)` — proportion of rows in this source that are duplicate representations of the same entity

**Value constraints** (phase two, static feasibility check):
- Generator cardinality vs `n_pool` — can this generator produce enough unique values?
- Uniqueness preservation under perturbation — does applying this rule to a unique set produce a unique set?
- Value space collision — does the perturbed value space collide with the base value space?

**Solver behaviour:**
- Count constraints are solved exactly. Conflicts raise an error with the specific constraints that interact identified.
- Value constraints are checked statically before generation. Failures raise an error with the generator, feature, and rule identified.
- Implicit boundary values surface as warnings. Explicit boundary values are honoured silently.
- Implicit reasonableness checks — overlap and coverage — warn if violated implicitly.

**Open implementation questions:** whether the solver uses a formal library (Z3, OR-Tools) or plain arithmetic. Given the variable space is small — effectively `n_pool`, per-source counts, and overlap counts — a library is almost certainly overkill. Plain algebra with explicit conflict reporting is likely sufficient and more transparent.

---

### `generation`

The generation engine. Takes a resolved constraint solution and materialises data.

**Responsibility:** given a pool, a set of sources, and a solved constraint assignment, generate the actual data. Outputs:
- Per-source data tables
- The entity-to-key mapping for each source
- The perturbation log

**Key design decisions:** generation is a pure function of the constraint solution and a random seed. The same seed always produces the same data. The Faker-per-record approach is used for MVP. The interface is designed so that a vectorised backend can be substituted without changing the output contract.

**Open implementation questions:** generation order within a source when multiple perturbation rules are declared — are they applied independently (one rule per row, randomly assigned) or can multiple rules apply to the same row? The matchbox approach applies one rule per row. Whether stacking is desirable is deferred to post-MVP.

---

### `bundle`

The top-level output container returned by `generate()`.

**Core type:**
- `Bundle` — contains `.data` and `.correctness`.

**`.data`** — the generated datasets, nodes, and edges:
- `data.datasets` — `dict[source_name, pl.DataFrame]` — one table per source
- `data.nodes` — `pl.DataFrame` of `(entity_id, entity_type)` — the abstract entity pool as nodes
- `data.edges` — `pl.DataFrame` of `(entity_id, source, key)` — the mapping from abstract entities to source records as edges

**`.correctness`** — the correctness oracle:
- `correctness.clusters(*sources)` — true clusters for a subset of sources, optionally filtered by entity type or record keys
- `correctness.diff(predicted, sources)` — returns a `Diff` object
- `correctness.provenance(key, source)` — perturbation history for a specific record
- `correctness.records_with(rule_type, source)` — all records where a given rule type was applied
- `correctness.splits_caused_by(rule_type)` — cross-reference of diff splits against perturbation type

**`Diff` object:**
- `diff.perfect` — clusters predicted exactly correctly
- `diff.splits` — true clusters that were fragmented
- `diff.merges` — true clusters that were collapsed
- `diff.missed` — true clusters not touched at all

The `Diff` object returns raw sets. Statistical measures — precision, recall, F1 — are out of scope. Users compute whatever metric they need from the raw sets.

**Accepted input format for `diff`:** resolved clusters as `(cluster_id, entity_type, source, key)`. The package does not accept scored edge lists or perform clustering internally.

**Open implementation questions:** whether `Diff` should expose its sets as Polars DataFrames or Python sets. DataFrames are more convenient for large-scale inspection; sets are more natural for set arithmetic. Likely DataFrames with set-like comparison methods.

---

### `solver`

The constraint validation and resolution layer. Sits between the user's declarations and the generation engine.

**Responsibility:**
1. Collect all constraints from pool, sources, and explicit declarations
2. Run phase one: check count constraint system for satisfiability
3. Run phase two: check value constraints statically
4. Resolve the constraint system to concrete integer assignments
5. Report conflicts and implicit boundary values before any generation is attempted

**Open implementation questions:** whether conflict reporting is depth-first (report the first conflict found) or exhaustive (report all conflicts). Exhaustive is more useful but requires more implementation. Likely depth-first for MVP.

---

## MVP scope

### In scope

**Data structures:**
- `EntityPool` with a single entity type
- `Feature`, `Key`, `FeatureConfig`
- `VariationRule`, `SuffixRule`, `PrefixRule`, `ReplaceRule`
- `Source` with feature-level perturbation declarations
- `SourceEntity`, `ClusterEntity`, `EntityReference`

**Constraints:**
- `Overlap`, `Coverage`, `Duplicates`
- Phase one count solver with conflict reporting
- Phase two static value feasibility check for generator cardinality and uniqueness preservation
- Implicit reasonableness warnings for overlap and coverage
- Explicit vs implicit boundary value distinction

**Generation:**
- Faker-per-record generation
- Deterministic perturbations only
- Reproducible via seed

**Bundle:**
- `Bundle.data` — datasets, nodes, edges
- `Bundle.correctness` — `clusters()`, `diff()`, `provenance()`, `records_with()`, `splits_caused_by()`
- `Diff` — perfect, splits, merges, missed

### Out of scope for MVP

- Multiple entity types
- Stochastic perturbation rules
- Vectorised/large-scale generation backend
- Perturbation rule stacking (multiple rules applied to the same row)
- Statistical measures on `Diff`
- Connected components or any clustering logic
- Any storage, database, or pipeline integration