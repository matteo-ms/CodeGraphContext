"""
Tree-sitter Indexer Wrapper

This module wraps the existing Tree-sitter based indexing logic
to conform to the new BaseIndexer interface.
"""

import logging
from pathlib import Path
from typing import Dict, List

from . import (
    BaseIndexer,
    IndexerConfig,
    IndexResult,
    SymbolInfo,
    ReferenceInfo,
    IndexerType,
    IndexerFactory
)

logger = logging.getLogger(__name__)


class TreeSitterIndexer(BaseIndexer):
    """
    Tree-sitter based indexer (existing implementation).
    
    This is a wrapper around the existing graph_builder.py logic
    to conform to the new indexer interface.
    """
    
    def __init__(self, config: IndexerConfig):
        super().__init__(config)
        
    def is_available(self) -> bool:
        """
        Check if Tree-sitter is available.
        
        Returns:
            True if tree-sitter is installed
        """
        try:
            import tree_sitter
            from tree_sitter_language_pack import get_language
            return True
        except ImportError:
            return False
    
    def get_version(self) -> str:
        """
        Get Tree-sitter version.
        
        Returns:
            Version string
        """
        try:
            import tree_sitter
            return tree_sitter.__version__
        except Exception:
            return "unknown"
    
    def index(self) -> IndexResult:
        """
        Index using Tree-sitter (delegates to existing graph_builder).
        
        For now, this returns a placeholder result. The actual integration
        with graph_builder.py will be done in the next step.
        
        Returns:
            IndexResult with symbols and references
        """
        logger.info(f"Indexing with Tree-sitter: {self.project_root}")
        
        # TODO: Integrate with existing graph_builder.py
        # For now, return a placeholder
        return IndexResult(
            symbols=[],
            references=[],
            files=[],
            indexer_type=IndexerType.TREE_SITTER,
            metadata={
                "indexer": "tree-sitter",
                "project_root": str(self.project_root),
            }
        )
