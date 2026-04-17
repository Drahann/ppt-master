from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reportId: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    fileUrl: str | None = None
    callbackUrl: str | None = None
    batchMode: str | None = Field(default=None, pattern="^(auto|always|never|parallel)$")
    batchSize: int | None = Field(default=None, ge=1)
    parallelBatchWorkers: int | None = Field(default=None, ge=1)


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


@dataclass(frozen=True)
class NormalizedRequest:
    report_id: str
    content: str
    file_url: str | None
    word_url: str | None
    title: str | None
    callback_url: str | None
    batch_mode: str | None
    batch_size: int | None
    parallel_batch_workers: int | None


class CallbackResult(BaseModel):
    success: bool
    error: str | None = None


class ReportResponse(BaseModel):
    success: bool
    reportId: str
    pptUrl: str
    slideCount: int
    title: str
    callback: CallbackResult


class GeneratePptResponse(BaseModel):
    success: bool
    report_id: str
    pptUrl: str
    slideCount: int
    title: str
    callback: CallbackResult
