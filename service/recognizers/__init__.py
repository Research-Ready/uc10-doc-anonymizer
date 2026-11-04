"""UC10 Custom Entity Recognizers."""
try:
    from .dutch import (
        BSNRecognizer,
        TitledNameRecognizer,
        is_valid_bsn,
        setup_custom_recognizers,
    )
except ImportError:
    from dutch import (
        BSNRecognizer,
        TitledNameRecognizer,
        is_valid_bsn,
        setup_custom_recognizers,
    )
