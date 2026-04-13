"""Test for constrained object maps in Pydantic generator."""
import pytest

from linkml.generators.pydanticgen import PydanticGenerator


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


pytestmark = pytest.mark.pydanticgen


def test_constrained_object_map_pydantic_type():
    """Test that constrained object maps generate correct Pydantic types."""
    generator = PydanticGenerator(CONSTRAINED_MAP_SCHEMA)
    code = generator.serialize()

    # Check that the generated type is a Union of dict and str
    assert "assessment_values: Union[dict[str, Union[float, bool, int, str]], str]" in code, (
        "assessment_values should be Union of constrained dict and str, without wrapper class reference"
    )

    # Verify the dict has constrained value types, not the wrapper class
    assert "AssessmentValueIdentifierOptional" not in code, "Should not reference wrapper class"
    assert "AssessmentValue__identifier_optional" not in code, "Should not reference wrapper class"


def test_constrained_object_map_value_type():
    """Test that the value slot has the correct Union type."""
    generator = PydanticGenerator(CONSTRAINED_MAP_SCHEMA)
    code = generator.serialize()

    # Check that the value slot in AssessmentValue has the correct type
    assert "value: Union[bool, float, int, str]" in code, "value slot should be Union of constrained types"

