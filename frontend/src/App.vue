<template>
  <main class="shell">
    <section class="topbar">
      <div>
        <p class="eyebrow">Local Simulation Mode</p>
        <h1>A股AI交易驾驶舱</h1>
        <p class="status">{{ statusText }}</p>
      </div>
      <div class="top-actions">
        <button data-testid="auto-discovery-button" @click="runAutoDiscovery" :disabled="discoveryLoading">
          {{ discoveryLoading ? "发现中" : "自动发现" }}
        </button>
        <button data-testid="local-scan-button" @click="runScan" :disabled="loading">{{ loading ? "扫描中" : "本地扫描" }}</button>
        <button data-testid="automation-run-button" @click="runAutomation" :disabled="automationLoading">
          {{ automationLoading ? "自动化中" : "运行自动化" }}
        </button>
        <button data-testid="monitoring-run-button" @click="runMonitoring" :disabled="monitoringLoading">
          {{ monitoringLoading ? "监控中" : "运行监控" }}
        </button>
        <button data-testid="phase-replay-button" @click="runPhaseReplay" :disabled="phaseReplayLoading">
          {{ phaseReplayLoading ? "回放中" : "阶段回放" }}
        </button>
        <button data-testid="phase-match-button" @click="runPhaseMatch" :disabled="phaseMatchLoading">
          {{ phaseMatchLoading ? "匹配中" : "阶段匹配" }}
        </button>
        <button data-testid="potential-search-button" @click="runPotentialSearch" :disabled="potentialSearchLoading">
          {{ potentialSearchLoading ? "搜索中" : "潜力搜索" }}
        </button>
        <button data-testid="live-trading-disabled-button" class="disabled-live" disabled>实盘禁用</button>
      </div>
    </section>

    <section class="grid">
<article class="panel wide">
        <h2>Price Readiness</h2>
        <p class="review-only-banner">⚠ This data is for simulation and system readiness only. Do not use as investment advice.</p>
        <div class="metrics">
          <span>就绪 (Ready) {{ priceReadinessSummary?.ready ?? 0 }}</span>
          <span>无价格 (Missing) {{ priceReadinessSummary?.missing_price ?? 0 }}</span>
          <span>价格陈旧 (Stale) {{ priceReadinessSummary?.stale_price ?? 0 }}</span>
          <span>历史不足 {{ priceReadinessSummary?.insufficient_history ?? 0 }}</span>
          <span>错误 (Error) {{ priceReadinessSummary?.error ?? 0 }}</span>
        </div>
        <div class="actions">
          <button data-testid="run-price-readiness-button" @click="runPriceReadiness" :disabled="priceReadinessLoading">
            {{ priceReadinessLoading ? '检查中' : '运行价格就绪检查' }}
          </button>
          <button data-testid="run-daily-bar-refresh-button" @click="runDailyBarRefresh" :disabled="dailyBarRefreshLoading">
            {{ dailyBarRefreshLoading ? '刷新中' : '刷新日线缓存' }}
          </button>
        </div>

        <h3 style="margin-top: 16px;">Daily Bar Coverage</h3>
        <div v-if="dailyBarCoverage.length" class="score-list" style="margin-bottom: 24px;">
          <div v-for="cov in dailyBarCoverage" :key="cov.symbol" class="score-item">
            <strong>{{ cov.symbol }} / {{ cov.quality_status }}</strong>
            <span>数量: {{ cov.cached_bar_count }} / 范围: {{ cov.first_trade_date }} 至 {{ cov.last_trade_date }}</span>
            <small>数据源: {{ cov.source }}</small>
          </div>
        </div>
        <p v-else style="margin-bottom: 24px;">暂无日线缓存覆盖率数据。点击上方按钮进行刷新。</p>

        <h3 style="margin-top: 16px;">Readiness Reports</h3>
        <div v-if="priceReadinessReports.length" class="score-list">
          <div v-for="report in priceReadinessReports" :key="report.symbol" class="score-item">
            <strong>{{ report.symbol }} {{ report.name }} / {{ report.coverage_status }}</strong>
            <span>最新价格: {{ report.latest_price ?? 'N/A' }} / 数据源: {{ report.source }}</span>
            <small>更新时间: {{ report.latest_price_at ?? 'N/A' }} / 历史数据点: {{ report.history_points }}</small>
            <small v-if="report.error_message">⚠ {{ report.error_message }}</small>
          </div>
        </div>
        <p v-else>暂无价格就绪报告。点击上方按钮进行检查。</p>
      </article>
<article class="panel wide">
        <h2>V4.0 高时效数据与事件驱动</h2>
        <p class="review-only-banner">只做秒级监控、提醒、模拟和 replay；不连接券商，不点击交易软件，不产生实盘订单。</p>
        <div class="actions">
          <button data-testid="refresh-realtime-button" @click="refreshRealtimeEvents" :disabled="realtimeLoading">
            {{ realtimeLoading ? "刷新中" : "刷新实时事件" }}
          </button>
          <button data-testid="sync-realtime-monitoring-button" @click="syncRealtimeMonitoring" :disabled="realtimeLoading">
            同步监控提醒
          </button>
          <button data-testid="run-realtime-cycle-button" @click="runRealtimeCycle" :disabled="realtimeLoading">
            运行实时闭环
          </button>
          <button data-testid="run-realtime-replay-button" @click="runRealtimeReplay" :disabled="realtimeLoading">
            运行信号 Replay
          </button>
        </div>
        <div class="metrics">
          <span>Provider {{ realtimeCapabilities?.active_provider ?? "disabled" }}</span>
          <span>状态 {{ realtimeCapabilities?.provider_status ?? "未加载" }}</span>
          <span>事件 {{ realtimeEvents.length }}</span>
          <span>提醒 {{ realtimeMonitoringSync?.created_alert_count ?? 0 }}</span>
          <span>闭环 {{ realtimeCycleResult?.status ?? "未运行" }}</span>
          <span>实盘 {{ realtimeCapabilities?.live_trading_enabled ? "开启" : "关闭" }}</span>
        </div>
        <div v-if="realtimeRefreshResult || realtimeMonitoringSync || realtimeCycleResult" class="score-list">
          <div v-if="realtimeRefreshResult" class="score-item">
            <strong>Refresh / {{ realtimeRefreshResult.status }}</strong>
            <span>写入 {{ realtimeRefreshResult.refreshed_count }} / 失败 {{ realtimeRefreshResult.failed_count }} / 请求 {{ realtimeRefreshResult.requested_count }}</span>
            <small>fallback {{ realtimeRefreshResult.fallback_required ? "required" : "not required" }} / simulation-only</small>
          </div>
          <div v-if="realtimeMonitoringSync" class="score-item">
            <strong>Monitoring Sync / {{ realtimeMonitoringSync.status }}</strong>
            <span>事件 {{ realtimeMonitoringSync.created_event_count }} / 提醒 {{ realtimeMonitoringSync.created_alert_count }} / 去重 {{ realtimeMonitoringSync.skipped_duplicate_count }}</span>
            <small>review-only / live trading disabled</small>
          </div>
          <div v-if="realtimeCycleResult" class="score-item">
            <strong>Realtime Cycle / {{ realtimeCycleResult.status }}</strong>
            <span>刷新 {{ realtimeCycleResult.summary.refreshed_count }} / 失败 {{ realtimeCycleResult.summary.refresh_failed_count }} / Replay {{ realtimeCycleResult.summary.replay_event_count }}</span>
            <small>提醒 {{ realtimeCycleResult.summary.created_alert_count }} / fallback {{ realtimeCycleResult.summary.fallback_required ? "required" : "not required" }}</small>
          </div>
        </div>
        <div v-if="realtimeHealth.length" class="score-list">
          <div v-for="item in realtimeHealth.slice(0, 4)" :key="item.provider" class="score-item">
            <strong>{{ item.provider }} / {{ item.status }}</strong>
            <span>配置 {{ item.configured ? "已配置" : "未配置" }} / 质量 {{ item.quality_status }}</span>
            <small>延迟 {{ item.latency_ms ?? "N/A" }} ms / {{ item.last_error ?? "暂无错误" }}</small>
          </div>
        </div>
        <div v-if="realtimeSnapshot?.event" class="score-list">
          <div class="score-item">
            <strong>{{ realtimeSnapshot.event.symbol }} 最新事件 / {{ realtimeSnapshot.status }}</strong>
            <span>价格 {{ realtimeSnapshot.event.price }} / 来源 {{ realtimeSnapshot.event.source }}</span>
            <small>延迟 {{ realtimeSnapshot.event.latency_ms?.toFixed?.(0) ?? realtimeSnapshot.event.latency_ms ?? "N/A" }} ms / 质量 {{ realtimeSnapshot.event.quality_status }}</small>
          </div>
        </div>
        <p v-else>暂无实时事件缓存。外部源未配置时系统保持 disabled/needs_config，不伪装为实时行情。</p>
        <div v-if="realtimeEvents.length" class="score-list">
          <div v-for="event in realtimeEvents.slice(0, 5)" :key="event.id" class="score-item">
            <strong>{{ event.symbol }} / {{ event.quality_status }}</strong>
            <span>{{ event.price }} / {{ event.source }}</span>
            <small>{{ event.event_ts }} / dedupe {{ event.dedupe_key }}</small>
          </div>
        </div>
        <div v-if="realtimeReplay" class="score-list">
          <div class="score-item">
            <strong>Replay / {{ realtimeReplay.status }}</strong>
            <span>事件 {{ realtimeReplay.event_count }} / 标的 {{ realtimeReplay.summary.symbol_count }} / 信号 {{ realtimeReplay.signals.length }}</span>
            <small>延迟均值 {{ realtimeReplay.summary.latency_ms.avg ?? "N/A" }} ms / simulation-only</small>
          </div>
          <div v-for="signal in realtimeReplay.signals.slice(0, 5)" :key="`${signal.symbol}-${signal.event_ts}-${signal.signal_type}`" class="score-item">
            <strong>{{ signal.symbol }} / {{ signal.signal_type }}</strong>
            <span>强度 {{ signal.strength }} / 质量 {{ signal.quality_status }}</span>
            <small>{{ signal.event_ts }} / {{ signal.reason }}</small>
          </div>
        </div>
      </article>
<article class="panel wide">
        <h2>V2.0 可信度证据面板</h2>
        <p class="review-only-banner">所有内容仅用于历史回测、模拟风控、告警复核和 AI 参数提案审查，不连接券商，不产生实盘订单。</p>
        <div class="actions">
          <button @click="runBacktest" :disabled="v15Loading">{{ v15Loading ? "运行中" : "运行回测" }}</button>
          <button @click="refreshMarketRegime" :disabled="v15Loading">刷新大盘环境</button>
          <button @click="runAiReview" :disabled="v15Loading">生成AI提案</button>
        </div>
        <div class="metrics">
          <span>大盘 {{ marketRegime?.regime ?? "未加载" }}</span>
          <span>组合姿态 {{ portfolioRisk?.posture ?? "未加载" }}</span>
          <span>回测数 {{ backtestRuns.length }}</span>
          <span>AI提案 {{ aiProposals.length }}</span>
        </div>
        <div v-if="backtestRuns.length" class="score-list">
          <div v-for="run in backtestRuns.slice(0, 3)" :key="run.id" class="score-item">
            <strong>回测 #{{ run.id }} / {{ run.status }}</strong>
            <span>收益 {{ ((run.metrics?.total_return ?? 0) * 100).toFixed(2) }}% / 回撤 {{ ((run.metrics?.max_drawdown ?? 0) * 100).toFixed(2) }}%</span>
            <small>成交 {{ run.metrics?.trade_count ?? 0 }} / 平仓 {{ run.metrics?.closed_trade_count ?? 0 }} / 期望 {{ (run.metrics?.expectancy ?? 0).toFixed(2) }}</small>
            <small>基准 {{ run.benchmark?.symbol ?? run.benchmark_symbol ?? "SH000300" }} / 超额 {{ ((run.metrics?.excess_return ?? 0) * 100).toFixed(2) }}%</small>
          </div>
        </div>
        <div v-if="backtestDetail" class="score-list">
          <div class="score-item">
            <strong>详情 #{{ backtestDetail.run.id }} / {{ backtestDetail.benchmark?.status ?? "benchmark_unknown" }}</strong>
            <span>权益点 {{ backtestDetail.daily_equity.length }} / 执行警告 {{ backtestDetail.execution_warnings.length }}</span>
            <small>{{ backtestDetail.execution_warnings.slice(0, 3).join("；") || "暂无执行警告" }}</small>
          </div>
          <div v-for="trade in backtestDetail.closed_trades.slice(0, 5)" :key="trade.id" class="score-item">
            <strong>{{ trade.symbol }} 平仓 / {{ trade.exit_reason }}</strong>
            <span>收益 {{ trade.realized_pnl.toFixed(2) }} / {{ (trade.realized_pnl_pct * 100).toFixed(2) }}%</span>
            <small>{{ trade.entry_date }} → {{ trade.exit_date }} / {{ trade.holding_days }} 天</small>
          </div>
        </div>
        <div v-if="portfolioRisk" class="score-list">
          <div v-for="gate in portfolioRisk.gates" :key="gate.name" class="score-item">
            <strong>{{ gate.name }} / {{ gate.status }}</strong>
            <span>当前 {{ gate.value }} / 限制 {{ gate.limit }}</span>
            <small>{{ gate.reason }}</small>
          </div>
        </div>
        <div v-if="monitoringLifecycle?.items?.length" class="score-list">
          <div v-for="item in monitoringLifecycle.items.slice(0, 5)" :key="item.alert_id" class="score-item">
            <strong>告警 #{{ item.alert_id }} {{ item.symbol }} / {{ item.state }}</strong>
            <span>{{ item.alert_type }} / {{ item.severity }}</span>
            <div class="actions" v-if="item.state === 'open'">
              <button @click="acknowledgeAlert(item.alert_id)">确认</button>
              <button @click="actionAlert(item.alert_id, 'add_to_review')">加入复核</button>
            </div>
          </div>
        </div>
        <div v-if="aiProposals.length" class="score-list">
          <div v-for="proposal in aiProposals.slice(0, 5)" :key="proposal.id" class="score-item">
            <strong>AI提案 #{{ proposal.id }} / {{ proposal.status }}</strong>
            <span>样本 {{ proposal.trades_analyzed }} / 安全拦截 {{ proposal.safety_blocks?.length ?? 0 }}</span>
            <small>验证 {{ proposal.validation?.status ?? "未验证" }}</small>
            <small v-if="proposal.validation?.out_of_sample">样本外 {{ proposal.validation.out_of_sample?.period?.start }} → {{ proposal.validation.out_of_sample?.period?.end }}</small>
            <div class="actions">
              <button @click="validateAiProposal(proposal.id)">验证</button>
              <button class="disabled-live" @click="rejectAiProposal(proposal.id)">拒绝</button>
            </div>
          </div>
        </div>
      </article>
