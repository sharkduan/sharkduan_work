# V2 真实数据 ETL — 推断规则、代码修改、操作流程记录

**日期:** 2026-06-18 / 2026-06-19
**分支:** main (起始 commit: `84dd8df`)
**最终 commit:** `60ea2e3`

---

## 一、操作流程总览

```
Step 1: 三个压缩包完全解压
Step 2: 重算 SHA-256，更新 source_manifest.json
Step 3: 运行三个转换脚本，产出 v1 parser 兼容 TSV
Step 4: 扩展 v2_conversion.py，支持 TSV 格式的三源转换
Step 5: 创建 v2 manifest + license_audit，运行 Task 40→41→42→43 全链路
Step 6: 编写 ETL 证据报告
Step 7: 编译检查 + 提交
```

### 命令速查

```bash
# 解压
tar -xzf D:\codex_work\data\CovInDB2.tar.gz -C D:\codex_work\data\CovalentInDB\raw
tar -xzf D:\codex_work\data\CovalentInDB\raw\CovInDB.tar.gz -C D:\codex_work\data\CovalentInDB\raw
Expand-Archive D:\codex_work\data\CovBinderInPDB_2022Q4.zip D:\codex_work\data\CovBinderInPDB\raw -Force
Expand-Archive D:\codex_work\data\CovPDB_complexes.zip D:\codex_work\data\CovPDB\raw -Force

# 计算 SHA-256
Get-FileHash -Algorithm SHA256 <path> | % Hash

# 运行转换
cd D:\codex_work\共价抑制剂设计
python data/v2/staging/transform_covalentin_db.py
python data/v2/staging/transform_covbinder_in_pdb.py
python data/v2/staging/transform_covpdb.py

# Pipeline dry-run
PYTHONPATH=src python -c "... validate_manifests ... stage ... convert ... license_gate ..."

# 编译检查
python -m compileall -q scripts src
```

---

## 二、数据解压情况

| 压缩包 | 大小 | 解压后 |
|--------|------|--------|
| `CovInDB2.tar.gz` (内含 `CovInDB.tar.gz`) | 1.9GB | PDB/ (3,445 pdb), `Covalent_Complex_Records.csv` (3,660行), `CovInDB_All.csv` (17,775行), `Natural_Compounds_Library.csv` (115MB), `Virtual_Screening_Library.csv` (1.9GB) |
| `CovBinderInPDB_2022Q4.zip` | 11MB | `CovBinderInPDB_2022Q4_AllRecords.csv` (7,376行), `binder_sdf/` (2,189 SDF) |
| `CovPDB_complexes.zip` | 393MB | `CovPDB_complexes/` (2,261 子目录, 4,535 文件) |

### 更新后的 source_manifest.json SHA-256

| 文件 | SHA-256 |
|------|---------|
| `CovalentInDB/raw/Covalent_Complex_Records.csv` | `f204e969695dea7deeb86f8a7c896445c3a1e843f18ad1bd9b3490b5e1774c3b` |
| `CovBinderInPDB/raw/CovBinderInPDB_2022Q4_AllRecords.csv` | `353e251a459a914450a53645d048f9ed1aea407137c240fb3245a879d6d790fa` |
| `CovPDB/raw/CovPDB_complexes.zip` | `6d05249c83ad24589fd4280c2a8e5665d839cf8ee6c33b5ea0949b40fbe04220` |

---

## 三、反应家族推断规则（按源详述）

### 3.1 CovalentInDB — 最可靠

**原始列:** `Reaction` (反应类型) + `Resi_name` (三字母残基名)

**推断步骤:**
1. `Reaction` 列查表 → `family_suffix`
2. `Resi_name` 列 → 残基前缀
3. 组合: `{RES}_{FAMILY_SUFFIX}`

**映射表 (`REACTION_TO_FAMILY`):**
```
"Michael Addition"          → MICHAEL_ADDITION
"Nucleophilic Substitution" → NUCLEOPHILIC_SUBSTITUTION
"Disulfide Exchange"        → DISULFIDE_EXCHANGE
"Acylation"                 → ACYLATION
"Phosphonate Addition"      → PHOSPHONYLATION
"Schiff Base"               → SCHIFF_BASE
未匹配                       → UNKNOWN
```

**atom_name 推断 (`RESIDUE_ATOM`):**
```
CYS→SG, SER→OG, LYS→NZ, HIS→NE2, THR→OG1, TYR→OH,
ASP→OD1, GLU→OE1, MET→SD, SEC→SE, ASN→ND2, GLN→NE2,
默认→SG
```

**bond_type 推断 (`BOND_TYPE_MAP`):**
```
Michael Addition           → single
Nucleophilic Substitution  → single
Disulfide Exchange         → single
Acylation                  → single
Phosphonate Addition       → single
Schiff Base                → double
默认                        → single
```

**结果:** 3,598 行（3,660 行源数据中 62 行缺失 Resi_name 被跳过）

---

### 3.2 CovBinderInPDB — 中等可靠

