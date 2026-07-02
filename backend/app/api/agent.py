"""AI planning API endpoints."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Query, status

from app.services.ai_planner import ai_planner
from app.services.foundry_agent import foundry_transit_agent
from app.services.transit_service import transit_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/agent/plan")
def plan_trip(destination: str = Query(..., min_length=2, description="Destination to search for")):
    """Return a simple trip-planning result for the requested destination."""
    try:
        if not transit_service.is_loaded:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GTFS data is not loaded yet.",
            )

        result = ai_planner.plan_trip(destination)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/agent/ask")
def ask_query(query: str = Query(..., min_length=1, description="Natural-language transit query")):
    """Answer a natural-language transit query using the planner service."""
    try:
        if not transit_service.is_loaded:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GTFS data is not loaded yet.",
            )

        return ai_planner.answer_query(query)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/agent/foundry")
def ask_foundry(query: Dict[str, Any] = Body(..., description="Foundry request payload")):
    """Route a natural-language transit question through the Foundry tool-calling service.

    This endpoint preserves the existing FastAPI routing pattern while invoking
    the Foundry-enabled service class for tool-calling and answer synthesis.
    """
    try:
        if not transit_service.is_loaded:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GTFS data is not loaded yet.",
            )

        user_query = query.get("query") if isinstance(query, dict) else None
        context = query.get("context") if isinstance(query, dict) else None
        intent = query.get("intent") if isinstance(query, dict) else None

        
        logger.warning("[FOUNDRY-API] query = %s", user_query)
        if context:
            logger.warning("[FOUNDRY-API] context keys = %s", list(context.keys()) if isinstance(context, dict) else "NOT_A_DICT")
            route = context.get('route', {}) if isinstance(context, dict) else {}
            logger.warning("[FOUNDRY-API] route keys = %s", list(route.keys()) if isinstance(route, dict) else "EMPTY")
            logger.warning("[FOUNDRY-API] has stopSequence = %s", 'stopSequence' in (context if isinstance(context, dict) else {}))
            if isinstance(context, dict) and 'stopSequence' in context:
                seq = context['stopSequence']
                logger.warning("[FOUNDRY-API] stopSequence length = %s", len(seq) if isinstance(seq, list) else "NOT_A_LIST")
                if isinstance(seq, list) and len(seq) > 0:
                    logger.warning("[FOUNDRY-API] stopSequence[0] = %s", seq[0])
        else:
            logger.warning("[FOUNDRY-API] context is None")
        
        if not isinstance(user_query, str) or not user_query.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query must be a non-empty string.")

        logger.warning("[FOUNDRY-API] calling foundry_transit_agent.answer()")
        result = foundry_transit_agent.answer(user_query, context=context, intent=intent)
        return {
            "answer": result.get("answer", "I could not generate a response."),
            "provider": result.get("provider", "foundry"),
            "classification": result.get("classification", "UNKNOWN"),
            "execution_time_ms": result.get("execution_time_ms", 0),
            "tools_used": result.get("tools_used", []),
            "route_data": result.get("route_data")
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
