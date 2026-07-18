# thesis-revision-professor

中文 | [English summary](#english-summary)

一个面向硕士、博士论文的开源混合审稿与 Word 受控修改系统。v3 将确定性安全引擎与 Codex 语义教授审查结合起来，提供主张—证据图、学科/方法路由、分阶段确认、跨轮次状态、回归回滚和保留原 DOCX 包结构的修订。

本项目不会虚构数据、文献、实验、访谈、案例、政策、统计结果或结论，也不承诺毕业、答辩、盲审、发表或查重结果。

## 30 秒体验

```bash
git clone https://github.com/shidesheng0218/thesis-revision-professor.git
cd thesis-revision-professor
python3 -m thesis_revision_professor demo --outdir demo-output
```

打开：

- `demo-output/修改说明与盲审风险报告.docx`
- `demo-output/逐条修改清单.docx`
- `demo-output/论文修改稿.docx`

## 安装

直接使用源码：

```bash
git clone https://github.com/shidesheng0218/thesis-revision-professor.git
cd thesis-revision-professor
python3 -m thesis_revision_professor --help
```

安装 CLI：

```bash
python3 -m pip install .
thesis-review --help
```

安装为 Codex Skill：

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/shidesheng0218/thesis-revision-professor.git ~/.codex/skills/thesis-revision-professor
```

重启 Codex 后，把论文 `.docx` 路径交给它，并要求使用 `thesis-revision-professor`。

## 完整混合审稿

第一轮确定性预检：

```bash
python3 -m thesis_revision_professor review thesis.docx \
  --level master \
  --discipline education \
  --method qualitative \
  --stage blind-review \
  --outdir outputs/round-001
```

关键输出：

- `document_model.json`：稳定段落定位与原文哈希；
- `claim_evidence_graph.json`：类型化主张—证据关系；
- `selected_strategy.json`：实际生效的学科和方法协议；
- `semantic_review_request.json`：供 Codex 独立语义审查；
- `revision_plan.json`：作者确认契约；
- `revision_state.json`：Issue 生命周期与收敛状态。

在 Codex 完成 `semantic_findings.json` 后重新合并：

```bash
python3 -m thesis_revision_professor review thesis.docx \
  --level master \
  --discipline education \
  --method qualitative \
  --semantic-findings semantic_findings.json \
  --state outputs/round-001/revision_state.json \
  --outdir outputs/round-001-semantic
```

确认 `revision_plan.json` 后执行 Word 修订：

```bash
python3 -m thesis_revision_professor revise thesis.docx \
  --plan outputs/round-001-semantic/revision_plan.json \
  --state outputs/round-001-semantic/revision_state.json \
  --outdir outputs/round-002
```

默认使用 Word 修订痕迹。若数字、年份、引用或 DOCX 部件发生未授权变化，候选稿会被隔离为 `论文修改候选稿-回归未通过.docx`，最终 `论文修改稿.docx` 回滚为原文件。

查看状态：

```bash
python3 -m thesis_revision_professor status outputs/round-002/revision_state.json
```

## 合法语料策略挖掘

先生成权限清单：

```bash
python3 -m thesis_revision_professor rights-template ./legal-corpus --out rights-manifest.json
```

逐文件填写 `allow_derived_strategy`、学科、学位、方法和质量依据后运行：

```bash
python3 -m thesis_revision_professor corpus ./legal-corpus \
  --rights-manifest rights-manifest.json \
  --out outputs/strategy-cards.md
```

未明确授权的文件不会进入分析。聚合产物不保存标题、作者、绝对路径或原文片段；样本量不足 `k=10` 时不会发布可泛化策略。

## v3 可信门禁

- 研究问题与研究目的不会因为没有句内引用而自动判为缺证据；
- 引用表与正文引用分区检查，引用存在不等于语义支持；
- `--discipline` 和 `--method` 会实际选择不同审查协议；
- Issue 使用稳定 fingerprint，支持 open、resolved、reopened、regressed 等状态；
- 修改仅命中稳定 locator，并保留原 DOCX 的媒体与包部件；
- 复杂 OOXML 段落拒绝自动修改；
- 未授权事实、数字和引用变化触发回滚。

## 验证

```bash
python3 tests/run_smoke.py
PYTHONPYCACHEPREFIX=/tmp/trp-pycache python3 -m py_compile scripts/*.py thesis_revision_professor/*.py
python3 scripts/release_gate.py
python3 -m pip wheel . --no-deps --no-build-isolation -w /tmp/trp-wheel
```

测试覆盖判断正确性、引用误报、学科路由、Word 部件保留、回归回滚、状态去重、语料权限和隔离 wheel 安装。

## 学术诚信与版权

- 只能处理你有权使用的论文、数据和文献；
- “公开可访问”不等于允许批量抓取、保存或再发布；
- 不在仓库中放置知网、万方、ProQuest 或其他受版权保护论文全文；
- 不复制语料论文措辞，不帮助规避查重；
- 不把本工具的输出冒充未经作者核验的研究事实。

## English summary

`thesis-revision-professor` is an evidence-bound hybrid review and controlled Word revision system for master's and doctoral theses. It combines deterministic integrity gates with Codex semantic review, creates a traceable claim-evidence graph, routes discipline/method protocols, preserves DOCX package parts, and rolls back unauthorized factual changes. It does not guarantee academic outcomes or bundle copyrighted thesis full text.
