"""
Tests for golden sample utilities.

Tests cover:
- Saving samples with various data types (dict, list, Pydantic models)
- Loading samples from disk
- Metadata inclusion
- Filename generation with timestamps
- Listing samples with and without filters
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from src.utils.samples import list_golden_samples, load_golden_sample, save_golden_sample


class SampleModel(BaseModel):
    """Test Pydantic model."""

    id: int
    name: str
    value: float


class LegacyModel:
    """Test model with legacy dict() method."""

    def __init__(self, data: dict[str, Any]):
        self._data = data

    def dict(self) -> dict[str, Any]:
        """Return dict representation."""
        return self._data


class TestSaveGoldenSample:
    """Test save_golden_sample function."""

    def test_save_dict_sample(self):
        """Test saving a dictionary sample."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            sample_data = {"id": 1, "name": "test"}

            filepath = save_golden_sample(
                data=sample_data,
                name="test_item",
                source="test",
                output_dir=output_dir,
            )

            assert filepath.exists()
            assert filepath.suffix == ".json"
            assert filepath.parent == output_dir
            assert filepath.name.startswith("test_test_item_")

            # Verify content
            with open(filepath) as f:
                content = json.load(f)
            assert content["data"] == sample_data
            assert content["_meta"]["name"] == "test_item"
            assert content["_meta"]["source"] == "test"
            assert "captured_at" in content["_meta"]
            assert content["_meta"]["captured_at"].endswith("Z")

    def test_save_list_sample(self):
        """Test saving a list sample."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            sample_data = [{"id": 1}, {"id": 2}, {"id": 3}]

            filepath = save_golden_sample(
                data=sample_data,
                name="test_list",
                source="test",
                output_dir=output_dir,
            )

            assert filepath.exists()
            with open(filepath) as f:
                content = json.load(f)
            assert content["data"] == sample_data

    def test_save_pydantic_model(self):
        """Test saving a Pydantic model (converts via model_dump)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            model = SampleModel(id=1, name="test", value=3.14)

            filepath = save_golden_sample(
                data=model,
                name="pydantic_item",
                source="test",
                output_dir=output_dir,
            )

            assert filepath.exists()
            with open(filepath) as f:
                content = json.load(f)
            assert content["data"]["id"] == 1
            assert content["data"]["name"] == "test"
            assert content["data"]["value"] == 3.14

    def test_save_legacy_model(self):
        """Test saving a model with legacy dict() method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            model = LegacyModel({"id": 1, "legacy": True})

            filepath = save_golden_sample(
                data=model,
                name="legacy_item",
                source="test",
                output_dir=output_dir,
            )

            assert filepath.exists()
            with open(filepath) as f:
                content = json.load(f)
            assert content["data"]["id"] == 1
            assert content["data"]["legacy"] is True

    def test_save_list_of_models(self):
        """Test saving a list of Pydantic models."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            models = [
                SampleModel(id=1, name="first", value=1.0),
                SampleModel(id=2, name="second", value=2.0),
            ]

            filepath = save_golden_sample(
                data=models,
                name="model_list",
                source="test",
                output_dir=output_dir,
            )

            assert filepath.exists()
            with open(filepath) as f:
                content = json.load(f)
            assert len(content["data"]) == 2
            assert content["data"][0]["name"] == "first"
            assert content["data"][1]["name"] == "second"

    def test_save_with_metadata(self):
        """Test saving sample with custom metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            sample_data = {"test": "data"}
            metadata = {"version": "1.0", "environment": "test"}

            filepath = save_golden_sample(
                data=sample_data,
                name="test_meta",
                source="test",
                output_dir=output_dir,
                metadata=metadata,
            )

            assert filepath.exists()
            with open(filepath) as f:
                content = json.load(f)
            assert content["_meta"]["version"] == "1.0"
            assert content["_meta"]["environment"] == "test"
            assert content["_meta"]["name"] == "test_meta"

    def test_save_creates_output_dir(self):
        """Test that save_golden_sample creates output directory if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "nested" / "deep" / "dir"
            assert not output_dir.exists()

            filepath = save_golden_sample(
                data={"test": "data"},
                name="test",
                source="test",
                output_dir=output_dir,
            )

            assert output_dir.exists()
            assert filepath.exists()

    def test_save_filename_format(self):
        """Test filename format includes source, name, and timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            filepath = save_golden_sample(
                data={},
                name="my_sample",
                source="abs",
                output_dir=output_dir,
            )

            filename = filepath.name
            assert filename.startswith("abs_my_sample_")
            assert filename.endswith(".json")
            # Verify timestamp format YYYYMMDD_HHMMSS
            # Note: my_sample contains underscore, so splits into 5 parts
            parts = filename.split("_")
            assert len(parts) == 5  # source_name_with_underscore_date_time
            assert parts[0] == "abs"
            assert parts[1] == "my"
            assert parts[2] == "sample"
            assert len(parts[3]) == 8  # YYYYMMDD
            assert len(parts[4]) == 11  # HHMMSS.json

    def test_save_with_non_serializable_objects(self):
        """Test saving data with non-serializable objects (uses default=str)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            now = datetime.now(timezone.utc)
            sample_data = {"timestamp": now, "path": Path("/tmp")}

            filepath = save_golden_sample(
                data=sample_data,
                name="complex",
                source="test",
                output_dir=output_dir,
            )

            assert filepath.exists()
            with open(filepath) as f:
                content = json.load(f)
            # Verify non-serializable objects were converted via str()
            assert isinstance(content["data"]["timestamp"], str)
            assert isinstance(content["data"]["path"], str)

    def test_save_empty_dict(self):
        """Test saving empty dictionary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            filepath = save_golden_sample(
                data={},
                name="empty",
                source="test",
                output_dir=output_dir,
            )

            assert filepath.exists()
            with open(filepath) as f:
                content = json.load(f)
            assert content["data"] == {}

    def test_save_empty_list(self):
        """Test saving empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            filepath = save_golden_sample(
                data=[],
                name="empty_list",
                source="test",
                output_dir=output_dir,
            )

            assert filepath.exists()
            with open(filepath) as f:
                content = json.load(f)
            assert content["data"] == []

    def test_save_captured_at_format(self):
        """Test that captured_at uses ISO format with Z suffix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            filepath = save_golden_sample(
                data={},
                name="test",
                source="test",
                output_dir=output_dir,
            )

            with open(filepath) as f:
                content = json.load(f)
            captured_at = content["_meta"]["captured_at"]
            # Should end with Z (UTC timezone indicator)
            assert captured_at.endswith("Z")
            # Should be parseable as ISO format
            datetime.fromisoformat(captured_at.replace("Z", "+00:00"))

    def test_save_string_source_and_name(self):
        """Test save with various string formats for source and name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Test with underscores and hyphens
            filepath = save_golden_sample(
                data={},
                name="my_complex_sample_v2",
                source="audible-api",
                output_dir=output_dir,
            )

            assert filepath.exists()
            assert "audible-api" in filepath.name
            assert "my_complex_sample_v2" in filepath.name


