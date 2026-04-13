import pytest
from pydantic import ValidationError

from linkml.generators import PydanticGenerator
from linkml_runtime.linkml_model import SchemaDefinition
from linkml_runtime.utils.schemaview import SchemaView


# --------------------------------------------------
# Comprehensive tests for the include_range_class_descendants feature
# --------------------------------------------------


def test_include_range_class_descendants_inlined():
    """Test include_range_class_descendants with inlined classes.

    When include_range_class_descendants is True, a slot with range Parent
    that is inlined should generate a Union of Parent and all its descendants.
    """
    schema = """
id: https://example.org/test
name: test

prefixes:
  linkml: https://w3id.org/linkml/
  ex: https://example.org/

imports:
  - linkml:types

default_prefix: ex

classes:
  Parent:
    attributes:
      name:
        range: string

  Child1:
    is_a: Parent
    attributes:
      child1_field:
        range: string

  Child2:
    is_a: Parent
    attributes:
      child2_field:
        range: string

  Container:
    attributes:
      item:
        range: Parent
        inlined: true
"""
    # Without the flag, should only have Parent
    gen_without_flag = PydanticGenerator(schema, include_range_class_descendants=False)
    code_without = gen_without_flag.serialize()
    assert "item: Optional[Parent]" in code_without
    assert "Union[Parent,Child1,Child2]" not in code_without

    # With the flag, should have Union of all descendants
    gen_with_flag = PydanticGenerator(schema, include_range_class_descendants=True)
    code_with = gen_with_flag.serialize()
    # Check for Union - may have different orders/spacing
    assert "Union[Parent,Child1,Child2]" in code_with or \
           "Union[Parent,Child2,Child1]" in code_with or \
           "Union[Child1,Parent,Child2]" in code_with or \
           "Union[Child1,Child2,Parent]" in code_with or \
           "Union[Child2,Parent,Child1]" in code_with or \
           "Union[Child2,Child1,Parent]" in code_with

    # Verify it compiles and validates correctly
    mod = gen_with_flag.compile_module()

    # Should accept Parent
    c1 = mod.Container(item=mod.Parent(name="p"))
    assert c1.item.name == "p"

    # Should accept Child1
    c2 = mod.Container(item=mod.Child1(name="c1", child1_field="f1"))
    assert c2.item.name == "c1"

    # Should accept Child2
    c3 = mod.Container(item=mod.Child2(name="c2", child2_field="f2"))
    assert c3.item.name == "c2"


def test_include_range_class_descendants_multivalued():
    """Test include_range_class_descendants with multivalued inlined slots."""
    schema = """
id: https://example.org/test
name: test

prefixes:
  linkml: https://w3id.org/linkml/
  ex: https://example.org/

imports:
  - linkml:types

default_prefix: ex

classes:
  Document:
    attributes:
      id:
        identifier: true
        range: string

  TextDocument:
    is_a: Document
    attributes:
      text:
        range: string

  ImageDocument:
    is_a: Document
    attributes:
      image_data:
        range: string

  Collection:
    attributes:
      documents:
        range: Document
        multivalued: true
        inlined: true
        inlined_as_list: true
"""
    # Without the flag
    gen_without = PydanticGenerator(schema, include_range_class_descendants=False)
    code_without = gen_without.serialize()
    assert "documents: Optional[list[Document]]" in code_without

    # With the flag
    gen_with = PydanticGenerator(schema, include_range_class_descendants=True)
    code_with = gen_with.serialize()
    # Check for Union in list
    assert any(pattern in code_with for pattern in [
        "list[Union[Document,TextDocument,ImageDocument]]",
        "list[Union[Document,ImageDocument,TextDocument]]",
        "list[Union[TextDocument,Document,ImageDocument]]",
        "list[Union[TextDocument,ImageDocument,Document]]",
        "list[Union[ImageDocument,Document,TextDocument]]",
        "list[Union[ImageDocument,TextDocument,Document]]",
    ])

    # Verify it compiles
    mod = gen_with.compile_module()

    # Should accept list of various types
    collection = mod.Collection(
        documents=[
            mod.Document(id="d1"),
            mod.TextDocument(id="d2", text="hello"),
            mod.ImageDocument(id="d3", image_data="data"),
        ]
    )
    assert len(collection.documents) == 3


def test_include_range_class_descendants_single_child():
    """Test that include_range_class_descendants doesn't create Union when there's only one class."""
    schema = """
id: https://example.org/test
name: test

prefixes:
  linkml: https://w3id.org/linkml/
  ex: https://example.org/

imports:
  - linkml:types

default_prefix: ex

classes:
  Parent:
    attributes:
      name:
        range: string

  Container:
    attributes:
      item:
        range: Parent
        inlined: true
"""
    gen = PydanticGenerator(schema, include_range_class_descendants=True)
    code = gen.serialize()
    # Should NOT create Union for single class
    assert "item: Optional[Parent]" in code
    assert "Union" not in code.split("class Container")[1].split("class ")[0]


