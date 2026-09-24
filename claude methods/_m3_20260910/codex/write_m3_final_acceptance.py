"""Write evidence-bound acceptance documents after actual independent review.

Only creates new Codex-owned reports/receipts. No labels, opinions or data are
changed. Technical closure and the unmet research target are separate fields.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PHASE = HERE.parent
DOCS = ROOT / 'claude methods'


def read(p):
    return json.loads(p.read_bytes())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def link(label, p):
    return f'[{label}](<{p.as_posix()}>)'


def put(p, value):
    assert not p.exists(), p
    p.write_text(value, encoding='utf-8')


def main():
    expected = {
        'backend/app/research/m3_labels.py': 'e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393',
        'backend/app/research/m3_frozen_reader.py': '288594cf0acf977c5ede3f5dec6584134a879889793c4c3542d01b1d7f7ae5af',
        'backend/tests/test_m3_labels.py': '41eba60b21b507250f9a9a4f359fdc330232306c61b535f3d82db18ba9e45180',
        'backend/tests/test_m3_frozen_reader.py': '22e79001acc1e58febd7865fbf01facd927488c87fc1ed2cfbd6d7c287b608ce',
        'claude methods/THREE_YEAR_RESEARCH_EXECUTION_GOAL.md': 'f8b699e531ab4e98e7bccd17bc0c2850355ed0ea75e5038cfecaa216a6266164',
        'claude methods/M3_01_R3_CODEX_REVIEW_20260910.md': '871999df90a932b69e7ca85e74b92e668ce5a0f5f43d2f0bb5caa3b8791313ef',
        'claude methods/M3_02_CODEX_ACCEPTANCE_20260910.md': '4c1fcc2376c93c5ebf233b28b1d2f6608108eadadd8754ca30cb3e79124648dd',
    }
    local_expected = {
        'claude_03/artifact_manifest.json': '7670b0115569c7899cfd3c4457a9a6bcb74b6ae9342978cd1d36346eadc5f841',
        'policy_freeze.json': '925ae86f772908babef6bc6a08a1ace58c2db7a5e71c7f97af8ad52f2c7a891f',
        'codex/individual_review_bound_01/manifest.json': '82ffd165f955220228560a23e2f6b147d8f5c5fb6b1b437323762b04d3c6d6ba',
        'codex/case_library_01/manifest.json': '74e13a63ac057aae7b9a6c54df663e1c004392b7a3affaa377370aa812f93c28',
        'codex/normalized_claude_reviews_01/normalized.json': '17bcc3c47757898c6b92d5d4f5abe32f00c778d6ac6e7b2a9c390405d9d9f1a3',
        'codex/reader_chronology_source_review_02/result.json': 'a0a0e3013ba3f796385fd2a886d4ce4bf0e737edf376b3072ad015ccda7ca4a1',
        'codex/reader_episode_packet_review_03/result.json': 'b8d445a913bc5dac6386ad73696fc0084d84b7383e3005f22c5637c6edfbbde9',
        'codex/review_m3_03_input/receipt.json': '662273a4024b75c6f05222fe5bd49018bf2bcf4a330b03a3076ff77b8d2b87c1',
        'codex/m3_03_manual_delivery_judgment.json': '2be594d514342a08eb371e791112fb927a2a11476e9a83d721ef80dd5e5f95c1',
    }
    expected.update({str((PHASE / r).relative_to(ROOT)): h for r, h in local_expected.items()})
    for rel, digest in expected.items():
        assert sha(ROOT / rel) == digest, rel
    receipts = ['case_library_independent_verification_01.json', 'preservation_m3_final_01.json',
                'claude_review_validator_isolated_01/execution.json', 'review_summary_statistics_01.json']
    for rel in receipts:
        assert read(HERE / rel)['passed'] is True, rel
    preservation = read(HERE / receipts[1])
    assert preservation['existing_tracked_checked'] == 316
    assert len(preservation['production_positions']) == 16
    assert all(v['passed'] for v in preservation['production_positions'].values())
    counts = read(HERE / 'case_library_01/library_counts.json')
    comparison = read(HERE / 'case_library_01/review_comparison.json')
    assert len(comparison) == 32 and not any(x['dual_positive'] or x['agreement'] for x in comparison)
    assert counts['disputed'] == 32 and counts['qualified_reviewed_positive_episodes'] == 0
    assert counts['target']['met'] is False and counts['target']['training_eligible'] is False
    # Reuse the previously executed, still-pinned label checks; do not rerun
    # unchanged suites just to increase the reported test count.
    r3 = read(HERE / 'review_03_validation.json')
    for run in r3['executions']:
        assert sha(Path(run['receipt'])) == run['sha256'] and run['passed']
    assert sum(x['test_count'] for x in r3['executions']) == 137
    # Compare our pre-correction capture with Claude's retained draft, rather
    # than relying only on the latter's self-declared history.
    preview = HERE / 'serialization_preview_01'
    retained = PHASE / 'claude_03/execution/superseded_draft_01'
    draft_hashes = {sha(p) for p in retained.rglob('*') if p.is_file()}
    snapshot = read(preview / 'snapshot.json')
    for item in snapshot['files']:
        assert sha(preview / item['path']) == item['sha256']
        assert item['sha256'] in draft_hashes, item['path']
    assert len(snapshot['files']) == 42
    now = datetime.now(timezone.utc).isoformat()
    index_path = DOCS / 'M3_CASE_LIBRARY_INDEX_20260910.md'
    m303_path = DOCS / 'M3_03_CODEX_ACCEPTANCE_20260910.md'
    final_path = DOCS / 'M3_FINAL_ACCEPTANCE_20260910.md'
    label_names = {'positive': '正例意见', 'negative': '负例意见', 'ambiguous': '不确定'}
    index = '# M3 案例库索引\n\n'
    index += '本库用于回顾性研究复核。32 个匹配阶段全部完成两名实际 agent 的分别审阅，均保留分歧；双审正例 0，训练准入未通过。阶段标签是可观察价格代理，不是隐蔽资金行为的事实认定。\n\n'
    index += f'总验收：{link("M3 最终验收", final_path)}。账本统计：{link("library_counts.json", HERE / "case_library_01/library_counts.json")}。\n\n'
    index += '| 案例 | 股票 | 代表日 | Codex | Claude | 对照数 | 原始材料与审阅 |\n|---|---|---|---|---|---|---|\n'
    for x in comparison:
        cid = x['case_id']
        links = [link('截点材料', HERE / f'case_review_bundle_01/cases/{cid}.json'),
                 link('Codex', HERE / f'individual_review_bound_01/reviews/{cid}.json'),
                 link('Claude', PHASE / f'claude_03/reviews/{cid}.json'),
                 link('合并账本', HERE / f'case_library_01/reviewed_representatives/{cid}.json')]
        index += f'| {cid} | {x["symbol"]} | {x["date"]} | {label_names[x["codex_verdict"]]} | {label_names[x["claude_verdict"]]} | {x["control_count"]} | {" · ".join(links)} |\n'
    index += '\n对照共 127 个不同日期记录，涉及 37 只股票；同一日期记录最大复用 1 次，同一股票跨日最大复用 10 次。127 组双方实际评估另存，未把 admissible 布尔值转换为虚构的负例审核条目。\n\n'
    index += link('127 组对照评估', HERE / 'case_library_01/control_reviews.json') + '\n\n'
    index += '| 诊断 | 范围 | 材料 |\n|---|---|---|\n'
    kinds = ['拉升阶段','派发阶段','拉升失败','预热不足','代表日停牌','已知现金事件门控','入场信号与未验证执行','BJ 单日口径例外']
    for i, kind in enumerate(kinds, 1):
        cid = f'D{i:03}'
        index += f'| {cid} | {kind} | {link("截点材料", HERE / f"case_review_bundle_01/diagnostics/{cid}.json")} · {link("Codex", HERE / f"individual_review_bound_01/diagnostics/{cid}.json")} · {link("Claude", PHASE / f"claude_03/diagnostics/{cid}.json")} |\n'
    index += '\n8 个诊断不计入吸筹正例；未提供真实持仓与成交，因此止损、退出事件只有合成契约验证，不能宣称真实执行验收。\n'
    put(index_path, index)
    m303 = f'''# M3-03 实际逐案例审阅与账本：Codex 验收

日期：2026-09-10。**通过实际审阅交付、绑定、保全及保守合并的技术验收；正例证据目标未通过。** 此结论不改变冻结标签规则，不把两名 agent 的不同判断强行改成一致。

已实际观察原 Claude 会话 Message 77 的 ready_for_review、清单哈希、Idle、完成提示、空输入框与禁用 Send。交付清单 SHA-256 为 `7670b0115569c7899cfd3c4457a9a6bcb74b6ae9342978cd1d36346eadc5f841`。201 个产物与 58 个来源逐项核对、快照前后字节一致。执行身份来自原生窗口的真实执行观察及文件日志；Claude 自报 session UUID 只作关联标识，不冒充独立身份认证。

## 实际审阅与分歧

Codex 在读取 Claude 意见前封存 32 个阶段、127 个对照及 8 个诊断的逐项意见：31 正例、C012 不确定。Claude 对同一截点材料分别审阅，提交 0 正例、14 负例、18 不确定。两者均为 agent，不是人工双盲评审；有共享材料及事实纠错反馈，不声称统计独立。

Codex 的正例意见支持冻结的可观察吸筹代理条件；Claude 对下跌、反弹、均线位置和阈值余量提出更严格的证据判断。其“余量 <0.01 为脆弱”的标准属于审阅意见，未并入冻结策略。双方未争议内核算术。C012 零振幅与约 -5% 日跌幅只能提示可能封板，ST/交易所状态未知；没有强行改判。

合并后 **32 个争议阶段、0 个双审正例**。只有这 32 条代表记录追加双方实际原始审核条目；127 组对照评估、8 组诊断另存，不制造 Claude 未写过的原始负例条目，不把诊断支持转成正例。17,554 条核心记录的非账本字段全部保持原值，17,522 条原账本仍待审。`independently_reviewed=0` 是内核“已达一致”状态数，不代表没有发生两次实际审阅。

## 独立执行结果

| 检查 | 结果 |
|---|---|
| 冻结交付 | 201 产物、58 来源全部哈希通过，最终 manifest 稳定 |
| 原交付验证器隔离复跑 | 通过、0 问题；代码与输入不改，仅将唯一结果输出重定向到 Codex 新目录；0 SQLite/网络 |
| 独立标准化 | 32 原始审核条目、127 对照评估、8 诊断绑定通过；无程序生成的判断 |
| 内核合并与计数 | 32 条代表账本，0 双审正例，目标 false，训练 false |
| 不调用标签/计数内核的独立核验 | 全部 17,554 条原核心和序列外壳相等，32 组账本等于双方封存原条目；对照与诊断原文相等 |
| 原始草稿保全 | Codex 预先截取的 42 文件哈希全部可在 Claude 留存草稿中找到；29 份作者笔记历史快照亦被验证 |
| 最终旧数据保全 | 316 个原有跟踪文件、16 个生产文件位置及 M2 全部固定证据检查通过 |

冻结策略 SHA-256：`d436ba1402f9d0b53e1008c2a2bd50678a457c3e050561a59ded30dbbd21c025`。合并案例库清单：`74e13a63ac057aae7b9a6c54df663e1c004392b7a3affaa377370aa812f93c28`。

## 纠错与统计解释

六份事实反馈均在原任务中完成。C016 新低误述、C013 高点时点、C008/C009 成交量分母归因、封板状态、C018 对照价格、C027 余量、C031 未来走势、C032 收益区间与 D007 无持仓输入含义已修正到当前字段及 raw_review.notes；旧内容与原因保留。reviewed_at 明确为实际绑定时间，证据检查和作者修订时间另存，不冒称同时完成全部人工阅读。

独立复算严格 <0.01 的前缀共 15/32（位置 5、均线差 8、120 柱收益 2，三组互斥），不是早期草稿 20/32。负例叙述分组为 7 次上涨/反弹与 7 次破位/下跌。32 个匹配阶段的政策依赖组为 23；Claude 的代表日距离链 26 不是这一口径。127 个不同日期对照记录涉及 37 个股票，同日记录最大重用 1，股票跨日最大重用 10；最终合格正例专属对照数则为 0。

Claude 报告第 1 节把旧草稿称为“42 review files”存在非实质笔误：实际审核文件为 32+8=40，旧草稿总文件 45；Codex 先前快照的 42 是 40 审核文件加执行回执和序列化脚本。以已核验清单为准，未为此改写已封存交付或重派任务。Codex 快照程序首跑误按项目根解析交付相对路径，在任何输出前失败；按实际清单规范修正后完整通过，未修改 Claude 清单。

证据入口：{link('案例索引', index_path)}、{link('独立账本核验', HERE / 'case_library_independent_verification_01.json')}、{link('最终保全', HERE / 'preservation_m3_final_01.json')}、{link('交付人工审阅记录', HERE / 'm3_03_manual_delivery_judgment.json')}。

Claude next-stage instruction: M3-03 is accepted as an actual agent-review delivery for conservative retrospective reconciliation. Preserve all original opinions, corrections, drafts and frozen inputs. No further task is dispatched. Keep the session idle; do not tune the policy, manufacture consensus, expand the universe, collect data, train, or start M4 without a separate explicitly scoped instruction.
'''
    put(m303_path, m303)
    final = f'''# M3 最终技术验收与证据限制

日期：2026-09-10。**M3 标签、冻结读取、实际逐案审阅和案例库合并已完成技术验收；至少 50 个双审正例的研究目标未达成，训练准入不通过。** 本轮按原目标中“证据不足如实报告”的分支收口，不把工程完成写成样本达标。

固定开发总体已穷尽盘点：最多只有 32 个具备 3–5 个合格对照的阶段；实际两名 agent 审阅后 32 个均有分歧，双审正例为 **0/50**。继续使用同一冻结总体和规则重跑不能补足目标。未调整阈值、扩大总体、挪用留出期、伪造审阅或凑合成正例。

## 已完成的交付

| 阶段 | 实际结果 | 验收 |
|---|---|---|
| M3-01 标签规范与内核 | 候选/非候选、五类阶段、入场资格、止损/退出/不交易、市场状态及流动性；版本化截点、输入和审阅契约 | {link('M3-01 R3 验收', DOCS / 'M3_01_R3_CODEX_REVIEW_20260910.md')} |
| M3-02 冻结读取与完整盘点 | 50 股票、2 指数；2023-09-04 至 2025-03-31，378 交易日；17,554 决策记录 | {link('M3-02 验收', DOCS / 'M3_02_CODEX_ACCEPTANCE_20260910.md')} |
| M3-03 实际审阅与案例库 | 每名 agent 实际审阅 32 个阶段、127 个对照和 8 个诊断；保留原意见与争议 | {link('M3-03 验收', m303_path)} |

可直接查阅 {link('逐案例索引', index_path)}；每项链接到原始截点材料、双方原始意见及合并账本。

## 数量与研究准入

| 口径 | 数量 / 状态 |
|---|---|
| 开发区间潜在股票日期键 | 18,900 |
| 尚未上市、按声明排除 | 1,346 |
| 当日价格 / 当日停牌 / 未解释缺失 | 17,402 / 152 / 0 |
| 全部阶段 / 吸筹代理阶段 | 1,626 / 342 |
| 达到三个连续交易日前缀 | 225；另 117 未达到 |
| 前缀代表日非候选 | 85 |
| 代表日候选 | 140：108 对照不足，32 有 3–5 个合格对照 |
| 已匹配阶段的依赖组 / 股票数 | 23 / 18 |
| 全部匹配对照 | 127 个不同日期记录，37 只股票 |
| Codex 原始意见 | 31 正例、1 不确定 |
| Claude 原始意见 | 0 正例、14 负例、18 不确定 |
| 合并账本 | 32 争议、0 一致通过、0 双审正例 |
| 最终合格正例的依赖组 / 对照使用 | 0 / 0 |
| ≥50 正例目标 / 训练准入 | 未达成 / 禁用 |

意见分歧集中于冻结代理与较严格形态解释的差别；两者都不构成隐蔽资金行为的真值。当前没有双审同意的正例，不应把 Codex 的单方 31 个正例用于已达标监督训练。负例、不确定、失败阶段和质量诊断均保留，未强制二值化。

## 验证证据与可用范围

标签阶段已实际通过 105 项交付、24 项消费者边界、8 项独立数值检查；读取器实际通过 20 项交付及 8 项额外边界/材料延伸检查。最终模块与测试文件哈希未改变，因此复用这些已封存运行结果，未用重复运行夸大数量。

真实来源对账覆盖 27,900 条含预热价格与 200 条停牌证据；独立来源重建复算全部 17,554 条最终记录，0 差异；全部 225 组截点材料、完整同日对照池及排序均已复核。这些自动复算与实际逐案审阅分别记录。合并后又用不调用标签/计数内核的核验程序逐条确认原字段与双方原条目，检查通过。

材料来自 2026 年捕获的回顾性历史数据，**strict_pit=false、training_eligible=false、review_only=true**。截点算法不看未来，不等于已证明历史时点真实可得。没有消费验证期或最终留出期价格。历史 ST、流通股本、换手、名称未知；公司行动只有两只股票的部分现金事件，其余覆盖未知。暖启动不足、上市证据等级和 BJ 单日例外继续限制使用。50 股票的日期覆盖不等于全市场覆盖。

止损、退出等有合成契约证明；本轮没有真实持仓、参考成交与订单证据，不能声称已实测真实退出或撮合。入场信号仍是未验证执行。种子三维通信不在固定总体，本轮未补造其案例。

生产 SQLite 没有连接或修改，没有替换旧数据/标签/知识、采集新行情、登录账户、资金或交易操作。最终 316 个原有跟踪文件、16 个生产文件位置及 M2 冻结证据均保全；原有工作区未提交变更保持原样。生成证据通过本地 Git exclude 排除，未暂存、提交或推送。

## 收口状态

机器回执明确使用 `M3_technical_complete=true`、`research_target_met=false`、`M3_complete=false`（严格的全部研究准入意义）、`training_eligible=false`。本轮已完成有限总体的研究材料交付与不足举证，状态为 `technically_closed_evidence_target_not_met`；没有隐含扩大授权，也不会自动重派同一批材料。

本验收与收口回执落盘后，结束原有 15 分钟 M3 巡检；实际暂停结果保存于独立运行回执。Claude 已完成并处于 Idle。M4 未启动。若后续继续，应先明确是修订有版本的研究假设、补充来源证据，还是独立启动 M4 的合成引擎验证；不能沿用本次成果宣称历史预测或收益有效。

收口证据：{link('completion.json', HERE / 'final_acceptance_01/completion.json')}；全链条哈希：{link('evidence.json', HERE / 'final_acceptance_01/evidence.json')}；巡检运行状态：{link('automation_closeout.json', HERE / 'final_acceptance_01/automation_closeout.json')}。

Claude next-stage instruction: The bounded M3 implementation and evidence review are technically closed, while the 50-positive research target and training gate remain unmet. Retain all frozen versions and dissent. No new task is dispatched. Remain idle; do not relabel, recapture, train, or start M4 without a separate explicitly scoped instruction from Codex under user authorization.
'''
    put(final_path, final)
    out = HERE / 'final_acceptance_01'
    assert not out.exists()
    out.mkdir()
    evidence_paths = [ROOT / rel for rel in expected]
    evidence_paths += [HERE / rel for rel in receipts]
    evidence_paths += [HERE / 'review_03_validation.json', HERE / 'm3_03_completion_observed.json',
                       HERE / 'reader_delivery_tests_isolated_01/execution.json',
                       HERE / 'reader_working_boundary_tests_02/execution.json',
                       HERE / 'reader_working_packet_extension_tests_01/execution.json',
                       HERE / 'case_library_01/library_counts.json', HERE / 'case_library_01/execution.json',
                       final_path, m303_path, index_path, Path(__file__)]
    evidence = {'verified_at_utc': now, 'files': {str(p.relative_to(ROOT)): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in evidence_paths},
                'original_claude_pre_correction_files_preserved': 42, 'old_evidence_and_production_preserved': True,
                'script_does_not_generate_review_judgments': True, 'sqlite_connections': 0, 'network_requests': 0}
    put(out / 'evidence.json', json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    completion = {'schema': 'm3.technical_closure.v1', 'closed_at_utc': now,
                  'status': 'technically_closed_evidence_target_not_met', 'M3_technical_complete': True,
                  'M3_complete': False, 'research_target_met': False, 'target_positive_episodes': 50,
                  'dual_reviewed_positive_episodes': 0, 'disputed_episodes': 32,
                  'complete_semantics': 'Bounded implementation, actual reviews and evidence-limitation reporting completed; original quantitative research acceptance remains unmet.',
                  'actual_reviewers': 2, 'reviewer_kind': 'agent', 'case_reviews_per_agent': 32,
                  'control_assessments_per_agent': 127, 'diagnostics_per_agent': 8,
                  'training_eligible': False, 'strict_pit': False, 'review_only': True,
                  'live_trading_enabled': False, 'M4_started': False, 'frozen_inputs_preserved': True,
                  'all_required_bounded_checks_passed': True, 'evidence_sha256': sha(out / 'evidence.json'),
                  'report': str(final_path.relative_to(ROOT)), 'report_sha256': sha(final_path),
                  'case_library_manifest_sha256': sha(HERE / 'case_library_01/manifest.json'),
                  'automation_exit_authorized_after_this_receipt': True}
    put(out / 'completion.json', json.dumps(completion, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'written': [str(x) for x in [index_path, m303_path, final_path, out / 'completion.json']],
                      'completion_sha256': sha(out / 'completion.json'), 'report_sha256': sha(final_path),
                      'technical_complete': True, 'target_met': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