class TestLoadGoldenSample:
    """Test load_golden_sample function."""

    def test_load_sample(self):
        """Test loading a saved sample."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            original_data = {"id": 1, "name": "test", "nested": {"key": "value"}}

            filepath = save_golden_sample(
                data=original_data,
                name="test",
                source="test",
                output_dir=output_dir,
                metadata={"custom": "meta"},
            )

            # Load and verify
            loaded = load_golden_sample(filepath)
            assert loaded["data"] == original_data
            assert loaded["_meta"]["name"] == "test"
            assert loaded["_meta"]["source"] == "test"
            assert loaded["_meta"]["custom"] == "meta"
            assert "captured_at" in loaded["_meta"]

    def test_load_sample_with_list_data(self):
        """Test loading a sample containing list data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            list_data = [{"id": 1}, {"id": 2}, {"id": 3}]

            filepath = save_golden_sample(
                data=list_data,
                name="list_sample",
                source="test",
                output_dir=output_dir,
            )

            loaded = load_golden_sample(filepath)
            assert loaded["data"] == list_data

    def test_load_preserves_data_types(self):
        """Test that loading preserves original data types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            original = {
                "string": "test",
                "int": 42,
                "float": 3.14,
                "bool": True,
                "none": None,
                "list": [1, 2, 3],
            }

            filepath = save_golden_sample(
                data=original,
                name="types",
                source="test",
                output_dir=output_dir,
            )

            loaded = load_golden_sample(filepath)
            assert loaded["data"]["string"] == "test"
            assert loaded["data"]["int"] == 42
            assert loaded["data"]["float"] == 3.14
            assert loaded["data"]["bool"] is True
            assert loaded["data"]["none"] is None
            assert loaded["data"]["list"] == [1, 2, 3]


class TestListGoldenSamples:
    """Test list_golden_samples function."""

    def test_list_empty_directory(self):
        """Test listing samples from empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            samples = list_golden_samples(Path(tmpdir))
            assert samples == []

    def test_list_nonexistent_directory(self):
        """Test listing from non-existent directory."""
        nonexistent = Path("/nonexistent/path/to/samples")
        samples = list_golden_samples(nonexistent)
        assert samples == []

    def test_list_all_samples(self):
        """Test listing all samples without filter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create multiple samples
            save_golden_sample({}, "item1", "abs", output_dir)
            save_golden_sample({}, "item2", "audible", output_dir)
            save_golden_sample({}, "item3", "abs", output_dir)

            samples = list_golden_samples(output_dir)
            assert len(samples) == 3
            # All should be .json files
            assert all(s.suffix == ".json" for s in samples)
            # Should be sorted
            assert samples == sorted(samples)

    def test_list_filtered_by_source(self):
        """Test listing samples filtered by source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create samples with different sources
            save_golden_sample({}, "item1", "abs", output_dir)
            save_golden_sample({}, "item2", "audible", output_dir)
            save_golden_sample({}, "item3", "abs", output_dir)

            abs_samples = list_golden_samples(output_dir, source="abs")
            assert len(abs_samples) == 2
            assert all("abs_" in s.name for s in abs_samples)

            audible_samples = list_golden_samples(output_dir, source="audible")
            assert len(audible_samples) == 1
            assert "audible_" in audible_samples[0].name

    def test_list_sorted_order(self):
        """Test that samples are returned in sorted order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create samples (order may vary)
            save_golden_sample({}, "zebra", "test", output_dir)
            save_golden_sample({}, "apple", "test", output_dir)
            save_golden_sample({}, "mango", "test", output_dir)

            samples = list_golden_samples(output_dir)
            names = [s.name for s in samples]
            assert names == sorted(names)

    def test_list_nonmatching_filter(self):
        """Test listing with filter that matches no files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            save_golden_sample({}, "item", "abs", output_dir)

            # Filter for non-existent source
            samples = list_golden_samples(output_dir, source="nonexistent")
            assert samples == []

    def test_list_with_non_json_files(self):
        """Test listing ignores non-JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create a JSON sample
            save_golden_sample({}, "item", "test", output_dir)

            # Create non-JSON files
            (output_dir / "readme.txt").write_text("not a sample")
            (output_dir / "notes.md").write_text("# Notes")

            # When listing all, only JSON files should be returned
            samples = list_golden_samples(output_dir)
            assert all(s.suffix == ".json" for s in samples)
            # But non-JSON might match glob if no filter
            # Actually, glob("*.json") won't match .txt or .md
            assert all(".json" in s.name for s in samples)

    def test_list_multiple_items_same_source(self):
        """Test listing multiple items from same source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            for i in range(5):
                save_golden_sample({}, f"item{i}", "abs", output_dir)

            abs_samples = list_golden_samples(output_dir, source="abs")
            assert len(abs_samples) == 5
            assert all("abs_item" in s.name for s in abs_samples)


