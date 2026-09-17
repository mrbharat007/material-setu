from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class Role(str, Enum):
    steward = "steward"
    admin = "admin"


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    cpse: str | None = None


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=128)


class RoleUpdateIn(BaseModel):
    role: Role


class UserOut(BaseModel):
    id: int
    email: str = Field(min_length=3, max_length=200)
    name: str
    role: Role
    cpse: str | None = None
    created_at: datetime | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MaterialIn(BaseModel):
    cpse: str = Field(min_length=1)
    sector: str | None = None
    local_code: str = Field(min_length=1)
    description: str = Field(min_length=1)
    material_family: str | None = None
    manufacturer: str | None = None
    manufacturer_part_no: str | None = None
    uom: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class MaterialBulkRow(BaseModel):
    """One row of a bulk CSV/XLSX upload.

    Every field is optional at the schema level — a spreadsheet row can be
    missing anything — so a single malformed row never 422s the whole
    request. ``bulk_ingest`` does the real (required-field) validation itself
    and reports failures per row instead.
    """
    row: int
    cpse: str | None = None
    local_code: str | None = None
    description: str | None = None
    material_family: str | None = None
    manufacturer: str | None = None
    manufacturer_part_no: str | None = None
    uom: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class UomStandard(BaseModel):
    """A unit resolved against UN/CEFACT Recommendation 20."""
    code: str | None = None
    name: str
    symbol: str = ""
    quantity: str = ""
    input: str
    matched: bool


class Classification(BaseModel):
    """A material placed in the Federal Supply Classification."""
    fsc: str
    fsc_title: str
    fsg: str
    fsg_title: str
    confidence: str
    basis: str = ""


class StandardizedMaterial(MaterialIn):
    id: int
    normalized_description: str
    extracted_attributes: dict[str, Any] = Field(default_factory=dict)
    uom_code: str | None = None
    fsc: str | None = None
    fsc_title: str | None = None
    fsg: str | None = None
    fsg_title: str | None = None


class BulkIngestError(BaseModel):
    row: int
    cpse: str | None = None
    local_code: str | None = None
    reason: str


class BulkIngestResult(BaseModel):
    total: int
    created: list[StandardizedMaterial]
    errors: list[BulkIngestError]


class StandardizedPreview(BaseModel):
    normalized_description: str
    extracted_attributes: dict[str, Any] = Field(default_factory=dict)
    normalized_uom: str | None = None
    resolved_family: str | None = None
    uom_standard: UomStandard | None = None
    classification: Classification | None = None


class AttachmentOut(BaseModel):
    id: int
    material_id: int
    filename: str
    content_type: str
    size_bytes: int
    uploaded_by: str | None = None
    created_at: datetime


class MatchStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class MatchCandidate(BaseModel):
    id: int
    left_material_id: int
    right_material_id: int
    score: float
    explanation: list[str]
    status: MatchStatus = MatchStatus.pending
    reviewer: str | None = None
    review_note: str | None = None
    reviewed_at: datetime | None = None


class DecisionIn(BaseModel):
    decision: MatchStatus
    reviewer: str = "steward"
    note: str | None = None


class NMCRecord(BaseModel):
    nmc: str
    canonical_material_id: int
    local_material_ids: list[int]
    explanation: str
    fsc: str | None = None
    fsc_title: str | None = None
    fsg: str | None = None
    fsg_title: str | None = None


class DecisionResult(BaseModel):
    match: MatchCandidate
    nmc: NMCRecord | None = None


class ProcurementBulkRow(BaseModel):
    """One line of a bulk procurement CSV — matched to an existing material by
    (cpse, local_code). Every field is a loose string (like
    :class:`MaterialBulkRow`) so one malformed cell never 422s the whole
    upload; ``ingest_procurement`` parses and validates each row itself and
    reports failures per row.
    """
    row: int
    cpse: str | None = None
    local_code: str | None = None
    order_date: str | None = None
    quantity: str | None = None
    unit_price_inr: str | None = None
    po_number: str | None = None
    supplier: str | None = None


class ProcurementImportSkip(BaseModel):
    row: int
    cpse: str
    local_code: str
    reason: str


class ProcurementImportResult(BaseModel):
    imported: int
    skipped: list[ProcurementImportSkip]


class CpseSpend(BaseModel):
    cpse: str
    quantity: float
    avg_price: float


class ProcurementOpportunity(BaseModel):
    nmc: str
    fsc: str
    fsc_title: str
    fsg: str
    fsg_title: str
    description: str
    cpses: list[str]
    cpse_count: int
    order_count: int
    uom: str | None = None
    total_quantity: float
    total_value_inr: float
    min_unit_price: float
    max_unit_price: float
    avg_unit_price: float
    price_spread_ratio: float
    best_price_cpse: str | None = None
    estimated_saving_inr: float
    per_cpse: list[CpseSpend]


class AuditEntry(BaseModel):
    id: int
    actor: str
    action: str
    entity_type: str
    entity_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class NameCount(BaseModel):
    name: str
    n: int


class Stats(BaseModel):
    materials: int
    cpses: int
    by_sector: list[NameCount]
    by_cpse: list[NameCount]
    by_family: list[NameCount]
    by_supply_group: list[NameCount]
    matches_pending: int
    matches_approved: int
    matches_rejected: int
    nmc_count: int
    linked_materials: int
    master_record_reduction: int
    max_cpses_linked: int
    procurement_opportunities: int = 0
    aggregation_saving_inr: float = 0.0
