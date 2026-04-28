from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, Field

AlgorithmMode = str
ATTENTION_VALUE_FORMULA = "Attention Value = 时间质量 × 信息价值 × 传播影响 × 深度参与"


class AlgorithmParameters(BaseModel):
    randomness: int = Field(default=50, ge=0, le=100)
    diversity: int = Field(default=70, ge=0, le=100)
    depth: int = Field(default=50, ge=0, le=100)
    entertainment: int = Field(default=50, ge=0, le=100)
    challenge: int = Field(default=50, ge=0, le=100)
    novelty: int = Field(default=60, ge=0, le=100)


class AlgorithmStateOut(BaseModel):
    mode: str
    personalized: bool
    resetAt: datetime | None = None
    explorationSeed: str | None = None
    coldStartStrategy: str
    parameters: AlgorithmParameters = Field(default_factory=AlgorithmParameters)
    attentionIndex: int = 0


class AlgorithmResetResponse(BaseModel):
    success: bool
    message: str
    data: AlgorithmStateOut


class AlgorithmStateUpdate(BaseModel):
    mode: AlgorithmMode = Field(pattern="^(origin|efficiency|growth|emotion|custom)$")
    parameters: AlgorithmParameters | None = None


class AlgorithmModeOption(BaseModel):
    mode: str
    title: str
    subtitle: str
    weights: AlgorithmParameters


class AlgorithmStateResponse(BaseModel):
    success: bool
    message: str
    data: AlgorithmStateOut


class AlgorithmPresetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=240)
    parameters: AlgorithmParameters | None = None


class AlgorithmPresetOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    parameters: AlgorithmParameters
    createdAt: datetime
    updatedAt: datetime


class AlgorithmPresetListResponse(BaseModel):
    success: bool
    items: list[AlgorithmPresetOut]


class AlgorithmPresetResponse(BaseModel):
    success: bool
    message: str
    data: AlgorithmPresetOut


class AttentionIndexOut(BaseModel):
    attentionIndex: int
    inputQuality: int
    outputValue: int
    cognitiveGrowth: int
    timeQuality: int = 0
    informationValue: int = 0
    propagationImpact: int = 0
    deepEngagement: int = 0
    formula: str = ATTENTION_VALUE_FORMULA
    detail: dict | None = None
    latestMode: str | None = None
    explanation: str


class AttentionIndexResponse(BaseModel):
    success: bool
    data: AttentionIndexOut


class AiAgentPanelOut(BaseModel):
    mode: str
    modelVersion: str = "agent-v1-rule-based"
    summary: str
    contentSummary: str
    attentionOptimization: str
    learningPathSuggestion: str
    alerts: list[str] = Field(default_factory=list)
    attentionFactors: dict[str, int] = Field(default_factory=dict)
    suggestions: list[str]
    nextActions: list[str]


class GovernancePowerOut(BaseModel):
    votingPower: int
    formula: str
    canVote: bool