class TestIntegration:
    """Integration tests for save, load, and list."""

    def test_roundtrip_save_load(self):
        """Test save and load roundtrip preserves data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            original_data = {
                "complex": {
                    "nested": {"data": [1, 2, 3]},
                    "value": 42,
                },
                "items": ["a", "b", "c"],
            }
            metadata = {"version": "1.0"}

            # Save
            filepath = save_golden_sample(
                data=original_data,
                name="complex",
                source="test",
                output_dir=output_dir,
                metadata=metadata,
            )

            # Load
            loaded = load_golden_sample(filepath)

            # Verify
            assert loaded["data"] == original_data
            assert loaded["_meta"]["version"] == "1.0"

    def test_save_and_list_workflow(self):
        """Test typical workflow of saving multiple samples and listing them."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Save multiple samples
            for i in range(3):
                save_golden_sample(
                    {"index": i},
                    f"sample{i}",
                    "abs",
                    output_dir,
                )

            for i in range(2):
                save_golden_sample(
                    {"index": i},
                    f"search{i}",
                    "audible",
                    output_dir,
                )

            # List all
            all_samples = list_golden_samples(output_dir)
            assert len(all_samples) == 5

            # List by source
            abs_samples = list_golden_samples(output_dir, source="abs")
            audible_samples = list_golden_samples(output_dir, source="audible")
            assert len(abs_samples) == 3
            assert len(audible_samples) == 2

            # Verify we can load any of them
            for sample_path in all_samples:
                loaded = load_golden_sample(sample_path)
                assert "_meta" in loaded
                assert "data" in loaded
