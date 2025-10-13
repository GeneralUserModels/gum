AUDIT_PROMPT = """You are a data privacy compliance assistant for a large language model (LLM). 

Here are some past interactions {user_name} had with an LLM

## Past Interactions

{past_interaction}

## Task

{user_name} currently is looking at the following:

User Input
---
{user_input}
---

Given {user_name}'s input, analyze and respond in structured JSON format with the following fields:

1. `is_new_information`: Boolean — Does the user's message contain new information compared to the past interactions?
2. `data_type`: String — What type of data is being disclosed (e.g., "Banking credentials and financial account information", "Sensitive topics", "None")?
3. `subject`: String — Who is the primary subject of the disclosed data?
4. `recipient`: String — Who or what is the recipient of the information (e.g., "An AI model that provides conversational assistance")?
5. `transmit_data`: Boolean — Based on how the user handles privacy in their past interactions, should this data be transmitted to the model?

Example output format:
{
  "is_new_information": true,
  "data_type": "[fill in]",
  "subject": "{user_name}",
  "recipient": "An AI model that generates inferences about the user to help in downstream tasks.",
  "transmit_data": true
}"""


PROPOSE_PROMPT = """You are a helpful assistant tasked with analyzing user behavior based on transcribed activity, with a focus on understanding **behavioral and temporal patterns**.

# Analysis

Using a transcription of {user_name}'s activity over time, analyze {user_name}'s current activities, behavior, and preferences. Go beyond describing what they are doing—draw **inferences about what kinds of patterns of behaviors, habits, or actions {user_name} appear through their computer use.

# Temporal Pattern Analysis

Pay special attention to:
- **Behavioral patterns over time**: How activities change throughout the observation period
- **Behavioral consistency**: Whether patterns are stable or variable
- **Temporal trends**: Whether behaviors are increasing, decreasing, or cycling
- **Time-based insights**: How time of day, duration, or frequency affects behavior

To support effective information retrieval (e.g., using BM25), your analysis must **explicitly identify and refer to specific named entities** mentioned in the transcript. This includes applications, websites, documents, people, organizations, tools, and any other proper nouns. Avoid general summaries—**use exact names** wherever possible, even if only briefly referenced.

Consider these points in your analysis:

Provide detailed, concrete explanations for each inference. **Support every claim with specific references to named entities in the transcript.**

## Evaluation Criteria

For each proposition you generate, evaluate its strength using two scales:

### 1. Confidence Scale

Rate your confidence based on how clearly the evidence supports your claim. Consider:

- **Direct Evidence**: Is there direct interaction with a specific, named entity (e.g., opened “Notion,” responded to “Slack” from “Alex”)?
- **Relevance**: Is the evidence clearly tied to the proposition?
- **Engagement Level**: Was the interaction meaningful or sustained?

Score: **1 (weak support)** to **10 (explicit, strong support)**. High scores require specific named references.

### 2. Decay Scale

Rate how long the proposition is likely to stay relevant. Consider:

- **Urgency**: Does the behavior pattern have clear time pressure?
- **Durability**: Will this pattern remain important 24 hours later or more?

Score: **1 (short-lived)** to **10 (long-lasting insight or pattern)**.

# Input

Below is a set of transcribed actions and interactions that {user_name} has performed:

## User Activity Transcriptions

{inputs}

# Task

Generate **at least 5 distinct, well-supported propositions** about {user_name}, each grounded in the transcript, focusing on **behavior patterns**. 

Be conservative in your confidence estimates. Just because an application appears on {user_name}'s screen does not mean they have deeply engaged with it. They may have only glanced at it for a second, making it difficult to draw strong conclusions. 

Assign high confidence scores (e.g., 8-10) only when the transcriptions provide explicit, direct evidence that {user_name} is actively engaging with the content in a meaningful way. Keep in mind that that the content on the screen is what the user is viewing. It may not be what the user is actively doing, so practice caution when assigning confidence.

Generate propositions across the scale to get a wide range of inferences about {user_name}.  

Return your results in this exact JSON format:

{
  "propositions": [
    {
      "proposition": "[Insert your proposition here]",
      "reasoning": "[Provide detailed evidence from specific parts of the transcriptions to clearly justify this proposition. Refer explicitly to named entities where applicable.]",
      "confidence": "[Confidence score (1–10)]",
      "decay": "[Decay score (1–10)]"
    },
    ...
  ]
}"""

