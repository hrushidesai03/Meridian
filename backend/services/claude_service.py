import json
import logging
from typing import Dict, Any, List
from groq import Groq
from config import get_settings
import asyncio

logger = logging.getLogger(__name__)

# Initialize Groq client
_client: Groq | None = None


def get_client() -> Groq:
    """Get or create Groq client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def _call(system: str, user: str, max_tokens: int = 1024) -> str:
    """Call Groq API with system and user messages."""
    client = get_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
    )
    return response.choices[0].message.content.strip()


def _parse_json(text: str) -> Dict[str, Any]:
    """Parse JSON from text, extracting it even if surrounded by other content."""
    text = text.strip()
    
    # First try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try to strip markdown code fences
    if text.startswith("```"):
        fenced = text
        if fenced.startswith("```json"):
            fenced = fenced[7:]  # Remove ```json
        elif fenced.startswith("```"):
            fenced = fenced[3:]
        
        if fenced.endswith("```"):
            fenced = fenced[:-3]
        
        fenced = fenced.strip()
        try:
            return json.loads(fenced)
        except json.JSONDecodeError:
            text = fenced
    
    # Try to find JSON object in text (look for { and })
    start_idx = text.find('{')
    if start_idx == -1:
        logger.error(f"No JSON object found in response: {text[:200]}")
        raise json.JSONDecodeError("No JSON object found", text, 0)
    
    # Find matching closing brace
    brace_count = 0
    end_idx = start_idx
    for i in range(start_idx, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end_idx = i + 1
                break
    
    json_str = text[start_idx:end_idx]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}\nExtracted: {json_str}\nOriginal: {text}")
        raise


def _extract_commitments_fallback(transcript: str) -> Dict[str, Any]:
    """
    Fallback commitment extraction using pattern matching.
    Used when API is rate-limited or unavailable.
    """
    import re
    
    commitments = []
    
    # Patterns that indicate commitments
    patterns = [
        r"(?:I|we|they|you|he|she)\s+(?:will|shall|am going to|are going to|is going to)\s+(.{10,200}?)(?:\.|,|$|\n)",
        r"(?:I'll|we'll|they'll|you'll|he'll|she'll)\s+(.{10,200}?)(?:\.|,|$|\n)",
        r"(?:I'm|we're|they're|you're|he's|she's)\s+(?:going to|going to)\s+(.{10,200}?)(?:\.|,|$|\n)",
        r"(?:can you|will you|could you|would you|should you)\s+(.{10,200}?)(?:\.|,|$|\n)",
        r"committed to\s+(.{10,200}?)(?:\.|,|$|\n)",
        r"agreed to\s+(.{10,200}?)(?:\.|,|$|\n)",
        r"promised to\s+(.{10,200}?)(?:\.|,|$|\n)",
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, transcript, re.IGNORECASE)
        for match in matches:
            text = match.group(1).strip()
            if len(text) > 5:  # Filter out too-short matches
                commitments.append({
                    "text": text,
                    "timestamp": "",
                    "speaker": ""
                })
    
    # Remove duplicates while preserving order
    seen = set()
    unique_commitments = []
    for c in commitments:
        if c["text"] not in seen:
            seen.add(c["text"])
            unique_commitments.append(c)
    
    logger.info(f"Fallback extraction found {len(unique_commitments)} commitments")
    return {"commitments": unique_commitments}


async def extract_commitments(transcript: str) -> Dict[str, Any]:
    """
    Extract commitments from transcript.
    
    Returns:
        {
            "commitments": [
                {
                    "text": "commitment statement",
                    "timestamp": "00:05:30",
                    "speaker": "name"
                },
                ...
            ]
        }
    """
    system = """You are an expert at analyzing meeting transcripts and extracting commitments.
A commitment is:
- An explicit action promised: "I will...", "I'll...", "I'm going to..."
- An assignment to someone: "You will...", "Can you...", "Will you..."
- Any actionable task that someone takes responsibility for
- Future work or decisions that were decided

Be thorough - extract ALL commitments, even implicit ones.
Always return valid JSON with only the structure specified, no markdown wrapping or extra text."""

    user = f"""Analyze this meeting transcript and extract ALL commitments made - both explicit and implicit.

Transcript:
{transcript}

Return ONLY this JSON structure, no other text:
{{
    "commitments": [
        {{
            "text": "the exact commitment statement from the transcript",
            "timestamp": "time if mentioned, or empty string",
            "speaker": "person's name if known, or empty string"
        }}
    ]
}}

