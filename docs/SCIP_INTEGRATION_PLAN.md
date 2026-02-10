# SCIP Integration Technical Specification

## Executive Summary

This document outlines the **exact technical approach** for integrating SCIP (Sourcegraph Code Intelligence Protocol) into CodeGraphContext to achieve 100% accurate code indexing.

---

## Background: Why SCIP?

### Current State (Tree-sitter)
- **Accuracy**: ~85-90% for cross-file references
- **Method**: AST-based syntax parsing
- **Limitation**: Cannot resolve types without running type checker

### Target State (SCIP)
- **Accuracy**: ~99-100% (compiler-level)
- **Method**: Uses actual type checker (Pyright for Python)
- **Advantage**: Knows exact types, handles dynamic features

---

## Integration Architecture

### Option 1: External SCIP Indexer (RECOMMENDED)

```
┌─────────────────────────────────────────────────────────────┐
│                    CodeGraphContext                          │
│                                                              │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │   CLI/MCP    │         │  Indexer     │                 │
│  │   Interface  │────────▶│  Manager     │                 │
│  └──────────────┘         └──────┬───────┘                 │
│                                   │                          │
│                    ┌──────────────┴──────────────┐          │
│                    │                             │          │
│           ┌────────▼────────┐         ┌─────────▼────────┐ │
│           │  Tree-sitter    │         │  SCIP Indexer    │ │
│           │  Indexer        │         │  (New)           │ │
│           │  (Existing)     │         │                  │ │
│           └────────┬────────┘         └─────────┬────────┘ │
│                    │                             │          │
│                    │         ┌───────────────────┘          │
│                    │         │                              │
│                    │         │  1. Run scip-python          │
│                    │         │     via subprocess           │
│                    │         │                              │
│                    │         │  2. Generate .scip file      │
│                    │         │     (Protobuf format)        │
│                    │         │                              │
│                    │         │  3. Parse .scip file         │
│                    │         │     using scip-python lib    │
│                    │         │                              │
│                    └─────────▼──────────────────────────────┤
│                    │   Graph Builder                        │
│                    │   (Unified Node/Edge Creation)         │
│                    └────────────────┬───────────────────────┤
│                                     │                        │
│                    ┌────────────────▼───────────────────┐   │
│                    │   Neo4j / FalkorDB                  │   │
│                    │   (Code Knowledge Graph)            │   │
│                    └─────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Details

#### Step 1: Install SCIP Dependencies

```bash
# Add to pyproject.toml
[tool.poetry.dependencies]
scip-python = "^0.3.0"  # Python bindings for SCIP protocol
protobuf = "^4.25.0"     # For parsing .scip files
```

#### Step 2: Create SCIP Indexer Module

**File Structure:**
```
src/codegraphcontext/indexers/
├── __init__.py
├── base.py                    # Abstract base class
├── tree_sitter_indexer.py     # Existing (refactored)
├── scip/
│   ├── __init__.py
│   ├── scip_indexer.py        # Main SCIP indexer
│   ├── scip_parser.py         # Parse .scip protobuf files
│   ├── scip_runner.py         # Run scip-python subprocess
│   └── scip_converter.py      # Convert SCIP data to CGC graph format
```

#### Step 3: SCIP Indexer Implementation

**Core Logic:**

```python
# src/codegraphcontext/indexers/scip/scip_indexer.py

import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
import scip_pb2  # Generated from SCIP protobuf schema

