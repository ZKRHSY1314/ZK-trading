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
          <span>调度 {{ realtimeSchedulerPlan?.status ?? "未加载" }}</span>
          <span>提案 {{ realtimeAutomationProposal?.proposal_count ?? 0 }}</span>
          <span>实盘 {{ realtimeCapabilities?.live_trading_enabled ? "开启" : "关闭" }}</span>
        </div>
        <div v-if="realtimeSchedulerPlan" class="score-list">
          <div class="score-item">
            <strong>Scheduler / {{ realtimeSchedulerPlan.status }}</strong>
            <span>模式 {{ realtimeSchedulerPlan.recommended_mode }} / 标的 {{ realtimeSchedulerPlan.recommended_symbols.join(", ") }}</span>
            <small>{{ realtimeSchedulerPlan.cadence.workday_trading_hours.map((item) => item.time).join(" / ") }} / live trading disabled</small>
          </div>
          <div class="score-item">
            <strong>Pause / Degrade</strong>
            <span>{{ realtimeSchedulerPlan.pause_controls[0] }}</span>
            <small>{{ realtimeSchedulerPlan.degrade_controls[0] }}</small>
          </div>
        </div>
        <div v-if="realtimeAutomationProposal" class="score-list">
          <div
            v-for="proposal in realtimeAutomationProposal.proposals"
            :key="proposal.id"
            class="score-item"
          >
            <strong>{{ proposal.name }} / {{ proposal.status }}</strong>
            <span>{{ proposal.cadence_text }}</span>
            <small>{{ proposal.mode }} / {{ proposal.default_status }} / {{ proposal.command }}</small>
          </div>
          <div class="score-item">
            <strong>Automation Guardrails</strong>
            <span>{{ realtimeAutomationProposal.acceptance_checks[0] }}</span>
            <small>{{ realtimeAutomationProposal.forbidden_actions.join(" / ") }}</small>
          </div>
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
            <strong>Realtime Cycle / {{ realtimeCycleResult.status }} / #{{ realtimeCycleResult.run_id ?? "new" }}</strong>
            <span>刷新 {{ realtimeCycleResult.summary.refreshed_count }} / 失败 {{ realtimeCycleResult.summary.refresh_failed_count }} / Replay {{ realtimeCycleResult.summary.replay_event_count }}</span>
            <small>提醒 {{ realtimeCycleResult.summary.created_alert_count }} / fallback {{ realtimeCycleResult.summary.fallback_required ? "required" : "not required" }}</small>
          </div>
        </div>
        <div v-if="realtimeCycleRuns.length" class="score-list">
          <div v-for="run in realtimeCycleRuns.slice(0, 5)" :key="run.id" class="score-item">
            <strong>Cycle #{{ run.id }} / {{ run.status }}</strong>
            <span>刷新 {{ run.refreshed_count }} / 失败 {{ run.refresh_failed_count }} / 提醒 {{ run.created_alert_count }} / Replay {{ run.replay_event_count }}</span>
            <small>{{ run.created_at }} / provider {{ run.provider ?? "disabled" }} / fallback {{ run.fallback_required ? "required" : "not required" }}</small>
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
        <h2>V4.5 屏幕只读监控</h2>
        <p class="review-only-banner">只记录屏幕观测证据；不读取真实像素、不 OCR、不点击、不输入、不下单。</p>
        <div class="actions">
          <button data-testid="mock-screen-observation-button" @click="recordMockScreenObservation" :disabled="screenMonitoringLoading">
            {{ screenMonitoringLoading ? "记录中" : "记录只读观测样本" }}
          </button>
          <button data-testid="fixture-screen-replay-button" @click="replayScreenFixture" :disabled="screenMonitoringLoading">
            回放屏幕 Fixture
          </button>
          <button data-testid="screen-preflight-button" @click="runScreenCapturePreflight" :disabled="screenMonitoringLoading">
            截图预检
          </button>
          <button data-testid="screen-capture-stub-button" @click="runScreenCaptureStub" :disabled="screenMonitoringLoading">
            生成截图 Artifact Stub
          </button>
          <button data-testid="screen-artifact-sync-button" @click="syncScreenArtifactReviews" :disabled="screenMonitoringLoading">
            同步 Artifact 复核
          </button>
          <button data-testid="screen-config-proposal-button" @click="generateScreenProviderConfigProposal" :disabled="screenMonitoringLoading">
            生成 local-safe 配置提案
          </button>
          <button data-testid="screen-provider-replay-button" @click="runScreenProviderReplay" :disabled="screenMonitoringLoading">
            运行 Provider Replay
          </button>
          <button data-testid="screen-readiness-audit-button" @click="refreshScreenReadinessAudit" :disabled="screenMonitoringLoading">
            生成 Readiness Audit
          </button>
          <button data-testid="screen-readiness-ack-button" @click="acknowledgeScreenReadinessAudit" :disabled="screenMonitoringLoading">
            确认 Audit 已审阅
          </button>
          <button data-testid="screen-readiness-timeline-button" @click="refreshScreenReadinessTimeline" :disabled="screenMonitoringLoading">
            刷新 Timeline
          </button>
          <button data-testid="screen-readiness-export-button" @click="refreshScreenReadinessExport" :disabled="screenMonitoringLoading">
            生成 Evidence Export
          </button>
          <button data-testid="screen-readiness-verify-button" @click="verifyScreenReadinessExport" :disabled="screenMonitoringLoading">
            校验证据包
          </button>
          <button data-testid="screen-readiness-compare-button" @click="compareScreenReadinessEvidence" :disabled="screenMonitoringLoading">
            对比证据稳定性
          </button>
          <button data-testid="screen-readiness-health-button" @click="refreshScreenReadinessHealth" :disabled="screenMonitoringLoading">
            生成健康摘要
          </button>
          <button data-testid="screen-digest-history-proposal-button" @click="refreshScreenDigestHistoryProposal" :disabled="screenMonitoringLoading">
            历史保留方案
          </button>
          <button data-testid="screen-digest-migration-checklist-button" @click="refreshScreenDigestMigrationChecklist" :disabled="screenMonitoringLoading">
            迁移就绪清单
          </button>
          <button data-testid="screen-digest-migration-spec-button" @click="verifyScreenDigestMigrationSpec" :disabled="screenMonitoringLoading">
            校验迁移草案
          </button>
          <button data-testid="screen-digest-migration-spec-approval-button" @click="approveScreenDigestMigrationSpec" :disabled="screenMonitoringLoading">
            确认草案已审阅
          </button>
          <button data-testid="screen-digest-migration-release-button" @click="refreshScreenDigestReleaseReadiness" :disabled="screenMonitoringLoading">
            发布就绪汇总
          </button>
          <button data-testid="screen-digest-approval-review-button" @click="refreshScreenDigestApprovalReview" :disabled="screenMonitoringLoading">
            审批有效期复核
          </button>
          <button data-testid="screen-digest-release-package-button" @click="refreshScreenDigestReleasePackage" :disabled="screenMonitoringLoading">
            最终发布包清单
          </button>
          <button @click="loadScreenMonitoring" :disabled="screenMonitoringLoading">刷新观测证据</button>
        </div>
        <div class="metrics">
          <span>阶段 {{ screenMonitoringCapabilities?.stage ?? "V4.5-P1" }}</span>
          <span>采集 {{ screenMonitoringCapabilities?.capture_provider ?? "disabled" }}</span>
          <span>Provider {{ screenMonitoringCapabilities?.provider_status ?? "disabled" }}</span>
          <span>Readiness {{ screenProviderReadiness?.status ?? "未加载" }}</span>
          <span>OCR {{ screenMonitoringCapabilities?.ocr_provider ?? "not_configured" }}</span>
          <span>观测 {{ screenObservations.length }}</span>
          <span>Artifact {{ screenArtifactReviews.length }}</span>
          <span>配置提案 {{ screenProviderConfigProposals.length }}</span>
          <span>Replay {{ screenProviderReplayRuns.length }}</span>
          <span>Audit {{ screenReadinessAudit?.status ?? "未加载" }}</span>
          <span>确认 {{ screenReadinessAuditAcks.length }}</span>
          <span>Timeline {{ screenReadinessTimeline?.item_count ?? 0 }}</span>
          <span>Export {{ screenReadinessExport?.status ?? "未生成" }}</span>
          <span>Verify {{ screenReadinessVerification?.status ?? "未校验" }}</span>
          <span>Compare {{ screenReadinessComparison?.status ?? "未对比" }}</span>
          <span>Health {{ screenReadinessHealth?.status ?? "未生成" }}</span>
          <span>History {{ screenDigestHistoryProposal?.status ?? "未生成" }}</span>
          <span>Migration {{ screenDigestMigrationChecklist?.status ?? "未生成" }}</span>
          <span>Spec {{ screenDigestMigrationSpecVerification?.status ?? "未校验" }}</span>
          <span>Spec审批 {{ screenDigestMigrationSpecApprovals.length }}</span>
          <span>Release {{ screenDigestReleaseReadiness?.status ?? "未生成" }}</span>
          <span>Approval {{ screenDigestApprovalReview?.status ?? "未复核" }}</span>
          <span>Package {{ screenDigestReleasePackage?.status ?? "未生成" }}</span>
          <span>会话 {{ screenMonitoringSession?.status ?? "empty" }}</span>
          <span>实盘 {{ screenMonitoringCapabilities?.live_trading_enabled ? "开启" : "关闭" }}</span>
        </div>
        <div v-if="screenMonitoringCapabilities" class="score-list">
          <div class="score-item">
            <strong>Read-only Guardrails / {{ screenMonitoringCapabilities.status }}</strong>
            <span>{{ screenMonitoringCapabilities.allowed_modes.join(" / ") }}</span>
            <small>禁止 {{ screenMonitoringCapabilities.forbidden_modes.join(" / ") }}</small>
          </div>
          <div v-for="provider in screenMonitoringProviders" :key="provider.provider" class="score-item">
            <strong>{{ provider.provider }} / {{ provider.status }}</strong>
            <span>配置 {{ provider.configured ? "已配置" : "未配置" }} / fixture {{ provider.fixture_replay_supported ? "enabled" : "disabled" }}</span>
            <small>真实截图 {{ provider.capture_supported ? "可用" : "关闭" }} / OCR {{ provider.ocr_supported ? "可用" : "关闭" }}</small>
          </div>
          <div v-if="screenProviderReadiness" class="score-item">
            <strong>Provider Readiness / {{ screenProviderReadiness.status }}</strong>
            <span>{{ screenProviderReadiness.active_provider }} / {{ screenProviderReadiness.provider_status }}</span>
            <small>{{ screenProviderReadiness.next_safe_steps.slice(0, 2).join("；") }}</small>
          </div>
          <div
            v-for="check in screenProviderReadiness?.checks.slice(0, 6) ?? []"
            :key="check.name"
            class="score-item"
          >
            <strong>{{ check.name }} / {{ check.status }}</strong>
            <span>{{ check.value || "未设置" }} / 期望 {{ check.expected }}</span>
            <small>{{ check.reason }}</small>
          </div>
          <div v-if="screenMonitoringSession && screenMonitoringSession.status !== 'empty'" class="score-item">
            <strong>Session #{{ screenMonitoringSession.id }} / {{ screenMonitoringSession.status }}</strong>
            <span>观测 {{ screenMonitoringSession.summary.observation_count }} / 警告 {{ screenMonitoringSession.summary.warning_count }}</span>
            <small>{{ screenMonitoringSession.window_title ?? "未记录窗口" }} / live trading disabled</small>
          </div>
          <div v-if="screenFixtureReplayResult" class="score-item">
            <strong>Fixture Replay / {{ screenFixtureReplayResult.status }}</strong>
            <span>{{ screenFixtureReplayResult.fixture_name }} / {{ screenFixtureReplayResult.observation.app_status }}</span>
            <small>真实截图 {{ screenFixtureReplayResult.real_screen_capture ? "是" : "否" }} / OCR {{ screenFixtureReplayResult.ocr_executed ? "是" : "否" }}</small>
          </div>
          <div v-if="screenPreflightResult" class="score-item">
            <strong>Capture Preflight / {{ screenPreflightResult.status }}</strong>
            <span>{{ screenPreflightResult.target_window_title ?? "未指定窗口" }} / {{ screenPreflightResult.reason }}</span>
            <small>允许 {{ screenPreflightResult.capture_would_be_allowed ? "是" : "否" }} / 真实截图 {{ screenPreflightResult.real_screen_capture ? "是" : "否" }} / OCR {{ screenPreflightResult.ocr_executed ? "是" : "否" }}</small>
          </div>
          <div v-if="screenCaptureStubResult" class="score-item">
            <strong>Capture Stub / {{ screenCaptureStubResult.status }}</strong>
            <span>{{ screenCaptureStubResult.artifact_status }} / {{ screenCaptureStubResult.artifact_ref ?? "未生成 artifact" }}</span>
            <small>像素保存 {{ screenCaptureStubResult.pixel_data_stored ? "是" : "否" }} / 真实截图 {{ screenCaptureStubResult.real_screen_capture ? "是" : "否" }} / OCR {{ screenCaptureStubResult.ocr_executed ? "是" : "否" }}</small>
          </div>
          <div v-if="screenArtifactPolicy" class="score-item">
            <strong>Retention Policy / {{ screenArtifactPolicy.status }}</strong>
            <span>保留 {{ screenArtifactPolicy.retention_days }} 天 / 队列 {{ screenArtifactPolicy.max_review_queue_items }}</span>
            <small>像素保存 {{ screenArtifactPolicy.pixel_data_stored ? "是" : "否" }} / OCR {{ screenArtifactPolicy.ocr_executed ? "是" : "否" }} / {{ screenArtifactPolicy.review_queue.decision_effect }}</small>
          </div>
          <div v-if="screenArtifactSyncResult" class="score-item">
            <strong>Artifact Sync / {{ screenArtifactSyncResult.status }}</strong>
            <span>新增 {{ screenArtifactSyncResult.created_review_count }} / 已存在 {{ screenArtifactSyncResult.skipped_existing_count }}</span>
            <small>扫描 {{ screenArtifactSyncResult.scanned_observation_count }} / audit only</small>
          </div>
          <div v-if="screenProviderConfigProposalResult" class="score-item">
            <strong>Config Proposal / {{ screenProviderConfigProposalResult.status }}</strong>
            <span>{{ screenProviderConfigProposalResult.provider }} / {{ screenProviderConfigProposalResult.target_window_title }}</span>
            <small>写入 env {{ screenProviderConfigProposalResult.proposal.writes_env ? "是" : "否" }} / 执行命令 {{ screenProviderConfigProposalResult.proposal.executes_commands ? "是" : "否" }}</small>
          </div>
          <div v-if="screenProviderReplayResult" class="score-item">
            <strong>Provider Replay / {{ screenProviderReplayResult.status }}</strong>
            <span>步骤 {{ screenProviderReplayResult.summary.step_count }} / 通过 {{ screenProviderReplayResult.summary.passed_count }} / 阻断 {{ screenProviderReplayResult.summary.blocked_count }}</span>
            <small>{{ screenProviderReplayResult.summary.allowed_output }} / live trading disabled</small>
          </div>
          <div v-if="screenReadinessAudit" class="score-item">
            <strong>Readiness Audit / {{ screenReadinessAudit.status }}</strong>
            <span>检查阻断 {{ screenReadinessAudit.summary.blocked_check_count }} / Artifact待审 {{ screenReadinessAudit.summary.artifact_pending_count }} / 配置待审 {{ screenReadinessAudit.summary.config_pending_count }}</span>
            <small>{{ screenReadinessAudit.summary.allowed_output }} / 安全 {{ screenReadinessAudit.summary.safety_passed ? "通过" : "需复核" }}</small>
          </div>
          <div v-if="screenReadinessAuditAckResult" class="score-item">
            <strong>Audit Ack / {{ screenReadinessAuditAckResult.status }}</strong>
            <span>{{ screenReadinessAuditAckResult.acknowledged_by }} / {{ screenReadinessAuditAckResult.acknowledgement_effect }}</span>
            <small>写 env {{ screenReadinessAuditAckResult.writes_env ? "是" : "否" }} / OCR {{ screenReadinessAuditAckResult.ocr_executed ? "执行" : "关闭" }} / live trading disabled</small>
          </div>
          <div v-if="screenReadinessExport" class="score-item">
            <strong>Evidence Export / {{ screenReadinessExport.status }}</strong>
            <span>{{ screenReadinessExport.export_metadata.allowed_output }} / {{ screenReadinessExport.export_metadata.delivery }}</span>
            <small>{{ screenReadinessExport.bundle_hash.slice(0, 16) }} / 写文件 {{ screenReadinessExport.safety.writes_file ? "是" : "否" }} / OCR {{ screenReadinessExport.safety.ocr_executed ? "执行" : "关闭" }}</small>
          </div>
          <div v-if="screenReadinessVerification" class="score-item">
            <strong>Evidence Verifier / {{ screenReadinessVerification.status }}</strong>
            <span>{{ screenReadinessVerification.passed_count }}/{{ screenReadinessVerification.check_count }} checks / {{ screenReadinessVerification.allowed_output }}</span>
            <small>{{ screenReadinessVerification.export_bundle_hash.slice(0, 16) }} / 失败 {{ screenReadinessVerification.failed_count }} / 实盘 {{ screenReadinessVerification.live_trading_enabled ? "开启" : "关闭" }}</small>
          </div>
          <div v-if="screenReadinessComparison" class="score-item">
            <strong>Evidence Compare / {{ screenReadinessComparison.status }}</strong>
            <span>差异 {{ screenReadinessComparison.difference_count }} / {{ screenReadinessComparison.allowed_output }}</span>
            <small>{{ screenReadinessComparison.baseline.export_bundle_hash.slice(0, 16) }} -> {{ screenReadinessComparison.candidate.export_bundle_hash.slice(0, 16) }} / OCR {{ screenReadinessComparison.safety_summary.ocr_executed ? "执行" : "关闭" }}</small>
          </div>
          <div v-if="screenReadinessHealth" class="score-item">
            <strong>Evidence Health / {{ screenReadinessHealth.status }}</strong>
            <span>{{ screenReadinessHealth.summary.verification_status }} / {{ screenReadinessHealth.summary.comparison_status }} / {{ screenReadinessHealth.allowed_output }}</span>
            <small>{{ screenReadinessHealth.summary.export_bundle_hash.slice(0, 16) }} / flags {{ screenReadinessHealth.failed_flags.length }} / 实盘 {{ screenReadinessHealth.live_trading_enabled ? "开启" : "关闭" }}</small>
          </div>
          <div v-if="screenDigestHistoryProposal" class="score-item">
            <strong>Digest History / {{ screenDigestHistoryProposal.status }}</strong>
            <span>{{ screenDigestHistoryProposal.proposal.default_state }} / {{ screenDigestHistoryProposal.allowed_output }}</span>
            <small>DB {{ screenDigestHistoryProposal.safety_summary.writes_database_now ? "写入" : "不写" }} / 保留 {{ screenDigestHistoryProposal.proposal.recommended_retention_days }} 天 / gates {{ screenDigestHistoryProposal.review_gates.length }}</small>
          </div>
          <div v-if="screenDigestMigrationChecklist" class="score-item">
            <strong>History Migration / {{ screenDigestMigrationChecklist.status }}</strong>
            <span>{{ screenDigestMigrationChecklist.migration_plan.default_state }} / {{ screenDigestMigrationChecklist.allowed_output }}</span>
            <small>允许迁移 {{ screenDigestMigrationChecklist.summary.migration_allowed_now ? "是" : "否" }} / 需复核 {{ screenDigestMigrationChecklist.summary.review_required_count }} / DB {{ screenDigestMigrationChecklist.safety_summary.writes_database_now ? "写入" : "不写" }}</small>
          </div>
          <div v-if="screenDigestMigrationSpecVerification" class="score-item">
            <strong>Migration Spec / {{ screenDigestMigrationSpecVerification.status }}</strong>
            <span>{{ screenDigestMigrationSpecVerification.passed_count }}/{{ screenDigestMigrationSpecVerification.check_count }} checks / {{ screenDigestMigrationSpecVerification.allowed_output }}</span>
            <small>执行 SQL {{ screenDigestMigrationSpecVerification.safety_summary.executes_sql ? "是" : "否" }} / 失败 {{ screenDigestMigrationSpecVerification.failed_count }} / 迁移 {{ screenDigestMigrationSpecVerification.migration_allowed_now ? "允许" : "禁止" }}</small>
          </div>
          <div v-if="screenDigestMigrationSpecApprovalResult" class="score-item">
            <strong>Spec Approval / {{ screenDigestMigrationSpecApprovalResult.status }}</strong>
            <span>{{ screenDigestMigrationSpecApprovalResult.approved_by }} / {{ screenDigestMigrationSpecApprovalResult.approval_effect }}</span>
            <small>事件 #{{ screenDigestMigrationSpecApprovalResult.event_id ?? "未记录" }} / 建表 {{ screenDigestMigrationSpecApprovalResult.safety_summary.creates_table_now ? "是" : "否" }} / 迁移 {{ screenDigestMigrationSpecApprovalResult.migration_allowed_now ? "允许" : "禁止" }}</small>
          </div>
          <div v-if="screenDigestMigrationSpecApprovals.length" class="score-item">
            <strong>Spec Approval History / {{ screenDigestMigrationSpecApprovals.length }}</strong>
            <span>{{ screenDigestMigrationSpecApprovals[0].approved_by }} / {{ screenDigestMigrationSpecApprovals[0].verification_status }}</span>
            <small>{{ screenDigestMigrationSpecApprovals[0].spec_hash.slice(0, 16) }} / {{ screenDigestMigrationSpecApprovals[0].approval_effect }}</small>
          </div>
          <div v-if="screenDigestReleaseReadiness" class="score-item">
            <strong>Release Readiness / {{ screenDigestReleaseReadiness.status }}</strong>
            <span>{{ screenDigestReleaseReadiness.decision.go_no_go }} / {{ screenDigestReleaseReadiness.allowed_output }}</span>
            <small>审批 {{ screenDigestReleaseReadiness.evidence.approval_count }} / gate {{ screenDigestReleaseReadiness.gates.length }} / 迁移 {{ screenDigestReleaseReadiness.decision.migration_allowed_now ? "允许" : "禁止" }}</small>
          </div>
          <div v-if="screenDigestApprovalReview" class="score-item">
            <strong>Approval Review / {{ screenDigestApprovalReview.status }}</strong>
            <span>{{ screenDigestApprovalReview.decision.next_required_action }} / {{ screenDigestApprovalReview.allowed_output }}</span>
            <small>有效期 {{ screenDigestApprovalReview.review_policy.max_age_days }} 天 / age {{ screenDigestApprovalReview.latest_approval.approval_age_days ?? "无" }} / 复用 {{ screenDigestApprovalReview.decision.approval_can_be_reused_for_manual_release_review ? "是" : "否" }}</small>
          </div>
          <div v-if="screenDigestReleasePackage" class="score-item">
            <strong>Release Package / {{ screenDigestReleasePackage.status }}</strong>
            <span>{{ screenDigestReleasePackage.decision.go_no_go }} / {{ screenDigestReleasePackage.allowed_output }}</span>
            <small>{{ screenDigestReleasePackage.package_id.slice(0, 16) }} / items {{ screenDigestReleasePackage.manifest.items.length }} / 执行 {{ screenDigestReleasePackage.decision.execution_allowed_now ? "允许" : "禁止" }}</small>
          </div>
          <div
            v-for="item in screenReadinessAudit?.safety_matrix.slice(0, 6) ?? []"
            :key="item.name"
            class="score-item"
          >
            <strong>{{ item.name }} / {{ item.status }}</strong>
            <span>{{ item.reason }}</span>
            <small>review-only / simulation-only / live trading disabled</small>
          </div>
          <div v-if="screenObservationResult" class="score-item">
            <strong>Latest Observation / {{ screenObservationResult.app_status }}</strong>
            <span>置信度 {{ screenObservationResult.confidence }} / 插入 {{ screenObservationResult.inserted ? "是" : "去重" }}</span>
            <small>{{ screenObservationResult.observed_at }} / {{ screenObservationResult.source }}</small>
          </div>
        </div>
        <div v-if="screenObservations.length" class="score-list">
          <div v-for="item in screenObservations.slice(0, 5)" :key="item.id" class="score-item">
            <strong>{{ item.app_status }} / {{ item.source }}</strong>
            <span>{{ item.window_title ?? "未记录窗口" }} / 识别项 {{ item.detected_items.length }} / 警告 {{ item.warnings.length }}</span>
            <small>{{ item.observed_at }} / read-only evidence</small>
          </div>
        </div>
        <div v-if="screenArtifactReviews.length" class="score-list">
          <div v-for="review in screenArtifactReviews.slice(0, 5)" :key="review.id" class="score-item">
            <strong>Artifact Review #{{ review.id }} / {{ review.review_status }}</strong>
            <span>{{ review.artifact_status }} / {{ review.artifact_ref ?? "无 artifact" }}</span>
            <small>{{ review.observation.window_title ?? "未记录窗口" }} / 像素保存 {{ review.redaction.pixel_data_stored ? "是" : "否" }} / live trading disabled</small>
            <div class="actions" v-if="review.review_status === 'pending_review'">
              <button @click="approveScreenArtifactReview(review.id)" :disabled="screenMonitoringLoading">接受</button>
              <button @click="rejectScreenArtifactReview(review.id)" :disabled="screenMonitoringLoading">拒绝</button>
            </div>
          </div>
        </div>
        <div v-if="screenProviderConfigProposals.length" class="score-list">
          <div v-for="proposal in screenProviderConfigProposals.slice(0, 5)" :key="proposal.id" class="score-item">
            <strong>Config Proposal #{{ proposal.id }} / {{ proposal.status }}</strong>
            <span>{{ proposal.provider }} / {{ proposal.target_window_title ?? "未指定窗口" }}</span>
            <small>写 env {{ proposal.proposal.writes_env ? "是" : "否" }} / 自动应用 {{ proposal.proposal.apply_automatically ? "是" : "否" }} / live trading disabled</small>
            <div class="actions" v-if="proposal.status === 'pending_review'">
              <button @click="approveScreenProviderConfigProposal(proposal.id)" :disabled="screenMonitoringLoading">接受</button>
              <button @click="rejectScreenProviderConfigProposal(proposal.id)" :disabled="screenMonitoringLoading">拒绝</button>
            </div>
          </div>
        </div>
        <div v-if="screenProviderReplayRuns.length" class="score-list">
          <div v-for="run in screenProviderReplayRuns.slice(0, 5)" :key="run.id" class="score-item">
            <strong>Provider Replay #{{ run.id }} / {{ run.status }}</strong>
            <span>{{ run.scenario_name }} / proposal {{ run.proposal_id ?? "none" }}</span>
            <small>通过 {{ run.summary.passed_count }} / 阻断 {{ run.summary.blocked_count }} / 像素与 OCR 关闭</small>
          </div>
        </div>
        <div v-if="screenReadinessAuditAcks.length" class="score-list">
          <div v-for="ack in screenReadinessAuditAcks.slice(0, 5)" :key="ack.id" class="score-item">
            <strong>Audit Ack #{{ ack.id }} / {{ ack.status }}</strong>
            <span>{{ ack.acknowledged_by }} / {{ ack.report_status }} / {{ ack.report_stage }}</span>
            <small>{{ ack.updated_at }} / {{ ack.acknowledgement_effect }} / 不启用截图或实盘</small>
          </div>
        </div>
        <div v-if="screenReadinessTimeline?.items.length" class="score-list">
          <div v-for="item in screenReadinessTimeline.items.slice(0, 8)" :key="item.id" class="score-item">
            <strong>{{ item.item_type }} / {{ item.status }}</strong>
            <span>{{ item.title }}</span>
            <small>{{ item.event_ts }} / 写 env {{ item.writes_env ? "是" : "否" }} / OCR {{ item.ocr_executed ? "执行" : "关闭" }} / live trading disabled</small>
          </div>
        </div>
        <p v-if="!screenObservations.length">暂无屏幕观测证据。V4.5 仅支持 mock、fixture、截图预检和 artifact 元数据复核，不控制交易软件。</p>
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
        <h2>V5.0 Trade Execution Gateway</h2>
        <p class="review-only-banner">只展示交易执行网关的架构审查和安全门禁；不连接券商、不读取账户、不保存凭证、不下单。</p>
        <div class="actions">
          <button data-testid="trade-gateway-refresh-button" @click="loadTradeExecutionGateway" :disabled="tradeGatewayLoading">
            {{ tradeGatewayLoading ? "刷新中" : "刷新网关门禁" }}
          </button>
          <button data-testid="trade-gateway-audit-spec-approve-button" @click="approveTradeGatewayAuditMigrationSpec" :disabled="tradeGatewayLoading">
            记录规格审批元数据
          </button>
          <button data-testid="trade-gateway-health-digest-history-spec-approve-button" @click="approveTradeGatewayHealthDigestHistoryMigrationSpec" :disabled="tradeGatewayLoading">
            Record history spec approval
          </button>
          <button class="disabled-live" disabled>实盘执行未启用</button>
        </div>
        <div class="metrics">
          <span>阶段 {{ tradeGatewayCapabilities?.stage ?? "V5.5-P26" }}</span>
          <span>状态 {{ tradeGatewayCapabilities?.status ?? "未加载" }}</span>
          <span>执行 {{ tradeGatewayCapabilities?.execution_enabled ? "允许" : "禁止" }}</span>
          <span>券商适配 {{ tradeGatewayCapabilities?.broker_adapter_enabled ? "开启" : "关闭" }}</span>
          <span>凭证存储 {{ tradeGatewayCapabilities?.credential_storage_enabled ? "开启" : "关闭" }}</span>
          <span>人工确认 {{ tradeGatewayManualContract?.status ?? "未加载" }}</span>
          <span>审计Schema {{ tradeGatewayAuditSchema?.status ?? "未加载" }}</span>
          <span>风险契约 {{ tradeGatewayRiskContract?.status ?? "未加载" }}</span>
          <span>回滚 {{ tradeGatewayRollbackRunbook?.status ?? "未加载" }}</span>
          <span>Pre-live {{ tradeGatewayPreLivePackage?.status ?? "未加载" }}</span>
          <span>验收 {{ tradeGatewayAcceptanceChecklist?.status ?? "未加载" }}</span>
          <span>发布门禁 {{ tradeGatewayReleaseGate?.status ?? "未加载" }}</span>
          <span>最终报告 {{ tradeGatewayFinalReport?.status ?? "未加载" }}</span>
          <span>威胁模型 {{ tradeGatewayBrokerThreatModel?.status ?? "未加载" }}</span>
          <span>接口草案 {{ tradeGatewayBrokerInterfaceDraft?.status ?? "未加载" }}</span>
          <span>契约验证 {{ tradeGatewayBrokerContractVerification?.status ?? "未加载" }}</span>
          <span>失败场景 {{ tradeGatewayOrderFailureFixtures?.status ?? "未加载" }}</span>
          <span>Runbook映射 {{ tradeGatewayOrderRunbookMapping?.status ?? "未加载" }}</span>
          <span>审计账本计划 {{ tradeGatewayAuditStoragePlan?.status ?? "未加载" }}</span>
          <span>迁移规格校验 {{ tradeGatewayAuditMigrationSpecVerification?.status ?? "未加载" }}</span>
          <span>规格审批 {{ tradeGatewayAuditMigrationSpecApprovals.length }}</span>
          <span>发布就绪 {{ tradeGatewayAuditMigrationReleaseReadiness?.status ?? "未加载" }}</span>
          <span>审批复核 {{ tradeGatewayAuditMigrationApprovalReview?.status ?? "未加载" }}</span>
          <span>发布包 {{ tradeGatewayAuditMigrationReleasePackage?.status ?? "未加载" }}</span>
          <span>完整性 {{ tradeGatewayAuditMigrationPackageIntegrity?.status ?? "未加载" }}</span>
          <span>复核演练 {{ tradeGatewayAuditMigrationReleaseRehearsal?.status ?? "未加载" }}</span>
          <span>证据校验 {{ tradeGatewayAuditMigrationEvidenceVerification?.status ?? "未加载" }}</span>
          <span>证据对比 {{ tradeGatewayAuditMigrationEvidenceComparison?.status ?? "未加载" }}</span>
          <span>健康摘要 {{ tradeGatewayAuditMigrationHealthDigest?.status ?? "未加载" }}</span>
          <span>摘要留痕 {{ tradeGatewayAuditMigrationHealthDigestHistoryProposal?.status ?? "未加载" }}</span>
          <span>迁移清单 {{ tradeGatewayAuditMigrationHealthDigestHistoryChecklist?.status ?? "未加载" }}</span>
          <span>历史规格 {{ tradeGatewayAuditMigrationHealthDigestHistorySpecVerification?.status ?? "未加载" }}</span>
          <span>History spec approvals {{ tradeGatewayAuditMigrationHealthDigestHistorySpecApprovals.length }}</span>
          <span>History release readiness {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseReadiness?.status ?? "not loaded" }}</span>
          <span>History approval review {{ tradeGatewayAuditMigrationHealthDigestHistoryApprovalReview?.status ?? "not loaded" }}</span>
          <span>History release package {{ tradeGatewayAuditMigrationHealthDigestHistoryReleasePackage?.status ?? "not loaded" }}</span>
          <span>History package integrity {{ tradeGatewayAuditMigrationHealthDigestHistoryPackageIntegrity?.status ?? "not loaded" }}</span>
          <span>History release rehearsal {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseRehearsal?.status ?? "not loaded" }}</span>
          <span>History release evidence {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidence?.status ?? "not loaded" }}</span>
          <span>History evidence comparison {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidenceComparison?.status ?? "not loaded" }}</span>
          <span>History release health {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseHealthDigest?.status ?? "not loaded" }}</span>
          <span>门禁阻断 {{ tradeGatewayReviewGates?.blocked_gate_count ?? 0 }}</span>
          <span>待设计 {{ tradeGatewayReviewGates?.review_required_count ?? 0 }}</span>
          <span>实盘 {{ tradeGatewayCapabilities?.live_trading_enabled ? "开启" : "关闭" }}</span>
        </div>
        <div v-if="tradeGatewayCapabilities" class="score-list">
          <div class="score-item">
            <strong>Gateway / {{ tradeGatewayCapabilities.status }}</strong>
            <span>{{ tradeGatewayCapabilities.current_output }}</span>
            <small>review-only {{ tradeGatewayCapabilities.review_only ? "是" : "否" }} / simulation-only {{ tradeGatewayCapabilities.simulation_only ? "是" : "否" }}</small>
          </div>
          <div v-if="tradeGatewayManualContract" class="score-item">
            <strong>Manual Confirmation / {{ tradeGatewayManualContract.status }}</strong>
            <span>{{ tradeGatewayManualContract.contract_state }} / TTL {{ tradeGatewayManualContract.expiry_policy.confirmation_ttl_seconds }}s</span>
            <small>执行 {{ tradeGatewayManualContract.decision.contract_allows_execution_now ? "允许" : "禁止" }} / {{ tradeGatewayManualContract.allowed_output }}</small>
          </div>
          <div v-if="tradeGatewayManualContract" class="score-item">
            <strong>Confirmation Inputs</strong>
            <span>{{ tradeGatewayManualContract.required_operator_inputs.map((item) => item.name).join(" / ") }}</span>
            <small>禁止输入 {{ tradeGatewayManualContract.forbidden_inputs.join(" / ") }}</small>
          </div>
          <div v-if="tradeGatewayAuditSchema" class="score-item">
            <strong>Audit Evidence / {{ tradeGatewayAuditSchema.status }}</strong>
            <span>{{ tradeGatewayAuditSchema.target_future_table }} / {{ tradeGatewayAuditSchema.storage_state }}</span>
            <small>写库 {{ tradeGatewayAuditSchema.writes_database_now ? "是" : "否" }} / 迁移 {{ tradeGatewayAuditSchema.decision.migration_allowed_now ? "允许" : "禁止" }}</small>
          </div>
          <div v-if="tradeGatewayAuditSchema" class="score-item">
            <strong>Audit Fields</strong>
            <span>{{ tradeGatewayAuditSchema.fields.map((item) => item.name).join(" / ") }}</span>
            <small>{{ tradeGatewayAuditSchema.immutability_rules.join(" / ") }}</small>
          </div>
          <div v-if="tradeGatewayRiskContract" class="score-item">
            <strong>Risk Gate / {{ tradeGatewayRiskContract.status }}</strong>
            <span>{{ tradeGatewayRiskContract.contract_state }} / {{ tradeGatewayRiskContract.allowed_output }}</span>
            <small>执行 {{ tradeGatewayRiskContract.decision.contract_allows_execution_now ? "允许" : "禁止" }} / 风险可覆盖人工确认 {{ tradeGatewayRiskContract.decision.risk_gate_can_override_manual_confirmation ? "是" : "否" }}</small>
          </div>
          <div v-if="tradeGatewayRiskContract" class="score-item">
            <strong>Portfolio Gates</strong>
            <span>{{ tradeGatewayRiskContract.portfolio_gates.map((item) => `${item.name}:${item.failure_status}`).join(" / ") }}</span>
            <small>人工覆盖 {{ tradeGatewayRiskContract.integration_notes.manual_confirmation_override_allowed ? "允许" : "禁止" }} / AI覆盖 {{ tradeGatewayRiskContract.integration_notes.ai_override_allowed ? "允许" : "禁止" }}</small>
          </div>
          <div v-if="tradeGatewayRiskContract" class="score-item">
            <strong>Symbol Gates</strong>
            <span>{{ tradeGatewayRiskContract.symbol_gates.map((item) => `${item.name}:${item.failure_status}`).join(" / ") }}</span>
            <small>{{ tradeGatewayRiskContract.required_evidence_hashes.join(" / ") }}</small>
          </div>
          <div v-if="tradeGatewayRollbackRunbook" class="score-item">
            <strong>Rollback Runbook / {{ tradeGatewayRollbackRunbook.status }}</strong>
            <span>{{ tradeGatewayRollbackRunbook.trigger_events.join(" / ") }}</span>
            <small>执行命令 {{ tradeGatewayRollbackRunbook.safety_summary.executes_commands ? "是" : "否" }} / 写库 {{ tradeGatewayRollbackRunbook.safety_summary.writes_database_now ? "是" : "否" }}</small>
          </div>
          <div v-if="tradeGatewayRollbackRunbook" class="score-item">
            <strong>Rollback Steps</strong>
            <span>{{ tradeGatewayRollbackRunbook.rollback_steps.map((item) => `${item.step}:${item.owner}`).join(" / ") }}</span>
            <small>当前仅供人工审查，不会冻结、改状态或执行本地命令。</small>
          </div>
          <div v-if="tradeGatewayPreLivePackage" class="score-item">
            <strong>Pre-live Review / {{ tradeGatewayPreLivePackage.status }}</strong>
            <span>{{ tradeGatewayPreLivePackage.package_id.slice(0, 16) }} / {{ tradeGatewayPreLivePackage.package_state }}</span>
            <small>可启用实盘 {{ tradeGatewayPreLivePackage.decision.ready_for_live_enablement ? "是" : "否" }} / gateway execute {{ tradeGatewayPreLivePackage.decision.gateway_can_execute ? "允许" : "禁止" }}</small>
          </div>
          <div v-if="tradeGatewayPreLivePackage" class="score-item">
            <strong>Pre-live Manifest</strong>
            <span>{{ tradeGatewayPreLivePackage.manifest.map((item) => `${item.name}:${item.status}`).join(" / ") }}</span>
            <small>{{ tradeGatewayPreLivePackage.required_manual_artifacts.slice(0, 3).join(" / ") }}</small>
          </div>
          <div v-if="tradeGatewayAcceptanceChecklist" class="score-item">
            <strong>Operator Acceptance / {{ tradeGatewayAcceptanceChecklist.status }}</strong>
            <span>{{ tradeGatewayAcceptanceChecklist.checklist_items.map((item) => `${item.id}:${item.required ? "必需" : "可选"}`).join(" / ") }}</span>
            <small>API记录验收 {{ tradeGatewayAcceptanceChecklist.acceptance_policy.api_can_record_acceptance ? "允许" : "禁止" }} / 启用网关 {{ tradeGatewayAcceptanceChecklist.acceptance_policy.api_can_enable_gateway ? "允许" : "禁止" }}</small>
          </div>
          <div v-if="tradeGatewayReleaseGate" class="score-item">
            <strong>Disabled Release Gate / {{ tradeGatewayReleaseGate.status }}</strong>
            <span>{{ tradeGatewayReleaseGate.default_state }} / {{ tradeGatewayReleaseGate.release_gate_state }}</span>
            <small>可启用 {{ tradeGatewayReleaseGate.decision.release_gate_allows_enablement_now ? "是" : "否" }} / API启用 {{ tradeGatewayReleaseGate.decision.api_can_enable_gateway ? "允许" : "禁止" }}</small>
          </div>
          <div v-if="tradeGatewayReleaseGate" class="score-item">
            <strong>Release Blockers</strong>
            <span>{{ tradeGatewayReleaseGate.release_blockers.join(" / ") }}</span>
            <small>这些阻断项只能由独立实盘集成项目和人工审查处理，当前面板不提供启用动作。</small>
          </div>
          <div v-if="tradeGatewayFinalReport" class="score-item">
            <strong>Final Readiness / {{ tradeGatewayFinalReport.status }}</strong>
            <span>{{ tradeGatewayFinalReport.report_id.slice(0, 16) }} / {{ tradeGatewayFinalReport.report_state }}</span>
            <small>V5基线 {{ tradeGatewayFinalReport.decision.v5_review_only_baseline_complete ? "完成" : "未完成" }} / V5.5威胁建模 {{ tradeGatewayFinalReport.decision.ready_for_v5_5_threat_modeling ? "可开始" : "等待" }}</small>
          </div>
          <div v-if="tradeGatewayFinalReport" class="score-item">
            <strong>Final Safety Matrix</strong>
            <span>{{ Object.entries(tradeGatewayFinalReport.safety_matrix).map(([key, value]) => `${key}:${value}`).join(" / ") }}</span>
            <small>实盘启用 {{ tradeGatewayFinalReport.decision.ready_for_live_enablement ? "允许" : "禁止" }} / gateway execute {{ tradeGatewayFinalReport.decision.gateway_can_execute ? "允许" : "禁止" }}</small>
          </div>
          <div v-if="tradeGatewayFinalReport" class="score-item">
            <strong>Remaining Blockers</strong>
            <span>{{ tradeGatewayFinalReport.remaining_blockers.join(" / ") }}</span>
            <small>{{ tradeGatewayFinalReport.summary.next_track }}</small>
          </div>
          <div v-if="tradeGatewayBrokerThreatModel" class="score-item">
            <strong>Broker Threat Model / {{ tradeGatewayBrokerThreatModel.status }}</strong>
            <span>{{ tradeGatewayBrokerThreatModel.threat_categories.map((item) => `${item.name}:${item.status}`).join(" / ") }}</span>
            <small>券商适配 {{ tradeGatewayBrokerThreatModel.decision.broker_adapter_allowed_now ? "允许" : "禁止" }} / 下单 {{ tradeGatewayBrokerThreatModel.decision.order_execution_allowed_now ? "允许" : "禁止" }}</small>
          </div>
          <div v-if="tradeGatewayBrokerThreatModel" class="score-item">
            <strong>Protected Assets</strong>
            <span>{{ tradeGatewayBrokerThreatModel.protected_assets.join(" / ") }}</span>
            <small>{{ tradeGatewayBrokerThreatModel.required_future_reviews.slice(0, 4).join(" / ") }}</small>
          </div>
          <div v-if="tradeGatewayBrokerInterfaceDraft" class="score-item">
            <strong>Broker Interface Draft / {{ tradeGatewayBrokerInterfaceDraft.status }}</strong>
            <span>{{ tradeGatewayBrokerInterfaceDraft.draft_methods.map((item) => `${item.name}:${item.mode}`).join(" / ") }}</span>
            <small>已实现 {{ tradeGatewayBrokerInterfaceDraft.decision.interface_implemented_now ? "是" : "否" }} / 可连接 {{ tradeGatewayBrokerInterfaceDraft.decision.adapter_can_connect_now ? "是" : "否" }}</small>
          </div>
          <div v-if="tradeGatewayBrokerInterfaceDraft" class="score-item">
            <strong>Forbidden Adapter Methods</strong>
            <span>{{ tradeGatewayBrokerInterfaceDraft.forbidden_methods.join(" / ") }}</span>
            <small>凭证输入 {{ tradeGatewayBrokerInterfaceDraft.required_inputs_policy.allows_credentials ? "允许" : "禁止" }} / 账户资金读取 {{ tradeGatewayBrokerInterfaceDraft.decision.adapter_can_read_account_now ? "允许" : "禁止" }}</small>
          </div>
          <div v-if="tradeGatewayBrokerContractVerification" class="score-item">
            <strong>Contract Verification / {{ tradeGatewayBrokerContractVerification.status }}</strong>
            <span>{{ tradeGatewayBrokerContractVerification.checks.map((item) => `${item.name}:${item.status}`).join(" / ") }}</span>
            <small>fixture-only {{ tradeGatewayBrokerContractVerification.summary.fixture_only ? "yes" : "no" }} / network calls {{ tradeGatewayBrokerContractVerification.summary.network_calls ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayBrokerContractVerification" class="score-item">
            <strong>Contract Safety</strong>
            <span>{{ tradeGatewayBrokerContractVerification.fixture_name }} / {{ tradeGatewayBrokerContractVerification.verification_state }}</span>
            <small>adapter implemented {{ tradeGatewayBrokerContractVerification.decision.adapter_implemented_now ? "yes" : "no" }} / can execute {{ tradeGatewayBrokerContractVerification.decision.adapter_can_execute_now ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayOrderFailureFixtures" class="score-item">
            <strong>Order Failure Fixtures / {{ tradeGatewayOrderFailureFixtures.status }}</strong>
            <span>{{ tradeGatewayOrderFailureFixtures.fixtures.map((item) => `${item.name}:${item.expected_status}`).join(" / ") }}</span>
            <small>blocked {{ tradeGatewayOrderFailureFixtures.summary.blocked_count }} / partial {{ tradeGatewayOrderFailureFixtures.summary.partial_count }} / rejected {{ tradeGatewayOrderFailureFixtures.summary.rejected_count }}</small>
          </div>
          <div v-if="tradeGatewayOrderFailureFixtures" class="score-item">
            <strong>Failure Fixture Safety</strong>
            <span>{{ tradeGatewayOrderFailureFixtures.fixture_suite }} / {{ tradeGatewayOrderFailureFixtures.fixture_state }}</span>
            <small>submit {{ tradeGatewayOrderFailureFixtures.decision.can_submit_order_now ? "yes" : "no" }} / real replay {{ tradeGatewayOrderFailureFixtures.decision.can_replay_as_real_order ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayOrderRunbookMapping" class="score-item">
            <strong>Failure Runbook Mapping / {{ tradeGatewayOrderRunbookMapping.status }}</strong>
            <span>{{ tradeGatewayOrderRunbookMapping.mappings.map((item) => `${item.fixture_name}:${item.manual_decision}`).join(" / ") }}</span>
            <small>audit fields {{ tradeGatewayOrderRunbookMapping.summary.audit_evidence_field_count }} / writes DB {{ tradeGatewayOrderRunbookMapping.summary.writes_database_now ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayOrderRunbookMapping" class="score-item">
            <strong>Runbook Mapping Safety</strong>
            <span>{{ tradeGatewayOrderRunbookMapping.mapping_state }} / {{ tradeGatewayOrderRunbookMapping.source_fixture_suite }}</span>
            <small>execute runbook {{ tradeGatewayOrderRunbookMapping.decision.can_execute_runbook_now ? "yes" : "no" }} / record audit {{ tradeGatewayOrderRunbookMapping.decision.can_record_audit_now ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditStoragePlan" class="score-item">
            <strong>Audit Ledger Storage Plan / {{ tradeGatewayAuditStoragePlan.status }}</strong>
            <span>{{ tradeGatewayAuditStoragePlan.target_future_table }} / {{ tradeGatewayAuditStoragePlan.storage_state }}</span>
            <small>columns {{ tradeGatewayAuditStoragePlan.summary.planned_column_count }} / indexes {{ tradeGatewayAuditStoragePlan.summary.proposed_index_count }} / writes DB {{ tradeGatewayAuditStoragePlan.summary.writes_database_now ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditStoragePlan" class="score-item">
            <strong>Storage Plan Safety</strong>
            <span>{{ tradeGatewayAuditStoragePlan.hash_chain_policy.algorithm }} / {{ tradeGatewayAuditStoragePlan.redaction_policy.excluded_sensitive_fields.join(" / ") }}</span>
            <small>create table {{ tradeGatewayAuditStoragePlan.decision.can_create_table_now ? "yes" : "no" }} / migration {{ tradeGatewayAuditStoragePlan.decision.can_run_migration_now ? "yes" : "no" }} / audit row {{ tradeGatewayAuditStoragePlan.decision.can_write_audit_row_now ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationSpecVerification" class="score-item">
            <strong>Audit Ledger Migration Spec / {{ tradeGatewayAuditMigrationSpecVerification.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationSpecVerification.target_table }} / {{ tradeGatewayAuditMigrationSpecVerification.verification_state }}</span>
            <small>failed {{ tradeGatewayAuditMigrationSpecVerification.failed_count }} / executes SQL {{ tradeGatewayAuditMigrationSpecVerification.summary.executes_sql ? "yes" : "no" }} / writes file {{ tradeGatewayAuditMigrationSpecVerification.summary.writes_migration_file_now ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationSpecVerification" class="score-item">
            <strong>Migration Spec Checks</strong>
            <span>{{ tradeGatewayAuditMigrationSpecVerification.checks.map((item) => `${item.name}:${item.status}`).join(" / ") }}</span>
            <small>create table {{ tradeGatewayAuditMigrationSpecVerification.decision.can_create_table_now ? "yes" : "no" }} / audit row {{ tradeGatewayAuditMigrationSpecVerification.decision.can_write_audit_row_now ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationSpecApprovalResult" class="score-item">
            <strong>Migration Spec Approval / {{ tradeGatewayAuditMigrationSpecApprovalResult.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationSpecApprovalResult.approved_by }} / {{ tradeGatewayAuditMigrationSpecApprovalResult.approval_effect }}</span>
            <small>event {{ tradeGatewayAuditMigrationSpecApprovalResult.event_id ?? "blocked" }} / writes ledger {{ tradeGatewayAuditMigrationSpecApprovalResult.safety_summary.writes_audit_ledger_row_now ? "yes" : "no" }} / SQL {{ tradeGatewayAuditMigrationSpecApprovalResult.safety_summary.executes_sql ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationSpecApprovals.length" class="score-item">
            <strong>Migration Spec Approval History</strong>
            <span>{{ tradeGatewayAuditMigrationSpecApprovals.slice(0, 3).map((item) => `${item.event_id}:${item.status}`).join(" / ") }}</span>
            <small>existing events only / live trading disabled</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationReleaseReadiness" class="score-item">
            <strong>Migration Release Readiness / {{ tradeGatewayAuditMigrationReleaseReadiness.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationReleaseReadiness.decision.go_no_go }} / {{ tradeGatewayAuditMigrationReleaseReadiness.allowed_output }}</span>
            <small>approval {{ tradeGatewayAuditMigrationReleaseReadiness.evidence.approval_count }} / gate {{ tradeGatewayAuditMigrationReleaseReadiness.gates.length }} / migration {{ tradeGatewayAuditMigrationReleaseReadiness.decision.migration_allowed_now ? "allowed" : "blocked" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationApprovalReview" class="score-item">
            <strong>Migration Approval Review / {{ tradeGatewayAuditMigrationApprovalReview.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationApprovalReview.decision.next_required_action }} / reuse {{ tradeGatewayAuditMigrationApprovalReview.decision.approval_can_be_reused_for_manual_release_review ? "yes" : "no" }}</span>
            <small>age {{ tradeGatewayAuditMigrationApprovalReview.latest_approval.approval_age_days ?? "none" }}d / max {{ tradeGatewayAuditMigrationApprovalReview.review_policy.max_age_days }}d / match {{ tradeGatewayAuditMigrationApprovalReview.latest_approval.matches_current_spec ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationReleasePackage" class="score-item">
            <strong>Migration Release Package / {{ tradeGatewayAuditMigrationReleasePackage.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationReleasePackage.decision.go_no_go }} / {{ tradeGatewayAuditMigrationReleasePackage.decision.next_required_action }}</span>
            <small>{{ tradeGatewayAuditMigrationReleasePackage.package_id.slice(0, 16) }} / items {{ tradeGatewayAuditMigrationReleasePackage.manifest.items.length }} / execution {{ tradeGatewayAuditMigrationReleasePackage.decision.execution_allowed_now ? "allowed" : "blocked" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationPackageIntegrity" class="score-item">
            <strong>Package Integrity / {{ tradeGatewayAuditMigrationPackageIntegrity.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationPackageIntegrity.decision.go_no_go }} / {{ tradeGatewayAuditMigrationPackageIntegrity.decision.next_required_action }}</span>
            <small>{{ tradeGatewayAuditMigrationPackageIntegrity.source_package_id.slice(0, 16) }} / stable {{ tradeGatewayAuditMigrationPackageIntegrity.decision.package_id_stable ? "yes" : "no" }} / failed {{ tradeGatewayAuditMigrationPackageIntegrity.failed_check_count }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationReleaseRehearsal" class="score-item">
            <strong>Manual Release Rehearsal / {{ tradeGatewayAuditMigrationReleaseRehearsal.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationReleaseRehearsal.decision.go_no_go }} / {{ tradeGatewayAuditMigrationReleaseRehearsal.decision.next_required_action }}</span>
            <small>{{ tradeGatewayAuditMigrationReleaseRehearsal.rehearsal_id.slice(0, 16) }} / pending {{ tradeGatewayAuditMigrationReleaseRehearsal.pending_steps.length }} / record {{ tradeGatewayAuditMigrationReleaseRehearsal.decision.manual_review_recorded_now ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationEvidenceVerification" class="score-item">
            <strong>Manual Evidence Verifier / {{ tradeGatewayAuditMigrationEvidenceVerification.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationEvidenceVerification.decision.go_no_go }} / {{ tradeGatewayAuditMigrationEvidenceVerification.decision.next_required_action }}</span>
            <small>{{ tradeGatewayAuditMigrationEvidenceVerification.verification_id.slice(0, 16) }} / missing {{ tradeGatewayAuditMigrationEvidenceVerification.missing_artifacts.length }} / persist {{ tradeGatewayAuditMigrationEvidenceVerification.safety_summary.persists_manual_release_evidence ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationEvidenceComparison" class="score-item">
            <strong>Evidence Comparison / {{ tradeGatewayAuditMigrationEvidenceComparison.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationEvidenceComparison.decision.go_no_go }} / {{ tradeGatewayAuditMigrationEvidenceComparison.decision.next_required_action }}</span>
            <small>{{ tradeGatewayAuditMigrationEvidenceComparison.comparison_id.slice(0, 16) }} / changed {{ tradeGatewayAuditMigrationEvidenceComparison.artifact_hash_changes.length }} / persist {{ tradeGatewayAuditMigrationEvidenceComparison.safety_summary.persists_manual_release_evidence_comparison ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationHealthDigest" class="score-item">
            <strong>Health Digest / {{ tradeGatewayAuditMigrationHealthDigest.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationHealthDigest.decision.go_no_go }} / {{ tradeGatewayAuditMigrationHealthDigest.decision.next_required_action }}</span>
            <small>{{ tradeGatewayAuditMigrationHealthDigest.digest_id.slice(0, 16) }} / attention {{ tradeGatewayAuditMigrationHealthDigest.summary.attention_count }} / persist {{ tradeGatewayAuditMigrationHealthDigest.safety_summary.persists_manual_release_health_digest ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationHealthDigestHistoryProposal" class="score-item">
            <strong>Health Digest History / {{ tradeGatewayAuditMigrationHealthDigestHistoryProposal.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationHealthDigestHistoryProposal.decision.go_no_go }} / {{ tradeGatewayAuditMigrationHealthDigestHistoryProposal.decision.next_required_action }}</span>
            <small>{{ tradeGatewayAuditMigrationHealthDigestHistoryProposal.proposal_id.slice(0, 16) }} / fields {{ tradeGatewayAuditMigrationHealthDigestHistoryProposal.summary.required_field_count }} / persist {{ tradeGatewayAuditMigrationHealthDigestHistoryProposal.safety_summary.persists_manual_release_health_digest_history ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationHealthDigestHistoryChecklist" class="score-item">
            <strong>Health Digest History Migration / {{ tradeGatewayAuditMigrationHealthDigestHistoryChecklist.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationHealthDigestHistoryChecklist.decision.go_no_go }} / {{ tradeGatewayAuditMigrationHealthDigestHistoryChecklist.decision.next_required_action }}</span>
            <small>{{ tradeGatewayAuditMigrationHealthDigestHistoryChecklist.migration_plan.target_table }} / review {{ tradeGatewayAuditMigrationHealthDigestHistoryChecklist.summary.review_required_count }} / migrate {{ tradeGatewayAuditMigrationHealthDigestHistoryChecklist.summary.migration_allowed_now ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationHealthDigestHistorySpecVerification" class="score-item">
            <strong>Health Digest History Migration Spec / {{ tradeGatewayAuditMigrationHealthDigestHistorySpecVerification.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationHealthDigestHistorySpecVerification.target_table }} / {{ tradeGatewayAuditMigrationHealthDigestHistorySpecVerification.verification_state }}</span>
            <small>failed {{ tradeGatewayAuditMigrationHealthDigestHistorySpecVerification.summary.failed_count }} / SQL {{ tradeGatewayAuditMigrationHealthDigestHistorySpecVerification.safety_summary.executes_sql ? "yes" : "no" }} / row {{ tradeGatewayAuditMigrationHealthDigestHistorySpecVerification.decision.can_write_history_row_now ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationHealthDigestHistorySpecApprovalResult" class="score-item">
            <strong>Health Digest History Spec Approval / {{ tradeGatewayAuditMigrationHealthDigestHistorySpecApprovalResult.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationHealthDigestHistorySpecApprovalResult.approved_by }} / {{ tradeGatewayAuditMigrationHealthDigestHistorySpecApprovalResult.approval_effect }}</span>
            <small>event {{ tradeGatewayAuditMigrationHealthDigestHistorySpecApprovalResult.event_id ?? "blocked" }} / SQL {{ tradeGatewayAuditMigrationHealthDigestHistorySpecApprovalResult.safety_summary.executes_sql ? "yes" : "no" }} / row {{ tradeGatewayAuditMigrationHealthDigestHistorySpecApprovalResult.safety_summary.writes_history_row_now ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationHealthDigestHistorySpecApprovals.length" class="score-item">
            <strong>Health Digest History Spec Approval History</strong>
            <span>{{ tradeGatewayAuditMigrationHealthDigestHistorySpecApprovals.slice(0, 3).map((item) => `${item.event_id}:${item.status}`).join(" / ") }}</span>
            <small>existing events only / live trading disabled</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationHealthDigestHistoryReleaseReadiness" class="score-item">
            <strong>Health Digest History Release Readiness / {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseReadiness.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseReadiness.decision.go_no_go }} / {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseReadiness.allowed_output }}</span>
            <small>approval {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseReadiness.evidence.approval_count }} / gate {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseReadiness.gates.length }} / row {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseReadiness.safety_summary.writes_history_row_now ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationHealthDigestHistoryApprovalReview" class="score-item">
            <strong>Health Digest History Approval Review / {{ tradeGatewayAuditMigrationHealthDigestHistoryApprovalReview.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationHealthDigestHistoryApprovalReview.decision.next_required_action }} / reuse {{ tradeGatewayAuditMigrationHealthDigestHistoryApprovalReview.decision.approval_can_be_reused_for_manual_release_review ? "yes" : "no" }}</span>
            <small>age {{ tradeGatewayAuditMigrationHealthDigestHistoryApprovalReview.latest_approval.approval_age_days ?? "none" }}d / max {{ tradeGatewayAuditMigrationHealthDigestHistoryApprovalReview.review_policy.max_age_days }}d / match {{ tradeGatewayAuditMigrationHealthDigestHistoryApprovalReview.latest_approval.matches_current_spec ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationHealthDigestHistoryReleasePackage" class="score-item">
            <strong>Health Digest History Release Package / {{ tradeGatewayAuditMigrationHealthDigestHistoryReleasePackage.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationHealthDigestHistoryReleasePackage.decision.go_no_go }} / {{ tradeGatewayAuditMigrationHealthDigestHistoryReleasePackage.decision.next_required_action }}</span>
            <small>{{ tradeGatewayAuditMigrationHealthDigestHistoryReleasePackage.package_id.slice(0, 16) }} / items {{ tradeGatewayAuditMigrationHealthDigestHistoryReleasePackage.manifest.items.length }} / file {{ tradeGatewayAuditMigrationHealthDigestHistoryReleasePackage.manifest.writes_file ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationHealthDigestHistoryPackageIntegrity" class="score-item">
            <strong>Health Digest History Package Integrity / {{ tradeGatewayAuditMigrationHealthDigestHistoryPackageIntegrity.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationHealthDigestHistoryPackageIntegrity.decision.next_required_action }} / stable {{ tradeGatewayAuditMigrationHealthDigestHistoryPackageIntegrity.decision.package_id_stable ? "yes" : "no" }}</span>
            <small>failed {{ tradeGatewayAuditMigrationHealthDigestHistoryPackageIntegrity.failed_check_count }} / items {{ tradeGatewayAuditMigrationHealthDigestHistoryPackageIntegrity.manifest_summary.item_count }} / mutate {{ tradeGatewayAuditMigrationHealthDigestHistoryPackageIntegrity.safety_summary.mutates_source_package ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationHealthDigestHistoryReleaseRehearsal" class="score-item">
            <strong>Health Digest History Release Rehearsal / {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseRehearsal.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseRehearsal.decision.go_no_go }} / {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseRehearsal.decision.next_required_action }}</span>
            <small>{{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseRehearsal.rehearsal_id.slice(0, 16) }} / pending {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseRehearsal.pending_steps.length }} / failed {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseRehearsal.failed_steps.length }} / record {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseRehearsal.decision.manual_review_recorded_now ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidence" class="score-item">
            <strong>Health Digest History Release Evidence / {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidence.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidence.decision.go_no_go }} / {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidence.decision.next_required_action }}</span>
            <small>{{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidence.verification_id.slice(0, 16) }} / missing {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidence.missing_artifacts.length }} / persist {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidence.safety_summary.persists_manual_release_health_digest_history_evidence ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidenceComparison" class="score-item">
            <strong>Health Digest History Evidence Comparison / {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidenceComparison.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidenceComparison.decision.go_no_go }} / {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidenceComparison.decision.next_required_action }}</span>
            <small>{{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidenceComparison.comparison_id.slice(0, 16) }} / changed {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidenceComparison.artifact_hash_changes.length }} / persist {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidenceComparison.safety_summary.persists_manual_release_health_digest_history_evidence_comparison ? "yes" : "no" }}</small>
          </div>
          <div v-if="tradeGatewayAuditMigrationHealthDigestHistoryReleaseHealthDigest" class="score-item">
            <strong>Health Digest History Release Health / {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseHealthDigest.status }}</strong>
            <span>{{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseHealthDigest.decision.go_no_go }} / {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseHealthDigest.decision.next_required_action }}</span>
            <small>{{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseHealthDigest.digest_id.slice(0, 16) }} / attention {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseHealthDigest.summary.attention_count }} / persist {{ tradeGatewayAuditMigrationHealthDigestHistoryReleaseHealthDigest.safety_summary.persists_manual_release_health_digest_history_release_health_digest ? "yes" : "no" }}</small>
          </div>
          <div
            v-for="component in tradeGatewayCapabilities.required_future_components"
            :key="component.name"
            class="score-item"
          >
            <strong>{{ component.name }} / {{ component.status }}</strong>
            <span>required before: {{ component.required_before }}</span>
            <small>当前仅审查元数据，不启用真实交易执行。</small>
          </div>
          <div v-if="tradeGatewayReviewGates" class="score-item">
            <strong>Decision / {{ tradeGatewayReviewGates.status }}</strong>
            <span>{{ tradeGatewayReviewGates.decision.next_required_action }}</span>
            <small>gateway execute {{ tradeGatewayReviewGates.decision.gateway_can_execute ? "允许" : "禁止" }} / live trading disabled</small>
          </div>
          <div
            v-for="gate in tradeGatewayReviewGates?.gates ?? []"
            :key="gate.name"
            class="score-item"
          >
            <strong>{{ gate.name }} / {{ gate.status }}</strong>
            <span>{{ gate.reason }}</span>
            <small>value {{ gate.value }} / limit {{ gate.limit }} / live {{ gate.live_trading_enabled ? "开启" : "关闭" }}</small>
          </div>
          <div class="score-item">
            <strong>Forbidden Modes</strong>
            <span>{{ tradeGatewayCapabilities.forbidden_modes.join(" / ") }}</span>
            <small>这些能力在 V5.5-P26 只能作为阻断项展示。</small>
          </div>
        </div>
        <p v-else>暂无 V5.0 网关审查数据。刷新后只会加载安全门禁，不会创建任何真实交易接口。</p>
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
        <div v-if="dataset2Readiness" class="report">
          <strong>Dataset2 Readiness / {{ dataset2Readiness.status }}</strong>
          <span>
            records {{ dataset2Readiness.record_count }} /
            bad risk {{ dataset2Readiness.quality.invalid_risk_level_count }} /
            stringified lists {{ dataset2Readiness.quality.stringified_list_item_count }}
          </span>
          <span>
            training now {{ dataset2Readiness.decision.can_start_training_now ? "allowed" : "blocked" }} /
            rule knowledge {{ dataset2Readiness.decision.can_use_as_rule_knowledge ? "usable" : "blocked" }}
          </span>
          <small>{{ dataset2Readiness.decision.next_required_action }} / live trading disabled</small>
        </div>
        <div v-if="dataset2Preview" class="report">
          <strong>Dataset2 Normalized Preview / {{ dataset2Preview.preview_count }}</strong>
          <span>
            {{ dataset2Preview.records.slice(0, 3).map((item) => `${item.pattern_id}:${item.risk_level}`).join(" / ") }}
          </span>
          <small>review-only preview; no database write, no training start</small>
        </div>
        <div v-if="dataset2CleanupPackage" class="report">
          <strong>Dataset2 Cleanup Package / {{ dataset2CleanupPackage.status }}</strong>
          <span>
            package {{ dataset2CleanupPackage.package_id.slice(0, 16) }} /
            review actions {{ dataset2CleanupPackage.summary.review_action_count }} /
            blockers {{ dataset2CleanupPackage.summary.blocking_action_count }}
          </span>
          <span>
            risk fixes {{ dataset2CleanupPackage.summary.risk_level_change_count }} /
            list fixes {{ dataset2CleanupPackage.summary.stringified_list_item_count }} /
            evidence todos {{ dataset2CleanupPackage.summary.missing_evidence_total }}
          </span>
          <small>{{ dataset2CleanupPackage.decision.next_required_action }} / no file, no DB, no training</small>
        </div>
        <div v-if="dataset2ImportQueueReview" class="report">
          <strong>Dataset2 Import Queue Review / {{ dataset2ImportQueueReview.status }}</strong>
          <span>
            event {{ dataset2ImportQueueReview.event_id ?? dataset2ImportQueueReview.id }} /
            package {{ dataset2ImportQueueReview.package_id.slice(0, 16) }} /
            records {{ dataset2ImportQueueReview.record_count }}
          </span>
          <span>
            metadata event {{ dataset2ImportQueueReview.decision.writes_existing_event_now ? "recorded" : "blocked" }} /
            normalized rows {{ dataset2ImportQueueReview.decision.normalized_records_persisted ? "persisted" : "not persisted" }} /
            training {{ dataset2ImportQueueReview.decision.training_started_now ? "started" : "blocked" }}
          </span>
          <small>{{ dataset2ImportQueueReview.decision.next_required_action }} / metadata only</small>
        </div>
        <div v-if="dataset2ImportQueueReviews.length" class="report">
          <strong>Dataset2 Import Queue History / {{ dataset2ImportQueueReviews.length }}</strong>
          <span>
            {{ dataset2ImportQueueReviews.slice(0, 3).map((item) => `#${item.id}:${item.package_id.slice(0, 8)}`).join(" / ") }}
          </span>
          <small>source records and normalized records are excluded from stored review payloads</small>
        </div>
        <div v-if="dataset2StagingImport" class="report">
          <strong>Dataset2 Staging Import / {{ dataset2StagingImport.status }}</strong>
          <span>
            package {{ dataset2StagingImport.package_id.slice(0, 16) }} /
            staged {{ dataset2StagingImport.imported_count }} /
            review #{{ dataset2StagingImport.review_event_id ?? "missing" }}
          </span>
          <span>
            staging {{ dataset2StagingImport.decision.writes_staging_records_now ? "written" : "blocked" }} /
            learning samples {{ dataset2StagingImport.decision.writes_learning_samples_now ? "written" : "not written" }} /
            training {{ dataset2StagingImport.decision.training_started_now ? "started" : "blocked" }}
          </span>
          <small>{{ dataset2StagingImport.decision.next_required_action }} / quarantine staging only</small>
        </div>
        <div v-if="dataset2StagingSummary" class="report">
          <strong>Dataset2 Staging Summary / {{ dataset2StagingSummary.status }}</strong>
          <span>
            staged records {{ dataset2StagingSummary.record_count }} /
            packages {{ dataset2StagingSummary.package_count }} /
            learning samples {{ dataset2StagingSummary.decision.learning_sample_count }}
          </span>
          <small>{{ dataset2StagingSummary.decision.next_required_action }} / no training start</small>
        </div>
        <div v-if="dataset2StagingRecords.length" class="report">
          <strong>Dataset2 Staging Records / {{ dataset2StagingRecords.length }}</strong>
          <span>
            {{ dataset2StagingRecords.slice(0, 3).map((item) => `${item.pattern_id}:${item.risk_level}:${item.status}`).join(" / ") }}
          </span>
          <small>records are staged for review, not promoted to training samples</small>
        </div>
        <div v-if="dataset2StagingQualityReview" class="report">
          <strong>Dataset2 Staging Quality Review / {{ dataset2StagingQualityReview.status }}</strong>
          <span>
            event {{ dataset2StagingQualityReview.event_id }} /
            records {{ dataset2StagingQualityReview.record_count }} /
            blocked gates {{ dataset2StagingQualityReview.summary.blocked_gate_count }}
          </span>
          <span>
            freeze {{ dataset2StagingQualityReview.decision.training_freeze_allowed ? "allowed" : "blocked" }} /
            training {{ dataset2StagingQualityReview.decision.training_started_now ? "started" : "not started" }} /
            learning samples {{ dataset2StagingQualityReview.decision.writes_learning_samples_now ? "written" : "not written" }}
          </span>
          <small>{{ dataset2StagingQualityReview.decision.next_required_action }} / review-only gates</small>
        </div>
        <div v-if="dataset2StagingQualityReviews.length" class="report">
          <strong>Dataset2 Quality Review History / {{ dataset2StagingQualityReviews.length }}</strong>
          <span>
            {{ dataset2StagingQualityReviews.slice(0, 3).map((item) => `#${item.id}:${item.status}:${item.summary.blocked_gate_count}`).join(" / ") }}
          </span>
          <small>review payloads store gate evidence, not record bodies</small>
        </div>
        <div v-if="dataset2StagingFixPlan" class="report">
          <strong>Dataset2 Freeze Fix Plan / {{ dataset2StagingFixPlan.status }}</strong>
          <span>
            event {{ dataset2StagingFixPlan.event_id }} /
            actions {{ dataset2StagingFixPlan.summary.action_item_count }} /
            blocked gates {{ dataset2StagingFixPlan.summary.blocked_gate_count }}
          </span>
          <span>
            auto apply {{ dataset2StagingFixPlan.plan.can_be_applied_automatically_now ? "allowed" : "blocked" }} /
            staging mutation {{ dataset2StagingFixPlan.decision.mutates_staging_records_now ? "yes" : "no" }} /
            training {{ dataset2StagingFixPlan.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2StagingFixPlan.decision.next_required_action }} / plan only</small>
        </div>
        <div v-if="dataset2StagingFixPlans.length" class="report">
          <strong>Dataset2 Fix Plan History / {{ dataset2StagingFixPlans.length }}</strong>
          <span>
            {{ dataset2StagingFixPlans.slice(0, 3).map((item) => `#${item.id}:${item.status}:${item.summary.action_item_count}`).join(" / ") }}
          </span>
          <small>plans are review-only and do not apply cleanup</small>
        </div>
        <div v-if="dataset2StagingFixApproval" class="report">
          <strong>Dataset2 Fix Approval / {{ dataset2StagingFixApproval.status }}</strong>
          <span>
            event {{ dataset2StagingFixApproval.event_id }} /
            fix plan {{ dataset2StagingFixApproval.fix_plan_event_id }} /
            preflight {{ dataset2StagingFixApproval.decision.can_generate_preflight_now ? "allowed" : "blocked" }}
          </span>
          <span>
            apply fixes {{ dataset2StagingFixApproval.decision.approval_allows_fix_application_now ? "allowed" : "blocked" }} /
            staging mutation {{ dataset2StagingFixApproval.decision.mutates_staging_records_now ? "yes" : "no" }}
          </span>
          <small>{{ dataset2StagingFixApproval.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2StagingFixPreflight" class="report">
          <strong>Dataset2 Fix Preflight / {{ dataset2StagingFixPreflight.status }}</strong>
          <span>
            event {{ dataset2StagingFixPreflight.event_id }} /
            checks {{ dataset2StagingFixPreflight.summary.check_count }} /
            blocked {{ dataset2StagingFixPreflight.summary.blocked_check_count }}
          </span>
          <span>
            fixes applied {{ dataset2StagingFixPreflight.decision.fixes_applied_now ? "yes" : "no" }} /
            training {{ dataset2StagingFixPreflight.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2StagingFixPreflight.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2CleanupExecutionSpec" class="report">
          <strong>Dataset2 Cleanup Execution Spec / {{ dataset2CleanupExecutionSpec.status }}</strong>
          <span>
            event {{ dataset2CleanupExecutionSpec.event_id }} /
            steps {{ dataset2CleanupExecutionSpec.summary.step_count }} /
            source blocked {{ dataset2CleanupExecutionSpec.summary.blocked_source_check_count }}
          </span>
          <span>
            executable code {{ dataset2CleanupExecutionSpec.spec.contains_executable_code ? "yes" : "no" }} /
            can execute {{ dataset2CleanupExecutionSpec.spec.can_execute_now ? "yes" : "no" }} /
            training {{ dataset2CleanupExecutionSpec.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2CleanupExecutionSpec.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2CleanupDryRun" class="report">
          <strong>Dataset2 Cleanup Dry Run / {{ dataset2CleanupDryRun.status }}</strong>
          <span>
            event {{ dataset2CleanupDryRun.event_id }} /
            checks {{ dataset2CleanupDryRun.summary.check_count }} /
            blocked {{ dataset2CleanupDryRun.summary.blocked_check_count }}
          </span>
          <span>
            application {{ dataset2CleanupDryRun.decision.cleanup_application_allowed_now ? "allowed" : "blocked" }} /
            cleanup {{ dataset2CleanupDryRun.decision.cleanup_executed_now ? "executed" : "not executed" }} /
            training {{ dataset2CleanupDryRun.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2CleanupDryRun.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2ManualEvidence" class="report">
          <strong>Dataset2 Manual Evidence / {{ dataset2ManualEvidence.status }}</strong>
          <span>
            event {{ dataset2ManualEvidence.event_id }} /
            sections {{ dataset2ManualEvidence.summary.provided_section_count }} /
            blocked {{ dataset2ManualEvidence.summary.blocked_check_count }}
          </span>
          <span>
            evidence accepted {{ dataset2ManualEvidence.decision.manual_evidence_accepted_for_review ? "yes" : "no" }} /
            cleanup {{ dataset2ManualEvidence.decision.cleanup_executed_now ? "executed" : "not executed" }} /
            training {{ dataset2ManualEvidence.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2ManualEvidence.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2ManualEvidenceAcceptance" class="report">
          <strong>Dataset2 Manual Evidence Acceptance / {{ dataset2ManualEvidenceAcceptance.status }}</strong>
          <span>
            event {{ dataset2ManualEvidenceAcceptance.event_id }} /
            source {{ dataset2ManualEvidenceAcceptance.manual_evidence_verification_id }} /
            blocked {{ dataset2ManualEvidenceAcceptance.summary.blocked_check_count }}
          </span>
          <span>
            ready for review {{ dataset2ManualEvidenceAcceptance.decision.manual_evidence_ready_for_cleanup_application_review ? "yes" : "no" }} /
            cleanup {{ dataset2ManualEvidenceAcceptance.decision.cleanup_executed_now ? "executed" : "not executed" }} /
            training {{ dataset2ManualEvidenceAcceptance.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2ManualEvidenceAcceptance.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2CleanupApplicationReview" class="report">
          <strong>Dataset2 Cleanup Application Review / {{ dataset2CleanupApplicationReview.status }}</strong>
          <span>
            event {{ dataset2CleanupApplicationReview.event_id }} /
            source {{ dataset2CleanupApplicationReview.acceptance_review_id }} /
            blocked {{ dataset2CleanupApplicationReview.summary.blocked_check_count }}
          </span>
          <span>
            ready for future plan {{ dataset2CleanupApplicationReview.decision.cleanup_application_ready_for_future_plan ? "yes" : "no" }} /
            cleanup {{ dataset2CleanupApplicationReview.decision.cleanup_executed_now ? "executed" : "not executed" }} /
            training {{ dataset2CleanupApplicationReview.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2CleanupApplicationReview.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2CleanupExecutionApprovalPlan" class="report">
          <strong>Dataset2 Cleanup Execution Approval / {{ dataset2CleanupExecutionApprovalPlan.status }}</strong>
          <span>
            event {{ dataset2CleanupExecutionApprovalPlan.event_id }} /
            source {{ dataset2CleanupExecutionApprovalPlan.cleanup_application_review_id }} /
            steps {{ dataset2CleanupExecutionApprovalPlan.approval_plan.step_count }} /
            blocked {{ dataset2CleanupExecutionApprovalPlan.summary.blocked_check_count }}
          </span>
          <span>
            ready for approval {{ dataset2CleanupExecutionApprovalPlan.decision.cleanup_execution_plan_ready_for_manual_approval ? "yes" : "no" }} /
            approved {{ dataset2CleanupExecutionApprovalPlan.decision.cleanup_execution_approved_now ? "yes" : "no" }} /
            training {{ dataset2CleanupExecutionApprovalPlan.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2CleanupExecutionApprovalPlan.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2CleanupExecutionManualApproval" class="report">
          <strong>Dataset2 Manual Cleanup Approval / {{ dataset2CleanupExecutionManualApproval.status }}</strong>
          <span>
            event {{ dataset2CleanupExecutionManualApproval.event_id }} /
            source {{ dataset2CleanupExecutionManualApproval.approval_plan_id }} /
            steps {{ dataset2CleanupExecutionManualApproval.source_approval_plan.step_count }} /
            blocked {{ dataset2CleanupExecutionManualApproval.summary.blocked_check_count }}
          </span>
          <span>
            metadata accepted {{ dataset2CleanupExecutionManualApproval.decision.cleanup_execution_approval_metadata_accepted ? "yes" : "no" }} /
            execute now {{ dataset2CleanupExecutionManualApproval.decision.can_execute_cleanup_now ? "yes" : "no" }} /
            training {{ dataset2CleanupExecutionManualApproval.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2CleanupExecutionManualApproval.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2CleanupExecutionPreflight" class="report">
          <strong>Dataset2 Cleanup Preflight / {{ dataset2CleanupExecutionPreflight.status }}</strong>
          <span>
            event {{ dataset2CleanupExecutionPreflight.event_id }} /
            source {{ dataset2CleanupExecutionPreflight.manual_approval_id }} /
            staged {{ dataset2CleanupExecutionPreflight.summary.staging_record_count }} /
            blocked {{ dataset2CleanupExecutionPreflight.summary.blocked_check_count }}
          </span>
          <span>
            dry-run ready {{ dataset2CleanupExecutionPreflight.decision.cleanup_execution_preflight_ready_for_dry_run ? "yes" : "no" }} /
            execute now {{ dataset2CleanupExecutionPreflight.decision.can_execute_cleanup_now ? "yes" : "no" }} /
            training {{ dataset2CleanupExecutionPreflight.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2CleanupExecutionPreflight.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2CleanupExecutionDryRun" class="report">
          <strong>Dataset2 Cleanup Dry-Run / {{ dataset2CleanupExecutionDryRun.status }}</strong>
          <span>
            event {{ dataset2CleanupExecutionDryRun.event_id }} /
            source {{ dataset2CleanupExecutionDryRun.preflight_id }} /
            records {{ dataset2CleanupExecutionDryRun.summary.candidate_record_count }} /
            simulated {{ dataset2CleanupExecutionDryRun.summary.simulated_mutation_count }}
          </span>
          <span>
            ready for review {{ dataset2CleanupExecutionDryRun.decision.cleanup_execution_dry_run_ready_for_review ? "yes" : "no" }} /
            execute now {{ dataset2CleanupExecutionDryRun.decision.can_execute_cleanup_now ? "yes" : "no" }} /
            training {{ dataset2CleanupExecutionDryRun.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2CleanupExecutionDryRun.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2CleanupExecutionDryRunReview" class="report">
          <strong>Dataset2 Cleanup Dry-Run Review / {{ dataset2CleanupExecutionDryRunReview.status }}</strong>
          <span>
            event {{ dataset2CleanupExecutionDryRunReview.event_id }} /
            source {{ dataset2CleanupExecutionDryRunReview.dry_run_id }} /
            records {{ dataset2CleanupExecutionDryRunReview.summary.candidate_record_count }} /
            simulated {{ dataset2CleanupExecutionDryRunReview.summary.simulated_mutation_count }}
          </span>
          <span>
            accepted {{ dataset2CleanupExecutionDryRunReview.decision.cleanup_execution_dry_run_review_accepted ? "yes" : "no" }} /
            execute now {{ dataset2CleanupExecutionDryRunReview.decision.can_execute_cleanup_now ? "yes" : "no" }} /
            training {{ dataset2CleanupExecutionDryRunReview.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2CleanupExecutionDryRunReview.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2CleanupExecutionPlan" class="report">
          <strong>Dataset2 Cleanup Execution Plan / {{ dataset2CleanupExecutionPlan.status }}</strong>
          <span>
            event {{ dataset2CleanupExecutionPlan.event_id }} /
            source {{ dataset2CleanupExecutionPlan.dry_run_review_id }} /
            auto {{ dataset2CleanupExecutionPlan.summary.automated_operation_count }} /
            manual {{ dataset2CleanupExecutionPlan.summary.manual_operation_count }}
          </span>
          <span>
            preflight {{ dataset2CleanupExecutionPlan.decision.cleanup_execution_plan_ready_for_preflight ? "ready" : "blocked" }} /
            execute now {{ dataset2CleanupExecutionPlan.decision.can_execute_cleanup_now ? "yes" : "no" }} /
            training {{ dataset2CleanupExecutionPlan.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2CleanupExecutionPlan.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2CleanupExecutionPlanPreflight" class="report">
          <strong>Dataset2 Cleanup Plan Preflight / {{ dataset2CleanupExecutionPlanPreflight.status }}</strong>
          <span>
            event {{ dataset2CleanupExecutionPlanPreflight.event_id }} /
            source {{ dataset2CleanupExecutionPlanPreflight.execution_plan_id }} /
            staged {{ dataset2CleanupExecutionPlanPreflight.summary.staging_record_count }} /
            auto {{ dataset2CleanupExecutionPlanPreflight.summary.automated_operation_count }}
          </span>
          <span>
            dry-run {{ dataset2CleanupExecutionPlanPreflight.decision.cleanup_execution_plan_preflight_ready_for_dry_run ? "ready" : "blocked" }} /
            execute now {{ dataset2CleanupExecutionPlanPreflight.decision.can_execute_cleanup_now ? "yes" : "no" }} /
            training {{ dataset2CleanupExecutionPlanPreflight.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2CleanupExecutionPlanPreflight.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2ControlledCleanupDryRun" class="report">
          <strong>Dataset2 Controlled Cleanup Dry-Run / {{ dataset2ControlledCleanupDryRun.status }}</strong>
          <span>
            event {{ dataset2ControlledCleanupDryRun.event_id }} /
            source {{ dataset2ControlledCleanupDryRun.plan_preflight_id }} /
            staged {{ dataset2ControlledCleanupDryRun.summary.staging_record_count_before }} /
            simulated {{ dataset2ControlledCleanupDryRun.summary.simulated_mutation_count }}
          </span>
          <span>
            auto {{ dataset2ControlledCleanupDryRun.summary.automated_operation_count }} /
            manual {{ dataset2ControlledCleanupDryRun.summary.manual_operation_count }} /
            review {{ dataset2ControlledCleanupDryRun.decision.controlled_cleanup_dry_run_ready_for_review ? "ready" : "blocked" }}
          </span>
          <span>
            execute now {{ dataset2ControlledCleanupDryRun.decision.can_execute_cleanup_now ? "yes" : "no" }} /
            training {{ dataset2ControlledCleanupDryRun.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2ControlledCleanupDryRun.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2ControlledCleanupDryRunReview" class="report">
          <strong>Dataset2 Controlled Dry-Run Review / {{ dataset2ControlledCleanupDryRunReview.status }}</strong>
          <span>
            event {{ dataset2ControlledCleanupDryRunReview.event_id }} /
            source {{ dataset2ControlledCleanupDryRunReview.controlled_dry_run_id }} /
            simulated {{ dataset2ControlledCleanupDryRunReview.summary.simulated_mutation_count }}
          </span>
          <span>
            accepted {{ dataset2ControlledCleanupDryRunReview.decision.controlled_cleanup_dry_run_review_accepted ? "yes" : "no" }} /
            execute now {{ dataset2ControlledCleanupDryRunReview.decision.can_execute_cleanup_now ? "yes" : "no" }} /
            training {{ dataset2ControlledCleanupDryRunReview.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2ControlledCleanupDryRunReview.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2ControlledCleanupApproval" class="report">
          <strong>Dataset2 Controlled Cleanup Approval / {{ dataset2ControlledCleanupApproval.status }}</strong>
          <span>
            event {{ dataset2ControlledCleanupApproval.event_id }} /
            source {{ dataset2ControlledCleanupApproval.controlled_review_id }} /
            simulated {{ dataset2ControlledCleanupApproval.summary.simulated_mutation_count }}
          </span>
          <span>
            preflight {{ dataset2ControlledCleanupApproval.decision.can_generate_controlled_cleanup_execution_preflight_now ? "ready" : "blocked" }} /
            execute now {{ dataset2ControlledCleanupApproval.decision.can_execute_cleanup_now ? "yes" : "no" }} /
            training {{ dataset2ControlledCleanupApproval.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2ControlledCleanupApproval.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2ControlledCleanupPreflight" class="report">
          <strong>Dataset2 Controlled Cleanup Preflight / {{ dataset2ControlledCleanupPreflight.status }}</strong>
          <span>
            event {{ dataset2ControlledCleanupPreflight.event_id }} /
            source {{ dataset2ControlledCleanupPreflight.controlled_approval_id }} /
            staged {{ dataset2ControlledCleanupPreflight.summary.staging_record_count }}
          </span>
          <span>
            apply dry-run {{ dataset2ControlledCleanupPreflight.decision.controlled_cleanup_execution_preflight_ready_for_apply_dry_run ? "ready" : "blocked" }} /
            execute now {{ dataset2ControlledCleanupPreflight.decision.can_execute_cleanup_now ? "yes" : "no" }} /
            training {{ dataset2ControlledCleanupPreflight.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2ControlledCleanupPreflight.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2ControlledCleanupApplyDryRun" class="report">
          <strong>Dataset2 Controlled Apply Dry-Run / {{ dataset2ControlledCleanupApplyDryRun.status }}</strong>
          <span>
            event {{ dataset2ControlledCleanupApplyDryRun.event_id }} /
            source {{ dataset2ControlledCleanupApplyDryRun.controlled_preflight_id }} /
            staged {{ dataset2ControlledCleanupApplyDryRun.summary.staging_record_count_before }}
          </span>
          <span>
            simulated {{ dataset2ControlledCleanupApplyDryRun.summary.simulated_mutation_count }} /
            review {{ dataset2ControlledCleanupApplyDryRun.decision.controlled_cleanup_apply_dry_run_ready_for_review ? "ready" : "blocked" }} /
            execute now {{ dataset2ControlledCleanupApplyDryRun.decision.can_execute_cleanup_now ? "yes" : "no" }} /
            training {{ dataset2ControlledCleanupApplyDryRun.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2ControlledCleanupApplyDryRun.decision.next_required_action }}</small>
        </div>
        <div v-if="dataset2ControlledCleanupApplyDryRunReview" class="report">
          <strong>Dataset2 Controlled Apply Review / {{ dataset2ControlledCleanupApplyDryRunReview.status }}</strong>
          <span>
            event {{ dataset2ControlledCleanupApplyDryRunReview.event_id }} /
            source {{ dataset2ControlledCleanupApplyDryRunReview.apply_dry_run_id }} /
            simulated {{ dataset2ControlledCleanupApplyDryRunReview.summary.simulated_mutation_count }}
          </span>
          <span>
            accepted {{ dataset2ControlledCleanupApplyDryRunReview.decision.controlled_cleanup_apply_dry_run_review_accepted ? "yes" : "no" }} /
            execute now {{ dataset2ControlledCleanupApplyDryRunReview.decision.can_execute_cleanup_now ? "yes" : "no" }} /
            training {{ dataset2ControlledCleanupApplyDryRunReview.decision.training_started_now ? "started" : "not started" }}
          </span>
          <small>{{ dataset2ControlledCleanupApplyDryRunReview.decision.next_required_action }}</small>
        </div>
        <div class="actions">
          <button data-testid="dataset2-readiness-button" @click="loadDataset2Readiness" :disabled="dataset2Loading">
            {{ dataset2Loading ? "Dataset2 checking" : "Check Dataset2 readiness" }}
          </button>
          <button data-testid="dataset2-preview-button" @click="loadDataset2Preview" :disabled="dataset2Loading">
            Dataset2 normalized preview
          </button>
          <button data-testid="dataset2-cleanup-package-button" @click="loadDataset2CleanupPackage" :disabled="dataset2Loading">
            Dataset2 cleanup package
          </button>
          <button data-testid="dataset2-import-queue-review-button" @click="recordDataset2ImportQueueReview" :disabled="dataset2Loading">
            Dataset2 import queue review
          </button>
          <button data-testid="dataset2-import-queue-history-button" @click="loadDataset2ImportQueueReviews" :disabled="dataset2Loading">
            Dataset2 queue history
          </button>
          <button data-testid="dataset2-staging-import-button" @click="importDataset2ToStaging" :disabled="dataset2Loading">
            Dataset2 staging import
          </button>
          <button data-testid="dataset2-staging-summary-button" @click="loadDataset2Staging" :disabled="dataset2Loading">
            Dataset2 staging status
          </button>
          <button data-testid="dataset2-staging-quality-review-button" @click="reviewDataset2StagingQuality" :disabled="dataset2Loading">
            Dataset2 quality review
          </button>
          <button data-testid="dataset2-staging-fix-plan-button" @click="planDataset2StagingFixes" :disabled="dataset2Loading">
            Dataset2 fix plan
          </button>
          <button data-testid="dataset2-staging-fix-approval-button" @click="approveDataset2StagingFixPlan" :disabled="dataset2Loading">
            Dataset2 approve preflight
          </button>
          <button data-testid="dataset2-staging-fix-preflight-button" @click="preflightDataset2StagingFixes" :disabled="dataset2Loading">
            Dataset2 fix preflight
          </button>
          <button data-testid="dataset2-cleanup-execution-spec-button" @click="specDataset2CleanupExecution" :disabled="dataset2Loading">
            Dataset2 execution spec
          </button>
          <button data-testid="dataset2-cleanup-dry-run-button" @click="verifyDataset2CleanupDryRun" :disabled="dataset2Loading">
            Dataset2 dry-run verify
          </button>
          <button data-testid="dataset2-manual-evidence-button" @click="verifyDataset2ManualEvidence" :disabled="dataset2Loading">
            Dataset2 manual evidence
          </button>
          <button data-testid="dataset2-manual-evidence-acceptance-button" @click="reviewDataset2ManualEvidenceAcceptance" :disabled="dataset2Loading">
            Dataset2 evidence acceptance
          </button>
          <button data-testid="dataset2-cleanup-application-review-button" @click="reviewDataset2CleanupApplication" :disabled="dataset2Loading">
            Dataset2 cleanup application
          </button>
          <button data-testid="dataset2-cleanup-execution-approval-button" @click="planDataset2CleanupExecutionApproval" :disabled="dataset2Loading">
            Dataset2 cleanup approval
          </button>
          <button data-testid="dataset2-cleanup-execution-manual-approval-button" @click="approveDataset2CleanupExecutionManually" :disabled="dataset2Loading">
            Dataset2 manual approval
          </button>
          <button data-testid="dataset2-cleanup-execution-preflight-button" @click="preflightDataset2CleanupExecution" :disabled="dataset2Loading">
            Dataset2 cleanup preflight
          </button>
          <button data-testid="dataset2-cleanup-execution-dry-run-button" @click="dryRunDataset2CleanupExecution" :disabled="dataset2Loading">
            Dataset2 cleanup dry-run
          </button>
          <button data-testid="dataset2-cleanup-execution-dry-run-review-button" @click="reviewDataset2CleanupExecutionDryRun" :disabled="dataset2Loading">
            Dataset2 dry-run review
          </button>
          <button data-testid="dataset2-cleanup-execution-plan-button" @click="planDataset2CleanupExecution" :disabled="dataset2Loading">
            Dataset2 execution plan
          </button>
          <button data-testid="dataset2-cleanup-execution-plan-preflight-button" @click="preflightDataset2CleanupExecutionPlan" :disabled="dataset2Loading">
            Dataset2 plan preflight
          </button>
          <button data-testid="dataset2-controlled-cleanup-dry-run-button" @click="dryRunDataset2ControlledCleanup" :disabled="dataset2Loading">
            Dataset2 controlled dry-run
          </button>
          <button data-testid="dataset2-controlled-cleanup-dry-run-review-button" @click="reviewDataset2ControlledCleanupDryRun" :disabled="dataset2Loading">
            Dataset2 controlled review
          </button>
          <button data-testid="dataset2-controlled-cleanup-approval-button" @click="approveDataset2ControlledCleanup" :disabled="dataset2Loading">
            Dataset2 controlled approval
          </button>
          <button data-testid="dataset2-controlled-cleanup-preflight-button" @click="preflightDataset2ControlledCleanup" :disabled="dataset2Loading">
            Dataset2 controlled preflight
          </button>
          <button data-testid="dataset2-controlled-cleanup-apply-dry-run-button" @click="dryRunDataset2ControlledCleanupApply" :disabled="dataset2Loading">
            Dataset2 apply dry-run
          </button>
          <button data-testid="dataset2-controlled-cleanup-apply-dry-run-review-button" @click="reviewDataset2ControlledCleanupApplyDryRun" :disabled="dataset2Loading">
            Dataset2 apply review
          </button>
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

type Dataset2Readiness = {
  stage: string;
  status: string;
  record_count: number;
  quality: {
    invalid_risk_level_count: number;
    stringified_list_item_count: number;
    missing_evidence_counts: Record<string, number>;
    missing_historical_outcome_field_counts: Record<string, number>;
    unsafe_model_target_count: number;
    low_support_action_labels: Array<{ action_label: string; count: number }>;
  };
  decision: {
    can_use_as_rule_knowledge: boolean;
    can_import_normalized_preview: boolean;
    training_gate_passed?: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type Dataset2Preview = {
  stage: string;
  status: string;
  preview_count: number;
  records: Array<{
    pattern_id: string;
    pattern_name?: string;
    action_label?: string;
    risk_level: string;
    risk_level_original?: string;
    quality_flags: string[];
  }>;
  decision: {
    writes_database_now: boolean;
    training_started_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2CleanupPackage = {
  stage: string;
  status: string;
  package_id: string;
  record_count: number;
  source_data_hash?: string | null;
  normalized_records_hash: string;
  summary: {
    risk_level_change_count: number;
    stringified_list_item_count: number;
    missing_evidence_total: number;
    missing_historical_outcome_total: number;
    low_support_action_label_count: number;
    unsafe_model_target_count: number;
    review_action_count: number;
    blocking_action_count: number;
  };
  cleanup_actions: Array<{
    name: string;
    status: string;
    count: number;
    reason: string;
  }>;
  decision: {
    cleanup_package_ready: boolean;
    cleanup_can_be_applied_automatically: boolean;
    can_export_file_now: boolean;
    can_import_to_database_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2ImportQueueReview = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  package_id: string;
  record_count: number;
  summary: {
    review_action_count: number;
    blocking_action_count: number;
  };
  review: {
    reviewed_by: string;
    note?: string | null;
    source_records_included: boolean;
    normalized_records_included: boolean;
  };
  decision: {
    writes_existing_event_now: boolean;
    normalized_records_persisted: boolean;
    training_started_now: boolean;
    can_import_to_database_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2StagingImport = {
  stage: string;
  status: string;
  package_id: string;
  record_count: number;
  imported_count: number;
  review_event_id?: number;
  staging_import_event_id?: number;
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now?: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    normalized_records_persisted_to_staging: boolean;
    normalized_records_persisted_to_training: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2StagingRecord = {
  id: number;
  package_id: string;
  pattern_id: string;
  action_label?: string;
  risk_level?: string;
  split_tag?: string;
  stock_code?: string;
  signal_date?: string;
  status: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type Dataset2StagingSummary = {
  stage: string;
  status: string;
  record_count: number;
  package_count: number;
  latest_packages: Array<{ package_id: string; record_count: number; latest_created_at?: string }>;
  action_label_counts: Record<string, number>;
  risk_level_counts: Record<string, number>;
  decision: {
    writes_database_now: boolean;
    writes_learning_samples_now: boolean;
    learning_sample_count: number;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2Gate = {
  name: string;
  status: string;
  value: unknown;
  limit: unknown;
  reason: string;
};

type Dataset2StagingQualityReview = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  package_id?: string | null;
  record_count: number;
  counts: {
    action_labels: Record<string, number>;
    risk_levels: Record<string, number>;
    splits: Record<string, number>;
    quality_flags: Record<string, number>;
    cleanup_operations: Record<string, number>;
  };
  summary: {
    blocked_gate_count: number;
    warning_gate_count: number;
    missing_historical_count: number;
    missing_required_count: number;
    low_support_label_count: number;
  };
  gates: Dataset2Gate[];
  review: {
    reviewed_by: string;
    note?: string | null;
    record_bodies_included: boolean;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_learning_samples_now: boolean;
    training_started_now: boolean;
    training_freeze_allowed: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2StagingFixPlan = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  quality_review_id?: number;
  package_id?: string | null;
  record_count?: number;
  source_quality_status?: string;
  action_items: Array<{
    id: string;
    gate_name: string;
    priority: string;
    execution_mode: string;
    title: string;
    acceptance_checks: string[];
    forbidden_actions: string[];
    review_only: boolean;
  }>;
  summary: {
    action_item_count: number;
    blocked_gate_count: number;
    warning_gate_count: number;
    manual_action_count: number;
    automated_action_count: number;
  };
  plan: {
    requires_operator_approval: boolean;
    can_be_applied_automatically_now: boolean;
    record_bodies_included: boolean;
    recommended_sequence: string[];
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    training_started_now: boolean;
    training_freeze_allowed: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  review: {
    planned_by: string;
    note?: string | null;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2StagingFixApproval = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  fix_plan_event_id?: number | null;
  quality_review_id?: number | null;
  package_id?: string | null;
  approval: {
    approved_by: string;
    approval_decision: string;
    note?: string | null;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    approval_allows_fix_application_now: boolean;
    can_generate_preflight_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2StagingFixPreflight = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  approval_event_id?: number | null;
  fix_plan_event_id?: number | null;
  preflight_checks: Array<{
    id: string;
    name: string;
    gate_name?: string;
    status: string;
    forbidden_actions: string[];
    review_only: boolean;
  }>;
  summary: {
    check_count: number;
    blocked_check_count: number;
    record_mutation_count: number;
    action_item_count: number;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    fixes_applied_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2CleanupExecutionSpec = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  preflight_event_id?: number | null;
  approval_event_id?: number | null;
  fix_plan_event_id?: number | null;
  execution_steps: Array<{
    id: string;
    name: string;
    execution_mode: string;
    source_check_status?: string;
    forbidden_actions: string[];
    review_only: boolean;
  }>;
  summary: {
    step_count: number;
    blocked_source_check_count: number;
    machine_assisted_step_count: number;
    manual_step_count: number;
    record_body_count: number;
  };
  spec: {
    requires_operator_approval: boolean;
    can_execute_now: boolean;
    contains_executable_code: boolean;
    sql_included: boolean;
    record_bodies_included: boolean;
    recommended_sequence: string[];
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    cleanup_executed_now: boolean;
    execution_spec_can_be_applied_now: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  review: {
    specified_by: string;
    note?: string | null;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2CleanupDryRun = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  execution_spec_event_id?: number | null;
  preflight_event_id?: number | null;
  checks: Array<{
    name: string;
    status: string;
    reason: string;
    review_only: boolean;
  }>;
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    execution_step_count: number;
    blocked_source_check_count: number;
    record_body_count: number;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    dry_run_executed_now: boolean;
    cleanup_executed_now: boolean;
    cleanup_application_allowed_now: boolean;
    can_advance_to_manual_cleanup_application_review: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  verification: {
    verified_by: string;
    note?: string | null;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2ManualEvidence = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  dry_run_verification_id?: number | null;
  execution_spec_event_id?: number | null;
  evidence_summary: {
    provided_sections: string[];
    provided_section_count: number;
    evidence_package_hash?: string | null;
    record_bodies_included: boolean;
    evidence_package_body_included: boolean;
  };
  checks: Array<{
    name: string;
    status: string;
    reason: string;
    review_only: boolean;
  }>;
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    provided_section_count: number;
    record_bodies_included: boolean;
    dry_run_blocked_check_count: number;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    manual_evidence_accepted_for_review: boolean;
    cleanup_application_allowed_now: boolean;
    cleanup_executed_now: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  verification: {
    verified_by: string;
    note?: string | null;
    evidence_package_body_included: boolean;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2ManualEvidenceAcceptance = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  manual_evidence_verification_id?: number | null;
  dry_run_verification_id?: number | null;
  evidence_summary: Dataset2ManualEvidence["evidence_summary"];
  source_manual_evidence_summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    provided_section_count: number;
    record_bodies_included: boolean;
  };
  checks: Dataset2ManualEvidence["checks"];
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    manual_evidence_check_count: number;
    manual_evidence_blocked_check_count: number | null;
    provided_section_count: number;
    record_bodies_included: boolean;
  };
  acceptance: {
    accepted_by: string;
    acceptance_decision: string;
    note?: string | null;
    record_bodies_included: boolean;
    evidence_package_body_included: boolean;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    manual_evidence_acceptance_recorded: boolean;
    manual_evidence_ready_for_cleanup_application_review: boolean;
    cleanup_application_allowed_now: boolean;
    cleanup_executed_now: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2CleanupApplicationReview = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  acceptance_review_id?: number | null;
  manual_evidence_verification_id?: number | null;
  dry_run_verification_id?: number | null;
  evidence_summary: Dataset2ManualEvidence["evidence_summary"];
  source_acceptance_summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    manual_evidence_blocked_check_count: number | null;
    record_bodies_included: boolean;
  };
  checks: Dataset2ManualEvidence["checks"];
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    acceptance_check_count: number;
    acceptance_blocked_check_count: number | null;
    provided_section_count: number;
    record_bodies_included: boolean;
  };
  review: {
    reviewed_by: string;
    review_decision: string;
    note?: string | null;
    record_bodies_included: boolean;
    evidence_package_body_included: boolean;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    cleanup_application_review_recorded: boolean;
    cleanup_application_ready_for_future_plan: boolean;
    cleanup_application_allowed_now: boolean;
    cleanup_executed_now: boolean;
    future_cleanup_execution_requires_separate_approval: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2CleanupExecutionApprovalPlan = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  cleanup_application_review_id?: number | null;
  acceptance_review_id?: number | null;
  manual_evidence_verification_id?: number | null;
  evidence_summary: Dataset2ManualEvidence["evidence_summary"];
  source_cleanup_application_summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    record_bodies_included: boolean;
  };
  approval_plan: {
    steps: Array<{
      id: string;
      name: string;
      execution_mode: string;
      approval_required: boolean;
      contains_sql: boolean;
      contains_executable_code: boolean;
      can_execute_now: boolean;
      forbidden_actions: string[];
    }>;
    step_count: number;
    contains_sql: boolean;
    contains_executable_code: boolean;
    can_execute_now: boolean;
    requires_manual_execution_approval: boolean;
    future_execution_requires_separate_approval: boolean;
  };
  checks: Dataset2ManualEvidence["checks"];
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    application_check_count: number;
    application_blocked_check_count: number | null;
    approval_step_count: number;
    record_bodies_included: boolean;
  };
  planning: {
    planned_by: string;
    plan_decision: string;
    note?: string | null;
    record_bodies_included: boolean;
    evidence_package_body_included: boolean;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    cleanup_execution_approval_plan_recorded: boolean;
    cleanup_execution_plan_ready_for_manual_approval: boolean;
    cleanup_execution_approved_now: boolean;
    cleanup_application_allowed_now: boolean;
    cleanup_executed_now: boolean;
    can_execute_cleanup_now: boolean;
    future_cleanup_execution_requires_separate_approval: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2CleanupExecutionManualApproval = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  approval_plan_id?: number | null;
  cleanup_application_review_id?: number | null;
  manual_evidence_verification_id?: number | null;
  evidence_summary: Dataset2ManualEvidence["evidence_summary"];
  source_approval_plan_summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    approval_step_count: number;
    record_bodies_included: boolean;
  };
  source_approval_plan: {
    step_count: number;
    contains_sql: boolean;
    contains_executable_code: boolean;
    can_execute_now: boolean;
    requires_manual_execution_approval: boolean;
    steps_body_included: boolean;
  };
  checks: Dataset2ManualEvidence["checks"];
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    source_plan_check_count: number;
    source_plan_blocked_check_count: number | null;
    approval_step_count: number;
    record_bodies_included: boolean;
  };
  manual_approval: {
    approved_by: string;
    approval_decision: string;
    note?: string | null;
    record_bodies_included: boolean;
    evidence_package_body_included: boolean;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    cleanup_execution_manual_approval_recorded: boolean;
    cleanup_execution_approval_metadata_accepted: boolean;
    cleanup_execution_approved_for_future_preflight: boolean;
    cleanup_execution_approved_now: boolean;
    cleanup_application_allowed_now: boolean;
    cleanup_executed_now: boolean;
    can_execute_cleanup_now: boolean;
    can_generate_cleanup_execution_preflight_now: boolean;
    future_cleanup_execution_preflight_required: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2CleanupExecutionPreflight = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  manual_approval_id?: number | null;
  approval_plan_id?: number | null;
  package_id?: string | null;
  evidence_summary: Dataset2ManualEvidence["evidence_summary"];
  preflight: {
    lock_key: string | null;
    rollback_plan_required: boolean;
    rollback_plan: {
      required: boolean;
      mode: string;
      snapshot_required_before_execution: boolean;
      verified_now: boolean;
    };
    environment: {
      database_path: string;
      package_id?: string | null;
      staging_record_count: number;
      learning_sample_count: number;
      source_dataset_mutation_allowed: boolean;
    };
    impact: {
      package_id?: string | null;
      candidate_staging_record_count: number;
      learning_sample_count_before: number;
      expected_learning_sample_count_after: number;
      affected_rows_body_included: boolean;
    };
    contains_sql: boolean;
    contains_executable_code: boolean;
    can_execute_now: boolean;
  };
  checks: Dataset2ManualEvidence["checks"];
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    source_manual_approval_check_count: number;
    source_manual_approval_blocked_check_count: number | null;
    staging_record_count: number;
    learning_sample_count: number;
    record_bodies_included: boolean;
  };
  request: {
    requested_by: string;
    preflight_decision: string;
    note?: string | null;
    record_bodies_included: boolean;
    evidence_package_body_included: boolean;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    cleanup_execution_preflight_recorded: boolean;
    cleanup_execution_preflight_ready_for_dry_run: boolean;
    cleanup_execution_approved_now: boolean;
    cleanup_application_allowed_now: boolean;
    cleanup_executed_now: boolean;
    can_execute_cleanup_now: boolean;
    future_cleanup_execution_dry_run_required: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2CleanupExecutionDryRun = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  preflight_id?: number | null;
  manual_approval_id?: number | null;
  package_id?: string | null;
  evidence_summary: Dataset2ManualEvidence["evidence_summary"];
  simulation: {
    package_id?: string | null;
    candidate_record_count: number;
    records_with_operations: number;
    records_with_quality_flags: number;
    simulated_mutation_count: number;
    operation_counts: Record<string, number>;
    field_counts: Record<string, number>;
    quality_flag_counts: Record<string, number>;
    action_label_counts: Record<string, number>;
    risk_level_counts: Record<string, number>;
    split_counts: Record<string, number>;
    learning_sample_count_before: number;
    expected_learning_sample_count_after: number;
    contains_sql: boolean;
    contains_executable_code: boolean;
    can_execute_now: boolean;
    record_bodies_included: boolean;
    affected_rows_body_included: boolean;
  };
  checks: Dataset2ManualEvidence["checks"];
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    source_preflight_check_count: number;
    source_preflight_blocked_check_count: number | null;
    candidate_record_count: number;
    simulated_mutation_count: number;
    learning_sample_count: number;
    record_bodies_included: boolean;
  };
  dry_run: {
    simulated_by: string;
    dry_run_decision: string;
    note?: string | null;
    record_bodies_included: boolean;
    evidence_package_body_included: boolean;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    cleanup_execution_dry_run_recorded: boolean;
    cleanup_execution_dry_run_ready_for_review: boolean;
    cleanup_execution_approved_now: boolean;
    cleanup_application_allowed_now: boolean;
    cleanup_executed_now: boolean;
    can_execute_cleanup_now: boolean;
    future_cleanup_execution_review_required: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2CleanupExecutionDryRunReview = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  dry_run_id?: number | null;
  preflight_id?: number | null;
  package_id?: string | null;
  evidence_summary: Dataset2ManualEvidence["evidence_summary"];
  source_dry_run_summary: {
    check_count: number;
    blocked_check_count: number | null;
    warning_check_count: number;
    source_preflight_blocked_check_count: number | null;
    candidate_record_count: number;
    simulated_mutation_count: number;
    learning_sample_count: number;
    record_bodies_included: boolean;
  };
  simulation_summary: {
    candidate_record_count: number;
    records_with_operations: number;
    records_with_quality_flags: number;
    simulated_mutation_count: number;
    operation_counts: Record<string, number>;
    field_counts: Record<string, number>;
    quality_flag_counts: Record<string, number>;
    learning_sample_count_before: number;
    expected_learning_sample_count_after: number;
    contains_sql: boolean;
    contains_executable_code: boolean;
    can_execute_now: boolean;
    record_bodies_included: boolean;
    affected_rows_body_included: boolean;
  };
  checks: Dataset2ManualEvidence["checks"];
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    source_dry_run_check_count: number;
    source_dry_run_blocked_check_count: number | null;
    candidate_record_count: number;
    simulated_mutation_count: number;
    learning_sample_count: number;
    record_bodies_included: boolean;
  };
  review: {
    reviewed_by: string;
    review_decision: string;
    note?: string | null;
    record_bodies_included: boolean;
    evidence_package_body_included: boolean;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    cleanup_execution_dry_run_review_recorded: boolean;
    cleanup_execution_dry_run_review_accepted: boolean;
    cleanup_execution_approved_now: boolean;
    cleanup_application_allowed_now: boolean;
    cleanup_executed_now: boolean;
    can_execute_cleanup_now: boolean;
    future_cleanup_execution_plan_required: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2CleanupExecutionPlan = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  dry_run_review_id?: number | null;
  dry_run_id?: number | null;
  package_id?: string | null;
  evidence_summary: Dataset2ManualEvidence["evidence_summary"];
  source_review_summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    candidate_record_count: number;
    simulated_mutation_count: number;
    record_bodies_included: boolean;
  };
  execution_plan: {
    scope: string;
    package_id?: string | null;
    candidate_record_count: number;
    planned_operation_count: number;
    automated_operation_count: number;
    manual_operation_count: number;
    total_simulated_operation_count: number;
    operation_counts: Record<string, number>;
    automated_operation_counts: Record<string, number>;
    manual_operation_counts: Record<string, number>;
    field_counts: Record<string, number>;
    execution_batches: Array<Record<string, any>>;
    manual_backfill_batches: Array<Record<string, any>>;
    contains_sql: boolean;
    contains_executable_code: boolean;
    can_execute_now: boolean;
    record_bodies_included: boolean;
    affected_rows_body_included: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
  };
  checks: Dataset2ManualEvidence["checks"];
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    source_review_blocked_check_count: number | null;
    candidate_record_count: number;
    planned_operation_count: number;
    automated_operation_count: number;
    manual_operation_count: number;
    record_bodies_included: boolean;
  };
  planning: {
    planned_by: string;
    plan_decision: string;
    note?: string | null;
    record_bodies_included: boolean;
    evidence_package_body_included: boolean;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    cleanup_execution_plan_recorded: boolean;
    cleanup_execution_plan_ready_for_preflight: boolean;
    cleanup_execution_approved_now: boolean;
    cleanup_application_allowed_now: boolean;
    cleanup_executed_now: boolean;
    can_execute_cleanup_now: boolean;
    future_cleanup_execution_preflight_required: boolean;
    manual_backfill_required: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2CleanupExecutionPlanPreflight = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  execution_plan_id?: number | null;
  dry_run_review_id?: number | null;
  package_id?: string | null;
  evidence_summary: Dataset2ManualEvidence["evidence_summary"];
  source_plan_summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    candidate_record_count: number;
    automated_operation_count: number;
    manual_operation_count: number;
    record_bodies_included: boolean;
  };
  preflight: {
    package_id?: string | null;
    lock_key?: string | null;
    staging_record_count: number;
    expected_staging_record_count_after: number;
    learning_sample_count: number;
    expected_learning_sample_count_after: number;
    automated_operation_count: number;
    manual_operation_count: number;
    automated_batch_count: number;
    manual_backfill_batch_count: number;
    transaction_required: boolean;
    rollback_required: boolean;
    rollback_plan: string[];
    allowed_tables: string[];
    forbidden_tables: string[];
    allowed_operations: string[];
    automated_batches: Array<Record<string, any>>;
    manual_backfill_batches: Array<Record<string, any>>;
    contains_sql: boolean;
    contains_executable_code: boolean;
    can_execute_now: boolean;
    record_bodies_included: boolean;
    affected_rows_body_included: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
  };
  checks: Dataset2ManualEvidence["checks"];
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    source_plan_blocked_check_count: number | null;
    staging_record_count: number;
    learning_sample_count: number;
    automated_operation_count: number;
    manual_operation_count: number;
    record_bodies_included: boolean;
  };
  request: {
    requested_by: string;
    preflight_decision: string;
    note?: string | null;
    record_bodies_included: boolean;
    evidence_package_body_included: boolean;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    cleanup_execution_plan_preflight_recorded: boolean;
    cleanup_execution_plan_preflight_ready_for_dry_run: boolean;
    cleanup_execution_approved_now: boolean;
    cleanup_application_allowed_now: boolean;
    cleanup_executed_now: boolean;
    can_execute_cleanup_now: boolean;
    future_controlled_cleanup_dry_run_required: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2ControlledCleanupDryRun = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  plan_preflight_id?: number | null;
  execution_plan_id?: number | null;
  package_id?: string | null;
  source_preflight_summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    staging_record_count: number;
    automated_operation_count: number;
    manual_operation_count: number;
    record_bodies_included: boolean;
  };
  simulation: {
    package_id?: string | null;
    lock_key?: string | null;
    staging_record_count_before: number;
    expected_staging_record_count_after: number;
    learning_sample_count_before: number;
    expected_learning_sample_count_after: number;
    automated_operation_count: number;
    manual_operation_count: number;
    automated_batch_count: number;
    manual_backfill_batch_count: number;
    automated_batches: Array<Record<string, any>>;
    manual_backfill_batches: Array<Record<string, any>>;
    simulated_quality_flag_reduction_count: number;
    simulated_manual_flag_remaining_count: number;
    simulated_mutation_count: number;
    contains_sql: boolean;
    contains_executable_code: boolean;
    can_execute_now: boolean;
    record_bodies_included: boolean;
    affected_rows_body_included: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
  };
  checks: Dataset2ManualEvidence["checks"];
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    source_preflight_blocked_check_count: number | null;
    staging_record_count_before: number;
    expected_staging_record_count_after: number;
    learning_sample_count_before: number;
    expected_learning_sample_count_after: number;
    automated_operation_count: number;
    manual_operation_count: number;
    simulated_quality_flag_reduction_count: number;
    simulated_manual_flag_remaining_count: number;
    simulated_mutation_count: number;
    record_bodies_included: boolean;
  };
  dry_run: {
    simulated_by: string;
    dry_run_decision: string;
    note?: string | null;
    record_bodies_included: boolean;
    evidence_package_body_included: boolean;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    controlled_cleanup_dry_run_recorded: boolean;
    controlled_cleanup_dry_run_ready_for_review: boolean;
    cleanup_execution_approved_now: boolean;
    cleanup_application_allowed_now: boolean;
    cleanup_executed_now: boolean;
    can_execute_cleanup_now: boolean;
    future_controlled_cleanup_review_required: boolean;
    manual_backfill_required: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2ControlledCleanupDryRunReview = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  controlled_dry_run_id?: number | null;
  plan_preflight_id?: number | null;
  execution_plan_id?: number | null;
  package_id?: string | null;
  source_dry_run_summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    source_preflight_blocked_check_count: number | null;
    staging_record_count_before: number;
    expected_staging_record_count_after: number;
    automated_operation_count: number;
    manual_operation_count: number;
    simulated_mutation_count: number;
    record_bodies_included: boolean;
  };
  simulation_summary: {
    package_id?: string | null;
    lock_key?: string | null;
    staging_record_count_before: number;
    expected_staging_record_count_after: number;
    learning_sample_count_before: number;
    expected_learning_sample_count_after: number;
    automated_operation_count: number;
    manual_operation_count: number;
    simulated_quality_flag_reduction_count: number;
    simulated_manual_flag_remaining_count: number;
    simulated_mutation_count: number;
    contains_sql: boolean;
    contains_executable_code: boolean;
    can_execute_now: boolean;
    record_bodies_included: boolean;
    affected_rows_body_included: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
  };
  checks: Dataset2ManualEvidence["checks"];
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    source_dry_run_check_count: number;
    source_dry_run_blocked_check_count: number;
    automated_operation_count: number;
    manual_operation_count: number;
    simulated_mutation_count: number;
    record_bodies_included: boolean;
  };
  review: {
    reviewed_by: string;
    review_decision: string;
    note?: string | null;
    record_bodies_included: boolean;
    evidence_package_body_included: boolean;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    controlled_cleanup_dry_run_review_recorded: boolean;
    controlled_cleanup_dry_run_review_accepted: boolean;
    cleanup_execution_approved_now: boolean;
    cleanup_application_allowed_now: boolean;
    cleanup_executed_now: boolean;
    can_execute_cleanup_now: boolean;
    future_controlled_cleanup_execution_approval_required: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2ControlledCleanupApproval = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  controlled_review_id?: number | null;
  controlled_dry_run_id?: number | null;
  plan_preflight_id?: number | null;
  package_id?: string | null;
  approval_scope: {
    package_id?: string | null;
    lock_key?: string | null;
    approval_scope: string;
    allowed_next_stage: string;
    requires_preflight: boolean;
    requires_transaction: boolean;
    requires_rollback: boolean;
    automated_operation_count: number;
    manual_operation_count: number;
    simulated_mutation_count: number;
    contains_sql: boolean;
    contains_executable_code: boolean;
    can_execute_now: boolean;
    record_bodies_included: boolean;
    affected_rows_body_included: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
  };
  checks: Dataset2ManualEvidence["checks"];
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    source_review_check_count: number;
    source_review_blocked_check_count: number;
    automated_operation_count: number;
    manual_operation_count: number;
    simulated_mutation_count: number;
    record_bodies_included: boolean;
  };
  approval: {
    approved_by: string;
    approval_decision: string;
    note?: string | null;
    record_bodies_included: boolean;
    evidence_package_body_included: boolean;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    controlled_cleanup_execution_approval_recorded: boolean;
    controlled_cleanup_execution_approval_accepted: boolean;
    controlled_cleanup_approved_for_future_preflight: boolean;
    cleanup_execution_approved_now: boolean;
    cleanup_application_allowed_now: boolean;
    cleanup_executed_now: boolean;
    can_execute_cleanup_now: boolean;
    can_generate_controlled_cleanup_execution_preflight_now: boolean;
    future_controlled_cleanup_execution_preflight_required: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2ControlledCleanupPreflight = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  controlled_approval_id?: number | null;
  controlled_review_id?: number | null;
  controlled_dry_run_id?: number | null;
  package_id?: string | null;
  preflight: {
    package_id?: string | null;
    lock_key?: string | null;
    staging_record_count: number;
    expected_staging_record_count_after: number;
    approved_staging_record_count: number;
    learning_sample_count: number;
    expected_learning_sample_count_after: number;
    automated_operation_count: number;
    manual_operation_count: number;
    simulated_mutation_count: number;
    transaction_required: boolean;
    rollback_required: boolean;
    rollback_plan: string[];
    allowed_tables: string[];
    forbidden_tables: string[];
    allowed_next_stage: string;
    contains_sql: boolean;
    contains_executable_code: boolean;
    can_execute_now: boolean;
    record_bodies_included: boolean;
    affected_rows_body_included: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
  };
  checks: Dataset2ManualEvidence["checks"];
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    source_approval_check_count: number;
    source_approval_blocked_check_count: number;
    staging_record_count: number;
    learning_sample_count: number;
    automated_operation_count: number;
    manual_operation_count: number;
    simulated_mutation_count: number;
    record_bodies_included: boolean;
  };
  request: {
    requested_by: string;
    preflight_decision: string;
    note?: string | null;
    record_bodies_included: boolean;
    evidence_package_body_included: boolean;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    controlled_cleanup_execution_preflight_recorded: boolean;
    controlled_cleanup_execution_preflight_ready_for_apply_dry_run: boolean;
    cleanup_execution_approved_now: boolean;
    cleanup_application_allowed_now: boolean;
    cleanup_executed_now: boolean;
    can_execute_cleanup_now: boolean;
    future_controlled_cleanup_execution_apply_dry_run_required: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2ControlledCleanupApplyDryRun = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  controlled_preflight_id?: number | null;
  controlled_approval_id?: number | null;
  controlled_review_id?: number | null;
  controlled_dry_run_id?: number | null;
  package_id?: string | null;
  simulation: {
    package_id?: string | null;
    lock_key?: string | null;
    source_controlled_preflight_id?: number | null;
    staging_record_count_before: number;
    expected_staging_record_count_after: number;
    preflight_staging_record_count: number;
    staging_count_still_matches: boolean;
    learning_sample_count_before: number;
    expected_learning_sample_count_after: number;
    automated_operation_count: number;
    manual_operation_count: number;
    records_with_operations: number;
    records_with_quality_flags: number;
    operation_counts: Record<string, number>;
    field_counts: Record<string, number>;
    quality_flag_counts: Record<string, number>;
    simulated_quality_flag_reduction_count: number;
    simulated_manual_flag_remaining_count: number;
    simulated_mutation_count: number;
    transaction_required: boolean;
    rollback_required: boolean;
    contains_sql: boolean;
    contains_executable_code: boolean;
    can_execute_now: boolean;
    record_bodies_included: boolean;
    affected_rows_body_included: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
  };
  checks: Dataset2ManualEvidence["checks"];
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    source_preflight_blocked_check_count: number;
    staging_record_count_before: number;
    expected_staging_record_count_after: number;
    learning_sample_count_before: number;
    expected_learning_sample_count_after: number;
    automated_operation_count: number;
    manual_operation_count: number;
    simulated_quality_flag_reduction_count: number;
    simulated_manual_flag_remaining_count: number;
    simulated_mutation_count: number;
    record_bodies_included: boolean;
  };
  dry_run: {
    simulated_by: string;
    dry_run_decision: string;
    note?: string | null;
    record_bodies_included: boolean;
    evidence_package_body_included: boolean;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    controlled_cleanup_apply_dry_run_recorded: boolean;
    controlled_cleanup_apply_dry_run_ready_for_review: boolean;
    cleanup_execution_approved_now: boolean;
    cleanup_application_allowed_now: boolean;
    cleanup_executed_now: boolean;
    can_execute_cleanup_now: boolean;
    future_controlled_cleanup_apply_review_required: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
};

type Dataset2ControlledCleanupApplyDryRunReview = {
  id?: number;
  event_id?: number;
  stage: string;
  status: string;
  apply_dry_run_id?: number | null;
  controlled_preflight_id?: number | null;
  controlled_approval_id?: number | null;
  controlled_review_id?: number | null;
  controlled_dry_run_id?: number | null;
  package_id?: string | null;
  simulation_summary: {
    package_id?: string | null;
    lock_key?: string | null;
    staging_record_count_before: number;
    expected_staging_record_count_after: number;
    learning_sample_count_before: number;
    expected_learning_sample_count_after: number;
    automated_operation_count: number;
    manual_operation_count: number;
    simulated_quality_flag_reduction_count: number;
    simulated_manual_flag_remaining_count: number;
    simulated_mutation_count: number;
    contains_sql: boolean;
    contains_executable_code: boolean;
    can_execute_now: boolean;
    record_bodies_included: boolean;
    affected_rows_body_included: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
  };
  checks: Dataset2ManualEvidence["checks"];
  summary: {
    check_count: number;
    blocked_check_count: number;
    warning_check_count: number;
    source_dry_run_check_count: number;
    source_dry_run_blocked_check_count: number;
    automated_operation_count: number;
    manual_operation_count: number;
    simulated_mutation_count: number;
    record_bodies_included: boolean;
  };
  review: {
    reviewed_by: string;
    review_decision: string;
    note?: string | null;
    record_bodies_included: boolean;
    evidence_package_body_included: boolean;
  };
  decision: {
    writes_database_now: boolean;
    writes_existing_event_now: boolean;
    writes_staging_records_now: boolean;
    writes_learning_samples_now: boolean;
    mutates_staging_records_now: boolean;
    controlled_cleanup_apply_dry_run_review_recorded: boolean;
    controlled_cleanup_apply_dry_run_review_accepted: boolean;
    cleanup_execution_approved_now: boolean;
    cleanup_application_allowed_now: boolean;
    cleanup_executed_now: boolean;
    can_execute_cleanup_now: boolean;
    future_controlled_cleanup_apply_execution_approval_required: boolean;
    can_promote_to_learning_samples_now: boolean;
    training_started_now: boolean;
    can_start_training_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
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

type TradeGatewayCapabilities = {
  schema_version: string;
  status: string;
  stage: string;
  gateway_enabled: boolean;
  execution_enabled: boolean;
  real_money_execution_enabled: boolean;
  broker_adapter_enabled: boolean;
  screen_click_trading_enabled: boolean;
  credential_storage_enabled: boolean;
  live_trading_enabled: boolean;
  review_only: boolean;
  simulation_only: boolean;
  allowed_modes: string[];
  forbidden_modes: string[];
  required_future_components: {
    name: string;
    status: string;
    required_before: string;
    review_only: boolean;
  }[];
  current_output: string;
  safety_summary: Record<string, boolean>;
  blocked_gate_count: number;
};

type TradeGatewayReviewGates = {
  schema_version: string;
  status: string;
  stage: string;
  gates: {
    name: string;
    status: string;
    value: string | boolean;
    limit: string | boolean;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }[];
  review_required_count: number;
  blocked_gate_count: number;
  allowed_output: string;
  decision: {
    gateway_can_execute: boolean;
    manual_confirmation_contract_ready: boolean;
    risk_contract_ready: boolean;
    audit_contract_ready: boolean;
    rollback_runbook_ready: boolean;
    pre_live_package_ready: boolean;
    operator_acceptance_checklist_ready: boolean;
    disabled_release_gate_ready: boolean;
    final_readiness_report_ready: boolean;
    broker_adapter_threat_model_ready: boolean;
    broker_adapter_interface_draft_ready: boolean;
    broker_adapter_contract_verification_ready: boolean;
    order_lifecycle_failure_fixtures_ready: boolean;
    order_failure_runbook_mapping_ready: boolean;
    disabled_audit_ledger_storage_plan_ready: boolean;
    audit_ledger_migration_spec_dry_run_ready: boolean;
    audit_ledger_migration_spec_approval_metadata_ready: boolean;
    audit_ledger_migration_release_readiness_ready: boolean;
    audit_ledger_migration_approval_freshness_ready: boolean;
    audit_ledger_migration_manual_release_package_ready: boolean;
    audit_ledger_migration_release_package_integrity_review_ready: boolean;
    audit_ledger_migration_manual_release_rehearsal_ready: boolean;
    audit_ledger_migration_manual_release_evidence_verifier_ready: boolean;
    audit_ledger_migration_manual_release_evidence_comparison_ready: boolean;
    audit_ledger_migration_manual_release_health_digest_ready: boolean;
    audit_ledger_migration_manual_release_health_digest_history_retention_proposal_ready: boolean;
    audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist_ready: boolean;
    audit_ledger_migration_manual_release_health_digest_history_migration_spec_verifier_ready: boolean;
    audit_ledger_migration_manual_release_health_digest_history_migration_spec_approval_metadata_ready: boolean;
    audit_ledger_migration_manual_release_health_digest_history_release_readiness_ready: boolean;
    audit_ledger_migration_manual_release_health_digest_history_approval_freshness_ready: boolean;
    audit_ledger_migration_manual_release_health_digest_history_release_package_ready: boolean;
    audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_review_ready: boolean;
    audit_ledger_migration_manual_release_health_digest_history_release_rehearsal_ready: boolean;
    audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier_ready: boolean;
    audit_ledger_migration_manual_release_health_digest_history_release_evidence_comparison_ready: boolean;
    audit_ledger_migration_manual_release_health_digest_history_release_health_digest_ready: boolean;
    ready_for_live_enablement: boolean;
    live_trading_enabled: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayManualContract = {
  schema_version: string;
  status: string;
  stage: string;
  contract_name: string;
  contract_state: string;
  required_operator_inputs: {
    name: string;
    type: string;
    sensitive: boolean;
    storage_policy: string;
    required_phrase?: string;
    reason: string;
  }[];
  required_preconditions: string[];
  expiry_policy: {
    confirmation_ttl_seconds: number;
    expires_on_price_or_risk_change: boolean;
    requires_reconfirmation_after_expiry: boolean;
  };
  dual_control_policy: {
    second_reviewer_required_for_high_risk: boolean;
    high_risk_triggers: string[];
  };
  decision: {
    contract_ready_for_review: boolean;
    contract_allows_execution_now: boolean;
    requires_future_risk_contract: boolean;
    requires_future_audit_storage: boolean;
    requires_future_rollback_runbook: boolean;
    next_required_action: string;
  };
  forbidden_inputs: string[];
  safety_summary: Record<string, boolean>;
  allowed_output: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditSchema = {
  schema_version: string;
  status: string;
  stage: string;
  schema_name: string;
  schema_state: string;
  storage_state: string;
  target_future_table: string;
  create_table_now: boolean;
  writes_database_now: boolean;
  fields: {
    name: string;
    type: string;
    description: string;
    sensitive: boolean;
    required: boolean;
    review_only: boolean;
  }[];
  immutability_rules: string[];
  excluded_sensitive_fields: string[];
  minimum_evidence_before_future_execution_review: string[];
  decision: {
    schema_ready_for_review: boolean;
    schema_allows_execution_now: boolean;
    schema_persistence_enabled_now: boolean;
    migration_allowed_now: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
  allowed_output: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayRiskGate = {
  name: string;
  source_limit: string;
  limit: string | number;
  failure_status: string;
  reason: string;
  manual_override_allowed: boolean;
  ai_override_allowed: boolean;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayRiskContract = {
  schema_version: string;
  status: string;
  stage: string;
  contract_name: string;
  contract_state: string;
  portfolio_gates: TradeGatewayRiskGate[];
  symbol_gates: TradeGatewayRiskGate[];
  ordering: string[];
  hard_block_statuses: string[];
  required_evidence_hashes: string[];
  decision: {
    contract_ready_for_review: boolean;
    contract_allows_execution_now: boolean;
    risk_gate_can_override_manual_confirmation: boolean;
    requires_fresh_risk_snapshot: boolean;
    requires_future_rollback_runbook: boolean;
    next_required_action: string;
  };
  integration_notes: {
    source_portfolio_limits: string;
    risk_posture_if_blocked: string;
    manual_confirmation_override_allowed: boolean;
    ai_override_allowed: boolean;
  };
  safety_summary: Record<string, boolean>;
  allowed_output: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayRollbackRunbook = {
  schema_version: string;
  status: string;
  stage: string;
  runbook_name: string;
  runbook_state: string;
  trigger_events: string[];
  rollback_steps: {
    step: string;
    owner: string;
    evidence_required: string;
    executes_commands: boolean;
  }[];
  recovery_requirements: string[];
  decision: {
    runbook_ready_for_review: boolean;
    runbook_allows_execution_now: boolean;
    requires_manual_postmortem: boolean;
    ready_for_live_enablement: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
  allowed_output: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayPreLivePackage = {
  schema_version: string;
  status: string;
  stage: string;
  package_id: string;
  package_state: string;
  manifest: {
    name: string;
    schema_version: string;
    status: string;
    stage: string;
    included: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }[];
  required_manual_artifacts: string[];
  included_safety_evidence: Record<string, string | number | boolean>;
  decision: {
    package_ready_for_manual_review: boolean;
    ready_for_live_enablement: boolean;
    gateway_can_execute: boolean;
    requires_operator_release_review: boolean;
    requires_separate_live_integration_plan: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
  allowed_output: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAcceptanceChecklist = {
  schema_version: string;
  status: string;
  stage: string;
  checklist_state: string;
  checklist_items: {
    id: string;
    requirement: string;
    required_evidence: string;
    required: boolean;
    blocking_if_missing: boolean;
    operator_review_required: boolean;
    api_can_mark_complete: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }[];
  operator_attestation_phrase: string;
  acceptance_policy: {
    all_items_required: boolean;
    operator_review_required: boolean;
    api_can_record_acceptance: boolean;
    api_can_enable_gateway: boolean;
    missing_item_effect: string;
  };
  decision: {
    checklist_ready_for_review: boolean;
    operator_acceptance_recorded_now: boolean;
    acceptance_allows_enablement_now: boolean;
    ready_for_live_enablement: boolean;
    gateway_can_execute: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
  allowed_output: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayReleaseGate = {
  schema_version: string;
  status: string;
  stage: string;
  gate_name: string;
  default_state: string;
  release_gate_state: string;
  preconditions_for_future_external_review: string[];
  release_blockers: string[];
  gate_evidence: Record<string, string | number | boolean>;
  decision: {
    release_gate_ready_for_review: boolean;
    release_gate_allows_enablement_now: boolean;
    ready_for_live_enablement: boolean;
    gateway_can_execute: boolean;
    api_can_enable_gateway: boolean;
    api_can_record_release_approval: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
  allowed_output: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayFinalReport = {
  schema_version: string;
  status: string;
  stage: string;
  report_id: string;
  report_state: string;
  manifest: {
    name: string;
    schema_version: string;
    status: string;
    stage: string;
    included: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }[];
  summary: {
    completed_review_modules: number;
    blocked_gate_count: number;
    review_required_count: number;
    pre_live_package_id: string;
    default_release_state: string;
    next_track: string;
  };
  safety_matrix: Record<string, boolean>;
  remaining_blockers: string[];
  decision: {
    v5_review_only_baseline_complete: boolean;
    ready_for_v5_5_threat_modeling: boolean;
    ready_for_live_enablement: boolean;
    gateway_can_execute: boolean;
    api_can_enable_gateway: boolean;
    api_can_record_release_approval: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
  allowed_output: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayBrokerThreatModel = {
  schema_version: string;
  status: string;
  stage: string;
  model_state: string;
  scope: string;
  protected_assets: string[];
  trust_boundaries: string[];
  threat_categories: {
    name: string;
    risk: string;
    mitigation: string;
    status: string;
  }[];
  required_future_reviews: string[];
  decision: {
    threat_model_ready_for_review: boolean;
    broker_adapter_allowed_now: boolean;
    credential_handling_allowed_now: boolean;
    account_read_allowed_now: boolean;
    order_execution_allowed_now: boolean;
    ready_for_live_enablement: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
  allowed_output: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayBrokerInterfaceDraft = {
  schema_version: string;
  status: string;
  stage: string;
  interface_state: string;
  adapter_contract_name: string;
  draft_methods: {
    name: string;
    purpose: string;
    mode: string;
    implemented_now: boolean;
    calls_broker_now: boolean;
    places_order_now: boolean;
    reads_account_now: boolean;
    stores_credentials_now: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }[];
  forbidden_methods: string[];
  required_inputs_policy: {
    allows_credentials: boolean;
    allows_account_number: boolean;
    allows_sms_code: boolean;
    allows_trading_pin: boolean;
    allows_plaintext_secret: boolean;
  };
  future_test_requirements: string[];
  decision: {
    interface_draft_ready_for_review: boolean;
    interface_implemented_now: boolean;
    adapter_can_connect_now: boolean;
    adapter_can_execute_now: boolean;
    adapter_can_read_account_now: boolean;
    ready_for_live_enablement: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
  allowed_output: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayBrokerContractVerification = {
  schema_version: string;
  status: string;
  stage: string;
  verification_state: string;
  source_contract: string;
  fixture_name: string;
  checks: {
    name: string;
    status: string;
    reason: string;
    fixture_evidence: Record<string, unknown>;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }[];
  summary: {
    total_checks: number;
    passed_checks: number;
    blocked_checks: number;
    fixture_only: boolean;
    network_calls: boolean;
    adapter_instantiated: boolean;
  };
  decision: {
    contract_verification_ready_for_review: boolean;
    fixture_contract_tests_passed: boolean;
    adapter_implemented_now: boolean;
    adapter_can_connect_now: boolean;
    adapter_can_execute_now: boolean;
    adapter_can_read_account_now: boolean;
    credentials_allowed_now: boolean;
    ready_for_live_enablement: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
  allowed_output: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayOrderFailureFixtures = {
  schema_version: string;
  status: string;
  stage: string;
  fixture_state: string;
  fixture_suite: string;
  fixtures: {
    name: string;
    expected_status: string;
    failure_mode: string;
    trigger: string;
    expected_handling: string;
    required_contracts: string[];
    fixture_payload: Record<string, unknown>;
    can_submit_order: boolean;
    can_cancel_order: boolean;
    can_modify_order: boolean;
    connects_broker: boolean;
    requires_credentials: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }[];
  summary: {
    fixture_count: number;
    blocked_count: number;
    partial_count: number;
    rejected_count: number;
    places_order: boolean;
    connects_broker: boolean;
    reads_account: boolean;
    requires_credentials: boolean;
  };
  decision: {
    failure_fixtures_ready_for_review: boolean;
    can_replay_as_real_order: boolean;
    can_submit_order_now: boolean;
    can_cancel_order_now: boolean;
    can_modify_order_now: boolean;
    requires_broker_connection: boolean;
    requires_credentials: boolean;
    ready_for_live_enablement: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
  allowed_output: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayOrderRunbookMapping = {
  schema_version: string;
  status: string;
  stage: string;
  mapping_state: string;
  source_fixture_suite: string;
  mappings: {
    fixture_name: string;
    failure_mode: string;
    expected_status: string;
    manual_decision: string;
    operator_action: string;
    required_audit_evidence: string[];
    required_hashes: string[];
    runbook_reference: string;
    can_execute_runbook: boolean;
    can_submit_order: boolean;
    writes_database_now: boolean;
    connects_broker: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }[];
  summary: {
    mapping_count: number;
    manual_review_required_count: number;
    audit_evidence_field_count: number;
    writes_database_now: boolean;
    executes_runbook_now: boolean;
    connects_broker: boolean;
    places_order: boolean;
  };
  decision: {
    runbook_mapping_ready_for_review: boolean;
    can_execute_runbook_now: boolean;
    can_record_audit_now: boolean;
    can_submit_order_now: boolean;
    requires_broker_connection: boolean;
    requires_credentials: boolean;
    ready_for_live_enablement: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
  allowed_output: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditStoragePlan = {
  schema_version: string;
  status: string;
  stage: string;
  storage_state: string;
  target_future_table: string;
  source_schema: string;
  source_runbook_mapping: string;
  planned_columns: {
    name: string;
    type: string;
    nullable: boolean;
    purpose: string;
    source: string;
    create_now: boolean;
    stores_sensitive_plaintext: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }[];
  proposed_indexes: {
    name: string;
    columns: string[];
    unique: boolean;
    create_now: boolean;
  }[];
  hash_chain_policy: {
    algorithm: string;
    canonicalization: string;
    previous_event_hash_required_after_first_row: boolean;
    manual_correction_policy: string;
    verify_before_any_future_live_review: boolean;
  };
  retention_policy: {
    default_retention_days: number;
    manual_archive_required_before_prune: boolean;
    prune_requires_operator_approval: boolean;
    prune_api_enabled_now: boolean;
  };
  redaction_policy: {
    store_only_hashes_for_sensitive_identity: boolean;
    store_short_review_note_excerpt_only: boolean;
    excluded_sensitive_fields: string[];
    raw_payload_storage_allowed: boolean;
  };
  migration_preconditions: string[];
  rollback_requirements: string[];
  blocked_actions: string[];
  summary: {
    planned_column_count: number;
    proposed_index_count: number;
    excluded_sensitive_field_count: number;
    create_table_now: boolean;
    writes_database_now: boolean;
    runs_migration_now: boolean;
    writes_migration_file_now: boolean;
    records_audit_rows_now: boolean;
  };
  decision: {
    storage_plan_ready_for_review: boolean;
    can_create_table_now: boolean;
    can_write_audit_row_now: boolean;
    can_run_migration_now: boolean;
    can_write_migration_file_now: boolean;
    requires_operator_approval_before_migration: boolean;
    requires_dry_run_verifier_before_migration: boolean;
    ready_for_live_enablement: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
  allowed_output: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditMigrationSpecVerification = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  verification_state: string;
  target_table: string;
  spec_hash: string;
  spec_excerpt: string;
  checks: {
    name: string;
    status: string;
    reason: string;
    details: Record<string, any>;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }[];
  missing_columns: string[];
  missing_indexes: string[];
  dangerous_matches: string[];
  sensitive_matches: string[];
  failed_count: number;
  migration_allowed_now: boolean;
  forbidden_actions: string[];
  summary: {
    required_column_count: number;
    covered_column_count: number;
    proposed_index_count: number;
    covered_index_count: number;
    dangerous_match_count: number;
    sensitive_match_count: number;
    executes_sql: boolean;
    creates_table_now: boolean;
    writes_database_now: boolean;
    runs_migration_now: boolean;
    writes_migration_file_now: boolean;
    records_audit_rows_now: boolean;
  };
  decision: {
    spec_verification_ready_for_review: boolean;
    spec_verification_passed: boolean;
    can_execute_sql_now: boolean;
    can_create_table_now: boolean;
    can_run_migration_now: boolean;
    can_write_migration_file_now: boolean;
    can_write_audit_row_now: boolean;
    requires_operator_approval_before_migration: boolean;
    ready_for_live_enablement: boolean;
    next_required_action: string;
  };
  safety_summary: Record<string, boolean>;
  allowed_output: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditMigrationSpecApproval = {
  schema_version: string;
  status: string;
  stage: string;
  event_id: number | null;
  event_type?: string;
  created_at?: string;
  approved_at: string;
  approved_by: string;
  approval_note?: string | null;
  approval_effect: string;
  spec_hash: string;
  verification_status: string;
  verification_failed_count: number;
  target_table: string;
  migration_allowed_now: boolean;
  future_migration_still_requires: string[];
  safety_summary: Record<string, boolean> & {
    writes_existing_event_now: boolean;
    writes_audit_ledger_row_now: boolean;
    creates_table_now: boolean;
    runs_migration_now: boolean;
    executes_sql: boolean;
    writes_migration_file_now: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
  verification?: {
    schema_version: string;
    status: string;
    spec_hash: string;
    failed_count: number;
    target_table: string;
    allowed_output: string;
    migration_allowed_now: boolean;
    live_trading_enabled: boolean;
  };
};

type TradeGatewayAuditMigrationReleaseReadiness = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  decision: {
    go_no_go: string;
    migration_allowed_now: boolean;
    release_approved_now: boolean;
    requires_human_release_approval: boolean;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  evidence: {
    storage_plan_status: string;
    verification_status: string;
    verification_failed_count: number;
    approval_count: number;
    latest_approval_status: string | null;
    latest_approval_event_id: number | null;
    target_table: string;
    spec_hash: string;
    approved_spec_hash: string | null;
    allowed_output: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  gates: Array<{
    name: string;
    status: string;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  blocked_gates: Array<{
    name: string;
    status: string;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  review_required_gates: Array<{
    name: string;
    status: string;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  required_before_actual_migration: string[];
  safety_summary: Record<string, boolean> & {
    executes_sql: boolean;
    runs_migration_now: boolean;
    creates_table_now: boolean;
    writes_database_now: boolean;
    writes_audit_ledger_row_now: boolean;
    writes_migration_file_now: boolean;
    approves_release_now: boolean;
    enables_gateway_now: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditMigrationApprovalReview = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  review_policy: {
    max_age_days: number;
    rotation_required_when: string[];
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  latest_approval: {
    event_id: number | null;
    status: string | null;
    approved_at: string | null;
    created_at: string | null;
    approved_by: string | null;
    spec_hash: string | null;
    verification_status: string | null;
    approval_age_hours: number | null;
    approval_age_days: number | null;
    expires_at: string | null;
    is_expired: boolean;
    matches_current_spec: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  current_spec: {
    spec_hash: string | null;
    verification_status: string;
    failed_count: number;
    migration_allowed_now: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  release_readiness: {
    status: string;
    go_no_go: string;
    approval_count: number;
    latest_approval_event_id: number | null;
    migration_allowed_now: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  gates: TradeGatewayAuditMigrationReleaseReadiness["gates"];
  blocked_gates: TradeGatewayAuditMigrationReleaseReadiness["blocked_gates"];
  review_required_gates: TradeGatewayAuditMigrationReleaseReadiness["review_required_gates"];
  decision: {
    next_required_action: string;
    migration_allowed_now: boolean;
    approval_can_be_reused_for_manual_release_review: boolean;
    requires_human_release_approval: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  safety_summary: TradeGatewayAuditMigrationReleaseReadiness["safety_summary"];
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditMigrationReleasePackage = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  package_id: string;
  package_id_inputs: Record<string, string | number | null>;
  manifest: {
    name: string;
    purpose: string;
    items: Array<{
      name: string;
      status: string;
      allowed_output: string;
      generated_at: string | null;
      safety_passed: boolean;
      included: boolean;
      review_only: boolean;
      simulation_only: boolean;
      live_trading_enabled: boolean;
    }>;
    required_manual_artifacts_before_execution: string[];
    delivery: string;
    writes_file: boolean;
    download_created: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  evidence: {
    storage_plan_status: string;
    verification_status: string;
    verification_failed_count: number;
    latest_approval_event_id: number | null;
    latest_approval_status: string | null;
    release_readiness_status: string;
    approval_review_status: string;
    spec_hash: string | null;
    approved_spec_hash: string | null;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  gates: TradeGatewayAuditMigrationReleaseReadiness["gates"];
  blocked_gates: TradeGatewayAuditMigrationReleaseReadiness["blocked_gates"];
  review_required_gates: TradeGatewayAuditMigrationReleaseReadiness["review_required_gates"];
  decision: {
    go_no_go: string;
    migration_allowed_now: boolean;
    execution_allowed_now: boolean;
    release_approved_now: boolean;
    requires_human_release_approval: boolean;
    next_required_action: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  safety_summary: TradeGatewayAuditMigrationReleaseReadiness["safety_summary"] & {
    writes_file: boolean;
    download_created: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditMigrationReleasePackageIntegrityReview = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  source_package_id: string;
  source_package_status: string;
  recomputed_package_id: string;
  repeat_checks: number;
  repeated_package_ids: string[];
  checks: Array<{
    name: string;
    status: string;
    reason: string;
    details: Record<string, any>;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  failed_checks: Array<{
    name: string;
    status: string;
    reason: string;
    details: Record<string, any>;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  failed_check_count: number;
  manifest_summary: {
    item_count: number;
    required_item_names: string[];
    missing_items: string[];
    duplicate_items: string[];
    missing_manual_artifacts: string[];
    delivery: string;
    writes_file: boolean;
    download_created: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  decision: {
    package_id_stable: boolean;
    manifest_integrity_passed: boolean;
    release_package_ready: boolean;
    go_no_go: string;
    migration_allowed_now: boolean;
    execution_allowed_now: boolean;
    release_approved_now: boolean;
    next_required_action: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  safety_summary: TradeGatewayAuditMigrationReleaseReadiness["safety_summary"] & {
    writes_file: boolean;
    download_created: boolean;
    mutates_source_package: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditMigrationManualReleaseRehearsal = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  rehearsal_id: string;
  source_package_id: string;
  source_package_status: string;
  integrity_status: string;
  steps: Array<{
    name: string;
    status: string;
    instruction: string;
    pending_reason: string | null;
    evidence: Record<string, any>;
    operator_action_required: boolean;
    api_can_mark_complete: boolean;
    api_can_record_approval: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  pending_steps: Array<{
    name: string;
    status: string;
    instruction: string;
    pending_reason: string | null;
    evidence: Record<string, any>;
    operator_action_required: boolean;
    api_can_mark_complete: boolean;
    api_can_record_approval: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  failed_steps: Array<{
    name: string;
    status: string;
    instruction: string;
    pending_reason: string | null;
    evidence: Record<string, any>;
    operator_action_required: boolean;
    api_can_mark_complete: boolean;
    api_can_record_approval: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  operator_rehearsal_policy: {
    api_can_record_operator_review: boolean;
    api_can_mark_rehearsal_complete: boolean;
    api_can_approve_release: boolean;
    api_can_execute_migration: boolean;
    offline_human_review_required: boolean;
    dual_control_required_before_future_execution: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  required_offline_artifacts: string[];
  decision: {
    rehearsal_ready_for_operator: boolean;
    manual_review_recorded_now: boolean;
    release_approved_now: boolean;
    migration_allowed_now: boolean;
    execution_allowed_now: boolean;
    gateway_can_execute: boolean;
    go_no_go: string;
    next_required_action: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  safety_summary: TradeGatewayAuditMigrationReleaseReadiness["safety_summary"] & {
    records_manual_review_now: boolean;
    marks_rehearsal_complete_now: boolean;
    writes_file: boolean;
    download_created: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseRehearsal =
  TradeGatewayAuditMigrationManualReleaseRehearsal;

type TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseEvidenceVerification =
  TradeGatewayAuditMigrationManualReleaseEvidenceVerification & {
    safety_summary: TradeGatewayAuditMigrationManualReleaseEvidenceVerification["safety_summary"] & {
      persists_manual_release_health_digest_history_evidence: boolean;
      writes_history_row_now: boolean;
    };
  };

type TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseEvidenceComparison =
  TradeGatewayAuditMigrationManualReleaseEvidenceComparison & {
    safety_summary: TradeGatewayAuditMigrationManualReleaseEvidenceComparison["safety_summary"] & {
      persists_manual_release_health_digest_history_evidence: boolean;
      persists_manual_release_health_digest_history_evidence_comparison: boolean;
      writes_history_row_now: boolean;
    };
  };

type TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseHealthDigest =
  TradeGatewayAuditMigrationManualReleaseHealthDigest & {
    safety_summary: TradeGatewayAuditMigrationManualReleaseHealthDigest["safety_summary"] & {
      persists_manual_release_health_digest_history: boolean;
      persists_manual_release_health_digest_history_evidence: boolean;
      persists_manual_release_health_digest_history_evidence_comparison: boolean;
      persists_manual_release_health_digest_history_release_health_digest: boolean;
      writes_history_row_now: boolean;
    };
  };

type TradeGatewayAuditMigrationManualReleaseEvidenceVerification = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  verification_id: string;
  source_package_id: string;
  rehearsal_id: string;
  rehearsal_status: string;
  required_artifacts: string[];
  provided_artifact_names: string[];
  missing_artifacts: string[];
  duplicate_artifacts: string[];
  checks: Array<{
    name: string;
    status: string;
    reason: string;
    details: Record<string, any>;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  failed_checks: Array<{
    name: string;
    status: string;
    reason: string;
    details: Record<string, any>;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  failed_check_count: number;
  decision: {
    evidence_complete: boolean;
    manual_review_recorded_now: boolean;
    release_approved_now: boolean;
    migration_allowed_now: boolean;
    execution_allowed_now: boolean;
    gateway_can_execute: boolean;
    go_no_go: string;
    next_required_action: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  safety_summary: TradeGatewayAuditMigrationReleaseReadiness["safety_summary"] & {
    persists_manual_release_evidence: boolean;
    records_manual_review_now: boolean;
    writes_file: boolean;
    download_created: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditMigrationManualReleaseEvidenceComparison = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  comparison_id: string;
  baseline: {
    status: string;
    verification_id: string;
    source_package_id: string;
    rehearsal_id: string;
    provided_artifact_names: string[];
    failed_check_count: number;
    evidence_complete: boolean;
  };
  candidate: {
    status: string;
    verification_id: string;
    source_package_id: string;
    rehearsal_id: string;
    provided_artifact_names: string[];
    failed_check_count: number;
    evidence_complete: boolean;
  };
  artifact_names_added: string[];
  artifact_names_removed: string[];
  artifact_hash_changes: Array<Record<string, any>>;
  artifact_review_changes: Array<Record<string, any>>;
  check_status_differences: Array<Record<string, any>>;
  checks: TradeGatewayAuditMigrationManualReleaseEvidenceVerification["checks"];
  failed_checks: TradeGatewayAuditMigrationManualReleaseEvidenceVerification["failed_checks"];
  failed_check_count: number;
  decision: {
    evidence_pair_stable: boolean;
    manual_review_recorded_now: boolean;
    release_approved_now: boolean;
    migration_allowed_now: boolean;
    execution_allowed_now: boolean;
    gateway_can_execute: boolean;
    go_no_go: string;
    next_required_action: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  safety_summary: TradeGatewayAuditMigrationReleaseReadiness["safety_summary"] & {
    persists_manual_release_evidence: boolean;
    persists_manual_release_evidence_comparison: boolean;
    mutates_evidence: boolean;
    records_manual_review_now: boolean;
    writes_file: boolean;
    download_created: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditMigrationManualReleaseHealthDigest = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  digest_id: string;
  module_statuses: Array<{
    name: string;
    status: string;
    evidence_id: string;
    go_no_go: string;
    included: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  attention_items: Array<{
    name: string;
    status: string;
    evidence_id: string;
    go_no_go: string;
    included: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  health_flags: Record<string, boolean>;
  summary: {
    module_count: number;
    attention_count: number;
    failed_check_count: number;
    missing_artifact_count: number;
    changed_artifact_hash_count: number;
    pending_rehearsal_step_count: number;
  };
  checks: TradeGatewayAuditMigrationManualReleaseEvidenceVerification["checks"];
  failed_checks: TradeGatewayAuditMigrationManualReleaseEvidenceVerification["failed_checks"];
  decision: {
    digest_healthy: boolean;
    manual_review_recorded_now: boolean;
    release_approved_now: boolean;
    migration_allowed_now: boolean;
    execution_allowed_now: boolean;
    gateway_can_execute: boolean;
    go_no_go: string;
    next_required_action: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  safety_summary: TradeGatewayAuditMigrationReleaseReadiness["safety_summary"] & {
    persists_manual_release_evidence: boolean;
    persists_manual_release_evidence_comparison: boolean;
    persists_manual_release_health_digest: boolean;
    mutates_evidence: boolean;
    records_manual_review_now: boolean;
    writes_file: boolean;
    download_created: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryProposal = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  proposal_id: string;
  proposal: {
    name: string;
    purpose: string;
    default_state: string;
    recommended_retention_days: number;
    max_records_per_day: number;
    dedupe_key: string;
    storage_mode: string;
    required_fields: string[];
    excluded_fields: string[];
    operator_review_required: boolean;
    apply_automatically: boolean;
    requires_future_migration: boolean;
    writes_database_now: boolean;
    writes_file: boolean;
    download_created: boolean;
    executes_commands: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  current_digest_summary: {
    digest_id: string;
    digest_status: string;
    digest_stage: string;
    module_statuses: Record<string, string>;
    attention_item_names: string[];
    failed_check_names: string[];
    summary: Record<string, any>;
    health_flags: Record<string, boolean>;
    decision_go_no_go: string;
    next_required_action: string;
    allowed_output: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  review_gates: Array<{
    name: string;
    status: string;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  summary: {
    required_field_count: number;
    excluded_field_count: number;
    blocked_gate_count: number;
    attention_item_count: number;
    failed_check_count: number;
    writes_database_now: boolean;
    persists_history_now: boolean;
  };
  decision: {
    proposal_ready_for_manual_review: boolean;
    history_persistence_enabled_now: boolean;
    can_create_table_now: boolean;
    can_write_history_row_now: boolean;
    can_run_migration_now: boolean;
    can_write_migration_file_now: boolean;
    release_approved_now: boolean;
    migration_allowed_now: boolean;
    execution_allowed_now: boolean;
    gateway_can_execute: boolean;
    go_no_go: string;
    next_required_action: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  safety_summary: TradeGatewayAuditMigrationManualReleaseHealthDigest["safety_summary"] & {
    persists_manual_release_health_digest_history: boolean;
    creates_table_now: boolean;
    writes_history_row_now: boolean;
    executes_commands: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryMigrationChecklist = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  checklist_id: string;
  source_proposal: {
    proposal_id: string;
    status: string;
    schema_version: string;
    allowed_output: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  migration_plan: {
    target_table: string;
    source_schema: string;
    source_proposal_id: string;
    source_digest_stage: string;
    migration_type: string;
    table_exists_now: boolean;
    create_table_now: boolean;
    backfill_now: boolean;
    writes_database_now: boolean;
    writes_migration_file_now: boolean;
    apply_automatically: boolean;
    operator_review_required: boolean;
    rollback_required: boolean;
    test_required: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  field_mapping: Array<{
    source_field: string;
    target_field: string;
    storage: string;
    required: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  excluded_fields: string[];
  checks: Array<{
    name: string;
    status: string;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  summary: {
    check_count: number;
    passed_check_count: number;
    review_required_count: number;
    blocked_check_count: number;
    field_mapping_count: number;
    excluded_field_count: number;
    migration_allowed_now: boolean;
    manual_review_required: boolean;
  };
  decision: {
    migration_readiness_review_ready: boolean;
    history_persistence_enabled_now: boolean;
    can_create_table_now: boolean;
    can_write_history_row_now: boolean;
    can_run_migration_now: boolean;
    can_write_migration_file_now: boolean;
    release_approved_now: boolean;
    migration_allowed_now: boolean;
    execution_allowed_now: boolean;
    gateway_can_execute: boolean;
    go_no_go: string;
    next_required_action: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  safety_summary: TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryProposal["safety_summary"] & {
    history_persistence_enabled_now: boolean;
    runs_migration_now: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryMigrationSpecVerification = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  verification_state: string;
  target_table: string;
  spec_hash: string;
  spec_excerpt: string;
  checks: Array<{
    name: string;
    status: string;
    reason: string;
    details: Record<string, any>;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  failed_checks: Array<{
    name: string;
    status: string;
    reason: string;
    details: Record<string, any>;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  missing_fields: string[];
  dangerous_matches: string[];
  sensitive_matches: string[];
  safety_blocks: Array<{
    name: string;
    matches: string[];
    blocked: boolean;
  }>;
  source_checklist_status: string;
  migration_allowed_now: boolean;
  forbidden_actions: string[];
  summary: {
    required_field_count: number;
    covered_field_count: number;
    dangerous_match_count: number;
    sensitive_match_count: number;
    failed_count: number;
    executes_sql: boolean;
    creates_table_now: boolean;
    writes_database_now: boolean;
    runs_migration_now: boolean;
    writes_migration_file_now: boolean;
    writes_history_row_now: boolean;
  };
  decision: {
    spec_verification_ready_for_review: boolean;
    spec_verification_passed: boolean;
    can_execute_sql_now: boolean;
    can_create_table_now: boolean;
    can_run_migration_now: boolean;
    can_write_migration_file_now: boolean;
    can_write_history_row_now: boolean;
    history_persistence_enabled_now: boolean;
    release_approved_now: boolean;
    migration_allowed_now: boolean;
    execution_allowed_now: boolean;
    gateway_can_execute: boolean;
    next_required_action: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  safety_summary: TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryMigrationChecklist["safety_summary"] & {
    dry_run_verifier_only: boolean;
    writes_history_row_now: boolean;
  };
  allowed_output: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryMigrationSpecApproval = {
  schema_version: string;
  status: string;
  stage: string;
  event_id: number | null;
  event_type?: string;
  created_at?: string;
  approved_at: string;
  approved_by: string;
  approval_note?: string | null;
  approval_effect: string;
  spec_hash: string;
  verification_status: string;
  verification_failed_count: number;
  target_table: string;
  source_checklist_status: string;
  migration_allowed_now: boolean;
  future_migration_still_requires: string[];
  safety_summary: Record<string, boolean> & {
    writes_existing_event_now: boolean;
    persists_manual_release_health_digest_history: boolean;
    writes_history_row_now: boolean;
    creates_table_now: boolean;
    runs_migration_now: boolean;
    executes_sql: boolean;
    writes_migration_file_now: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
  verification?: {
    schema_version: string;
    status: string;
    spec_hash: string;
    failed_count: number;
    target_table: string;
    source_checklist_status: string;
    allowed_output: string;
    migration_allowed_now: boolean;
    live_trading_enabled: boolean;
  };
};

type TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseReadiness = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  decision: {
    go_no_go: string;
    migration_allowed_now: boolean;
    execution_allowed_now: boolean;
    release_approved_now: boolean;
    requires_human_release_approval: boolean;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  evidence: {
    proposal_status: string;
    checklist_status: string;
    verification_status: string;
    verification_failed_count: number;
    approval_count: number;
    latest_approval_status: string | null;
    latest_approval_event_id: number | null;
    target_table: string;
    spec_hash: string;
    approved_spec_hash: string | null;
    allowed_output: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  gates: TradeGatewayAuditMigrationReleaseReadiness["gates"];
  blocked_gates: TradeGatewayAuditMigrationReleaseReadiness["blocked_gates"];
  review_required_gates: TradeGatewayAuditMigrationReleaseReadiness["review_required_gates"];
  required_before_actual_migration: string[];
  safety_summary: Record<string, boolean> & {
    persists_manual_release_health_digest_history: boolean;
    writes_history_row_now: boolean;
    creates_table_now: boolean;
    runs_migration_now: boolean;
    executes_sql: boolean;
    writes_database_now: boolean;
    writes_migration_file_now: boolean;
    writes_file: boolean;
    download_created: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryApprovalReview = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  review_policy: TradeGatewayAuditMigrationApprovalReview["review_policy"];
  latest_approval: TradeGatewayAuditMigrationApprovalReview["latest_approval"];
  current_spec: TradeGatewayAuditMigrationApprovalReview["current_spec"];
  release_readiness: TradeGatewayAuditMigrationApprovalReview["release_readiness"] & {
    execution_allowed_now: boolean;
    release_approved_now: boolean;
  };
  gates: TradeGatewayAuditMigrationReleaseReadiness["gates"];
  blocked_gates: TradeGatewayAuditMigrationReleaseReadiness["blocked_gates"];
  review_required_gates: TradeGatewayAuditMigrationReleaseReadiness["review_required_gates"];
  decision: {
    next_required_action: string;
    migration_allowed_now: boolean;
    execution_allowed_now: boolean;
    release_approved_now: boolean;
    approval_can_be_reused_for_manual_release_review: boolean;
    requires_human_release_approval: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  safety_summary: Record<string, boolean> & {
    persists_manual_release_health_digest_history: boolean;
    writes_history_row_now: boolean;
    creates_table_now: boolean;
    runs_migration_now: boolean;
    executes_sql: boolean;
    writes_database_now: boolean;
    writes_migration_file_now: boolean;
    writes_file: boolean;
    download_created: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleasePackage = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  package_id: string;
  package_id_inputs: Record<string, string | number | null>;
  manifest: TradeGatewayAuditMigrationReleasePackage["manifest"];
  evidence: {
    proposal_status: string;
    checklist_status: string;
    verification_status: string;
    verification_failed_count: number;
    latest_approval_event_id: number | null;
    latest_approval_status: string | null;
    release_readiness_status: string;
    approval_review_status: string;
    spec_hash: string | null;
    approved_spec_hash: string | null;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  gates: TradeGatewayAuditMigrationReleaseReadiness["gates"];
  blocked_gates: TradeGatewayAuditMigrationReleaseReadiness["blocked_gates"];
  review_required_gates: TradeGatewayAuditMigrationReleaseReadiness["review_required_gates"];
  decision: TradeGatewayAuditMigrationReleasePackage["decision"];
  safety_summary: Record<string, boolean> & {
    persists_manual_release_health_digest_history: boolean;
    writes_history_row_now: boolean;
    creates_table_now: boolean;
    runs_migration_now: boolean;
    executes_sql: boolean;
    writes_database_now: boolean;
    writes_migration_file_now: boolean;
    writes_file: boolean;
    download_created: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryPackageIntegrityReview = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  source_package_id: string;
  source_package_status: string;
  recomputed_package_id: string;
  repeat_checks: number;
  repeated_package_ids: string[];
  checks: TradeGatewayAuditMigrationReleasePackageIntegrityReview["checks"];
  failed_checks: TradeGatewayAuditMigrationReleasePackageIntegrityReview["failed_checks"];
  failed_check_count: number;
  manifest_summary: TradeGatewayAuditMigrationReleasePackageIntegrityReview["manifest_summary"] & {
    required_item_names: string[];
    missing_items: string[];
    duplicate_items: string[];
    missing_manual_artifacts: string[];
  };
  decision: TradeGatewayAuditMigrationReleasePackageIntegrityReview["decision"];
  safety_summary: Record<string, boolean> & {
    persists_manual_release_health_digest_history: boolean;
    writes_history_row_now: boolean;
    creates_table_now: boolean;
    runs_migration_now: boolean;
    executes_sql: boolean;
    writes_database_now: boolean;
    writes_migration_file_now: boolean;
    writes_file: boolean;
    download_created: boolean;
    mutates_source_package: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
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

type RealtimeSchedulerPlan = {
  status: string;
  active_provider: string;
  provider_status: string;
  recommended_mode: string;
  recommended_symbols: string[];
  command_examples: string[];
  cadence: {
    workday_trading_hours: Array<{
      time: string;
      mode: string;
      reason: string;
    }>;
    non_trading_day: Array<{
      time: string;
      mode: string;
      reason: string;
    }>;
    provider_unconfigured_behavior: string;
  };
  pause_controls: string[];
  degrade_controls: string[];
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type RealtimeAutomationProposalItem = {
  id: string;
  name: string;
  mode: string;
  status: string;
  default_status: string;
  cadence_text: string;
  command: string;
  summary: string;
  evidence_endpoints: string[];
  expected_output: string[];
  requires_provider_config: boolean;
  provider_unconfigured_behavior: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
  requires_user_review: boolean;
};

type RealtimeAutomationProposal = {
  status: string;
  active_provider: string;
  provider_status: string;
  provider_configured: boolean;
  proposal_count: number;
  proposals: RealtimeAutomationProposalItem[];
  acceptance_checks: string[];
  pause_controls: string[];
  forbidden_actions: string[];
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
  run_id?: number;
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

type RealtimeCycleRun = {
  id: number;
  status: string;
  symbols: string[];
  provider?: string | null;
  refresh_status?: string | null;
  monitoring_session_id?: number | null;
  refreshed_count: number;
  refresh_failed_count: number;
  created_alert_count: number;
  replay_event_count: number;
  fallback_required: boolean;
  summary: RealtimeCycleResult["summary"];
  steps: Record<string, any>;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
  created_at: string;
};

type ScreenMonitoringCapabilities = {
  status: string;
  stage: string;
  capture_provider: string;
  provider_status: string;
  provider_configured: boolean;
  ocr_provider: string;
  provider_capabilities: ScreenProviderCapabilities;
  allowed_modes: string[];
  forbidden_modes: string[];
  default_session_name: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenProviderCapabilities = {
  provider: string;
  status: string;
  configured: boolean;
  capture_supported: boolean;
  capture_preflight_supported: boolean;
  capture_stub_supported?: boolean;
  ocr_supported: boolean;
  fixture_replay_supported: boolean;
  last_error?: string | null;
  details?: Record<string, any>;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenProviderReadiness = {
  status: string;
  stage: string;
  active_provider: string;
  provider_status: string;
  provider_configured: boolean;
  checks: Array<{
    name: string;
    status: string;
    value: string;
    expected: string;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  environment: Record<string, any>;
  runbook: {
    safe_sequence: string[];
    safe_api_checks: string[];
    blocked_actions: string[];
  };
  next_safe_steps: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenObservation = {
  id: number;
  session_id?: number | null;
  source: string;
  app_status: string;
  window_title?: string | null;
  observed_at: string;
  confidence: number;
  detected_items: Array<Record<string, any>>;
  warnings: string[];
  raw_payload: Record<string, any>;
  artifact_ref?: string | null;
  dedupe_key: string;
  inserted?: boolean;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenMonitoringSession = {
  id?: number;
  name?: string;
  status: string;
  source?: string;
  window_title?: string | null;
  started_at?: string;
  completed_at?: string | null;
  summary: {
    observation_count: number;
    status_counts: Record<string, number>;
    warning_count: number;
    read_only: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  observations: ScreenObservation[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenFixtureReplayResult = {
  status: string;
  provider: string;
  fixture_name: string;
  observation: ScreenObservation;
  real_screen_capture: boolean;
  ocr_executed: boolean;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenPreflightResult = {
  status: string;
  provider: string;
  reason: string;
  target_window_title?: string | null;
  configured: boolean;
  capture_preflight_supported: boolean;
  capture_would_be_allowed: boolean;
  real_screen_capture: boolean;
  ocr_executed: boolean;
  artifact_ref?: string | null;
  redaction_required: boolean;
  operator_review_required: boolean;
  observation: ScreenObservation;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenCaptureStubResult = {
  status: string;
  provider: string;
  target_window_title?: string | null;
  artifact_status: string;
  artifact_ref?: string | null;
  preflight: Record<string, any>;
  real_screen_capture: boolean;
  pixel_data_stored: boolean;
  ocr_executed: boolean;
  redaction_applied: boolean;
  redaction_required: boolean;
  operator_review_required: boolean;
  observation: ScreenObservation;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenArtifactPolicy = {
  status: string;
  artifact_kind: string;
  retention_days: number;
  max_review_queue_items: number;
  artifact_schemes: string[];
  pixel_data_stored: boolean;
  real_screen_capture: boolean;
  ocr_executed: boolean;
  redaction: Record<string, any>;
  review_queue: {
    default_status: string;
    allowed_decisions: string[];
    decision_effect: string;
  };
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenArtifactReview = {
  id: number;
  artifact_ref?: string | null;
  artifact_status: string;
  review_status: string;
  retention_policy: ScreenArtifactPolicy;
  redaction: Record<string, any>;
  reviewed_by?: string | null;
  review_note?: string | null;
  reviewed_at?: string | null;
  observation: ScreenObservation;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenArtifactSyncResult = {
  status: string;
  scanned_observation_count: number;
  created_review_count: number;
  skipped_existing_count: number;
  reviews: ScreenArtifactReview[];
  policy: ScreenArtifactPolicy;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenProviderConfigProposal = {
  id: number;
  status: string;
  title: string;
  provider: string;
  target_window_title?: string | null;
  proposal: {
    env_patch: Record<string, string>;
    manual_review_required: boolean;
    apply_automatically: boolean;
    writes_env: boolean;
    executes_commands: boolean;
    real_screen_capture_enabled_by_api: boolean;
    ocr_enabled_by_api: boolean;
    operator_steps: string[];
    rollback_steps: string[];
  };
  rationale: Record<string, any>;
  reviewed_by?: string | null;
  review_note?: string | null;
  reviewed_at?: string | null;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenProviderReplayRun = {
  id: number;
  status: string;
  proposal_id?: number | null;
  proposal_title?: string | null;
  proposal_status?: string | null;
  scenario_name: string;
  steps: Array<{
    name: string;
    status: string;
    reason: string;
    evidence: Record<string, any>;
    real_screen_capture: boolean;
    pixel_data_stored: boolean;
    ocr_executed: boolean;
    writes_env: boolean;
    executes_commands: boolean;
  }>;
  summary: {
    scenario_name: string;
    proposal_id?: number | null;
    step_count: number;
    passed_count: number;
    blocked_count: number;
    readiness_status: string;
    allowed_output: string;
    forbidden_actions: string[];
  };
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
  created_at: string;
};

type ScreenReadinessAuditReport = {
  status: string;
  stage: string;
  generated_at: string;
  summary: {
    readiness_status: string;
    active_provider: string;
    provider_status: string;
    ready_check_count: number;
    blocked_check_count: number;
    observation_count: number;
    observation_warning_count: number;
    artifact_review_count: number;
    artifact_pending_count: number;
    config_proposal_count: number;
    config_pending_count: number;
    provider_replay_count: number;
    provider_replay_blocked_count: number;
    safety_passed: boolean;
    allowed_output: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  blockers: Array<{
    source: string;
    name?: string;
    reason?: string;
    status?: string;
  }>;
  evidence: Record<string, any>;
  safety_matrix: Array<{
    name: string;
    status: string;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  next_safe_steps: string[];
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenReadinessAuditAck = {
  id: number;
  status: string;
  report_hash: string;
  report_status: string;
  report_stage: string;
  summary: ScreenReadinessAuditReport["summary"];
  safety_matrix: ScreenReadinessAuditReport["safety_matrix"];
  report: ScreenReadinessAuditReport;
  acknowledged_by: string;
  acknowledgement_note?: string | null;
  acknowledgement_effect: string;
  writes_env: boolean;
  executes_commands: boolean;
  real_screen_capture: boolean;
  pixel_data_stored: boolean;
  ocr_executed: boolean;
  broker_action: boolean;
  order_action: boolean;
  credential_access: boolean;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
  created_at: string;
  updated_at: string;
};

type ScreenReadinessTimeline = {
  status: string;
  stage: string;
  generated_at: string;
  item_count: number;
  counts_by_type: Record<string, number>;
  items: Array<{
    id: string;
    item_type: string;
    source_id?: string | number | null;
    event_ts: string;
    title: string;
    status: string;
    summary: Record<string, any>;
    writes_env: boolean;
    executes_commands: boolean;
    real_screen_capture: boolean;
    pixel_data_stored: boolean;
    ocr_executed: boolean;
    broker_action: boolean;
    order_action: boolean;
    credential_access: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenReadinessEvidenceExport = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  bundle_hash: string;
  bundle_scope: string[];
  capabilities: ScreenMonitoringCapabilities;
  provider_readiness: ScreenProviderReadiness;
  readiness_audit_report: ScreenReadinessAuditReport;
  readiness_audit_acknowledgements: ScreenReadinessAuditAck[];
  readiness_timeline: ScreenReadinessTimeline;
  export_metadata: {
    format: string;
    delivery: string;
    writes_file: boolean;
    download_created: boolean;
    operator_archive_ready: boolean;
    allowed_output: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  safety: {
    writes_env: boolean;
    executes_commands: boolean;
    writes_file: boolean;
    download_created: boolean;
    real_screen_capture: boolean;
    pixel_data_stored: boolean;
    ocr_executed: boolean;
    broker_action: boolean;
    order_action: boolean;
    credential_access: boolean;
    live_trading_enabled: boolean;
    allowed_output: string;
    review_only: boolean;
    simulation_only: boolean;
  };
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenReadinessVerification = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  export_bundle_hash: string;
  verified_export_stage: string;
  check_count: number;
  passed_count: number;
  failed_count: number;
  checks: Array<{
    name: string;
    status: string;
    value: unknown;
    expected: unknown;
    reason: string;
    severity: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  failed_checks: Array<{
    name: string;
    status: string;
    value: unknown;
    expected: unknown;
    reason: string;
    severity: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  safety_summary: {
    writes_file: boolean;
    download_created: boolean;
    executes_commands: boolean;
    writes_env: boolean;
    real_screen_capture: boolean;
    pixel_data_stored: boolean;
    ocr_executed: boolean;
    broker_action: boolean;
    order_action: boolean;
    credential_access: boolean;
    live_trading_enabled: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenReadinessComparisonSummary = {
    schema_version: string;
    status: string;
    stage: string;
    export_bundle_hash: string;
    verified_export_stage: string;
    check_count: number;
    passed_count: number;
    failed_count: number;
    failed_check_names: string[];
    check_statuses: Record<string, string>;
    safety_summary: ScreenReadinessVerification["safety_summary"];
    allowed_output: string;
    forbidden_actions: string[];
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
};

type ScreenReadinessComparison = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  baseline: ScreenReadinessComparisonSummary;
  candidate: ScreenReadinessComparisonSummary;
  difference_count: number;
  differences: Array<{
    field: string;
    status: string;
    baseline: unknown;
    candidate: unknown;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  comparison_scope: string[];
  safety_summary: ScreenReadinessVerification["safety_summary"];
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenReadinessHealthFlag = {
  name: string;
  status: string;
  reason: string;
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenReadinessHealth = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  summary: {
    capture_provider: string;
    provider_status: string;
    readiness_status: string;
    audit_status: string;
    export_status: string;
    verification_status: string;
    comparison_status: string;
    acknowledgement_count: number;
    timeline_item_count: number;
    readiness_blocked_count: number;
    audit_blocked_check_count: number;
    artifact_pending_count: number;
    config_pending_count: number;
    verification_failed_count: number;
    comparison_difference_count: number;
    export_bundle_hash: string;
    allowed_output: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  module_statuses: Array<{
    name: string;
    status: string;
    stage: string;
    live_trading_enabled: boolean;
    review_only: boolean;
    simulation_only: boolean;
  }>;
  health_flags: ScreenReadinessHealthFlag[];
  failed_flags: ScreenReadinessHealthFlag[];
  operator_notes: string[];
  safety_summary: ScreenReadinessVerification["safety_summary"];
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenDigestHistoryProposal = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  proposal: {
    name: string;
    purpose: string;
    default_state: string;
    recommended_retention_days: number;
    max_records_per_day: number;
    dedupe_key: string;
    storage_mode: string;
    required_fields: string[];
    excluded_fields: string[];
    operator_review_required: boolean;
    apply_automatically: boolean;
    writes_database_now: boolean;
    writes_file: boolean;
    download_created: boolean;
    executes_commands: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  current_digest_summary: {
    digest_status: string;
    digest_stage: string;
    export_bundle_hash: string;
    readiness_status: string;
    audit_status: string;
    verification_status: string;
    comparison_status: string;
    failed_health_flag_names: string[];
    allowed_output: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  review_gates: Array<{
    name: string;
    status: string;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  safety_summary: ScreenReadinessHealth["safety_summary"] & {
    writes_database_now: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenDigestMigrationChecklist = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  migration_plan: {
    target_table: string;
    source_schema: string;
    source_digest_stage: string;
    migration_type: string;
    default_state: string;
    table_exists_now: boolean;
    create_table_now: boolean;
    backfill_now: boolean;
    writes_database_now: boolean;
    writes_migration_file_now: boolean;
    apply_automatically: boolean;
    operator_review_required: boolean;
    rollback_required: boolean;
    test_required: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  field_mapping: Array<{
    source: string;
    target: string;
    storage: string;
  }>;
  excluded_fields: string[];
  checks: Array<{
    name: string;
    status: string;
    required: boolean;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  summary: {
    required_check_count: number;
    passed_check_count: number;
    review_required_count: number;
    blocked_check_count: number;
    migration_allowed_now: boolean;
    manual_review_required: boolean;
    current_export_bundle_hash: string;
    proposal_allowed_output: string;
    allowed_output: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  required_future_artifacts: string[];
  safety_summary: ScreenDigestHistoryProposal["safety_summary"] & {
    creates_table_now: boolean;
    runs_migration_now: boolean;
    writes_migration_file_now: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenDigestMigrationSpecVerification = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  spec_hash: string;
  spec_preview: string;
  target_table: string;
  check_count: number;
  passed_count: number;
  failed_count: number;
  checks: Array<{
    name: string;
    status: string;
    reason: string;
    details: Record<string, any>;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  failed_checks: Array<{
    name: string;
    status: string;
    reason: string;
    details: Record<string, any>;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  missing_fields: string[];
  safety_blocks: Array<{
    name: string;
    matches: string[];
    blocked: boolean;
  }>;
  source_checklist_status: string;
  migration_allowed_now: boolean;
  safety_summary: ScreenDigestMigrationChecklist["safety_summary"] & {
    executes_sql: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenDigestMigrationSpecApproval = {
  schema_version: string;
  status: string;
  stage: string;
  event_id: number | null;
  event_type?: string;
  created_at?: string;
  approved_at: string;
  approved_by: string;
  approval_note: string | null;
  approval_effect: string;
  spec_hash: string;
  verification_status: string;
  verification_failed_count: number;
  source_checklist_status: string;
  migration_allowed_now: boolean;
  future_migration_still_requires: string[];
  safety_summary: ScreenDigestMigrationSpecVerification["safety_summary"] & {
    writes_database_event_now: boolean;
    writes_digest_history_table_now: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
  verification?: {
    schema_version: string;
    status: string;
    spec_hash: string;
    failed_count: number;
    allowed_output: string;
    migration_allowed_now: boolean;
    live_trading_enabled: boolean;
  };
};

type ScreenDigestReleaseReadiness = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  decision: {
    go_no_go: string;
    migration_allowed_now: boolean;
    requires_human_release_approval: boolean;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  evidence: {
    checklist_status: string;
    verification_status: string;
    verification_failed_count: number;
    approval_count: number;
    latest_approval_status: string | null;
    latest_approval_event_id: number | null;
    spec_hash: string;
    approved_spec_hash: string | null;
    allowed_output: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  gates: Array<{
    name: string;
    status: string;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  blocked_gates: Array<{
    name: string;
    status: string;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  review_required_gates: Array<{
    name: string;
    status: string;
    reason: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  }>;
  required_before_actual_migration: string[];
  safety_summary: ScreenDigestMigrationSpecApproval["safety_summary"] & {
    writes_database_now: boolean;
    writes_digest_history_table_now: boolean;
    writes_file: boolean;
    download_created: boolean;
    executes_commands: boolean;
    writes_env: boolean;
    real_screen_capture: boolean;
    pixel_data_stored: boolean;
    credential_access: boolean;
  };
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenDigestApprovalReview = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  review_policy: {
    max_age_days: number;
    rotation_required_when: string[];
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  latest_approval: {
    event_id: number | null;
    status: string | null;
    approved_at: string | null;
    created_at: string | null;
    approved_by: string | null;
    spec_hash: string | null;
    verification_status: string | null;
    approval_age_hours: number | null;
    approval_age_days: number | null;
    expires_at: string | null;
    is_expired: boolean;
    matches_current_spec: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  current_spec: {
    spec_hash: string;
    verification_status: string;
    failed_count: number;
    migration_allowed_now: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  release_readiness: {
    status: string;
    go_no_go: string;
    approval_count: number;
    latest_approval_event_id: number | null;
    migration_allowed_now: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  gates: ScreenDigestReleaseReadiness["gates"];
  blocked_gates: ScreenDigestReleaseReadiness["gates"];
  review_required_gates: ScreenDigestReleaseReadiness["gates"];
  decision: {
    next_required_action: string;
    migration_allowed_now: boolean;
    approval_can_be_reused_for_manual_release_review: boolean;
    requires_human_release_approval: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  safety_summary: ScreenDigestReleaseReadiness["safety_summary"];
  allowed_output: string;
  forbidden_actions: string[];
  review_only: boolean;
  simulation_only: boolean;
  live_trading_enabled: boolean;
};

type ScreenDigestReleasePackage = {
  schema_version: string;
  status: string;
  stage: string;
  generated_at: string;
  package_id: string;
  package_id_inputs: Record<string, any>;
  manifest: {
    name: string;
    purpose: string;
    items: Array<{
      name: string;
      status: string | null;
      allowed_output: string | null;
      generated_at: string | null;
      included: boolean;
      review_only: boolean;
      simulation_only: boolean;
      live_trading_enabled: boolean;
    }>;
    required_manual_artifacts_before_execution: string[];
    delivery: string;
    writes_file: boolean;
    download_created: boolean;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  evidence: {
    proposal_status: string;
    checklist_status: string;
    verification_status: string;
    verification_failed_count: number;
    latest_approval_event_id: number | null;
    latest_approval_status: string | null;
    release_readiness_status: string;
    approval_review_status: string;
    spec_hash: string;
    approved_spec_hash: string | null;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  gates: ScreenDigestReleaseReadiness["gates"];
  blocked_gates: ScreenDigestReleaseReadiness["gates"];
  review_required_gates: ScreenDigestReleaseReadiness["gates"];
  decision: {
    go_no_go: string;
    migration_allowed_now: boolean;
    execution_allowed_now: boolean;
    requires_human_release_approval: boolean;
    next_required_action: string;
    review_only: boolean;
    simulation_only: boolean;
    live_trading_enabled: boolean;
  };
  safety_summary: ScreenDigestReleaseReadiness["safety_summary"];
  allowed_output: string;
  forbidden_actions: string[];
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
const dataset2Readiness = ref<Dataset2Readiness | null>(null);
const dataset2Preview = ref<Dataset2Preview | null>(null);
const dataset2CleanupPackage = ref<Dataset2CleanupPackage | null>(null);
const dataset2ImportQueueReview = ref<Dataset2ImportQueueReview | null>(null);
const dataset2ImportQueueReviews = ref<Dataset2ImportQueueReview[]>([]);
const dataset2StagingImport = ref<Dataset2StagingImport | null>(null);
const dataset2StagingRecords = ref<Dataset2StagingRecord[]>([]);
const dataset2StagingSummary = ref<Dataset2StagingSummary | null>(null);
const dataset2StagingQualityReview = ref<Dataset2StagingQualityReview | null>(null);
const dataset2StagingQualityReviews = ref<Dataset2StagingQualityReview[]>([]);
const dataset2StagingFixPlan = ref<Dataset2StagingFixPlan | null>(null);
const dataset2StagingFixPlans = ref<Dataset2StagingFixPlan[]>([]);
const dataset2StagingFixApproval = ref<Dataset2StagingFixApproval | null>(null);
const dataset2StagingFixApprovals = ref<Dataset2StagingFixApproval[]>([]);
const dataset2StagingFixPreflight = ref<Dataset2StagingFixPreflight | null>(null);
const dataset2StagingFixPreflights = ref<Dataset2StagingFixPreflight[]>([]);
const dataset2CleanupExecutionSpec = ref<Dataset2CleanupExecutionSpec | null>(null);
const dataset2CleanupExecutionSpecs = ref<Dataset2CleanupExecutionSpec[]>([]);
const dataset2CleanupDryRun = ref<Dataset2CleanupDryRun | null>(null);
const dataset2CleanupDryRuns = ref<Dataset2CleanupDryRun[]>([]);
const dataset2ManualEvidence = ref<Dataset2ManualEvidence | null>(null);
const dataset2ManualEvidenceHistory = ref<Dataset2ManualEvidence[]>([]);
const dataset2ManualEvidenceAcceptance = ref<Dataset2ManualEvidenceAcceptance | null>(null);
const dataset2ManualEvidenceAcceptanceHistory = ref<Dataset2ManualEvidenceAcceptance[]>([]);
const dataset2CleanupApplicationReview = ref<Dataset2CleanupApplicationReview | null>(null);
const dataset2CleanupApplicationReviews = ref<Dataset2CleanupApplicationReview[]>([]);
const dataset2CleanupExecutionApprovalPlan = ref<Dataset2CleanupExecutionApprovalPlan | null>(null);
const dataset2CleanupExecutionApprovalPlans = ref<Dataset2CleanupExecutionApprovalPlan[]>([]);
const dataset2CleanupExecutionManualApproval = ref<Dataset2CleanupExecutionManualApproval | null>(null);
const dataset2CleanupExecutionManualApprovals = ref<Dataset2CleanupExecutionManualApproval[]>([]);
const dataset2CleanupExecutionPreflight = ref<Dataset2CleanupExecutionPreflight | null>(null);
const dataset2CleanupExecutionPreflights = ref<Dataset2CleanupExecutionPreflight[]>([]);
const dataset2CleanupExecutionDryRun = ref<Dataset2CleanupExecutionDryRun | null>(null);
const dataset2CleanupExecutionDryRuns = ref<Dataset2CleanupExecutionDryRun[]>([]);
const dataset2CleanupExecutionDryRunReview = ref<Dataset2CleanupExecutionDryRunReview | null>(null);
const dataset2CleanupExecutionDryRunReviews = ref<Dataset2CleanupExecutionDryRunReview[]>([]);
const dataset2CleanupExecutionPlan = ref<Dataset2CleanupExecutionPlan | null>(null);
const dataset2CleanupExecutionPlans = ref<Dataset2CleanupExecutionPlan[]>([]);
const dataset2CleanupExecutionPlanPreflight = ref<Dataset2CleanupExecutionPlanPreflight | null>(null);
const dataset2CleanupExecutionPlanPreflights = ref<Dataset2CleanupExecutionPlanPreflight[]>([]);
const dataset2ControlledCleanupDryRun = ref<Dataset2ControlledCleanupDryRun | null>(null);
const dataset2ControlledCleanupDryRuns = ref<Dataset2ControlledCleanupDryRun[]>([]);
const dataset2ControlledCleanupDryRunReview = ref<Dataset2ControlledCleanupDryRunReview | null>(null);
const dataset2ControlledCleanupDryRunReviews = ref<Dataset2ControlledCleanupDryRunReview[]>([]);
const dataset2ControlledCleanupApproval = ref<Dataset2ControlledCleanupApproval | null>(null);
const dataset2ControlledCleanupApprovals = ref<Dataset2ControlledCleanupApproval[]>([]);
const dataset2ControlledCleanupPreflight = ref<Dataset2ControlledCleanupPreflight | null>(null);
const dataset2ControlledCleanupPreflights = ref<Dataset2ControlledCleanupPreflight[]>([]);
const dataset2ControlledCleanupApplyDryRun = ref<Dataset2ControlledCleanupApplyDryRun | null>(null);
const dataset2ControlledCleanupApplyDryRuns = ref<Dataset2ControlledCleanupApplyDryRun[]>([]);
const dataset2ControlledCleanupApplyDryRunReview = ref<Dataset2ControlledCleanupApplyDryRunReview | null>(null);
const dataset2ControlledCleanupApplyDryRunReviews = ref<Dataset2ControlledCleanupApplyDryRunReview[]>([]);
const monitoring = ref<MonitoringRun | null>(null);
const monitoringReview = ref<MonitoringReview | null>(null);
const phaseReplays = ref<PhaseReplay[]>([]);
const phaseMatch = ref<PhaseMatch | null>(null);
const potentialSearch = ref<PotentialSearchRun | null>(null);
const agentCapabilities = ref<AgentCapabilities | null>(null);
const agentTasks = ref<AgentTask[]>([]);
const agentAudit = ref<any[]>([]);
const tradeGatewayCapabilities = ref<TradeGatewayCapabilities | null>(null);
const tradeGatewayReviewGates = ref<TradeGatewayReviewGates | null>(null);
const tradeGatewayManualContract = ref<TradeGatewayManualContract | null>(null);
const tradeGatewayAuditSchema = ref<TradeGatewayAuditSchema | null>(null);
const tradeGatewayRiskContract = ref<TradeGatewayRiskContract | null>(null);
const tradeGatewayRollbackRunbook = ref<TradeGatewayRollbackRunbook | null>(null);
const tradeGatewayPreLivePackage = ref<TradeGatewayPreLivePackage | null>(null);
const tradeGatewayAcceptanceChecklist = ref<TradeGatewayAcceptanceChecklist | null>(null);
const tradeGatewayReleaseGate = ref<TradeGatewayReleaseGate | null>(null);
const tradeGatewayFinalReport = ref<TradeGatewayFinalReport | null>(null);
const tradeGatewayBrokerThreatModel = ref<TradeGatewayBrokerThreatModel | null>(null);
const tradeGatewayBrokerInterfaceDraft = ref<TradeGatewayBrokerInterfaceDraft | null>(null);
const tradeGatewayBrokerContractVerification = ref<TradeGatewayBrokerContractVerification | null>(null);
const tradeGatewayOrderFailureFixtures = ref<TradeGatewayOrderFailureFixtures | null>(null);
const tradeGatewayOrderRunbookMapping = ref<TradeGatewayOrderRunbookMapping | null>(null);
const tradeGatewayAuditStoragePlan = ref<TradeGatewayAuditStoragePlan | null>(null);
const tradeGatewayAuditMigrationSpecVerification = ref<TradeGatewayAuditMigrationSpecVerification | null>(null);
const tradeGatewayAuditMigrationSpecApprovals = ref<TradeGatewayAuditMigrationSpecApproval[]>([]);
const tradeGatewayAuditMigrationSpecApprovalResult = ref<TradeGatewayAuditMigrationSpecApproval | null>(null);
const tradeGatewayAuditMigrationReleaseReadiness = ref<TradeGatewayAuditMigrationReleaseReadiness | null>(null);
const tradeGatewayAuditMigrationApprovalReview = ref<TradeGatewayAuditMigrationApprovalReview | null>(null);
const tradeGatewayAuditMigrationReleasePackage = ref<TradeGatewayAuditMigrationReleasePackage | null>(null);
const tradeGatewayAuditMigrationPackageIntegrity = ref<TradeGatewayAuditMigrationReleasePackageIntegrityReview | null>(null);
const tradeGatewayAuditMigrationReleaseRehearsal = ref<TradeGatewayAuditMigrationManualReleaseRehearsal | null>(null);
const tradeGatewayAuditMigrationEvidenceVerification = ref<TradeGatewayAuditMigrationManualReleaseEvidenceVerification | null>(null);
const tradeGatewayAuditMigrationEvidenceComparison = ref<TradeGatewayAuditMigrationManualReleaseEvidenceComparison | null>(null);
const tradeGatewayAuditMigrationHealthDigest = ref<TradeGatewayAuditMigrationManualReleaseHealthDigest | null>(null);
const tradeGatewayAuditMigrationHealthDigestHistoryProposal = ref<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryProposal | null>(null);
const tradeGatewayAuditMigrationHealthDigestHistoryChecklist = ref<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryMigrationChecklist | null>(null);
const tradeGatewayAuditMigrationHealthDigestHistorySpecVerification = ref<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryMigrationSpecVerification | null>(null);
const tradeGatewayAuditMigrationHealthDigestHistorySpecApprovalResult = ref<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryMigrationSpecApproval | null>(null);
const tradeGatewayAuditMigrationHealthDigestHistorySpecApprovals = ref<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryMigrationSpecApproval[]>([]);
const tradeGatewayAuditMigrationHealthDigestHistoryReleaseReadiness = ref<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseReadiness | null>(null);
const tradeGatewayAuditMigrationHealthDigestHistoryApprovalReview = ref<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryApprovalReview | null>(null);
const tradeGatewayAuditMigrationHealthDigestHistoryReleasePackage = ref<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleasePackage | null>(null);
const tradeGatewayAuditMigrationHealthDigestHistoryPackageIntegrity = ref<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryPackageIntegrityReview | null>(null);
const tradeGatewayAuditMigrationHealthDigestHistoryReleaseRehearsal = ref<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseRehearsal | null>(null);
const tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidence = ref<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseEvidenceVerification | null>(null);
const tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidenceComparison = ref<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseEvidenceComparison | null>(null);
const tradeGatewayAuditMigrationHealthDigestHistoryReleaseHealthDigest = ref<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseHealthDigest | null>(null);
const discoveryLoading = ref(false);
const loading = ref(false);
const planLoading = ref(false);
const analysisLoading = ref(false);
const automationLoading = ref(false);
const monitoringLoading = ref(false);
const dataset2Loading = ref(false);
const phaseReplayLoading = ref(false);
const phaseMatchLoading = ref(false);
const potentialSearchLoading = ref(false);
const agentTaskLoading = ref(false);
const tradeGatewayLoading = ref(false);
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
const realtimeSchedulerPlan = ref<RealtimeSchedulerPlan | null>(null);
const realtimeAutomationProposal = ref<RealtimeAutomationProposal | null>(null);
const realtimeHealth = ref<RealtimeProviderHealth[]>([]);
const realtimeSnapshot = ref<RealtimeSnapshot | null>(null);
const realtimeEvents = ref<RealtimeEvent[]>([]);
const realtimeReplay = ref<RealtimeReplay | null>(null);
const realtimeRefreshResult = ref<RealtimeRefreshResult | null>(null);
const realtimeMonitoringSync = ref<RealtimeMonitoringSyncResult | null>(null);
const realtimeCycleResult = ref<RealtimeCycleResult | null>(null);
const realtimeCycleRuns = ref<RealtimeCycleRun[]>([]);
const realtimeLoading = ref(false);
const screenMonitoringCapabilities = ref<ScreenMonitoringCapabilities | null>(null);
const screenMonitoringProviders = ref<ScreenProviderCapabilities[]>([]);
const screenProviderReadiness = ref<ScreenProviderReadiness | null>(null);
const screenMonitoringSession = ref<ScreenMonitoringSession | null>(null);
const screenObservations = ref<ScreenObservation[]>([]);
const screenObservationResult = ref<ScreenObservation | null>(null);
const screenFixtureReplayResult = ref<ScreenFixtureReplayResult | null>(null);
const screenPreflightResult = ref<ScreenPreflightResult | null>(null);
const screenCaptureStubResult = ref<ScreenCaptureStubResult | null>(null);
const screenArtifactPolicy = ref<ScreenArtifactPolicy | null>(null);
const screenArtifactReviews = ref<ScreenArtifactReview[]>([]);
const screenArtifactSyncResult = ref<ScreenArtifactSyncResult | null>(null);
const screenProviderConfigProposals = ref<ScreenProviderConfigProposal[]>([]);
const screenProviderConfigProposalResult = ref<ScreenProviderConfigProposal | null>(null);
const screenProviderReplayRuns = ref<ScreenProviderReplayRun[]>([]);
const screenProviderReplayResult = ref<ScreenProviderReplayRun | null>(null);
const screenReadinessAudit = ref<ScreenReadinessAuditReport | null>(null);
const screenReadinessAuditAcks = ref<ScreenReadinessAuditAck[]>([]);
const screenReadinessAuditAckResult = ref<ScreenReadinessAuditAck | null>(null);
const screenReadinessTimeline = ref<ScreenReadinessTimeline | null>(null);
const screenReadinessExport = ref<ScreenReadinessEvidenceExport | null>(null);
const screenReadinessVerification = ref<ScreenReadinessVerification | null>(null);
const screenReadinessComparison = ref<ScreenReadinessComparison | null>(null);
const screenReadinessHealth = ref<ScreenReadinessHealth | null>(null);
const screenDigestHistoryProposal = ref<ScreenDigestHistoryProposal | null>(null);
const screenDigestMigrationChecklist = ref<ScreenDigestMigrationChecklist | null>(null);
const screenDigestMigrationSpecVerification = ref<ScreenDigestMigrationSpecVerification | null>(null);
const screenDigestMigrationSpecApprovalResult = ref<ScreenDigestMigrationSpecApproval | null>(null);
const screenDigestMigrationSpecApprovals = ref<ScreenDigestMigrationSpecApproval[]>([]);
const screenDigestReleaseReadiness = ref<ScreenDigestReleaseReadiness | null>(null);
const screenDigestApprovalReview = ref<ScreenDigestApprovalReview | null>(null);
const screenDigestReleasePackage = ref<ScreenDigestReleasePackage | null>(null);
const screenMonitoringLoading = ref(false);
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

async function loadDataset2Readiness() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    dataset2Readiness.value = await fetchJson<Dataset2Readiness>("/api/learning/dataset2/readiness");
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 readiness failed";
    dataset2Readiness.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2Preview() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    dataset2Preview.value = await fetchJson<Dataset2Preview>("/api/learning/dataset2/normalized-preview?limit=10", {
      method: "POST"
    });
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 normalized preview failed";
    dataset2Preview.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2CleanupPackage() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    dataset2CleanupPackage.value = await fetchJson<Dataset2CleanupPackage>("/api/learning/dataset2/cleanup-package", {
      method: "POST"
    });
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 cleanup package failed";
    dataset2CleanupPackage.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function recordDataset2ImportQueueReview() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    dataset2ImportQueueReview.value = await fetchJson<Dataset2ImportQueueReview>("/api/learning/dataset2/import-queue/review", {
      method: "POST",
      body: JSON.stringify({ reviewed_by: "dashboard", note: "V5.6-P3 pre-staging metadata review" })
    });
    await loadDataset2ImportQueueReviews();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 import queue review failed";
    dataset2ImportQueueReview.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2ImportQueueReviews() {
  try {
    dataset2ImportQueueReviews.value = await fetchJson<Dataset2ImportQueueReview[]>("/api/learning/dataset2/import-queue/reviews?limit=5");
  } catch {
    dataset2ImportQueueReviews.value = [];
  }
}

async function importDataset2ToStaging() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2ImportQueueReview?.value?.event_id) {
      dataset2ImportQueueReview.value = await fetchJson<Dataset2ImportQueueReview>("/api/learning/dataset2/import-queue/review", {
        method: "POST",
        body: JSON.stringify({ reviewed_by: "dashboard", note: "V5.6-P3 pre-staging metadata review" })
      });
    }
    dataset2StagingImport.value = await fetchJson<Dataset2StagingImport>("/api/learning/dataset2/staging/import", {
      method: "POST",
      body: JSON.stringify({
        review_event_id: dataset2ImportQueueReview.value?.event_id,
        imported_by: "dashboard",
        note: "V5.6-P3 quarantine staging only"
      })
    });
    await loadDataset2Staging();
    await loadDataset2StagingQualityReviews();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 staging import failed";
    dataset2StagingImport.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function reviewDataset2StagingQuality() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    dataset2StagingQualityReview.value = await fetchJson<Dataset2StagingQualityReview>("/api/learning/dataset2/staging/quality-review", {
      method: "POST",
      body: JSON.stringify({
        package_id: dataset2StagingImport.value?.package_id ?? dataset2StagingSummary.value?.latest_packages?.[0]?.package_id,
        reviewed_by: "dashboard",
        note: "V5.6-P4 training-freeze quality gates"
      })
    });
    await loadDataset2StagingQualityReviews();
    await loadDataset2StagingFixPlans();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 staging quality review failed";
    dataset2StagingQualityReview.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function planDataset2StagingFixes() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2StagingQualityReview.value?.event_id) {
      await reviewDataset2StagingQuality();
    }
    dataset2StagingFixPlan.value = await fetchJson<Dataset2StagingFixPlan>("/api/learning/dataset2/staging/fix-plan", {
      method: "POST",
      body: JSON.stringify({
        quality_review_id: dataset2StagingQualityReview.value?.event_id,
        planned_by: "dashboard",
        note: "V5.6-P5 review-only freeze fix plan"
      })
    });
    await loadDataset2StagingFixPlans();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 staging fix plan failed";
    dataset2StagingFixPlan.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2Staging() {
  try {
    dataset2StagingSummary.value = await fetchJson<Dataset2StagingSummary>("/api/learning/dataset2/staging/summary");
    dataset2StagingRecords.value = await fetchJson<Dataset2StagingRecord[]>("/api/learning/dataset2/staging/records?limit=5");
  } catch {
    dataset2StagingSummary.value = null;
    dataset2StagingRecords.value = [];
  }
}

async function loadDataset2StagingQualityReviews() {
  try {
    dataset2StagingQualityReviews.value = await fetchJson<Dataset2StagingQualityReview[]>("/api/learning/dataset2/staging/quality-reviews?limit=5");
    dataset2StagingQualityReview.value = dataset2StagingQualityReviews.value[0] ?? dataset2StagingQualityReview.value;
  } catch {
    dataset2StagingQualityReviews.value = [];
  }
}

async function loadDataset2StagingFixPlans() {
  try {
    dataset2StagingFixPlans.value = await fetchJson<Dataset2StagingFixPlan[]>("/api/learning/dataset2/staging/fix-plans?limit=5");
    dataset2StagingFixPlan.value = dataset2StagingFixPlans.value[0] ?? dataset2StagingFixPlan.value;
  } catch {
    dataset2StagingFixPlans.value = [];
  }
}

async function approveDataset2StagingFixPlan() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2StagingFixPlan.value?.event_id && !dataset2StagingFixPlan.value?.id) {
      await planDataset2StagingFixes();
    }
    dataset2StagingFixApproval.value = await fetchJson<Dataset2StagingFixApproval>("/api/learning/dataset2/staging/fix-plan/approval", {
      method: "POST",
      body: JSON.stringify({
        fix_plan_event_id: dataset2StagingFixPlan.value?.event_id ?? dataset2StagingFixPlan.value?.id,
        approved_by: "dashboard",
        approval_decision: "approved_for_preflight",
        note: "V5.6-P6 metadata approval for preflight only"
      })
    });
    await loadDataset2StagingFixApprovals();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 fix approval failed";
    dataset2StagingFixApproval.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function preflightDataset2StagingFixes() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2StagingFixApproval.value?.event_id && !dataset2StagingFixApproval.value?.id) {
      await approveDataset2StagingFixPlan();
    }
    dataset2StagingFixPreflight.value = await fetchJson<Dataset2StagingFixPreflight>("/api/learning/dataset2/staging/fix-preflight", {
      method: "POST",
      body: JSON.stringify({
        approval_event_id: dataset2StagingFixApproval.value?.event_id ?? dataset2StagingFixApproval.value?.id,
        requested_by: "dashboard",
        note: "V5.6-P6 deterministic preflight only"
      })
    });
    await loadDataset2StagingFixPreflights();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 fix preflight failed";
    dataset2StagingFixPreflight.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2StagingFixApprovals() {
  try {
    dataset2StagingFixApprovals.value = await fetchJson<Dataset2StagingFixApproval[]>("/api/learning/dataset2/staging/fix-plan/approvals?limit=5");
    dataset2StagingFixApproval.value = dataset2StagingFixApprovals.value[0] ?? dataset2StagingFixApproval.value;
  } catch {
    dataset2StagingFixApprovals.value = [];
  }
}

async function loadDataset2StagingFixPreflights() {
  try {
    dataset2StagingFixPreflights.value = await fetchJson<Dataset2StagingFixPreflight[]>("/api/learning/dataset2/staging/fix-preflights?limit=5");
    dataset2StagingFixPreflight.value = dataset2StagingFixPreflights.value[0] ?? dataset2StagingFixPreflight.value;
  } catch {
    dataset2StagingFixPreflights.value = [];
  }
}

async function specDataset2CleanupExecution() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2StagingFixPreflight.value?.event_id && !dataset2StagingFixPreflight.value?.id) {
      await preflightDataset2StagingFixes();
    }
    dataset2CleanupExecutionSpec.value = await fetchJson<Dataset2CleanupExecutionSpec>("/api/learning/dataset2/staging/cleanup-execution-spec", {
      method: "POST",
      body: JSON.stringify({
        preflight_event_id: dataset2StagingFixPreflight.value?.event_id ?? dataset2StagingFixPreflight.value?.id,
        specified_by: "dashboard",
        note: "V5.6-P7 review-only cleanup execution spec"
      })
    });
    await loadDataset2CleanupExecutionSpecs();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 cleanup execution spec failed";
    dataset2CleanupExecutionSpec.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2CleanupExecutionSpecs() {
  try {
    dataset2CleanupExecutionSpecs.value = await fetchJson<Dataset2CleanupExecutionSpec[]>("/api/learning/dataset2/staging/cleanup-execution-specs?limit=5");
    dataset2CleanupExecutionSpec.value = dataset2CleanupExecutionSpecs.value[0] ?? dataset2CleanupExecutionSpec.value;
  } catch {
    dataset2CleanupExecutionSpecs.value = [];
  }
}

async function verifyDataset2CleanupDryRun() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2CleanupExecutionSpec.value?.event_id && !dataset2CleanupExecutionSpec.value?.id) {
      await specDataset2CleanupExecution();
    }
    dataset2CleanupDryRun.value = await fetchJson<Dataset2CleanupDryRun>("/api/learning/dataset2/staging/cleanup-execution-spec/dry-run-verify", {
      method: "POST",
      body: JSON.stringify({
        execution_spec_event_id: dataset2CleanupExecutionSpec.value?.event_id ?? dataset2CleanupExecutionSpec.value?.id,
        verified_by: "dashboard",
        note: "V5.6-P8 dry-run verification only"
      })
    });
    await loadDataset2CleanupDryRuns();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 cleanup dry-run verification failed";
    dataset2CleanupDryRun.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2CleanupDryRuns() {
  try {
    dataset2CleanupDryRuns.value = await fetchJson<Dataset2CleanupDryRun[]>("/api/learning/dataset2/staging/cleanup-execution-spec/dry-run-verifications?limit=5");
    dataset2CleanupDryRun.value = dataset2CleanupDryRuns.value[0] ?? dataset2CleanupDryRun.value;
  } catch {
    dataset2CleanupDryRuns.value = [];
  }
}

async function verifyDataset2ManualEvidence() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2CleanupDryRun.value?.event_id && !dataset2CleanupDryRun.value?.id) {
      await verifyDataset2CleanupDryRun();
    }
    dataset2ManualEvidence.value = await fetchJson<Dataset2ManualEvidence>("/api/learning/dataset2/staging/cleanup-manual-evidence/verify", {
      method: "POST",
      body: JSON.stringify({
        dry_run_verification_id: dataset2CleanupDryRun.value?.event_id ?? dataset2CleanupDryRun.value?.id,
        evidence_package: {},
        verified_by: "dashboard",
        note: "V5.6-P12 empty evidence package verification only"
      })
    });
    await loadDataset2ManualEvidenceHistory();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 manual evidence verification failed";
    dataset2ManualEvidence.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2ManualEvidenceHistory() {
  try {
    dataset2ManualEvidenceHistory.value = await fetchJson<Dataset2ManualEvidence[]>("/api/learning/dataset2/staging/cleanup-manual-evidence/verifications?limit=5");
    dataset2ManualEvidence.value = dataset2ManualEvidenceHistory.value[0] ?? dataset2ManualEvidence.value;
  } catch {
    dataset2ManualEvidenceHistory.value = [];
  }
}

async function reviewDataset2ManualEvidenceAcceptance() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2ManualEvidence.value?.event_id && !dataset2ManualEvidence.value?.id) {
      await loadDataset2ManualEvidenceHistory();
    }
    dataset2ManualEvidenceAcceptance.value = await fetchJson<Dataset2ManualEvidenceAcceptance>(
      "/api/learning/dataset2/staging/cleanup-manual-evidence/acceptance-review",
      {
        method: "POST",
        body: JSON.stringify({
          manual_evidence_verification_id: dataset2ManualEvidence.value?.event_id ?? dataset2ManualEvidence.value?.id,
          accepted_by: "dashboard",
          acceptance_decision: "accepted_for_cleanup_review",
          note: "V5.6-P12 metadata-only acceptance review"
        })
      }
    );
    await loadDataset2ManualEvidenceAcceptanceHistory();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 manual evidence acceptance failed";
    dataset2ManualEvidenceAcceptance.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2ManualEvidenceAcceptanceHistory() {
  try {
    dataset2ManualEvidenceAcceptanceHistory.value = await fetchJson<Dataset2ManualEvidenceAcceptance[]>(
      "/api/learning/dataset2/staging/cleanup-manual-evidence/acceptance-reviews?limit=5"
    );
    dataset2ManualEvidenceAcceptance.value =
      dataset2ManualEvidenceAcceptanceHistory.value[0] ?? dataset2ManualEvidenceAcceptance.value;
  } catch {
    dataset2ManualEvidenceAcceptanceHistory.value = [];
  }
}

async function reviewDataset2CleanupApplication() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2ManualEvidenceAcceptance.value?.event_id && !dataset2ManualEvidenceAcceptance.value?.id) {
      await loadDataset2ManualEvidenceAcceptanceHistory();
    }
    dataset2CleanupApplicationReview.value = await fetchJson<Dataset2CleanupApplicationReview>(
      "/api/learning/dataset2/staging/cleanup-application-review",
      {
        method: "POST",
        body: JSON.stringify({
          acceptance_review_id: dataset2ManualEvidenceAcceptance.value?.event_id ?? dataset2ManualEvidenceAcceptance.value?.id,
          reviewed_by: "dashboard",
          review_decision: "ready_for_future_cleanup_application",
          note: "V5.6-P12 metadata-only cleanup application review"
        })
      }
    );
    await loadDataset2CleanupApplicationReviews();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 cleanup application review failed";
    dataset2CleanupApplicationReview.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2CleanupApplicationReviews() {
  try {
    dataset2CleanupApplicationReviews.value = await fetchJson<Dataset2CleanupApplicationReview[]>(
      "/api/learning/dataset2/staging/cleanup-application-reviews?limit=5"
    );
    dataset2CleanupApplicationReview.value =
      dataset2CleanupApplicationReviews.value[0] ?? dataset2CleanupApplicationReview.value;
  } catch {
    dataset2CleanupApplicationReviews.value = [];
  }
}

async function planDataset2CleanupExecutionApproval() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2CleanupApplicationReview.value?.event_id && !dataset2CleanupApplicationReview.value?.id) {
      await loadDataset2CleanupApplicationReviews();
    }
    dataset2CleanupExecutionApprovalPlan.value = await fetchJson<Dataset2CleanupExecutionApprovalPlan>(
      "/api/learning/dataset2/staging/cleanup-execution-approval-plan",
      {
        method: "POST",
        body: JSON.stringify({
          cleanup_application_review_id: dataset2CleanupApplicationReview.value?.event_id ?? dataset2CleanupApplicationReview.value?.id,
          planned_by: "dashboard",
          plan_decision: "prepared_for_manual_approval",
          note: "V5.6-P12 metadata-only cleanup execution approval plan"
        })
      }
    );
    await loadDataset2CleanupExecutionApprovalPlans();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 cleanup execution approval plan failed";
    dataset2CleanupExecutionApprovalPlan.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2CleanupExecutionApprovalPlans() {
  try {
    dataset2CleanupExecutionApprovalPlans.value = await fetchJson<Dataset2CleanupExecutionApprovalPlan[]>(
      "/api/learning/dataset2/staging/cleanup-execution-approval-plans?limit=5"
    );
    dataset2CleanupExecutionApprovalPlan.value =
      dataset2CleanupExecutionApprovalPlans.value[0] ?? dataset2CleanupExecutionApprovalPlan.value;
  } catch {
    dataset2CleanupExecutionApprovalPlans.value = [];
  }
}

async function approveDataset2CleanupExecutionManually() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2CleanupExecutionApprovalPlan.value?.event_id && !dataset2CleanupExecutionApprovalPlan.value?.id) {
      await loadDataset2CleanupExecutionApprovalPlans();
    }
    dataset2CleanupExecutionManualApproval.value = await fetchJson<Dataset2CleanupExecutionManualApproval>(
      "/api/learning/dataset2/staging/cleanup-execution-manual-approval",
      {
        method: "POST",
        body: JSON.stringify({
          approval_plan_id:
            dataset2CleanupExecutionApprovalPlan.value?.event_id ?? dataset2CleanupExecutionApprovalPlan.value?.id,
          approved_by: "dashboard",
          approval_decision: "approved_for_cleanup_execution_preflight",
          note: "V5.6-P13 metadata-only manual cleanup execution approval"
        })
      }
    );
    await loadDataset2CleanupExecutionManualApprovals();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 manual cleanup execution approval failed";
    dataset2CleanupExecutionManualApproval.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2CleanupExecutionManualApprovals() {
  try {
    dataset2CleanupExecutionManualApprovals.value = await fetchJson<Dataset2CleanupExecutionManualApproval[]>(
      "/api/learning/dataset2/staging/cleanup-execution-manual-approvals?limit=5"
    );
    dataset2CleanupExecutionManualApproval.value =
      dataset2CleanupExecutionManualApprovals.value[0] ?? dataset2CleanupExecutionManualApproval.value;
  } catch {
    dataset2CleanupExecutionManualApprovals.value = [];
  }
}

async function preflightDataset2CleanupExecution() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2CleanupExecutionManualApproval.value?.event_id && !dataset2CleanupExecutionManualApproval.value?.id) {
      await loadDataset2CleanupExecutionManualApprovals();
    }
    dataset2CleanupExecutionPreflight.value = await fetchJson<Dataset2CleanupExecutionPreflight>(
      "/api/learning/dataset2/staging/cleanup-execution-preflight",
      {
        method: "POST",
        body: JSON.stringify({
          manual_approval_id:
            dataset2CleanupExecutionManualApproval.value?.event_id ?? dataset2CleanupExecutionManualApproval.value?.id,
          requested_by: "dashboard",
          preflight_decision: "prepared_for_cleanup_execution_dry_run",
          note: "V5.6-P14 metadata-only cleanup execution preflight"
        })
      }
    );
    await loadDataset2CleanupExecutionPreflights();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 cleanup execution preflight failed";
    dataset2CleanupExecutionPreflight.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2CleanupExecutionPreflights() {
  try {
    dataset2CleanupExecutionPreflights.value = await fetchJson<Dataset2CleanupExecutionPreflight[]>(
      "/api/learning/dataset2/staging/cleanup-execution-preflights?limit=5"
    );
    dataset2CleanupExecutionPreflight.value =
      dataset2CleanupExecutionPreflights.value[0] ?? dataset2CleanupExecutionPreflight.value;
  } catch {
    dataset2CleanupExecutionPreflights.value = [];
  }
}

async function dryRunDataset2CleanupExecution() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2CleanupExecutionPreflight.value?.event_id && !dataset2CleanupExecutionPreflight.value?.id) {
      await loadDataset2CleanupExecutionPreflights();
    }
    dataset2CleanupExecutionDryRun.value = await fetchJson<Dataset2CleanupExecutionDryRun>(
      "/api/learning/dataset2/staging/cleanup-execution-dry-run",
      {
        method: "POST",
        body: JSON.stringify({
          preflight_id: dataset2CleanupExecutionPreflight.value?.event_id ?? dataset2CleanupExecutionPreflight.value?.id,
          simulated_by: "dashboard",
          dry_run_decision: "simulated_for_manual_review",
          note: "V5.6-P15 aggregate-only cleanup execution dry-run"
        })
      }
    );
    await loadDataset2CleanupExecutionDryRuns();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 cleanup execution dry-run failed";
    dataset2CleanupExecutionDryRun.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2CleanupExecutionDryRuns() {
  try {
    dataset2CleanupExecutionDryRuns.value = await fetchJson<Dataset2CleanupExecutionDryRun[]>(
      "/api/learning/dataset2/staging/cleanup-execution-dry-runs?limit=5"
    );
    dataset2CleanupExecutionDryRun.value =
      dataset2CleanupExecutionDryRuns.value[0] ?? dataset2CleanupExecutionDryRun.value;
  } catch {
    dataset2CleanupExecutionDryRuns.value = [];
  }
}

async function reviewDataset2CleanupExecutionDryRun() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2CleanupExecutionDryRun.value?.event_id && !dataset2CleanupExecutionDryRun.value?.id) {
      await loadDataset2CleanupExecutionDryRuns();
    }
    dataset2CleanupExecutionDryRunReview.value = await fetchJson<Dataset2CleanupExecutionDryRunReview>(
      "/api/learning/dataset2/staging/cleanup-execution-dry-run-review",
      {
        method: "POST",
        body: JSON.stringify({
          dry_run_id: dataset2CleanupExecutionDryRun.value?.event_id ?? dataset2CleanupExecutionDryRun.value?.id,
          reviewed_by: "dashboard",
          review_decision: "approved_for_cleanup_execution_plan",
          note: "V5.6-P16 metadata-only dry-run manual review gate"
        })
      }
    );
    await loadDataset2CleanupExecutionDryRunReviews();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 cleanup execution dry-run review failed";
    dataset2CleanupExecutionDryRunReview.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2CleanupExecutionDryRunReviews() {
  try {
    dataset2CleanupExecutionDryRunReviews.value = await fetchJson<Dataset2CleanupExecutionDryRunReview[]>(
      "/api/learning/dataset2/staging/cleanup-execution-dry-run-reviews?limit=5"
    );
    dataset2CleanupExecutionDryRunReview.value =
      dataset2CleanupExecutionDryRunReviews.value[0] ?? dataset2CleanupExecutionDryRunReview.value;
  } catch {
    dataset2CleanupExecutionDryRunReviews.value = [];
  }
}

async function planDataset2CleanupExecution() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2CleanupExecutionDryRunReview.value?.event_id && !dataset2CleanupExecutionDryRunReview.value?.id) {
      await loadDataset2CleanupExecutionDryRunReviews();
    }
    dataset2CleanupExecutionPlan.value = await fetchJson<Dataset2CleanupExecutionPlan>(
      "/api/learning/dataset2/staging/cleanup-execution-plan",
      {
        method: "POST",
        body: JSON.stringify({
          dry_run_review_id:
            dataset2CleanupExecutionDryRunReview.value?.event_id ?? dataset2CleanupExecutionDryRunReview.value?.id,
          planned_by: "dashboard",
          plan_decision: "prepared_for_controlled_cleanup_execution_preflight",
          note: "V5.6-P17 metadata-only controlled cleanup execution plan"
        })
      }
    );
    await loadDataset2CleanupExecutionPlans();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 cleanup execution plan failed";
    dataset2CleanupExecutionPlan.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2CleanupExecutionPlans() {
  try {
    dataset2CleanupExecutionPlans.value = await fetchJson<Dataset2CleanupExecutionPlan[]>(
      "/api/learning/dataset2/staging/cleanup-execution-plans?limit=5"
    );
    dataset2CleanupExecutionPlan.value =
      dataset2CleanupExecutionPlans.value[0] ?? dataset2CleanupExecutionPlan.value;
  } catch {
    dataset2CleanupExecutionPlans.value = [];
  }
}

async function preflightDataset2CleanupExecutionPlan() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2CleanupExecutionPlan.value?.event_id && !dataset2CleanupExecutionPlan.value?.id) {
      await loadDataset2CleanupExecutionPlans();
    }
    dataset2CleanupExecutionPlanPreflight.value = await fetchJson<Dataset2CleanupExecutionPlanPreflight>(
      "/api/learning/dataset2/staging/cleanup-execution-plan/preflight",
      {
        method: "POST",
        body: JSON.stringify({
          execution_plan_id:
            dataset2CleanupExecutionPlan.value?.event_id ?? dataset2CleanupExecutionPlan.value?.id,
          requested_by: "dashboard",
          preflight_decision: "prepared_for_controlled_cleanup_execution_dry_run",
          note: "V5.6-P18 metadata-only controlled cleanup execution preflight"
        })
      }
    );
    await loadDataset2CleanupExecutionPlanPreflights();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 cleanup execution plan preflight failed";
    dataset2CleanupExecutionPlanPreflight.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2CleanupExecutionPlanPreflights() {
  try {
    dataset2CleanupExecutionPlanPreflights.value = await fetchJson<Dataset2CleanupExecutionPlanPreflight[]>(
      "/api/learning/dataset2/staging/cleanup-execution-plan/preflights?limit=5"
    );
    dataset2CleanupExecutionPlanPreflight.value =
      dataset2CleanupExecutionPlanPreflights.value[0] ?? dataset2CleanupExecutionPlanPreflight.value;
  } catch {
    dataset2CleanupExecutionPlanPreflights.value = [];
  }
}

async function dryRunDataset2ControlledCleanup() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2CleanupExecutionPlanPreflight.value?.event_id && !dataset2CleanupExecutionPlanPreflight.value?.id) {
      await loadDataset2CleanupExecutionPlanPreflights();
    }
    dataset2ControlledCleanupDryRun.value = await fetchJson<Dataset2ControlledCleanupDryRun>(
      "/api/learning/dataset2/staging/cleanup-execution-controlled-dry-run",
      {
        method: "POST",
        body: JSON.stringify({
          plan_preflight_id:
            dataset2CleanupExecutionPlanPreflight.value?.event_id ?? dataset2CleanupExecutionPlanPreflight.value?.id,
          simulated_by: "dashboard",
          dry_run_decision: "simulated_for_controlled_cleanup_review",
          note: "V5.6-P19 aggregate-only controlled cleanup dry-run"
        })
      }
    );
    await loadDataset2ControlledCleanupDryRuns();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 controlled cleanup dry-run failed";
    dataset2ControlledCleanupDryRun.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2ControlledCleanupDryRuns() {
  try {
    dataset2ControlledCleanupDryRuns.value = await fetchJson<Dataset2ControlledCleanupDryRun[]>(
      "/api/learning/dataset2/staging/cleanup-execution-controlled-dry-runs?limit=5"
    );
    dataset2ControlledCleanupDryRun.value =
      dataset2ControlledCleanupDryRuns.value[0] ?? dataset2ControlledCleanupDryRun.value;
  } catch {
    dataset2ControlledCleanupDryRuns.value = [];
  }
}

async function reviewDataset2ControlledCleanupDryRun() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2ControlledCleanupDryRun.value?.event_id && !dataset2ControlledCleanupDryRun.value?.id) {
      await loadDataset2ControlledCleanupDryRuns();
    }
    dataset2ControlledCleanupDryRunReview.value = await fetchJson<Dataset2ControlledCleanupDryRunReview>(
      "/api/learning/dataset2/staging/cleanup-execution-controlled-dry-run-review",
      {
        method: "POST",
        body: JSON.stringify({
          controlled_dry_run_id:
            dataset2ControlledCleanupDryRun.value?.event_id ?? dataset2ControlledCleanupDryRun.value?.id,
          reviewed_by: "dashboard",
          review_decision: "approved_for_controlled_cleanup_execution_review",
          note: "V5.6-P20 metadata-only controlled cleanup dry-run review"
        })
      }
    );
    await loadDataset2ControlledCleanupDryRunReviews();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 controlled cleanup dry-run review failed";
    dataset2ControlledCleanupDryRunReview.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2ControlledCleanupDryRunReviews() {
  try {
    dataset2ControlledCleanupDryRunReviews.value = await fetchJson<Dataset2ControlledCleanupDryRunReview[]>(
      "/api/learning/dataset2/staging/cleanup-execution-controlled-dry-run-reviews?limit=5"
    );
    dataset2ControlledCleanupDryRunReview.value =
      dataset2ControlledCleanupDryRunReviews.value[0] ?? dataset2ControlledCleanupDryRunReview.value;
  } catch {
    dataset2ControlledCleanupDryRunReviews.value = [];
  }
}

async function approveDataset2ControlledCleanup() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2ControlledCleanupDryRunReview.value?.event_id && !dataset2ControlledCleanupDryRunReview.value?.id) {
      await loadDataset2ControlledCleanupDryRunReviews();
    }
    dataset2ControlledCleanupApproval.value = await fetchJson<Dataset2ControlledCleanupApproval>(
      "/api/learning/dataset2/staging/cleanup-execution-controlled-approval",
      {
        method: "POST",
        body: JSON.stringify({
          controlled_review_id:
            dataset2ControlledCleanupDryRunReview.value?.event_id ?? dataset2ControlledCleanupDryRunReview.value?.id,
          approved_by: "dashboard",
          approval_decision: "approved_for_controlled_cleanup_execution_preflight",
          note: "V5.6-P21 metadata-only controlled cleanup execution approval"
        })
      }
    );
    await loadDataset2ControlledCleanupApprovals();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 controlled cleanup approval failed";
    dataset2ControlledCleanupApproval.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2ControlledCleanupApprovals() {
  try {
    dataset2ControlledCleanupApprovals.value = await fetchJson<Dataset2ControlledCleanupApproval[]>(
      "/api/learning/dataset2/staging/cleanup-execution-controlled-approvals?limit=5"
    );
    dataset2ControlledCleanupApproval.value =
      dataset2ControlledCleanupApprovals.value[0] ?? dataset2ControlledCleanupApproval.value;
  } catch {
    dataset2ControlledCleanupApprovals.value = [];
  }
}

async function preflightDataset2ControlledCleanup() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2ControlledCleanupApproval.value?.event_id && !dataset2ControlledCleanupApproval.value?.id) {
      await loadDataset2ControlledCleanupApprovals();
    }
    dataset2ControlledCleanupPreflight.value = await fetchJson<Dataset2ControlledCleanupPreflight>(
      "/api/learning/dataset2/staging/cleanup-execution-controlled-preflight",
      {
        method: "POST",
        body: JSON.stringify({
          controlled_approval_id:
            dataset2ControlledCleanupApproval.value?.event_id ?? dataset2ControlledCleanupApproval.value?.id,
          requested_by: "dashboard",
          preflight_decision: "prepared_for_controlled_cleanup_execution_apply_dry_run",
          note: "V5.6-P22 metadata-only controlled cleanup execution preflight"
        })
      }
    );
    await loadDataset2ControlledCleanupPreflights();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 controlled cleanup preflight failed";
    dataset2ControlledCleanupPreflight.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2ControlledCleanupPreflights() {
  try {
    dataset2ControlledCleanupPreflights.value = await fetchJson<Dataset2ControlledCleanupPreflight[]>(
      "/api/learning/dataset2/staging/cleanup-execution-controlled-preflights?limit=5"
    );
    dataset2ControlledCleanupPreflight.value =
      dataset2ControlledCleanupPreflights.value[0] ?? dataset2ControlledCleanupPreflight.value;
  } catch {
    dataset2ControlledCleanupPreflights.value = [];
  }
}

async function dryRunDataset2ControlledCleanupApply() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2ControlledCleanupPreflight.value?.event_id && !dataset2ControlledCleanupPreflight.value?.id) {
      await loadDataset2ControlledCleanupPreflights();
    }
    dataset2ControlledCleanupApplyDryRun.value = await fetchJson<Dataset2ControlledCleanupApplyDryRun>(
      "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-dry-run",
      {
        method: "POST",
        body: JSON.stringify({
          controlled_preflight_id:
            dataset2ControlledCleanupPreflight.value?.event_id ?? dataset2ControlledCleanupPreflight.value?.id,
          simulated_by: "dashboard",
          dry_run_decision: "simulated_for_controlled_cleanup_apply_review",
          note: "V5.6-P23 aggregate-only controlled cleanup apply dry-run"
        })
      }
    );
    await loadDataset2ControlledCleanupApplyDryRuns();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 controlled cleanup apply dry-run failed";
    dataset2ControlledCleanupApplyDryRun.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2ControlledCleanupApplyDryRuns() {
  try {
    dataset2ControlledCleanupApplyDryRuns.value = await fetchJson<Dataset2ControlledCleanupApplyDryRun[]>(
      "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-dry-runs?limit=5"
    );
    dataset2ControlledCleanupApplyDryRun.value =
      dataset2ControlledCleanupApplyDryRuns.value[0] ?? dataset2ControlledCleanupApplyDryRun.value;
  } catch {
    dataset2ControlledCleanupApplyDryRuns.value = [];
  }
}

async function reviewDataset2ControlledCleanupApplyDryRun() {
  dataset2Loading.value = true;
  error.value = "";
  try {
    if (!dataset2ControlledCleanupApplyDryRun.value?.event_id && !dataset2ControlledCleanupApplyDryRun.value?.id) {
      await loadDataset2ControlledCleanupApplyDryRuns();
    }
    dataset2ControlledCleanupApplyDryRunReview.value = await fetchJson<Dataset2ControlledCleanupApplyDryRunReview>(
      "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-dry-run-review",
      {
        method: "POST",
        body: JSON.stringify({
          apply_dry_run_id:
            dataset2ControlledCleanupApplyDryRun.value?.event_id ?? dataset2ControlledCleanupApplyDryRun.value?.id,
          reviewed_by: "dashboard",
          review_decision: "approved_for_controlled_cleanup_apply_execution_review",
          note: "V5.6-P24 metadata-only controlled cleanup apply dry-run review"
        })
      }
    );
    await loadDataset2ControlledCleanupApplyDryRunReviews();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Dataset2 controlled cleanup apply dry-run review failed";
    dataset2ControlledCleanupApplyDryRunReview.value = null;
  } finally {
    dataset2Loading.value = false;
  }
}

async function loadDataset2ControlledCleanupApplyDryRunReviews() {
  try {
    dataset2ControlledCleanupApplyDryRunReviews.value = await fetchJson<Dataset2ControlledCleanupApplyDryRunReview[]>(
      "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-dry-run-reviews?limit=5"
    );
    dataset2ControlledCleanupApplyDryRunReview.value =
      dataset2ControlledCleanupApplyDryRunReviews.value[0] ?? dataset2ControlledCleanupApplyDryRunReview.value;
  } catch {
    dataset2ControlledCleanupApplyDryRunReviews.value = [];
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

async function loadTradeExecutionGateway() {
  tradeGatewayLoading.value = true;
  error.value = "";
  try {
    const [
      capabilitiesData,
      gatesData,
      manualContractData,
      auditSchemaData,
      riskContractData,
      rollbackRunbookData,
      preLivePackageData,
      acceptanceChecklistData,
      releaseGateData,
      finalReportData,
      brokerThreatModelData,
      brokerInterfaceDraftData,
      brokerContractVerificationData,
      orderFailureFixturesData,
      orderRunbookMappingData,
      auditStoragePlanData,
      auditMigrationSpecVerificationData,
      auditMigrationSpecApprovalsData,
      auditMigrationReleaseReadinessData,
      auditMigrationApprovalReviewData,
      auditMigrationReleasePackageData,
      auditMigrationPackageIntegrityData,
      auditMigrationReleaseRehearsalData,
      auditMigrationEvidenceVerificationData,
      auditMigrationEvidenceComparisonData,
      auditMigrationHealthDigestData,
      auditMigrationHealthDigestHistoryData,
      auditMigrationHealthDigestHistoryChecklistData,
      auditMigrationHealthDigestHistorySpecData,
      auditMigrationHealthDigestHistorySpecApprovalData,
      auditMigrationHealthDigestHistorySpecApprovalsData,
      auditMigrationHealthDigestHistoryReleaseReadinessData,
      auditMigrationHealthDigestHistoryApprovalReviewData,
      auditMigrationHealthDigestHistoryReleasePackageData,
      auditMigrationHealthDigestHistoryPackageIntegrityData,
      auditMigrationHealthDigestHistoryReleaseRehearsalData,
      auditMigrationHealthDigestHistoryReleaseEvidenceData,
      auditMigrationHealthDigestHistoryReleaseEvidenceComparisonData,
      auditMigrationHealthDigestHistoryReleaseHealthDigestData
    ] = await Promise.all([
      fetchJson<TradeGatewayCapabilities>("/api/trade-execution-gateway/capabilities"),
      fetchJson<TradeGatewayReviewGates>("/api/trade-execution-gateway/review-gates"),
      fetchJson<TradeGatewayManualContract>("/api/trade-execution-gateway/manual-confirmation-contract"),
      fetchJson<TradeGatewayAuditSchema>("/api/trade-execution-gateway/audit-evidence-schema"),
      fetchJson<TradeGatewayRiskContract>("/api/trade-execution-gateway/risk-gate-contract"),
      fetchJson<TradeGatewayRollbackRunbook>("/api/trade-execution-gateway/rollback-runbook"),
      fetchJson<TradeGatewayPreLivePackage>("/api/trade-execution-gateway/pre-live-review-package"),
      fetchJson<TradeGatewayAcceptanceChecklist>("/api/trade-execution-gateway/operator-acceptance-checklist"),
      fetchJson<TradeGatewayReleaseGate>("/api/trade-execution-gateway/disabled-release-gate"),
      fetchJson<TradeGatewayFinalReport>("/api/trade-execution-gateway/final-readiness-report"),
      fetchJson<TradeGatewayBrokerThreatModel>("/api/trade-execution-gateway/broker-adapter-threat-model"),
      fetchJson<TradeGatewayBrokerInterfaceDraft>("/api/trade-execution-gateway/broker-adapter-interface-draft"),
      fetchJson<TradeGatewayBrokerContractVerification>("/api/trade-execution-gateway/broker-adapter-contract-verification"),
      fetchJson<TradeGatewayOrderFailureFixtures>("/api/trade-execution-gateway/order-lifecycle-failure-fixtures"),
      fetchJson<TradeGatewayOrderRunbookMapping>("/api/trade-execution-gateway/order-failure-runbook-mapping"),
      fetchJson<TradeGatewayAuditStoragePlan>("/api/trade-execution-gateway/audit-ledger-storage-plan"),
      fetchJson<TradeGatewayAuditMigrationSpecVerification>(
        "/api/trade-execution-gateway/audit-ledger-migration-spec/verify",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ spec_text: null })
        }
      ),
      fetchJson<TradeGatewayAuditMigrationSpecApproval[]>(
        "/api/trade-execution-gateway/audit-ledger-migration-spec/approvals?limit=10"
      ),
      fetchJson<TradeGatewayAuditMigrationReleaseReadiness>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-readiness?limit=10"
      ),
      fetchJson<TradeGatewayAuditMigrationApprovalReview>(
        "/api/trade-execution-gateway/audit-ledger-migration-approval-review?limit=10&max_age_days=7"
      ),
      fetchJson<TradeGatewayAuditMigrationReleasePackage>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-package?limit=10&max_age_days=7"
      ),
      fetchJson<TradeGatewayAuditMigrationReleasePackageIntegrityReview>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-package/integrity-review?limit=10&max_age_days=7&repeat_checks=2"
      ),
      fetchJson<TradeGatewayAuditMigrationManualReleaseRehearsal>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-review/rehearsal?limit=10&max_age_days=7&repeat_checks=2"
      ),
      fetchJson<TradeGatewayAuditMigrationManualReleaseEvidenceVerification>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/verify?limit=10&max_age_days=7&repeat_checks=2",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ evidence: {} })
        }
      ),
      fetchJson<TradeGatewayAuditMigrationManualReleaseEvidenceComparison>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/compare?limit=10&max_age_days=7&repeat_checks=2",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ baseline_evidence: {}, candidate_evidence: {} })
        }
      ),
      fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigest>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest?limit=10&max_age_days=7&repeat_checks=2",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ baseline_evidence: {}, candidate_evidence: {} })
        }
      ),
      fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryProposal>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-proposal?limit=10&max_age_days=7&repeat_checks=2",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ baseline_evidence: {}, candidate_evidence: {} })
        }
      ),
      fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryMigrationChecklist>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-checklist?limit=10&max_age_days=7&repeat_checks=2",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ baseline_evidence: {}, candidate_evidence: {} })
        }
      ),
      fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryMigrationSpecVerification>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-spec/verify?limit=10&max_age_days=7&repeat_checks=2",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ spec_text: null, baseline_evidence: {}, candidate_evidence: {} })
        }
      ),
      Promise.resolve(null as TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryMigrationSpecApproval | null),
      fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryMigrationSpecApproval[]>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-spec/approvals?limit=10"
      ),
      fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseReadiness>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-readiness?limit=10&max_age_days=7&repeat_checks=2"
      ),
      fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryApprovalReview>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-approval-review?limit=10&max_age_days=7&repeat_checks=2"
      ),
      fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleasePackage>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-package?limit=10&max_age_days=7&repeat_checks=2"
      ),
      fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryPackageIntegrityReview>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-package/integrity-review?limit=10&max_age_days=7&repeat_checks=2"
      ),
      fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseRehearsal>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-review/rehearsal?limit=10&max_age_days=7&repeat_checks=2"
      ),
      fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseEvidenceVerification>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-evidence/verify?limit=10&max_age_days=7&repeat_checks=2",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ evidence: {} })
        }
      ),
      fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseEvidenceComparison>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-evidence/compare?limit=10&max_age_days=7&repeat_checks=2",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ baseline_evidence: {}, candidate_evidence: {} })
        }
      ),
      fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseHealthDigest>(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-evidence/health-digest?limit=10&max_age_days=7&repeat_checks=2",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ baseline_evidence: {}, candidate_evidence: {} })
        }
      )
    ]);
    tradeGatewayCapabilities.value = capabilitiesData;
    tradeGatewayReviewGates.value = gatesData;
    tradeGatewayManualContract.value = manualContractData;
    tradeGatewayAuditSchema.value = auditSchemaData;
    tradeGatewayRiskContract.value = riskContractData;
    tradeGatewayRollbackRunbook.value = rollbackRunbookData;
    tradeGatewayPreLivePackage.value = preLivePackageData;
    tradeGatewayAcceptanceChecklist.value = acceptanceChecklistData;
    tradeGatewayReleaseGate.value = releaseGateData;
    tradeGatewayFinalReport.value = finalReportData;
    tradeGatewayBrokerThreatModel.value = brokerThreatModelData;
    tradeGatewayBrokerInterfaceDraft.value = brokerInterfaceDraftData;
    tradeGatewayBrokerContractVerification.value = brokerContractVerificationData;
    tradeGatewayOrderFailureFixtures.value = orderFailureFixturesData;
    tradeGatewayOrderRunbookMapping.value = orderRunbookMappingData;
    tradeGatewayAuditStoragePlan.value = auditStoragePlanData;
    tradeGatewayAuditMigrationSpecVerification.value = auditMigrationSpecVerificationData;
    tradeGatewayAuditMigrationSpecApprovals.value = auditMigrationSpecApprovalsData;
    tradeGatewayAuditMigrationReleaseReadiness.value = auditMigrationReleaseReadinessData;
    tradeGatewayAuditMigrationApprovalReview.value = auditMigrationApprovalReviewData;
    tradeGatewayAuditMigrationReleasePackage.value = auditMigrationReleasePackageData;
    tradeGatewayAuditMigrationPackageIntegrity.value = auditMigrationPackageIntegrityData;
    tradeGatewayAuditMigrationReleaseRehearsal.value = auditMigrationReleaseRehearsalData;
    tradeGatewayAuditMigrationEvidenceVerification.value = auditMigrationEvidenceVerificationData;
    tradeGatewayAuditMigrationEvidenceComparison.value = auditMigrationEvidenceComparisonData;
    tradeGatewayAuditMigrationHealthDigest.value = auditMigrationHealthDigestData;
    tradeGatewayAuditMigrationHealthDigestHistoryProposal.value = auditMigrationHealthDigestHistoryData;
    tradeGatewayAuditMigrationHealthDigestHistoryChecklist.value = auditMigrationHealthDigestHistoryChecklistData;
    tradeGatewayAuditMigrationHealthDigestHistorySpecVerification.value = auditMigrationHealthDigestHistorySpecData;
    tradeGatewayAuditMigrationHealthDigestHistorySpecApprovalResult.value = auditMigrationHealthDigestHistorySpecApprovalData;
    tradeGatewayAuditMigrationHealthDigestHistorySpecApprovals.value = auditMigrationHealthDigestHistorySpecApprovalsData;
    tradeGatewayAuditMigrationHealthDigestHistoryReleaseReadiness.value = auditMigrationHealthDigestHistoryReleaseReadinessData;
    tradeGatewayAuditMigrationHealthDigestHistoryApprovalReview.value = auditMigrationHealthDigestHistoryApprovalReviewData;
    tradeGatewayAuditMigrationHealthDigestHistoryReleasePackage.value = auditMigrationHealthDigestHistoryReleasePackageData;
    tradeGatewayAuditMigrationHealthDigestHistoryPackageIntegrity.value = auditMigrationHealthDigestHistoryPackageIntegrityData;
    tradeGatewayAuditMigrationHealthDigestHistoryReleaseRehearsal.value = auditMigrationHealthDigestHistoryReleaseRehearsalData;
    tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidence.value = auditMigrationHealthDigestHistoryReleaseEvidenceData;
    tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidenceComparison.value = auditMigrationHealthDigestHistoryReleaseEvidenceComparisonData;
    tradeGatewayAuditMigrationHealthDigestHistoryReleaseHealthDigest.value = auditMigrationHealthDigestHistoryReleaseHealthDigestData;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "交易执行网关门禁加载失败";
  } finally {
    tradeGatewayLoading.value = false;
  }
}

async function approveTradeGatewayAuditMigrationSpec() {
  tradeGatewayLoading.value = true;
  error.value = "";
  try {
    tradeGatewayAuditMigrationSpecApprovalResult.value = await fetchJson<TradeGatewayAuditMigrationSpecApproval>(
      "/api/trade-execution-gateway/audit-ledger-migration-spec/approve",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          spec_text: null,
          approved_by: "dashboard-operator",
          note: "verified audit ledger migration spec reviewed in dashboard"
        })
      }
    );
    tradeGatewayAuditMigrationSpecApprovals.value = await fetchJson<TradeGatewayAuditMigrationSpecApproval[]>(
      "/api/trade-execution-gateway/audit-ledger-migration-spec/approvals?limit=10"
    );
    tradeGatewayAuditMigrationReleaseReadiness.value = await fetchJson<TradeGatewayAuditMigrationReleaseReadiness>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-readiness?limit=10"
    );
    tradeGatewayAuditMigrationApprovalReview.value = await fetchJson<TradeGatewayAuditMigrationApprovalReview>(
      "/api/trade-execution-gateway/audit-ledger-migration-approval-review?limit=10&max_age_days=7"
    );
    tradeGatewayAuditMigrationReleasePackage.value = await fetchJson<TradeGatewayAuditMigrationReleasePackage>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-package?limit=10&max_age_days=7"
    );
    tradeGatewayAuditMigrationPackageIntegrity.value = await fetchJson<TradeGatewayAuditMigrationReleasePackageIntegrityReview>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-package/integrity-review?limit=10&max_age_days=7&repeat_checks=2"
    );
    tradeGatewayAuditMigrationReleaseRehearsal.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseRehearsal>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-review/rehearsal?limit=10&max_age_days=7&repeat_checks=2"
    );
    tradeGatewayAuditMigrationEvidenceVerification.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseEvidenceVerification>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/verify?limit=10&max_age_days=7&repeat_checks=2",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ evidence: {} })
      }
    );
    tradeGatewayAuditMigrationEvidenceComparison.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseEvidenceComparison>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/compare?limit=10&max_age_days=7&repeat_checks=2",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ baseline_evidence: {}, candidate_evidence: {} })
      }
    );
    tradeGatewayAuditMigrationHealthDigest.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigest>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest?limit=10&max_age_days=7&repeat_checks=2",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ baseline_evidence: {}, candidate_evidence: {} })
      }
    );
    tradeGatewayAuditMigrationHealthDigestHistoryProposal.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryProposal>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-proposal?limit=10&max_age_days=7&repeat_checks=2",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ baseline_evidence: {}, candidate_evidence: {} })
      }
    );
    tradeGatewayAuditMigrationHealthDigestHistoryChecklist.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryMigrationChecklist>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-checklist?limit=10&max_age_days=7&repeat_checks=2",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ baseline_evidence: {}, candidate_evidence: {} })
      }
    );
    tradeGatewayAuditMigrationHealthDigestHistorySpecVerification.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryMigrationSpecVerification>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-spec/verify?limit=10&max_age_days=7&repeat_checks=2",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ spec_text: null, baseline_evidence: {}, candidate_evidence: {} })
      }
    );
  } catch (err) {
    error.value = err instanceof Error ? err.message : "审计账本迁移规格审批元数据记录失败";
  } finally {
    tradeGatewayLoading.value = false;
  }
}

async function approveTradeGatewayHealthDigestHistoryMigrationSpec() {
  tradeGatewayLoading.value = true;
  error.value = "";
  try {
    tradeGatewayAuditMigrationHealthDigestHistorySpecApprovalResult.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryMigrationSpecApproval>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-spec/approve?limit=10&max_age_days=7&repeat_checks=2",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          spec_text: null,
          approved_by: "dashboard-operator",
          note: "verified manual release health digest history migration spec reviewed in dashboard",
          baseline_evidence: {},
          candidate_evidence: {}
        })
      }
    );
    tradeGatewayAuditMigrationHealthDigestHistorySpecApprovals.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryMigrationSpecApproval[]>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-spec/approvals?limit=10"
    );
    tradeGatewayAuditMigrationHealthDigestHistoryReleaseReadiness.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseReadiness>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-readiness?limit=10&max_age_days=7&repeat_checks=2"
    );
    tradeGatewayAuditMigrationHealthDigestHistoryApprovalReview.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryApprovalReview>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-approval-review?limit=10&max_age_days=7&repeat_checks=2"
    );
    tradeGatewayAuditMigrationHealthDigestHistoryReleasePackage.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleasePackage>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-package?limit=10&max_age_days=7&repeat_checks=2"
    );
    tradeGatewayAuditMigrationHealthDigestHistoryPackageIntegrity.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryPackageIntegrityReview>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-package/integrity-review?limit=10&max_age_days=7&repeat_checks=2"
    );
    tradeGatewayAuditMigrationHealthDigestHistoryReleaseRehearsal.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseRehearsal>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-review/rehearsal?limit=10&max_age_days=7&repeat_checks=2"
    );
    tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidence.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseEvidenceVerification>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-evidence/verify?limit=10&max_age_days=7&repeat_checks=2",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ evidence: {} })
      }
    );
    tradeGatewayAuditMigrationHealthDigestHistoryReleaseEvidenceComparison.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseEvidenceComparison>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-evidence/compare?limit=10&max_age_days=7&repeat_checks=2",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ baseline_evidence: {}, candidate_evidence: {} })
      }
    );
    tradeGatewayAuditMigrationHealthDigestHistoryReleaseHealthDigest.value = await fetchJson<TradeGatewayAuditMigrationManualReleaseHealthDigestHistoryReleaseHealthDigest>(
      "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-evidence/health-digest?limit=10&max_age_days=7&repeat_checks=2",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ baseline_evidence: {}, candidate_evidence: {} })
      }
    );
    tradeGatewayReviewGates.value = await fetchJson<TradeGatewayReviewGates>("/api/trade-execution-gateway/review-gates");
  } catch (err) {
    error.value = err instanceof Error ? err.message : "history migration spec approval failed";
  } finally {
    tradeGatewayLoading.value = false;
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
    const [
      capabilitiesData,
      schedulerPlanData,
      automationProposalData,
      healthData,
      snapshotData,
      eventsData,
      cycleRunsData
    ] = await Promise.all([
      fetchJson<RealtimeCapabilities>("/api/realtime/capabilities"),
      fetchJson<RealtimeSchedulerPlan>("/api/realtime/scheduler-plan"),
      fetchJson<RealtimeAutomationProposal>("/api/realtime/automation-proposal"),
      fetchJson<RealtimeProviderHealth[]>("/api/realtime/provider-health"),
      fetchJson<RealtimeSnapshot>("/api/realtime/snapshot/SZ002081"),
      fetchJson<RealtimeEvent[]>("/api/realtime/events?limit=20"),
      fetchJson<RealtimeCycleRun[]>("/api/realtime/cycles?limit=10")
    ]);
    realtimeCapabilities.value = capabilitiesData;
    realtimeSchedulerPlan.value = schedulerPlanData;
    realtimeAutomationProposal.value = automationProposalData;
    realtimeHealth.value = healthData;
    realtimeSnapshot.value = snapshotData;
    realtimeEvents.value = eventsData;
    realtimeCycleRuns.value = cycleRunsData;
  } catch (err) {
    realtimeCapabilities.value = null;
    realtimeSchedulerPlan.value = null;
    realtimeAutomationProposal.value = null;
    realtimeHealth.value = [];
    realtimeSnapshot.value = null;
    realtimeEvents.value = [];
    realtimeCycleRuns.value = [];
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

async function loadScreenMonitoring() {
  screenMonitoringLoading.value = true;
  try {
    const [
      capabilitiesData,
      providersData,
      readinessData,
      sessionData,
      observationsData,
      artifactPolicyData,
      artifactReviewsData,
      providerConfigProposalsData,
      providerReplayRunsData,
      readinessAuditData,
      readinessAuditAcksData,
      readinessTimelineData,
      readinessExportData,
      readinessVerificationData,
      readinessComparisonData,
      readinessHealthData,
      digestHistoryProposalData,
      digestMigrationChecklistData,
      digestMigrationSpecApprovalsData,
      digestReleaseReadinessData,
      digestApprovalReviewData,
      digestReleasePackageData
    ] = await Promise.all([
      fetchJson<ScreenMonitoringCapabilities>("/api/screen-monitoring/capabilities"),
      fetchJson<ScreenProviderCapabilities[]>("/api/screen-monitoring/providers"),
      fetchJson<ScreenProviderReadiness>("/api/screen-monitoring/provider-readiness"),
      fetchJson<ScreenMonitoringSession>("/api/screen-monitoring/sessions/latest"),
      fetchJson<ScreenObservation[]>("/api/screen-monitoring/observations?limit=20"),
      fetchJson<ScreenArtifactPolicy>("/api/screen-monitoring/artifact-policy"),
      fetchJson<ScreenArtifactReview[]>("/api/screen-monitoring/artifact-reviews?limit=20"),
      fetchJson<ScreenProviderConfigProposal[]>("/api/screen-monitoring/provider-config-proposals?limit=20"),
      fetchJson<ScreenProviderReplayRun[]>("/api/screen-monitoring/provider-replay?limit=20"),
      fetchJson<ScreenReadinessAuditReport>("/api/screen-monitoring/readiness-audit?limit=20"),
      fetchJson<ScreenReadinessAuditAck[]>("/api/screen-monitoring/readiness-audit/acknowledgements?limit=20"),
      fetchJson<ScreenReadinessTimeline>("/api/screen-monitoring/readiness-timeline?limit=40"),
      fetchJson<ScreenReadinessEvidenceExport>("/api/screen-monitoring/readiness-export?limit=40"),
      fetchJson<ScreenReadinessVerification>("/api/screen-monitoring/readiness-export/verify?limit=40"),
      fetchJson<ScreenReadinessComparison>("/api/screen-monitoring/readiness-export/compare?limit=40"),
      fetchJson<ScreenReadinessHealth>("/api/screen-monitoring/readiness-health?limit=40"),
      fetchJson<ScreenDigestHistoryProposal>("/api/screen-monitoring/readiness-health/history-proposal?limit=40"),
      fetchJson<ScreenDigestMigrationChecklist>("/api/screen-monitoring/readiness-health/history-migration-checklist?limit=40"),
      fetchJson<ScreenDigestMigrationSpecApproval[]>("/api/screen-monitoring/readiness-health/history-migration-spec/approvals?limit=10"),
      fetchJson<ScreenDigestReleaseReadiness>("/api/screen-monitoring/readiness-health/history-migration-release-readiness?limit=40"),
      fetchJson<ScreenDigestApprovalReview>("/api/screen-monitoring/readiness-health/history-migration-approval-review?limit=40&max_age_days=7"),
      fetchJson<ScreenDigestReleasePackage>("/api/screen-monitoring/readiness-health/history-migration-release-package?limit=40&max_age_days=7")
    ]);
    screenMonitoringCapabilities.value = capabilitiesData;
    screenMonitoringProviders.value = providersData;
    screenProviderReadiness.value = readinessData;
    screenMonitoringSession.value = sessionData;
    screenObservations.value = observationsData;
    screenArtifactPolicy.value = artifactPolicyData;
    screenArtifactReviews.value = artifactReviewsData;
    screenProviderConfigProposals.value = providerConfigProposalsData;
    screenProviderReplayRuns.value = providerReplayRunsData;
    screenReadinessAudit.value = readinessAuditData;
    screenReadinessAuditAcks.value = readinessAuditAcksData;
    screenReadinessTimeline.value = readinessTimelineData;
    screenReadinessExport.value = readinessExportData;
    screenReadinessVerification.value = readinessVerificationData;
    screenReadinessComparison.value = readinessComparisonData;
    screenReadinessHealth.value = readinessHealthData;
    screenDigestHistoryProposal.value = digestHistoryProposalData;
    screenDigestMigrationChecklist.value = digestMigrationChecklistData;
    screenDigestMigrationSpecApprovals.value = digestMigrationSpecApprovalsData;
    screenDigestReleaseReadiness.value = digestReleaseReadinessData;
    screenDigestApprovalReview.value = digestApprovalReviewData;
    screenDigestReleasePackage.value = digestReleasePackageData;
  } catch (err) {
    screenMonitoringCapabilities.value = null;
    screenMonitoringProviders.value = [];
    screenProviderReadiness.value = null;
    screenMonitoringSession.value = null;
    screenObservations.value = [];
    screenArtifactPolicy.value = null;
    screenArtifactReviews.value = [];
    screenProviderConfigProposals.value = [];
    screenProviderReplayRuns.value = [];
    screenReadinessAudit.value = null;
    screenReadinessAuditAcks.value = [];
    screenReadinessTimeline.value = null;
    screenReadinessExport.value = null;
    screenReadinessVerification.value = null;
    screenReadinessComparison.value = null;
    screenReadinessHealth.value = null;
    screenDigestHistoryProposal.value = null;
    screenDigestMigrationChecklist.value = null;
    screenDigestMigrationSpecApprovals.value = [];
    screenDigestReleaseReadiness.value = null;
    screenDigestApprovalReview.value = null;
    screenDigestReleasePackage.value = null;
    error.value = err instanceof Error ? err.message : "屏幕只读监控状态加载失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function refreshScreenReadinessAudit() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenReadinessAudit.value = await fetchJson<ScreenReadinessAuditReport>(
      "/api/screen-monitoring/readiness-audit?limit=20"
    );
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Readiness audit 生成失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function acknowledgeScreenReadinessAudit() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenReadinessAuditAckResult.value = await fetchJson<ScreenReadinessAuditAck>(
      "/api/screen-monitoring/readiness-audit/acknowledge",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          acknowledged_by: "dashboard-operator",
          note: "readiness audit reviewed in dashboard"
        })
      }
    );
    await loadScreenMonitoring();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Readiness audit 确认失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function refreshScreenReadinessTimeline() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenReadinessTimeline.value = await fetchJson<ScreenReadinessTimeline>(
      "/api/screen-monitoring/readiness-timeline?limit=40"
    );
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Readiness timeline 刷新失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function refreshScreenReadinessExport() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenReadinessExport.value = await fetchJson<ScreenReadinessEvidenceExport>(
      "/api/screen-monitoring/readiness-export?limit=40"
    );
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Readiness evidence export 生成失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function verifyScreenReadinessExport() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenReadinessVerification.value = await fetchJson<ScreenReadinessVerification>(
      "/api/screen-monitoring/readiness-export/verify?limit=40"
    );
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Readiness evidence verifier 校验失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function compareScreenReadinessEvidence() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenReadinessComparison.value = await fetchJson<ScreenReadinessComparison>(
      "/api/screen-monitoring/readiness-export/compare?limit=40"
    );
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Readiness evidence comparison 对比失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function refreshScreenReadinessHealth() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenReadinessHealth.value = await fetchJson<ScreenReadinessHealth>(
      "/api/screen-monitoring/readiness-health?limit=40"
    );
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Readiness health digest 生成失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function refreshScreenDigestHistoryProposal() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenDigestHistoryProposal.value = await fetchJson<ScreenDigestHistoryProposal>(
      "/api/screen-monitoring/readiness-health/history-proposal?limit=40"
    );
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Digest history proposal 生成失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function refreshScreenDigestMigrationChecklist() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenDigestMigrationChecklist.value = await fetchJson<ScreenDigestMigrationChecklist>(
      "/api/screen-monitoring/readiness-health/history-migration-checklist?limit=40"
    );
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Digest history migration checklist 生成失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function verifyScreenDigestMigrationSpec() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenDigestMigrationSpecVerification.value = await fetchJson<ScreenDigestMigrationSpecVerification>(
      "/api/screen-monitoring/readiness-health/history-migration-spec/verify?limit=40",
      {
        method: "POST",
        body: JSON.stringify({ spec_text: null }),
        headers: { "Content-Type": "application/json" }
      }
    );
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Digest history migration spec 校验失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function approveScreenDigestMigrationSpec() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenDigestMigrationSpecApprovalResult.value = await fetchJson<ScreenDigestMigrationSpecApproval>(
      "/api/screen-monitoring/readiness-health/history-migration-spec/approve?limit=40",
      {
        method: "POST",
        body: JSON.stringify({
          spec_text: null,
          approved_by: "operator",
          note: "UI reviewed dry-run migration spec metadata"
        }),
        headers: { "Content-Type": "application/json" }
      }
    );
    screenDigestMigrationSpecApprovals.value = await fetchJson<ScreenDigestMigrationSpecApproval[]>(
      "/api/screen-monitoring/readiness-health/history-migration-spec/approvals?limit=10"
    );
    screenDigestReleaseReadiness.value = await fetchJson<ScreenDigestReleaseReadiness>(
      "/api/screen-monitoring/readiness-health/history-migration-release-readiness?limit=40"
    );
    screenDigestApprovalReview.value = await fetchJson<ScreenDigestApprovalReview>(
      "/api/screen-monitoring/readiness-health/history-migration-approval-review?limit=40&max_age_days=7"
    );
    screenDigestReleasePackage.value = await fetchJson<ScreenDigestReleasePackage>(
      "/api/screen-monitoring/readiness-health/history-migration-release-package?limit=40&max_age_days=7"
    );
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Digest history migration spec 审批记录失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function refreshScreenDigestReleaseReadiness() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenDigestReleaseReadiness.value = await fetchJson<ScreenDigestReleaseReadiness>(
      "/api/screen-monitoring/readiness-health/history-migration-release-readiness?limit=40"
    );
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Digest history release readiness 生成失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function refreshScreenDigestApprovalReview() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenDigestApprovalReview.value = await fetchJson<ScreenDigestApprovalReview>(
      "/api/screen-monitoring/readiness-health/history-migration-approval-review?limit=40&max_age_days=7"
    );
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Digest history approval review 生成失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function refreshScreenDigestReleasePackage() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenDigestReleasePackage.value = await fetchJson<ScreenDigestReleasePackage>(
      "/api/screen-monitoring/readiness-health/history-migration-release-package?limit=40&max_age_days=7"
    );
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Digest history release package 生成失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function replayScreenFixture() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenFixtureReplayResult.value = await fetchJson<ScreenFixtureReplayResult>(
      "/api/screen-monitoring/observations/fixture-replay",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fixture_name: "trading_client_online" })
      }
    );
    screenObservationResult.value = screenFixtureReplayResult.value.observation;
    await loadScreenMonitoring();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "屏幕 fixture 回放失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function runScreenCapturePreflight() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenPreflightResult.value = await fetchJson<ScreenPreflightResult>(
      "/api/screen-monitoring/capture-preflight",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_window_title: "Untitled - Notepad" })
      }
    );
    screenObservationResult.value = screenPreflightResult.value.observation;
    await loadScreenMonitoring();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "屏幕截图预检失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function runScreenCaptureStub() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenCaptureStubResult.value = await fetchJson<ScreenCaptureStubResult>(
      "/api/screen-monitoring/capture-stub",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_window_title: "Untitled - Notepad" })
      }
    );
    screenObservationResult.value = screenCaptureStubResult.value.observation;
    screenArtifactSyncResult.value = null;
    await loadScreenMonitoring();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "截图 artifact stub 生成失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function syncScreenArtifactReviews() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenArtifactSyncResult.value = await fetchJson<ScreenArtifactSyncResult>(
      "/api/screen-monitoring/artifact-reviews/sync?limit=100",
      { method: "POST" }
    );
    screenArtifactReviews.value = screenArtifactSyncResult.value.reviews;
    screenArtifactPolicy.value = screenArtifactSyncResult.value.policy;
    await loadScreenMonitoring();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Artifact 复核队列同步失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function approveScreenArtifactReview(id: number) {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    await fetchJson<ScreenArtifactReview>(`/api/screen-monitoring/artifact-reviews/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewed_by: "operator", note: "Metadata accepted from dashboard" })
    });
    await loadScreenMonitoring();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Artifact 复核接受失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function rejectScreenArtifactReview(id: number) {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    await fetchJson<ScreenArtifactReview>(`/api/screen-monitoring/artifact-reviews/${id}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewed_by: "operator", note: "Metadata rejected from dashboard" })
    });
    await loadScreenMonitoring();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Artifact 复核拒绝失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function generateScreenProviderConfigProposal() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenProviderConfigProposalResult.value = await fetchJson<ScreenProviderConfigProposal>(
      "/api/screen-monitoring/provider-config-proposals",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_window_title: "Untitled - Notepad" })
      }
    );
    await loadScreenMonitoring();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "local-safe 配置提案生成失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function approveScreenProviderConfigProposal(id: number) {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    await fetchJson<ScreenProviderConfigProposal>(`/api/screen-monitoring/provider-config-proposals/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewed_by: "operator", note: "Config proposal accepted from dashboard; not applied by API" })
    });
    await loadScreenMonitoring();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "local-safe 配置提案接受失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function rejectScreenProviderConfigProposal(id: number) {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    await fetchJson<ScreenProviderConfigProposal>(`/api/screen-monitoring/provider-config-proposals/${id}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewed_by: "operator", note: "Config proposal rejected from dashboard" })
    });
    await loadScreenMonitoring();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "local-safe 配置提案拒绝失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function runScreenProviderReplay() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    const proposalId = screenProviderConfigProposals.value[0]?.id ?? null;
    screenProviderReplayResult.value = await fetchJson<ScreenProviderReplayRun>(
      "/api/screen-monitoring/provider-replay",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ proposal_id: proposalId, scenario_name: "dashboard_provider_readiness_replay" })
      }
    );
    await loadScreenMonitoring();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Provider replay 运行失败";
  } finally {
    screenMonitoringLoading.value = false;
  }
}

async function recordMockScreenObservation() {
  screenMonitoringLoading.value = true;
  error.value = "";
  try {
    screenObservationResult.value = await fetchJson<ScreenObservation>("/api/screen-monitoring/observations/mock", {
      method: "POST"
    });
    await loadScreenMonitoring();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "屏幕只读观测记录失败";
  } finally {
    screenMonitoringLoading.value = false;
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
    loadDataset2Readiness(),
    loadDataset2ImportQueueReviews(),
    loadDataset2Staging(),
    loadDataset2StagingQualityReviews(),
    loadDataset2StagingFixPlans(),
    loadDataset2StagingFixApprovals(),
    loadDataset2StagingFixPreflights(),
    loadDataset2CleanupExecutionSpecs(),
    loadDataset2CleanupDryRuns(),
    loadDataset2ManualEvidenceHistory(),
    loadDataset2ManualEvidenceAcceptanceHistory(),
    loadDataset2CleanupApplicationReviews(),
    loadDataset2CleanupExecutionApprovalPlans(),
    loadDataset2CleanupExecutionManualApprovals(),
    loadDataset2CleanupExecutionPreflights(),
    loadDataset2CleanupExecutionDryRuns(),
    loadDataset2CleanupExecutionDryRunReviews(),
    loadDataset2CleanupExecutionPlans(),
    loadDataset2CleanupExecutionPlanPreflights(),
    loadDataset2ControlledCleanupDryRuns(),
    loadDataset2ControlledCleanupDryRunReviews(),
    loadDataset2ControlledCleanupApprovals(),
    loadDataset2ControlledCleanupPreflights(),
    loadDataset2ControlledCleanupApplyDryRuns(),
    loadDataset2ControlledCleanupApplyDryRunReviews(),
    loadMonitoring(),
    loadMonitoringReview(),
    loadPhaseReplay(),
    loadPhaseMatch(),
    loadPotentialSearch(),
    loadAgentCapabilities(),
    loadTradeExecutionGateway(),
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
    loadScreenMonitoring(),
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
