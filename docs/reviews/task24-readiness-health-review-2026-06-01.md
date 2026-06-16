# Task 24 前项目健康审查

审查日期：2026-06-01

审查模式：只读审查。除新增本审查记录外，没有修改源代码、测试、spec、ADR、配置或 CI 文件。

## Executive Summary

结论：

- **Task 1-23 Health：Needs Patch**
- **Task 24 Ready：No**
- **建议下一步：先修复 Task 12/18/20/22/23 的集成 contract，再实现 Task 24**
- **当前不应直接编写 `losses.py` 或 smoke training loop**

基线证据是健康的：`python -m compileall -q scripts src` 通过，完整 `unittest` 共 **906 tests passed**。Task 17-23 的定向 `unittest` 也全部通过。仓库没有发现包级循环依赖。

但是，测试通过掩盖了数个跨任务语义断层。最严重的问题是：Task 18 声称读取 Task 12 静态 `edge_candidates` artifact，但真实 Task 12 输出与 Task 18 输入 schema 不兼容。用真实 Task 12 fixture 调用 `build_stepwise_candidates()` 会直接得到：

```text
KeyError: 'ligand_atom_index'
```

此外，Task 12 和 Task 18 都按 `atom_name` 选取第一个蛋白原子。蛋白中多个残基可共享 `SG`、`OG`、`NZ` 等名称，这会把监督边绑定到错误残基。只读探针已复现：目标是链 B、残基 2 的 `SG`，实现却选择链 A、残基 1 的首个 `SG`，得到距离 `11.0` 而不是 `1.0`，并错误标记为 forced positive。

Task 20、22、23 也仍是独立通过测试的局部模块，没有形成 Task 24 所需的可执行训练路径：

```text
split-filtered dataset
  -> ModelBatch
  -> per-timestep StepwiseCandidateSet
  -> PMDM fake backbone
  -> covalent heads
  -> detached message weights actually applied
  -> MaskAudit / EdgeDenominators
  -> LossReport JSON
```

在修复前直接进入 Task 24，会迫使 smoke loop 自行发明缺失接口，形成重复逻辑或错误冻结。

## Review Scope And Method

使用的 skill：

- `zoom-out`
- `improve-codebase-architecture`
- `code-review-and-quality`
- `code-reviewer`
- `doubt-driven-development`
- `documentation-and-adrs`
- `api-and-interface-design`
- `test-driven-development`

`source-driven-development` 仅用于判断是否需要外部 API 核验。本轮没有新增外部 API 决策，因此没有联网查询。

`debugging-and-error-recovery` 未启用：项目基线验证没有失败。可选 `pytest` 命令失败的原因是当前解释器未安装 `pytest`，不是项目测试失败。

按用户要求，本轮没有创建 Claude 子窗口，也没有运行 `codex-claude-docs.ps1`。`doubt-driven-development` 采用 Codex 内部对抗性复核，重点寻找“局部测试通过但跨任务不可执行”的情况。

重点读取：

- `CONTEXT.md`
- `README.md`
- `docs/specs/README.md`
- `docs/specs/implementation-plan.md`
- `docs/specs/interface-design.md`
- `docs/specs/verification-matrix.md`
- `docs/specs/key-design-decisions.md`
- `docs/specs/01-data-processing.md`
- `docs/specs/02-model.md`
- `docs/specs/03-training.md`
- `docs/adr/0030-etl-data-contracts-and-completion-gates.md`
- `docs/adr/0035-task17-model-batch-contract.md`
- `docs/adr/0036-message-weight-leakage-prevention.md`
- `docs/reviews/`
- `src/covalent_design/`
- `tests/`
- `.github/workflows/ci.yml`

## Verification Evidence

已运行并通过：

| 命令 | 结果 |
| --- | --- |
| `$env:PYTHONPATH='src'; python -m compileall -q scripts src` | PASS |
| `$env:PYTHONPATH='src'; python -m unittest discover -s tests -t . -q` | PASS，`Ran 906 tests in 28.618s` |
| `$env:PYTHONPATH='src'; python -m unittest tests.training.test_masks_denominators -v` | PASS，86 tests |
| `$env:PYTHONPATH='src'; python -m unittest tests.training.test_dataset -v` | PASS，85 tests |
| `$env:PYTHONPATH='src'; python -m unittest tests.model.test_final_decode -v` | PASS，54 tests |
| `$env:PYTHONPATH='src'; python -m unittest tests.model.test_covalent_heads -v` | PASS，42 tests |
| `$env:PYTHONPATH='src'; python -m unittest tests.model.test_pmdm_adapter -v` | PASS，48 tests |
| `$env:PYTHONPATH='src'; python -m unittest tests.model.test_stepwise_candidates -v` | PASS，37 tests |
| `$env:PYTHONPATH='src'; python -m unittest tests.model.test_batch -v` | PASS，34 tests |

