# V2 Documentation System Review - 2026-06-16

## Executive Summary

结论：**不建议直接进入 Task 37 实现**。V2 文档已经形成较完整的 planning baseline，Task 37-59 连续存在，verification matrix 覆盖全部任务，非共价预训练也被正确放在 experimental/non-blocking 轨道；但如果按 v1 的严格流程要求审查，当前还存在两个 Task 37 前必须解决的问题：

- **P0-1：Task 37 的 smoke profile 命名不一致。** `docs/v2/04-v2-dependency-and-environment-spec.md` 使用 `--profile cpu` / `--profile heavy`，而 `docs/v2/10-v2-implementation-plan.md` 和 `docs/v2/11-v2-verification-matrix.md` 使用 `--profile lightweight`。这是 Task 37 要创建的第一个 CLI 接口，必须先冻结。
- **P0-2：V2 硬决策没有 ADR 计划或 ADR 0037+ 承接。** `docs/v2/01-v2-intent.md` 明确说 planning decisions 不写成 irreversible ADR，但 Task 37 将把环境边界、heavy dependency policy、default CI policy 和 source-verification policy 落成可执行接口。当前 `docs/adr/` 只有 0001-0036，没有 V2 ADR，也没有在 Task 37/38 中明确“何时需要 ADR、哪些决策由既有 ADR 覆盖”。

因此本次审查给出的严格 verdict：

- **Task 37 Ready:** No，先修 P0-1 和 P0-2。
- **V2 docs v1-equivalent:** Partial。结构接近 v1，但 ADR governance、CLI 命名一致性、verification rigor 和 contract detail 还未完全达到 v1 后期标准。
- **V2 implementation planning usable:** Yes after small docs/ADR-plan patch，不需要重写整个 V2 文档体系。

本次只读审查未运行会改动代码的命令，未实现 V2，未改 `src/`、`tests/`、`.github/`、PMDM、PocketFlow、真实数据、模型权重或 docking 输出。唯一允许的写入是本审查文档。

## V1 Process Baseline

V1 的成熟流程基线不是单一文档，而是一组相互校验的文件：

- `docs/specs/implementation-plan.md`：每个 task 有 Goal、Files/modules、Dependencies、Contracts/Acceptance、Verification，并通过 Checkpoint 串联阶段 gate。
- `docs/specs/interface-design.md`：定义 public API、module boundary、CLI boundary、artifact roles、failure reasons、misuse guards。
- `docs/specs/verification-matrix.md`：按 Area/Task 记录 evidence required、primary command 和 blocking target。
- `docs/specs/key-design-decisions.md`：作为 decision index，指向 ADR 和 spec，不替代 ADR。
- `docs/adr/`：对 hard-to-reverse decisions 建立 durable decision record。近期 ADR 0030-0036 已有 Status、Date、Context、Decision、Consequences；ADR 0033/0034 还包含 Alternatives Considered。
- `docs/reviews/`：在关键节点记录 readiness verdict、P0/P1/P2/P3 findings 和 gate decision。

V1 的质量标准可以概括为：

1. Task 能被独立执行，且不会要求实现者临时猜 CLI 名称、artifact schema 或 dependency boundary。
2. Verification command 不只是“有 diff”，而是能证明行为、schema、failure path 或 governance rule。
3. Hard decision 不只散落在 specs 中，而是能回链到 ADR 或明确说明由既有 ADR 覆盖。
4. 默认 CI/lightweight path 与 heavy/manual path 分离，并且分离规则可测试、可审计。

V2 当前文档已经接近该结构，但还没有完全达到这个基线。

## V2 Task Slice Audit

审查对象：`docs/v2/10-v2-implementation-plan.md`。

Task 37-59 连续存在，阶段划分如下：

