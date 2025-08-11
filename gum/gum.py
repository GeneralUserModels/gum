# gum.py

from __future__ import annotations

import asyncio
import json
import logging
import os
from uuid import uuid4
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Callable, List
from .models import observation_proposition

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert

from .db_utils import (
    get_related_observations,
    search_propositions_bm25,
)
from .models import Observation, Proposition, init_db
from .observers import Observer
from .schemas import (
    PropositionItem,
    PropositionSchema,
    RelationSchema,
    Update,
    AuditSchema
)
from gum.prompts.gum import AUDIT_PROMPT, PROPOSE_PROMPT, REVISE_PROMPT, SIMILAR_PROMPT

class gum:
    """A class for managing general user models.

    This class provides functionality for observing user behavior, generating and managing
    propositions about user behavior, and maintaining relationships between observations
    and propositions.

    The system uses a unified AI client that supports multiple providers:
    - Text completion: Azure OpenAI (default) or OpenAI (set TEXT_PROVIDER=openai)
    - Vision completion: OpenRouter (default)

    Args:
        user_name (str): The name of the user being modeled.
        *observers (Observer): Variable number of observer instances to track user behavior.
        propose_prompt (str, optional): Custom prompt for proposition generation.
        similar_prompt (str, optional): Custom prompt for similarity analysis.
        revise_prompt (str, optional): Custom prompt for proposition revision.
        audit_prompt (str, optional): Custom prompt for auditing.
        data_directory (str, optional): Directory for storing data. Defaults to "~/.cache/gum".
        db_name (str, optional): Name of the database file. Defaults to "gum.db".
        max_concurrent_updates (int, optional): Maximum number of concurrent updates. Defaults to 4.
        verbosity (int, optional): Logging verbosity level. Defaults to logging.INFO.
        audit_enabled (bool, optional): Whether to enable auditing. Defaults to False.
        api_base (str, optional): Deprecated, use environment variables instead.
        api_key (str, optional): Deprecated, use environment variables instead.
    """

    def __init__(
        self,
        user_name: str,
        model: str,
        *observers: Observer,
        propose_prompt: str | None = None,
        similar_prompt: str | None = None,
        revise_prompt: str | None = None,
        audit_prompt: str | None = None,
        data_directory: str = "~/.cache/gum",
        db_name: str = "gum.db",
        max_concurrent_updates: int = 4,
        verbosity: int = logging.INFO,
        audit_enabled: bool = False,
        api_base: str | None = None,
        api_key: str | None = None,
    ):
        # basic paths
        data_directory = os.path.expanduser(data_directory)
        os.makedirs(data_directory, exist_ok=True)

        # runtime
        self.user_name = user_name
        self.observers: list[Observer] = list(observers)
        self.model = model
        self.audit_enabled = audit_enabled

        # logging
        self.logger = logging.getLogger("gum")
        self.logger.setLevel(verbosity)
        if not self.logger.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            self.logger.addHandler(h)

        # prompts - use default prompts from gum.py, or load from files if custom methods are added
        self.propose_prompt = propose_prompt or PROPOSE_PROMPT
        self.similar_prompt = similar_prompt or SIMILAR_PROMPT
        self.revise_prompt = revise_prompt or REVISE_PROMPT
        self.audit_prompt = audit_prompt or AUDIT_PROMPT

        # Initialize unified AI client (supports Azure OpenAI, OpenAI, and OpenRouter)
        self.ai_client = None  # Will be initialized lazily

        self.engine = None
        self.Session = None
        self._db_name        = db_name
        self._data_directory = data_directory

        self._update_sem = asyncio.Semaphore(max_concurrent_updates)
        self._tasks: set[asyncio.Task] = set()
        self._loop_task: asyncio.Task | None = None
        self.update_handlers: list[Callable[[Observer, Update], None]] = []

    async def _get_ai_client(self):
        """Get the unified AI client, initializing it if needed."""
        if self.ai_client is None:
            # Import here to avoid circular imports
            from gum.unified_ai_client import get_unified_client
            self.ai_client = await get_unified_client()
            self.logger.info("Unified AI client initialized for GUM")
        return self.ai_client

    def _parse_ai_json_response(self, response_content: str, expected_key: str = None):
        """Parse JSON from AI response content with fallback handling."""
        
        # Add detailed logging for debugging
        self.logger.info(f"JSON Parsing Debug - Input Analysis:")
        self.logger.info(f"   Response length: {len(response_content)} characters")
        self.logger.info(f"   Expected key: {expected_key}")
        self.logger.info(f"   Raw response (first 300 chars): {response_content[:300]}...")
        self.logger.info(f"   Raw response (last 100 chars): ...{response_content[-100:]}")
        
        try:
            # Try to parse the response as JSON directly
            self.logger.info("Attempting direct JSON parsing...")
            parsed_response = json.loads(response_content)
            self.logger.info(f"Direct JSON parsing successful!")
            self.logger.info(f"   Parsed keys: {list(parsed_response.keys()) if isinstance(parsed_response, dict) else 'Not a dict'}")
            
            if expected_key and expected_key in parsed_response:
                self.logger.info(f"Found expected key '{expected_key}' in response")
                return parsed_response[expected_key]
            return parsed_response
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"Direct JSON parsing failed: {e}")
            
            # Try to extract JSON from markdown code blocks first
            import re
            
            self.logger.info("Attempting markdown JSON extraction...")
            # Look for JSON in markdown code blocks - handle both complete and truncated blocks
            markdown_match = re.search(r'```(?:json)?\s*(.*?)(?:```|\Z)', response_content, re.DOTALL)
            if markdown_match:
                json_content = markdown_match.group(1).strip()
                self.logger.info(f"Extracted JSON from markdown (length: {len(json_content)}):")
                self.logger.info(f"   Extracted content: {json_content}")
                
                # Try to parse the extracted content as-is first
                try:
                    parsed_response = json.loads(json_content)
                    self.logger.info(f"Markdown JSON parsing successful!")
                    self.logger.info(f"   Parsed keys: {list(parsed_response.keys()) if isinstance(parsed_response, dict) else 'Not a dict'}")
                    
                    if expected_key and expected_key in parsed_response:
                        self.logger.info(f"Found expected key '{expected_key}' in markdown JSON")
                        return parsed_response[expected_key]
                    return parsed_response
                    
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse extracted JSON as-is: {e}")
                    
                    # Try to repair truncated JSON by finding the last complete object
                    self.logger.info("Attempting to repair truncated JSON...")
                    
                    # Find the last complete JSON object/array
                    brace_count = 0
                    bracket_count = 0
                    last_complete_pos = -1
                    
                    for i, char in enumerate(json_content):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                        elif char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                            
                        # Check if we have a complete structure
                        if brace_count == 0 and bracket_count == 0 and i > 0:
                            last_complete_pos = i + 1
                    
                    if last_complete_pos > 0:
                        repaired_json = json_content[:last_complete_pos]
                        self.logger.info(f"Attempting repair with content up to position {last_complete_pos}")
                        self.logger.info(f"   Repaired JSON: {repaired_json}")
                        
                        try:
                            parsed_response = json.loads(repaired_json)
                            self.logger.info(f"Repaired JSON parsing successful!")
                            self.logger.info(f"   Parsed keys: {list(parsed_response.keys()) if isinstance(parsed_response, dict) else 'Not a dict'}")
                            
                            if expected_key and expected_key in parsed_response:
                                self.logger.info(f"Found expected key '{expected_key}' in repaired JSON")
                                return parsed_response[expected_key]
                            return parsed_response
                            
                        except json.JSONDecodeError as e2:
                            self.logger.error(f"Repair attempt also failed: {e2}")
                    else:
                        self.logger.warning("Could not find a complete JSON structure to repair")
                        
            else:
                self.logger.warning("No markdown code blocks found")
            
            # Fallback: look for any JSON-like structure
            self.logger.info("Attempting fallback JSON pattern matching...")
            json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
            if json_match:
                json_candidate = json_match.group(0)
                self.logger.info(f"Found JSON-like pattern (length: {len(json_candidate)}):")
                self.logger.info(f"   JSON candidate: {json_candidate}")
                
                try:
                    parsed_response = json.loads(json_candidate)
                    self.logger.info(f"Fallback JSON parsing successful!")
                    self.logger.info(f"   Parsed keys: {list(parsed_response.keys()) if isinstance(parsed_response, dict) else 'Not a dict'}")
                    
                    if expected_key and expected_key in parsed_response:
                        self.logger.info(f"Found expected key '{expected_key}' in fallback JSON")
                        return parsed_response[expected_key]
                    return parsed_response
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"Fallback JSON parsing also failed: {e}")
                    self.logger.error(f"   Problematic content: {json_candidate}")
            else:
                self.logger.warning("No JSON-like patterns found")
            
            # If JSON parsing fails, log the response and return appropriate default
            self.logger.error(f"ALL JSON parsing methods failed!")
            self.logger.error(f"   Full response content:")
            self.logger.error(f"   {response_content}")
            
            if expected_key == "propositions":
                self.logger.info("Returning empty list for propositions")
                return []
            else:
                self.logger.info("Returning empty dict")
                return {}

    def start_update_loop(self):
        """Start the asynchronous update loop for processing observer updates."""
        if self._loop_task is None:
            self._loop_task = asyncio.create_task(self._update_loop())

    async def stop_update_loop(self):
        """Stop the asynchronous update loop and clean up resources."""
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None

    async def connect_db(self):
        """Initialize the database connection if not already connected."""
        if self.engine is None:
            self.engine, self.Session = await init_db(
                self._db_name, self._data_directory
            )

    async def __aenter__(self):
        """Async context manager entry point.
        
        Returns:
            gum: The instance of the gum class.
        """
        await self.connect_db()
        self.start_update_loop()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Async context manager exit point.
        
        Args:
            exc_type: The type of exception if any.
            exc: The exception instance if any.
            tb: The traceback if any.
        """
        await self.stop_update_loop()

        # wait for any in-flight handlers
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # stop observers
        for obs in self.observers:
            await obs.stop()

    async def _update_loop(self):
        """Efficiently wait for any observer to produce an Update and dispatch it.
        
        This method continuously monitors all observers for updates and processes them
        through the semaphore-guarded handler.
        """
        while True:
            gets = {
                asyncio.create_task(obs.update_queue.get()): obs
                for obs in self.observers
            }

            done, _ = await asyncio.wait(
                gets.keys(), return_when=asyncio.FIRST_COMPLETED
            )

            for fut in done:
                upd: Update = fut.result()
                obs = gets[fut]

                t = asyncio.create_task(self._run_with_gate(obs, upd))
                self._tasks.add(t)

    async def _run_with_gate(self, observer: Observer, update: Update):
        """Wrapper that enforces max_concurrent_updates.
        
        Args:
            observer (Observer): The observer that generated the update.
            update (Update): The update to process.
        """
        async with self._update_sem:
            try:
                await self._default_handler(observer, update)
            finally:
                self._tasks.discard(asyncio.current_task())

    async def _construct_propositions(self, update: Update) -> list[PropositionItem]:
        """Generate propositions from an update.
        
        Args:
            update (Update): The update to generate propositions from.
            
        Returns:
            list[PropositionItem]: List of generated propositions.
        """
        prompt = (
            self.propose_prompt.replace("{user_name}", self.user_name)
            .replace("{inputs}", update.content)
        )

        # Get the unified AI client
        client = await self._get_ai_client()
        
        # Make the API call using the unified client
        response_content = await client.text_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.1
        )

        # Parse the JSON response
        return self._parse_ai_json_response(response_content, "propositions")

    async def _build_relation_prompt(self, all_props) -> str:
        """Build a prompt for analyzing relationships between propositions.
        
        Args:
            all_props: List of propositions to analyze.
            
        Returns:
            str: The formatted prompt for relationship analysis.
        """
        blocks = [
            f"[id={p['id']}] {p['proposition']}\n    Reasoning: {p['reasoning']}"
            for p in all_props
        ]
        body = "\n\n".join(blocks)
        return self.similar_prompt.replace("{body}", body)

    async def _filter_propositions(
        self, rel_props: list[Proposition]
    ) -> tuple[list[Proposition], list[Proposition], list[Proposition]]:
        """Filter propositions into identical, similar, and unrelated groups.
        
        Args:
            rel_props (list[Proposition]): List of propositions to filter.
            
        Returns:
            tuple[list[Proposition], list[Proposition], list[Proposition]]: Three lists containing
                identical, similar, and unrelated propositions respectively.
        """
        if not rel_props:
            return [], [], []

        payload = [
            {"id": p.id, "proposition": p.text, "reasoning": p.reasoning or ""}
            for p in rel_props
        ]
        prompt_text = await self._build_relation_prompt(payload)

        # Get the unified AI client
        client = await self._get_ai_client()
        
        # Make the API call using the unified client
        response_content = await client.text_completion(
            messages=[{"role": "user", "content": prompt_text}],
            max_tokens=2000,
            temperature=0.1
        )

        # Parse the JSON response and validate
        try:
            relations_data = self._parse_ai_json_response(response_content, "relations")
            data = RelationSchema.model_validate({"relations": relations_data})
        except Exception as e:
            self.logger.error(f"Failed to parse relation data: {e}")
            # Return empty groups if parsing fails
            return [], [], []

        id_to_prop = {p.id: p for p in rel_props}
        ident, sim, unrel = set(), set(), set()

        for r in data.relations:
            if r.label == "IDENTICAL":
                ident.add(r.source)
                ident.update(r.target or [])
            elif r.label == "SIMILAR":
                sim.add(r.source)
                sim.update(r.target or [])
            else:
                unrel.add(r.source)

        # only keep IDs we actually know about
        valid_ids = set(id_to_prop.keys())
        ident &= valid_ids
        sim &= valid_ids
        unrel &= valid_ids

        return (
            [id_to_prop[i] for i in ident],
            [id_to_prop[i] for i in sim - ident],
            [id_to_prop[i] for i in unrel - ident - sim],
        )

    async def _build_revision_body(
        self, similar: List[Proposition], related_obs: List[Observation]
    ) -> str:
        """Build the body text for proposition revision.
        
        Args:
            similar (List[Proposition]): List of similar propositions.
            related_obs (List[Observation]): List of related observations.
            
        Returns:
            str: The formatted body text for revision.
        """
        blocks = [
            f"Proposition {idx}: {p.text}\nReasoning: {p.reasoning}"
            for idx, p in enumerate(similar, 1)
        ]
        if related_obs:
            blocks.append("\nSupporting observations:")
            blocks.extend(f"- {o.content}" for o in related_obs[:10])
        return "\n".join(blocks)

    async def _revise_propositions(
        self,
        related_obs: list[Observation],
        similar_cluster: list[Proposition],
    ) -> list[dict]:
        """Revise propositions based on related observations and similar propositions.
        
        Args:
            related_obs (list[Observation]): List of related observations.
            similar_cluster (list[Proposition]): List of similar propositions.
            
        Returns:
            list[dict]: List of revised propositions.
        """
        body = await self._build_revision_body(similar_cluster, related_obs)
        prompt = self.revise_prompt.replace("{body}", body).replace("{user_name}", self.user_name)
        
        # Get the unified AI client
        client = await self._get_ai_client()
        
        # Make the API call using the unified client
        response_content = await client.text_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.1
        )

        # Parse the JSON response
        return self._parse_ai_json_response(response_content, "propositions")

    async def _generate_and_search(
        self, session: AsyncSession, update: Update, obs: Observation
    ) -> list[Proposition]:

        drafts_raw = await self._construct_propositions(update)
        drafts: list[Proposition] = []
        pool: dict[int, Proposition] = {}

        for itm in drafts_raw:
            draft = Proposition(
                text=itm["proposition"],
                reasoning=itm["reasoning"],
                confidence=itm.get("confidence"),
                decay=itm.get("decay"),
                revision_group=str(uuid4()),
                version=1,
            )
            drafts.append(draft)

            # search existing persisted props
            with session.no_autoflush:
                hits = await search_propositions_bm25(
                    session, f"{draft.text}\n{draft.reasoning}", mode="OR",
                    include_observations=False,
                    enable_mmr=True,
                    enable_decay=True
                )
                
            for prop, _score in hits:
                pool[prop.id] = prop

        session.add_all(drafts)
        await session.flush()

        for draft in drafts:
            pool[draft.id] = draft

        return list(pool.values())

    async def _handle_identical(
        self, session, identical: list[Proposition], obs: Observation
    ) -> None:
        for p in identical:
            await self._attach_obs_if_missing(p, obs, session)

    async def _handle_similar(
        self,
        session: AsyncSession,
        similar: list[Proposition],
        obs: Observation,
    ) -> None:

        if not similar:
            return

        rel_obs = {
            o
            for p in similar
            for o in await get_related_observations(session, p.id)
        }
        rel_obs.add(obs)

        revised_items = await self._revise_propositions(list(rel_obs), similar)
        newest_version = max(p.version for p in similar)
        parent_groups = {p.revision_group for p in similar}
        if len(parent_groups) == 1:
            revision_group = parent_groups.pop()
        else:
            revision_group = uuid4().hex

        new_children: list[Proposition] = []
        for item in revised_items:
            child = Proposition(
                text=item["proposition"],
                reasoning=item["reasoning"],
                confidence=item.get("confidence"),
                decay=item.get("decay"),
                version=newest_version + 1,
                revision_group=revision_group,
                observations=rel_obs,
                parents=set(similar),
            )
            session.add(child)
            new_children.append(child)

        await session.flush()

    async def _handle_different(
        self, session, different: list[Proposition], obs: Observation
    ) -> None:
        for p in different:
            await self._attach_obs_if_missing(p, obs, session)

    async def _handle_audit(self, obs: Observation) -> bool:
        if not self.audit_enabled:
            return False

        hits = await self.query(obs.content, limit=10, mode="OR")

        if not hits:
            past_interaction = "*None*"
        else:
            ctx_chunks: list[str] = []
            async with self._session() as session:
                for prop, score in hits:
                    chunk = [f"• {prop.text}"]
                    if prop.reasoning:
                        chunk.append(f"  Reasoning: {prop.reasoning}")
                    if prop.confidence is not None:
                        chunk.append(f"  Confidence: {prop.confidence}")
                    chunk.append(f"  Relevance Score: {score:.2f}")

                    obs_list = await get_related_observations(session, prop.id)
                    if obs_list:
                        chunk.append("  Supporting Observations:")
                        for rel_obs in obs_list:
                            preview = rel_obs.content.replace("\n", " ")[:120]
                            chunk.append(f"    - [{rel_obs.observer_name}] {preview}")

                    ctx_chunks.append("\n".join(chunk))

            past_interaction = "\n\n".join(ctx_chunks)

        prompt = (
            self.audit_prompt
            .replace("{past_interaction}", past_interaction)
            .replace("{user_input}", obs.content)
            .replace("{user_name}", self.user_name)
        )

        # Get the unified AI client
        client = await self._get_ai_client()
        
        # Make the API call using the unified client
        response_content = await client.text_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.0
        )

        # Parse the JSON response
        decision = self._parse_ai_json_response(response_content)
        
        # Safely handle the decision with fallbacks
        transmit_data = decision.get("transmit_data", True) if isinstance(decision, dict) else True
        data_type = decision.get("data_type", "Unknown") if isinstance(decision, dict) else "Unknown"
        subject = decision.get("subject", "Unknown") if isinstance(decision, dict) else "Unknown"

        if not transmit_data:
            self.logger.warning(
                "Audit blocked transmission (data_type=%s, subject=%s)",
                data_type,
                subject,
            )
            return True

        return False

    async def _default_handler(self, observer: Observer, update: Update) -> None:
        self.logger.info(f"Processing update from {observer.name}")

        async with self._session() as session:
            observation = Observation(
                observer_name=observer.name,
                content=update.content,
                content_type=update.content_type,
            )

            if await self._handle_audit(observation):
                return

            session.add(observation)
            await session.flush() # Observation gets its ID

            pool = await self._generate_and_search(session, update, observation)

            if pool:
                self.logger.info(f"Linking observation to {len(pool)} candidate propositions.")
                for prop in pool:
                    await self._attach_obs_if_missing(prop, observation, session)
                await session.flush()

            identical, similar, different = await self._filter_propositions(pool)

            self.logger.info("Applying proposition updates...")
            await self._handle_identical(session, identical, observation)
            await self._handle_similar(session, similar, observation)
            await self._handle_different(session, different, observation)
            self.logger.info("Completed processing update")

    @asynccontextmanager
    async def _session(self):
        async with self.Session() as s:
            async with s.begin():
                yield s

    @staticmethod
    async def _attach_obs_if_missing(prop: Proposition, obs: Observation, session):
        await session.execute(
            insert(observation_proposition)
            .prefix_with("OR IGNORE")
            .values(observation_id=obs.id, proposition_id=prop.id)
        )
        prop.updated_at = datetime.now(timezone.utc)

    def add_observer(self, observer: Observer):
        """Add an observer to track user behavior.
        
        Args:
            observer (Observer): The observer to add.
        """
        self.observers.append(observer)

    def remove_observer(self, observer: Observer):
        """Remove an observer from tracking.
        
        Args:
            observer (Observer): The observer to remove.
        """
        if observer in self.observers:
            self.observers.remove(observer)

    def register_update_handler(self, fn: Callable[[Observer, Update], None]):
        """Register a custom update handler function.
        
        Args:
            fn (Callable[[Observer, Update], None]): The handler function to register.
        """
        self.update_handlers.append(fn)

    async def query(
        self,
        user_query: str,
        *,
        limit: int = 3,
        mode: str = "OR",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[tuple[Proposition, float]]:
        """Query the database for propositions matching the user query.
        
        Args:
            user_query (str): The query string to search for.
            limit (int, optional): Maximum number of results to return. Defaults to 3.
            mode (str, optional): Search mode ("OR" or "AND"). Defaults to "OR".
            start_time (datetime, optional): Start time for filtering results. Defaults to None.
            end_time (datetime, optional): End time for filtering results. Defaults to None.
            
        Returns:
            list[tuple[Proposition, float]]: List of tuples containing propositions and their relevance scores.
        """
        async with self._session() as session:
            return await search_propositions_bm25(
                session,
                user_query,
                limit=limit,
                mode=mode,
                start_time=start_time,
                end_time=end_time,
            )
