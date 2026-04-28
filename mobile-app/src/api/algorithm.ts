import { apiGetJson, apiPatchJson } from "./client";

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

export async function getAttentionIndex(token: string): Promise<{
  success: boolean;
  data: { attentionIndex: number; inputQuality: number; outputValue: number; cognitiveGrowth: number };
}> {
  const { data } = await apiGetJson<{
    success: boolean;
    data: { attentionIndex: number; inputQuality: number; outputValue: number; cognitiveGrowth: number };
  }>("/users/me/attention-index", { token });
  return data;
}

export async function getAiAgentPanel(token: string): Promise<{ summary: string; suggestions: string[]; nextActions: string[] }> {
  const { data } = await apiGetJson<{ summary: string; suggestions: string[]; nextActions: string[] }>("/users/me/ai-agent-panel", { token });
  return data;
}

export async function getGovernancePower(token: string): Promise<{ votingPower: number; formula: string; canVote: boolean }> {
  const { data } = await apiGetJson<{ votingPower: number; formula: string; canVote: boolean }>("/users/me/governance-power", { token });
  return data;
}
