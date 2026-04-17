from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reportId: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    fileUrl: str | None = None
    callbackUrl: str | None = None
    batchMode: str | None = Field(default=None, pattern="^(auto|always|never)$")
    batchSize: int | None = Field(default=None, ge=1)


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
