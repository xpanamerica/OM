import { apiGetJson, apiPatchJson, apiPostJson } from "./client";

export type AlgorithmMode = "origin" | "efficiency" | "growth" | "emotion" | "custom";

export type AlgorithmParameters = {
  randomness: number;
  diversity: number;
  depth: number;
  entertainment: number;
  challenge: number;
  novelty: number;
};

export type AlgorithmState = {
  mode: AlgorithmMode | string;
  personalized: boolean;
  resetAt: string | null;
  explorationSeed: string | null;
  coldStartStrategy: string;
  parameters: AlgorithmParameters;
  attentionIndex: number;
};

export type AlgorithmStateResponse = {
  success: boolean;
  message: string;
  data: AlgorithmState;
};

export async function getAlgorithmState(token: string): Promise<AlgorithmStateResponse> {
  const { data } = await apiGetJson<AlgorithmStateResponse>("/users/me/algorithm-state", { token });
  return data;
}

export async function updateAlgorithmState(
  token: string,
  body: { mode: AlgorithmMode; parameters?: AlgorithmParameters },
): Promise<AlgorithmStateResponse> {
  const { data } = await apiPatchJson<AlgorithmStateResponse, typeof body>("/users/me/algorithm-state", body, { token });
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

export async function listAlgorithmPresets(token: string): Promise<{ success: boolean; items: AlgorithmPreset[] }> {
  const { data } = await apiGetJson<{ success: boolean; items: AlgorithmPreset[] }>("/users/me/algorithm-presets", { token });
  return data;
}

export async function saveAlgorithmPreset(
  token: string,
  body: { name: string; description?: string | null; parameters?: AlgorithmParameters },
): Promise<{ success: boolean; message: string; data: AlgorithmPreset }> {
  const { data } = await apiPostJson<{ success: boolean; message: string; data: AlgorithmPreset }, typeof body>(
    "/users/me/algorithm-presets",
    body,
    { token },
  );
  return data;
}

export async function applyAlgorithmPreset(token: string, id: string): Promise<AlgorithmStateResponse> {
  const { data } = await apiPostJson<AlgorithmStateResponse, Record<string, never>>(
    `/users/me/algorithm-presets/${id}/apply`,
    {},
    { token },
  );
  return data;
}

export async function resetCustomDefaults(token: string): Promise<AlgorithmStateResponse> {
  const { data } = await apiPostJson<AlgorithmStateResponse, Record<string, never>>(
    "/users/me/algorithm-state/reset-custom-defaults",
    {},
    { token },
  );
  return data;
}

export async function getAttentionIndex(token: string): Promise<{
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
    explanation: string;
  };
}> {
  const { data } = await apiGetJson<{
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
      explanation: string;
    };
  }>("/users/me/attention-index", { token });
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

export async function getAiAgentPanel(token: string): Promise<AiAgentPanel> {
  const { data } = await apiGetJson<AiAgentPanel>("/users/me/ai-agent-panel", { token });
  return data;
}

export async function getGovernancePower(token: string): Promise<{ votingPower: number; formula: string; canVote: boolean }> {
  const { data } = await apiGetJson<{ votingPower: number; formula: string; canVote: boolean }>("/users/me/governance-power", { token });
  return data;
}
