import os
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import (
    attachment_repository,
    audit_repository,
    auth,
    match_repository,
    nmc_repository,
    procurement_repository,
    stats_repository,
    user_repository,
)
from .database import get_connection
from .material_repository import (
    get_all_materials,
    get_material,
    get_material_by_cpse_code,
    insert_material,
)
from .schemas import (
    AttachmentOut,
    AuditEntry,
    BulkIngestResult,
    DecisionIn,
    DecisionResult,
    LoginIn,
    MatchCandidate,
    MatchStatus,
    MaterialBulkRow,
    MaterialIn,
    NMCRecord,
    ProcurementBulkRow,
    ProcurementImportResult,
    ProcurementOpportunity,
    RegisterIn,
    RoleUpdateIn,
    StandardizedMaterial,
    StandardizedPreview,
    Stats,
    TokenOut,
    UserOut,
)
from .services.attribute_templates import resolve_family
from .services.classifier import classify
from .services.matcher import compare_materials
from .services.semantic import SemanticModel
from .services.standardizer import extract_attributes, normalize_text
from .services.uom_registry import resolve_uom


@asynccontextmanager
async def lifespan(_: FastAPI):
    from .db_bootstrap import ensure_schema

    ensure_schema()
    yield


app = FastAPI(
    title="Material Setu API",
    version="0.4.0",
    description=(
        "AI-driven standardization and harmonization of material codes "
        "across CPSEs."
    ),
    lifespan=lifespan,
)


cors_origins_env = os.environ.get("CORS_ORIGINS", "").strip()
if cors_origins_env:
    cors_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
    cors_regex = None
else:
    cors_origins = []
    # Allow localhost, 127.0.0.1, Vercel deployments, and any standard web origin
    cors_regex = r"^https?://.*$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _actor(user: object) -> str:
    """Audit-log actor label for the caller.

    ``user`` is a resolved user dict on the HTTP path; scripts that call these
    endpoint functions directly pass :data:`auth.SYSTEM_USER`.
    """
    if isinstance(user, dict):
        return user.get("name") or user.get("email") or "system"
    return "system"


# ---------------------------------------------------------
# Persistence
# ---------------------------------------------------------
# Materials, match candidates, National Material Codes and the audit log all
# live in PostgreSQL (see db/schema.sql).


# ---------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------

@app.get("/health")
def health():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()

    return {
        "status": "ok",
        "service": "material-setu",
        "database": "connected",
    }


# ---------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------
# The first account created becomes an admin; every later sign-up is a steward.
# Stewards (and admins) can act on the review queue.

@app.post("/auth/register", response_model=TokenOut, status_code=201)
def register(payload: RegisterIn):
    if user_repository.get_user_by_email(payload.email):
        raise HTTPException(status_code=409, detail="Email already registered")

    role = "admin" if user_repository.count_users() == 0 else "steward"
    user = user_repository.create_user(
        email=payload.email,
        name=payload.name,
        password_hash=auth.hash_password(payload.password),
        role=role,
        cpse=(payload.cpse or None),
    )

    audit_repository.write_audit(
        actor=user["email"],
        action="user.registered",
        entity_type="user",
        entity_id=str(user["id"]),
        details={"name": user["name"], "role": user["role"]},
    )

    return {"access_token": auth.create_token(user), "user": user}


@app.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn):
    user = user_repository.get_user_by_email(payload.email)
    if user is None or not auth.verify_password(
        payload.password, user["password_hash"]
    ):
        raise HTTPException(status_code=401, detail="Wrong email or password")

    return {"access_token": auth.create_token(user), "user": user}


@app.get("/auth/me", response_model=UserOut)
def me(user: dict = Depends(auth.get_current_user)):
    return user


@app.get("/auth/users", response_model=list[UserOut])
def list_users(_: dict = Depends(auth.require_role("admin"))):
    return user_repository.list_users()