可选 `pytest` 验证：

| 命令 | 结果 |
| --- | --- |
| `python -m pytest tests/training/test_masks_denominators.py -q` | 未运行：`No module named pytest` |
| `python -m pytest tests/training/test_dataset.py -q` | 未运行：`No module named pytest` |
| `python -m pytest tests/model/test_final_decode.py -q` | 未运行：`No module named pytest` |
| `python -m pytest tests/model/test_covalent_heads.py -q` | 未运行：`No module named pytest` |

只读探针：

| 探针 | 结果 |
| --- | --- |
| 将真实 Task 12 fixture 传入 Task 18 `build_stepwise_candidates()` | `KeyError: 'ligand_atom_index'` |
| 两个不同残基都含 `SG`，目标指定第二个 `SG` | 实现选择第一个 `SG`，`selected_distance=11.0`，错误 forced positive |
| 构造含 strata 的 `LossReport` 并调用 `.to_dict()` | strata 仅含 `denominators`、`residue_reaction_family`、`timestep_bucket`，缺失 `mask_audit` |
| 调用 `load_training_batch(object(), 'batch-0')` | `NotImplementedError: load_training_batch is not yet implemented` |
| AST 包依赖 SCC 检查 | `cycles: []` |

## Git State And Repository Hygiene

审查开始及写入前工作树均已有用户改动。没有 staged changes。

Tracked modified files：

```text
 M docs/specs/03-training.md
 M docs/specs/implementation-plan.md
 M docs/specs/interface-design.md
 M docs/specs/key-design-decisions.md
 M docs/specs/verification-matrix.md
```

Untracked directories：

```text
?? docs/reviews/
?? prompts/
?? src/covalent_design/training/
?? tests/fixtures/training/
?? tests/training/
```

验证命令生成了被忽略的 `__pycache__/`。没有删除或修改这些目录。

## Architecture Map

当前 `src/covalent_design/` 模块：

| 模块 | 职责 | 主要依赖 |
| --- | --- | --- |
| `contracts/` | 共享 dataclass、错误、receipt、lifecycle、denominator validator | 无下游业务包依赖 |
| `io/` | JSONL、artifact ref、checksum、path resolution | `contracts` |
| `data/` | manifest、ingest、normalize、identity、quality、records、artifact manifests、splits、quality report、CLI | `contracts`、`io`、`rules` |
| `rules/` | rule schema、rule validation、calibration、CLI | `contracts`、`io` |
| `candidates/` | Task 12 静态 edge candidate artifact | `contracts`、`io` |
| `viz/` | visual check artifact 与 CLI | `contracts`、`io` |
| `model/` | Task 17 batch、Task 18 stepwise candidates、Task 19 PMDM adapter skeleton、Task 20 heads/message guard、Task 21 final decode | `contracts`、`io` |
| `training/` | Task 22 dataset/stub batch loader、Task 23 masks/denominators | `contracts`、`io` |

AST 包依赖图：

```text
candidates -> contracts, io
contracts  -> -
data       -> contracts, io, rules
io         -> contracts
model      -> contracts, io
rules      -> contracts, io
training   -> contracts, io
viz        -> contracts, io
```

结论：

- 包级依赖方向总体合理。
- 没有发现包级循环依赖。
- 风险不在循环依赖，而在 artifact schema、identity resolver、denominator semantics 和训练接线路径缺少共享边界。

Task 1-23 数据流的预期形态：

```text
raw source manifests
  -> source parsers
  -> normalize / identity / conflicts / quality
  -> records.jsonl + artifacts
  -> rule calibration
  -> Task 12 static edge_candidates
  -> Task 13 finalized manifests
  -> Task 14 splits
  -> Task 15 visual checks
  -> Task 16 quality report / Data Release Gate
  -> Task 17 ModelBatch
  -> Task 18 per-timestep StepwiseCandidateSet
  -> Task 19 fake PMDM forward
  -> Task 20 covalent heads + detached message weights
  -> Task 21 final decode interface
  -> Task 22 split-filtered training dataset
  -> Task 23 masks + denominator audit
  -> Task 24 smoke training loop
```

当前实际断层：

```text
Task 12 artifact -X-> Task 18 reader
Task 22 dataset   -X-> ModelBatch
Task 18 builder   -X-> Task 20 forward
Task 20 weights   -X-> message passing consumer
Task 23 audit     -X-> Task 24 compute_losses contract
```

