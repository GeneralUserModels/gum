# db_utils.py

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from sqlalchemy import (
    MetaData,
    Table,
    select,
    literal_column,
    text,
    func,
)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    Observation,
    Proposition,
    observation_proposition,
)

# Constants
K_DECAY = 2.0      # decay rate for recency adjustment
LAMBDA = 0.5       # trade-off for MMR

def build_fts_query(raw: str, mode: str = "OR") -> str:
    tokens = re.findall(r"\w+", raw.lower())
    if not tokens:
        return ""
    if mode == "PHRASE":
        return f'"{" ".join(tokens)}"'
    elif mode == "OR":
        return " OR ".join(tokens)
    else:  # implicit AND
        return " ".join(tokens)




async def search_propositions_bm25(
    session: AsyncSession,
    user_query: str,
    *,
    limit: int = 3,
    mode: str = "OR",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    include_observations: bool = True,
    enable_decay: bool = True,
    enable_mmr: bool = True,
) -> list[tuple["Proposition", float]]:

    q = build_fts_query(user_query, mode)
    has_query = bool(q)

    # --------------------------------------------------------
    # 1  Build candidate list
    # --------------------------------------------------------
    candidate_pool = limit * 10 if enable_mmr else limit

    if has_query:
        fts_prop = Table("propositions_fts", MetaData())

        if include_observations:
            # --- 1-a-1  WITH observations --------------------
            fts_obs  = Table("observations_fts", MetaData())

            bm25_p   = literal_column("bm25(propositions_fts)").label("score")
            bm25_o   = literal_column("bm25(observations_fts)").label("score")

            sub_p = (
                select(Proposition.id.label("pid"), bm25_p)
                .select_from(
                    fts_prop.join(
                        Proposition,
                        literal_column("propositions_fts.rowid") == Proposition.id,
                    )
                )
                .where(text("propositions_fts MATCH :q"))
            )

            sub_o = (
                select(observation_proposition.c.proposition_id.label("pid"), bm25_o)
                .select_from(
                    fts_obs
                    .join(
                        Observation,
                        literal_column("observations_fts.rowid") == Observation.id,
                    )
                    .join(
                        observation_proposition,
                        observation_proposition.c.observation_id == Observation.id,
                    )
                )
                .where(text("observations_fts MATCH :q"))
            )

            union_sub = sub_p.union_all(sub_o).subquery()

            best_scores = (
                select(
                    union_sub.c.pid,
                    func.min(union_sub.c.score).label("bm25"),
                )
                .group_by(union_sub.c.pid)
                .subquery()
            )
        else:
            # --- 1-a-2  WITHOUT observations -----------------
            best_scores = (
                select(
                    Proposition.id.label("pid"),
                    literal_column("bm25(propositions_fts)").label("bm25"),
                )
                .select_from(
                    fts_prop.join(
                        Proposition,
                        literal_column("propositions_fts.rowid") == Proposition.id,
                    )
                )
                .where(text("propositions_fts MATCH :q"))
                .subquery()
            )

        stmt = (
            select(Proposition, best_scores.c.bm25)
            .join(best_scores, best_scores.c.pid == Proposition.id)
            .order_by(best_scores.c.bm25.asc())          # smallest→best
        )
    else:
        # --- 1-b  No user query ------------------------------
        stmt = (
            select(Proposition, literal_column("0.0").label("bm25"))
            .order_by(Proposition.created_at.desc())
        )

    # --------------------------------------------------------
    # 2  Time filtering & eager-load
    # --------------------------------------------------------
    if end_time is None:
        end_time = datetime.now(timezone.utc)
    if start_time is not None and start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    if start_time is not None:
        stmt = stmt.where(Proposition.created_at >= start_time)
    stmt = stmt.where(Proposition.created_at <= end_time)

    if include_observations:
        stmt = stmt.options(selectinload(Proposition.observations))

    stmt = stmt.limit(candidate_pool)

   # --------------------------------------------------------
    # 3  Execute & score
    # --------------------------------------------------------
    bind = {"q": q} if has_query else {}
    rows = (await session.execute(stmt, bind)).all()
    if not rows:
        return []

    # --- 3-a. Calculate initial scores ---
    initial_scores: list[float] = []
    now = datetime.now(timezone.utc)
    for prop, raw_score in rows:
        relevance_score = -raw_score if has_query else 0.0
        gamma = 0.0
        if enable_decay:
            dt = prop.created_at.replace(tzinfo=timezone.utc)
            age_days = max((now - dt).total_seconds() / 86_400, 0.0)
            alpha = prop.decay if prop.decay is not None else 0.0
            gamma = -alpha * K_DECAY * age_days

        score = relevance_score * math.exp(gamma)
        initial_scores.append(score)

    final_scores_np = np.array(initial_scores)
    min_score = np.min(final_scores_np)
    max_score = np.max(final_scores_np)
    
    if max_score > min_score:
        final_scores_np = (final_scores_np - min_score) / (max_score - min_score)
    else:
        final_scores_np = np.full_like(final_scores_np, 0.5)

    final_scores = final_scores_np.tolist()

    if enable_mmr and len(rows) > 1:
        docs: list[str] = []
        for p, _ in rows:
            doc_parts = [p.text, p.reasoning]
            if include_observations and p.observations:
                obs_concat = " ".join(o.content for o in list(p.observations)[:10])
                doc_parts.append(obs_concat)
            docs.append(" ".join(doc_parts))

        vecs = TfidfVectorizer().fit_transform(docs)
        
        selected_idxs = []
        mmr_scores = np.array(final_scores)

        while len(selected_idxs) < min(limit, len(rows)):
            if not selected_idxs:
                idx = int(np.argmax(mmr_scores))
            else:
                sims = cosine_similarity(vecs, vecs[selected_idxs]).max(axis=1)
                mmr = LAMBDA * mmr_scores - (1 - LAMBDA) * sims
                mmr[selected_idxs] = -np.inf 
                idx = int(np.argmax(mmr))

            selected_idxs.append(idx)
    else:
        idxs = np.argsort(final_scores)[::-1][:limit]
        selected_idxs = idxs.tolist()

    result = [(rows[i][0], final_scores[i]) for i in selected_idxs]    
    return result

