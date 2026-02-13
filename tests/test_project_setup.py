"""Tests for project setup and structure."""

import os
import sys
from pathlib import Path
import subprocess


def test_project_structure():
    """Test that the project has the correct directory structure."""
    project_root = Path(__file__).parent.parent
    required_dirs = [
        project_root / "src",
        project_root / "src" / "btc_monitor",
        project_root / "tests",
        project_root / "config",
    ]
    
    for dir_path in required_dirs:
        assert dir_path.exists(), f"Required directory {dir_path} does not exist"
        assert dir_path.is_dir(), f"{dir_path} is not a directory"


def test_init_files_exist():
    """Test that __init__.py files exist in the right places."""
    project_root = Path(__file__).parent.parent
    init_files = [
        project_root / "src" / "__init__.py",
        project_root / "src" / "btc_monitor" / "__init__.py",
        project_root / "tests" / "__init__.py",
        project_root / "config" / "__init__.py",
    ]
    
    for init_file in init_files:
        assert init_file.exists(), f"Required __init__.py {init_file} does not exist"


def test_pyproject_toml_exists():
    """Test that pyproject.toml exists and contains required dependencies."""
    project_root = Path(__file__).parent.parent
    pyproject = project_root / "pyproject.toml"
    
    assert pyproject.exists(), "pyproject.toml does not exist"
    
    # Read and check for required dependencies
    import toml
    config = toml.load(pyproject)
    
    required_deps = [
        "pandas",
        "numpy",
        "yfinance",
        "tweepy",
        "requests",
        "beautifulsoup4",
        "TA-Lib",
        "SQLAlchemy",
        "pydantic",
    ]
    
    deps = config.get("project", {}).get("dependencies", [])
    
    for dep in required_deps:
        # Check if the dependency is in the list (allowing for version specs)
        found = any(dep.lower() in d.lower() for d in deps)
        assert found, f"Required dependency {dep} not found in pyproject.toml"


def test_pytest_ini_exists():
    """Test that pytest.ini exists."""
    project_root = Path(__file__).parent.parent
    pytest_ini = project_root / "pytest.ini"
    
    assert pytest_ini.exists(), "pytest.ini does not exist"


def test_mypy_ini_exists():
    """Test that mypy.ini exists."""
    project_root = Path(__file__).parent.parent
    mypy_ini = project_root / "mypy.ini"
    
    assert mypy_ini.exists(), "mypy.ini does not exist"


def test_gitignore_exists():
    """Test that .gitignore exists and contains Python-specific patterns."""
    project_root = Path(__file__).parent.parent
    gitignore = project_root / ".gitignore"
    
    assert gitignore.exists(), ".gitignore does not exist"
    
    content = gitignore.read_text()
    
    required_patterns = ["__pycache__", ".venv"]
    
    for pattern in required_patterns:
        assert pattern in content, f"Required pattern '{pattern}' not in .gitignore"
    
    # Check for .pyc patterns (either literal or glob pattern like *.py[cod])
    assert "*.py" in content, "Python file patterns not found in .gitignore"


def test_btc_monitor_package_importable():
    """Test that the btc_monitor package can be imported."""
    try:
        import btc_monitor
        # Package exists and can be imported - check for expected attributes
        # If the package has no __version__ attribute, that's okay at this stage
        # The important thing is that it can be imported
    except ImportError as e:
        raise AssertionError(
            f"btc_monitor package cannot be imported. "
            f"Ensure the package is installed with 'pip install -e .'. "
            f"ImportError: {e}"
        )


def test_config_directory_has_files():
    """Test that config directory has configuration files."""
    project_root = Path(__file__).parent.parent
    config_dir = project_root / "config"
    
    assert config_dir.exists(), "config directory does not exist"
    
    # Check for at least one config file
    config_files = list(config_dir.glob("*.yaml")) + list(config_dir.glob("*.yml"))
    assert len(config_files) > 0, "No YAML configuration files found in config/"
