# PocketFlow Supervision And Loss Context

本文档用 context-engineering 的方式整理 PocketFlow 中“监督信号如何构造”和“损失函数如何设计”。目标不是复述每一行代码，而是给后续分析、改模型、复现实验时一个可加载的上下文地图。

## 1. 快速结论

PocketFlow 是一个基于蛋白口袋上下文的逐原子自回归生成模型。训练时，它把完整配体拆成一系列生长步骤；每一步输入“蛋白口袋 + 已生成配体上下文”，监督模型预测下一步：

1. 从哪里继续生长，也就是 focal atom / protein surface focal。
2. 下一颗原子的元素类型。
3. 下一颗原子的三维坐标。
4. 下一颗原子与已有上下文原子的键类型。

总损失定义在 `PocketFlow/pocket_flow/gdbp_model/pocket_flow.py::PocketFlow.get_loss`：

```python
loss = ll_atom + loss_pos + ll_edge + focal_loss + surf_loss
```

五个损失项分别对应：原子类型 flow 似然、坐标 MDN 负对数似然、键类型 flow 似然、配体 frontier 二分类、蛋白表面起始焦点二分类。

## 2. 上下文索引

后续如果让 agent 继续分析 PocketFlow 的训练或损失函数，优先加载这些文件，而不是一次性加载整个仓库。

| 层级 | 文件 | 为什么重要 |
| --- | --- | --- |
| 入口 | `PocketFlow/pretraining.py` | ZINC 预训练入口，定义 transform、模型配置、训练循环。 |
| 入口 | `PocketFlow/finetuning.py` | CrossDocked 口袋-配体微调入口。 |
| 模型汇合点 | `PocketFlow/pocket_flow/gdbp_model/pocket_flow.py` | `PocketFlow` 模块组合和 `get_loss()` 总损失。 |
| 数据轨迹 | `PocketFlow/pocket_flow/utils/transform.py` | `LigandTrajectory`、`FocalMaker`、`AtomComposer`、`Combine`。 |
| 标签构造 | `PocketFlow/pocket_flow/utils/transform_utils.py` | `mask_node()`、`sample_edge_with_radius()`、`get_tri_edges()`。 |
| 推理对应关系 | `PocketFlow/pocket_flow/generate.py` | 生成时按焦点、原子、坐标、键的顺序串联各预测头。 |
| 训练循环 | `PocketFlow/pocket_flow/utils/train.py` | 每步调用 `model.get_loss(batch)` 并反传。 |

## 3. 数据流总览

训练样本原始形态是 `ComplexData`，包含蛋白口袋原子、配体原子、配体键、三维坐标等。transform 管线把一个完整配体拆成多个“下一步生成”样本。

```text
raw protein-ligand complex
  -> RefineData
  -> LigandCountNeighbors
  -> FeaturizeProteinAtom / FeaturizeLigandAtom
  -> Combine
      -> choose ligand generation order by BFS/RFS/mix
      -> mask_node: split ligand into context atoms and future atoms
      -> FocalMaker: build focal, atom, edge labels
      -> AtomComposer: compose protein + ligand context graph
  -> collate_fn
  -> PocketFlow.get_loss
```

核心概念：

- `context_idx`：当前步骤中已经生成的配体原子。
- `masked_idx`：当前步骤中还未生成的配体原子，`masked_idx[0]` 是本步要预测的下一颗真实原子。
- `ligand_context_*`：当前已生成配体上下文的元素、坐标、键、邻居数等。
- `cpx_*`：protein pocket 和 ligand context 拼接后的 complex graph。
- `y_pos`：下一颗真实原子的坐标标签。
- `atom_label`：下一颗真实原子的元素类型标签。
- `edge_label`：下一颗原子与候选上下文原子之间的键类型标签。

## 4. 监督信号如何构造

### 4.1 生长轨迹监督

`LigandTrajectory` / `Combine` 会为每个配体选择一个生成顺序。支持：

- BFS：普通广度优先。
- RFS：优先考虑 ring-aware 的顺序。
- mix：训练中随机在 BFS 和 RFS 之间选。

每个生成顺序都会产生多个训练步骤。第 `ix` 步输入前 `ix` 个原子作为上下文，监督模型预测第 `ix + 1` 个原子。

### 4.2 `mask_node()` 构造当前上下文

