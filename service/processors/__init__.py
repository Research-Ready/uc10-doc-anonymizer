"""UC10 Natural Language Processing and Text Processing Pipeline."""
try:
    from .text import (
        analyze_text,
        docling_to_markdown,
        drop_overlaps,
        extend_names,
        find_spans,
        guess_language,
        in_scope,
        inside,
        leaks,
        load_common_words,
        plain_for_ner,
        protect_per_block,
        protected_spans,
        replacement_patterns,
        surnames,
    )
except ImportError:
    from text import (
        analyze_text,
        docling_to_markdown,
        drop_overlaps,
        extend_names,
        find_spans,
        guess_language,
        in_scope,
        inside,
        leaks,
        load_common_words,
        plain_for_ner,
        protect_per_block,
        protected_spans,
        replacement_patterns,
        surnames,
    )
