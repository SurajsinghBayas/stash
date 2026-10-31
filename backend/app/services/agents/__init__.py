"""Stash's AI agents.

Ingest (worker, per card): moderator → reader (links, long cards) / vision (images) → chunker → embedder.
Chat (per question): planner → retriever → ranker (rerank + evidence judge, one corrective round) → writer →
verifier, with the memory agent extracting durable facts after each answer.
Every input to every agent is a SafeText (see services/safety); every agent call is traced in ai_requests.
"""
