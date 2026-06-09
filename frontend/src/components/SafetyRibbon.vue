<template>
  <aside class="safety-ribbon" aria-label="Safety status">
    <div>
      <span class="label">Safety</span>
      <strong>{{ liveTradingEnabled ? "Live Trading Enabled" : "Simulation Only" }}</strong>
    </div>
    <p>{{ statusText }}</p>
  </aside>
</template>

<script setup lang="ts">
defineProps<{
  statusText: string;
  liveTradingEnabled?: boolean;
}>();
</script>

<style scoped>
.safety-ribbon {
  display: grid;
  gap: 8px;
  min-width: 220px;
  padding: 12px 14px;
  border: 1px solid rgba(22, 101, 52, 0.18);
  border-radius: 8px;
  background: #f0fdf4;
  color: #14532d;
}

.label {
  display: block;
  margin-bottom: 2px;
  color: #46745a;
  font-size: 12px;
  text-transform: uppercase;
}

strong,
p {
  margin: 0;
}

p {
  color: #3d5f4a;
  font-size: 13px;
  line-height: 1.45;
}
</style>
