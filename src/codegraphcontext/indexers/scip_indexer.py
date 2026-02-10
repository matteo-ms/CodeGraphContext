"""
SCIP Indexer Implementation

This module implements the SCIP-based indexer for 100% accurate code intelligence.
It uses scip-python (Pyright-based) to generate SCIP indexes.
"""

import subprocess
import shutil
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from . import (
    BaseIndexer,
    IndexerConfig,
    IndexResult,
    SymbolInfo,
    ReferenceInfo,
    IndexerType
)

logger = logging.getLogger(__name__)


class SCIPIndexer(BaseIndexer):
    """
    SCIP-based indexer using scip-python (Pyright).
    
    This indexer provides compiler-level accuracy by using Pyright's
    type checker to resolve symbols, types, and references.
    
    Workflow:
    1. Run scip-python via subprocess to generate .scip file
    2. Parse the .scip file (Protobuf format)
    3. Convert SCIP data to CGC's IndexResult format
    """
    
    def __init__(self, config: IndexerConfig):
        super().__init__(config)
        self.scip_binary = config.scip_binary_path or "npx"
        self.scip_args = ["@sourcegraph/scip-python", "index"]
        
    def is_available(self) -> bool:
        """
        Check if scip-python is available.
        
        Returns:
            True if scip-python can be executed
        """
        try:
            # Check if npx is available
            result = subprocess.run(
                ["npx", "--version"],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                return False
            
            # Check if scip-python package is available
            result = subprocess.run(
                ["npx", "@sourcegraph/scip-python", "--version"],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def get_version(self) -> str:
        """
        Get scip-python version.
        
        Returns:
            Version string or "unknown"
        """
        try:
            result = subprocess.run(
                ["npx", "@sourcegraph/scip-python", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return "unknown"
        except Exception:
            return "unknown"
    
    def index(self) -> IndexResult:
        """
        Index the project using SCIP.
        
        Returns:
            IndexResult with all symbols and references
            
        Raises:
            RuntimeError: If indexing fails
        """
        if not self.validate_project():
            raise ValueError(f"Invalid project root: {self.project_root}")
        
        logger.info(f"Starting SCIP indexing for {self.project_root}")
        
        # Step 1: Generate SCIP index
        scip_file = self._generate_scip_index()
        
        # Step 2: Parse SCIP file
        scip_data = self._parse_scip_file(scip_file)
        
        # Step 3: Convert to IndexResult
        result = self._convert_to_index_result(scip_data)
        
        # Cleanup
        if scip_file.exists():
            scip_file.unlink()
        
        logger.info(f"SCIP indexing complete: {len(result.symbols)} symbols, {len(result.references)} references")
        
        return result
    
    def _generate_scip_index(self) -> Path:
        """
        Run scip-python to generate .scip file.
        
        Returns:
            Path to generated .scip file
            
        Raises:
            RuntimeError: If scip-python execution fails
        """
        output_file = self.project_root / "index.scip"
        
        cmd = [
            "npx",
            "@sourcegraph/scip-python",
            "index",
            "--cwd", str(self.project_root),
            "--output", str(output_file),
        ]
        
        # Add environment if specified
        if self.config.scip_environment:
            cmd.extend(["--environment", self.config.scip_environment])
        
        logger.debug(f"Running SCIP command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                cwd=self.project_root
            )
            
            if result.returncode != 0:
                error_msg = f"SCIP indexing failed:\n{result.stderr}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            if not output_file.exists():
                raise RuntimeError(f"SCIP file not generated at {output_file}")
            
            logger.info(f"SCIP file generated: {output_file} ({output_file.stat().st_size} bytes)")
            return output_file
            
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"SCIP indexing timed out after {self.config.timeout} seconds")
        except FileNotFoundError:
            raise RuntimeError(
                "scip-python not found. Install with: npm install -g @sourcegraph/scip-python"
            )
    
    def _parse_scip_file(self, scip_file: Path) -> Dict:
        """
        Parse SCIP file into structured data.
        
        For now, we'll use scip-python's JSON export feature instead of
        parsing protobuf directly (simpler implementation).
        
        Args:
            scip_file: Path to .scip file
            
        Returns:
            Parsed SCIP data as dictionary
        """
        # Convert .scip to JSON for easier parsing
        json_file = scip_file.with_suffix('.json')
        
        try:
            # scip-python can export to JSON
            cmd = [
                "npx",
                "@sourcegraph/scip-python",
                "print",
                "--input", str(scip_file),
                "--output", str(json_file),
                "--format", "json"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                # Fallback: parse protobuf directly
                logger.warning("JSON export failed, using protobuf parser")
                return self._parse_scip_protobuf(scip_file)
            
            # Read JSON
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Cleanup
            if json_file.exists():
                json_file.unlink()
            
            return data
            
        except Exception as e:
            logger.warning(f"JSON parsing failed: {e}, trying protobuf")
            return self._parse_scip_protobuf(scip_file)
    
    def _parse_scip_protobuf(self, scip_file: Path) -> Dict:
        """
        Parse SCIP protobuf file directly.
        
        This is a fallback if JSON export doesn't work.
        Requires the scip-python protobuf bindings.
        
        Args:
            scip_file: Path to .scip file
            
        Returns:
            Parsed SCIP data
        """
        try:
            # Try to import protobuf bindings
            try:
                from . import scip_pb2
            except ImportError:
                import scip_pb2
            
            with open(scip_file, 'rb') as f:
                index = scip_pb2.Index()
                index.ParseFromString(f.read())
                
                # Convert to dict
                return self._protobuf_to_dict(index)
                
        except ImportError:
            raise RuntimeError(
                "scip-python protobuf bindings not found. "
                "Install with: pip install scip-python"
            )
    
    def _protobuf_to_dict(self, index) -> Dict:
        """
        Convert SCIP protobuf Index to dictionary.
        
        Args:
            index: scip_pb2.Index object
            
        Returns:
            Dictionary representation
        """
        # This is a simplified conversion
        # In production, we'd need full protobuf parsing
        return {
            "metadata": {
                "version": index.metadata.version,
                "project_root": index.metadata.project_root,
            },
            "documents": [
                {
                    "relative_path": doc.relative_path,
                    "language": doc.language,
                    "symbols": [
                        {
                            "symbol": sym.symbol,
                            "documentation": list(sym.documentation),
                        }
                        for sym in doc.symbols
                    ],
                    "occurrences": [
                        {
                            "range": list(occ.range),
                            "symbol": occ.symbol,
                            "symbol_roles": occ.symbol_roles,
                        }
                        for occ in doc.occurrences
                    ]
                }
                for doc in index.documents
            ]
        }
    
    def _convert_to_index_result(self, scip_data: Dict) -> IndexResult:
        """
        Convert SCIP data to CGC's IndexResult format.
        
        Args:
            scip_data: Parsed SCIP data
            
        Returns:
            IndexResult with symbols and references
        """
        symbols = []
        references = []
        files = []
        
        # Process each document
        for document in scip_data.get("documents", []):
            file_path = document["relative_path"]
            files.append(file_path)
            
            # Map definition occurrences by symbol name
            definitions = {}
            for occurrence in document.get("occurrences", []):
                roles = occurrence.get("symbol_roles", 0)
                if roles & 1:  # Definition
                    symbol = occurrence["symbol"]
                    definitions[symbol] = occurrence

            # Process symbols (definitions)
            for symbol_data in document.get("symbols", []):
                symbol_name = symbol_data["symbol"]
                # Find corresponding definition occurrence to get line number
                def_occurrence = definitions.get(symbol_name)
                
                symbol_info = self._parse_symbol(symbol_data, file_path, def_occurrence)
                if symbol_info:
                    symbols.append(symbol_info)
            
            # Add symbols that have definition but no symbol info (if any)
            for symbol_name, def_occurrence in definitions.items():
                # Check if we already processed this symbol
                if not any(s.name == symbol_name for s in symbols if s.file_path == file_path):
                     # Create symbol info from occurrence only
                     symbol_info = self._create_symbol_from_occurrence(def_occurrence, file_path)
                     if symbol_info:
                         symbols.append(symbol_info)
            
            # Process occurrences (references)
            for occurrence in document.get("occurrences", []):
                ref_info = self._parse_occurrence(occurrence, file_path)
                if ref_info:
                    references.append(ref_info)
        
        return IndexResult(
            symbols=symbols,
            references=references,
            files=files,
            indexer_type=IndexerType.SCIP,
            metadata={
                "scip_version": scip_data.get("metadata", {}).get("version", "unknown"),
                "project_root": str(self.project_root),
            }
        )
    
    def _parse_symbol(self, symbol_data: Dict, file_path: str, def_occurrence: Optional[Dict] = None) -> Optional[SymbolInfo]:
        """
        Parse SCIP symbol into SymbolInfo.
        
        SCIP symbol format: "scip-python python <pkg> <version> <path>`<symbol>"
        Example: "scip-python python myproject 1.0.0 src/main.py`MyClass#method"
        
        Args:
            symbol_data: SCIP symbol data
            file_path: File containing the symbol
            def_occurrence: Optional occurrence defining the symbol (for location)
            
        Returns:
            SymbolInfo or None if parsing fails
        """
        try:
            symbol_str = symbol_data["symbol"]
            
            # Use line number from definition occurrence if available
            line_number = 0
            if def_occurrence:
                range_data = def_occurrence.get("range", [])
                if len(range_data) >= 1:
                    line_number = range_data[0]
            
            # Parse symbol string
            # Format: "scip-python python <pkg> <version> <path>`<descriptor>"
            parts = symbol_str.split(' ')
            if len(parts) < 3: # allow shorter symbols
                 # Try to guess
                 path_part = "unknown"
                 symbol_part = symbol_str
            else:
                descriptor = parts[-1]  # "path`Class#method"
                
                if '`' in descriptor:
                    path_part, symbol_part = descriptor.split('`', 1)
                else:
                    symbol_part = descriptor
            
            # Determine symbol kind and name
            if '#' in symbol_part:
                # Method: "Class#method"
                class_parts = symbol_part.split('#')
                name = class_parts[-1]
                parent = class_parts[-2] if len(class_parts) > 1 else None
                kind = "method"
            elif '.' in symbol_part and not symbol_part.startswith('.'):
                # Class or module
                kind = "class"
                name = symbol_part.split('.')[-1]
                parent = None
            else:
                # Function or variable
                kind = "function"
                name = symbol_part
                parent = None
            
            # Basic validation
            if not name:
                return None

            # Sanitize name for compatibility with Tree-sitter (remove signature)
            if '(' in name:
                name = name.split('(')[0]

            return SymbolInfo(
                name=name,
                scip_symbol=symbol_str,
                kind=kind,
                file_path=file_path,
                line_number=line_number, 
                column_number=0,
                signature=None,
                documentation='\n'.join(symbol_data.get("documentation", [])),
                parent_symbol=parent,
            )
            
        except Exception as e:
            logger.debug(f"Failed to parse symbol: {e}")
            return None
    
    def _parse_occurrence(self, occurrence: Dict, file_path: str) -> Optional[ReferenceInfo]:
        """
        Parse SCIP occurrence into ReferenceInfo.
        
        Args:
            occurrence: SCIP occurrence data
            file_path: File containing the occurrence
            
        Returns:
            ReferenceInfo or None
        """
        try:
            # SCIP range format: [start_line, start_col, end_line, end_col] or [start_line, start_col, length]
            range_data = occurrence.get("range", [])
            if len(range_data) < 3:
                return None
            
            line_number = range_data[0]
            column_number = range_data[1]
            
            symbol = occurrence["symbol"]
            symbol_roles = occurrence.get("symbol_roles", 0)
            
            # Determine reference type based on symbol roles
            # SCIP SymbolRole enum:
            # Definition = 1, Import = 2, WriteAccess = 4, ReadAccess = 8, etc.
            if symbol_roles & 1:  # Definition
                ref_type = "definition"
            elif symbol_roles & 2:  # Import
                ref_type = "import"
            else:  # Reference (likely a call)
                ref_type = "call"
            
            return ReferenceInfo(
                source_symbol="",  # We'll need to resolve this from context
                target_symbol=symbol,
                reference_type=ref_type,
                file_path=file_path,
                line_number=line_number,
                column_number=column_number,
            )
            
        except Exception as e:
            logger.debug(f"Failed to parse occurrence: {e}")
            return None

    def _create_symbol_from_occurrence(self, occurrence: Dict, file_path: str) -> Optional[SymbolInfo]:
        """Create SymbolInfo from a definition occurrence when no symbol documentation exists."""
        symbol_data = {"symbol": occurrence["symbol"], "documentation": []}
        return self._parse_symbol(symbol_data, file_path, occurrence)
