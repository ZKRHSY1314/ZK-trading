import { onMounted, onUnmounted, ref } from "vue";

import {
  fetchControlPlaneStatus,
  fetchReadiness,
  type ControlPlaneStatusSnapshot,
  type ReadinessSnapshot,
} from "../api/cockpit";

const DEFAULT_POLL_INTERVAL_MS = 30_000;

export function useCockpitObservability(pollIntervalMs = DEFAULT_POLL_INTERVAL_MS) {
  const readiness = ref<ReadinessSnapshot | null>(null);
  const controlPlane = ref<ControlPlaneStatusSnapshot | null>(null);
  const loading = ref(true);
  const error = ref("");
  const lastRefreshedAt = ref<string | null>(null);

  let timer: ReturnType<typeof setInterval> | null = null;
  let controller: AbortController | null = null;
  let refreshInFlight = false;
  let refreshGeneration = 0;

  async function refresh() {
    if (refreshInFlight || (typeof document !== "undefined" && document.hidden)) return;
    refreshInFlight = true;
    const generation = ++refreshGeneration;
    loading.value = readiness.value === null && controlPlane.value === null;
    error.value = "";
    controller?.abort();
    const activeController = new AbortController();
    controller = activeController;

    const results = await Promise.allSettled([
      fetchReadiness(activeController.signal),
      fetchControlPlaneStatus(activeController.signal),
    ]);

    if (generation !== refreshGeneration) return;

    const failures: string[] = [];
    const readinessResult = results[0];
    const controlResult = results[1];
    if (readinessResult.status === "fulfilled") {
      readiness.value = readinessResult.value;
    } else if (readinessResult.reason?.name !== "AbortError") {
      failures.push(`运行心跳：${errorMessage(readinessResult.reason)}`);
    }
    if (controlResult.status === "fulfilled") {
      controlPlane.value = controlResult.value;
    } else if (controlResult.reason?.name !== "AbortError") {
      failures.push(`控制面：${errorMessage(controlResult.reason)}`);
    }

    if (results.some((result) => result.status === "fulfilled")) {
      lastRefreshedAt.value = new Date().toISOString();
    }
    error.value = failures.join("；");
    loading.value = false;
    refreshInFlight = false;
  }

  function stopPolling() {
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
  }

  function startPolling() {
    stopPolling();
    if (typeof document !== "undefined" && document.hidden) return;
    timer = setInterval(() => void refresh(), Math.max(5_000, pollIntervalMs));
  }

  function handleVisibilityChange() {
    if (document.hidden) {
      stopPolling();
      refreshGeneration += 1;
      refreshInFlight = false;
      controller?.abort();
      return;
    }
    void refresh();
    startPolling();
  }

  onMounted(() => {
    document.addEventListener("visibilitychange", handleVisibilityChange);
    void refresh();
    startPolling();
  });

  onUnmounted(() => {
    document.removeEventListener("visibilitychange", handleVisibilityChange);
    stopPolling();
    refreshGeneration += 1;
    refreshInFlight = false;
    controller?.abort();
  });

  return {
    readiness,
    controlPlane,
    loading,
    error,
    lastRefreshedAt,
    refresh,
  };
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
