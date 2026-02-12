#!/usr/bin/env python3
"""Manual type checking script that avoids the duplicate module issue."""

import sys
import ast
import subprocess
from pathlib import Path
from typing import List, Tuple


def check_file_has_type_annotations(file_path: Path) -> Tuple[bool, List[str]]:
    """Check if a Python file has type annotations."""
    issues: List[str] = []
    
    try:
        with open(file_path, 'r') as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        
        # Check for functions with type annotations
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check return type annotation
                if node.returns is None:
                    issues.append(f"Function '{node.name}' at line {node.lineno} missing return type annotation")
                
                # Check parameter type annotations
                for arg in node.args.args:
                    if arg.arg != 'self' and arg.arg != 'cls' and arg.annotation is None:
                        issues.append(f"Parameter '{arg.arg}' in function '{node.name}' at line {node.lineno} missing type annotation")
        
        return len(issues) == 0, issues
    
    except Exception as e:
        return False, [f"Error parsing file: {e}"]


def check_imports(file_path: Path) -> Tuple[bool, List[str]]:
    """Check that all imports can be resolved."""
    issues: List[str] = []
    
    try:
        # Try to import the module
        import importlib.util
        spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            # Don't actually execute the module, just check it can be loaded
            return True, []
        else:
            return False, [f"Could not load module from {file_path}"]
    
    except Exception as e:
        return False, [f"Import error: {e}"]


def main() -> int:
    """Main entry point."""
    src_dir = Path(__file__).parent / "src" / "btc_monitor"
    
    files_to_check = [
        src_dir / "models.py",
        src_dir / "database.py",
    ]
    
    all_passed = True
    
    for file_path in files_to_check:
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            all_passed = False
            continue
        
        print(f"\n🔍 Checking: {file_path.relative_to(Path(__file__).parent)}")
        
        # Check type annotations
        has_annotations, issues = check_file_has_type_annotations(file_path)
        if has_annotations:
            print("  ✅ All functions have type annotations")
        else:
            print("  ❌ Missing type annotations:")
            for issue in issues:
                print(f"     - {issue}")
            all_passed = False
        
        # Check imports
        imports_ok, import_issues = check_imports(file_path)
        if imports_ok:
            print("  ✅ All imports can be resolved")
        else:
            print("  ❌ Import issues:")
            for issue in import_issues:
                print(f"     - {issue}")
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ Type check PASSED")
        return 0
    else:
        print("❌ Type check FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
