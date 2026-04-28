<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import * as videosApi from "@/api/videos";
import type { VideoListItem } from "@/api/videos";
import * as algorithmApi from "@/api/algorithmReset";
import { formatApiError } from "@/util/errors";
import { resolveApiAssetUrl } from "@/util/resolveApiAssetUrl";
import { useAuthStore } from "@/stores/auth";
import { useAlgorithmStore } from "@/stores/algorithm";

const auth = useAuthStore();
const algorithm = useAlgorithmStore();
const loading = ref(true);
const trending = ref<VideoListItem[]>([]);
const searchQ = ref("");
const modePanelOpen = ref(false);
const modeSaving = ref(false);
const attentionIndex = ref<number | null>(null);
const attentionDetail = ref<{
  timeQuality: number;
  informationValue: number;
  propagationImpact: number;
  deepEngagement: number;
  explanation: string;
} | null>(null);
const aiSummary = ref("");
const aiAgent = ref<algorithmApi.AiAgentPanel | null>(null);
const governancePower = ref<number | null>(null);
const presets = ref<algorithmApi.AlgorithmPreset[]>([]);

const customParams = reactive<algorithmApi.AlgorithmParameters>({
  randomness: 50,
  diversity: 70,
  depth: 50,
  entertainment: 50,
  challenge: 50,
  novelty: 60,
});

const modeOptions = [
  { key: "origin", title: "归源模式", desc: "完全随机、无画像、多样性最大" },
  { key: "efficiency", title: "效率模式", desc: "快速获取高密度、高价值内容" },
  { key: "growth", title: "成长模式", desc: "反舒适区，挑战认知边界" },
  { key: "emotion", title: "情绪模式", desc: "放松、娱乐、沉浸，但可控" },
  { key: "custom", title: "自定义模式", desc: "训练自己的世界模型" },
] as const;

const activeModeTitle = computed(() => modeOptions.find((m) => m.key === algorithm.algorithmMode)?.title || "算法模式");
const worldModelSummary = computed(() =>
  `随机 ${customParams.randomness} / 多样 ${customParams.diversity} / 深度 ${customParams.depth} / 娱乐 ${customParams.entertainment} / 挑战 ${customParams.challenge} / 新颖 ${customParams.novelty}`,
);