<article class="panel wide">
        <h2>V2.5 交易经验记忆库</h2>
        <p class="review-only-banner">记忆库只汇总候选生命周期、监控告警、模拟成交、可信回测和 AI 提案审计；保持 review-only，不产生实盘动作。</p>
        <div class="actions">
          <button data-testid="run-experience-review-button" @click="runExperienceReview" :disabled="experienceLoading">
            {{ experienceLoading ? "复盘中" : "生成每日经验复盘" }}
          </button>
          <button @click="loadExperienceMemory" :disabled="experienceLoading">刷新记忆库</button>
        </div>
        <div class="metrics">
          <span>复盘 {{ experienceSummary?.review_count ?? 0 }}</span>
          <span>策略快照 {{ experienceSummary?.strategy_snapshot_count ?? 0 }}</span>
          <span>代码演进 {{ experienceSummary?.code_evolution_count ?? 0 }}</span>
          <span>实盘 {{ experienceSummary?.live_trading_enabled ? "开启" : "关闭" }}</span>
        </div>
        <div v-if="experienceEventCounts.length" class="lifecycle">
          <span v-for="item in experienceEventCounts.slice(0, 8)" :key="item.category">
            {{ item.category }} {{ item.count }}
          </span>
        </div>
        <div v-if="experienceReviews.length" class="score-list">
          <div v-for="review in experienceReviews.slice(0, 3)" :key="review.id" class="score-item">
            <strong>{{ review.period_start }} / {{ review.title }}</strong>
            <span>
              回测平仓 {{ review.summary?.backtest_metrics?.closed_trade_count ?? 0 }} /
              风控 {{ review.summary?.portfolio_risk?.posture ?? "unknown" }}
            </span>
            <small>{{ (review.next_actions ?? []).slice(0, 2).join("；") || "暂无下一步动作" }}</small>
          </div>
        </div>
        <div v-if="experienceStrategyPerformance.length" class="score-list">
          <div v-for="snapshot in experienceStrategyPerformance.slice(0, 3)" :key="snapshot.id" class="score-item">
            <strong>{{ snapshot.strategy_name }} / {{ snapshot.period_start }} → {{ snapshot.period_end }}</strong>
            <span>
              收益 {{ ((snapshot.metrics?.total_return ?? 0) * 100).toFixed(2) }}% /
              回撤 {{ ((snapshot.metrics?.max_drawdown ?? 0) * 100).toFixed(2) }}%
            </span>
            <small>benchmark {{ snapshot.metrics?.benchmark?.symbol ?? "unknown" }} / posture {{ snapshot.metrics?.portfolio_posture ?? "unknown" }}</small>
          </div>
        </div>
        <div v-if="experienceEvents.length" class="score-list">
          <div v-for="event in experienceEvents.slice(0, 5)" :key="event.id" class="score-item">
            <strong>{{ event.category }} / {{ event.event_type }}</strong>
            <span>{{ event.symbol ?? "system" }} {{ event.name ?? "" }} / {{ event.outcome_label ?? "unknown" }}</span>
            <small>{{ event.event_date ?? event.created_at }}</small>
          </div>
        </div>
        <div v-if="experienceCodeEvolution.length" class="score-list">
          <div v-for="record in experienceCodeEvolution.slice(0, 3)" :key="record.id" class="score-item">
            <strong>{{ record.record_type }} / {{ record.status }}</strong>
            <span>{{ record.title }}</span>
            <small>{{ record.created_at }}</small>
          </div>
        </div>
      </article>
<article class="panel wide">
        <h2>V3.0 Codex代码进化审查</h2>
        <p class="review-only-banner">Codex 只能基于复盘证据生成审查建议和验证记录；不生成可自动应用的 patch，不创建实盘接口，不修改交易权限。</p>
        <div class="actions">
          <button data-testid="generate-code-evolution-button" @click="generateCodeEvolutionReviews" :disabled="codeEvolutionLoading">
            {{ codeEvolutionLoading ? "生成中" : "生成代码进化建议" }}
          </button>
          <button data-testid="refresh-code-evolution-button" @click="loadExperienceMemory" :disabled="codeEvolutionLoading">
            刷新验证结果
          </button>
        </div>
        <div class="metrics">
          <span>总数 {{ experienceCodeEvolution.length }}</span>
          <span>待验证 {{ codeEvolutionStatusCount.pending_validation + codeEvolutionStatusCount.draft }}</span>
          <span>验证通过 {{ codeEvolutionStatusCount.validation_passed }}</span>
          <span>已接受 {{ codeEvolutionStatusCount.accepted }}</span>
        </div>
        <div class="v35-model-review">
          <div class="actions">
            <button data-testid="refresh-ai-model-audit-button" @click="loadAIModelAuditLogs" :disabled="aiModelLoading">
              刷新审计日志
            </button>
          </div>
          <div class="metrics">
            <span>V3.5 Provider {{ aiModelCapabilities?.provider ?? "mock_local_rule" }}</span>
            <span>允许输出 {{ aiModelCapabilities?.allowed_outputs?.length ?? 4 }}</span>
            <span>审计 {{ aiModelAuditLogs.length }}</span>
            <span>实盘 {{ aiModelCapabilities?.live_trading_enabled ? "开启" : "关闭" }}</span>
          </div>
        </div>
        <div v-if="experienceCodeEvolution.length" class="score-list">
          <div v-for="record in experienceCodeEvolution.slice(0, 8)" :key="record.id" :class="['score-item', codeEvolutionClass(record)]">
            <strong>#{{ record.id }} {{ record.record_type }} / {{ record.status }}</strong>
            <span>{{ record.title }}</span>
            <small>风险 {{ record.rationale?.severity ?? "unknown" }} / 验证 {{ record.validation?.status ?? "not_run" }}</small>
            <small>{{ (record.plan?.actions ?? []).slice(0, 2).join("；") }}</small>
            <template v-if="modelReview(record)">
              <small>AI解释 {{ modelReviewSummary(record) }}</small>
              <small>归因 {{ modelReviewTags(record).join(" / ") || "none" }} / 相似案例 {{ modelReviewSimilarCount(record) }}</small>
              <small>安全拦截 {{ modelReviewSafetyBlocks(record).length }}</small>
            </template>
            <small v-else>AI解释 未生成</small>
            <div class="actions">
              <button @click="explainCodeEvolutionWithModel(record.id)" :disabled="aiModelLoading || codeEvolutionLoading">
                生成AI解释
              </button>
              <button @click="approveCodeEvolution(record.id)" :disabled="record.status !== 'validation_passed' || codeEvolutionLoading">
                接受
              </button>
              <button class="disabled-live" @click="rejectCodeEvolution(record.id)" :disabled="codeEvolutionLoading">
                拒绝
              </button>
            </div>
          </div>
        </div>
        <div v-if="aiModelAuditLogs.length" class="score-list">
          <div v-for="log in aiModelAuditLogs.slice(0, 4)" :key="log.id" class="score-item">
            <strong>模型审计 #{{ log.id }} / {{ log.operation }}</strong>
            <span>{{ log.provider }} / safety {{ log.safety?.safety_blocks_applied?.length ?? 0 }}</span>
            <small>{{ log.created_at }}</small>
          </div>
        </div>
        <p v-if="!experienceCodeEvolution.length">暂无代码进化建议。先生成每日经验复盘，再生成审查建议。</p>
      </article>
<article class="panel">
        <h2>候选池</h2>
        <div class="metrics">
          <span>强候选 {{ latestScan?.strong_count ?? 0 }}</span>
          <span>观察 {{ latestScan?.watch_count ?? 0 }}</span>
          <span>剔除 {{ latestScan?.rejected_count ?? 0 }}</span>
          <span>自动发现 {{ discovery?.discovered_count ?? automation?.summary?.auto_discovery?.discovered_count ?? 0 }}</span>
          <span>涨停优先 {{ discovery?.limit_up_count ?? automation?.summary?.auto_discovery?.limit_up_count ?? 0 }}</span>
        </div>
        <div class="lifecycle">
          <span>待复核 {{ lifecycleSummary?.state_counts.pending_review ?? 0 }}</span>
          <span>重点观察 {{ lifecycleSummary?.state_counts.focus_watch ?? 0 }}</span>
          <span>阶段风控 {{ lifecycleSummary?.state_counts.phase_guarded ?? 0 }}</span>
          <span>淘汰 {{ lifecycleSummary?.state_counts.rejected ?? 0 }}</span>
        </div>
        <div v-for="item in topCandidates" :key="`${item.tier}-${item.symbol}`" :class="['tier', item.tier]">
          <strong>{{ item.symbol }} {{ item.name }}</strong>
          <span>{{ item.rating || "未评级" }} / {{ item.risk_level || "无风险标记" }}</span>
          <small>{{ item.reasons?.join("；") }}</small>
        </div>
      </article>
<article class="panel wide">
        <h2>盘后潜力搜索</h2>
        <div v-if="potentialSearch" class="metrics">
          <span>状态 {{ potentialSearch.status }}</span>
          <span>扫描 {{ potentialSearch.total_scanned }}</span>
          <span>入库 {{ potentialSearch.stored_count }}</span>
          <span>评分 {{ potentialSearch.scored_count }}</span>
        </div>
        <div v-if="potentialSearch?.errors?.length" class="potential-errors">
          <small v-for="(err, idx) in potentialSearch.errors" :key="idx">⚠ {{ err }}</small>
        </div>
        <div v-if="potentialTopItems.length" class="score-list">
          <div v-for="item in potentialTopItems" :key="item.symbol" class="score-item">
            <strong>{{ item.symbol }} {{ item.name }} / {{ (item.potential_score ?? 0).toFixed(1) }}</strong>
            <span>{{ item.lifecycle_state ?? '未知' }}
              <template v-if="item.current_price"> / ¥{{ item.current_price }}</template>
              <template v-if="item.pct_change != null"> / {{ item.pct_change.toFixed(2) }}%</template>
            </span>
            <small>{{ (item.reasons ?? []).slice(0, 3).join('；') }}</small>
          </div>
        </div>
        <p v-else>暂无搜索记录。可在盘后运行「潜力搜索」按钮收集更多候选。</p>
      </article>
