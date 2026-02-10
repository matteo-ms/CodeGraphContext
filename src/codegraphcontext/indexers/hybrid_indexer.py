"""
Hybrid Indexer Implementation

This module implements a smart hybrid indexer that automatically chooses
the best indexing strategy based on project type and availability.

Strategy:
1. Try SCIP first (if available and project is supported)
2. Fall back to Tree-sitter if SCIP fails
3. Provide detailed logging about which indexer was used
"""

import logging
from pathlib import Path
from typing import Optional

from . import (
    BaseIndexer,
    IndexerConfig,
    IndexResult,
    IndexerType,
    IndexerFactory
)

logger = logging.getLogger(__name__)


class HybridIndexer(BaseIndexer):
    """
    Intelligent hybrid indexer that chooses the best strategy.
    
    Decision logic:
    1. Check if project is Python-based (has .py files, pyproject.toml, etc.)
    2. If Python and SCIP available → use SCIP
    3. Otherwise → use Tree-sitter
    4. If SCIP fails → fall back to Tree-sitter
    """
    
    def __init__(self, config: IndexerConfig):
        super().__init__(config)
        self._scip_indexer = None
        self._tree_sitter_indexer = None
        
    def is_available(self) -> bool:
        """
        Hybrid indexer is always available (falls back to Tree-sitter).
        
        Returns:
            True (always available)
        """
        return True
    
    def get_version(self) -> str:
        """
        Get version info for both indexers.
        
        Returns:
            Version string with both indexer versions
        """
        versions = []
        
        # Get SCIP version if available
        try:
            scip_indexer = self._get_scip_indexer()
            if scip_indexer.is_available():
                versions.append(f"SCIP: {scip_indexer.get_version()}")
        except Exception:
            pass
        
        # Get Tree-sitter version
        try:
            ts_indexer = self._get_tree_sitter_indexer()
            if ts_indexer.is_available():
                versions.append(f"Tree-sitter: {ts_indexer.get_version()}")
        except Exception:
            pass
        
        return " | ".join(versions) if versions else "unknown"
    
    def index(self) -> IndexResult:
        """
        Index using the best available strategy.
        
        Returns:
            IndexResult from the chosen indexer
        """
        if not self.validate_project():
            raise ValueError(f"Invalid project root: {self.project_root}")
        
        # Determine best indexer
        indexer_choice = self._choose_indexer()
        
        logger.info(f"Hybrid indexer chose: {indexer_choice}")
        
        if indexer_choice == IndexerType.SCIP:
            return self._index_with_scip()
        else:
            return self._index_with_tree_sitter()
    
    def _choose_indexer(self) -> IndexerType:
        """
        Choose the best indexer for this project.
        
        Returns:
            IndexerType to use
        """
        # Check if project is Python-based
        if not self._is_python_project():
            logger.debug("Not a Python project, using Tree-sitter")
            return IndexerType.TREE_SITTER
        
        # Check if SCIP is available
        scip_indexer = self._get_scip_indexer()
        if not scip_indexer.is_available():
            logger.debug("SCIP not available, using Tree-sitter")
            return IndexerType.TREE_SITTER
        
        # Use SCIP for Python projects
        logger.debug("Python project with SCIP available, using SCIP")
        return IndexerType.SCIP
    
    def _is_python_project(self) -> bool:
        """
        Detect if project is primarily Python.
        
        Checks for:
        - .py files
        - pyproject.toml
        - setup.py
        - requirements.txt
        
        Returns:
            True if Python project
        """
        # Check for Python project markers
        python_markers = [
            "pyproject.toml",
            "setup.py",
            "requirements.txt",
            "Pipfile",
            "poetry.lock",
        ]
        
        for marker in python_markers:
            if (self.project_root / marker).exists():
                logger.debug(f"Found Python marker: {marker}")
                return True
        
        # Check for .py files
        py_files = list(self.project_root.rglob("*.py"))
        if len(py_files) > 0:
            logger.debug(f"Found {len(py_files)} Python files")
            return True
        
        return False
    
    def _index_with_scip(self) -> IndexResult:
        """
        Index using SCIP with fallback to Tree-sitter.
        
        Returns:
            IndexResult from SCIP or Tree-sitter (fallback)
        """
        try:
            scip_indexer = self._get_scip_indexer()
            logger.info("Indexing with SCIP...")
            result = scip_indexer.index()
            logger.info(f"SCIP indexing successful: {len(result.symbols)} symbols")
            return result
            
        except Exception as e:
            logger.warning(f"SCIP indexing failed: {e}")
            logger.info("Falling back to Tree-sitter...")
            return self._index_with_tree_sitter()
    
    def _index_with_tree_sitter(self) -> IndexResult:
        """
        Index using Tree-sitter.
        
        Returns:
            IndexResult from Tree-sitter
        """
        ts_indexer = self._get_tree_sitter_indexer()
        logger.info("Indexing with Tree-sitter...")
        result = ts_indexer.index()
        logger.info(f"Tree-sitter indexing successful: {len(result.symbols)} symbols")
        return result
    
    def _get_scip_indexer(self) -> BaseIndexer:
        """
        Get or create SCIP indexer instance.
        
        Returns:
            SCIP indexer
        """
        if self._scip_indexer is None:
            from .scip_indexer import SCIPIndexer
            
            scip_config = IndexerConfig(
                indexer_type=IndexerType.SCIP,
                project_root=self.config.project_root,
                timeout=self.config.timeout,
                cache_enabled=self.config.cache_enabled,
                cache_dir=self.config.cache_dir,
                scip_binary_path=self.config.scip_binary_path,
                scip_environment=self.config.scip_environment,
            )
            self._scip_indexer = SCIPIndexer(scip_config)
        
        return self._scip_indexer
    
    def _get_tree_sitter_indexer(self) -> BaseIndexer:
        """
        Get or create Tree-sitter indexer instance.
        
        Returns:
            Tree-sitter indexer
        """
        if self._tree_sitter_indexer is None:
            # Import the existing Tree-sitter indexer
            # This will need to be adapted from the existing graph_builder.py
            from .tree_sitter_indexer import TreeSitterIndexer
            
            ts_config = IndexerConfig(
                indexer_type=IndexerType.TREE_SITTER,
                project_root=self.config.project_root,
                timeout=self.config.timeout,
                cache_enabled=self.config.cache_enabled,
                cache_dir=self.config.cache_dir,
                max_file_size_mb=self.config.max_file_size_mb,
                parallel_workers=self.config.parallel_workers,
            )
            self._tree_sitter_indexer = TreeSitterIndexer(ts_config)
        
        return self._tree_sitter_indexer