async function load() {
  loading.value = true;
  try {
    const tr = await videosApi.listTrendingVideos({ offset: 0, limit: 14 });
    trending.value = tr.items;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

async function chooseMode(mode: (typeof modeOptions)[number]["key"]) {
  if (!auth.isLoggedIn) {
    ElMessage.warning("请先登录后再切换算法模式");
    return;
  }
  modeSaving.value = true;
  try {
    const result = await algorithmApi.updateAlgorithmState({
      mode,
      parameters: mode === "custom" ? { ...customParams } : undefined,
    });
    algorithm.setState(result.data);
    Object.assign(customParams, result.data.parameters);
    ElMessage.success(result.message || "算法模式已更新");
    modePanelOpen.value = false;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    modeSaving.value = false;
  }
}

async function openModePanel() {
  modePanelOpen.value = true;
  if (!auth.isLoggedIn) return;
  try {
    const [attention, agent, governance, presetList, state] = await Promise.all([
      algorithmApi.getAttentionIndex(),
      algorithmApi.getAiAgentPanel(),
      algorithmApi.getGovernancePower(),
      algorithmApi.listAlgorithmPresets(),
      algorithmApi.getAlgorithmState(),
    ]);
    attentionIndex.value = attention.data.attentionIndex;
    attentionDetail.value = {
      timeQuality: attention.data.timeQuality,
      informationValue: attention.data.informationValue,
      propagationImpact: attention.data.propagationImpact,
      deepEngagement: attention.data.deepEngagement,
      explanation: attention.data.explanation,
    };
    aiSummary.value = agent.summary;
    aiAgent.value = agent;
    governancePower.value = governance.votingPower;
    presets.value = presetList.items;
    algorithm.setState(state.data);
    Object.assign(customParams, state.data.parameters);
  } catch {
    // 面板洞察是增强信息，失败时不阻塞模式切换。
  }
}

async function saveCurrentPreset() {
  if (!auth.isLoggedIn) {
    ElMessage.warning("请先登录后再保存世界模型");
    return;
  }
  modeSaving.value = true;
  try {
    const name = `世界模型 ${new Date().toLocaleDateString("zh-CN")}`;
    await algorithmApi.saveAlgorithmPreset({
      name,
      description: "从当前自定义参数保存",
      parameters: { ...customParams },
    });
    presets.value = (await algorithmApi.listAlgorithmPresets()).items;
    ElMessage.success("世界模型模板已保存");
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    modeSaving.value = false;
  }
}

async function applyPreset(id: string) {
  modeSaving.value = true;
  try {
    const result = await algorithmApi.applyAlgorithmPreset(id);
    algorithm.setState(result.data);
    Object.assign(customParams, result.data.parameters);
    ElMessage.success(result.message || "世界模型已应用");
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    modeSaving.value = false;
  }
}

async function resetDefaults() {
  modeSaving.value = true;
  try {
    const result = await algorithmApi.resetCustomDefaults();
    algorithm.setState(result.data);
    Object.assign(customParams, result.data.parameters);
    ElMessage.success(result.message || "已恢复默认参数");
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    modeSaving.value = false;
  }
}

onMounted(() => {
  void load();
});
</script>

<template>
  <div v-loading="loading" class="native-stack discover" :class="{ 'is-loading': loading }">
    <section class="discover-hero">
      <div class="discover-hero__glow" aria-hidden="true" />
      <div class="discover-hero__head">
        <h1>Discovery</h1>
        <button type="button" class="mode-chip" @click="openModePanel">
          <span>算法模式</span>
          <b>{{ activeModeTitle }}</b>
        </button>
      </div>
      <div class="search-row">
        <input id="disc-q" v-model="searchQ" class="discover-input" type="search" enterkeyhint="search" placeholder="关键词" />
        <RouterLink class="native-btn native-btn--primary search-go" :to="{ name: 'search', query: searchQ.trim() ? { q: searchQ.trim() } : {} }">
          搜索
        </RouterLink>
      </div>
    </section>

    <section class="native-card">
      <h2 class="section-title">趋势</h2>
      <div class="trend-grid">
        <RouterLink v-for="v in trending" :key="v.id" class="trend-tile" :to="{ name: 'video-detail', params: { id: v.id } }">
          <div class="trend-tile__thumb">
            <img
              v-if="resolveApiAssetUrl(v.cover_url)"
              :src="resolveApiAssetUrl(v.cover_url)"
              :alt="v.title ?? ''"
              loading="lazy"
            />
            <div v-else class="trend-tile__thumb trend-tile__thumb--ph" aria-hidden="true" />
          </div>
          <div class="trend-tile__cap">{{ v.title }}</div>
        </RouterLink>
      </div>
    </section>

    <Teleport to="body">
      <div v-if="modePanelOpen" class="mode-sheet-root" @click.self="modePanelOpen = false">
        <section class="mode-sheet" role="dialog" aria-modal="true" aria-label="算法模式">
          <div class="mode-sheet__head">
            <div>
              <p>透明算法控制面板</p>
              <h2>选择你的世界模型</h2>
            </div>
            <button type="button" @click="modePanelOpen = false">×</button>
          </div>
          <div class="mode-list">
            <button
              v-for="item in modeOptions"
              :key="item.key"
              type="button"
              class="mode-card"
              :class="{ on: algorithm.algorithmMode === item.key }"
              :disabled="modeSaving"
              @click="chooseMode(item.key)"
            >
              <b>{{ item.title }}</b>
              <span>{{ item.desc }}</span>
            </button>
          </div>
          <div class="insight-strip">
            <div><b>{{ attentionIndex ?? "—" }}</b><span>Attention Index</span></div>
            <div><b>{{ governancePower ?? "—" }}</b><span>治理投票权重</span></div>
            <div><b>{{ attentionDetail?.timeQuality ?? "—" }}</b><span>时间质量</span></div>
            <div><b>{{ attentionDetail?.informationValue ?? "—" }}</b><span>信息价值</span></div>
            <div><b>{{ attentionDetail?.propagationImpact ?? "—" }}</b><span>传播影响</span></div>
            <div><b>{{ attentionDetail?.deepEngagement ?? "—" }}</b><span>深度参与</span></div>
            <p v-if="attentionDetail">{{ attentionDetail.explanation }}</p>
            <p>{{ aiSummary || "AI Agent 将基于你的算法模式生成总结、注意力优化和学习路径建议。" }}</p>
          </div>
          <div class="agent-panel">
            <h3>AI Agent v1</h3>
            <p>{{ aiAgent?.contentSummary || "等待真实浏览样本后生成内容摘要。" }}</p>
            <p><b>注意力优化：</b>{{ aiAgent?.attentionOptimization || "暂无优化建议。" }}</p>
            <p><b>学习路径：</b>{{ aiAgent?.learningPathSuggestion || "先选择算法模式并浏览内容。" }}</p>
            <div v-if="aiAgent?.alerts?.length" class="agent-alerts">
              <span v-for="alert in aiAgent.alerts" :key="alert">{{ alert }}</span>
            </div>
            <ul v-if="aiAgent?.suggestions?.length">
              <li v-for="item in aiAgent.suggestions" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div class="custom-panel">
            <h3>自定义参数</h3>
            <p class="world-model">{{ worldModelSummary }}</p>
            <label v-for="(label, key) in { randomness: '随机性', diversity: '多样性', depth: '深度', entertainment: '娱乐性', challenge: '认知挑战', novelty: '新颖性' }" :key="key">
              <span>{{ label }} · {{ customParams[key] }}</span>
              <input v-model.number="customParams[key]" type="range" min="0" max="100" />
            </label>
            <div class="custom-actions">
              <button type="button" class="custom-apply" :disabled="modeSaving" @click="chooseMode('custom')">应用自定义模式</button>
              <button type="button" class="custom-secondary" :disabled="modeSaving" @click="saveCurrentPreset">保存模板</button>
              <button type="button" class="custom-secondary" :disabled="modeSaving" @click="resetDefaults">恢复默认</button>
            </div>
            <div v-if="presets.length" class="preset-list">
              <button v-for="preset in presets" :key="preset.id" type="button" :disabled="modeSaving" @click="applyPreset(preset.id)">
                <b>{{ preset.name }}</b>
                <span>深度 {{ preset.parameters.depth }} · 挑战 {{ preset.parameters.challenge }} · 新颖 {{ preset.parameters.novelty }}</span>
              </button>
            </div>
          </div>
        </section>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.discover {
  position: relative;
  padding-bottom: 8px;
}

.is-loading {
  min-height: min(40vh, 400px);
}

.section-title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--native-text-primary);
}

