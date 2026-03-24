"""
DEPRECATED — use modules.rag.ragService instead.
This file is kept only to avoid breaking any remaining import references.
"""
import warnings

warnings.warn(
    "modules.memory.ragService is deprecated. Import from modules.rag.ragService instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.rag.ragService import ragService  # re-export

__all__ = ["ragService"]