## Task 1-23 Health Matrix

| Task | 状态 | 测试证据 | 审查结论 |
| --- | --- | --- | --- |
| 1 Shared contracts skeleton | Complete | 完整 suite 通过 | 共享类型边界存在；`contracts/types.py` 已较大，可后续拆分 |
| 2 Denominator/lifecycle validators | Needs Patch | contract tests 通过 | validator 只验证部分不变量，可能允许 under-accounting |
| 3 Artifact IO primitives | Complete | IO tests 通过 | checksum/path primitives 可用 |
| 4 Raw manifests | Complete | data tests 通过 | 未发现 Task 24 阻塞 |
| 5 CovBinder ingest | Complete | data tests 通过 | 未发现 Task 24 阻塞 |
| 6 CovPDB/CovalentInDB parsers | Complete | data tests 通过 | 未发现 Task 24 阻塞 |
| 7 Identity/conflicts | Complete | data tests 通过 | 规范化 identity 已存在，但 Task 12/18 没有完整复用 |
| 8 Rule schema/validation | Complete | rules tests 通过 | 未发现 Task 24 阻塞 |
| 9 Normalize/quality gates | Complete | data tests 通过 | 未发现 Task 24 阻塞 |
| 10 Record index/artifacts | Complete | data tests 通过 | Task 24 上游可用 |
| 11 Rule calibration | Complete | rules tests 通过 | 未发现 Task 24 阻塞 |
| 12 Static edge candidates | **Needs Patch** | candidates tests 通过 | target atom 解析按名称取首项；artifact schema 不足以供 Task 18 使用；denominator 语义与 Task 23 漂移 |
| 13 Finalized manifests | Complete with upstream caveat | finalize tests 通过 | 能挂接 edge artifact，但不能发现 Task 12 内容 schema 不满足 Task 18 |
| 14 Leakage-aware splits | Complete with fixture policy caveat | splits tests 通过 | 生产 scaffold 算法仍为 fixture-level 决策，不阻塞 smoke |
| 15 Visual checks | Complete | viz tests 通过 | 未发现 Task 24 阻塞 |
| 16 ETL quality report | Complete with governance caveat | quality report tests 通过 | fixture gate 可验证；真实 release approval 是外部治理证据 |
| 17 ModelBatch | Needs Patch | `tests.model.test_batch` 34 tests 通过 | visual status 被硬编码为 pending；仅聚合后验证 denominators |
| 18 Stepwise candidates | **Blocked for integration** | `tests.model.test_stepwise_candidates` 37 tests 通过 | fixtures 绕过真实 Task 12 schema；target atom 选错风险；denominator 语义与 Task 23 冲突 |
| 19 PMDM adapter skeleton | Complete as skeleton | `tests.model.test_pmdm_adapter` 48 tests 通过 | fake backbone 边界清楚；尚非真实 PMDM 集成 |
| 20 Covalent heads/message guard | Partial | `tests.model.test_covalent_heads` 42 tests 通过 | guard 存在，但 stepwise candidates 与 message passing 没有接入 forward 路径 |
| 21 Final decode/gate interface | Complete as interface | `tests.model.test_final_decode` 54 tests 通过 | 可作为后续结果写入边界；生产 gate 实现仍是后续工作 |
| 22 Training dataset/batch loader | Partial | `tests.training.test_dataset` 85 tests 通过 | dataset policy 较完整；`load_training_batch()` 仍是 stub |
| 23 Masks/denominators | Partial, isolated complete | `tests.training.test_masks_denominators` 86 tests 通过 | 局部语义较清楚；没有与 Task 18、Task 20、Task 24 接线 |

## Task 17-23 Detailed Review

### Task 17 ModelBatch

健康部分：

- `make_model_batch()` 在 tensor 构造前检查 artifact refs、checksum、role 和 contract version。
- `BatchRecordHeader` 包含 target atom identity、index 和 artifact role。
- `ModelBatch.static_edge_candidates_refs` 保留 Task 12 artifact refs。
- `BatchSpec.bond_type_vocabulary` 保持 `"no_edge"` 为 index 0。

问题：

- [P1] `src/covalent_design/model/batch.py:167-168` 将 `visual_check_status` 固定为 `"pending"`，没有读取 finalized record metadata。ADR 0035 要求 provenance header 保留该字段，见 `docs/adr/0035-task17-model-batch-contract.md:37`。
- [P1] `src/covalent_design/model/batch.py:440-446` 构造每条记录的 `EdgeDenominators`，但没有立即调用 `.validate()`；只在聚合后调用 `total.validate()`，见 `src/covalent_design/model/batch.py:513-545`。逐记录错误理论上可能被聚合掩盖。
- [P2] `target_atom_identity` 的 chain/residue 来源是 protein table 顶层元数据，atom serial 首选 index 后回退到 name，见 `src/covalent_design/model/batch.py:392-403`、`:552-571`。需要与 Task 12/18 的共享 resolver 统一。

