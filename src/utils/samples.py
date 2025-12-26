"""
Golden sample utilities for collecting API response samples.

Used for testing and documentation - captures real API responses
to understand data structures and for offline testing.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


def save_golden_sample(
    data: Any,
    name: str,
    source: str,
    output_dir: Path,
    metadata: Optional[dict] = None,
) -> Path:
    """
    Save a golden sample to disk.
    
    Args:
        data: The data to save (dict, list, or Pydantic model)
        name: Sample name (e.g., "library_item", "catalog_search")
        source: Source API (e.g., "abs", "audible")
        output_dir: Directory to save samples
        metadata: Optional metadata to include
        
    Returns:
        Path to saved sample file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert Pydantic models to dict
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    elif hasattr(data, "dict"):
        data = data.dict()
    
    # If it's a list of models, convert each
    if isinstance(data, list):
        data = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in data
        ]
    
    # Build sample document
    sample = {
        "_meta": {
            "name": name,
            "source": source,
            "captured_at": datetime.utcnow().isoformat() + "Z",
            **(metadata or {}),
        },
        "data": data,
    }
    
    # Generate filename
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{source}_{name}_{timestamp}.json"
    filepath = output_dir / filename
    
    # Save
    with open(filepath, "w") as f:
        json.dump(sample, f, indent=2, default=str)
    
    return filepath


def load_golden_sample(filepath: Path) -> dict:
    """
    Load a golden sample from disk.
    
    Args:
        filepath: Path to sample file
        
    Returns:
        Sample document with _meta and data
    """
    with open(filepath) as f:
        return json.load(f)


def list_golden_samples(
    sample_dir: Path,
    source: Optional[str] = None,
) -> list[Path]:
    """
    List available golden samples.
    
    Args:
        sample_dir: Directory containing samples
        source: Filter by source (abs, audible)
        
    Returns:
        List of sample file paths
    """
    sample_dir = Path(sample_dir)
    if not sample_dir.exists():
        return []
    
    pattern = f"{source}_*.json" if source else "*.json"
    return sorted(sample_dir.glob(pattern))
