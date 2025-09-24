# db_utils.py

from __future__ import annotations

import math
from datetime import datetime, timezone
import re
from typing import List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from sqlalchemy import MetaData, Table, literal_column, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Observation, Proposition, proposition_parent 

def build_fts_query(raw: str, mode: str = "OR") -> str:
    tokens = re.findall(r"\w+", raw.lower())
    if not tokens:
        return ""
    if mode == "PHRASE":
        return f'"{" ".join(tokens)}"'
    elif mode == "OR":
        return " OR ".join(tokens)
    else:                              # implicit AND
        return " ".join(tokens)

def _has_child_subquery() -> select:
    return (
        select(literal_column("1"))
        .select_from(proposition_parent)
        .where(proposition_parent.c.parent_id == Proposition.id)
        .exists()
    )

# constants
K_DECAY = 2.0     # decay rate for recency adjustment
LAMBDA = 0.5      # trade-off for MMR

async def search_propositions_bm25(
    session: AsyncSession,
    user_query: str,
    *,
    limit: int = 3,
    mode: str = "OR",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[tuple[Proposition, float]]:
    """    
    Args:
        session: AsyncSession for database operations
        user_query: Search query string
        limit: Maximum number of results to return
        mode: Search mode ("AND", "OR", or "PHRASE")
        start_time: Start of time range (UTC, inclusive)
        end_time: End of time range (UTC, inclusive, defaults to now)
    """
    q = build_fts_query(user_query, mode)
    if not q:
        return []

    candidate_pool = max(limit * 10, limit)

    fts       = Table("propositions_fts", MetaData())
    bm25_col  = literal_column("bm25(propositions_fts)").label("bm25")
    join_cond = literal_column("propositions_fts.rowid") == Proposition.id
    has_child = _has_child_subquery()

    # Set default end_time to now if not provided
    if end_time is None:
        end_time = datetime.now(timezone.utc)

    # Ensure both times are timezone-aware
    if start_time is not None and start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    stmt = (
        select(Proposition, bm25_col)
        .select_from(fts.join(Proposition, join_cond))
        .where(text("propositions_fts MATCH :q"))
        .where(~has_child)
    )

    # Add time range filtering
    if start_time is not None:
        stmt = stmt.where(Proposition.created_at >= start_time)
    stmt = stmt.where(Proposition.created_at <= end_time)

    stmt = (
        stmt.order_by(bm25_col)
        .options(selectinload(Proposition.observations))
        .limit(candidate_pool)
    )

    raw = await session.execute(stmt, {"q": q})
    rows = raw.all()
    if not rows:
        return []

    now = datetime.now(timezone.utc)
    rel_scores: List[float] = []
    for prop, raw_score in rows:

        dt = prop.created_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        age_days = max((now - dt).total_seconds() / 86400, 0.0)

        alpha = prop.decay if prop.decay is not None else 0.0
        gamma = math.exp(-alpha * K_DECAY * age_days)

        r_eff = -raw_score * gamma
        rel_scores.append(r_eff)

    docs = [f"{p.text} {p.reasoning}" for p, _ in rows]
    vecs = TfidfVectorizer().fit_transform(docs)

    # MMR selection
    selected_idxs: List[int] = []
    final_scores:  List[float] = []

    while len(selected_idxs) < min(limit, len(rows)):
        if not selected_idxs:
            idx = int(np.argmax(rel_scores))
            selected_idxs.append(idx)
            final_scores.append(rel_scores[idx])
            continue

        sims = cosine_similarity(vecs, vecs[selected_idxs]).max(axis=1)
        mmr_scores = (LAMBDA * np.array(rel_scores)
                      - (1 - LAMBDA) * sims)
        
        # never pick twice
        mmr_scores[selected_idxs] = -np.inf

        idx = int(np.argmax(mmr_scores))
        selected_idxs.append(idx)
        final_scores.append(float(mmr_scores[idx]))

    return [(rows[i][0], final_scores[pos])
            for pos, i in enumerate(selected_idxs)]

async def get_related_observations(
    session: AsyncSession,
    proposition_id: int,
    *, 
    limit: int = 5,
) -> List[Observation]:

    stmt = (
        select(Observation)
        .join(Observation.propositions)
        .where(Proposition.id == proposition_id)
        .order_by(Observation.created_at.desc())
        .limit(limit)  # Use the limit parameter
    )
    result = await session.execute(stmt)
    return result.scalars().all()