**原始列:** `full_residue_name` (全名残基) + `warhead_name` (弹头名)

**推断步骤:**
1. `full_residue_name` 转三字母（如 "Cysteine" → "CYS"）
2. `warhead_name` 查表 → `(family_suffix, bond_type)`
3. 组合: `{3-letter}_{family_suffix}`

**残基全名→三字母 (`FULL_TO_3LETTER`):**
```
cysteine→CYS, serine→SER, lysine→LYS, histidine→HIS,
threonine→THR, tyrosine→TYR, aspartic acid/aspartate→ASP,
glutamic acid/glutamate→GLU, methionine→MET, asparagine→ASN,
glutamine→GLN, tryptophan→TRP, phenylalanine→PHE,
arginine→ARG, proline→PRO, selenocysteine→SEC, glycine→GLY,
alanine→ALA, valine→VAL, leucine→LEU, isoleucine→ILE
```

**弹头→反应家族 (`WARHEAD_FAMILY`):**
```
haloacetamide      → (NUCLEOPHILIC_SUBSTITUTION, single)
α-ketoamide        → (MICHAEL_ADDITION, single)
acrylamide         → (MICHAEL_ADDITION, single)
vinyl sulfone      → (MICHAEL_ADDITION, single)
michael acceptor   → (MICHAEL_ADDITION, single)
disulfide          → (DISULFIDE_EXCHANGE, single)
phosphonate        → (PHOSPHONYLATION, single)
β-lactam           → (ACYLATION, single)
sulfonyl fluoride  → (ACYLATION, single)
aldehyde           → (SCHIFF_BASE, double)
未匹配              → (UNKNOWN, single)
```

**atom_name 推断:** 同 CovalentInDB 的 `RESIDUE_ATOM`
**attachment_atom:** 全部默认 `"C1"`

**结果:** 7,375 行全部写入。108 种弹头不在映射表中，被标记为 `{RES}_UNKNOWN`。

---

### 3.3 CovPDB — 最不可靠（纯结构推断）

**原始数据:** PDB 文件（ATOM/HETATM/LINK 行），无化学分类标注。

**推断步骤:**
1. 解析 PDB `LINK` 记录（正则提取两端的 atom/residue/chain/number/distance）
2. 判断哪侧是蛋白（残基名在标准 20 种氨基酸中），哪侧是配体
3. 蛋白残基名 → 反应类型
4. LINK 距离 → 键级
5. 组合: `{RES}_{TYPE}`

**标准氨基酸列表 (`STD_AMINO`):**
```
ALA, ARG, ASN, ASP, CYS, GLN, GLU, GLY, HIS, ILE,
LEU, LYS, MET, PHE, PRO, SER, THR, TRP, TYR, VAL,
SEC, PYL
```

**残基→反应类型 (`REACTION_FROM_RESIDUE`):**
```
CYS → MICHAEL_ADDITION
SER → ACYLATION
LYS → SCHIFF_BASE
HIS → MICHAEL_ADDITION
THR → ACYLATION
TYR → MICHAEL_ADDITION
其余 → MICHAEL_ADDITION (兜底)
```

**距离→键级:**
```
dist < 1.5Å  → double
1.5 ≤ dist < 2.5Å → single
dist ≥ 2.5Å → single
```

**问题:**
- 无法区分 CYS 的三种反应（Michael/Nucleophilic/Disulfide）
- GLU/ASP/ARG/LEU 等非标准共价残基全标为 MICHAEL_ADDITION
- LINK 记录可能只是空间邻近而非共价

**结果:** 2,261 目录 → 10,578 LINK 记录 → 10,515 有效行（63 行 resolution/ligand_chain 缺失）

---

## 四、代码修改清单

### 4.1 新建文件

| 文件 | 行数 | 用途 |
|------|------|------|
| `data/v2/staging/transform_covalentin_db.py` | 132 | CovalentInDB 26列CSV → 17列TSV 转换 |
| `data/v2/staging/transform_covbinder_in_pdb.py` | 129 | CovBinderInPDB 19列CSV → 16列TSV 转换 |
| `data/v2/staging/transform_covpdb.py` | 199 | CovPDB PDB LINK → 15列TSV 转换 |
| `data/v2/staging/covalentin_db_v1.tsv` | 3,624 | **产出** — 3,598 行 v1 TSV |
| `data/v2/staging/covbinder_in_pdb_v1.tsv` | 7,376 | **产出** — 7,375 行 v1 TSV |
| `data/v2/staging/covpdb_v1.tsv` | 10,579 | **产出** — 10,515 行 v1 TSV |
| `data/v2/manifests/covalentin_db_v2_manifest.json` | 13 | V2 manifest (SHA-256 绑定) |
| `data/v2/manifests/covbinder_in_pdb_v2_manifest.json` | 13 | V2 manifest |
| `data/v2/manifests/covpdb_v2_manifest.json` | 13 | V2 manifest |
| `data/v2/manifests/license_audit.json` | 9 | manual_exempt 许可证 |
| `data/v2/reports/v2-real-data-pipeline-dry-run-2026-06-19.json` | 44 | Pipeline dry-run 报告 |
| `docs/reviews/v2-real-local-data-etl-evidence-review-2026-06-19.md` | 68 | ETL 证据报告 |
| `docs/superpowers/plans/2026-06-18-v2-real-data-etl.md` | 1,270 | 执行计划 |

