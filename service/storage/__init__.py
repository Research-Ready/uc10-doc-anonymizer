"""UC10 Persistent Entity Storage and Label Registry."""
try:
    from .registry import (
        close_neo4j_driver,
        get_neo4j_driver,
        resolve_label,
    )
except ImportError:
    from registry import (
        close_neo4j_driver,
        get_neo4j_driver,
        resolve_label,
    )