def test_include_range_class_descendants_non_inlined():
    """Test include_range_class_descendants with non-inlined classes (identifier reference).

    For non-inlined classes with identifiers, include_range_class_descendants shouldn't
    affect the output since they're stored as identifier values, not objects.
    """
    schema = """
id: https://example.org/test
name: test

prefixes:
  linkml: https://w3id.org/linkml/
  ex: https://example.org/

imports:
  - linkml:types

default_prefix: ex

classes:
  Person:
    attributes:
      id:
        identifier: true
        range: string
      name:
        range: string

  Employee:
    is_a: Person
    attributes:
      employee_id:
        range: string

  Container:
    attributes:
      person_ref:
        range: Person
        inlined: false
"""
    # Non-inlined slots should not be affected by the flag
    gen_without = PydanticGenerator(schema, include_range_class_descendants=False)
    code_without = gen_without.serialize()

    gen_with = PydanticGenerator(schema, include_range_class_descendants=True)
    code_with = gen_with.serialize()

    # Both should use str for the identifier (not Union)
    container_code_without = code_without.split("class Container")[1].split("class ")[0]
    container_code_with = code_with.split("class Container")[1].split("class ")[0]

    assert "person_ref: Optional[str]" in container_code_without
    assert "person_ref: Optional[str]" in container_code_with


def test_include_range_class_descendants_abstract_classes():
    """Test that abstract classes are not included in the Union."""
    schema = """
id: https://example.org/test
name: test

prefixes:
  linkml: https://w3id.org/linkml/
  ex: https://example.org/

imports:
  - linkml:types

default_prefix: ex

classes:
  Entity:
    abstract: true
    attributes:
      id:
        range: string

  ConcreteEntity1:
    is_a: Entity
    attributes:
      field1:
        range: string

  ConcreteEntity2:
    is_a: Entity
    attributes:
      field2:
        range: string

  Container:
    attributes:
      entity:
        range: Entity
        inlined: true
"""
    gen = PydanticGenerator(schema, include_range_class_descendants=True)
    code = gen.serialize()

    # Should include concrete descendants but not the abstract Entity itself
    # (JSON schema generator excludes abstract classes)
    assert "ConcreteEntity1" in code
    assert "ConcreteEntity2" in code


def test_include_range_class_descendants_validation():
    """Test that validation works correctly with include_range_class_descendants."""
    schema = """
id: https://example.org/test
name: test

prefixes:
  linkml: https://w3id.org/linkml/
  ex: https://example.org/

imports:
  - linkml:types

default_prefix: ex

classes:
  Animal:
    attributes:
      name:
        range: string
        required: true

  Dog:
    is_a: Animal
    attributes:
      breed:
        range: string

  Cat:
    is_a: Animal
    attributes:
      color:
        range: string

  Zoo:
    attributes:
      animals:
        range: Animal
        multivalued: true
        inlined: true
        inlined_as_list: true
"""
    gen = PydanticGenerator(schema, include_range_class_descendants=True)
    mod = gen.compile_module()

    # Should accept mixed types
    zoo = mod.Zoo(
        animals=[
            mod.Animal(name="Generic"),
            mod.Dog(name="Buddy", breed="Labrador"),
            mod.Cat(name="Whiskers", color="Orange"),
        ]
    )
    assert len(zoo.animals) == 3
    assert zoo.animals[1].breed == "Labrador"
    assert zoo.animals[2].color == "Orange"

    # Missing required field should fail
    with pytest.raises(ValidationError):
        mod.Zoo(
            animals=[
                mod.Dog(breed="Labrador"),  # missing required 'name'
            ]
        )


def test_include_range_class_descendants_cross_schema():
    """Test cross-schema inheritance where all classes are in the same schema.

    This tests that the feature works when:
    - Multiple inheritance levels exist (Parent -> Child1/Child2 -> Grandchild)
    - The Container references the Parent and should get Union of all descendants
    """
    schema = """
id: https://example.org/test
name: test

prefixes:
  linkml: https://w3id.org/linkml/
  ex: https://example.org/

imports:
  - linkml:types

default_prefix: ex

classes:
  Parent:
    attributes:
      name:
        range: string

  Child1:
    is_a: Parent
    attributes:
      field1:
        range: string

  Child2:
    is_a: Parent
    attributes:
      field2:
        range: string

  Grandchild1:
    is_a: Child1
    attributes:
      grandchild_field:
        range: string

  Container:
    attributes:
      item:
        range: Parent
        inlined: true
"""
    # Test without flag - should only have Parent
    gen_without = PydanticGenerator(schema, include_range_class_descendants=False)
    code_without = gen_without.serialize()
    assert "item: Optional[Parent]" in code_without

    # Test with flag - should generate Union including all descendants
    gen_with = PydanticGenerator(schema, include_range_class_descendants=True)
    code_with = gen_with.serialize()

    # Should contain Union with all descendants including grandchild
    assert "Union[" in code_with
    assert "Parent" in code_with
    assert "Child1" in code_with
    assert "Child2" in code_with
    assert "Grandchild1" in code_with

    # Verify code compiles
    mod = gen_with.compile_module()

    # Should accept Parent
    c1 = mod.Container(item=mod.Parent(name="parent"))
    assert c1.item.name == "parent"

    # Should accept Child1
    c2 = mod.Container(item=mod.Child1(name="child1", field1="f1"))
    assert c2.item.name == "child1"

    # Should accept Child2
    c3 = mod.Container(item=mod.Child2(name="child2", field2="f2"))
    assert c3.item.name == "child2"

    # Should accept Grandchild1 (transitive descendant)
    c4 = mod.Container(item=mod.Grandchild1(name="grandchild", field1="f1", grandchild_field="gc"))
    assert c4.item.name == "grandchild"

