"""Tests for adjacency discovery: hierarchy traversal, property traversal, and graph structure.

Validates that discover_adjacent_concepts traverses both class hierarchy
(subClassOf/parentClassOf) and OWL object properties (find_connections),
returns graph structure with nodes and edges, deduplicates, and respects limits.
"""

from unittest.mock import MagicMock

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_owl_class(iri: str, label: str):
    """Create a mock OWLClass."""
    cls = MagicMock()
    cls.iri = iri
    cls.label = label
    return cls


def _make_owl_property(iri: str, label: str):
    """Create a mock OWLObjectProperty."""
    prop = MagicMock()
    prop.iri = iri
    prop.label = label
    return prop


# ── discover_adjacent_concepts Tests ─────────────────────────────────────────


def test_discover_children(mock_folio):
    """Traverses children via get_children, creates nodes and subClassOf edges."""
    from app.services.folio.adjacency import AdjacencyConfig, discover_adjacent_concepts

    source_iri = "https://folio.openlegalstandard.org/objective001"
    config = AdjacencyConfig(include_properties=False)

    result = discover_adjacent_concepts(mock_folio, source_iri, config)

    assert "nodes" in result
    assert "edges" in result
    # Source + 2 children + 1 parent = 4 nodes
    # (parents are also traversed since include_hierarchy=True)
    node_iris = {n["iri"] for n in result["nodes"]}
    assert source_iri in node_iris
    assert "https://folio.openlegalstandard.org/child001" in node_iris
    assert "https://folio.openlegalstandard.org/child002" in node_iris

    # Check child edges have subClassOf relationship
    child_edges = [e for e in result["edges"] if e["target_iri"].startswith("https://folio.openlegalstandard.org/child")]
    assert len(child_edges) == 2
    for edge in child_edges:
        assert edge["relationship"] == "rdfs:subClassOf"


def test_discover_parents(mock_folio):
    """Traverses parents via get_parents, creates nodes and subClassOf edges."""
    from app.services.folio.adjacency import AdjacencyConfig, discover_adjacent_concepts

    source_iri = "https://folio.openlegalstandard.org/objective001"
    config = AdjacencyConfig(include_properties=False)

    result = discover_adjacent_concepts(mock_folio, source_iri, config)

    node_iris = {n["iri"] for n in result["nodes"]}
    assert "https://folio.openlegalstandard.org/parent001" in node_iris

    # Parent edges: source_iri is target, parent is source
    parent_edges = [e for e in result["edges"] if e["source_iri"] == "https://folio.openlegalstandard.org/parent001"]
    assert len(parent_edges) == 1
    assert parent_edges[0]["relationship"] == "rdfs:subClassOf"
    assert parent_edges[0]["target_iri"] == source_iri


def test_discover_properties(mock_folio):
    """Traverses object properties via find_connections with property labels."""
    from app.services.folio.adjacency import AdjacencyConfig, discover_adjacent_concepts

    source_iri = "https://folio.openlegalstandard.org/objective001"
    config = AdjacencyConfig(include_hierarchy=False)

    result = discover_adjacent_concepts(mock_folio, source_iri, config)

    # find_connections returns [(objective001, relates_to, areaoflaw001)]
    prop_edges = [e for e in result["edges"] if e["relationship"] == "relates_to"]
    assert len(prop_edges) == 1
    assert prop_edges[0]["source_iri"] == "https://folio.openlegalstandard.org/objective001"
    assert prop_edges[0]["target_iri"] == "https://folio.openlegalstandard.org/areaoflaw001"


def test_max_depth_respected(mock_folio):
    """Config max_depth is passed to get_children and get_parents."""
    from app.services.folio.adjacency import AdjacencyConfig, discover_adjacent_concepts

    source_iri = "https://folio.openlegalstandard.org/objective001"
    config = AdjacencyConfig(max_depth=1, include_properties=False)

    discover_adjacent_concepts(mock_folio, source_iri, config)

    mock_folio.get_children.assert_called_with(source_iri, max_depth=1)
    mock_folio.get_parents.assert_called_with(source_iri, max_depth=1)