@app.patch("/auth/users/{user_id}", response_model=UserOut)
def set_user_role(
    user_id: int,
    payload: RoleUpdateIn,
    admin: dict = Depends(auth.require_role("admin")),
):
    target = user_repository.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    new_role = payload.role.value
    if (
        target["role"] == "admin"
        and new_role != "admin"
        and user_repository.count_admins() <= 1
    ):
        raise HTTPException(
            status_code=409, detail="Cannot demote the last administrator"
        )

    if target["role"] == new_role:
        return {k: target[k] for k in ("id", "email", "name", "role", "cpse")}

    updated = user_repository.set_role(user_id, new_role)

    audit_repository.write_audit(
        actor=admin["name"],
        action="user.role_changed",
        entity_type="user",
        entity_id=str(user_id),
        details={
            "email": updated["email"],
            "from": target["role"],
            "to": new_role,
        },
    )
    return updated


# ---------------------------------------------------------
# MATERIAL INGESTION
# ---------------------------------------------------------

@app.post(
    "/materials/ingest",
    response_model=list[StandardizedMaterial],
)
def ingest(
    items: list[MaterialIn],
    user: dict = Depends(auth.require_role("steward", "admin")),
):
    created = []

    existing_materials = get_all_materials()

    existing_keys = {
        (
            material["cpse"].lower(),
            material["local_code"].lower(),
        )
        for material in existing_materials
    }

    for item in items:
        key = (
            item.cpse.lower(),
            item.local_code.lower(),
        )

        if key in existing_keys:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Duplicate local code in CPSE: "
                    f"{item.cpse}/{item.local_code}"
                ),
            )

        data = item.model_dump()

        normalized = normalize_text(item.description)
        classification = classify(item.description, item.material_family, normalized)

        record = {
            **data,
            "normalized_description": normalized,
            "extracted_attributes": extract_attributes(
                item.description,
                item.attributes,
                item.material_family,
            ),
            "uom_code": (resolve_uom(item.uom) or {}).get("code"),
            "fsc": classification["fsc"],
            "fsc_title": classification["fsc_title"],
        }

        saved_record = insert_material(record)

        created.append(saved_record)

        existing_keys.add(key)

        audit_repository.write_audit(
            actor=_actor(user),
            action="material.ingested",
            entity_type="material",
            entity_id=str(saved_record["id"]),
            details={
                "cpse": saved_record["cpse"],
                "sector": saved_record.get("sector"),
                "local_code": saved_record["local_code"],
                "material_family": saved_record.get("material_family"),
                "fsc": saved_record.get("fsc"),
            },
        )

    return created


# ---------------------------------------------------------
# BULK MATERIAL UPLOAD  (CSV / XLSX — parsed client-side, posted in chunks)
# ---------------------------------------------------------
# Unlike /materials/ingest (used by the single "Add material" form, which is
# fine failing the whole call on one bad row), a bulk upload must keep going:
# each row is validated on its own and bad ones are reported back with a row
# number instead of aborting the batch.

_VALID_CATEGORIES = {
    "bearing", "cable", "valve", "fastener", "pipe", "motor", "plate",
    "electrical", "instrument", "gasket", "seal", "hose", "filter", "grease",
}