<article class="panel wide">
        <h2>Agent Control Queue</h2>
        <div class="metrics">
          <span>实盘状态: {{ agentCapabilities?.live_trading_enabled ? '允许' : '禁用' }}</span>
          <span>券商控制: {{ agentCapabilities?.broker_control_blocked ? '拦截' : '允许' }}</span>
        </div>
        <p>安全沙盒任务:</p>
        <div class="actions">
          <button v-for="t in agentCapabilities?.safe_tasks" :key="t" @click="runAgentTask(t)" :disabled="agentTaskLoading">
            运行 {{ t }}
          </button>
        </div>
        <p>需要审批的任务:</p>
        <div class="actions">
          <button v-for="t in agentCapabilities?.observation_tasks" :key="t" @click="runAgentTask(t)" :disabled="agentTaskLoading" class="ghost">
            发起 {{ t }}
          </button>
        </div>
        <p>阻断任务:</p>
        <div class="actions">
          <button class="disabled-live" v-for="t in agentCapabilities?.blocked_tasks" :key="t" disabled>
            拦截 {{ t }}
          </button>
        </div>

        <div v-if="agentTasks.length" class="score-list">
          <div v-for="task in agentTasks" :key="task.id" class="score-item">
            <strong>任务 #{{ task.id }} : {{ task.task_type }}</strong>
            <span>状态: {{ task.status }} / 审批: {{ task.approval_status }}</span>
            <div class="actions" v-if="task.approval_status === 'pending'">
              <button @click="approveTask(task.id)">Approve</button>
              <button class="disabled-live" @click="rejectTask(task.id)">Reject</button>
            </div>
            <div class="actions" v-else-if="task.approval_status === 'approved' && task.status !== 'completed' && task.status !== 'failed'">
              <button @click="executeTask(task.id)" :disabled="agentTaskLoading">Execute</button>
            </div>
            <small v-if="task.error">⚠ {{ task.error }}</small>
          </div>
        </div>
        <p v-else>暂无Agent任务记录。</p>

        <p>审计日志:</p>
        <div v-if="agentAudit.length" class="score-list">
          <div v-for="audit in agentAudit" :key="audit.id" class="score-item">
            <strong>事件: {{ audit.event_type }} (任务 #{{ audit.task_id }})</strong>
            <span>{{ audit.message }}</span>
            <small>{{ audit.created_at }}</small>
          </div>
        </div>
      </article>

<article class="panel wide">
        <h2>Sandbox Experiments</h2>
        <p class="review-only-banner">🔬 Sandbox-only: experiments simulate what-if scenarios for approved proposals. No scoring rules, candidate scores, or trading behavior are changed.</p>
        <div class="metrics">
          <span>实验总数 {{ sandboxSummary?.total_experiments ?? 0 }}</span>
          <span>待运行提案 {{ sandboxSummary?.approved_proposals_without_experiment ?? 0 }}</span>
        </div>
        <div class="metrics" v-if="sandboxSummary?.by_conclusion">
          <span v-for="(cnt, key) in sandboxSummary.by_conclusion" :key="key">{{ key }}: {{ cnt }}</span>
        </div>
        <div class="actions">
          <button data-testid="run-sandbox-approved-button" @click="runSandboxApproved" :disabled="sandboxLoading">
            {{ sandboxLoading ? '实验中' : '运行已批准提案实验' }}
          </button>
        </div>
        <div v-if="sandboxExperiments.length" class="score-list">
          <div v-for="exp in sandboxExperiments" :key="exp.id" :class="['score-item', sandboxConclusionClass(exp)]">
            <strong>实验 #{{ exp.id }} / 提案 #{{ exp.proposal_id }} — {{ exp.conclusion }}</strong>
            <span>
              基线样本 {{ exp.baseline_metrics?.sample_count ?? 0 }} /
              强突破 {{ exp.baseline_metrics?.strong_follow_through_count ?? 0 }} /
              失败 {{ exp.baseline_metrics?.failed_signal_count ?? 0 }}
            </span>
            <span v-if="exp.proposed_metrics?.behavior_change">
              提案动作: {{ exp.proposed_metrics?.action }} /
              <template v-if="exp.proposed_metrics?.estimated_coverage_pct != null">覆盖率 {{ exp.proposed_metrics.estimated_coverage_pct }}%</template>
              <template v-if="exp.proposed_metrics?.collateral_damage_pct != null">误伤率 {{ exp.proposed_metrics.collateral_damage_pct }}%</template>
            </span>
            <span v-else>无行为变化: {{ exp.proposed_metrics?.note }}</span>
            <small>创建: {{ exp.created_at }} / 状态: {{ exp.status }}</small>
          </div>
        </div>
        <p v-else>暂无沙盒实验记录。批准校准提案后点击「运行已批准提案实验」开始。</p>
      </article>
<article class="panel wide">
        <h2>Paper Simulation</h2>
        <p class="review-only-banner">🧪 SIMULATION ONLY: All actions shown here are simulated paper-trading results. They are NOT real orders, NOT investment advice, and NOT connected to any broker.</p>
        <div class="metrics">
          <span>策略总数 {{ paperSimSummary?.policy_count ?? 0 }}</span>
          <span>草稿 {{ paperSimSummary?.policy_by_status?.draft ?? 0 }}</span>
          <span>已批准 {{ paperSimSummary?.policy_by_status?.approved ?? 0 }}</span>
          <span>已拒绝 {{ paperSimSummary?.policy_by_status?.rejected ?? 0 }}</span>
        </div>
        <div class="metrics">
          <span>模拟运行 {{ paperSimSummary?.run_count ?? 0 }}</span>
          <span>模拟动作 {{ paperSimSummary?.action_count ?? 0 }}</span>
          <span v-for="(cnt, key) in paperSimSummary?.action_by_type" :key="key">{{ key }}: {{ cnt }}</span>
        </div>
        <div class="actions">
          <button data-testid="draft-sim-policies-button" @click="draftSimPolicies" :disabled="paperSimLoading">
            {{ paperSimLoading ? '生成中' : '从实验生成策略草稿' }}
          </button>
          <button data-testid="run-approved-sims-button" @click="runApprovedSimulations" :disabled="paperSimLoading">
            {{ paperSimLoading ? '运行中' : '运行已批准模拟' }}
          </button>
        </div>

        <h3 v-if="paperSimPolicies.length" style="margin-top: 16px;">Simulation Policies</h3>
        <div v-if="paperSimPolicies.length" class="score-list">
          <div v-for="p in paperSimPolicies" :key="p.id" :class="['score-item', policyStatusClass(p)]">
            <strong>策略 #{{ p.id }} / 实验 #{{ p.source_experiment_id }} — {{ p.policy_type }}</strong>
            <span>状态: {{ p.status }} / {{ p.policy?.disclaimer ? '⚠ 仅限模拟' : '' }}</span>
            <small>动作: {{ p.policy?.action ?? '观察' }} / 创建: {{ p.created_at }}</small>
            <div class="actions" v-if="p.status === 'draft'">
              <button @click="approveSimPolicy(p.id)">Approve</button>
              <button class="disabled-live" @click="rejectSimPolicy(p.id)">Reject</button>
            </div>
          </div>
        </div>

        <h3 v-if="paperSimRuns.length" style="margin-top: 16px;">Recent Simulation Runs</h3>
        <div v-if="paperSimRuns.length" class="score-list">
          <div v-for="run in paperSimRuns" :key="run.id" class="score-item">
            <strong>运行 #{{ run.id }} / 策略 #{{ run.policy_id }} — {{ run.status }}</strong>
            <span>
              候选 {{ run.metrics?.total_candidates ?? 0 }} /
              观察 {{ run.metrics?.observe_count ?? 0 }} /
              模拟入场 {{ run.metrics?.simulated_entry_count ?? 0 }} /
              模拟退出 {{ run.metrics?.simulated_exit_count ?? 0 }} /
              跳过 {{ run.metrics?.skip_count ?? 0 }}
            </span>
            <small>{{ run.metrics?.disclaimer ?? '仅限模拟' }}</small>
          </div>
        </div>
        <p v-if="!paperSimPolicies.length && !paperSimRuns.length">暂无模拟策略或运行记录。请先运行沙盒实验，然后点击「从实验生成策略草稿」。</p>
      </article>
<article class="panel wide">
        <h2>Simulation Evaluation</h2>
        <p class="review-only-banner">🧪 EVALUATION ONLY: This panel evaluates simulated actions against subsequent market data. It does NOT alter production scoring, rules, or live trading.</p>
        <div class="metrics">
          <span>总评估数 {{ paperSimEvalSummary?.total_evaluations ?? 0 }}</span>
          <span>已完成 {{ paperSimEvalSummary?.by_status?.completed ?? 0 }}</span>
          <span>等待未来数据 {{ paperSimEvalSummary?.by_status?.pending_future_data ?? 0 }}</span>
          <span>无价格跳过 {{ paperSimEvalSummary?.by_status?.skipped_no_price ?? 0 }}</span>
        </div>
        <div class="metrics">
          <span v-for="(cnt, key) in paperSimEvalSummary?.by_outcome_label" :key="'lbl-'+key">{{ key }}: {{ cnt }}</span>
        </div>
        <div class="actions">
          <button data-testid="eval-recent-sims-button" @click="evaluateRecentSimulations" :disabled="paperSimEvalLoading">
            {{ paperSimEvalLoading ? '评估中' : '评估近期模拟动作' }}
          </button>
        </div>

        <h3 v-if="paperSimEvalPolicies.length" style="margin-top: 16px;">Policy Performance Conclusions</h3>
        <div v-if="paperSimEvalPolicies.length" class="score-list">
          <div v-for="p in paperSimEvalPolicies" :key="p.policy_id" :class="['score-item', evalConclusionClass(p.conclusion)]">
            <strong>策略 #{{ p.policy_id }} ({{ p.policy_type }}) — {{ p.conclusion }}</strong>
            <span>
              已完成 {{ p.completed }} /
              强突破 {{ p.strong_follow_through }} /
              失败信号 {{ p.failed_signal }} /
              大回撤 {{ p.large_drawdowns }}
            </span>
            <small>
              待定: {{ p.pending_future_data }} /
              跳过: {{ p.skipped_no_price }} /
              {{ p.disclaimer }}
            </small>
          </div>
        </div>
        <p v-if="!paperSimEvalPolicies.length">暂无策略评估结论。点击「评估近期模拟动作」开始评估。</p>
      </article>
<article class="panel wide">
        <h2>AI复盘</h2>
        <p>{{ reviewText }}</p>
        <div class="account">
          <span>模拟现金 {{ account?.cash?.toFixed(2) ?? "未加载" }}</span>
          <span>持仓 {{ account?.positions?.length ?? 0 }}</span>
          <span>自动化 {{ automation?.status ?? "未运行" }}</span>
          <span>处理 {{ automation?.summary?.processed_count ?? 0 }}</span>
        </div>
        <div v-if="automation" class="plan">
          <strong>自动化进程 #{{ automation.run_id || automation.id }}</strong>
          <span>计划 {{ automation.summary?.planned_count ?? 0 }} / 跳过 {{ automation.summary?.skipped_count ?? 0 }}</span>
          <span v-if="automation.summary?.phase_matches?.length">
            阶段风控 {{ automation.summary.phase_guarded_count ?? 0 }} /
            {{ automation.summary.phase_matches[0].target_symbol }}
            {{ automation.summary.phase_matches[0].score?.toFixed(1) ?? "NA" }}
          </span>
          <span v-if="automation.summary?.auto_discovery">
            自动发现 {{ automation.summary.auto_discovery.discovered_count }} /
            涨停 {{ automation.summary.auto_discovery.limit_up_count }}
          </span>
          <span v-if="automation.summary?.scoring">
            潜力评分 {{ automation.summary.scoring.scored_count }} /
            {{ automation.summary.scoring.top_scores?.[0]?.symbol ?? "NA" }}
            {{ automation.summary.scoring.top_scores?.[0]?.total_score?.toFixed(1) ?? "NA" }}
          </span>
          <small>{{ (automation.summary?.items ?? []).map((item) => `${item.symbol}:${item.status}`).join("；") }}</small>
        </div>
        <div v-if="lifecycleSummary" class="report">
          <strong>候选池生命周期</strong>
          <span>
            自动发现 {{ lifecycleSummary.state_counts.auto_discovered }} /
            待复核 {{ lifecycleSummary.state_counts.pending_review }} /
            重点观察 {{ lifecycleSummary.state_counts.focus_watch }} /
            阶段风控 {{ lifecycleSummary.state_counts.phase_guarded }} /
            淘汰 {{ lifecycleSummary.state_counts.rejected }}
          </span>
          <small>{{ lifecycleSummary.latest_events.slice(0, 5).map((item) => `${item.symbol}:${item.from_state ?? "new"}→${item.to_state}`).join("；") }}</small>
        </div>
        <div v-if="learningReport" class="report">
          <strong>{{ learningReport.title }} #{{ learningReport.id }}</strong>
          <span>
            样本 {{ learningReport.summary.learning.backtest.sample_count }} /
            胜率 {{ (learningReport.summary.learning.backtest.win_rate * 100).toFixed(1) }}%
          </span>
          <span v-if="learningReport.summary.main_force_patterns?.pattern_count">
            主力阶段样本 {{ learningReport.summary.main_force_patterns.pattern_count }} /
            {{ learningReport.summary.main_force_patterns.patterns[0].symbol }}
            {{ learningReport.summary.main_force_patterns.patterns[0].current_phase }}
          </span>
          <span v-if="learningReport.summary.phase_matches?.guarded_count">
            阶段风控 {{ learningReport.summary.phase_matches.guarded_count }} /
            {{ learningReport.summary.phase_matches.matches[0].target_symbol }}
            {{ learningReport.summary.phase_matches.matches[0].score?.toFixed(1) ?? "NA" }}
          </span>
          <span>
            乐凯胶片、三维通信保留用户确认样本；金螳螂按出货完成阶段样本训练
          </span>
          <small>{{ learningReport.summary.next_actions.slice(0, 2).join("；") }}</small>
        </div>
        <div v-if="monitoring" class="report">
          <strong>盘中监控 #{{ monitoring.session_id }}</strong>
          <span>
            事件 {{ monitoring.event_count }} / 告警 {{ monitoring.alert_count ?? 0 }} /
            允许买入 {{ monitoring.allowed_count }}
          </span>
          <small>{{ monitoring.events.slice(0, 5).map((item) => item.summary).join("；") }}</small>
          <small>{{ (monitoring.alerts ?? []).slice(0, 5).map((item) => item.message).join("；") }}</small>
        </div>
        <div v-if="monitoringReview" class="report">
          <strong>{{ monitoringReview.title }} #{{ monitoringReview.id }}</strong>
          <span>
            事件 {{ monitoringReview.summary.event_count }} / 告警 {{ monitoringReview.summary.alert_count }} /
            风控阻断 {{ monitoringReview.summary.risk_blocked_count }}
          </span>
          <span>{{ monitoringReview.summary.diagnosis }}</span>
          <small>{{ monitoringReview.summary.next_actions.slice(0, 3).join("；") }}</small>
        </div>
        <div v-for="item in phaseReplays" :key="item.id" class="report">
          <strong>主力阶段回放 #{{ item.id }} {{ item.symbol }} {{ item.name }}</strong>
          <span>
            {{ item.summary.start_date }} 至 {{ item.summary.end_date }} /
            最新 {{ item.summary.latest_phase_name }} /
            区间 {{ item.summary.period_return_pct?.toFixed(1) ?? "NA" }}%
          </span>
          <span>{{ item.summary.diagnosis }}</span>
          <small>{{ item.segments.slice(-4).map((segment) => `${segment.phase_name}:${segment.start_date}-${segment.end_date}`).join("；") }}</small>
        </div>
        <div v-if="phaseMatch" class="report">
          <strong>阶段相似度 #{{ phaseMatch.id }} {{ phaseMatch.target_symbol }} {{ phaseMatch.target_name }}</strong>
          <span>
            最像 {{ phaseMatch.summary.best_match?.core_symbol }}
            {{ phaseMatch.summary.best_match?.core_name }} /
            分数 {{ phaseMatch.summary.best_match?.score.toFixed(1) ?? "NA" }}
          </span>
          <span>{{ phaseMatch.summary.diagnosis }}</span>
          <small>{{ phaseMatch.summary.next_actions.slice(0, 3).join("；") }}</small>
        </div>
      </article>
<article class="panel wide">
        <h2>Agent Learning Samples</h2>
        <div class="metrics">
          <span>总样本 {{ agentLearningSummary?.total_count ?? 0 }}</span>
          <span v-for="(cnt, key) in agentLearningSummary?.by_sample_type" :key="key">{{ key }}: {{ cnt }}</span>
        </div>
        <div class="metrics">
          <span v-for="(cnt, key) in agentLearningSummary?.by_label" :key="key">{{ key }}: {{ cnt }}</span>
        </div>
        <div class="actions">
          <button data-testid="agent-learning-ingest-button" @click="ingestAgentLearning" :disabled="agentLearningLoading">
            {{ agentLearningLoading ? '收集中' : '收集最近完成的任务' }}
          </button>
        </div>
        <div v-if="agentLearningIngestResult" class="report">
          <strong>收集结果</strong>
          <span>处理任务 {{ agentLearningIngestResult.tasks_processed }} / 新增样本 {{ agentLearningIngestResult.total_created }}</span>
        </div>
        <div v-if="agentLearningSamples.length" class="score-list">
          <div v-for="sample in agentLearningSamples" :key="sample.id" class="score-item">
            <strong>{{ sample.symbol ?? '系统' }} {{ sample.name ?? '' }} / {{ sample.sample_type }}</strong>
            <span>任务 #{{ sample.source_task_id }} / 标签: {{ sample.label ?? '未标注' }}</span>
            <small v-if="sample.risk_flags?.length">⚠ {{ sample.risk_flags.join('；') }}</small>
          </div>
        </div>
        <p v-else>暂无Agent学习样本。点击「收集最近完成的任务」开始收集。</p>
      </article>
<article class="panel wide">
        <h2>Agent Learning Outcomes</h2>
        <div class="metrics">
          <span>覆盖数 {{ agentOutcomeSummary?.coverage_count ?? 0 }}</span>
          <span>等待未来数据 {{ agentOutcomeSummary?.pending_count ?? 0 }}</span>
        </div>
        <div class="metrics">
          <span v-for="(cnt, key) in agentOutcomeSummary?.by_label" :key="key">{{ key }}: {{ cnt }}</span>
        </div>
        <div class="actions">
          <button data-testid="agent-outcomes-label-button" @click="labelRecentOutcomes" :disabled="agentOutcomeLoading">
            {{ agentOutcomeLoading ? '评估中' : '评估最近样本结局' }}
          </button>
        </div>
        <div v-if="agentOutcomes.length" class="score-list">
          <div v-for="outcome in agentOutcomes" :key="outcome.id" class="score-item">
            <strong>样本 #{{ outcome.sample_id }} / 周期 {{ outcome.horizon_days }}天 / {{ outcome.outcome_label }}</strong>
            <span>
              {{ outcome.start_date }} 至 {{ outcome.end_date }} / 风险: {{ outcome.risk_outcome }}
            </span>
            <small v-if="hasOutcomeReturns(outcome)">
              最大收益: {{ formatOutcomeMetric(outcome, "max_return") }}% / 最大回撤: {{ formatOutcomeMetric(outcome, "min_return") }}% / 最终收益: {{ formatOutcomeMetric(outcome, "close_return") }}%
            </small>
            <small v-else-if="outcome.outcome_label === 'pending_future_data'">待未来数据确认</small>
          </div>
        </div>
        <p v-else>暂无结局评估记录。点击「评估最近样本结局」开始评估。</p>
      </article>
<article class="panel wide">
        <h2>Signal Performance & Calibration</h2>
        <p class="review-only-banner">⚠ All calibration proposals are review-only. No scoring weights or trading rules are changed automatically.</p>
        <div class="metrics">
          <span>有结局样本 {{ signalPerformanceSummary?.total_samples_with_outcomes ?? 0 }}</span>
          <span>类型组 {{ Object.keys(signalPerformanceSummary?.by_sample_type ?? {}).length }}</span>
          <span>标签组 {{ Object.keys(signalPerformanceSummary?.by_label ?? {}).length }}</span>
          <span>风险标签组 {{ Object.keys(signalPerformanceSummary?.by_risk_flag ?? {}).length }}</span>
        </div>
        <div class="actions">
          <button data-testid="generate-proposals-button" @click="generateCalibrationProposals" :disabled="calibrationLoading">
            {{ calibrationLoading ? '生成中' : '生成校准提案' }}
          </button>
        </div>

        <div v-if="signalPerfRows.length" class="score-list">
          <div v-for="row in signalPerfRows" :key="row.key" class="score-item">
            <strong>{{ row.group }}: {{ row.key }}</strong>
            <span>
              样本 {{ row.stats.sample_count }} /
              强突破 {{ row.stats.strong_follow_through_count }} /
              弱突破 {{ row.stats.mild_follow_through_count }} /
              失败 {{ row.stats.failed_signal_count }}
            </span>
            <span>
              待定率 {{ (row.stats.pending_rate * 100).toFixed(1) }}% /
              平均收益 {{ row.stats.avg_close_return != null ? row.stats.avg_close_return.toFixed(2) + '%' : '无' }} /
              大回撤 {{ row.stats.large_drawdown_count }}
            </span>
            <small v-if="row.stats.small_sample_warning" class="small-sample-warn">⚠ 小样本 (&lt;{{ smallSampleThreshold }})</small>
          </div>
        </div>
        <p v-else>暂无信号绩效数据。请先运行「评估最近样本结局」。</p>

        <h3 v-if="calibrationProposals.length" style="margin-top: 16px;">Pending Calibration Proposals</h3>
        <div v-if="calibrationProposals.length" class="score-list">
          <div v-for="p in calibrationProposals" :key="p.id" :class="['score-item', proposalBorderClass(p)]">
            <strong>{{ p.proposal_type }}: {{ p.target }} — {{ p.proposal?.action }}</strong>
            <span>{{ p.proposal?.reason }}</span>
            <small>{{ p.proposal?.recommendation }}</small>
            <small>状态: {{ p.status }} / 创建: {{ p.created_at }}</small>
            <div class="actions" v-if="p.status === 'pending'">
              <button @click="approveCalibrationProposal(p.id)">Approve</button>
              <button class="disabled-live" @click="rejectCalibrationProposal(p.id)">Reject</button>
            </div>
          </div>
        </div>
      </article>
<article class="panel">
        <h2>知识库</h2>
        <div class="knowledge">
          <span>铁律 {{ summary?.principles ?? 0 }}</span>
          <span>战法 {{ summary?.strategies ?? 0 }}</span>
          <span>案例 {{ summary?.trade_cases ?? 0 }}</span>
          <span>档案 {{ summary?.stock_profiles ?? 0 }}</span>
        </div>
        <p>候选股分析会自动引用交易铁律、相关战法、相似案例和成本线档案。</p>
        <div class="actions">
          <button data-testid="simulation-plan-button" @click="loadPlan" :disabled="!topCandidates.length || planLoading">
            {{ planLoading ? "生成中" : "生成模拟计划" }}
          </button>
          <button data-testid="analyze-symbol-button" @click="runAnalysis" :disabled="!topCandidates.length || analysisLoading">
            {{ analysisLoading ? "分析中" : "生成分析解释" }}
          </button>
          <button disabled>模拟卖出</button>
          <button class="ghost" disabled>实盘买入</button>
        </div>
        <div v-if="topScores.length" class="score-list">
          <div v-for="item in topScores.slice(0, 5)" :key="item.symbol" class="score-item">
            <strong>{{ item.symbol }} {{ item.name }} / {{ item.total_score.toFixed(1) }}</strong>
            <span>{{ item.state }} / 发现 {{ item.components.discovery_score.toFixed(1) }} / 量能 {{ item.components.volume_score.toFixed(1) }} / 阶段 {{ item.components.phase_score.toFixed(1) }}</span>
            <small>{{ item.reasons.slice(0, 3).join("；") }}</small>
          </div>
        </div>
        <div v-if="plan" class="plan">
          <strong>{{ plan.symbol }} {{ plan.name }}：{{ plan.action }}</strong>
          <span>数量 {{ plan.quantity }} 股 / 参考价 {{ plan.reference_price }}</span>
          <span>止损 {{ plan.stop_loss ?? "待确认" }} / 目标 {{ plan.target_price ?? "待确认" }}</span>
          <small>{{ plan.reasons.join("；") }}</small>
        </div>
        <div v-if="analysis?.explanation" class="plan">
          <strong>AI 决策分析：{{ analysis.snapshot.symbol }}</strong>
          <span>{{ analysis.explanation.signal_summary }}</span>
          <span>匹配规则：{{ analysis.explanation.matched_rules.join("；") || "无" }}</span>
          <span>风险拦截：{{ analysis.explanation.risk_blockers.join("；") || "无" }}</span>
          <span>数据质量：{{ analysis.explanation.data_quality }}</span>
          <span v-if="analysis.explanation.similar_cases?.length">
            相似案例：{{ analysis.explanation.similar_cases.map((c: any) => c.name).join("；") }}
          </span>
          <small v-for="(note, idx) in analysis.explanation.uncertainty_notes" :key="idx">⚠ {{ note }}</small>
          <small class="review-only-banner">{{ analysis.explanation.simulation_disclaimer }}</small>
        </div>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

type KnowledgeSummary = {
  principles: number;
  strategies: number;
  trade_cases: number;
  stock_profiles: number;
};

type CandidateItem = {
  symbol: string;
  name: string;
  tier: "strong" | "watch" | "rejected";
  rating?: string;
  risk_level?: string;
  reasons?: string[];
};

type AutoDiscoveryResult = {
  status: string;
  source: string;
  discovered_count: number;
  limit_up_count?: number;
  near_limit_up_count?: number;
  strong_mover_count?: number;
  error?: string;
  items: Array<{
    symbol: string;
    name?: string;
    pct_change?: number;
    discovery_type: string;
    priority: number;
  }>;
};

type CandidateScan = {
  id?: number;
  scan_id?: number;
  strong_count: number;
  watch_count: number;
  rejected_count: number;
  buckets: Record<"strong" | "watch" | "rejected", CandidateItem[]>;
};

type CandidateLifecycleSummary = {
  state_counts: {
    auto_discovered: number;
    pending_review: number;
    focus_watch: number;
    phase_guarded: number;
    rejected: number;
  };
  state_labels: Record<string, string>;
  latest_events: Array<{
    id: number;
    symbol: string;
    name?: string;
    from_state?: string | null;
    to_state: string;
    event_type: string;
    source: string;
    created_at: string;
  }>;
};

type CandidateScore = {
  id?: number;
  symbol: string;
  name?: string;
  total_score: number;
  rating?: string;
  state?: string;
  reasons: string[];
  components: {
    discovery_score: number;
    volume_score: number;
    phase_score: number;
    lifecycle_score: number;
    focus_score: number;
    risk_penalty: number;
  };
};

type SimulationPlan = {
  symbol: string;
  name?: string;
  action: string;
  quantity: number;
  reference_price: number;
  stop_loss?: number;
  target_price?: number;
  reasons: string[];
};

type SimulationAccount = {
  cash: number;
  initial_cash: number;
  positions: Array<{
    symbol: string;
    quantity: number;
    sellable_quantity: number;
    avg_cost: number;
  }>;
};

type AutomationRun = {
  id?: number;
  run_id?: number;
  status: string;
  summary?: {
    auto_discovery?: {
      status: string;
      discovered_count: number;
      limit_up_count: number;
      near_limit_up_count?: number;
      strong_mover_count?: number;
      error?: string;
    };
    processed_count?: number;
    planned_count?: number;
    skipped_count?: number;
    scoring?: {
      scored_count: number;
      top_scores: CandidateScore[];
    };
    phase_match_count?: number;
    phase_guarded_count?: number;
    phase_matches?: Array<{
      target_symbol: string;
      target_name?: string;
      match_id?: number;
      best_core_symbol?: string;
      score?: number;
      diagnosis?: string;
    }>;
    items: Array<{ symbol: string; status: string; action?: string }>;
  };
};

type LearningReport = {
  id: number;
  title: string;
  summary: {
    learning: {
      backtest: {
        sample_count: number;
        win_rate: number;
      };
    };
    main_force_patterns?: {
      pattern_count: number;
      patterns: Array<{
        symbol: string;
        name?: string;
        status: string;
        current_phase: string;
        training_focus: string[];
        caution_notes: string[];
      }>;
    };
    phase_matches?: {
      match_count: number;
      guarded_count: number;
      matches: Array<{
        target_symbol: string;
        target_name?: string;
        best_core_symbol?: string;
        score?: number;
        diagnosis?: string;
      }>;
    };
    next_actions: string[];
  };
};

type MonitoringEvent = {
  id?: number;
  symbol: string;
  name?: string;
  price?: number;
  pct_change?: number;
  signal: string;
  action?: string;
  allowed: boolean;
  summary: string;
};

type MonitoringAlert = {
  id?: number;
  symbol: string;
  severity: string;
  alert_type: string;
  message: string;
};

type MonitoringRun = {
  session_id: number;
  event_count: number;
  allowed_count: number;
  alert_count?: number;
  signals: Record<string, number>;
  events: MonitoringEvent[];
  alerts?: MonitoringAlert[];
};

type MonitoringReview = {
  id: number;
  title: string;
  summary: {
    event_count: number;
    alert_count: number;
    risk_blocked_count: number;
    diagnosis: string;
    next_actions: string[];
  };
};

type PhaseReplay = {
  id: number;
  symbol: string;
  name?: string;
  latest_phase: string;
  summary: {
    start_date: string;
    end_date: string;
    latest_phase_name: string;
    period_return_pct?: number;
    diagnosis: string;
  };
  segments: Array<{
    phase: string;
    phase_name: string;
    start_date: string;
    end_date: string;
    bars: number;
    return_pct?: number;
  }>;
};

type PhaseMatch = {
  id: number;
  target_symbol: string;
  target_name?: string;
  summary: {
    target_latest_phase?: string;
    target_latest_phase_name?: string;
    diagnosis: string;
    next_actions: string[];
    best_match?: {
      core_symbol: string;
      core_name?: string;
      score: number;
      inference: string;
    };
  };
};

type AutomationCycle = {
  status: string;
  live_trading_enabled: boolean;
  automation: AutomationRun;
  learning_report?: LearningReport | null;
  monitoring?: MonitoringRun;
  monitoring_review?: MonitoringReview;
};

type PotentialSearchItem = {
  symbol: string;
  name?: string;
  current_price?: number | null;
  pct_change?: number | null;
  turnover_rate?: number | null;
  amount?: number | null;
  lifecycle_state?: string;
  potential_score?: number;
  reasons?: string[];
  components?: Record<string, number>;
};

type PotentialSearchRun = {
  run_id?: number | null;
  id?: number;
  status: string;
  source: string;
  total_scanned: number;
  stored_count: number;
  scored_count: number;
  top_scored_symbols?: string[];
  top_scored_items?: PotentialSearchItem[];
  items?: PotentialSearchItem[];
  notes?: string;
  errors?: string[];
  created_at?: string;
};

type AgentCapabilities = {
  safe_tasks: string[];
  observation_tasks: string[];
  blocked_tasks: string[];
  live_trading_enabled: boolean;
  broker_control_blocked: boolean;
};

type AgentTask = {
  id: number;
  task_type: string;
  status: string;
  approval_status: string;
  error?: string;
};

type AgentLearningSampleItem = {
  id: number;
  source_task_id: number;
  sample_type: string;
  symbol?: string;
  name?: string;
  features?: Record<string, any>;
  decision?: Record<string, any>;
  risk_flags?: string[];
  label?: string;
  label_source?: string;
  created_at?: string;
};

type AgentLearningSummaryData = {
  total_count: number;
  by_sample_type: Record<string, number>;
  by_label: Record<string, number>;
};

type AgentLearningIngestResult = {
  tasks_processed: number;
  total_created: number;
  details: any[];
};

type AgentLearningOutcomeItem = {
  id: number;
  sample_id: number;
  symbol?: string;
  horizon_days: number;
  start_date?: string;
  end_date?: string;
  start_price?: number;
  end_price?: number;
  max_return_pct?: number;
  min_return_pct?: number;
  close_return_pct?: number;
  outcome_label: string;
  risk_outcome: string;
  metrics?: Record<string, any>;
};

type AgentOutcomeSummaryData = {
  coverage_count: number;
  pending_count: number;
  by_sample_type: Record<string, any>;
  by_label: Record<string, number>;
};

type SignalPerformanceSummaryData = {
  total_samples_with_outcomes: number;
  by_sample_type: Record<string, SignalGroupStats>;
  by_label: Record<string, SignalGroupStats>;
  by_risk_flag: Record<string, SignalGroupStats>;
  by_symbol: Record<string, SignalGroupStats>;
  by_scoring_component: Record<string, SignalGroupStats>;
  generated_at?: string;
};

type SignalGroupStats = {
  sample_count: number;
  outcome_count: number;
  pending_count: number;
  pending_rate: number;
  strong_follow_through_count: number;
  mild_follow_through_count: number;
  failed_signal_count: number;
  avg_close_return: number | null;
  avg_max_return: number | null;
  avg_min_return: number | null;
  large_drawdown_count: number;
  small_sample_warning?: boolean;
};

type CalibrationProposalItem = {
  id: number;
  proposal_type: string;
  target: string;
  status: string;
  evidence: Record<string, any>;
  proposal: {
    action: string;
    reason: string;
    recommendation: string;
    review_only: boolean;
  };
  created_by?: string;
  reviewed_by?: string;
  review_note?: string;
  created_at?: string;
  updated_at?: string;
  reviewed_at?: string;
};

type SandboxExperimentItem = {
  id: number;
  proposal_id: number;
  status: string;
  baseline_metrics: Record<string, any>;
  proposed_metrics: Record<string, any>;
  comparison: Record<string, any>;
  conclusion: string;
  created_by?: string;
  created_at?: string;
  updated_at?: string;
  completed_at?: string;
};

type SandboxSummaryData = {
  total_experiments: number;
  by_conclusion: Record<string, number>;
  by_status: Record<string, number>;
  approved_proposals_without_experiment: number;
};

type SimulationPolicyItem = {
  id: number;
  source_experiment_id: number;
  policy_type: string;
  status: string;
  policy: Record<string, any>;
  risk_limits: Record<string, any>;
  created_by?: string;
  reviewed_by?: string;
  review_note?: string;
  created_at?: string;
  updated_at?: string;
  reviewed_at?: string;
};

type PaperSimulationRunItem = {
  id: number;
  policy_id: number;
  status: string;
  started_at?: string;
  completed_at?: string;
  metrics: Record<string, any>;
  created_by?: string;
  created_at?: string;
  actions?: Array<{
    id: number;
    symbol: string;
    action_type: string;
    simulated_price?: number;
    risk_flags?: string[];
  }>;
};

type PaperSimulationSummaryData = {
  policy_count: number;
  policy_by_status: Record<string, number>;
  run_count: number;
  run_by_status: Record<string, number>;
  action_count: number;
  action_by_type: Record<string, number>;
  latest_run_metrics: Record<string, any> | null;
  disclaimer: string;
};

type PaperSimulationEvaluationSummaryData = {
  total_evaluations: number;
  by_status: Record<string, number>;
  by_outcome_label: Record<string, number>;
  by_risk_outcome: Record<string, number>;
  disclaimer: string;
};

type PaperSimulationPolicyConclusion = {
  policy_id: number;
  policy_type: string;
  total_evaluations: number;
  completed: number;
  pending_future_data: number;
  skipped_no_price: number;
  errors: number;
  strong_follow_through: number;
  mild_follow_through: number;
  failed_signal: number;
  large_drawdowns: number;
  conclusion: string;
  disclaimer: string;
};

type PriceReadinessReport = {
  symbol: string;
  name?: string;
  source: string;
  latest_price?: number;
  latest_price_at?: string;
  coverage_status: string;
  history_points: number;
  error_message?: string;
};

type PriceReadinessSummary = Record<string, number>;

type RealtimeCapabilities = {
  status: string;
  active_provider: string;
  provider_status: string;
  allowed_modes: string[];
  forbidden_modes: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type RealtimeProviderHealth = {
  provider: string;
  status: string;
  configured: boolean;
  quality_status: string;
  last_error?: string | null;
  last_event_ts?: string | null;
  latency_ms?: number | null;
  details?: Record<string, any>;
};

type RealtimeEvent = {
  id: number;
  symbol: string;
  name?: string;
  price: number;
  volume?: number;
  amount?: number;
  source: string;
  provider_status: string;
  event_ts: string;
  received_ts: string;
  latency_ms?: number;
  quality_status: string;
  fallback_used: boolean;
  dedupe_key: string;
  payload?: Record<string, any>;
};

type RealtimeSnapshot = {
  status: string;
  quality_status?: string;
  fallback_status?: string;
  event?: RealtimeEvent;
  provider_health?: RealtimeProviderHealth[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type RealtimeReplaySummary = {
  symbol_count: number;
  symbols: string[];
  signal_counts: Record<string, number>;
  quality_counts: Record<string, number>;
  latency_ms: {
    min: number | null;
    max: number | null;
    avg: number | null;
  };
  strongest_signals: Array<Record<string, any>>;
  ordered_by: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type RealtimeReplay = {
  status: string;
  event_count: number;
  signals: Array<{
    symbol: string;
    event_ts: string;
    signal_type: string;
    strength: number;
    price?: number;
    previous_price?: number;
    quality_status: string;
    reason: string;
  }>;
  summary: RealtimeReplaySummary;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type RealtimeRefreshResult = {
  status: string;
  provider?: string;
  provider_status?: string;
  configured: boolean;
  requested_count: number;
  refreshed_count: number;
  failed_count: number;
  fallback_required: boolean;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type RealtimeMonitoringSyncResult = {
  status: string;
  session_id: number;
  scanned_event_count: number;
  created_event_count: number;
  created_alert_count: number;
  skipped_duplicate_count: number;
  alerts_by_type: Record<string, number>;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type RealtimeCycleResult = {
  status: string;
  steps: {
    refresh: RealtimeRefreshResult;
    monitoring_sync: RealtimeMonitoringSyncResult;
    replay: RealtimeReplay;
  };
  summary: {
    refreshed_count: number;
    refresh_failed_count: number;
    created_alert_count: number;
    replay_event_count: number;
    signal_counts: Record<string, number>;
    quality_counts: Record<string, number>;
    fallback_required: boolean;
  };
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type BacktestRunItem = {
  id: number;
  status: string;
  data_source: string;
  benchmark_symbol?: string;
  metrics: Record<string, number>;
  benchmark?: Record<string, any>;
  execution_warnings?: string[];
};

type BacktestDetail = {
  run: BacktestRunItem;
  trades: Array<Record<string, any>>;
  closed_trades: Array<{
    id: number;
    symbol: string;
    quantity: number;
    entry_date: string;
    exit_date: string;
    entry_price: number;
    exit_price: number;
    realized_pnl: number;
    realized_pnl_pct: number;
    holding_days: number;
    exit_reason: string;
  }>;
  daily_equity: Array<Record<string, any>>;
  benchmark: Record<string, any>;
  execution_warnings: string[];
};

type MarketRegimeData = {
  regime: string;
  confidence: number;
  reasons: string[];
  data_quality: string;
};

type PortfolioRiskData = {
  posture: string;
  gates: Array<{ name: string; status: string; value: string | number; limit: string | number; reason: string }>;
};

type MonitoringLifecycleData = {
  items: Array<{
    alert_id: number;
    symbol: string;
    severity: string;
    alert_type: string;
    state: string;
  }>;
  open_count: number;
  actioned_count: number;
};

type AIProposalItem = {
  id: number;
  status: string;
  trades_analyzed: number;
  proposed_patch?: Record<string, any>;
  safety_blocks?: string[];
  validation?: Record<string, any>;
};

type ExperienceSummaryData = {
  event_counts: Record<string, number>;
  review_count: number;
  strategy_snapshot_count: number;
  code_evolution_count: number;
  latest_review?: ExperienceReviewItem | null;
  live_trading_enabled: boolean;
};

type ExperienceReviewItem = {
  id: number;
  period_type: string;
  period_start: string;
  period_end: string;
  title: string;
  summary?: Record<string, any>;
  classification?: Record<string, any>;
  next_actions?: string[];
  live_trading_enabled?: number | boolean;
  created_at?: string;
};

type ExperienceEventItem = {
  id: number;
  event_date?: string;
  event_type: string;
  category: string;
  source_table: string;
  source_id?: string;
  symbol?: string;
  name?: string;
  outcome_label?: string;
  confidence?: number;
  payload?: Record<string, any>;
  created_at?: string;
};

type StrategyPerformanceSnapshot = {
  id: number;
  strategy_name: string;
  period_start?: string;
  period_end?: string;
  market_regime?: string;
  metrics?: Record<string, any>;
  source_run_id?: number;
  created_at?: string;
};

type CodeEvolutionRecord = {
  id: number;
  record_type: string;
  status: string;
  title: string;
  rationale?: Record<string, any>;
  plan?: {
    actions?: string[];
    acceptance_criteria?: string[];
    allowed_output?: string;
  };
  validation?: Record<string, any>;
  reviewed_by?: string;
  review_note?: string;
  created_at?: string;
  updated_at?: string;
  reviewed_at?: string;
};

type AIModelCapabilities = {
  provider: string;
  default_provider?: string;
  external_network: boolean;
  api_key_required: boolean;
  operations: string[];
  allowed_outputs: string[];
  forbidden_outputs: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type AIModelAuditLog = {
  id: number;
  provider: string;
  operation: string;
  prompt?: Record<string, any>;
  response?: Record<string, any>;
  safety?: Record<string, any>;
  simulation_only?: boolean;
  created_at?: string;
};

const summary = ref<KnowledgeSummary | null>(null);
const latestScan = ref<CandidateScan | null>(null);
const discovery = ref<AutoDiscoveryResult | null>(null);
const lifecycleSummary = ref<CandidateLifecycleSummary | null>(null);
const topScores = ref<CandidateScore[]>([]);
const plan = ref<SimulationPlan | null>(null);
const analysis = ref<any | null>(null);
const account = ref<SimulationAccount | null>(null);
const automation = ref<AutomationRun | null>(null);
const learningReport = ref<LearningReport | null>(null);
const monitoring = ref<MonitoringRun | null>(null);
const monitoringReview = ref<MonitoringReview | null>(null);
const phaseReplays = ref<PhaseReplay[]>([]);
const phaseMatch = ref<PhaseMatch | null>(null);
const potentialSearch = ref<PotentialSearchRun | null>(null);
const agentCapabilities = ref<AgentCapabilities | null>(null);
const agentTasks = ref<AgentTask[]>([]);
const agentAudit = ref<any[]>([]);
const discoveryLoading = ref(false);
const loading = ref(false);
const planLoading = ref(false);
const analysisLoading = ref(false);
const automationLoading = ref(false);
const monitoringLoading = ref(false);
const phaseReplayLoading = ref(false);
const phaseMatchLoading = ref(false);
const potentialSearchLoading = ref(false);
const agentTaskLoading = ref(false);
const agentLearningSamples = ref<AgentLearningSampleItem[]>([]);
const agentLearningSummary = ref<AgentLearningSummaryData | null>(null);
const agentLearningIngestResult = ref<AgentLearningIngestResult | null>(null);
const agentLearningLoading = ref(false);
const agentOutcomes = ref<AgentLearningOutcomeItem[]>([]);
const agentOutcomeSummary = ref<AgentOutcomeSummaryData | null>(null);
const agentOutcomeLoading = ref(false);
const signalPerformanceSummary = ref<SignalPerformanceSummaryData | null>(null);
const calibrationProposals = ref<CalibrationProposalItem[]>([]);
const calibrationLoading = ref(false);
const sandboxExperiments = ref<SandboxExperimentItem[]>([]);
const sandboxSummary = ref<SandboxSummaryData | null>(null);
const sandboxLoading = ref(false);
const paperSimPolicies = ref<SimulationPolicyItem[]>([]);
const paperSimRuns = ref<PaperSimulationRunItem[]>([]);
const paperSimSummary = ref<PaperSimulationSummaryData | null>(null);
const paperSimLoading = ref(false);
const paperSimEvalSummary = ref<PaperSimulationEvaluationSummaryData | null>(null);
const paperSimEvalPolicies = ref<PaperSimulationPolicyConclusion[]>([]);
const paperSimEvalLoading = ref(false);
const priceReadinessReports = ref<PriceReadinessReport[]>([]);
const priceReadinessSummary = ref<PriceReadinessSummary | null>(null);
const priceReadinessLoading = ref(false);
const dailyBarCoverage = ref<any[]>([]);
const dailyBarRefreshLoading = ref(false);
const realtimeCapabilities = ref<RealtimeCapabilities | null>(null);
const realtimeHealth = ref<RealtimeProviderHealth[]>([]);
const realtimeSnapshot = ref<RealtimeSnapshot | null>(null);
const realtimeEvents = ref<RealtimeEvent[]>([]);
const realtimeReplay = ref<RealtimeReplay | null>(null);
const realtimeRefreshResult = ref<RealtimeRefreshResult | null>(null);
const realtimeMonitoringSync = ref<RealtimeMonitoringSyncResult | null>(null);
const realtimeCycleResult = ref<RealtimeCycleResult | null>(null);
const realtimeLoading = ref(false);
const backtestRuns = ref<BacktestRunItem[]>([]);
const backtestDetail = ref<BacktestDetail | null>(null);
const marketRegime = ref<MarketRegimeData | null>(null);
const portfolioRisk = ref<PortfolioRiskData | null>(null);
const monitoringLifecycle = ref<MonitoringLifecycleData | null>(null);
const aiProposals = ref<AIProposalItem[]>([]);
const experienceSummary = ref<ExperienceSummaryData | null>(null);
const experienceReviews = ref<ExperienceReviewItem[]>([]);
const experienceEvents = ref<ExperienceEventItem[]>([]);
const experienceStrategyPerformance = ref<StrategyPerformanceSnapshot[]>([]);
const experienceCodeEvolution = ref<CodeEvolutionRecord[]>([]);
const aiModelCapabilities = ref<AIModelCapabilities | null>(null);
const aiModelAuditLogs = ref<AIModelAuditLog[]>([]);
const experienceLoading = ref(false);
const codeEvolutionLoading = ref(false);
const aiModelLoading = ref(false);
const v15Loading = ref(false);
const smallSampleThreshold = 10;
const error = ref("");

const statusText = computed(() => {
  if (error.value) return error.value;
  if (latestScan.value) return "本地候选池已加载，实盘权限保持关闭";
  return "等待候选池扫描";
});

const topCandidates = computed(() => {
  const buckets = latestScan.value?.buckets;
  if (!buckets) return [];
  return [...buckets.strong, ...buckets.watch, ...buckets.rejected].slice(0, 8);
});

const experienceEventCounts = computed(() =>
  Object.entries(experienceSummary.value?.event_counts ?? {}).map(([category, count]) => ({
    category,
    count
  }))
);

const codeEvolutionStatusCount = computed(() => {
  const counts: Record<string, number> = {
    draft: 0,
    pending_validation: 0,
    validation_passed: 0,
    validation_failed: 0,
    accepted: 0,
    rejected: 0
  };
  for (const record of experienceCodeEvolution.value) {
    counts[record.status] = (counts[record.status] ?? 0) + 1;
  }
  return counts;
});

const reviewText = computed(() => {
  if (!latestScan.value) return "AI可以提出权重调整，但必须经过收益、最大回撤、胜率、盈亏比验证。";
  return `最近扫描产生 ${latestScan.value.strong_count} 个强候选、${latestScan.value.watch_count} 个观察候选；下一步可进入模拟交易计划生成。`;
});

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) throw new Error(`${url} returned ${response.status}`);
  return response.json() as Promise<T>;
}

async function loadSummary() {
  summary.value = await fetchJson<KnowledgeSummary>("/api/knowledge/summary");
}

async function loadLatestScan() {
  try {
    latestScan.value = await fetchJson<CandidateScan>("/api/candidates/latest");
  } catch {
    latestScan.value = null;
  }
}

async function loadLatestDiscovery() {
  try {
    const items = await fetchJson<AutoDiscoveryResult["items"]>("/api/candidates/auto-discovery/latest?limit=20");
    discovery.value = {
      status: "loaded",
      source: "local_auto_discovery",
      discovered_count: items.length,
      limit_up_count: items.filter((item) => item.discovery_type === "limit_up").length,
      near_limit_up_count: items.filter((item) => item.discovery_type === "near_limit_up").length,
      strong_mover_count: items.filter((item) => item.discovery_type === "strong_mover").length,
      items
    };
  } catch {
    discovery.value = null;
  }
}

async function loadLifecycleSummary() {
  try {
    lifecycleSummary.value = await fetchJson<CandidateLifecycleSummary>("/api/candidates/lifecycle/summary");
  } catch {
    lifecycleSummary.value = null;
  }
}

async function loadScores() {
  try {
    topScores.value = await fetchJson<CandidateScore[]>("/api/candidates/scores?limit=10");
  } catch {
    topScores.value = [];
  }
}

async function loadAccount() {
  account.value = await fetchJson<SimulationAccount>("/api/simulation/account");
}

async function loadAutomation() {
  try {
    automation.value = await fetchJson<AutomationRun>("/api/automation/latest");
  } catch {
    automation.value = null;
  }
}

async function loadLearningReport() {
  try {
    learningReport.value = await fetchJson<LearningReport>("/api/learning/reports/latest");
  } catch {
    learningReport.value = null;
  }
}

async function loadMonitoring() {
  try {
    const session = await fetchJson<{ summary?: MonitoringRun }>("/api/monitoring/sessions/latest");
    monitoring.value = session.summary?.events ? session.summary : null;
  } catch {
    monitoring.value = null;
  }
}

async function loadMonitoringReview() {
  try {
    const reviews = await fetchJson<MonitoringReview[]>("/api/monitoring/reviews?limit=1");
    monitoringReview.value = reviews[0] ?? null;
  } catch {
    monitoringReview.value = null;
  }
}

async function loadPhaseReplay() {
  try {
    phaseReplays.value = await fetchJson<PhaseReplay[]>("/api/learning/phase-replays?limit=2");
  } catch {
    phaseReplays.value = [];
  }
}

async function loadPhaseMatch() {
  try {
    const matches = await fetchJson<PhaseMatch[]>("/api/learning/phase-matches?limit=1");
    phaseMatch.value = matches[0] ?? null;
  } catch {
    phaseMatch.value = null;
  }
}

async function runScan() {
  loading.value = true;
  error.value = "";
  try {
    latestScan.value = await fetchJson<CandidateScan>("/api/candidates/local-scan?limit=100&persist=true");
    await loadLifecycleSummary();
    await loadScores();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "扫描失败";
  } finally {
    loading.value = false;
  }
}

async function runAutoDiscovery() {
  discoveryLoading.value = true;
  error.value = "";
  try {
    discovery.value = await fetchJson<AutoDiscoveryResult>("/api/candidates/auto-discovery?limit=80&persist=true", {
      method: "POST"
    });
    if (discovery.value.status === "failed") {
      error.value = discovery.value.error || "自动发现失败";
      return;
    }
    await runScan();
    await loadLifecycleSummary();
    await loadScores();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "自动发现失败";
  } finally {
    discoveryLoading.value = false;
  }
}

async function loadPlan() {
  const first = topCandidates.value[0];
  if (!first) return;
  planLoading.value = true;
  error.value = "";
  try {
    plan.value = await fetchJson<SimulationPlan>(`/api/simulation/plan/${first.symbol}`);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "模拟计划生成失败";
  } finally {
    planLoading.value = false;
  }
}

async function runAnalysis() {
  const first = topCandidates.value[0];
  if (!first) return;
  analysisLoading.value = true;
  error.value = "";
  try {
    analysis.value = await fetchJson<any>(`/api/decision/analyze-symbol/${first.symbol}`);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "分析生成失败";
  } finally {
    analysisLoading.value = false;
  }
}

async function runAutomation() {
  automationLoading.value = true;
  error.value = "";
  try {
    const cycle = await fetchJson<AutomationCycle>(
      "/api/automation/cycles/run-once?limit=5&monitor_limit=5&review_symbol=SZ002081",
      {
        method: "POST"
      }
    );
    automation.value = cycle.automation;
    if (cycle.automation.summary?.auto_discovery) {
      discovery.value = {
        status: cycle.automation.summary.auto_discovery.status,
        source: "automation_cycle",
        discovered_count: cycle.automation.summary.auto_discovery.discovered_count,
        limit_up_count: cycle.automation.summary.auto_discovery.limit_up_count,
        near_limit_up_count: cycle.automation.summary.auto_discovery.near_limit_up_count,
        strong_mover_count: cycle.automation.summary.auto_discovery.strong_mover_count,
        error: cycle.automation.summary.auto_discovery.error,
        items: []
      };
    }
    learningReport.value = cycle.learning_report ?? null;
    monitoring.value = cycle.monitoring ?? null;
    monitoringReview.value = cycle.monitoring_review ?? null;
    if (cycle.live_trading_enabled) {
      throw new Error("Live trading unexpectedly enabled");
    }
    await loadLatestScan();
    await loadLifecycleSummary();
    await loadScores();
    if (!learningReport.value) await loadLearningReport();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "automation cycle failed";
  } finally {
    automationLoading.value = false;
  }
}

async function runMonitoring() {
  monitoringLoading.value = true;
  error.value = "";
  try {
    monitoring.value = await fetchJson<MonitoringRun>("/api/monitoring/run-once?limit=5", {
      method: "POST"
    });
    monitoringReview.value = await fetchJson<MonitoringReview>("/api/monitoring/reviews/SZ002081", {
      method: "POST"
    });
  } catch (err) {
    error.value = err instanceof Error ? err.message : "监控运行失败";
  } finally {
    monitoringLoading.value = false;
  }
}

async function runPhaseReplay() {
  phaseReplayLoading.value = true;
  error.value = "";
  try {
    const result = await fetchJson<{ results: PhaseReplay[] }>("/api/learning/phase-replays/core-samples?lookback_years=3", {
      method: "POST"
    });
    phaseReplays.value = result.results;
    await loadLearningReport();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "阶段回放失败";
  } finally {
    phaseReplayLoading.value = false;
  }
}

async function runPhaseMatch() {
  phaseMatchLoading.value = true;
  error.value = "";
  try {
    phaseMatch.value = await fetchJson<PhaseMatch>(
      "/api/learning/phase-matches/SH600135?name=乐凯胶片&lookback_years=3",
      { method: "POST" }
    );
    await loadPhaseReplay();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "阶段匹配失败";
  } finally {
    phaseMatchLoading.value = false;
  }
}

async function loadPotentialSearch() {
  try {
    potentialSearch.value = await fetchJson<PotentialSearchRun>("/api/candidates/potential-search/latest");
  } catch {
    potentialSearch.value = null;
  }
}

async function runPotentialSearch() {
  potentialSearchLoading.value = true;
  error.value = "";
  try {
    potentialSearch.value = await fetchJson<PotentialSearchRun>(
      "/api/candidates/potential-search/run?limit=100&persist=true",
      { method: "POST" }
    );
    await loadScores();
    await loadLifecycleSummary();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "潜力搜索失败";
  } finally {
    potentialSearchLoading.value = false;
  }
}

async function loadAgentCapabilities() {
  try {
    agentCapabilities.value = await fetchJson<AgentCapabilities>("/api/agent-control/capabilities");
  } catch {
    agentCapabilities.value = null;
  }
}

async function loadAgentTasks() {
  try {
    agentTasks.value = await fetchJson<AgentTask[]>("/api/agent-control/tasks?limit=5");
  } catch {
    agentTasks.value = [];
  }
}

async function runAgentTask(taskType: string) {
  agentTaskLoading.value = true;
  error.value = "";
  try {
    await fetchJson(`/api/agent-control/tasks/run-now?task_type=${taskType}`, { method: "POST" });
    await loadAgentTasks();
    await loadAgentAudit();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Agent任务执行失败";
  } finally {
    agentTaskLoading.value = false;
  }
}

async function executeTask(id: number) {
  agentTaskLoading.value = true;
  error.value = "";
  try {
    await fetchJson(`/api/agent-control/tasks/${id}/run`, { method: "POST" });
    await loadAgentTasks();
    await loadAgentAudit();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "执行失败";
  } finally {
    agentTaskLoading.value = false;
  }
}

async function approveTask(id: number) {
  try {
    await fetchJson(`/api/agent-control/tasks/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ user: "admin", note: "Approved via UI" }),
      headers: { 'Content-Type': 'application/json' }
    });
    await loadAgentTasks();
    await loadAgentAudit();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "审批失败";
  }
}

async function rejectTask(id: number) {
  try {
    await fetchJson(`/api/agent-control/tasks/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ user: "admin", note: "Rejected via UI" }),
      headers: { 'Content-Type': 'application/json' }
    });
    await loadAgentTasks();
    await loadAgentAudit();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "拒绝失败";
  }
}

async function loadAgentAudit() {
  try {
    agentAudit.value = await fetchJson<any[]>("/api/agent-control/audit?limit=10");
  } catch {
    agentAudit.value = [];
  }
}

const potentialTopItems = computed(() => {
  if (!potentialSearch.value) return [];
  const items = potentialSearch.value.top_scored_items ?? potentialSearch.value.items ?? [];
  return items.slice(0, 5);
});

async function loadAgentLearningSamples() {
  try {
    agentLearningSamples.value = await fetchJson<AgentLearningSampleItem[]>("/api/learning/agent-samples?limit=10");
  } catch {
    agentLearningSamples.value = [];
  }
}

async function loadAgentLearningSummary() {
  try {
    agentLearningSummary.value = await fetchJson<AgentLearningSummaryData>("/api/learning/agent-samples/summary");
  } catch {
    agentLearningSummary.value = null;
  }
}

async function ingestAgentLearning() {
  agentLearningLoading.value = true;
  error.value = "";
  try {
    agentLearningIngestResult.value = await fetchJson<AgentLearningIngestResult>(
      "/api/learning/agent-samples/from-recent?limit=20",
      { method: "POST" }
    );
    await loadAgentLearningSamples();
    await loadAgentLearningSummary();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Agent学习收集失败";
  } finally {
    agentLearningLoading.value = false;
  }
}

async function loadAgentOutcomes() {
  try {
    agentOutcomes.value = await fetchJson<AgentLearningOutcomeItem[]>("/api/learning/agent-outcomes?limit=10");
  } catch {
    agentOutcomes.value = [];
  }
}

async function loadAgentOutcomeSummary() {
  try {
    agentOutcomeSummary.value = await fetchJson<AgentOutcomeSummaryData>("/api/learning/agent-outcomes/summary");
  } catch {
    agentOutcomeSummary.value = null;
  }
}

async function labelRecentOutcomes() {
  agentOutcomeLoading.value = true;
  error.value = "";
  try {
    await fetchJson("/api/learning/agent-outcomes/label-recent?limit=20&horizon_days=5", { method: "POST" });
    await loadAgentOutcomes();
    await loadAgentOutcomeSummary();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "评估结局失败";
  } finally {
    agentOutcomeLoading.value = false;
  }
}

function hasOutcomeReturns(outcome: AgentLearningOutcomeItem) {
  const metrics = outcome.metrics ?? {};
  return (
    typeof metrics.max_return === "number" &&
    typeof metrics.min_return === "number" &&
    typeof metrics.close_return === "number"
  );
}

function formatOutcomeMetric(outcome: AgentLearningOutcomeItem, key: "max_return" | "min_return" | "close_return") {
  const value = outcome.metrics?.[key];
  return typeof value === "number" ? value.toFixed(2) : "待数据";
}

const signalPerfRows = computed(() => {
  if (!signalPerformanceSummary.value) return [];
  const rows: Array<{ group: string; key: string; stats: SignalGroupStats }> = [];
  for (const [k, v] of Object.entries(signalPerformanceSummary.value.by_sample_type ?? {})) {
    rows.push({ group: "sample_type", key: k, stats: v });
  }
  for (const [k, v] of Object.entries(signalPerformanceSummary.value.by_label ?? {})) {
    rows.push({ group: "label", key: k, stats: v });
  }
  for (const [k, v] of Object.entries(signalPerformanceSummary.value.by_risk_flag ?? {})) {
    rows.push({ group: "risk_flag", key: k, stats: v });
  }
  return rows.slice(0, 20);
});

function proposalBorderClass(p: CalibrationProposalItem) {
  const action = p.proposal?.action;
  if (action === "increase_review_priority") return "proposal-strong";
  if (action === "reduce_score_contribution") return "proposal-weak";
  if (action === "wait_for_more_data" || action === "wait_for_future_data") return "proposal-wait";
  return "";
}

function codeEvolutionClass(record: CodeEvolutionRecord) {
  if (record.status === "accepted" || record.status === "validation_passed") return "proposal-strong";
  if (record.status === "rejected" || record.status === "validation_failed") return "proposal-weak";
  return "proposal-wait";
}

function modelReview(record: CodeEvolutionRecord): Record<string, any> | null {
  return (record.rationale?.model_review as Record<string, any> | undefined) ?? null;
}

function modelReviewSummary(record: CodeEvolutionRecord) {
  return String(modelReview(record)?.response?.explanation?.summary ?? "暂无摘要");
}

function modelReviewTags(record: CodeEvolutionRecord): string[] {
  const tags = modelReview(record)?.response?.attribution?.tags;
  return Array.isArray(tags) ? tags.map((tag) => String(tag)).slice(0, 6) : [];
}

function modelReviewSimilarCount(record: CodeEvolutionRecord) {
  const groups = modelReview(record)?.response?.similar_groups;
  if (!Array.isArray(groups)) return 0;
  return groups.reduce((total, group) => total + Number(group?.count ?? 0), 0);
}

function modelReviewSafetyBlocks(record: CodeEvolutionRecord): string[] {
  const blocks = modelReview(record)?.safety?.safety_blocks_applied;
  return Array.isArray(blocks) ? blocks.map((block) => String(block)) : [];
}

async function loadSignalPerformanceSummary() {
  try {
    signalPerformanceSummary.value = await fetchJson<SignalPerformanceSummaryData>("/api/learning/signal-performance/summary");
  } catch {
    signalPerformanceSummary.value = null;
  }
}

async function loadCalibrationProposals() {
  try {
    calibrationProposals.value = await fetchJson<CalibrationProposalItem[]>("/api/learning/calibration-proposals?limit=20");
  } catch {
    calibrationProposals.value = [];
  }
}

async function generateCalibrationProposals() {
  calibrationLoading.value = true;
  error.value = "";
  try {
    await fetchJson("/api/learning/calibration-proposals/generate", { method: "POST" });
    await loadCalibrationProposals();
    await loadSignalPerformanceSummary();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "校准提案生成失败";
  } finally {
    calibrationLoading.value = false;
  }
}

async function approveCalibrationProposal(id: number) {
  try {
    await fetchJson(`/api/learning/calibration-proposals/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ user: "admin", note: "Approved via UI" }),
      headers: { 'Content-Type': 'application/json' }
    });
    await loadCalibrationProposals();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "审批失败";
  }
}

async function rejectCalibrationProposal(id: number) {
  try {
    await fetchJson(`/api/learning/calibration-proposals/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ user: "admin", note: "Rejected via UI" }),
      headers: { 'Content-Type': 'application/json' }
    });
    await loadCalibrationProposals();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "拒绝失败";
  }
}

function sandboxConclusionClass(exp: SandboxExperimentItem) {
  const c = exp.conclusion;
  if (c === 'priority_increase_viable' || c === 'reduction_justified') return 'proposal-strong';
  if (c === 'reduction_high_collateral') return 'proposal-weak';
  if (c === 'insufficient_evidence' || c === 'no_behavior_change') return 'proposal-wait';
  return '';
}

async function loadSandboxExperiments() {
  try {
    sandboxExperiments.value = await fetchJson<SandboxExperimentItem[]>("/api/learning/sandbox-experiments?limit=10");
  } catch {
    sandboxExperiments.value = [];
  }
}

async function loadSandboxSummary() {
  try {
    sandboxSummary.value = await fetchJson<SandboxSummaryData>("/api/learning/sandbox-experiments/summary");
  } catch {
    sandboxSummary.value = null;
  }
}

async function runSandboxApproved() {
  sandboxLoading.value = true;
  error.value = "";
  try {
    await fetchJson("/api/learning/sandbox-experiments/run-approved?limit=20", { method: "POST" });
    await loadSandboxExperiments();
    await loadSandboxSummary();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "沙盒实验执行失败";
  } finally {
    sandboxLoading.value = false;
  }
}

function policyStatusClass(p: SimulationPolicyItem) {
  if (p.status === 'approved') return 'proposal-strong';
  if (p.status === 'rejected') return 'proposal-weak';
  if (p.status === 'draft') return 'proposal-wait';
  return '';
}

async function loadPaperSimPolicies() {
  try {
    paperSimPolicies.value = await fetchJson<SimulationPolicyItem[]>("/api/learning/simulation-policies?limit=20");
  } catch {
    paperSimPolicies.value = [];
  }
}

async function loadPaperSimRuns() {
  try {
    paperSimRuns.value = await fetchJson<PaperSimulationRunItem[]>("/api/learning/paper-simulations?limit=10");
  } catch {
    paperSimRuns.value = [];
  }
}

async function loadPaperSimSummary() {
  try {
    paperSimSummary.value = await fetchJson<PaperSimulationSummaryData>("/api/learning/paper-simulations/summary");
  } catch {
    paperSimSummary.value = null;
  }
}

async function draftSimPolicies() {
  paperSimLoading.value = true;
  error.value = "";
  try {
    await fetchJson("/api/learning/simulation-policies/draft-from-experiments?limit=20", { method: "POST" });
    await loadPaperSimPolicies();
    await loadPaperSimSummary();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "生成模拟策略草稿失败";
  } finally {
    paperSimLoading.value = false;
  }
}

async function approveSimPolicy(id: number) {
  try {
    await fetchJson(`/api/learning/simulation-policies/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ user: "admin", note: "Approved via UI" }),
      headers: { 'Content-Type': 'application/json' }
    });
    await loadPaperSimPolicies();
    await loadPaperSimSummary();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "审批失败";
  }
}

async function rejectSimPolicy(id: number) {
  try {
    await fetchJson(`/api/learning/simulation-policies/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ user: "admin", note: "Rejected via UI" }),
      headers: { 'Content-Type': 'application/json' }
    });
    await loadPaperSimPolicies();
    await loadPaperSimSummary();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "拒绝失败";
  }
}

