#!/usr/bin/env python3
"""
Simple GUM Notification Module
Integrates with GUM's batching pipeline and uses BM25 for similarity search.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import json
from pathlib import Path

from .db_utils import search_propositions_bm25, search_observations_bm25, get_related_propositions
from .models import Observation, Proposition
from .prompts.gum import NOTIFICATION_DECISION_PROMPT
import re


@dataclass
class NotificationContext:
    """Context for a notification decision."""
    timestamp: str
    observation_content: str
    observation_id: Optional[int]
    generated_propositions: List[Dict[str, Any]]  # Propositions generated from this observation
    similar_propositions: List[Dict[str, Any]]    # Similar propositions found via BM25
    similar_observations: List[Dict[str, Any]]    # Similar observations found via BM25
    
@dataclass
class NotificationDecision:
    """LLM decision about whether to notify."""
    should_notify: bool
    relevance_score: float
    urgency_score: float
    impact_score: float
    reasoning: str
    notification_message: str
    notification_type: str


class GUMNotifier:
    """Simple notification system that uses BM25 to find similar propositions and observations."""
    
    def __init__(self, user_name: str, gum_instance=None):
        """
        Initialize the notifier.
        
        Args:
            user_name: Name of the user
            gum_instance: Reference to the GUM instance for database access
        """
        self.user_name = user_name
        self.gum_instance = gum_instance
        self.logger = logging.getLogger("gum.notifier")
        
        # Notification log
        self.notification_contexts: List[NotificationContext] = []
        self.sent_notifications: List[Dict[str, Any]] = []
        self.decisions_log: List[Dict[str, Any]] = []
        self.contexts_file = Path(f"notification_contexts_{user_name.lower().replace(' ', '_')}.json")
        self.decisions_file = Path(f"notification_decisions_{user_name.lower().replace(' ', '_')}.json")
        
        # Load existing contexts if available
        self._load_notification_log()
    
    def _load_notification_log(self):
        """Load notification contexts from file."""
        if self.contexts_file.exists():
            try:
                with open(self.contexts_file, 'r') as f:
                    data = json.load(f)
                    self.notification_contexts = [NotificationContext(**entry) for entry in data]
                self.logger.info(f"Loaded {len(self.notification_contexts)} notification contexts")
            except Exception as e:
                self.logger.error(f"Error loading notification log: {e}")
                self.notification_contexts = []
    
    def _save_notification_log(self):
        """Save notification contexts to file."""
        try:
            data = [asdict(ctx) for ctx in self.notification_contexts]
            with open(self.contexts_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving notification log: {e}")
    
    def _save_decision(self, context: NotificationContext, decision: NotificationDecision):
        """Save a notification decision to separate file for GUI."""
        try:
            decision_entry = {
                'timestamp': context.timestamp,
                'observation_id': context.observation_id,
                'should_notify': decision.should_notify,
                'relevance_score': decision.relevance_score,
                'urgency_score': decision.urgency_score,
                'impact_score': decision.impact_score,
                'reasoning': decision.reasoning,
                'notification_message': decision.notification_message,
                'notification_type': decision.notification_type,
                'observation_content': context.observation_content[:200] + "...",
                'generated_propositions_count': len(context.generated_propositions),
                'similar_propositions_count': len(context.similar_propositions),
                'similar_observations_count': len(context.similar_observations)
            }
            
            self.decisions_log.append(decision_entry)
            
            self.logger.info(f"Saving decision to {self.decisions_file}")
            with open(self.decisions_file, 'w') as f:
                json.dump(self.decisions_log, f, indent=2)
            self.logger.info(f"Decision saved successfully")
        except Exception as e:
            self.logger.error(f"Error saving decision: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
    
    
    async def _find_similar_propositions(self, propositions: List[Proposition], 
                                        limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find similar propositions using BM25 search based on generated propositions.
        Uses the same approach as GUM's _generate_and_search method.
        
        Args:
            propositions: List of generated propositions to search with
            limit: Maximum number of similar propositions to return per generated proposition
            
        Returns:
            List of similar propositions with their metadata
        """
        if not self.gum_instance:
            self.logger.warning("No GUM instance available for BM25 search")
            return []
        
        try:
            async with self.gum_instance._session() as session:
                similar_props = []
                seen_prop_ids = set()
                
                # For each generated proposition, find similar ones (like GUM does)
                for prop in propositions:
                    # Skip if this is one we already found
                    if prop.id in seen_prop_ids:
                        continue
                    
                    # Search using proposition text + reasoning (same as GUM's approach)
                    query = f"{prop.text}\n{prop.reasoning}"
                    self.logger.info(f"Searching for propositions similar to: {prop.text[:50]}...")
                    
                    with session.no_autoflush:
                        results = await search_propositions_bm25(
                            session,
                            query,
                            limit=limit,
                            mode="OR",
                            include_observations=False,
                            start_time=datetime.now() - timedelta(days=30),
                            enable_decay=True,
                            enable_mmr=False
                        )
                    
                    # Convert results to dictionaries
                    for similar_prop, score in results:
                        if similar_prop.id not in seen_prop_ids:
                            similar_props.append({
                                "id": similar_prop.id,
                                "text": similar_prop.text,
                                "reasoning": similar_prop.reasoning,
                                "confidence": similar_prop.confidence,
                                "decay": similar_prop.decay,
                                "relevance_score": float(score),
                                "created_at": similar_prop.created_at.isoformat() if hasattr(similar_prop.created_at, 'isoformat') else str(similar_prop.created_at),
                                "matched_with": prop.text[:50] + "..."  # Which generated prop it matched with
                            })
                            seen_prop_ids.add(similar_prop.id)
                
                self.logger.info(f"Found {len(similar_props)} similar propositions")
                return similar_props
                
        except Exception as e:
            self.logger.error(f"Error finding similar propositions: {e}")
            return []
    
    async def _find_similar_observations(self, observation_content: str, 
                                        limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find similar observations using direct BM25 search on observations.
        
        Args:
            observation_content: The observation content to search for
            limit: Maximum number of similar observations to return
            
        Returns:
            List of similar observations with their metadata
        """
        if not self.gum_instance:
            self.logger.warning("No GUM instance available for observation search")
            return []
        
        try:
            async with self.gum_instance._session() as session:
                self.logger.info(f"Searching for similar observations")
                
                # Search observations directly using BM25
                results = await search_observations_bm25(
                    session,
                    observation_content,  # Use full content as query
                    limit=limit,
                    mode="OR",
                    start_time=datetime.now() - timedelta(days=7),  # Last 7 days
                )
                
                # Convert results to dictionaries
                similar_obs = []
                for obs, score in results:
                    similar_obs.append({
                        "id": obs.id,
                        "observer_name": obs.observer_name,
                        "content": obs.content[:200] + "..." if len(obs.content) > 200 else obs.content,
                        "content_type": obs.content_type,
                        "created_at": obs.created_at.isoformat() if hasattr(obs.created_at, 'isoformat') else str(obs.created_at),
                        "relevance_score": float(score)
                    })
                
                self.logger.info(f"Found {len(similar_obs)} similar observations")
                return similar_obs
                
        except Exception as e:
            self.logger.error(f"Error finding similar observations: {e}")
            return []
    
    async def _make_notification_decision(self, 
                                         observation_content: str,
                                         generated_propositions: List[Dict[str, Any]],
                                         similar_propositions: List[Dict[str, Any]],
                                         similar_observations: List[Dict[str, Any]]) -> Optional[NotificationDecision]:
        """
        Use LLM to decide whether to send a notification.
        
        Args:
            observation_content: The observation text
            generated_propositions: Propositions generated from this observation
            similar_propositions: Similar propositions from history
            similar_observations: Similar observations from history
            
        Returns:
            NotificationDecision or None if error
        """
        # Format generated propositions
        gen_props_text = "\n".join([
            f"- {p['text']} (confidence: {p['confidence']}/10)"
            for p in generated_propositions[:3]
        ]) if generated_propositions else "None"
        
        # Format similar propositions
        sim_props_text = "\n".join([
            f"- {p['text']} (confidence: {p['confidence']}/10, relevance: {p['relevance_score']:.2f})"
            for p in similar_propositions[:5]
        ]) if similar_propositions else "None"
        
        # Format similar observations
        sim_obs_text = "\n".join([
            f"- {o['content'][:100]}... (relevance: {o['relevance_score']:.2f})"
            for o in similar_observations[:5]
        ]) if similar_observations else "None"
        
        # Format notification history (last 5)
        recent_notifs = self.sent_notifications[-5:]
        notif_history_text = "\n".join([
            f"- [{n['timestamp']}] {n['message']} (type: {n['type']})"
            for n in recent_notifs
        ]) if recent_notifs else "No recent notifications"
        
        # Construct prompt
        prompt = NOTIFICATION_DECISION_PROMPT.format(
            user_name=self.user_name,
            observation_content=observation_content,
            generated_propositions=gen_props_text,
            similar_propositions=sim_props_text,
            similar_observations=sim_obs_text,
            notification_history=notif_history_text
        )
        
        try:
            # Call LLM using chat_completion (same as GUM does)
            response = await self.gum_instance.provider.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "text"}
            )
            
            # Debug: Log the response
            self.logger.debug(f"LLM response: {repr(response)}")
            
            if not response or not response.strip():
                self.logger.error("Empty response from LLM")
                return None
            
            # Clean up the response - remove markdown code blocks if present (same as GUM does)
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                # Remove ```json from start and ``` from end
                cleaned_response = cleaned_response[7:]  # Remove ```json
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3]  # Remove ```
                cleaned_response = cleaned_response.strip()
            elif cleaned_response.startswith('```'):
                # Remove ``` from start and end
                cleaned_response = cleaned_response[3:]
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3]
                cleaned_response = cleaned_response.strip()
            
            # Parse JSON
            try:
                result = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON decode error: {e}")
                self.logger.error(f"Original response: {repr(response)}")
                self.logger.error(f"Cleaned response: {repr(cleaned_response)}")
                return None
            
            # Create decision object
            decision = NotificationDecision(
                should_notify=result.get('should_notify', False),
                relevance_score=float(result.get('relevance_score', 0)),
                urgency_score=float(result.get('urgency_score', 0)),
                impact_score=float(result.get('impact_score', 0)),
                reasoning=result.get('reasoning', ''),
                notification_message=result.get('notification_message', ''),
                notification_type=result.get('notification_type', 'none')
            )
            
            self.logger.info(
                f"LLM Decision: should_notify={decision.should_notify}, "
                f"relevance={decision.relevance_score}, urgency={decision.urgency_score}, "
                f"impact={decision.impact_score}"
            )
            
            return decision
                
        except Exception as e:
            self.logger.error(f"Error making notification decision: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    async def process_observation_batch(self, batched_observations: List[Dict[str, Any]]):
        """
        Process a batch of observations and find similar propositions/observations.
        
        This method is called after GUM's _process_batch completes.
        By this point, propositions are already attached to observations in the DB.
        
        Args:
            batched_observations: List of observation dictionaries from GUM's batch
        """
        self.logger.info(f"Processing {len(batched_observations)} observations for notifications")
        
        # Process each observation
        for obs_data in batched_observations:
            try:
                # Extract observation data
                observation_content = obs_data.get('content', '')
                observation_id = obs_data.get('id')
                
                self.logger.info(f"Processing observation {observation_id}")
                self.logger.debug(f"Content preview: {observation_content[:100]}...")
                
                # Get propositions that were generated/attached to this observation
                async with self.gum_instance._session() as session:
                    generated_propositions = await get_related_propositions(session, observation_id)
                
                self.logger.info(f"Found {len(generated_propositions)} propositions for observation {observation_id}")
                
                # Find similar propositions using the generated propositions
                similar_propositions = await self._find_similar_propositions(generated_propositions)
                
                # Find similar observations using the observation content
                similar_observations = await self._find_similar_observations(observation_content)
                
                # Convert generated propositions to dict format
                generated_props_dict = []
                for prop in generated_propositions:
                    generated_props_dict.append({
                        "id": prop.id,
                        "text": prop.text,
                        "reasoning": prop.reasoning,
                        "confidence": prop.confidence,
                        "decay": prop.decay,
                        "created_at": prop.created_at.isoformat() if hasattr(prop.created_at, 'isoformat') else str(prop.created_at)
                    })
                
                # Create notification context
                context = NotificationContext(
                    timestamp=datetime.now().isoformat(),
                    observation_content=observation_content,
                    observation_id=observation_id,
                    generated_propositions=generated_props_dict,
                    similar_propositions=similar_propositions,
                    similar_observations=similar_observations
                )
                
                # Store context
                self.notification_contexts.append(context)
                
                # Use LLM to decide whether to notify
                decision = await self._make_notification_decision(
                    observation_content,
                    generated_props_dict,
                    similar_propositions,
                    similar_observations
                )
                
                if decision:
                    self.logger.info(f"LLM made a decision: should_notify={decision.should_notify}")
                    # Save decision to file for GUI
                    self._save_decision(context, decision)
                    
                    # Log decision
                    self.logger.info(
                        f"LLM Decision - Should notify: {decision.should_notify}, "
                        f"Relevance: {decision.relevance_score}/10, "
                        f"Urgency: {decision.urgency_score}/10, "
                        f"Impact: {decision.impact_score}/10"
                    )
                    
                    # Print to console
                    print(f"\n{'='*60}")
                    print(f"LLM NOTIFICATION DECISION")
                    print(f"{'='*60}")
                    print(f"Should Notify: {'✅ YES' if decision.should_notify else '❌ NO'}")
                    print(f"Type: {decision.notification_type}")
                    print(f"Relevance: {decision.relevance_score}/10")
                    print(f"Urgency: {decision.urgency_score}/10")
                    print(f"Impact: {decision.impact_score}/10")
                    print(f"Reasoning: {decision.reasoning}")
                    
                    if decision.should_notify:
                        print(f"\n📢 NOTIFICATION MESSAGE:")
                        print(f"{decision.notification_message}")
                        print(f"{'='*60}\n")
                        
                        # Track sent notification
                        self.sent_notifications.append({
                            'timestamp': context.timestamp,
                            'message': decision.notification_message,
                            'type': decision.notification_type,
                            'relevance': decision.relevance_score,
                            'urgency': decision.urgency_score,
                            'impact': decision.impact_score
                        })
                    else:
                        print(f"\n❌ No notification sent")
                        print(f"{'='*60}\n")
                else:
                    self.logger.warning("LLM returned no decision")
                
            except Exception as e:
                self.logger.error(f"Error processing observation for notifications: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Save all contexts to file
        self._save_notification_log()
        self.logger.info(f"Saved notification contexts to {self.log_file}")
    
    def get_recent_contexts(self, limit: int = 10) -> List[NotificationContext]:
        """Get the most recent notification contexts."""
        return self.notification_contexts[-limit:]
    
    def get_context_by_observation_id(self, observation_id: int) -> Optional[NotificationContext]:
        """Get notification context for a specific observation."""
        for context in reversed(self.notification_contexts):
            if context.observation_id == observation_id:
                return context
        return None