### 4.2 修改文件

| 文件 | 变更 | 说明 |
|------|------|------|
| `src/covalent_design/data/v2_conversion.py` | +385 行 | 新增 `from dataclasses import dataclass`；`SUPPORTED_PARSER_TARGETS` 从 `{"covalentin_db"}` 扩展为 `{"covalentin_db", "covpdb", "covbinder_in_pdb"}`；替换 v1 parser 桥接逻辑为 TSV 直读方案；新增 `_COLUMN_SCHEMAS` 字典 (三源各自的 required columns)；新增 `_TSVRowFailure` dataclass、`_parse_tsv_source()` 函数、`_tsv_row_to_source_ingest_record()` 函数、`_parse_residue_num_from_residue()` 函数 |
| `D:\codex_work\data\CovalentInDB\source_manifest.json` | checksum 更新 | `f204e96...` |
| `D:\codex_work\data\CovBinderInPDB\source_manifest.json` | checksum 更新 | `353e251...` |
| `D:\codex_work\data\CovPDB\source_manifest.json` | checksum 更新 | `6d05249...` |

### 4.3 未修改（只读引用）

| 文件 | 用途 |
|------|------|
| `src/covalent_design/data/sources/covalentin_db.py` | V1 CovalentInDB parser（定义了10个 REQUIRED_COLUMNS） |
| `src/covalent_design/data/sources/covpdb.py` | V1 CovPDB parser（定义了12个 REQUIRED_COLUMNS） |
| `src/covalent_design/data/sources/covbinder_in_pdb.py` | V1 CovBinderInPDB parser（定义了11个 REQUIRED_COLUMNS） |
| `src/covalent_design/data/v2_intake.py` | V2 staging (Task 41) |
| `src/covalent_design/data/v2_license.py` | V2 license gate (Task 43) |
| `src/covalent_design/data/v2_manifests.py` | V2 manifest validation (Task 40) |

---

## 五、Git Commit 记录

```
60ea2e3 docs: add V2 real data ETL evidence review and implementation plan
4ff7c5e feat(v2): add v2 manifests, pipeline dry-run report, and TSV-based conversion bridge
bea50e7 feat(v2): regenerate v1 parser TSV files after full extraction
353ddce feat(v2): extend v2_conversion to support covpdb and covbinder_in_pdb via v1 parser bridge
a7b5f69 feat(v2): add CovPDB PDB LINK -> v1 parser TSV transformation script and output
48dbd94 feat(v2): add CovBinderInPDB -> v1 parser TSV transformation script and output
10c8c90 feat(v2): add CovalentInDB -> v1 parser TSV transformation script and output
84dd8df docs: update v2 intake governance  ← 起始点
```

---

## 六、Pipeline 全链路结果

```
Task 40 (manifest validation)   : ALL PASS (3/3)
Task 41 (staging)               : ALL checksum_verified (3/3)
Task 42 (conversion)            : 21,488 SourceIngestRecords
  CovalentInDB  : 3,598 records (0 errors)
  CovBinderInPDB: 7,375 records (0 errors)
  CovPDB        : 10,515 records (63 errors: 34 missing resolution, 29 missing ligand_chain)
Task 43 (license gate)          : ALL training_eligible (manual_exempt)
```

### 产出 TSV SHA-256

```
covalentin_db_v1.tsv     : cc3a91a609932cb9db36aa0af8b568274653f5991e46206e4231067d9eaf637e
covbinder_in_pdb_v1.tsv  : c87b78404abd8ef0c4ad8a52dd40f29dae130ee1d3627983cea94043b099bfe1
covpdb_v1.tsv            : a9bbe5c599e7091f024e020b6e0b622649050de24f38dc7dede13f57f8b15883
```

---

## 七、已知限制与待办

1. **CovBinderInPDB 108 种未知 warhead** — 需要化学专家补全 `WARHEAD_FAMILY` 映射表
2. **CovPDB 反应类型不可靠** — 所有 CYS 统一标为 MICHAEL_ADDITION，无法区分 Disulfide/Nucleophilic；非标准残基（GLU/ASP/ARG/LEU）全标为 MICHAEL_ADDITION
3. **attachment_atom 全部默认 "C1"** — CovalentInDB 和 CovBinderInPDB 原始数据无 attachment atom 信息
4. **CovPDB 63 行缺失字段** — 需人工补全 resolution 或确认某 PDB 文件缺少 REMARK 2
5. **bond_type 启发式** — 距离判断粗糙（<1.5Å = double），Disulfide bond 应为 single 但距离可能类似