`mask_node(data, context_idx, masked_idx, ...)` 是监督构造的基础：

- `ligand_context_pos = ligand_pos[context_idx]`
- `ligand_masked_pos = ligand_pos[masked_idx]`
- `y_pos = ligand_masked_pos[0] + noise`
- 重新计算上下文中的邻居数、价态、键数特征
- `ligand_frontier = ligand_context_num_neighbors < ligand_num_neighbors[context_idx]`

`ligand_frontier` 的含义是：上下文中哪些已生成原子在完整配体里还有未生成邻居，因此可以继续作为生长焦点。

### 4.3 起始原子的蛋白表面监督

当 `ligand_context_pos.size(0) == 0`，也就是还没有任何配体原子时，模型不能从配体 frontier 开始生长。此时 `FocalMaker` 在蛋白原子中找靠近真实配体原子的位置：

- 用 `radius(x=ligand_masked_pos, y=protein_pos, r=...)` 找候选蛋白 focal。
- 如果半径内没有候选点，就退化为选择离真实配体最近的蛋白原子。
- 输出 `candidate_focal_label_in_protein` 作为蛋白表面二分类标签。

这对应损失里的 `surf_loss`。

### 4.4 非起始步骤的焦点监督

当已有配体上下文时，下一颗真实原子的邻居中，已经在上下文里的那些原子就是候选 focal：

```text
new_step_atom_idx = masked_idx[0]
candidate_focal_idx_in_context = ligand_nbh_list[new_step_atom_idx]
focal_idx_in_context_ = candidate_focal_idx_in_context intersect context_idx
focal_idx_in_context = random choice from focal_idx_in_context_
```

代码会随机选一个真实邻接原子作为当前训练步的 focal，并把 `focal_label` 中对应位置置为 1。与此同时，所有 frontier 标签仍由 `ligand_frontier` 提供，用于 BCE 监督。

### 4.5 原子类型监督

`atom_label` 是下一颗真实原子的元素类别：

```text
atom_label = index of ligand_element[masked_idx[0]] in [C, N, O, F, P, S, Cl, Br, I]
```

模型不是直接用交叉熵，而是将 one-hot 原子类型加均匀噪声做 dequantization，然后用 conditional normalizing flow 学似然。

### 4.6 坐标监督

`y_pos` 是下一颗真实原子的三维坐标，训练时加少量高斯噪声。`PositionPredictor` 输出一个混合高斯分布：

- `abs_mu`：各混合分量的绝对坐标均值。
- `sigma`：各分量标准差。
- `pi`：混合权重。

监督目标是最大化真实坐标 `y_pos` 在该混合高斯下的概率。

### 4.7 键类型监督

`sample_edge_with_radius(data, r=4.0)` 会以新原子真实坐标 `y_pos` 为 query，找半径 4A 内的 ligand context 原子作为候选边。

对每条候选边：

- 如果完整配体中真实存在该键，`edge_label` 是真实键类型：1 单键、2 双键、3 三键。
- 如果不存在键，`edge_label = 0`。

因此键预测是一个四分类问题：`0 = no bond`，`1/2/3 = chemical bond type`。但实现上同样使用 conditional flow 而不是普通交叉熵。

`get_tri_edges()` 额外构造候选边之间的三角关系特征，让 `BondFlow` 的 edge attention 可以感知已有上下文键结构。

## 5. 模型与损失函数对应关系

### 5.1 上下文编码

`PocketFlow.get_loss()` 先执行：

```python
h_cpx = embed_compose(...)
h_cpx = self.encoder(...)
```

这里 `h_cpx` 是蛋白原子和已生成配体上下文原子的联合表示，后续所有预测头都依赖它。

### 5.2 `focal_loss`

```python
focal_pred = self.focal_net(h_cpx, data.idx_ligand_ctx_in_cpx)
focal_loss = BCEWithLogits(focal_pred, data.ligand_frontier)
```

监督对象是当前配体上下文里的 frontier 原子。它解决的是：已经有部分配体时，下一步应该从哪个已有配体原子继续长。

### 5.3 `surf_loss`

```python
focal_pred_apo = self.focal_net(h_cpx, data.apo_protein_idx)
surf_loss = BCEWithLogits(focal_pred_apo, data.candidate_focal_label_in_protein)
```

监督对象是 apo protein / protein surface 上的候选起点。它解决的是：还没有任何配体原子时，第一个原子应该从口袋哪个区域开始生成。

