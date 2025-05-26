# db_utils.py

from __future__ import annotations

import math
from datetime import datetime, timezone
import re
from typing import List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from sqlalchemy import MetaData, Table, literal_column, select, text, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    Observation,
    Proposition,
    proposition_parent,
    observation_proposition,
)

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
    """Search propositions by BM25 over *both* their own text and the
    text of the observations that support them.  Results are re‑ranked
    with a recency‑aware MMR strategy.
    
    Args:
        session: AsyncSession bound to the DB.
        user_query: Raw query string.
        limit: Max number of items to return.
        mode: "AND", "OR" or "PHRASE" interpreted by :func:`build_fts_query`.
        start_time: Only propositions **created_at ≥ start_time** (UTC).
        end_time: Only propositions **created_at ≤ end_time** (UTC, default *now*).
    Returns:
        List of ``(Proposition, relevance_score)`` pairs, highest relevance first.
    """
    q = build_fts_query(user_query, mode)
    if not q:
        return []

    # --------------------------------------------------------
    # 1  Build candidate list at SQL level
    # --------------------------------------------------------

    candidate_pool = max(limit * 10, limit)

    # Virtual FTS5 tables
    fts_prop = Table("propositions_fts", MetaData())
    fts_obs = Table("observations_fts", MetaData())

    # BM25 columns (lower is better)
    bm25_p = literal_column("bm25(propositions_fts)").label("score")
    bm25_o = literal_column("bm25(observations_fts)").label("score")

    # a) direct match against proposition text / reasoning
    join_cond = literal_column("propositions_fts.rowid") == Proposition.id
    sub_p = (
        select(Proposition.id.label("pid"), bm25_p)
        .select_from(fts_prop.join(Proposition, join_cond))
        .where(text("propositions_fts MATCH :q"))
    )

    # b) match against observation text, then map to proposition via link‑table
    sub_o = (
        select(observation_proposition.c.proposition_id.label("pid"), bm25_o)
        .select_from(
            fts_obs
            .join(Observation, literal_column("observations_fts.rowid") == Observation.id)
            .join(observation_proposition, observation_proposition.c.observation_id == Observation.id)
        )
        .where(text("observations_fts MATCH :q"))
    )

    # UNION‑ALL then take best (minimum) score for each proposition id
    union_sub = sub_p.union_all(sub_o).subquery()
    best_scores = (
        select(union_sub.c.pid.label("pid"), func.min(union_sub.c.score).label("bm25"))
        .group_by(union_sub.c.pid)
        .subquery()
    )

    has_child = _has_child_subquery()

    # Default time range
    if end_time is None:
        end_time = datetime.now(timezone.utc)

    if start_time is not None and start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    stmt = (
        select(Proposition, best_scores.c.bm25)
        .join(best_scores, best_scores.c.pid == Proposition.id)
        .where(~has_child)
    )

    if start_time is not None:
        stmt = stmt.where(Proposition.created_at >= start_time)
    stmt = stmt.where(Proposition.created_at <= end_time)

    stmt = (
        stmt.order_by(best_scores.c.bm25)
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
        # Ensure tz‑aware timestamp
        dt = prop.created_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        age_days = max((now - dt).total_seconds() / 86400, 0.0)
        alpha = prop.decay if prop.decay is not None else 0.0
        gamma = math.exp(-alpha * K_DECAY * age_days)

        r_eff = -raw_score * gamma  # BM25: lower is better → negate
        rel_scores.append(r_eff)

    docs: list[str] = []
    for p, _ in rows:
        obs_concat = " ".join(o.content for o in list(p.observations)[:10])
        docs.append(f"{p.text} {p.reasoning} {obs_concat}")

    vecs = TfidfVectorizer().fit_transform(docs)

    selected_idxs: List[int] = []
    final_scores:  List[float] = []

    while len(selected_idxs) < min(limit, len(rows)):
        if not selected_idxs:
            idx = int(np.argmax(rel_scores))
        else:
            sims = cosine_similarity(vecs, vecs[selected_idxs]).max(axis=1)
            mmr = LAMBDA * np.array(rel_scores) - (1 - LAMBDA) * sims
            mmr[selected_idxs] = -np.inf  # don’t repeat
            idx = int(np.argmax(mmr))
        selected_idxs.append(idx)
        final_scores.append(rel_scores[idx])

    return [(rows[i][0], final_scores[pos]) for pos, i in enumerate(selected_idxs)]

async def get_related_observations(
    session: AsyncSession,
    proposition_id: int,
    *,  # Force keyword arguments for optional parameters
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