REVISE_PROMPT = """You are an expert analyst. A cluster of similar propositions are shown below, followed by their supporting observations.

Your job is to produce a **final set** of propositions that is clear, non-redundant, and captures everything about behavioral patterns of {user_name}.

To support information retrieval (e.g., with BM25), you must **explicitly identify and preserve all named entities** from the input wherever possible. These may include applications, websites, documents, people, organizations, tools, or any other specific proper nouns mentioned in the original propositions or their evidence.

You MAY:

- **Edit** a proposition for clarity, precision, or brevity.
- **Merge** propositions that convey the same meaning.
- **Split** a proposition that contains multiple distinct claims.
- **Add** a new proposition if a distinct behavior pattern is implied by the evidence but not yet stated.
- **Remove** propositions that become redundant after merging or splitting.

You should **liberally add new propositions** when useful to express distinct behavior-related ideas that are otherwise implicit or entangled in broader statements—but never preserve duplicates.

When editing, **retain or introduce references to specific named entities** from the evidence wherever possible, as this improves clarity and retrieval fidelity.

Edge cases to handle:

- **Contradictions** – If two propositions conflict, keep the one with stronger supporting evidence, or merge them into a conditional statement. Lower the confidence score of weaker or uncertain claims.
- **No supporting observations** – Keep the proposition, but retain its original confidence and decay unless justified by new evidence.
- **Granularity mismatch** – If one proposition subsumes others, prefer the version that avoids redundancy while preserving all distinct ideas.
- **Confidence and decay recalibration** – After editing, merging, or splitting, update the confidence and decay scores based on the final form of the proposition and evidence.

General guidelines:

- Keep each proposition clear and concise (typically 1–2 sentences).
- Maintain all meaningful behavior patterns–related content from the originals.
- Provide a brief reasoning/evidence statement for each final proposition.
- Confidence and decay scores range from 1–10 (higher = stronger or longer-lasting).

## Evaluation Criteria

For each proposition you revise, evaluate its strength using two scales:

### 1. Confidence Scale

Rate your confidence in the proposition based on how directly and clearly it is supported by the evidence. Consider:

- **Direct Evidence**: Is the claim directly supported by clear, named interactions in the observations?
- **Relevance**: Is the evidence closely tied to the proposed behavioral pattern?
- **Completeness**: Are key details present and unambiguous?
- **Engagement Level**: Does the user interact meaningfully with the named content in a way that reflects a habit or behavioral pattern?

Score: **1 (weak/assumed)** to **10 (explicitly demonstrated)**. High scores require direct and strong evidence from the observations.

### 2. Decay Scale

Rate how long the behavior pattern insight is likely to remain relevant. Consider:

- **Immediacy**: Is the action contributing to the behavior pattern time-sensitive?
- **Durability**: Will the behavior pattern remain relevant over the long term?

Score: **1 (short-lived)** to **10 (long-term relevance or enduring habit/pattern)**.

# Input

{body}

# Output

Assign high confidence scores (e.g., 8-10) only when the transcriptions provide explicit, direct evidence that {user_name} is engaging in a behavior that reflects a goal, challenge, or habit they may want to change. Remember that the input shows what {user_name} is viewing, not always what they are intentionally doing. Be cautious about over-interpreting surface-level activity.

Return **only** JSON in the following format:

{
  "propositions": [
    {
      "proposition": "<rewritten / merged / new proposition>",
      "reasoning":   "<revised reasoning including any named entities where applicable, focused on the behavior pattern>",
      "confidence":  <integer 1-10>,
      "decay":       <integer 1-10>
    },
    ...
  ]
}"""

NOTIFICATION_DECISION_PROMPT = """You are a helpful assistant that decides whether to send behavioral nudge notifications to {user_name}.

Your goal is to help {user_name} change behaviors they want to improve by sending timely, relevant, and actionable notifications.

# Current Context

## Current Observation
{observation_content}

## Generated Propositions (from this observation)
{generated_propositions}

## Similar Past Behavioral Patterns
{similar_propositions}

## Similar Past Observations
{similar_observations}

## Recent Notification History
{notification_history}

# Decision Criteria

Consider these factors when deciding whether to notify:

1. **Relevance**: Is this observation related to a behavior {user_name} likely wants to change?
2. **Timing**: Is this an appropriate moment to nudge {user_name}?
3. **Actionability**: Can {user_name} act on this notification right now?
4. **Novelty**: Is this different enough from recent notifications to be valuable?
5. **Impact**: Could this notification actually influence behavior change?

# Notification Guidelines

**DO notify when:**
- Pattern suggests procrastination, distraction, or unhealthy habits
- User is starting/continuing a behavior they've struggled with before
- Timing is appropriate (not during deep work, important meetings, etc.)
- Notification offers clear, actionable guidance
- It's been a while since last similar notification

**DON'T notify when:**
- User is in focused work state
- Recent notifications already addressed this
- Observation is neutral/positive behavior
- Too many notifications sent recently (notification fatigue)
- Message would be vague or unhelpful

# Task

Decide whether to send a notification. If yes, craft a **succinct, actionable message** (max 100 characters) that:
- Acknowledges the current behavior
- Suggests a specific change
- Is encouraging, not judgmental
- Focuses on what user wants to improve

Return your decision in this exact JSON format:

{{
  "should_notify": true/false,
  "relevance_score": <1-10>,
  "urgency_score": <1-10>,
  "impact_score": <1-10>,
  "reasoning": "<brief explanation for decision>",
  "notification_message": "<succinct message if should_notify=true, otherwise empty string>",
  "notification_type": "<one of: 'focus', 'break', 'habit', 'health', 'productivity', 'none'>"
}}

Be conservative - only notify when there's clear value. Quality over quantity."""

SIMILAR_PROMPT = """You will label sets of propositions based on how similar they are to eachother.

# Propositions

{body}

# Task

Use exactly these labels:

(A) IDENTICAL – The propositions say practically the same thing.
(B) SIMILAR   – The propositions relate to a similar idea or topic.
(C) UNRELATED – The propositions are fundamentally different.

Always refer to propositions by their numeric IDs.

Return **only** JSON in the following format:

{
  "relations": [
    {
      "source": <ID>,
      "label": "IDENTICAL" | "SIMILAR" | "UNRELATED",
      "target": [<ID>, ...] // empty list if UNRELATED
    }
    // one object per judgement, go through ALL propositions in the input.
  ]
}"""