async def get_related_observations(
    session: AsyncSession,
    proposition_id: int,
    *,  # Force keyword arguments for optional parameters
    limit: int = 5,
) -> List[Observation]:

    stmt = (
        select(Observation)
        .join(observation_proposition)
        .join(Proposition)
        .where(Proposition.id == proposition_id)
        .order_by(Observation.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_related_propositions(
    session: AsyncSession,
    observation_id: int,
    *,  # Force keyword arguments for optional parameters
    limit: int | None = None,
) -> List[Proposition]:
    """
    Get propositions related to a specific observation.
    
    Args:
        session: Database session
        observation_id: ID of the observation
        limit: Optional limit on number of propositions to return
        
    Returns:
        List of related Proposition objects
    """
    stmt = (
        select(Proposition)
        .join(observation_proposition)
        .join(Observation)
        .where(Observation.id == observation_id)
        .order_by(Proposition.created_at.desc())
    )
    
    if limit is not None:
        stmt = stmt.limit(limit)
    
    result = await session.execute(stmt)
    return result.scalars().all()


async def search_observations_bm25(
    session: AsyncSession,
    user_query: str,
    *,
    limit: int = 5,
    mode: str = "OR",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[tuple[Observation, float]]:
    """
    Search observations directly using BM25.
    
    Args:
        session: Database session
        user_query: Query string to search for
        limit: Maximum number of results to return
        mode: Search mode ("OR", "AND", or "PHRASE")
        start_time: Filter observations after this time
        end_time: Filter observations before this time
        
    Returns:
        List of (Observation, score) tuples
    """
    q = build_fts_query(user_query, mode)
    if not q:
        return []
    
    fts_obs = Table("observations_fts", MetaData())
    
    # Build BM25 query for observations
    stmt = (
        select(
            Observation,
            literal_column("bm25(observations_fts)").label("bm25")
        )
        .select_from(
            fts_obs.join(
                Observation,
                literal_column("observations_fts.rowid") == Observation.id,
            )
        )
        .where(text("observations_fts MATCH :q"))
        .order_by(literal_column("bm25").asc())  # smallest = best
        .limit(limit * 2)  # Get more candidates for filtering
    )
    
    # Apply time filters if provided
    if start_time:
        stmt = stmt.where(Observation.created_at >= start_time)
    if end_time:
        stmt = stmt.where(Observation.created_at <= end_time)
    
    result = await session.execute(stmt, {"q": q})
    rows = result.all()
    
    if not rows:
        return []
    
    # Convert BM25 scores to similarity scores (invert and normalize)
    observations = [(row[0], row[1]) for row in rows]
    bm25_scores = np.array([score for _, score in observations])
    
    # Normalize scores (smaller BM25 = better, so invert)
    if len(bm25_scores) > 0:
        max_score = bm25_scores.max()
        min_score = bm25_scores.min()
        if max_score != min_score:
            normalized = 1 - (bm25_scores - min_score) / (max_score - min_score)
        else:
            normalized = np.ones_like(bm25_scores)
    else:
        normalized = bm25_scores
    
    # Return top results
    result_list = [(observations[i][0], float(normalized[i])) for i in range(len(observations))]
    return result_list[:limit]