| Phase | Tasks | Scope | Audit verdict |
| --- | ---: | --- | --- |
| V2-A | 37-39 | environment, dependency source verification, smoke probes | 结构合理；Task 37 profile 命名冲突是 P0 |
| V2-B | 40-43 | real data intake, staging, conversion, license gate | 切片合理；license audit 对 Task 41/43 的依赖关系可再收紧 |
| V2-C | 44-45 | RDKit normalization, scaffold/descriptor diagnostics | 合理；需要明确 default skip marker 和 heavy evidence |
| V2-D | 46-51 | tensor backend, PMDM/baseline, dataset, training loop, manifests | 切片合理；contract detail 还偏粗 |
| V2-E | 52 | tiny tuning | 可实现；缺 Notes |
| V2-F | 53-56 | sampling, deterministic smoke, evaluation, docking feasibility | 合理；sampling/evaluation CLI naming 与 spec 有 drift |
| V2-G | 57-58 | optional noncovalent pretraining | 放置正确；Task 57 verification 太弱 |
| V2-H | 59 | beta release gate | 合理；需要把 ADR/governance evidence 纳入 gate |

字段覆盖审计结果：

- Task 37-59 都有 `Goal`、`Files/modules`、`Dependencies`、`Acceptance`、`Verification`。
- Task 51-57 缺 `Notes`，与“每个 task 都应有 Notes”的严格要求不一致。
- Task 37、38、39 的切片粒度适合启动环境阶段，但 Task 37 的 CLI profile contract 尚未冻结。
- Task 40-59 基本可作为后续实现计划，但有几处 verification 和 CLI naming 需要在对应 task 前修正。

关键证据：

- `docs/v2/10-v2-implementation-plan.md:15` Task 37。
- `docs/v2/10-v2-implementation-plan.md:44` Task 38。
- `docs/v2/10-v2-implementation-plan.md:71` Task 39。
- `docs/v2/10-v2-implementation-plan.md:447` Task 51，缺 `Notes`。
- `docs/v2/10-v2-implementation-plan.md:479` Task 52，缺 `Notes`。
- `docs/v2/10-v2-implementation-plan.md:513` Task 53，缺 `Notes`。
- `docs/v2/10-v2-implementation-plan.md:539` Task 54，缺 `Notes`。
- `docs/v2/10-v2-implementation-plan.md:565` Task 55，缺 `Notes`。
- `docs/v2/10-v2-implementation-plan.md:591` Task 56，缺 `Notes`。
- `docs/v2/10-v2-implementation-plan.md:623` Task 57，缺 `Notes`。

## ADR Slice Audit

当前 ADR 状态：

- `docs/adr/` 中 ADR 编号连续为 `0001` 到 `0036`。
- 没有 `0037-*` 或任何明显的 V2 ADR。
- 近期 ADR 0030-0036 已形成较稳定模板：Status、Date、Context、Decision、Consequences；部分包含 Alternatives。
- `docs/v2/01-v2-intent.md:47` 写明：planning decisions 记录为 planning docs，不作为 irreversible ADR。

严格审查结论：

当前 **不是“每个 Task 需要一个 ADR”** 的问题。V1 也没有为每个 task 建 ADR；它为 hard-to-reverse architecture decisions 建 ADR。V2 当前缺的是 **ADR 创建标准和对应切片**：

| Decision area | Current location | ADR status | Severity |
| --- | --- | --- | --- |
| V2 environment/dependency boundary: Linux/WSL2 Conda/Mamba, Windows lightweight only, heavy deps excluded from default CI | `docs/v2/01-v2-intent.md`, `docs/v2/04-v2-dependency-and-environment-spec.md`, `docs/v2/11-v2-verification-matrix.md` | No V2 ADR / no explicit coverage by ADR 0034 | P0 before Task 37 |
| Source verification and dependency lock policy | `docs/v2/04-v2-dependency-and-environment-spec.md`, Task 38 | No ADR plan; verification currently `git diff` | P1 before Task 38 |
| Data license audit as hard pre-training gate | `docs/v2/03-v2-requirements.md`, `docs/v2/05-v2-data-automation-spec.md`, Task 43 | Could be spec-only, but should be explicitly linked to ADR coverage or new ADR | P1 before Task 40/43 |
| PMDM preferred path vs `non_pmdm_baseline` fallback | `docs/v2/01-v2-intent.md`, Task 47/48 | No ADR or explicit extension of ADR 0006/0034 | P1 before Task 47 |
| V2 additive contract compatibility and no heavy objects in serialized contracts | `docs/v2/09-v2-interface-and-contract-changes.md` | No ADR or clear link to ADR 0030/0035 | P1 before Task 46 |
| Noncovalent pretraining experimental/non-blocking decision | `docs/v2/08-v2-noncovalent-pretraining-feasibility.md`, Task 57/58 | Decision note exists; ADR optional if user wants durable research-scope decision | P2 before Task 57 |

