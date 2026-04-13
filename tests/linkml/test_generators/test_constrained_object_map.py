"""Test for constrained object maps (issue with any_of value constraints in inlined dicts)."""
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import jsonschema
import pytest

from linkml.generators.jsonschemagen import JsonSchemaGenerator


pytestmark = pytest.mark.jsonschemagen


CONSTRAINED_MAP_SCHEMA = """
id: https://w3id.org/linkml/test_constrained_map
name: test_constrained_map
prefixes:
  linkml: https://w3id.org/linkml/
default_prefix: https://w3id.org/linkml/test/
imports:
  - linkml:types

classes:
  QualityAssessment:
    description: A quality assessment with constrained assessment values
    tree_root: true
    attributes:
      assessment_method:
        range: string
        required: true
      assessment_values:
        description: Main values produced by the quality assessment
        required: true
        range: Any
        any_of:
          - range: string
          - range: AssessmentValue
            multivalued: true
            inlined: true
            inlined_as_list: false

  AssessmentValue:
    description: Key-value pair representing a specific value produced by a quality assessment
    slots:
      - key
      - value

slots:
  key:
    range: string
    required: true
    identifier: true

  value:
    description: Value corresponding to the assessment key
    range: Any
    required: true
    any_of:
      - range: float
      - range: boolean
      - range: integer
      - range: string
"""


def test_constrained_object_map_schema_generation():
    """Test that constrained object maps generate correct JSON Schema."""
    with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(CONSTRAINED_MAP_SCHEMA)
        f.flush()
        schema_file = f.name

    try:
        generator = JsonSchemaGenerator(
            schema_file,
            top_class="QualityAssessment",
        )
        schema = json.loads(generator.serialize())

        # Check that QualityAssessment class is at root
        assert "properties" in schema
        assert "assessment_method" in schema["properties"]
        assert "assessment_values" in schema["properties"]

        # Check assessment_values structure
        av_schema = schema["properties"]["assessment_values"]
        assert "anyOf" in av_schema
        assert len(av_schema["anyOf"]) == 2

        # First option should be string
        assert av_schema["anyOf"][0] == {"type": "string"}

        # Second option should be object with constrained additionalProperties
        dict_schema = av_schema["anyOf"][1]
        assert dict_schema["type"] == "object"
        assert "additionalProperties" in dict_schema

        # Check that additionalProperties only contains the value constraints,
        # NOT a reference to the AssessmentValue class
        add_props = dict_schema["additionalProperties"]
        assert "anyOf" in add_props

        # Should contain the value types: float, boolean, integer, string
        types_in_anyOf = [item.get("type") for item in add_props["anyOf"]]
        assert set(types_in_anyOf) == {"number", "boolean", "integer", "string"}

        # Should NOT contain a $ref to AssessmentValue
        for item in add_props["anyOf"]:
            assert "$ref" not in item, "additionalProperties should not reference the wrapper class"

        # Check that AssessmentValue__identifier_optional is NOT created
        # (since we're using only value constraints, not the wrapper)
        defs = schema.get("$defs", {})
        assert "AssessmentValueIdentifierOptional" not in defs
        assert "AssessmentValue__identifier_optional" not in defs
    finally:
        Path(schema_file).unlink()


def test_constrained_object_map_validation():
    """Test that valid and invalid data is validated correctly."""
    with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(CONSTRAINED_MAP_SCHEMA)
        f.flush()
        schema_file = f.name

    try:
        generator = JsonSchemaGenerator(
            schema_file,
            top_class="QualityAssessment",
        )
        schema = json.loads(generator.serialize())

        # Valid data: dict with scalar values matching the constraints
        valid_data = {
            "assessment_method": "test-method",
            "assessment_values": {
                "metric1": 0.5,
                "metric2": 100,
                "metric3": True,
                "metric4": "string_value",
            },
        }
        jsonschema.validate(valid_data, schema)  # Should not raise

        # Valid data: string value for assessment_values
        valid_data_string = {
            "assessment_method": "test-method",
            "assessment_values": "some_string",
        }
        jsonschema.validate(valid_data_string, schema)  # Should not raise

        # Invalid data: dict with object value (should fail)
        invalid_data_with_object = {
            "assessment_method": "test-method",
            "assessment_values": {
                "metric1": {"key": "metric1", "value": 0.5},  # Should not be allowed
            },
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_data_with_object, schema)

        # Invalid data: dict with unsupported type
        invalid_data_with_array = {
            "assessment_method": "test-method",
            "assessment_values": {
                "metric1": [1, 2, 3],  # Arrays not in constraint
            },
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_data_with_array, schema)
    finally:
        Path(schema_file).unlink()


def test_constrained_object_map_no_identifier_optional_def():
    """Test that __identifier_optional variant is not created for constrained maps."""
    with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(CONSTRAINED_MAP_SCHEMA)
        f.flush()
        schema_file = f.name

    try:
        generator = JsonSchemaGenerator(
            schema_file,
            top_class="QualityAssessment",
        )
        schema = json.loads(generator.serialize())

        # Check that AssessmentValue class exists (for reference in $defs)
        defs = schema.get("$defs", {})
        assert "AssessmentValue" in defs

        # But AssessmentValue__identifier_optional should NOT exist
        # because the constrained map pattern only uses the value slot constraints
        assert "AssessmentValueIdentifierOptional" not in defs
        assert "AssessmentValue__identifier_optional" not in defs
    finally:
        Path(schema_file).unlink()

