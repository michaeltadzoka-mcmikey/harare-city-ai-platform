# app/evidence_cleaner.py
"""
Strip RAG metadata blocks and format evidence cleanly for the LLM.
Uses content-type-aware truncation limits to ensure key facts survive.
"""

CONTENT_TYPE_LIMITS = {
    'fee_schedule':       2000,   # full fee table
    'emergency':          1200,   # symptoms / contacts after template header
    'contact_directory':  2000,   # phone tables start late in the document
    'policy':             2000,   # policy statement + who qualifies section
    'procedure':          2000,   # step list can be long
    'faq':                9999,   # never truncate Q&A pairs
}
DEFAULT_LIMIT = 2000


def clean_evidence_for_llm(evidence_list: list) -> str:
    clean_blocks = []

    for chunk in evidence_list:
        meta = chunk.get("metadata", {})
        title = meta.get("title", "Council Document")
        content_type = meta.get("content_type", "unknown")
        raw_text = chunk.get("text", "")

        # Remove everything before "## CONTENT_BLOCK"
        if "## CONTENT_BLOCK" in raw_text:
            content = raw_text.split("## CONTENT_BLOCK", 1)[-1].strip()
        elif "## METADATA_BLOCK" in raw_text:
            lines = raw_text.splitlines()
            in_meta = False
            kept = []
            for line in lines:
                if line.strip().startswith("## METADATA_BLOCK"):
                    in_meta = True
                    continue
                if in_meta and line.strip().startswith("##"):
                    in_meta = False
                if not in_meta:
                    kept.append(line)
            content = "\n".join(kept).strip()
        else:
            content = raw_text.strip()

        # Content-type-aware truncation (never truncate faq)
        limit = CONTENT_TYPE_LIMITS.get(content_type, DEFAULT_LIMIT)
        if len(content) > limit and content_type != 'faq':
            content = content[:limit].rsplit('\n', 1)[0] + "\n... (truncated)"

        clean_blocks.append(
            f"[SOURCE: {title} | type: {content_type}]\n{content}"
        )

    return "\n\n---\n\n".join(clean_blocks)