async function runApprovedSimulations() {
  paperSimLoading.value = true;
  error.value = "";
  try {
    await fetchJson("/api/learning/paper-simulations/run-approved?limit=20", { method: "POST" });
    await loadPaperSimRuns();
    await loadPaperSimSummary();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "运行模拟失败";
  } finally {
    paperSimLoading.value = false;
  }
}

function evalConclusionClass(conclusion: string) {
  if (conclusion === 'promising_simulation_policy') return 'proposal-strong';
  if (conclusion === 'weak_simulation_policy') return 'proposal-weak';
  if (conclusion === 'mixed_or_unproven_policy') return 'proposal-wait';
  return '';
}

async function loadPaperSimEvalSummary() {
  try {
    paperSimEvalSummary.value = await fetchJson<PaperSimulationEvaluationSummaryData>("/api/learning/paper-simulation-evaluations/summary");
  } catch {
    paperSimEvalSummary.value = null;
  }
}

async function loadPaperSimEvalPolicies() {
  try {
    paperSimEvalPolicies.value = await fetchJson<PaperSimulationPolicyConclusion[]>("/api/learning/paper-simulation-evaluations/policies");
  } catch {
    paperSimEvalPolicies.value = [];
  }
}

async function evaluateRecentSimulations() {
  paperSimEvalLoading.value = true;
  error.value = "";
  try {
    await fetchJson("/api/learning/paper-simulation-evaluations/evaluate-recent?limit=100&horizon_days=5", { method: "POST" });
    await loadPaperSimEvalSummary();
    await loadPaperSimEvalPolicies();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "评估模拟动作失败";
  } finally {
    paperSimEvalLoading.value = false;
  }
}