@app.post(
    "/materials/bulk-ingest",
    response_model=BulkIngestResult,
)
def bulk_ingest(
    rows: list[MaterialBulkRow],
    user: dict = Depends(auth.require_role("steward", "admin")),
):
    existing_materials = get_all_materials()
    existing_keys = {
        (m["cpse"].lower(), m["local_code"].lower()) for m in existing_materials
    }

    created = []
    errors = []

    for row in rows:
        missing = [
            label
            for value, label in (
                (row.cpse, "CPSE code"),
                (row.local_code, "Material code"),
                (row.description, "Material description"),
                (row.uom, "UOM"),
            )
            if not (value or "").strip()
        ]
        if missing:
            errors.append({
                "row": row.row,
                "cpse": row.cpse,
                "local_code": row.local_code,
                "reason": f"Missing {', '.join(missing)}",
            })
            continue

        if row.material_family and row.material_family.strip().lower() not in _VALID_CATEGORIES:
            errors.append({
                "row": row.row,
                "cpse": row.cpse,
                "local_code": row.local_code,
                "reason": f"Invalid category: {row.material_family}",
            })
            continue

        key = (row.cpse.lower(), row.local_code.lower())
        if key in existing_keys:
            errors.append({
                "row": row.row,
                "cpse": row.cpse,
                "local_code": row.local_code,
                "reason": "Duplicate local code in this CPSE",
            })
            continue

        description = row.description.strip()
        normalized = normalize_text(description)
        classification = classify(description, row.material_family, normalized)

        record = {
            "cpse": row.cpse.strip(),
            "sector": None,
            "local_code": row.local_code.strip(),
            "description": description,
            "material_family": (row.material_family or "").strip() or None,
            "manufacturer": (row.manufacturer or "").strip() or None,
            "manufacturer_part_no": (row.manufacturer_part_no or "").strip() or None,
            "uom": row.uom.strip(),
            "attributes": row.attributes,
            "normalized_description": normalized,
            "extracted_attributes": extract_attributes(
                description, row.attributes, row.material_family,
            ),
            "uom_code": (resolve_uom(row.uom) or {}).get("code"),
            "fsc": classification["fsc"],
            "fsc_title": classification["fsc_title"],
        }

        saved_record = insert_material(record)
        created.append(saved_record)
        existing_keys.add(key)

    if created or errors:
        audit_repository.write_audit(
            actor=_actor(user),
            action="material.bulk_imported",
            entity_type="material",
            entity_id="bulk",
            details={
                "total": len(rows),
                "created": len(created),
                "errors": len(errors),
            },
        )

    return {"total": len(rows), "created": created, "errors": errors}


# ---------------------------------------------------------
# STANDARDIZATION PREVIEW  (no write — powers the "Add material" form)
# ---------------------------------------------------------

@app.post("/materials/standardize", response_model=StandardizedPreview)
def standardize(
    item: MaterialIn,
    _: dict = Depends(auth.get_current_user),
):
    normalized = normalize_text(item.description)
    uom_standard = resolve_uom(item.uom)
    return {
        "normalized_description": normalized,
        "extracted_attributes": extract_attributes(
            item.description, item.attributes, item.material_family
        ),
        "normalized_uom": uom_standard["name"] if uom_standard else None,
        "resolved_family": resolve_family(item.material_family),
        "uom_standard": uom_standard,
        "classification": classify(item.description, item.material_family, normalized),
    }


# ---------------------------------------------------------
# LIST MATERIALS
# ---------------------------------------------------------

@app.get(
    "/materials",
    response_model=list[StandardizedMaterial],
)
def list_materials(_: dict = Depends(auth.get_current_user)):
    return get_all_materials()


# ---------------------------------------------------------
# MATERIAL ATTACHMENTS  (datasheets, drawings, photos — image / PDF / PPTX)
# ---------------------------------------------------------

_ALLOWED_ATTACHMENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
_MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024  # 15 MB — inline bytea, not an object store


@app.post(
    "/materials/{material_id}/attachments",
    response_model=AttachmentOut,
    status_code=201,
)
async def upload_attachment(
    material_id: int,
    file: UploadFile = File(...),
    user: dict = Depends(auth.require_role("steward", "admin")),
):
    if get_material(material_id) is None:
        raise HTTPException(status_code=404, detail="Material not found")

    content_type = file.content_type or ""
    if content_type not in _ALLOWED_ATTACHMENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Only images (PNG/JPEG/WEBP/GIF), PDF or PPTX files are accepted",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > _MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail="File too large — 15 MB limit")

    saved = attachment_repository.insert_attachment(
        material_id=material_id,
        filename=file.filename or "upload",
        content_type=content_type,
        data=data,
        uploaded_by=_actor(user),
    )

    audit_repository.write_audit(
        actor=_actor(user),
        action="material.attachment_added",
        entity_type="material",
        entity_id=str(material_id),
        details={
            "filename": saved["filename"],
            "content_type": content_type,
            "size_bytes": saved["size_bytes"],
        },
    )

    return saved


@app.get(
    "/materials/{material_id}/attachments",
    response_model=list[AttachmentOut],
)
def list_attachments(
    material_id: int,
    _: dict = Depends(auth.get_current_user),
):
    return attachment_repository.list_for_material(material_id)