Recommended ADR policy:

- Do **not** create one ADR per V2 task.
- Create or plan **one immediate ADR** before Task 37: `0037-v2-environment-and-heavy-dependency-boundary.md`.
- Add a short V2 ADR decision table in `docs/v2/10-v2-implementation-plan.md` or `docs/v2/00-v2-project-map.md` that states which decisions are covered by existing ADRs and which will require future ADRs.
- Future ADR candidates should be triggered only when a task freezes a hard-to-reverse public boundary, not when it merely adds fixtures or tests.

## Verification Matrix Audit

审查对象：`docs/v2/11-v2-verification-matrix.md`。

Coverage result:

- Matrix 覆盖 Task 37-59，无 missing task，无 extra task。
- Checkpoints 覆盖 V2-A、V2-B、V2-C、V2-D、V2-E、V2-F、V2-H。
- V2-G 没有 checkpoint row；考虑到 noncovalent pretraining 是 optional/non-blocking，这不是 blocker，但最好明确“V2-G intentionally has no release gate unless promoted”。

Evidence quality:

- Task 37 有可执行形态：`python scripts/v2_smoke_check.py --profile lightweight` 和 `compileall`。
- Task 38 的 evidence 是 `git diff -- docs/v2/04... docs/v2/dependency-source-verification.md`，这只能证明文件变了，不能证明 source verification 质量。
- Task 57 的 evidence 也是 `git diff -- docs/v2/08...`，只能证明文档变了，不能证明 feasibility review 已经按 criteria 完成。
- Default Lightweight Verification 使用 `python -m pytest -q` 和 `python -m unittest discover`，但 heavy tests 的 marker/skip policy 还没有在 matrix 中形成可执行 contract。

建议增强：

- Matrix 增加或补充一个“mode”概念：lightweight、heavy-manual、network-manual、gpu-manual。
- Task 38 verification 应要求 source verification table 中每项有 official URL、version/constraint、license status、date、verifier、unverified/blocking marker。
- Task 43 verification 应有 explicit fixture：`allowed`、`allowed_with_conditions`、`unknown`、`blocked`，并验证 unknown/blocked 不进入 training eligibility。
- Task 57 verification 应要求 review doc 或 structured checklist，而不是单纯 `git diff`。

## Cross-Document Consistency

主要一致性问题如下：

1. **Smoke profile 命名冲突。**
   - `docs/v2/04-v2-dependency-and-environment-spec.md:85-86` 使用 `--profile cpu` 和 `--profile heavy`。
   - `docs/v2/10-v2-implementation-plan.md:38` 使用 `--profile lightweight`。
   - `docs/v2/11-v2-verification-matrix.md:8` 使用 `--profile lightweight`。
   - Impact: Task 37 会直接创建 `scripts/v2_smoke_check.py`，实现者必须猜 `cpu` 和 `lightweight` 是否同义。

2. **Script CLI 与 package CLI 命名混用。**
   - `docs/v2/05-v2-data-automation-spec.md:122-125` 使用 `scripts/v2_validate_source_manifest.py`、`scripts/v2_download_sources.py`、`scripts/v2_stage_manual_source.py`、`scripts/v2_run_real_etl.py`。
   - `docs/v2/10-v2-implementation-plan.md:166` 使用 `python -m covalent_design.data.cli.v2_stage_source`。
   - `docs/v2/06-v2-training-and-tuning-spec.md:96-98` 使用 `scripts/v2_train_smoke.py` / `scripts/v2_tune.py`。
   - `docs/v2/11-v2-verification-matrix.md:21` 和 `:23` 使用 `python -m covalent_design.training.cli.v2_train` / `v2_tune`。
   - Impact: 不影响 Task 37，但会在 Task 41、50、52 造成 CLI ownership 和 test target drift。