### Task 18 Stepwise Candidate Builder

问题：

- [P0] `src/covalent_design/model/candidate_builder.py:23-25` 读取 `positive_edge["ligand_atom_index"]`、`positive_edge["target_atom"]`、`positive_edge["bond_type"]`，但 Task 12 真实 artifact 没有这些字段。
- [P0] `src/covalent_design/model/candidate_builder.py:34-39` 仅按 atom name 取首个 target atom，忽略 chain、residue number 和 index。
- [P0] `src/covalent_design/model/candidate_builder.py:115-116` 将所有 natural candidates 计入 bond-type 与 geometry denominator；natural negatives 不应获得真实 bond 或 geometry target。

### Task 19 PMDM Adapter Skeleton

结论：

- skeleton 边界可接受。
- fake backbone 可在无 PMDM、无 GPU 环境下验证。
- 本轮没有发现 Task 24 前必须单独修改 Task 19 的问题。

### Task 20 Covalent Heads And Message Weight Interface

健康部分：

- `ModelForwardOutput.__post_init__` 已实现 detached weights 和 source marker 验证，见 `src/covalent_design/contracts/types.py:496-508`。
- `forward_covalent()` 从 logits 计算 `.sigmoid().detach()`，见 `src/covalent_design/model/covalent_heads.py:169`。
- `apply_edge_message_weights()` 拒绝 label、ground truth、target edge、unknown source 和 trainable weights，见 `src/covalent_design/model/edge_message_passing.py:11-38`。

问题：

- [P0] `forward_covalent()` 仅使用静态 `ModelBatch.tensors.edge_candidates_shape`，见 `src/covalent_design/model/covalent_heads.py:131-132`。它不接收或生成 `StepwiseCandidateSet`。
- [P0] 全仓搜索显示 `build_stepwise_candidates()` 和 `apply_edge_message_weights()` 在 `src/` 中只有定义和 export，没有生产调用方。防泄漏 guard 存在，但没有证明训练路径实际经过 guard。

### Task 21 Final Decode

结论：

- 作为接口 skeleton 可接受。
- valid、invalid、all-candidates-fail、required-state-unavailable 分支有测试。
- Task 24 可暂不实现真实 rule gate，但 smoke 路径必须明确是否绕过 Task 21，避免误把 skeleton 当生产 gate。

### Task 22 Training Dataset And Batch Loader

健康部分：

- `prepare_dataset()` 实现 split-specific filtering、visual block、quality tier、multi-linkage、Q2 policy 和 exclusion summary。
- Exclusion order 文档与代码总体一致。

问题：

- [P0] `src/covalent_design/training/batch.py:10-24` 的 `load_training_batch()` 仍直接抛出 `NotImplementedError`。
- [P0] `TrainingDatasetIndex` 仅保留过滤后的 `TrainingRecordEntry`，没有定义 `batch_id` 到 record subset 的映射，也没有定义如何把 split-filtered records 交给只接受 `records_path` 的 `make_model_batch()`。
- [P1] `prepare_dataset()` 对 malformed JSON object 的结构防御不足。`src/covalent_design/training/dataset.py:151-152`、`:158-159`、`:290-297` 可能抛出原始 `AttributeError`、`KeyError` 或 `TypeError`，没有转换为 `ContractEnvelope` structured failure。

### Task 23 Loss Masks And Denominators

健康部分：

- `compute_mask_audit()` 明确区分 NP、FP、NN、Q2、pending SMARTS、pending geometry、missing chemical state。
- `build_edge_denominators()` 从 audit 投影 10-field denominator 并调用 `.validate()`。
- strata 聚合会逐字段求和再投影。

问题：

- [P0] Task 23 正确规定 bond-type 和 geometry 只使用 NP，见 `src/covalent_design/training/masks.py:52-58`；Task 12/18 却使用更宽的 denominator。共享语义没有冻结。
- [P1] `LossReport.to_dict()` 丢弃每个 strata 的 `mask_audit`，见 `src/covalent_design/contracts/types.py:651-659`。这与 `DenominatorsStratum.mask_audit` 类型及 Checkpoint B 证据目标不一致。
- [P1] `compute_mask_audit()` 的四个布尔输入声明为 upstream-normalized，但 Task 24 前尚无明确 resolver owner。`compute_losses(output, batch, weights)` 的 public signature 也没有参数承载 candidate set、audit 或 normalized flags。