@app.get("/attachments/{attachment_id}")
def download_attachment(
    attachment_id: int,
    _: dict = Depends(auth.get_current_user),
):
    row = attachment_repository.get_attachment(attachment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    inline = row["content_type"].startswith("image/") or row["content_type"] == "application/pdf"
    disposition = "inline" if inline else "attachment"

    return Response(
        content=bytes(row["data"]),
        media_type=row["content_type"],
        headers={"Content-Disposition": f'{disposition}; filename="{row["filename"]}"'},
    )


@app.delete("/attachments/{attachment_id}", status_code=204)
def remove_attachment(
    attachment_id: int,
    user: dict = Depends(auth.require_role("steward", "admin")),
):
    row = attachment_repository.get_attachment(attachment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    attachment_repository.delete_attachment(attachment_id)

    audit_repository.write_audit(
        actor=_actor(user),
        action="material.attachment_removed",
        entity_type="material",
        entity_id=str(row["material_id"]),
        details={"filename": row["filename"]},
    )


# ---------------------------------------------------------
# RUN MATERIAL MATCHING
# ---------------------------------------------------------

@app.post(
    "/matches/run",
    response_model=list[MatchCandidate],
)
def run_matching(
    threshold: float = 0.60,
    user: dict = Depends(auth.require_role("steward", "admin")),
):
    db_materials = get_all_materials()

    semantic_model = SemanticModel(
        [m["normalized_description"] for m in db_materials]
    )

    candidates: list[dict] = []

    for i, left in enumerate(db_materials):
        for right in db_materials[i + 1:]:

            # For our initial SIH MVP,
            # compare materials from different CPSEs.
            if (
                left["cpse"].lower()
                == right["cpse"].lower()
            ):
                continue

            score, explanation = compare_materials(
                left,
                right,
                semantic_model,
            )

            if score >= threshold:
                candidates.append(
                    {
                        "left_material_id": left["id"],
                        "right_material_id": right["id"],
                        "score": score,
                        "explanation": explanation,
                    }
                )

    match_repository.replace_pending_matches(candidates)

    audit_repository.write_audit(
        actor=_actor(user),
        action="matches.run",
        entity_type="match_batch",
        entity_id="-",
        details={
            "threshold": threshold,
            "candidates": len(candidates),
            "materials": len(db_materials),
        },
    )

    return match_repository.list_matches()


# ---------------------------------------------------------
# LIST MATCHES
# ---------------------------------------------------------

@app.get(
    "/matches",
    response_model=list[MatchCandidate],
)
def list_matches(_: dict = Depends(auth.get_current_user)):
    return match_repository.list_matches()


# ---------------------------------------------------------
# APPROVE / REJECT MATCH
# ---------------------------------------------------------

@app.post(
    "/matches/{match_id}/decision",
    response_model=DecisionResult,
)
def decide(
    match_id: int,
    payload: DecisionIn,
    user: dict = Depends(auth.require_role("steward", "admin")),
):
    if payload.decision == MatchStatus.pending:
        raise HTTPException(
            status_code=400,
            detail="Decision must be approved or rejected",
        )

    reviewer = payload.reviewer if not isinstance(user, dict) else user["name"]

    result = match_repository.apply_decision(
        match_id=match_id,
        decision=payload.decision.value,
        reviewer=reviewer,
        note=payload.note,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Match not found",
        )

    return result


# ---------------------------------------------------------
# LIST NATIONAL MATERIAL CODES
# ---------------------------------------------------------

@app.get(
    "/nmc",
    response_model=list[NMCRecord],
)
def list_nmc(_: dict = Depends(auth.get_current_user)):
    return nmc_repository.list_nmc()


# ---------------------------------------------------------
# AUDIT TRAIL
# ---------------------------------------------------------

@app.get(
    "/audit",
    response_model=list[AuditEntry],
)
def list_audit(limit: int = 100, _: dict = Depends(auth.get_current_user)):
    return audit_repository.list_audit(limit)


# ---------------------------------------------------------
# COLLABORATIVE PROCUREMENT
# ---------------------------------------------------------

@app.post(
    "/procurement/ingest",
    response_model=ProcurementImportResult,
)
def ingest_procurement(
    rows: list[ProcurementBulkRow],
    user: dict = Depends(auth.require_role("steward", "admin")),
):
    to_insert = []
    skipped = []

    for row in rows:
        missing = [
            label
            for value, label in (
                (row.cpse, "CPSE code"),
                (row.local_code, "Material code"),
                (row.order_date, "Order date"),
                (row.quantity, "Quantity"),
                (row.unit_price_inr, "Unit price"),
                (row.po_number, "PO number"),
            )
            if not (value or "").strip()
        ]
        if missing:
            skipped.append({
                "row": row.row,
                "cpse": row.cpse,
                "local_code": row.local_code,
                "reason": f"Missing {', '.join(missing)}",
            })
            continue

        try:
            order_date = date.fromisoformat(row.order_date.strip())
        except ValueError:
            skipped.append({
                "row": row.row,
                "cpse": row.cpse,
                "local_code": row.local_code,
                "reason": f"Invalid order date (expected YYYY-MM-DD): {row.order_date}",
            })
            continue

        try:
            quantity = float(row.quantity)
            unit_price_inr = float(row.unit_price_inr)
        except ValueError:
            skipped.append({
                "row": row.row,
                "cpse": row.cpse,
                "local_code": row.local_code,
                "reason": "Quantity and unit price must be numbers",
            })
            continue

        if quantity <= 0 or unit_price_inr <= 0:
            skipped.append({
                "row": row.row,
                "cpse": row.cpse,
                "local_code": row.local_code,
                "reason": "Quantity and unit price must be greater than zero",
            })
            continue

        material = get_material_by_cpse_code(row.cpse, row.local_code)
        if material is None:
            skipped.append({
                "row": row.row,
                "cpse": row.cpse,
                "local_code": row.local_code,
                "reason": "No matching material for this CPSE / material code",
            })
            continue

        to_insert.append(
            {
                "material_id": material["id"],
                "order_date": order_date,
                "quantity": quantity,
                "unit_price_inr": unit_price_inr,
                "po_number": row.po_number.strip(),
                "supplier": (row.supplier or "").strip() or None,
            }
        )

    imported = procurement_repository.insert_transactions(to_insert)

    if imported or skipped:
        audit_repository.write_audit(
            actor=_actor(user),
            action="procurement.imported",
            entity_type="procurement",
            entity_id="bulk",
            details={"imported": imported, "skipped": len(skipped)},
        )

    return {"imported": imported, "skipped": skipped}


@app.get(
    "/procurement/opportunities",
    response_model=list[ProcurementOpportunity],
)
def procurement_opportunities(_: dict = Depends(auth.get_current_user)):
    return procurement_repository.opportunities()


@app.post("/procurement/clear")
def clear_procurement(user: dict = Depends(auth.require_role("admin"))):
    """Wipe procurement transactions — used to drop the seeded demo/synthetic
    data before real uploads so the aggregation numbers aren't a mix of the
    two."""
    deleted = procurement_repository.clear_transactions()

    audit_repository.write_audit(
        actor=_actor(user),
        action="procurement.cleared",
        entity_type="procurement",
        entity_id="bulk",
        details={"deleted": deleted},
    )

    return {"deleted": deleted}


# ---------------------------------------------------------
# DASHBOARD STATISTICS
# ---------------------------------------------------------

@app.get("/stats", response_model=Stats)
def stats(_: dict = Depends(auth.get_current_user)):
    return stats_repository.get_stats()


# ---------------------------------------------------------
# DEMO RESET  (disabled unless MATERIAL_SETU_DEMO=1, the default)
# ---------------------------------------------------------

@app.post("/admin/reset")
def admin_reset(_: dict = Depends(auth.require_role("admin"))):
    if os.environ.get("MATERIAL_SETU_DEMO", "1") != "1":
        raise HTTPException(status_code=403, detail="Reset is disabled")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                TRUNCATE audit_log, nmc_crosswalk, national_materials,
                         match_candidates, procurement_transactions, materials
                         RESTART IDENTITY CASCADE
                """
            )

    return {"status": "reset"}