.section-hint {
  margin-bottom: 12px;
}

.discover-hero {
  position: relative;
  overflow: hidden;
  margin-bottom: 12px;
  padding: 16px;
  border: 1px solid rgba(103, 232, 249, 0.16);
  border-radius: 26px;
  background:
    radial-gradient(circle at 0% 0%, rgba(34, 211, 238, 0.22), transparent 34%),
    radial-gradient(circle at 100% 20%, rgba(139, 92, 246, 0.16), transparent 36%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.88), rgba(2, 6, 23, 0.94));
  box-shadow: 0 18px 54px rgba(0, 0, 0, 0.22);
}

.discover-hero__glow {
  position: absolute;
  inset: -46px -80px auto auto;
  width: 190px;
  height: 190px;
  border-radius: 999px;
  border: 1px solid rgba(103, 232, 249, 0.18);
  background: rgba(34, 211, 238, 0.08);
  pointer-events: none;
}

.discover-hero__head {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: start;
  gap: 12px;
  margin-bottom: 12px;
}

.discover-hero__head h1 {
  margin: 0;
  color: #f8fafc;
  font-size: clamp(28px, 9vw, 42px);
  line-height: 1;
  font-weight: 950;
  letter-spacing: -0.08em;
  grid-column: 2;
  text-align: center;
}

.discover-hero__head span {
  flex-shrink: 0;
  color: #67e8f9;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.06em;
}

.mode-chip {
  grid-column: 3;
  justify-self: end;
  flex-shrink: 0;
  display: grid;
  gap: 2px;
  border: 1px solid rgba(103, 232, 249, 0.22);
  border-radius: 16px;
  padding: 8px 10px;
  background: rgba(2, 6, 23, 0.62);
  color: #e0f2fe;
  text-align: left;
  cursor: pointer;
}

.mode-chip span {
  color: #67e8f9;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.08em;
}

.mode-chip b {
  color: #f8fafc;
  font-size: 13px;
  font-weight: 950;
}

.search-row {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 8px;
  align-items: stretch;
}

.discover-input {
  flex: 1;
  min-width: 0;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 18px;
  padding: 0 14px;
  min-height: 52px;
  background: rgba(2, 6, 23, 0.72);
  color: #f8fafc;
  font-size: 17px;
  font-weight: 800;
  outline: none;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.discover-input::placeholder {
  color: #8b94a7;
}

.discover-input:focus {
  border-color: rgba(103, 232, 249, 0.55);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.05),
    0 0 0 3px rgba(34, 211, 238, 0.1);
}

.search-go {
  flex-shrink: 0;
  min-width: 84px;
  min-height: 52px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 18px;
  text-decoration: none;
  white-space: nowrap;
  font-size: 17px;
  font-weight: 950;
  box-shadow: 0 14px 30px rgba(34, 211, 238, 0.22);
}

.trend-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.trend-tile {
  border-radius: var(--native-radius-md);
  border: 1px solid var(--native-border);
  overflow: hidden;
  background: var(--native-bg-elevated);
  text-decoration: none;
  color: inherit;
  transition: transform var(--native-duration) var(--native-ease-out);
}

.trend-tile:active {
  transform: scale(var(--native-tap-scale));
}