## Documentation-Code Drift

### [P0] Task 12 artifact schema 与 Task 18 reader 不一致

证据：

- Task 12 writer：`src/covalent_design/candidates/edge_candidates.py:194-201`
- Task 18 reader：`src/covalent_design/model/candidate_builder.py:23-25`
- Task 12 fixture：`tests/fixtures/edge_candidates/valid/artifacts/e1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6/edge_candidates.json`
- Task 18 fixture：`tests/fixtures/model/stepwise_candidates/within_radius/edge_candidates.json`

Task 12 平铺输出：

```text
positive_edge.target_atom_name
positive_edge.target_atom_element
positive_edge.ligand_atom_name
positive_edge.ligand_atom_element
positive_edge.distance_angstrom
```

Task 18 要求：

```text
positive_edge.ligand_atom_index
positive_edge.target_atom
positive_edge.bond_type
```

影响：Task 18 无法消费真实 Task 13 finalized manifests 中挂接的 Task 12 artifact。

### [P0] denominator 语义在 Task 12、18、23 之间冲突

证据：

- Task 12：`src/covalent_design/candidates/edge_candidates.py:31-49`
- Task 18：`src/covalent_design/model/candidate_builder.py:108-119`
- Task 23：`src/covalent_design/training/masks.py:52-58`
- Training spec：`docs/specs/03-training.md:88-90`、`:162-166`
- Model spec：`docs/specs/02-model.md:267-277`

Task 23 明确 natural negative 只进入 edge existence 和 message passing，不进入 bond-type 或 geometry。Task 12 将所有 candidates 计入 bond/geometry；Task 18 将所有 natural candidates 计入 bond/geometry。`docs/specs/02-model.md:274-275` 又固化了 Task 18 的较宽语义。

### [P1] Task 24 依赖声明不完整

证据：

- `docs/specs/implementation-plan.md:1051-1099`

文档只列 `Tasks 20, 23`，但 smoke train 至少还依赖：

- Task 22 dataset-to-batch loader
- Task 18 per-timestep candidates
- upstream flag resolver
- smoke fixture bundle
- loss weights policy
- `python -m covalent_design.training.train` CLI module

Task 24 文件列表仅列 `losses.py`、`train_loop.py`、`test_train_smoke.py`，但 verification 命令要求 `covalent_design.training.train` 和 `configs/covalent_train_smoke.yml`。

### [P1] Training spec 中仍有内部冲突

证据：

- `docs/specs/03-training.md:5` 把 family auxiliary head 描述为 optional diagnostic。
- `docs/specs/03-training.md:184` 又声明 `family_aux_loss` 在 v1 必填。
- `docs/specs/03-training.md:19` 使用不存在的 `covalent_design.training.prepare_dataset` CLI，并传入非法 split 名 `"scaffold"`。
- `docs/specs/03-training.md:52-60` 示例缺少 `family_aux_loss`，且调用不存在的 `denominators.to_dict()`。
- `docs/specs/03-training.md:81` 写成 “Q0/Q1 rejected records absent”，术语不准确；Q0/Q1 是质量层级，不应等同 rejected。

### [P1] Verification matrix 使用当前环境不可执行的 pytest 命令

证据：

- `docs/specs/verification-matrix.md:24-30`
- `.github/workflows/ci.yml:31-37`

文档使用 `pytest`，当前解释器没有安装 `pytest`；CI 只运行 `unittest discover`。建议补充开发依赖或同时记录 `unittest` 等价命令。

### [P1] Checkpoint B CLI 证据尚未规划完整

证据：

- `docs/specs/verification-matrix.md:54-61`

Checkpoint B 要求：

```text
python -m covalent_design.model.forward_smoke --config configs/covalent_model_smoke.yml
python -m covalent_design.training.train --config configs/covalent_train_smoke.yml
```

但 Task 24 文件清单没有明确 `model.forward_smoke`、`training.train` 和配置文件 owner。

## Code Quality Findings

### P0

#### [P0] Reactive target atom resolver 不满足结构原子身份要求

文件：

- `src/covalent_design/candidates/edge_candidates.py:104-109`
- `src/covalent_design/model/candidate_builder.py:34-39`

证据：

两个模块都使用：

```python
if atom.get("name") == target_atom_name:
    target_atom = atom
    break
```

影响：

- 多残基蛋白中会选错 target atom。
- Task 12 静态监督 edge、Task 18 动态 edge、denominators 和 forced-positive 统计都会被污染。
- 现有 fixtures 只有一个匹配 atom name，无法发现错误。

