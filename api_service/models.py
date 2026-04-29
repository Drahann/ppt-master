from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


BATCH_PARTITION_PATTERN = r"^((fixed|ramp|ramp_2_3_4_5_6_7_8|anchor_even)|([0-9]+\+)*[0-9]+\+?)$"


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reportId: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    fileUrl: str | None = None
    callbackUrl: str | None = None
    batchMode: str | None = Field(default=None, pattern="^(auto|always|never|parallel)$")
    batchSize: int | None = Field(default=None, ge=1)
    parallelBatchWorkers: int | None = Field(default=None, ge=1)
    batchPartition: str | None = Field(default=None, pattern=BATCH_PARTITION_PATTERN)
    specModel: str | None = None
    notesModel: str | None = None
    responseMode: str | None = Field(default=None, pattern="^(sync|async)$")
    callbackMode: str | None = Field(default=None, pattern="^(auto|defer|none)$")
    svgWorkers: int | None = Field(default=None, ge=1)
    svgBatchSize: int | None = Field(default=None, ge=1)
    qwenModel: str | None = None
    claudeEffort: str | None = Field(default=None, pattern="^(low|medium|high|max)$")


class GeneratePptRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    msg: str | None = None
    companyId: str | None = None
    userId: str | None = None
    report_id: str = Field(..., min_length=1)
    fileUrl: str | None = None
    wordUrl: str | None = None
    title: Any | None = None
    content: str = Field(..., min_length=1)
    themeId: str | None = None
    callbackUrl: str | None = None
    batchMode: str | None = Field(default=None, pattern="^(auto|always|never|parallel)$")
    batchSize: int | None = Field(default=None, ge=1)
    parallelBatchWorkers: int | None = Field(default=None, ge=1)
    batchPartition: str | None = Field(default=None, pattern=BATCH_PARTITION_PATTERN)
    specModel: str | None = None
    notesModel: str | None = None
    responseMode: str | None = Field(default=None, pattern="^(sync|async)$")
    callbackMode: str | None = Field(default=None, pattern="^(auto|defer|none)$")
    svgWorkers: int | None = Field(default=None, ge=1)
    svgBatchSize: int | None = Field(default=None, ge=1)
    qwenModel: str | None = None
    claudeEffort: str | None = Field(default=None, pattern="^(low|medium|high|max)$")


@dataclass(frozen=True)
class NormalizedRequest:
    report_id: str
    content: str
    file_url: str | None
    word_url: str | None
    title: str | None
    callback_url: str | None
    response_mode: str
    callback_mode: str
    svg_workers: int | None
    svg_batch_size: int | None
    qwen_model: str | None
    notes_model: str | None
    claude_effort: str | None


class CallbackResult(BaseModel):
    success: bool
    error: str | None = None


class ReportResponse(BaseModel):
    success: bool
    reportId: str
    pptUrl: str | None = None
    slideCount: int = 0
    title: str | None = None
    callback: CallbackResult | None = None
    status: str | None = None
    job_id: str | None = None
    pollingUrl: str | None = None


class GeneratePptResponse(BaseModel):
    success: bool
    report_id: str
    pptUrl: str | None = None
    slideCount: int = 0
    title: str | None = None
    callback: CallbackResult | None = None
    status: str | None = None
    job_id: str | None = None
    pollingUrl: str | None = None