async function loadPriceReadinessReports() {
  try {
    priceReadinessReports.value = await fetchJson<PriceReadinessReport[]>("/api/data/price-readiness/latest?limit=20");
  } catch {
    priceReadinessReports.value = [];
  }
}

async function loadPriceReadinessSummary() {
  try {
    const results = await Promise.allSettled([
      fetch("/api/data/price-readiness/summary").then((r) => r.json()).then((data) => {
        priceReadinessSummary.value = data;
      }),
      fetch("/api/data/price-readiness/latest?limit=50").then((r) => r.json()).then((data) => {
        priceReadinessReports.value = data;
      }),
      fetch("/api/data/daily-bars/coverage?limit=50").then((r) => r.json()).then((data) => {
        dailyBarCoverage.value = data;
      })
    ]);
  } catch {
    priceReadinessSummary.value = null;
  }
}

async function runPriceReadiness() {
  priceReadinessLoading.value = true;
  error.value = "";
  try {
    await fetchJson("/api/data/price-readiness/run?limit=100", { method: "POST" });
    await loadPriceReadinessReports();
    await loadPriceReadinessSummary();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "价格就绪检查失败";
  } finally {
    priceReadinessLoading.value = false;
  }
}

async function runDailyBarRefresh() {
  dailyBarRefreshLoading.value = true;
  error.value = "";
  try {
    await fetchJson("/api/data/daily-bars/refresh?limit=50&days=120", { method: "POST" });
    await loadPriceReadinessSummary();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "日线缓存刷新失败";
  } finally {
    dailyBarRefreshLoading.value = false;
  }
}