建议：

- 复用一个共享 target atom resolver。
- 优先使用 `target_atom_index` 或完整 `ProteinAtomIdentity`。
- 对 fallback-by-name 设为显式兼容模式，并在多匹配时 hard fail。

#### [P0] Task 20 仍未消费 Task 18 动态 candidates

文件：

- `src/covalent_design/model/candidate_builder.py`
- `src/covalent_design/model/covalent_heads.py:99-179`
- `src/covalent_design/model/edge_message_passing.py`

影响：

- 训练 smoke 可能继续使用 ground-truth-coordinate 静态 candidate shape。
- 动态候选、forced positive 和 denominator audit 不会真正参与 forward。
- ADR 0035 明确警告 train/inference skew，见 `docs/adr/0035-task17-model-batch-contract.md:68-75`。

### P1

#### [P1] `LossReport.to_dict()` 丢失 strata audit

文件：

- `src/covalent_design/contracts/types.py:651-659`

影响：

- Checkpoint B 无法从 `train_metrics.jsonl` 复核每个 family/timestep stratum 的 mask 原因。

#### [P1] `EdgeDenominators.validate()` 允许 under-accounting

文件：

- `src/covalent_design/contracts/denominators.py:53-60`

当前只拒绝：

```text
eligible_edge_count + masked_candidate_count > candidate_count
```

对于由 mask projection 产生的 denominator，应要求等于 `candidate_count`。当前 validator 也没有约束 edge-loss denominator 必须等于 eligible edge count。

影响：

- Task 24 日志可能通过 validator，但遗漏部分候选。

#### [P1] ModelBatch 的 visual provenance 被硬编码

文件：

- `src/covalent_design/model/batch.py:167-168`

影响：

- header 与 finalized record metadata 不一致。
- 训练治理和 debug 输出会错误显示 pending。

#### [P1] Task 22 malformed input 可能逃逸 structured error

文件：

- `src/covalent_design/training/dataset.py:135-159`
- `src/covalent_design/training/dataset.py:283-309`

影响：

- JSON 可解析但 shape 错误时可能抛出原始异常，而不是 `ContractEnvelope` failure。

### P2

#### [P2] `contracts/types.py` 已承担过多领域类型

文件：

- `src/covalent_design/contracts/types.py`

建议：

- Task 24 阻塞修复完成后，再按 domain 拆分 `contracts/model.py`、`contracts/training.py`、`contracts/inference.py`、`contracts/evaluation.py`。
- 保留 `contracts/__init__.py` 作为稳定 re-export facade。
- 不要在 Task 24 前做大规模搬迁。

#### [P2] 部分 contract 使用宽泛 `dict` 与 raw string

建议：

- 后续逐步增强 schema validation，不要在 smoke loop 中临时补 ad-hoc parsing。

## Test Quality Findings

### 健康部分

- 完整 suite 共 906 tests，通过。
- Task 17-23 都有 focused `unittest`。
- Task 18 覆盖 forced positive、zero negatives、determinism、pure in-memory。
- Task 20 覆盖 detached message weights、forbidden source、provenance marker。
- Task 22 覆盖过滤优先级、Q2、visual blocking、determinism。
- Task 23 覆盖 masks、projection、strata、timestep bucket。

### [P0] 缺少真实 Task 12 -> Task 18 artifact compatibility test

现有 Task 18 fixtures：

- `tests/fixtures/model/stepwise_candidates/`

真实 Task 12 fixtures：

- `tests/fixtures/edge_candidates/`

问题：

- 两套 fixture schema 不同。
- Task 18 测试没有读取 Task 12 writer 的真实输出。

必须补：

- 使用 Task 12 builder 输出或 Task 13 finalized bundle，直接调用 Task 18 builder。
- 验证 positive target identity、ligand atom identity、bond type、forced-positive 和 denominator。

### [P0] 缺少多残基同名原子 fixture

必须补：

- 至少两个 CYS 残基都包含 `SG`。
- target identity 指向第二个残基。
- Task 12 与 Task 18 都必须选择正确原子。
- 如果仅给 atom name 且多匹配，必须 hard fail。

### [P0] 缺少 Task 17 -> 24 tracer-bullet integration fixture

必须覆盖：

```text
finalized records
  -> split filtering
  -> load_training_batch
  -> make_model_batch
  -> stepwise candidates
  -> fake PMDM
  -> covalent heads
  -> message guard
  -> mask audit
  -> denominators
  -> LossReport.to_dict()
```

### [P1] 缺少 malformed training artifact tests

建议覆盖：