3. **V2 interface doc 比 v1 interface-design 粒度更浅。**
   - `docs/v2/09-v2-interface-and-contract-changes.md:22-98` 列出 V2EnvironmentManifest、SourceLicenseAudit、V2DataIntakeManifest、FamilyReadinessReport、V2TrainingRunManifest、V2SamplingEvaluationReport。
   - 当前多为字段名列表，缺少 required/optional、allowed enum、error code、lifecycle、count equation、serialization envelope、schema versioning。
   - Impact: Task 40+ 能开始设计，但 Task 46+ 的 contract implementation 仍可能反向迫使 schema 大改。

4. **V2 specs 与 v1 specs 的整合边界还未冻结。**
   - `docs/specs/README.md` 仍把 `docs/specs/` 描述为 project-owned development entrypoint。
   - V2 计划全部在 `docs/v2/`，这是合理的 staging 方式，但需要一个明确的“何时并入 docs/specs/ 或保持 v2 overlay”的规则。

## Noncovalent Pretraining Decision Audit

当前定位是合理的：

- `docs/v2/01-v2-intent.md:46`：Noncovalent pretraining 是 experimental research track，不是 v2-beta mainline。
- `docs/v2/02-v2-idea-refinement.md:34`：非共价预训练 mainline 被 rejected from beta critical path。
- `docs/v2/03-v2-requirements.md:63-65`：需要独立 license audit、label compatibility、transfer hypothesis、ablation plan、rejection criteria。
- `docs/v2/08-v2-noncovalent-pretraining-feasibility.md:6-8`：明确不阻塞 v2-beta completion。
- Task 57/58 在 V2-G optional phase，Task 59 声明 Task 57/58 非 blocking，除非显式提升。

剩余风险：

- Task 57 的 verification 是 `git diff`，不够证明 feasibility review 质量。
- 如果用户希望“非共价预训练是否进入 future research track”成为可追溯决策，建议后续用 ADR 或 review decision note 固化；但它不应阻塞 Task 37。

## V1 Equivalence Assessment

| Dimension | V1 baseline | V2 current | Verdict |
| --- | --- | --- | --- |
| Task numbering and dependency order | Task 1-36 with checkpoints | Task 37-59 with checkpoints | Pass |
| Task slice fields | Goal, files, deps, acceptance, verification, notes/scope | All core fields present; Task 51-57 missing Notes | Partial |
| Interface design | Explicit APIs, CLIs, artifacts, errors, misuse guards | Proposed contracts exist but are field-list level | Partial |
| Verification matrix | Evidence and commands tied to gates | Full task coverage; some weak `git diff` verifications | Partial |
| ADR governance | Hard decisions captured in ADRs, especially 0030+ | No V2 ADRs or ADR plan | Fail |
| Heavy/default CI boundary | ADR 0034 + CI checks | V2 states policy but lacks V2-specific ADR/marker contract | Partial |
| Reviews | Readiness docs with severity findings | Prior reviews exist; current strict report adds blockers | Pass |
| Scientific optionality | Non-blocking research questions separated | Pretraining correctly optional | Pass |

Overall: **V2 documentation is close, but not yet v1-equivalent under strict audit.**

## Findings By Severity

### P0

- **[P0] Task 37 smoke profile contract is not frozen**
  - **Evidence:** `docs/v2/04-v2-dependency-and-environment-spec.md:85-86` uses `--profile cpu` / `--profile heavy`; `docs/v2/10-v2-implementation-plan.md:38` and `docs/v2/11-v2-verification-matrix.md:8` use `--profile lightweight`.
  - **Impact:** Task 37 would create the first V2 CLI with ambiguous public interface. Tests, docs, and future CI could diverge immediately.
  - **Recommended fix:** Pick one vocabulary before Task 37. Recommended: `lightweight` and `heavy`, with `lightweight` explicitly meaning no RDKit/PyTorch/CUDA/PMDM hard import. If `cpu` is retained, define whether it allows PyTorch CPU imports.
  - **Suggested skill:** `api-and-interface-design`, `documentation-and-adrs`.