async function loadRealtimeData() {
  realtimeLoading.value = true;
  try {
    const [capabilitiesData, healthData, snapshotData, eventsData] = await Promise.all([
      fetchJson<RealtimeCapabilities>("/api/realtime/capabilities"),
      fetchJson<RealtimeProviderHealth[]>("/api/realtime/provider-health"),
      fetchJson<RealtimeSnapshot>("/api/realtime/snapshot/SZ002081"),
      fetchJson<RealtimeEvent[]>("/api/realtime/events?limit=20")
    ]);
    realtimeCapabilities.value = capabilitiesData;
    realtimeHealth.value = healthData;
    realtimeSnapshot.value = snapshotData;
    realtimeEvents.value = eventsData;
  } catch (err) {
    realtimeCapabilities.value = null;
    realtimeHealth.value = [];
    realtimeSnapshot.value = null;
    realtimeEvents.value = [];
    error.value = err instanceof Error ? err.message : "实时行情状态加载失败";
  } finally {
    realtimeLoading.value = false;
  }
}

async function refreshRealtimeEvents() {
  realtimeLoading.value = true;
  error.value = "";
  try {
    realtimeRefreshResult.value = await fetchJson<RealtimeRefreshResult>(
      "/api/realtime/refresh?symbols=SZ002081,SZ002115&limit=20",
      { method: "POST" }
    );
    await loadRealtimeData();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "实时事件刷新失败";
  } finally {
    realtimeLoading.value = false;
  }
}

