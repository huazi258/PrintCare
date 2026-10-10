"""Structured contracts for the future diagnosis workflow.

These models validate only the shape and internal consistency of a diagnosis
request or decision.  Session lifecycle, source existence, and evidence
authorization remain service-layer responsibilities in later T2 tasks.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from knowledge.core.devices import UnsupportedDeviceError, resolve_supported_device


NonEmptyText = Annotated[str, Field(min_length=1)]


class DiagnosisSchemaModel(BaseModel):
    """Base configuration shared by diagnosis API and LLM contracts."""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class EvidenceReference(DiagnosisSchemaModel):
    """A reference to a source returned by the current local retrieval round."""

    source_id: NonEmptyText = Field(
        ..., description="真实检索来源标识，例如 chunk:<真实chunk_id>"
    )


class DiagnosisOption(DiagnosisSchemaModel):
    """One selectable answer for a diagnosis question."""

    option_id: NonEmptyText
    text: NonEmptyText
    option_type: Literal["normal", "uncertain", "other"] = "normal"


class DiagnosisQuestion(DiagnosisSchemaModel):
    """One independently answerable diagnosis question."""

    question_id: NonEmptyText
    text: NonEmptyText
    options: list[DiagnosisOption] = Field(min_length=2, max_length=4)
    references: list[EvidenceReference] = Field(
        min_length=1,
        description="支撑本问题的本轮检索来源标识；真实性由 T2-05 校验。",
    )

    @model_validator(mode="after")
    def validate_unique_option_ids(self) -> "DiagnosisQuestion":
        option_ids = [option.option_id for option in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("同一道问题中的 option_id 不可重复")
        return self


class DiagnosisAnswerInput(DiagnosisSchemaModel):
    """The user's answer to one question in a batch submission."""

    question_id: NonEmptyText
    option_id: NonEmptyText
    supplemental_note: NonEmptyText | None = None


class DiagnosisStartRequest(DiagnosisSchemaModel):
    """Input required to begin a new diagnosis session."""

    device_id: NonEmptyText
    original_problem: NonEmptyText

    @field_validator("device_id")
    @classmethod
    def validate_supported_device(cls, value: str) -> str:
        """Reuse the canonical device registry instead of copying its allowlist."""
        try:
            resolve_supported_device(value)
        except UnsupportedDeviceError as exc:
            raise ValueError(str(exc)) from exc
        return value


class DiagnosisContinueRequest(DiagnosisSchemaModel):
    """A full set of answers submitted for the current diagnosis round."""

    diagnosis_id: NonEmptyText
    answers: list[DiagnosisAnswerInput] = Field(min_length=1)
    request_id: NonEmptyText
    expected_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_unique_answer_question_ids(self) -> "DiagnosisContinueRequest":
        question_ids = [answer.question_id for answer in self.answers]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("同一轮提交中的 question_id 不可重复")
        return self


class DiagnosisAskDecision(DiagnosisSchemaModel):
    """Decision to collect another independent group of answers."""

    action: Literal["ask"]
    questions: list[DiagnosisQuestion] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def validate_unique_question_ids(self) -> "DiagnosisAskDecision":
        question_ids = [question.question_id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("同一问题组中的 question_id 不可重复")
        return self


class DiagnosisAnswerDecision(DiagnosisSchemaModel):
    """Decision with a bounded conclusion and structured troubleshooting steps."""

    action: Literal["answer"]
    conclusion: NonEmptyText
    recommendations: list[NonEmptyText] = Field(min_length=1)
    references: list[EvidenceReference] = Field(min_length=1)
    safety_notes: list[NonEmptyText]


class DiagnosisInsufficientDecision(DiagnosisSchemaModel):
    """Decision that the available local evidence is not sufficient."""

    action: Literal["insufficient"]
    reason: NonEmptyText
    confirmed_facts: list[NonEmptyText] = Field(default_factory=list)
    next_steps: list[NonEmptyText] = Field(min_length=1)


DiagnosisDecision = Annotated[
    Union[DiagnosisAskDecision, DiagnosisAnswerDecision, DiagnosisInsufficientDecision],
    Field(discriminator="action"),
]


DiagnosisStatus = Literal[
    "in_progress",
    "pending_verification",
    "resolved",
    "unresolved",
    "insufficient",
    "ended",
]


class DiagnosisResponse(DiagnosisSchemaModel):
    """Minimal response envelope shared by future HTTP, MongoDB, and SSE code."""

    diagnosis_id: NonEmptyText
    device_id: NonEmptyText
    decision: DiagnosisDecision
    clarification_round: int = Field(ge=0)
    status: DiagnosisStatus

    @field_validator("device_id")
    @classmethod
    def validate_supported_device(cls, value: str) -> str:
        try:
            resolve_supported_device(value)
        except UnsupportedDeviceError as exc:
            raise ValueError(str(exc)) from exc
        return value
