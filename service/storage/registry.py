"""UC10 Document Anonymizer — Entity Label Registry.

Manages persistent label assignments (e.g. PERSOON_1, ORGANISATIE_1) across documents.
Uses Neo4j graph database as primary authoritative store, with an in-memory fallback
when Neo4j is offline or in local non-cluster development.
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None

try:
    from service.data.wordlists import _LABEL_PREFIX
except ImportError:
    from data.wordlists import _LABEL_PREFIX

log = logging.getLogger("presidio-service")

NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")

neo4j_driver: Any | None = None
_mem_registry: dict[str, str] = {}
_mem_counters: dict[str, int] = {}


def get_neo4j_driver() -> Any | None:
    """Return an active Neo4j driver, attempting reconnect if disconnected."""
    global neo4j_driver
    if neo4j_driver is not None:
        try:
            neo4j_driver.verify_connectivity()
            return neo4j_driver
        except Exception:
            try:
                neo4j_driver.close()
            except Exception:
                pass
            neo4j_driver = None
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        log.info("Neo4j connected at %s", NEO4J_URI)
        neo4j_driver = driver
        return neo4j_driver
    except Exception as exc:
        log.warning("Neo4j unavailable (%s) — labels will be in-memory only.", exc)
        return None


def close_neo4j_driver() -> None:
    """Gracefully close Neo4j connection pool."""
    global neo4j_driver
    if neo4j_driver:
        try:
            neo4j_driver.close()
        except Exception:
            pass
        neo4j_driver = None


def entity_hash(text: str) -> str:
    """Generate deterministic SHA-256 hash of normalized entity string."""
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


def label_prefix(entity_type: str) -> str:
    """Map Presidio entity type to Dutch label prefix."""
    return _LABEL_PREFIX.get(entity_type, "ENTITEIT")


def counter_key(entity_type: str) -> str:
    """Counter key per label prefix: unmapped types share 'ENTITEIT'."""
    return entity_type if entity_type in _LABEL_PREFIX else "ENTITEIT"


def next_mem_label(entity_type: str) -> str:
    """Allocate the next in-memory label for an entity type."""
    key = counter_key(entity_type)
    count = _mem_counters.get(key, 0) + 1
    _mem_counters[key] = count
    return f"{label_prefix(entity_type)}_{count}"


def resolve_label(original: str, entity_type: str) -> str:
    """Return a stable Dutch label for *original*, creating one if new.

    Labels are global across all documents. Neo4j is the authoritative store;
    the in-memory dict is used as fallback when Neo4j is unavailable.
    """
    h = entity_hash(f"{label_prefix(entity_type)}|{original}")
    driver = get_neo4j_driver()

    if driver is None:
        log.warning("Neo4j down — using in-memory label store.")
        if h not in _mem_registry:
            _mem_registry[h] = next_mem_label(entity_type)
        return _mem_registry[h]

    try:
        with driver.session() as session:
            existing = session.run(
                "MATCH (e:Entity {hash: $hash}) RETURN e.label AS label",
                hash=h,
            ).single()
            if existing:
                return existing["label"]

            result = session.run(
                """
                OPTIONAL MATCH (e:Entity)
                WHERE e.hash IS NOT NULL AND e.label STARTS WITH $prefix + '_'
                WITH max(toInteger(substring(e.label, size($prefix) + 1))) AS seen
                MERGE (c:LabelCounter {type: $counter})
                ON CREATE SET c.value = coalesce(seen, 0)
                SET c.value = c.value + 1
                WITH c.value AS n
                CREATE (:Entity {hash: $hash, label: $prefix + '_' + toString(n), type: $type})
                RETURN $prefix + '_' + toString(n) AS label
                """,
                hash=h,
                type=entity_type,
                counter=counter_key(entity_type),
                prefix=label_prefix(entity_type),
            )
            return result.single()["label"]
    except Exception as exc:
        log.warning("Neo4j query failed (%s) — falling back to in-memory label.", exc)
        if h not in _mem_registry:
            _mem_registry[h] = next_mem_label(entity_type)
        return _mem_registry[h]