- **[P0] V2 hard decisions lack ADR plan before implementation begins**
  - **Evidence:** `docs/v2/01-v2-intent.md:47` says planning decisions are not irreversible ADRs; `docs/adr/` currently ends at `0036-message-weight-leakage-prevention.md`; Task 37 will freeze environment policy and smoke interface without listing any ADR file.
  - **Impact:** V2 environment/heavy dependency/default CI/source-verification decisions are hard to reverse after Task 37-39 create scripts, CI assumptions, and dependency docs. Without ADR coverage, later agents may treat planning text, ADR 0034, and V2 specs as competing authorities.
  - **Recommended fix:** Before Task 37, add a V2 ADR plan and preferably create or schedule `0037-v2-environment-and-heavy-dependency-boundary.md`. At minimum, Task 37 must state whether it extends ADR 0034 or creates a new ADR.
  - **Suggested skill:** `documentation-and-adrs`, `improve-codebase-architecture`.

### P1

- **[P1] Verification matrix has full coverage but weak evidence for source-verification tasks**
  - **Evidence:** `docs/v2/11-v2-verification-matrix.md:9` uses `git diff` as Task 38 command; `docs/v2/11-v2-verification-matrix.md:28` uses `git diff` as Task 57 command.
  - **Impact:** A task could pass by changing text without proving official-source verification, license review, or feasibility criteria.
  - **Recommended fix:** Replace or supplement `git diff` with structured checklist validation. For Task 38 require official source URL, license status, version/constraint, verification date, verifier, and unresolved marker. For Task 57 require review doc with accepted/rejected/deferred decision and criteria table.
  - **Suggested skill:** `source-driven-development`, `test-driven-development`, `documentation-and-adrs`.

- **[P1] CLI ownership drifts between `scripts/` and package module entry points**
  - **Evidence:** `docs/v2/05-v2-data-automation-spec.md:122-125` defines script commands; `docs/v2/10-v2-implementation-plan.md:166` defines package module command for staging. `docs/v2/06-v2-training-and-tuning-spec.md:96-98` defines script commands; `docs/v2/11-v2-verification-matrix.md:21,23` defines package module training/tuning CLIs.
  - **Impact:** Implementers may create duplicate wrappers or tests against different entry points.
  - **Recommended fix:** Freeze one convention: either scripts are thin wrappers around `covalent_design.*.cli` modules, or verification uses package CLIs only and scripts are limited to environment probes.
  - **Suggested skill:** `api-and-interface-design`, `code-review-and-quality`.

- **[P1] V2 interface contracts are not yet detailed enough for implementation-heavy tasks**
  - **Evidence:** `docs/v2/09-v2-interface-and-contract-changes.md:22-98` lists proposed contract fields but does not define required/optional status, enum values, validation errors, envelope roles, lifecycle states, or count equations.
  - **Impact:** Task 40+ can start as design work, but Task 46+ may produce incompatible dataclasses or JSON schemas.
  - **Recommended fix:** Before each implementation-heavy phase, expand the relevant contract from field list to schema contract. Start with V2EnvironmentManifest and SourceLicenseAudit for Tasks 37-43.
  - **Suggested skill:** `api-and-interface-design`, `documentation-and-adrs`.

- **[P1] Heavy-test skip policy is described but not test-contract precise**
  - **Evidence:** `docs/v2/11-v2-verification-matrix.md:49-55` says default lightweight verification runs broad pytest/unittest and heavy commands are opt-in/manual.
  - **Impact:** Once RDKit/PyTorch/PMDM tests are added, default CI may either fail on missing heavy deps or silently skip too much without visible evidence.
  - **Recommended fix:** Define marker names and skip behavior before Task 39/44/46, for example `@pytest.mark.heavy`, `@pytest.mark.gpu`, `@pytest.mark.network`, and require skip tests that prove missing dependencies produce structured status rather than import errors.
  - **Suggested skill:** `test-driven-development`, `ci-cd-and-automation`.