async function syncRealtimeMonitoring() {
  realtimeLoading.value = true;
  error.value = "";
  try {
    realtimeMonitoringSync.value = await fetchJson<RealtimeMonitoringSyncResult>(
      "/api/realtime/monitoring-sync?limit=100",
      { method: "POST" }
    );
    await loadRealtimeData();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "实时监控提醒同步失败";
  } finally {
    realtimeLoading.value = false;
  }
}

async function runRealtimeCycle() {
  realtimeLoading.value = true;
  error.value = "";
  try {
    realtimeCycleResult.value = await fetchJson<RealtimeCycleResult>(
      "/api/realtime/cycle?symbols=SZ002081,SZ002115&refresh_limit=20&sync_limit=100&replay_limit=100",
      { method: "POST" }
    );
    realtimeRefreshResult.value = realtimeCycleResult.value.steps.refresh;
    realtimeMonitoringSync.value = realtimeCycleResult.value.steps.monitoring_sync;
    realtimeReplay.value = realtimeCycleResult.value.steps.replay;
    await loadRealtimeData();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "实时闭环运行失败";
  } finally {
    realtimeLoading.value = false;
  }
}

async function runRealtimeReplay() {
  realtimeLoading.value = true;
  error.value = "";
  try {
    realtimeReplay.value = await fetchJson<RealtimeReplay>("/api/realtime/replay?limit=100", { method: "POST" });
    await loadRealtimeData();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "实时信号 Replay 失败";
  } finally {
    realtimeLoading.value = false;
  }
}

