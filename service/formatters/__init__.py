"""UC10 Document Formatters (PDF & DOCX)."""
try:
    from .docx import anonymize_docx, docx_part_texts
    from .handler import (
        anonymize_document,
        file_text,
        source_texts,
        unmatched_entities,
    )
    from .pdf import anonymize_pdf, pdf_lines, pdf_page_text
except ImportError:
    from docx import anonymize_docx, docx_part_texts
    from handler import (
        anonymize_document,
        file_text,
        source_texts,
        unmatched_entities,
    )
    from pdf import anonymize_pdf, pdf_lines, pdf_page_text