- split root 不是 object
- assignments 不是 list
- assignment 缺 `record_id`
- record row 缺 `record_id`
- artifact 缺 `uri`、`sha256` 或 `format`
- artifact entry 不是 object

### [P1] fixture 仍偏理想化

问题：

- Task 18 fixture 直接提供理想化 nested target atom。
- Task 22 dataset fixture artifact refs 不足以证明真实 batch loading。
- 当前没有同时覆盖 Q2、pending geometry、pending SMARTS、missing state、forced positive 和 strata serialization 的单个 smoke bundle。

## Integration Risks

### [P0] Task 12 -> 13 -> 17 -> 18 artifact chain 当前不可执行

Task 13 只验证 edge candidate artifact 的 path/checksum 与 manifest linkage，不验证它是否满足 Task 18 的内容 schema。因此 finalized manifest 可以通过，但 Task 18 运行时失败。

### [P0] Task 22 -> Task 17 batch seam 尚未定义

`prepare_dataset()` 返回 split-filtered entries，但 `make_model_batch()` 接受完整 records path。`load_training_batch()` 仍为 stub。若 Task 24 自行读取 JSONL 并过滤，会复制 Task 22/17 逻辑。

### [P0] Task 18 -> Task 20 seam 尚未定义

需要冻结：

- 谁在每个 timestep 调用 `build_stepwise_candidates()`
- candidate padding 与 batch flatten 策略
- `StepwiseCandidateSet` 如何映射为 logits 维度和 labels
- forced positives 如何进入 edge loss、gate，但排除 bond/geometry/message passing

### [P0] Task 23 -> Task 24 seam 尚未定义

`docs/specs/interface-design.md:1486-1490` 当前签名：

```python
compute_losses(output: ModelForwardOutput, batch: ModelBatch, weights: LossWeights) -> LossReport
```

该接口无法明确接收：

- `StepwiseCandidateSet`
- `MaskAudit`
- upstream-normalized flags
- per-family/timestep strata entries

### [P1] Task 24 loss weights 尚未冻结

证据：

- `docs/specs/03-training.md:194-197`
- `docs/specs/implementation-plan.md:1065-1084`

Task 24 smoke config 没有 loss weights。至少需要明确 smoke 默认值、weighted total 的计算方式，以及 class imbalance 是否在 Task 24 deferred。

## Doubt-Driven Adversarial Findings

本轮采用以下反证问题：

1. 如果每个局部测试都通过，真实上游 artifact 能否直接进入下游？
2. 如果 protein atom name 重复，identity 是否仍唯一？
3. 如果 Task 24 只按当前 interface 实现，是否会复制 batch/filter/candidate 逻辑？
4. 如果 guard 有测试，真实 forward 是否一定经过 guard？
5. 如果 denominator validator 通过，是否代表 conservation 完整？

得到的反证结果：

- 局部测试通过，但 Task 12 artifact 不能直接进入 Task 18。
- target atom name 不是结构原子身份，重复名称会选错监督原子。
- `load_training_batch()` 仍为 stub，Task 24 没有合法 dataset-to-batch 路径。
- `apply_edge_message_weights()` 只有定义与单测，没有生产调用。
- denominator validator 仍允许部分 under-accounting。

## Task 24 Readiness

**Task 24 Ready：No**

Task 24 的最小可启动条件尚未满足。

必须冻结的输入：

- 真实 Task 12 edge artifact v2 schema 或兼容 adapter。
- 完整 target atom identity resolver。
- split-filtered dataset 到 `ModelBatch` 的 batch-loader contract。
- per-timestep candidate batch representation。
- Task 20 forward 如何消费动态 candidates。
- Task 23 normalized flags 的 resolver owner。
- `compute_losses()` 的完整输入 contract。
- smoke loss weights 与 weighted total 规则。
- smoke fixture bundle 与 CLI module owner。

可以暂时 deferred：

- 真实 PMDM upstream dependency。
- GPU training。
- full epoch convergence。
- experiment tracking backend。
- production RDKit scaffold derivation。
- contracts 大规模拆分。

## Required Fixes Before Task 24

### P0 必须先修

1. 统一 Task 12 与 Task 18 的 `edge_candidates` schema。
   - 补充 `ligand_atom_index`、完整 `target_atom` identity、`bond_type`。
   - 决定兼容旧 artifact 还是升级 contract version。
   - 增加 Task 12 -> Task 18 integration test。

2. 提取并复用 target atom resolver。
   - Task 12、Task 17、Task 18 使用同一语义。
   - 首选 index 或完整 identity。
   - atom-name fallback 多匹配时 hard fail。

