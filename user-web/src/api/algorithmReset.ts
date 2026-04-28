import { http } from "./http";

export type AlgorithmState = {
  mode: "origin" | string;
  personalized: boolean;
  resetAt: string | null;
  explorationSeed: string | null;
  coldStartStrategy: "random_balanced" | string;
  parameters: AlgorithmParameters;
  attentionIndex: number;
};

export type AlgorithmParameters = {
  randomness: number;
  diversity: number;
  depth: number;
  entertainment: number;
  challenge: number;
  novelty: number;
};

export type AlgorithmResetResponse = {
  success: boolean;
  message: string;
  data: AlgorithmState;
};

export async function algorithmReset(): Promise<AlgorithmResetResponse> {
  const { data } = await http.post<AlgorithmResetResponse>("/users/me/algorithm-reset");
  return data;
}

export async function getAlgorithmState(): Promise<AlgorithmResetResponse> {
  const { data } = await http.get<AlgorithmResetResponse>("/users/me/algorithm-state");
  return data;
}

export async function updateAlgorithmState(body: {
  mode: "origin" | "efficiency" | "growth" | "emotion" | "custom";
  parameters?: AlgorithmParameters;
}): Promise<AlgorithmResetResponse> {
  const { data } = await http.patch<AlgorithmResetResponse>("/users/me/algorithm-state", body);
  return data;
}

export type AlgorithmPreset = {
  id: string;
  name: string;
  description: string | null;
  parameters: AlgorithmParameters;
  createdAt: string;
  updatedAt: string;
};

export async function listAlgorithmPresets(): Promise<{ success: boolean; items: AlgorithmPreset[] }> {
  const { data } = await http.get("/users/me/algorithm-presets");
  return data;
}

export async function saveAlgorithmPreset(body: {
  name: string;
  description?: string | null;
  parameters?: AlgorithmParameters;
}): Promise<{ success: boolean; message: string; data: AlgorithmPreset }> {
  const { data } = await http.post("/users/me/algorithm-presets", body);
  return data;
}

export async function applyAlgorithmPreset(id: string): Promise<AlgorithmResetResponse> {
  const { data } = await http.post<AlgorithmResetResponse>(`/users/me/algorithm-presets/${id}/apply`);
  return data;
}

export async function resetCustomDefaults(): Promise<AlgorithmResetResponse> {
  const { data } = await http.post<AlgorithmResetResponse>("/users/me/algorithm-state/reset-custom-defaults");
  return data;
}

export async function getAttentionIndex(): Promise<{
  success: boolean;
  data: {
    attentionIndex: number;
    inputQuality: number;
    outputValue: number;
    cognitiveGrowth: number;
    timeQuality: number;
    informationValue: number;
    propagationImpact: number;
    deepEngagement: number;
    formula: string;
    detail: Record<string, unknown> | null;
    latestMode: string | null;
    explanation: string;
  };
}> {
  const { data } = await http.get("/users/me/attention-index");
  return data;
}

export type AiAgentPanel = {
  mode: string;
  modelVersion: string;
  summary: string;
  contentSummary: string;
  attentionOptimization: string;
  learningPathSuggestion: string;
  alerts: string[];
  attentionFactors: Record<string, number>;
  suggestions: string[];
  nextActions: string[];
};

export async function getAiAgentPanel(): Promise<AiAgentPanel> {
  const { data } = await http.get("/users/me/ai-agent-panel");
  return data;
}

export async function getGovernancePower(): Promise<{ votingPower: number; formula: string; canVote: boolean }> {
  const { data } = await http.get("/users/me/governance-power");
  return data;
}