- **[P1] V2 docs do not yet define when V2 overlay merges into canonical specs**
  - **Evidence:** `docs/specs/README.md` describes `docs/specs/` as implementation entrypoint, while Task 37+ lives under `docs/v2/`.
  - **Impact:** Agents may update `docs/v2/` only, while others expect `docs/specs/implementation-plan.md` and `verification-matrix.md` to remain canonical.
  - **Recommended fix:** Add a short governance rule: V2 remains overlay until Task 37 is accepted, or each V2 task must update both V2 and canonical specs once implemented.
  - **Suggested skill:** `context-engineering`, `documentation-and-adrs`.

### P2

- **[P2] Task 51-57 are missing Notes**
  - **Evidence:** Task field parser found missing `Notes` for Tasks 51, 52, 53, 54, 55, 56, 57 in `docs/v2/10-v2-implementation-plan.md`.
  - **Impact:** Not a Task 37 blocker, but it weakens parity with v1 task slices and removes useful scope boundaries for later agents.
  - **Recommended fix:** Add one-line Notes for each task, especially stating what not to do.
  - **Suggested skill:** `planning-and-task-breakdown`.

- **[P2] V2-G optional phase has no explicit checkpoint row**
  - **Evidence:** `docs/v2/11-v2-verification-matrix.md:36-42` lists V2-A through V2-F and V2-H, but not V2-G.
  - **Impact:** It is probably intentional because pretraining is optional, but future readers may think a checkpoint was accidentally omitted.
  - **Recommended fix:** Add an explicit note: “V2-G has no beta release checkpoint unless pretraining is promoted.”
  - **Suggested skill:** `documentation-and-adrs`.

- **[P2] Data license gate dependencies could be more explicit**
  - **Evidence:** Task 43 depends on Task 40, while Task 41 stages/downloads fixtures and Task 42 converts to v1-compatible ETL inputs.
  - **Impact:** License audit can be designed from schema alone, but implementation must validate real staged source metadata and should not drift from intake behavior.
  - **Recommended fix:** Clarify whether Task 43 is schema-only or consumes Task 41 fixture manifests. If it consumes staged manifests, add Task 41 as dependency.
  - **Suggested skill:** `planning-and-task-breakdown`, `code-review-and-quality`.

- **[P2] Risk register lacks explicit doc/ADR drift risk**
  - **Evidence:** `docs/v2/12-v2-risk-register.md` covers dependency, license, PMDM, data, training, sampling, pretraining, docking, and governance noise, but not V2 ADR/document authority drift.
  - **Impact:** The biggest current risk found by this review is governance/document drift, but the risk register does not track it.
  - **Recommended fix:** Add a risk row for V2 ADR/spec authority drift after P0 ADR plan is resolved.
  - **Suggested skill:** `documentation-and-adrs`.

### P3

- **[P3] Prior V2 reviews are less strict than this audit**
  - **Evidence:** `docs/reviews/v2-documentation-review-2026-06-16.md` and `docs/reviews/v2-documentation-hardening-review-2026-06-16.md` both report no blockers / PASS.
  - **Impact:** Not an implementation blocker, but future readers may see conflicting readiness conclusions.
  - **Recommended fix:** Add a short closure note after P0 fixes explaining whether this stricter review supersedes the earlier PASS.
  - **Suggested skill:** `documentation-and-adrs`.

- **[P3] Working tree has unrelated modified/untracked files**
  - **Evidence:** `git status --short` before this report showed modifications in `.github/workflows/ci.yml`, `.gitignore`, `README.md`, `docs/github-management.md`, `docs/specs/implementation-plan.md`, `docs/specs/verification-matrix.md`, and untracked `docs/reviews/`, `docs/v2/`, `tests/ci/`, `tests/fixtures/FIXTURE_POLICY.md`.
  - **Impact:** Not a V2 docs content blocker, but it makes review baseline noisy.
  - **Recommended fix:** Resolve or intentionally stage these separately before publishing V2 docs.
  - **Suggested skill:** `git-workflow-and-versioning`, `code-review-and-quality`.