3. 统一 denominator 语义。
   - natural negatives：edge existence + message passing only。
   - forced positives：edge existence + gate only。
   - bond-type / geometry：仅 natural positives，且受 pending masks 控制。
   - 更新 Task 12、Task 18、Task 23、spec 和 tests。

4. 实现并冻结 `load_training_batch()`。
   - 定义 `batch_id`。
   - 定义 split-filtered record subset 如何交给 `make_model_batch()`。
   - 禁止 Task 24 复制 Task 17 batch construction。

5. 定义 Task 18 -> Task 20 -> Task 23 -> Task 24 集成 contract。
   - 动态 candidates 的 batch representation。
   - logits/labels/padding 对齐。
   - message weights 实际应用点。
   - normalized flags resolver owner。
   - `compute_losses()` 完整输入。

6. 冻结 Task 24 smoke loss weights。
   - 默认权重。
   - total loss 公式。
   - class imbalance 是否 deferred。

### P1 建议在 Task 24 代码前一并修

1. 修复 `LossReport.to_dict()` strata serialization，保留 `mask_audit`。
2. 修复 ModelBatch 的 `visual_check_status` metadata passthrough。
3. 对每条记录的 `EdgeDenominators` 立即 validate。
4. 收紧 shared denominator conservation validator。
5. 补 malformed Task 22 input 的 structured failure tests。
6. 修正文档 CLI、Task 24 files/modules、family aux 术语和 verification 命令。

## Deferrable Improvements

### P2 可后修

- 拆分 `contracts/types.py`，保留 façade。
- 将 raw string status 逐步收紧为枚举或集中常量。
- 为 parser/resolver 增加 typed artifact schema。
- 增加 production scaffold chemistry library 决策。
- 增加实验 tracking backend。
- 增加真实 PMDM/PyTorch/GPU integration。
- 增加 Task 21 production validity gate backend。

## Recommended Next Workflow

建议不要直接进入 Task 24。按以下顺序修复：

1. **Contract freeze**
   - 明确 edge artifact schema、target identity、denominator equations、dynamic candidate batch、loss input contract。

2. **Tracer-bullet tests**
   - 先补 Task 12 -> 18 compatibility test。
   - 再补 multi-residue duplicate atom-name fixture。
   - 再补 Task 17 -> 24 最小 smoke integration fixture。

3. **Narrow implementation patches**
   - 修 Task 12 writer 与共享 resolver。
   - 修 Task 18 reader 与 denominator。
   - 实现 Task 22 loader。
   - 接通 Task 18 -> 20 message path。
   - 修 LossReport strata serializer。

4. **Documentation synchronization**
   - 更新 `02-model.md`、`03-training.md`、`interface-design.md`、`implementation-plan.md`、`verification-matrix.md`。
   - 如 edge artifact schema 或 identity authority 改变，新增 ADR。

5. **Re-run readiness gate**
   - compileall
   - full unittest
   - directed integration tests
   - CLI smoke
   - git status

6. **开始 Task 24**
   - 仅在 tracer-bullet 路径通过后实现 `losses.py`、train loop 和 CLI。

## Suggested Skills For Next Step

| Skill | 用途 |
| --- | --- |
| `grill-with-docs` | 冻结 edge artifact schema、identity authority、denominator 公式、Task 24 loss 输入 |
| `api-and-interface-design` | 设计 `load_training_batch()`、dynamic candidate batch、`compute_losses()` |
| `documentation-and-adrs` | 记录 schema/version 与 identity resolver 决策 |
| `test-driven-development` | 先写 Task 12 -> 18、duplicate atom name、Task 17 -> 24 tracer-bullet tests |
| `incremental-implementation` | 将修复拆成小批次，避免同时改动过多边界 |
| `code-review-and-quality` | 每批修复后检查回归、职责漂移与文档同步 |
| `doubt-driven-development` | 在 Task 24 开始前再次做 fresh-context 对抗复核 |
| `debugging-and-error-recovery` | 仅在验证失败时定位根因 |

## Files That Should Not Be Touched Yet

在 P0 contract freeze 前，不建议修改：

- `src/covalent_design/training/losses.py`
- `src/covalent_design/training/train_loop.py`
- `src/covalent_design/training/train.py`
- `configs/covalent_train_smoke.yml`
- Task 25+ training manifest/checkpoint files
- `src/covalent_design/inference/`
- `src/covalent_design/evaluation/`
- Task 26+ specs

原因：这些文件会依赖尚未冻结的 edge artifact、identity、dynamic candidate、batch-loader、mask 和 loss contracts。提前实现只会把缺口扩散到更多模块。
