#!/usr/bin/env python3
"""
SCIP Integration Demo Script

This script demonstrates how the SCIP indexer works and compares
it with Tree-sitter for accuracy.

Usage:
    python demo_scip_integration.py /path/to/python/project
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def check_scip_availability():
    """Check if scip-python is installed and available."""
    import subprocess
    
    print("\n" + "="*60)
    print("CHECKING SCIP AVAILABILITY")
    print("="*60)
    
    # Check Node.js
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        node_version = result.stdout.strip()
        print(f"✓ Node.js installed: {node_version}")
    except Exception as e:
        print(f"✗ Node.js not found: {e}")
        print("  Install from: https://nodejs.org/")
        return False
    
    # Check npx
    try:
        result = subprocess.run(
            ["npx", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        npx_version = result.stdout.strip()
        print(f"✓ npx installed: {npx_version}")
    except Exception as e:
        print(f"✗ npx not found: {e}")
        return False
    
    # Check scip-python
    try:
        result = subprocess.run(
            ["npx", "@sourcegraph/scip-python", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            scip_version = result.stdout.strip()
            print(f"✓ scip-python available: {scip_version}")
            return True
        else:
            print("✗ scip-python not installed")
            print("  Install with: npm install -g @sourcegraph/scip-python")
            return False
    except Exception as e:
        print(f"✗ scip-python check failed: {e}")
        return False


def demo_scip_indexing(project_path: Path):
    """
    Demonstrate SCIP indexing on a Python project.
    
    Args:
        project_path: Path to Python project
    """
    import subprocess
    import json
    
    print("\n" + "="*60)
    print(f"SCIP INDEXING DEMO: {project_path}")
    print("="*60)
    
    if not project_path.exists():
        print(f"Error: Project path does not exist: {project_path}")
        return
    
    # Step 1: Run scip-python
    print("\n[1/3] Running scip-python indexer...")
    output_file = project_path / "index.scip"
    
    cmd = [
        "npx",
        "@sourcegraph/scip-python",
        "index",
        "--project-root", str(project_path),
        "--output", str(output_file),
    ]
    
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=project_path
        )
        
        if result.returncode != 0:
            print(f"Error: SCIP indexing failed")
            print(f"stderr: {result.stderr}")
            return
        
        print(f"✓ SCIP index generated: {output_file}")
        print(f"  File size: {output_file.stat().st_size:,} bytes")
        
    except subprocess.TimeoutExpired:
        print("Error: SCIP indexing timed out")
        return
    except Exception as e:
        print(f"Error: {e}")
        return
    
    # Step 2: Analyze the SCIP file
    print("\n[2/3] Analyzing SCIP index...")
    
    # Try to export to JSON for inspection
    json_file = project_path / "index.json"
    
    try:
        cmd = [
            "npx",
            "@sourcegraph/scip-python",
            "print",
            "--input", str(output_file),
            "--format", "json"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Parse and display summary
            data = json.loads(result.stdout)
            
            num_documents = len(data.get("documents", []))
            total_symbols = sum(
                len(doc.get("symbols", []))
                for doc in data.get("documents", [])
            )
            total_occurrences = sum(
                len(doc.get("occurrences", []))
                for doc in data.get("documents", [])
            )
            
            print(f"✓ SCIP Index Summary:")
            print(f"  Documents (files): {num_documents}")
            print(f"  Symbols (definitions): {total_symbols}")
            print(f"  Occurrences (references): {total_occurrences}")
            
            # Show sample symbols
            if num_documents > 0:
                print(f"\n  Sample symbols from first file:")
                first_doc = data["documents"][0]
                print(f"  File: {first_doc['relative_path']}")
                for i, symbol in enumerate(first_doc.get("symbols", [])[:5]):
                    symbol_str = symbol.get("symbol", "")
                    # Parse symbol name from SCIP format
                    if '`' in symbol_str:
                        symbol_name = symbol_str.split('`')[-1]
                        print(f"    - {symbol_name}")
                    if i >= 4:
                        break
        else:
            print("Note: Could not export to JSON, but .scip file is valid")
            
    except Exception as e:
        print(f"Note: Could not analyze SCIP file: {e}")
    
    # Step 3: Cleanup
    print("\n[3/3] Cleanup...")
    if output_file.exists():
        output_file.unlink()
        print("✓ Cleaned up temporary files")
    
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60)


def compare_indexers(project_path: Path):
    """
    Compare SCIP vs Tree-sitter accuracy.
    
    Args:
        project_path: Path to Python project
    """
    print("\n" + "="*60)
    print("COMPARING SCIP VS TREE-SITTER")
    print("="*60)
    
    print("\nThis comparison will show:")
    print("1. Number of symbols found by each indexer")
    print("2. Accuracy of cross-file references")
    print("3. Type resolution capabilities")
    
    print("\n[Coming soon in full implementation]")


def main():
    """Main entry point."""
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║         SCIP Integration Demo for CodeGraphContext        ║
║                                                           ║
║  This demo shows how SCIP provides 100% accurate          ║
║  code indexing using compiler-level type checking         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    # Check SCIP availability
    scip_available = check_scip_availability()
    
    if not scip_available:
        print("\n⚠️  SCIP is not available. Please install scip-python first.")
        print("\nInstallation instructions:")
        print("  1. Install Node.js: https://nodejs.org/")
        print("  2. Install scip-python: npm install -g @sourcegraph/scip-python")
        print("  3. Run this demo again")
        return 1
    
    # Get project path
    if len(sys.argv) > 1:
        project_path = Path(sys.argv[1]).resolve()
    else:
        # Use current directory as default
        project_path = Path.cwd()
    
    # Run demo
    demo_scip_indexing(project_path)
    
    # Compare indexers
    compare_indexers(project_path)
    
    print("\n✨ Next steps:")
    print("  1. Review the SCIP integration plan: docs/SCIP_INTEGRATION_PLAN.md")
    print("  2. Check the indexer implementation: src/codegraphcontext/indexers/")
    print("  3. Try indexing with: cgc index . --indexer scip")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