## Required Fix Plan

Before Task 37:

1. Freeze smoke profile vocabulary across `docs/v2/04-v2-dependency-and-environment-spec.md`, `docs/v2/10-v2-implementation-plan.md`, and `docs/v2/11-v2-verification-matrix.md`.
2. Add a V2 ADR plan. Recommended minimum: create or explicitly schedule `0037-v2-environment-and-heavy-dependency-boundary.md`, and update Task 37/38 to mention ADR coverage.
3. Decide whether V2 planning docs stay as overlay or whether Task 37 starts canonical integration into `docs/specs/`.

Before Task 38:

1. Replace `git diff`-only verification with source-verification evidence requirements.
2. Define exact fields for dependency source verification: package, official source URL, version/constraint, license, CUDA compatibility, verification date, verifier, unresolved marker.

Before Task 40-43:

1. Expand `SourceLicenseAudit` and `V2DataIntakeManifest` into schema-level contracts.
2. Freeze allowed license statuses and training eligibility behavior.
3. Align data CLI naming between scripts and package modules.

Before Task 44-46:

1. Define heavy test markers and default skip policy.
2. Freeze how RDKit/PyTorch unavailable status is serialized in manifests and reports.

Before Task 47-52:

1. Decide whether PMDM vs `non_pmdm_baseline` fallback needs its own ADR or an extension to ADR 0006/0034.
2. Expand V2 training manifest schema with required hashes, baseline mode, dependency lock hash, data hash, family readiness hash, and checkpoint refs.

Before Task 53-59:

1. Align sampling/evaluation CLI names.
2. Add Notes for Tasks 53-57.
3. Strengthen Task 57 feasibility verification beyond `git diff`.

## User Questions

### P0 Must Answer Before Task 37

1. **Smoke profile 名称到底是什么？** 你要 `lightweight/heavy`，还是 `cpu/heavy`？如果保留 `cpu`，它是否允许 PyTorch CPU import，还是必须像 `lightweight` 一样完全不硬依赖 PyTorch/RDKit/PMDM？
2. **V2 环境和 heavy dependency boundary 要不要在 Task 37 前写 ADR 0037？** 如果不写，你是否明确接受 `docs/v2/*` planning docs 在 Task 37-39 期间临时作为 authoritative decision source？

### P1 Must Answer Before Specific Later Task

3. **V2 CLI 入口统一走哪里？** `scripts/v2_*.py` 是正式入口，还是只做 thin wrapper，正式 verification 用 `python -m covalent_design.<area>.cli...`？
4. **Task 38 的 source verification 需要谁签字？** 仅记录官方 URL 和日期够不够，还是要 reviewer/user acceptance 字段？
5. **PMDM 不可用时的 fallback 是科学 baseline 还是 engineering smoke path？** 如果是后者，evaluation/report 必须显著标记不能与 PMDM 结果混报。
6. **V2 overlay 什么时候并入 canonical specs？** Task 37 开始并入，还是 V2-beta release gate 后再并入？

### P2 Can Defer

7. **Noncovalent pretraining 是否需要 ADR？** 当前 feasibility doc 已够用；只有当你希望把“非 blocking research track”变成长期项目策略时才需要 ADR。
8. **Docking feasibility 是否要指定候选 engine？** 当前不阻塞 v2-beta，但 Task 56 前要决定 engine/license/manifest 是否进入 feasibility scope。

## Final Verdict

**Can enter Task 37 now: No.**

最小阻塞项：

1. 统一 `scripts/v2_smoke_check.py` 的 profile vocabulary。
2. 为 V2 environment/heavy dependency/default CI/source-verification boundary 增加 ADR 计划，最好直接创建 ADR 0037 或把 Task 37 scope 改为包含该 ADR。

修完这两个 P0 后，Task 37 可以启动。其余 P1/P2 不需要阻塞 Task 37，但必须在对应阶段前解决，否则 V2 会在 Task 40+ 和 Task 46+ 进入“文档看起来完整、实现时仍需猜接口”的状态。