async function loadBacktestRuns() {
  try {
    backtestRuns.value = await fetchJson<BacktestRunItem[]>("/api/backtest/runs?limit=10");
    if (backtestRuns.value[0]?.id) {
      backtestDetail.value = await fetchJson<BacktestDetail>(`/api/backtest/runs/${backtestRuns.value[0].id}`);
    } else {
      backtestDetail.value = null;
    }
  } catch {
    backtestRuns.value = [];
    backtestDetail.value = null;
  }
}

async function runBacktest() {
  v15Loading.value = true;
  error.value = "";
  try {
    const end = new Date();
    const start = new Date(end.getTime() - 90 * 24 * 60 * 60 * 1000);
    await fetchJson("/api/backtest/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        start_date: start.toISOString().slice(0, 10),
        end_date: end.toISOString().slice(0, 10),
        symbols: [],
        initial_cash: 100000,
        max_positions: 5,
        per_symbol_cap: 0.2,
        benchmark_symbol: "SH000300",
      }),
    });
    await loadBacktestRuns();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "回测运行失败";
  } finally {
    v15Loading.value = false;
  }
}

async function loadMarketRegime() {
  try {
    marketRegime.value = await fetchJson<MarketRegimeData>("/api/market-regime/latest");
  } catch {
    marketRegime.value = null;
  }
}

async function refreshMarketRegime() {
  v15Loading.value = true;
  error.value = "";
  try {
    marketRegime.value = await fetchJson<MarketRegimeData>("/api/market-regime/refresh", { method: "POST" });
    await loadPortfolioRisk();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "刷新大盘环境失败";
  } finally {
    v15Loading.value = false;
  }
}

async function loadPortfolioRisk() {
  try {
    portfolioRisk.value = await fetchJson<PortfolioRiskData>("/api/risk/portfolio-state");
  } catch {
    portfolioRisk.value = null;
  }
}

async function loadMonitoringLifecycle() {
  try {
    monitoringLifecycle.value = await fetchJson<MonitoringLifecycleData>("/api/monitoring/lifecycle?limit=20");
  } catch {
    monitoringLifecycle.value = null;
  }
}

async function acknowledgeAlert(alertId: number) {
  await actionAlert(alertId, "acknowledge");
}

async function actionAlert(alertId: number, actionType: string) {
  try {
    await fetchJson(`/api/monitoring/alerts/${alertId}/action?action_type=${encodeURIComponent(actionType)}`, { method: "POST" });
    await loadMonitoringLifecycle();
    await loadLifecycleSummary();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "告警动作失败";
  }
}

async function loadAiProposals() {
  try {
    aiProposals.value = await fetchJson<AIProposalItem[]>("/api/ai/review/proposals?limit=20");
  } catch {
    aiProposals.value = [];
  }
}

async function runAiReview() {
  v15Loading.value = true;
  error.value = "";
  try {
    await fetchJson("/api/ai/review/run", { method: "POST" });
    await loadAiProposals();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "AI提案生成失败";
  } finally {
    v15Loading.value = false;
  }
}

async function validateAiProposal(id: number) {
  try {
    await fetchJson(`/api/ai/review/proposals/${id}/validate`, { method: "POST" });
    await loadAiProposals();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "AI提案验证失败";
  }
}

async function rejectAiProposal(id: number) {
  try {
    await fetchJson(`/api/ai/review/proposals/${id}/reject`, { method: "POST" });
    await loadAiProposals();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "AI提案拒绝失败";
  }
}

async function loadExperienceMemory() {
  try {
    const [summaryData, reviewsData, eventsData, strategyData, codeEvolutionData] = await Promise.all([
      fetchJson<ExperienceSummaryData>("/api/experience/summary"),
      fetchJson<ExperienceReviewItem[]>("/api/experience/reviews?limit=10"),
      fetchJson<ExperienceEventItem[]>("/api/experience/events?limit=30"),
      fetchJson<StrategyPerformanceSnapshot[]>("/api/experience/strategy-performance?limit=10"),
      fetchJson<CodeEvolutionRecord[]>("/api/experience/code-evolution?limit=20")
    ]);
    experienceSummary.value = summaryData;
    experienceReviews.value = reviewsData;
    experienceEvents.value = eventsData;
    experienceStrategyPerformance.value = strategyData;
    experienceCodeEvolution.value = codeEvolutionData;
  } catch {
    experienceSummary.value = null;
    experienceReviews.value = [];
    experienceEvents.value = [];
    experienceStrategyPerformance.value = [];
    experienceCodeEvolution.value = [];
  }
}

async function loadAIModelCapabilities() {
  try {
    aiModelCapabilities.value = await fetchJson<AIModelCapabilities>("/api/ai/model/capabilities");
  } catch {
    aiModelCapabilities.value = null;
  }
}

async function loadAIModelAuditLogs() {
  aiModelLoading.value = true;
  try {
    aiModelAuditLogs.value = await fetchJson<AIModelAuditLog[]>(
      "/api/ai/model/audit-logs?operation=code_evolution_explanation&limit=20"
    );
  } catch {
    aiModelAuditLogs.value = [];
  } finally {
    aiModelLoading.value = false;
  }
}

async function explainCodeEvolutionWithModel(id: number) {
  aiModelLoading.value = true;
  error.value = "";
  try {
    await fetchJson(`/api/ai/model/explain-code-evolution/${id}`, { method: "POST" });
    await Promise.all([loadExperienceMemory(), loadAIModelAuditLogs()]);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "AI解释生成失败";
  } finally {
    aiModelLoading.value = false;
  }
}

async function generateCodeEvolutionReviews() {
  codeEvolutionLoading.value = true;
  error.value = "";
  try {
    await fetchJson("/api/experience/code-evolution/generate?limit=5", { method: "POST" });
    await loadExperienceMemory();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "代码进化建议生成失败";
  } finally {
    codeEvolutionLoading.value = false;
  }
}

async function approveCodeEvolution(id: number) {
  codeEvolutionLoading.value = true;
  error.value = "";
  try {
    await fetchJson(`/api/experience/code-evolution/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewed_by: "user", note: "accepted from dashboard" })
    });
    await loadExperienceMemory();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "代码进化建议接受失败";
  } finally {
    codeEvolutionLoading.value = false;
  }
}

async function rejectCodeEvolution(id: number) {
  codeEvolutionLoading.value = true;
  error.value = "";
  try {
    await fetchJson(`/api/experience/code-evolution/${id}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewed_by: "user", note: "rejected from dashboard" })
    });
    await loadExperienceMemory();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "代码进化建议拒绝失败";
  } finally {
    codeEvolutionLoading.value = false;
  }
}

async function runExperienceReview() {
  experienceLoading.value = true;
  error.value = "";
  try {
    await fetchJson("/api/experience/reviews/daily", { method: "POST" });
    await loadExperienceMemory();
    await loadLearningReport();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "经验复盘生成失败";
  } finally {
    experienceLoading.value = false;
  }
}

onMounted(async () => {
  const results = await Promise.allSettled([
    loadSummary(),
    loadLatestDiscovery(),
    loadLifecycleSummary(),
    loadScores(),
    loadLatestScan(),
    loadAccount(),
    loadAutomation(),
    loadLearningReport(),
    loadMonitoring(),
    loadMonitoringReview(),
    loadPhaseReplay(),
    loadPhaseMatch(),
    loadPotentialSearch(),
    loadAgentCapabilities(),
    loadAgentTasks(),
    loadAgentAudit(),
    loadAgentLearningSamples(),
    loadAgentLearningSummary(),
    loadAgentOutcomes(),
    loadAgentOutcomeSummary(),
    loadSignalPerformanceSummary(),
    loadCalibrationProposals(),
    loadSandboxExperiments(),
    loadSandboxSummary(),
    loadPaperSimPolicies(),
    loadPaperSimRuns(),
    loadPaperSimSummary(),
    loadPaperSimEvalSummary(),
    loadPaperSimEvalPolicies(),
    loadPriceReadinessReports(),
    loadPriceReadinessSummary(),
    loadRealtimeData(),
    loadBacktestRuns(),
    loadMarketRegime(),
    loadPortfolioRisk(),
    loadMonitoringLifecycle(),
    loadAiProposals(),
    loadExperienceMemory(),
    loadAIModelCapabilities(),
    loadAIModelAuditLogs()
  ]);
  const firstError = results.find((item) => item.status === "rejected");
  if (firstError && firstError.status === "rejected") {
    error.value = firstError.reason instanceof Error ? firstError.reason.message : "部分数据加载失败";
  }
});
</script>

<style scoped>
:global(body) {
  margin: 0;
  font-family: "Microsoft YaHei", Arial, sans-serif;
  background: #f3f5f7;
  color: #17202a;
}

.shell {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
}

.top-actions {
  display: flex;
  gap: 10px;
}

.eyebrow {
  margin: 0 0 6px;
  color: #5e6b78;
  font-size: 13px;
}

.status {
  margin: 8px 0 0;
  color: #5e6b78;
}

h1,
h2,
p {
  margin-top: 0;
}

h1 {
  font-size: 28px;
  margin-bottom: 0;
}

h2 {
  font-size: 18px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.panel {
  background: #ffffff;
  border: 1px solid #d9e0e7;
  border-radius: 8px;
  padding: 18px;
}

.wide {
  grid-column: 1 / -1;
}

.tier {
  border-left: 4px solid #8a96a3;
  padding: 10px 12px;
  margin-top: 10px;
  background: #f8fafb;
  display: grid;
  gap: 4px;
}

.strong {
  border-color: #d23f31;
}

.watch {
  border-color: #c18c1d;
}

.rejected {
  border-color: #56616d;
}

.metrics,
.knowledge,
.account,
.lifecycle {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.metrics span,
.knowledge span,
.account span,
.lifecycle span {
  background: #eef3f7;
  border: 1px solid #d8e0e8;
  border-radius: 6px;
  padding: 8px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.plan,
.report {
  display: grid;
  gap: 5px;
  margin-top: 14px;
  padding: 12px;
  border: 1px solid #d9e0e7;
  border-radius: 8px;
  background: #f8fafb;
}

.score-list {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}

.score-item {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid #d9e0e7;
  border-left: 4px solid #2b7a78;
  border-radius: 8px;
  background: #f8fafb;
}

button {
  border: 0;
  border-radius: 6px;
  padding: 10px 14px;
  background: #1f6feb;
  color: #fff;
  cursor: pointer;
}

button:disabled,
.ghost,
.disabled-live {
  background: #d9dee5;
  color: #66717d;
  cursor: not-allowed;
}

.potential-errors {
  display: grid;
  gap: 4px;
  margin-bottom: 8px;
  color: #b55a00;
}

.review-only-banner {
  background: #fef3cd;
  border: 1px solid #ffc107;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 13px;
  color: #856404;
  margin-bottom: 10px;
}

.small-sample-warn {
  color: #b55a00;
  font-weight: 600;
}

.proposal-strong {
  border-left-color: #28a745 !important;
}

.proposal-weak {
  border-left-color: #dc3545 !important;
}

.proposal-wait {
  border-left-color: #ffc107 !important;
}

@media (max-width: 720px) {
  .grid {
    grid-template-columns: 1fr;
  }

  .topbar {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
