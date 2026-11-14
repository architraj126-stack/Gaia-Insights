"""
Admin API endpoints — protected by ADMIN_TOKEN from .env.

POST /api/admin/catalog/refresh
  Triggers a catalogue refresh for all configured datasets (or one, if
  ?dataset_id=... is provided).  Returns a summary of changes.

Authentication: Bearer token or X-Admin-Token header, matched with
constant-time comparison to prevent timing attacks.
"""
from __future__ import annotations

import hmac
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.services.catalogue_refresh import refresh_all_datasets, refresh_one_dataset

logger = logging.getLogger("backend.api.admin")
router = APIRouter(prefix="/api/admin", tags=["Admin"])

_bearer_scheme = HTTPBearer(auto_error=False)


def _verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> None:
    """
    Constant-time comparison of the provided token against ADMIN_TOKEN.
    Raises HTTP 401 on mismatch or missing token.
    """
    token: Optional[str] = None
    if credentials:
        token = credentials.credentials

    configured_token = settings.ADMIN_TOKEN
    if not configured_token:
        raise HTTPException(
            status_code=503,
            detail="Admin token not configured on this server. Set ADMIN_TOKEN in .env.",
        )
    if token is None or not hmac.compare_digest(
        token.encode("utf-8"), configured_token.encode("utf-8")
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing admin token. Provide Authorization: Bearer <ADMIN_TOKEN>.",
        )


@router.post(
    "/catalog/refresh",
    summary="Refresh catalogue latest-observation metadata",
    response_model=Dict[str, Any],
    dependencies=[Depends(_verify_token)],
)
async def trigger_catalog_refresh(
    dataset_id: Optional[str] = Query(
        None,
        description="Optional dataset ID to refresh; omit to refresh all configured datasets.",
    ),
) -> Dict[str, Any]:
    """
    Opens each configured dataset's data source, reads its time coordinate,
    determines the latest COMPLETE monthly step, and updates the database.

    Two separate timestamps are stored per SPEC 15.3:
      latest_observation_date — date of the data's most recent complete step
      last_catalogue_check    — UTC wall-clock time of this refresh
    """
    async with get_db() as session:
        if dataset_id:
            result = await refresh_one_dataset(session, dataset_id)
            return {"refreshed": {dataset_id: result}}
        else:
            results = await refresh_all_datasets(session)
            return {"refreshed": results}