class SCIPIndexer:
    """
    SCIP-based indexer for 100% accurate code intelligence.
    Uses scip-python (Pyright-based) for Python projects.
    """
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.scip_file = None
        
    def index(self) -> Dict:
        """
        Main indexing workflow:
        1. Run scip-python to generate .scip file
        2. Parse the .scip file
        3. Convert to CGC graph format
        """
        # Step 1: Generate SCIP index
        scip_file = self._run_scip_indexer()
        
        # Step 2: Parse SCIP protobuf
        scip_data = self._parse_scip_file(scip_file)
        
        # Step 3: Convert to CGC format
        graph_data = self._convert_to_graph(scip_data)
        
        return graph_data
    
    def _run_scip_indexer(self) -> Path:
        """
        Run scip-python via subprocess to generate .scip file.
        
        Command: npx @sourcegraph/scip-python index --project-root .
        """
        output_file = self.project_root / "index.scip"
        
        cmd = [
            "npx",
            "@sourcegraph/scip-python",
            "index",
            "--project-root", str(self.project_root),
            "--output", str(output_file)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"SCIP indexing failed: {result.stderr}")
            
            return output_file
            
        except FileNotFoundError:
            raise RuntimeError(
                "scip-python not found. Install with: npm install -g @sourcegraph/scip-python"
            )
    
    def _parse_scip_file(self, scip_file: Path) -> scip_pb2.Index:
        """
        Parse the .scip protobuf file into structured data.
        
        SCIP file structure:
        - metadata: project info, tool version
        - documents: list of source files
        - symbols: definitions and references
        - occurrences: where symbols are used
        """
        with open(scip_file, 'rb') as f:
            index = scip_pb2.Index()
            index.ParseFromString(f.read())
            return index
    
    def _convert_to_graph(self, scip_index: scip_pb2.Index) -> Dict:
        """
        Convert SCIP data to CGC graph format.
        
        SCIP Symbol Format: "scip-python python <package> <version> <path>`<symbol>"
        Example: "scip-python python myproject 1.0.0 src/main.py`MyClass#method"
        
        CGC Graph Format:
        {
            "files": [...],
            "functions": [...],
            "classes": [...],
            "calls": [...],  # CALLS edges
            "imports": [...],  # IMPORTS edges
            "inheritance": [...]  # INHERITS edges
        }
        """
        graph_data = {
            "files": [],
            "functions": [],
            "classes": [],
            "calls": [],
            "imports": [],
            "inheritance": []
        }
        
        # Process each document (source file)
        for document in scip_index.documents:
            file_path = document.relative_path
            
            # Add file node
            graph_data["files"].append({
                "path": file_path,
                "language": document.language
            })
            
            # Process symbols (functions, classes, variables)
            for symbol in document.symbols:
                symbol_info = self._parse_symbol(symbol)
                
                if symbol_info["kind"] == "function":
                    graph_data["functions"].append(symbol_info)
                elif symbol_info["kind"] == "class":
                    graph_data["classes"].append(symbol_info)
            
            # Process occurrences (references, calls)
            for occurrence in document.occurrences:
                if occurrence.symbol_roles & scip_pb2.SymbolRole.Definition:
                    # This is a definition
                    pass
                elif occurrence.symbol_roles & scip_pb2.SymbolRole.Reference:
                    # This is a reference (potential function call)
                    graph_data["calls"].append({
                        "caller": self._get_enclosing_symbol(occurrence),
                        "callee": occurrence.symbol
                    })
        
        return graph_data
    
    def _parse_symbol(self, symbol: scip_pb2.SymbolInformation) -> Dict:
        """
        Parse SCIP symbol into CGC format.
        
        SCIP symbol encoding:
        - Package: scip-python python <pkg> <version>
        - Descriptor: <path>`<class>#<method>
        """
        # Symbol format: "scip-python python myproject 1.0.0 src/main.py`MyClass#method"
        parts = symbol.symbol.split(' ')
        
        # Extract path and symbol name
        descriptor = parts[-1]  # "src/main.py`MyClass#method"
        path, symbol_name = descriptor.split('`')
        
        # Determine symbol kind
        if '#' in symbol_name:
            # Method
            class_name, method_name = symbol_name.split('#')
            return {
                "kind": "function",
                "name": method_name,
                "class": class_name,
                "file": path,
                "signature": symbol.signature_documentation.text if symbol.signature_documentation else ""
            }
        elif '.' in symbol_name:
            # Class
            return {
                "kind": "class",
                "name": symbol_name,
                "file": path,
                "documentation": symbol.documentation[0] if symbol.documentation else ""
            }
        else:
            # Top-level function
            return {
                "kind": "function",
                "name": symbol_name,
                "file": path,
                "signature": symbol.signature_documentation.text if symbol.signature_documentation else ""
            }
```

---

## Option 2: LSP-Based SCIP Generation (Alternative)

Instead of running `scip-python` as a subprocess, we could:

1. **Start Pyright Language Server** in the background
2. **Query LSP for symbol information** (definitions, references)
3. **Convert LSP responses to SCIP format** (or directly to graph)

**Pros:**
- More integrated (no subprocess)
- Can reuse LSP server across multiple queries

**Cons:**
- More complex implementation
- Need to maintain LSP client code
- Pyright LSP doesn't directly output SCIP

---

## Option 3: Hybrid Indexer (Best of Both Worlds)

```python
class HybridIndexer:
    """
    Intelligent indexer that chooses the best strategy:
    - SCIP for Python (if available)
    - Tree-sitter for other languages or fallback
    """
    
    def index(self, project_root: Path) -> Dict:
        # Detect project type
        if self._has_python_project(project_root):
            try:
                return SCIPIndexer(project_root).index()
            except Exception as e:
                logger.warning(f"SCIP indexing failed: {e}, falling back to Tree-sitter")
                return TreeSitterIndexer(project_root).index()
        else:
            return TreeSitterIndexer(project_root).index()
