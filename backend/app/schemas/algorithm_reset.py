from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

AlgorithmMode = str


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


class AttentionIndexOut(BaseModel):
    attentionIndex: int
    inputQuality: int
    outputValue: int
    cognitiveGrowth: int
    latestMode: str | None = None
    explanation: str


class AttentionIndexResponse(BaseModel):
    success: bool
    data: AttentionIndexOut


class AiAgentPanelOut(BaseModel):
    summary: str
    suggestions: list[str]
    nextActions: list[str]


class GovernancePowerOut(BaseModel):
    votingPower: int
    formula: str
    canVote: bool