def test_deduplication(mock_folio):
    """Overlapping nodes from hierarchy and properties are deduplicated by IRI."""
    from app.services.folio.adjacency import discover_adjacent_concepts

    # The mock_folio has objective001 as source and also in find_connections
    source_iri = "https://folio.openlegalstandard.org/objective001"

    result = discover_adjacent_concepts(mock_folio, source_iri)

    # Check no duplicate IRIs in nodes
    iris = [n["iri"] for n in result["nodes"]]
    assert len(iris) == len(set(iris)), f"Duplicate IRIs found: {iris}"


def test_max_nodes_cap():
    """Config max_nodes caps the number of nodes returned."""
    from app.services.folio.adjacency import AdjacencyConfig, discover_adjacent_concepts

    folio = MagicMock()
    source_iri = "https://folio.openlegalstandard.org/source"
    source_cls = _make_owl_class(source_iri, "Source")
    folio.classes = {source_iri: source_cls}

    # Return many children
    children = [_make_owl_class(f"https://folio.openlegalstandard.org/child{i:03d}", f"Child {i}") for i in range(50)]
    folio.get_children = MagicMock(return_value=children)
    folio.get_parents = MagicMock(return_value=[])
    folio.find_connections = MagicMock(return_value=[])

    config = AdjacencyConfig(max_nodes=5)
    result = discover_adjacent_concepts(folio, source_iri, config)

    assert len(result["nodes"]) <= 5


def test_returns_graph_structure(mock_folio):
    """Result has 'nodes' (list) and 'edges' (list) keys -- not a flat list."""
    from app.services.folio.adjacency import discover_adjacent_concepts

    source_iri = "https://folio.openlegalstandard.org/objective001"
    result = discover_adjacent_concepts(mock_folio, source_iri)

    assert isinstance(result, dict)
    assert "nodes" in result
    assert "edges" in result
    assert isinstance(result["nodes"], list)
    assert isinstance(result["edges"], list)


# ── discover_adjacent_for_unmapped Tests ─────────────────────────────────────


def test_discover_for_unmapped(mock_folio):
    """Unmapped adjacency uses nearest concepts as traversal anchors."""
    from app.services.folio.adjacency import discover_adjacent_for_unmapped
    from app.services.folio.unmapped import UnmappedConceptData

    unmapped = UnmappedConceptData(
        local_iri="https://folio.openlegalstandard.org/localUnmapped001",
        original_text="novel legal concept",
        suggested_branch="Objectives",
        unmapped_confidence=0.8,
        nearest_concepts=[
            {"iri": "https://folio.openlegalstandard.org/objective001", "label": "Wrongful Termination Claim", "confidence": 0.3},
            {"iri": "https://folio.openlegalstandard.org/areaoflaw001", "label": "Employment Law", "confidence": 0.2},
        ],
    )

    result = discover_adjacent_for_unmapped(mock_folio, unmapped)

    # The unmapped node itself should be in the graph
    node_iris = {n["iri"] for n in result["nodes"]}
    assert unmapped.local_iri in node_iris

    # The unmapped node should be flagged
    unmapped_node = next(n for n in result["nodes"] if n["iri"] == unmapped.local_iri)
    assert unmapped_node["is_unmapped"] is True

    # Edges from unmapped to nearest concepts
    nearest_edges = [e for e in result["edges"] if e["source_iri"] == unmapped.local_iri]
    assert len(nearest_edges) == 2
    for edge in nearest_edges:
        assert edge["relationship"] == "nearest_mapped_concept"

    # Anchor traversal results should be merged
    assert "https://folio.openlegalstandard.org/objective001" in node_iris
    assert "https://folio.openlegalstandard.org/areaoflaw001" in node_iris
