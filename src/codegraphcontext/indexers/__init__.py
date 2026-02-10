"""
SCIP Indexer Base Classes and Interfaces

This module defines the abstract base class for all indexers and provides
the foundation for the SCIP integration.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class IndexerType(Enum):
    """Supported indexer types"""
    TREE_SITTER = "tree-sitter"
    SCIP = "scip"
    HYBRID = "hybrid"


@dataclass
class IndexerConfig:
    """Configuration for indexers"""
    indexer_type: IndexerType
    project_root: Path
    timeout: int = 300  # seconds
    cache_enabled: bool = True
    cache_dir: Optional[Path] = None
    
    # SCIP-specific settings
    scip_binary_path: Optional[str] = None
    scip_environment: Optional[str] = None
    scip_languages: Optional[str] = None
    
    # Tree-sitter specific settings
    max_file_size_mb: int = 10
    parallel_workers: int = 4


@dataclass
class SymbolInfo:
    """Unified symbol information from any indexer"""
    name: str
    kind: str  # "function", "class", "method", "variable"
    file_path: str
    line_number: int
    column_number: int
    signature: Optional[str] = None
    documentation: Optional[str] = None
    scip_symbol: Optional[str] = None  # Full SCIP symbol string
    parent_symbol: Optional[str] = None  # For methods in classes
    
    # Type information (SCIP provides this, Tree-sitter doesn't)
    return_type: Optional[str] = None
    parameter_types: Optional[List[str]] = None


@dataclass
class ReferenceInfo:
    """Information about a symbol reference (call, import, etc.)"""
    source_symbol: str  # Who is referencing
    target_symbol: str  # What is being referenced
    reference_type: str  # "call", "import", "inheritance", "implementation"
    file_path: str
    line_number: int
    column_number: int


@dataclass
class IndexResult:
    """Result from indexing operation"""
    symbols: List[SymbolInfo]
    references: List[ReferenceInfo]
    files: List[str]
    indexer_type: IndexerType
    metadata: Dict[str, Any]


class BaseIndexer(ABC):
    """
    Abstract base class for all indexers.
    
    All indexers (Tree-sitter, SCIP, etc.) must implement this interface
    to ensure consistent behavior and easy swapping.
    """
    
    def __init__(self, config: IndexerConfig):
        self.config = config
        self.project_root = config.project_root
        
    @abstractmethod
    def index(self) -> IndexResult:
        """
        Index the project and return structured results.
        
        Returns:
            IndexResult containing all symbols, references, and metadata
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this indexer is available and can be used.
        
        For SCIP: checks if scip-python is installed
        For Tree-sitter: checks if tree-sitter is available
        
        Returns:
            True if indexer can be used, False otherwise
        """
        pass
    
    @abstractmethod
    def get_version(self) -> str:
        """
        Get the version of the indexer.
        
        Returns:
            Version string (e.g., "0.3.0" for scip-python)
        """
        pass
    
    def validate_project(self) -> bool:
        """
        Validate that the project can be indexed.
        
        Returns:
            True if project is valid, False otherwise
        """
        if not self.project_root.exists():
            return False
        if not self.project_root.is_dir():
            return False
        return True


class IndexerFactory:
    """
    Factory class for creating indexers based on configuration.
    """
    
    _indexers = {}  # Registry of available indexers
    
    @classmethod
    def register_indexer(cls, indexer_type: IndexerType, indexer_class: type):
        """Register an indexer implementation"""
        cls._indexers[indexer_type] = indexer_class
    
    @classmethod
    def create_indexer(cls, config: IndexerConfig) -> BaseIndexer:
        """
        Create an indexer based on configuration.
        
        Args:
            config: Indexer configuration
            
        Returns:
            Appropriate indexer instance
            
        Raises:
            ValueError: If indexer type is not supported
        """
        if config.indexer_type not in cls._indexers:
            raise ValueError(f"Unsupported indexer type: {config.indexer_type}")
        
        indexer_class = cls._indexers[config.indexer_type]
        return indexer_class(config)
    
    @classmethod
    def get_available_indexers(cls) -> List[IndexerType]:
        """
        Get list of available indexers that can be used.
        
        Returns:
            List of indexer types that are available
        """
        available = []
        for indexer_type, indexer_class in cls._indexers.items():
            # Create a temporary config to test availability
            temp_config = IndexerConfig(
                indexer_type=indexer_type,
                project_root=Path(".")
            )
            indexer = indexer_class(temp_config)
            if indexer.is_available():
                available.append(indexer_type)
        return available


# Import and register all indexers
def _register_indexers():
    """Register all available indexers"""
    try:
        from .tree_sitter_indexer import TreeSitterIndexer
        IndexerFactory.register_indexer(IndexerType.TREE_SITTER, TreeSitterIndexer)
    except ImportError:
        pass
    
    try:
        from .scip_indexer import SCIPIndexer
        IndexerFactory.register_indexer(IndexerType.SCIP, SCIPIndexer)
    except ImportError:
        pass
    
    try:
        from .hybrid_indexer import HybridIndexer
        IndexerFactory.register_indexer(IndexerType.HYBRID, HybridIndexer)
    except ImportError:
        pass


# Register indexers on module import
_register_indexers()


# Convenience function for creating indexers from config
def create_indexer_from_config(
    project_root: Path,
    indexer_type: str = "tree-sitter",
    **kwargs
) -> BaseIndexer:
    """
    Create an indexer from configuration.
    
    Args:
        project_root: Path to project
        indexer_type: Type of indexer ("tree-sitter", "scip", "hybrid")
        **kwargs: Additional configuration options
        
    Returns:
        Indexer instance
    """
    # Convert string to IndexerType enum
    try:
        indexer_enum = IndexerType(indexer_type)
    except ValueError:
        raise ValueError(
            f"Invalid indexer type: {indexer_type}. "
            f"Must be one of: {[t.value for t in IndexerType]}"
        )
    
    config = IndexerConfig(
        indexer_type=indexer_enum,
        project_root=project_root,
        **kwargs
    )
    
    return IndexerFactory.create_indexer(config)


__all__ = [
    "IndexerType",
    "IndexerConfig",
    "SymbolInfo",
    "ReferenceInfo",
    "IndexResult",
    "BaseIndexer",
    "IndexerFactory",
    "create_indexer_from_config",
]
