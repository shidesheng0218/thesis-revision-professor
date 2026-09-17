# thesis-revision-professor

中文 | [English summary](#english-summary)

一个面向硕士、博士论文的开源混合审稿与 Word 受控修改系统。v4 在 v3 基础上增加证据账本、跨章节一致性、五轮深度 Loop、Word 批注、规范 profile 和答辩问题包。

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

### 五轮深度模式（推荐）

```bash
python3 -m thesis_revision_professor evidence-template ./evidence --out ./evidence/evidence_manifest.json
python3 -m thesis_revision_professor deep-review thesis.docx \
  --level master --discipline education --method qualitative \
  --profile profiles/generic-cn-master.json \
  --evidence-dir ./evidence \
  --outdir outputs/round-001
```

这一步生成 `claim_evidence_ledger.json`、`consistency_matrix.json`、`loop_trace.json` 和 `semantic_review_request.json`。在 Codex 中按语义审查协议生成 `semantic_findings.json`，然后合并：

```bash
python3 -m thesis_revision_professor merge-semantic \
  --review outputs/round-001 \
  --findings semantic_findings.json \
  --outdir outputs/round-002
```

作者确认修改计划后，生成带修订痕迹和批注的 Word：

```bash
python3 -m thesis_revision_professor revise thesis.docx \
  --plan outputs/round-002/revision_plan.json \
  --state outputs/round-002/revision_state.json \
  --tracked --comments \
  --outdir outputs/round-003
```

生成答辩准备包：

```bash
python3 -m thesis_revision_professor defense \
  --review outputs/round-003 \
  --outdir outputs/defense
```

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

## v4 可信增强

- `claim_evidence_ledger.json` 统一登记论文和作者授权材料中的证据；未核验材料不会成为自动改写依据。
- `consistency_matrix.json` 检查摘要、方法、结果、结论、表格和附录之间的事实关系。
- `loop_trace.json` 固定记录五轮深度 Loop；达到上限仍未收敛时标记人工复核。
- `--comments` 为人工判断项写入 Word 批注；批注失败时保留外部清单，不静默丢失。
- `profiles/` 只提供通用安全 profile；学校规范应由用户提供并核对版本。

## 合规披露(AI 辅助内容清单)

国内部分高校已要求学位论文附《AI 辅助内容清单》。本工具可从任意轮目录的机器产物直接生成：

```bash
python3 -m thesis_revision_professor disclosure --review outputs/round-001 --outdir outputs/disclosure
```

输出 `AI辅助内容清单.md` / `.docx` / `.json`，汇总每轮审查阶段、参与角色、每条修改计划的执行方式与证据来源、作者确认状态、被拒收的语义 finding 与产物完整性；缺失的产物如实注明"缺失"，不补造内容。

## 外部意见导入闭环(可选)

盲审或导师意见可导入受控修改流程,形成"评审意见→受控修改→对照表"闭环:

```bash
python3 -m thesis_revision_professor import-feedback 盲审意见.txt --review outputs/round-001 --outdir outputs/round-002
python3 -m thesis_revision_professor revise thesis.docx --plan outputs/round-002/revision_plan.json --outdir outputs/round-002-applied
```

意见按启发式规则切分(编号/"第X条"优先,切不开整段一条),可定位项进入标记路径,无法定位的项只进人工队列;`revise` 检测到 `feedback_mapping.json` 时自动生成《意见—修改对照表.docx》(状态随 patch 结果更新,不采纳理由由作者填写)。规则见 `references/feedback-protocol.md`。

## 自动化语义审查(可选)

`semantic_findings.json` 除手工编写外，也可通过 OpenAI 兼容 API 自动生成：

```bash
export THESIS_REVIEW_API_KEY=...
export THESIS_REVIEW_MODEL=gpt-4o-mini   # 可选
export THESIS_REVIEW_API_BASE=https://api.openai.com/v1  # 可选
python3 -m thesis_revision_professor llm-review --request outputs/round-001/semantic_review_request.json --out semantic_findings.json
```

只使用标准库 `urllib`，不引入任何第三方依赖；未设置 `THESIS_REVIEW_API_KEY` 时清晰报错退出。输出经过与手工载荷相同的字段校验，被拒 finding 连同原因写入 `rejected_findings`。三点边界：

- 不替代人工判断：产出仍需按 `references/semantic-review-protocol.md` 复核后 merged；
- 不绕过任何门禁：llm-review 只是 `semantic_findings.json` 的另一种生产方式，merge 与后续 converge 门禁完全一致；
- 不联网时整条链路仍可手动跑：手工产出 `semantic_findings.json` 后 `merge-semantic` 行为不变。

## 验证

```bash
python3 tests/run_smoke.py
PYTHONPYCACHEPREFIX=/tmp/trp-pycache python3 -m py_compile scripts/*.py thesis_revision_professor/*.py
python3 scripts/release_gate.py
python3 -m pip wheel . --no-deps --no-build-isolation -w /tmp/trp-wheel
```

测试覆盖判断正确性、引用误报、学科路由、Word 部件保留、回归回滚、状态去重、语料权限和隔离 wheel 安装。

## 与改写/降重类工具的区别

市面上多数 AI 论文工具走"自由改写"路线:降重、降 AIGC、整段生成,不区分事实与表达,也不会告诉你改了什么。本工具的设计取向相反:

- **事实锁定**:数字、年份、样本量、引用、结论的改动一律视为需授权变更,未授权即回滚;证据不足的实质修改只标记 `[需作者确认：…]`,绝不代编;
- **可审计**:每条意见绑定规则、定位与证据来源,修改全程留痕(track changes + 批注 + `revision_plan.json`/`revision_state.json`),并可直接生成高校要求的《AI 辅助内容清单》;
- **本地运行**:论文不离开你的机器,适合未发表成果;
- **立场声明**:不提供、也不协助规避查重或 AIGC 检测的功能。

## 学术诚信与版权

- 只能处理你有权使用的论文、数据和文献；
- “公开可访问”不等于允许批量抓取、保存或再发布；
- 不在仓库中放置知网、万方、ProQuest 或其他受版权保护论文全文；
- 不复制语料论文措辞，不帮助规避查重；
- 不把本工具的输出冒充未经作者核验的研究事实。

## English summary

`thesis-revision-professor` is an evidence-bound hybrid review and controlled Word revision system for master's and doctoral theses. It combines deterministic integrity gates with Codex semantic review, creates a traceable claim-evidence graph, routes discipline/method protocols, preserves DOCX package parts, and rolls back unauthorized factual changes. It does not guarantee academic outcomes or bundle copyrighted thesis full text.