If no commitments found, return: {{"commitments": []}}"""

    try:
        response_text = await asyncio.to_thread(lambda: _call(system, user, max_tokens=2000))
        
        try:
            result = _parse_json(response_text)
            logger.info(f"Extracted {len(result.get('commitments', []))} commitments from transcript: {transcript[:100]}")
            return result
        except Exception as e:
            logger.error(f"Failed to parse commitment extraction response: {e}\nResponse: {response_text}")
            return {"commitments": []}
    except Exception as e:
        # Catch Groq rate limits and other API errors
        logger.error(f"Commitment extraction API error: {type(e).__name__}: {str(e)}")
        # Extract commitments from transcript using simple pattern matching as fallback
        logger.warning(f"Using fallback commitment extraction due to API error")
        return _extract_commitments_fallback(transcript)


async def score_commitment_confidence(commitment_text: str, context: str) -> Dict[str, Any]:
    """
    Score confidence in a commitment.
    
    Returns:
        {
            "confidence_score": 0.85,
            "reasoning": "explanation",
            "risk_factors": ["factor1", "factor2"]
        }
    """
    system = """You are an expert at assessing the likelihood of commitment completion.
Analyze tone, specificity, resources, and urgency. Return ONLY valid JSON in the exact format specified."""

    user = f"""Score the confidence that this commitment will actually be completed.

Commitment: {commitment_text}

Context: {context}

Return ONLY this JSON structure, no other text:
{{
    "confidence_score": 0.5,
    "reasoning": "why this score",
    "risk_factors": ["unclear deadline", "no owner", "vague scope", etc]
}}

The score should be between 0.0 (very unlikely) and 1.0 (very likely) based on how specific and clear the commitment is."""

    response_text = await asyncio.to_thread(lambda: _call(system, user, max_tokens=500))
    try:
        result = _parse_json(response_text)
        logger.info(f"Scored commitment confidence: {result.get('confidence_score', 0.5)}")
        return result
    except Exception as e:
        logger.error(f"Failed to score commitment: {e}\nResponse: {response_text}")
        return {"confidence_score": 0.5, "reasoning": "Error in scoring", "risk_factors": []}


async def extract_decisions(commitment_text: str, context: str) -> Dict[str, Any]:
    """
    Extract technical/implementation decisions from a commitment.
    
    Returns:
        {
            "decisions": [
                {
                    "text": "decision statement",
                    "watch_terms": ["term1", "term2"],
                    "category": "tech/timeline/scope/resource"
                }
            ]
        }
    """
    system = """You are an expert at identifying key decisions from commitments.
Decisions include technology choices, timing, scope, team assignments, etc.
Return ONLY valid JSON in the exact format specified. No preamble, no explanation, just JSON."""

    user = f"""From this commitment and context, extract the specific decisions that were made.

Commitment: {commitment_text}

Context: {context}

Return ONLY this JSON structure, no other text:
{{
    "decisions": [
        {{
            "text": "exact decision statement",
            "watch_terms": ["term1", "term2", "term3"],
            "category": "tech|timeline|scope|resource"
        }}
    ]
}}

If no decisions found, return: {{"decisions": []}}"""

    response_text = await asyncio.to_thread(lambda: _call(system, user, max_tokens=1000))
    try:
        result = _parse_json(response_text)
        logger.info(f"Extracted {len(result.get('decisions', []))} decisions: {response_text[:100]}")
        return result
    except Exception as e:
        logger.error(f"Failed to extract decisions: {e}\nResponse: {response_text}")
        return {"decisions": []}


async def verify_decision_drift(decision_text: str, watch_terms: List[str], screen_observation: str) -> Dict[str, Any]:
    """
    Verify if a decision is drifting based on screen observations.
    
    Returns:
        {
            "drift_detected": True/False,
            "drift_description": "if drift found",
            "evidence": "direct quote from observation",
            "severity": "high|medium|low"
        }
    """
    system = """You are an expert at detecting when decisions are being violated or drifted from.
Drift means the actual behavior contradicts the stated decision.
Always return valid JSON."""

    user = f"""Check if this decision is being violated by what we see on screen.

Decision: {decision_text}

Watch terms to look for: {', '.join(watch_terms)}

Screen observation: {screen_observation}

Return a JSON object:
{{
    "drift_detected": true|false,
    "drift_description": "what changed (only if drift_detected is true)",
    "evidence": "exact quote from the observation",
    "severity": "high|medium|low"
}}

Drift means the actual behavior contradicts the stated decision.
High severity = core commitment violated. Low severity = minor deviation."""

    response_text = await asyncio.to_thread(lambda: _call(system, user, max_tokens=500))
    result = _parse_json(response_text)
    logger.info(f"Drift verification: {result.get('drift_detected', False)}")
    return result


async def assess_commitment_gap(commitment_text: str, timeline: str, current_date: str, context: str) -> Dict[str, Any]:
    """
    Assess if a commitment has a gap (not being executed).
    
    Returns:
        {
            "gap_exists": True/False,
            "gap_description": "if gap found",
            "expected_progress": "what we should have seen by now",
            "severity": "high|medium|low"
        }
    """
    system = """You are an expert at assessing commitment execution and progress.
Gap = no progress or insufficient progress by this point in time.
Always return valid JSON."""

    user = f"""Assess whether this commitment is on track or has a gap in execution.

Commitment: {commitment_text}

Timeline: {timeline}

Current date: {current_date}

Context: {context}