注意：非起始步骤中 `apo_protein_idx` 和 `candidate_focal_label_in_protein` 为空，因此这一项只在起始步骤实际贡献监督。

### 5.4 `ll_atom`

```python
x_z = one_hot(data.atom_label)
x_z += deq_coeff * rand(...)
z_atom, atom_log_jacob = self.atom_flow(x_z, h_cpx, data.focal_idx_in_context)
ll_atom = (0.5 * z_atom ** 2 - atom_log_jacob).mean()
```

这是原子类型的 conditional flow 负对数似然近似。直觉上：

- flow 把离散 one-hot 原子类型映射到标准高斯潜变量空间。
- `0.5 * z^2` 是标准高斯能量项。
- `- log|J|` 是 normalizing flow 的雅可比修正项。
- 条件是 focal atom 的上下文表示。

### 5.5 `loss_pos`

```python
relative_mu, abs_mu, sigma, pi = self.pos_predictor(...)
loss_pos = -log(MDN_probability(abs_mu, sigma, pi, data.y_pos)).mean()
```

这是坐标的混合密度网络负对数似然。模型预测的不是单点坐标，而是多个可能的三维高斯分量。这样可以表达同一个 focal 附近多种合理方向或构象。

### 5.6 `ll_edge`

```python
z_edge = one_hot(data.edge_label, num_classes=4)
z_edge += deq_coeff * rand(...)
z_edge, edge_log_jacob = self.edge_flow(...)
ll_edge = (0.5 * z_edge ** 2 - edge_log_jacob).mean()
```

这是候选边键类型的 conditional flow 负对数似然。候选边来自半径采样，标签包含无键和三种键型。

`BondFlow` 的条件信息包括：

- 新原子坐标 `y_pos`。
- 候选边 `edge_query_index`。
- complex graph 表示 `h_cpx`。
- query 位置到 complex graph 的 KNN。
- 三角边结构 `tri_edge_index` / `tri_edge_feat`。
- 新原子类型 embedding。

## 6. 训练与生成的一致性

训练时的监督顺序与生成时的采样顺序一致：

| 训练监督 | 生成函数 | 作用 |
| --- | --- | --- |
| `surf_loss` / `focal_loss` | `Generate.choose_focal()` | 选择蛋白起点或配体 frontier。 |
| `ll_atom` | `Generate.atom_generate()` | 从 flow reverse 得到原子类型。 |
| `loss_pos` | `Generate.pos_generate()` | 从 MDN 输出中选择新原子坐标。 |
| `ll_edge` | `Generate.bond_generate()` | 从 flow reverse 得到候选边键类型。 |

生成中还额外加入了化学规则过滤：

- focal 原子价态检查。
- 新键距离范围过滤。
- RDKit valency check。
- 部分 alert substructure 过滤。
- 最终 `modify()` 修正部分结构。

这些规则不是训练损失的一部分，而是推理时保证化学有效性的后处理和重采样约束。

## 7. 需要注意的实现细节

1. 原子和键的分类没有用普通 cross entropy，而是用 dequantized one-hot + conditional normalizing flow。
2. 坐标使用 MDN，不是 MSE；这对多模态空间构象更合理。
3. `focal_label` 字段被构造出来，但 `get_loss()` 实际使用的是 `ligand_frontier` 作为配体上下文 focal BCE 的 target。
4. `surf_loss` 只在配体为空的起始步骤有效；非起始步骤相关 tensor 为空。
5. 预训练里 `Combine(..., lig_only=True)` 会跳过第一个空配体起始步骤，因此更偏向学习配体内部增长；微调会包含蛋白口袋起始监督。
6. `Experiment.fit_step()` 会给 `batch.cpx_pos` 加噪声，这意味着上下文图坐标也有训练时扰动。
7. `pos_fake` / `pos_real` 在 transform 中构造，但当前 `PocketFlow.get_loss()` 没有使用对应的 fake/real position classification loss，相关代码像是旧实验遗留。

## 8. 一句话心智模型

PocketFlow 的监督设计可以理解为把一个真实配体拆成 teacher-forcing 的生长轨迹：在每个局部状态下，模型被要求学会“从哪里长、长什么、长到哪里、怎么连键”。损失函数则分别用 BCE、flow likelihood 和 MDN likelihood 来监督这些子决策。