```

---

## Configuration

Add to `.env`:

```bash
# Indexer selection
INDEXER_BACKEND=hybrid  # Options: tree-sitter, scip, hybrid

# SCIP-specific settings
SCIP_ENABLED=true
SCIP_PYTHON_PATH=/usr/local/bin/scip-python  # Optional: custom path
SCIP_TIMEOUT=300  # Timeout in seconds
SCIP_CACHE_DIR=/home/shashank/.codegraphcontext/scip_cache
```

---

## Migration Path

### Phase 1: Proof of Concept (Week 1)
- [ ] Install scip-python
- [ ] Create basic SCIP parser
- [ ] Test on small Python project
- [ ] Compare accuracy with Tree-sitter

### Phase 2: Integration (Week 2-3)
- [ ] Implement full SCIP indexer
- [ ] Add hybrid fallback logic
- [ ] Update CLI to support `--indexer` flag
- [ ] Add configuration options

### Phase 3: Testing & Optimization (Week 4)
- [ ] Test on large projects (Bitcoin, Linux kernel)
- [ ] Performance benchmarking
- [ ] Error handling and edge cases
- [ ] Documentation

### Phase 4: Rollout (Week 5)
- [ ] Make hybrid indexer default
- [ ] Update documentation
- [ ] Release v0.3.0 with SCIP support

---

## Performance Comparison

| Metric | Tree-sitter | SCIP | Hybrid |
|--------|-------------|------|--------|
| **Accuracy** | 85-90% | 99-100% | 99-100% |
| **Speed** | Fast (~0.05s/file) | Slower (~0.2s/file) | Adaptive |
| **Memory** | Low | Higher | Medium |
| **Dependencies** | Python only | Node.js + Python | Both |
| **Cross-file refs** | Heuristic | Precise | Precise |

---

## Example Usage

```bash
# Use SCIP indexer explicitly
cgc index . --indexer scip

# Use hybrid (auto-detect)
cgc index . --indexer hybrid

# Fall back to tree-sitter
cgc index . --indexer tree-sitter

# Check indexer status
cgc doctor --check-scip
```

---

## Technical Challenges & Solutions

### Challenge 1: Node.js Dependency
**Problem**: scip-python requires Node.js/npm  
**Solution**: 
- Check for Node.js in `cgc doctor`
- Provide clear installation instructions
- Fall back to Tree-sitter if unavailable

### Challenge 2: SCIP File Size
**Problem**: .scip files can be large (10MB+ for big projects)  
**Solution**:
- Stream parsing instead of loading entire file
- Cache parsed results
- Clean up .scip files after indexing

### Challenge 3: Type Stubs
**Problem**: Pyright needs type stubs for accurate analysis  
**Solution**:
- Auto-detect virtual environment
- Install type stubs automatically (`pip install types-*`)
- Provide configuration for custom stub paths

---

## Protobuf Schema Reference

SCIP uses Protocol Buffers. Key message types:

```protobuf
message Index {
  Metadata metadata = 1;
  repeated Document documents = 2;
  repeated SymbolInformation external_symbols = 3;
}

message Document {
  string relative_path = 1;
  string language = 2;
  repeated SymbolInformation symbols = 3;
  repeated Occurrence occurrences = 4;
}

message Occurrence {
  repeated int32 range = 1;  // [start_line, start_col, end_line, end_col]
  string symbol = 2;
  int32 symbol_roles = 3;  // Bitmask: Definition, Reference, etc.
}

message SymbolInformation {
  string symbol = 1;  // "scip-python python pkg 1.0.0 path`Class#method"
  repeated string documentation = 2;
  repeated Relationship relationships = 3;  // Inheritance, implementation
}
```

---

## Next Steps

1. **Install scip-python**: `npm install -g @sourcegraph/scip-python`
2. **Test on sample project**: Generate .scip file manually
3. **Implement parser**: Parse .scip file and print symbols
4. **Integrate with graph builder**: Convert SCIP data to Neo4j nodes

---

## References

- SCIP Protocol: https://github.com/sourcegraph/scip
- scip-python: https://github.com/sourcegraph/scip-python
- Pyright: https://github.com/microsoft/pyright
- SCIP vs LSIF: https://about.sourcegraph.com/blog/announcing-scip