Return a JSON object:
{{
    "gap_exists": true|false,
    "gap_description": "what's missing (only if gap_exists is true)",
    "expected_progress": "what we should see by this date",
    "severity": "high|medium|low"
}}

Gap = no progress or insufficient progress by this point in time.
High severity = critical deadline passed. Low severity = minor delay."""

    response_text = await asyncio.to_thread(lambda: _call(system, user, max_tokens=500))
    result = _parse_json(response_text)
    logger.info(f"Gap assessment: {result.get('gap_exists', False)}")
    return result


async def generate_receipt_narrative(commitment_text: str, decision_text: str, gap_or_drift: str, evidence: str) -> Dict[str, Any]:
    """
    Generate narrative for accountability receipt video.
    
    Returns:
        {
            "title": "receipt title",
            "narration": "spoken narration script",
            "visuals": ["text overlay 1", "text overlay 2"],
            "tone": "professional|concerned|neutral"
        }
    """
    system = """You are an expert at creating clear, factual accountability narratives.
Write in third person, objective tone. Content should be suitable for team review.
Always return valid JSON."""

    user = f"""Create a narrative for an accountability receipt video showing a commitment and its gap/drift.

Commitment: {commitment_text}

Decision: {decision_text}

Gap/Drift type: {gap_or_drift}

Evidence: {evidence}

Return a JSON object:
{{
    "title": "concise title for the video",
    "narration": "3-4 sentence spoken narration (as if a narrator is speaking)",
    "visuals": ["text overlay 1", "text overlay 2", "text overlay 3"],
    "tone": "professional|concerned|neutral"
}}

The receipt should be clear, factual, and suitable for team accountability review.
Narration should be in third person and objective."""

    response_text = await asyncio.to_thread(lambda: _call(system, user, max_tokens=800))
    result = _parse_json(response_text)
    logger.info("Generated receipt narrative")
    return result


async def generate_sprint_retro(
    commitments: list[dict], decisions: list[dict], date_range: str
) -> dict:
    """
    Generate a sprint retrospective report analyzing commitments and decisions.
    
    Returns:
        {
            "summary": "sprint health assessment",
            "commitments_delivered": [{"text": "...", "owner": "..."}],
            "commitments_missed": [{"text": "...", "owner": "...", "reason": "..."}],
            "commitments_at_risk": [{"text": "...", "owner": "..."}],
            "decisions_holding": [{"text": "..."}],
            "decisions_drifted": [{"text": "...", "drift_evidence": "..."}],
            "recommendation": "actionable recommendation"
        }
    """
    system = """You are an expert at analyzing sprint retrospectives and commitment tracking.
Provide clear, actionable insights on sprint health and decision execution.
Always return valid JSON."""

    user = f"""Generate a sprint retrospective report.

Date range: {date_range}

Commitments data:
{json.dumps(commitments, indent=2, default=str)}

Decisions data:
{json.dumps(decisions, indent=2, default=str)}

Return a JSON object:
{{
    "summary": "2-3 sentence overall sprint health assessment",
    "commitments_delivered": [{{"text": "...", "owner": "..."}}],
    "commitments_missed": [{{"text": "...", "owner": "...", "reason": "..."}}],
    "commitments_at_risk": [{{"text": "...", "owner": "..."}}],
    "decisions_holding": [{{"text": "..."}}],
    "decisions_drifted": [{{"text": "...", "drift_evidence": "..."}}],
    "recommendation": "one actionable recommendation for next sprint"
}}"""

    response_text = await asyncio.to_thread(lambda: _call(system, user, max_tokens=2000))
    result = _parse_json(response_text)
    logger.info("Generated sprint retrospective")
    return result


async def extract_screen_tech(description: str) -> dict:
    """Extract technology names from screen description."""
    def _call_groq(system: str, user: str) -> str:
        return _call(system, user, max_tokens=500)
    
    result = await asyncio.to_thread(_call_groq,
        "You are a tech stack analyzer. Extract all technology names, frameworks, databases, libraries from descriptions. Always return valid JSON.",
        description
    )
    try:
        return json.loads(result)
    except:
        return {"detected_terms": [], "description": description}


async def verify_decision_drift(decision_text: str, watch_terms: list, screen_observation: str) -> dict:
    """Check if screen observation contradicts a decision."""
    def _call_groq(system: str, user: str) -> str:
        return _call(system, user, max_tokens=500)
    
    prompt = f"Decision: {decision_text}\nWatch terms: {watch_terms}\nScreen: {screen_observation}\nIs there drift (contradiction)? Return JSON with: drift_detected (bool), drift_description (string), evidence (string), severity (high/medium/low)."
    result = await asyncio.to_thread(_call_groq, 
        "You detect when developers contradict team decisions. You analyze screen observations against stated decisions and find contradictions. Always return valid JSON.",
        prompt
    )
    try:
        return json.loads(result)
    except:
        return {"drift_detected": False, "drift_description": "", "evidence": "", "severity": "low"}