.trend-tile__thumb {
  aspect-ratio: 3 / 4;
  background: linear-gradient(145deg, #27272a, #18181b);
  position: relative;
}

.trend-tile__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.trend-tile__thumb--ph {
  min-height: 120px;
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 50%, #312e81 100%);
}

.trend-tile__cap {
  padding: 8px 10px 10px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--native-text-primary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mode-sheet-root {
  position: fixed;
  inset: 0;
  z-index: 4200;
  display: grid;
  place-items: end center;
  padding: 18px;
  background: rgba(2, 6, 23, 0.68);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.mode-sheet {
  width: min(560px, 100%);
  max-height: min(82vh, 760px);
  overflow: auto;
  border: 1px solid rgba(103, 232, 249, 0.2);
  border-radius: 28px;
  padding: 18px;
  background:
    radial-gradient(circle at 0% 0%, rgba(34, 211, 238, 0.16), transparent 34%),
    linear-gradient(180deg, #101827, #05070d);
  color: #f8fafc;
  box-shadow: 0 24px 90px rgba(0, 0, 0, 0.45);
}

.mode-sheet__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.mode-sheet__head p {
  margin: 0 0 4px;
  color: #67e8f9;
  font-size: 12px;
  font-weight: 900;
}

.mode-sheet__head h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 950;
}

.mode-sheet__head button {
  width: 36px;
  height: 36px;
  border: 0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: #e2e8f0;
  font-size: 22px;
}

.mode-list {
  display: grid;
  gap: 10px;
}

.insight-strip {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 10px 0;
  padding: 10px;
  border: 1px solid rgba(103, 232, 249, 0.14);
  border-radius: 18px;
  background: rgba(15, 23, 42, 0.58);
}

.insight-strip div {
  display: grid;
  gap: 2px;
}

.insight-strip b {
  color: #e0f2fe;
  font-size: 18px;
  font-weight: 950;
}

.insight-strip span,
.insight-strip p {
  margin: 0;
  color: #93c5fd;
  font-size: 11px;
  line-height: 1.45;
}

.insight-strip p {
  grid-column: 1 / -1;
}

.agent-panel {
  display: grid;
  gap: 8px;
  margin-top: 10px;
  padding: 11px;
  border: 1px solid rgba(167, 139, 250, 0.18);
  border-radius: 18px;
  background: rgba(30, 27, 75, 0.36);
}

.agent-panel h3,
.agent-panel p {
  margin: 0;
}

.agent-panel h3 {
  color: #e9d5ff;
  font-size: 14px;
  font-weight: 950;
}

.agent-panel p,
.agent-panel li {
  color: #c4b5fd;
  font-size: 11px;
  line-height: 1.45;
}

.agent-panel ul {
  margin: 0;
  padding-left: 16px;
}

.agent-alerts {
  display: grid;
  gap: 5px;
}

.agent-alerts span {
  border: 1px solid rgba(251, 191, 36, 0.2);
  border-radius: 12px;
  padding: 6px 8px;
  background: rgba(120, 53, 15, 0.24);
  color: #fde68a;
  font-size: 11px;
  line-height: 1.4;
}

.mode-card {
  display: grid;
  gap: 4px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 18px;
  padding: 12px;
  background: rgba(15, 23, 42, 0.72);
  color: #f8fafc;
  text-align: left;
}

.mode-card.on {
  border-color: rgba(103, 232, 249, 0.68);
  background: rgba(8, 47, 73, 0.62);
  box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.08);
}

.mode-card b {
  font-size: 15px;
  font-weight: 950;
}

.mode-card span {
  color: #94a3b8;
  font-size: 12px;
}

.custom-panel {
  margin-top: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 14px;
}

.custom-panel h3 {
  margin: 0 0 10px;
  font-size: 15px;
}

.world-model {
  margin: 0 0 10px;
  padding: 8px 10px;
  border: 1px solid rgba(103, 232, 249, 0.14);
  border-radius: 14px;
  background: rgba(8, 47, 73, 0.28);
  color: #bae6fd;
  font-size: 11px;
  line-height: 1.45;
}

.custom-panel label {
  display: grid;
  gap: 6px;
  margin: 10px 0;
  color: #cbd5e1;
  font-size: 12px;
  font-weight: 800;
}

.custom-panel input {
  accent-color: #22d3ee;
}

.custom-actions {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr 0.8fr;
  gap: 8px;
}

.custom-apply {
  width: 100%;
  min-height: 42px;
  border: 0;
  border-radius: 999px;
  background: linear-gradient(135deg, #67e8f9, #a78bfa);
  color: #06111f;
  font-weight: 950;
}

.custom-secondary {
  min-height: 42px;
  border: 1px solid rgba(103, 232, 249, 0.22);
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.76);
  color: #bae6fd;
  font-weight: 900;
}

.preset-list {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.preset-list button {
  display: grid;
  gap: 3px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 14px;
  padding: 9px 10px;
  background: rgba(2, 6, 23, 0.45);
  color: #e0f2fe;
  text-align: left;
}

.preset-list span {
  color: #93c5fd;
  font-size: 11px;
}
</style>
