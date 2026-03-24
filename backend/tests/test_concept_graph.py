"""Tests for concept graph persistence: nodes, edges, relationships, and traversal depth.

Validates that persist_concept_graph creates ConceptGraphNode and
ConceptGraphEdge records in the tenant DB, stores relationship labels,
traversal depth, and handles unmapped nodes correctly.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folio_concepts import ConceptGraphEdge, ConceptGraphNode


# ── Persistence Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_persist_graph_creates_nodes(async_session: AsyncSession):
    """persist_concept_graph creates ConceptGraphNode records in DB."""
    from app.services.folio.adjacency import persist_concept_graph

    graph = {
        "nodes": [
            {"iri": "https://folio.openlegalstandard.org/n1", "label": "Node 1", "branch": "Objectives", "is_unmapped": False},
            {"iri": "https://folio.openlegalstandard.org/n2", "label": "Node 2", "branch": "Area of Law", "is_unmapped": False},
            {"iri": "https://folio.openlegalstandard.org/n3", "label": "Node 3", "branch": None, "is_unmapped": False},
        ],
        "edges": [],
    }

    nodes, edges = await persist_concept_graph(async_session, intake_id=1, graph=graph)
    assert len(nodes) == 3

    # Query DB to verify
    result = await async_session.execute(
        select(ConceptGraphNode).where(ConceptGraphNode.intake_id == 1)
    )
    db_nodes = result.scalars().all()
    assert len(db_nodes) == 3
    iris = {n.iri for n in db_nodes}
    assert "https://folio.openlegalstandard.org/n1" in iris
    assert "https://folio.openlegalstandard.org/n2" in iris
    assert "https://folio.openlegalstandard.org/n3" in iris


@pytest.mark.asyncio
async def test_persist_graph_creates_edges(async_session: AsyncSession):
    """persist_concept_graph creates ConceptGraphEdge records in DB."""
    from app.services.folio.adjacency import persist_concept_graph

    graph = {
        "nodes": [
            {"iri": "https://folio.openlegalstandard.org/src", "label": "Source"},
            {"iri": "https://folio.openlegalstandard.org/tgt", "label": "Target"},
        ],
        "edges": [
            {
                "source_iri": "https://folio.openlegalstandard.org/src",
                "target_iri": "https://folio.openlegalstandard.org/tgt",
                "relationship": "rdfs:subClassOf",
                "traversal_depth": 1,
            },
            {
                "source_iri": "https://folio.openlegalstandard.org/tgt",
                "target_iri": "https://folio.openlegalstandard.org/src",
                "relationship": "relates_to",
                "traversal_depth": 2,
            },
        ],
    }

    nodes, edges = await persist_concept_graph(async_session, intake_id=2, graph=graph)
    assert len(edges) == 2

    result = await async_session.execute(
        select(ConceptGraphEdge).where(ConceptGraphEdge.intake_id == 2)
    )
    db_edges = result.scalars().all()
    assert len(db_edges) == 2


@pytest.mark.asyncio
async def test_persist_graph_stores_relationship_labels(async_session: AsyncSession):
    """Edge records store the actual property label string as relationship."""
    from app.services.folio.adjacency import persist_concept_graph

    graph = {
        "nodes": [
            {"iri": "https://folio.openlegalstandard.org/a", "label": "A"},
            {"iri": "https://folio.openlegalstandard.org/b", "label": "B"},
        ],
        "edges": [
            {
                "source_iri": "https://folio.openlegalstandard.org/a",
                "target_iri": "https://folio.openlegalstandard.org/b",
                "relationship": "has_jurisdiction_over",
                "traversal_depth": 1,
            },
        ],
    }

    await persist_concept_graph(async_session, intake_id=3, graph=graph)

    result = await async_session.execute(
        select(ConceptGraphEdge).where(ConceptGraphEdge.intake_id == 3)
    )
    edge = result.scalar_one()
    assert edge.relationship == "has_jurisdiction_over"


@pytest.mark.asyncio
async def test_persist_graph_sets_traversal_depth(async_session: AsyncSession):
    """Edge records store the traversal_depth from the input graph."""
    from app.services.folio.adjacency import persist_concept_graph

    graph = {
        "nodes": [
            {"iri": "https://folio.openlegalstandard.org/x", "label": "X"},
            {"iri": "https://folio.openlegalstandard.org/y", "label": "Y"},
        ],
        "edges": [
            {
                "source_iri": "https://folio.openlegalstandard.org/x",
                "target_iri": "https://folio.openlegalstandard.org/y",
                "relationship": "rdfs:subClassOf",
                "traversal_depth": 3,
            },
        ],
    }

    await persist_concept_graph(async_session, intake_id=4, graph=graph)

    result = await async_session.execute(
        select(ConceptGraphEdge).where(ConceptGraphEdge.intake_id == 4)
    )
    edge = result.scalar_one()
    assert edge.traversal_depth == 3


@pytest.mark.asyncio
async def test_persist_graph_handles_unmapped_node(async_session: AsyncSession):
    """Unmapped nodes are stored with is_unmapped=True."""
    from app.services.folio.adjacency import persist_concept_graph

    graph = {
        "nodes": [
            {
                "iri": "https://folio.openlegalstandard.org/local001",
                "label": "Novel Unmapped Concept",
                "branch": "Objectives",
                "is_unmapped": True,
            },
            {
                "iri": "https://folio.openlegalstandard.org/mapped001",
                "label": "Known Concept",
                "branch": "Area of Law",
                "is_unmapped": False,
            },
        ],
        "edges": [],
    }

    await persist_concept_graph(async_session, intake_id=5, graph=graph)

    result = await async_session.execute(
        select(ConceptGraphNode).where(
            ConceptGraphNode.intake_id == 5,
            ConceptGraphNode.is_unmapped == True,  # noqa: E712
        )
    )
    unmapped = result.scalar_one()
    assert unmapped.label == "Novel Unmapped Concept"
    assert unmapped.is_unmapped is True

    result2 = await async_session.execute(
        select(ConceptGraphNode).where(
            ConceptGraphNode.intake_id == 5,
            ConceptGraphNode.is_unmapped == False,  # noqa: E712
        )
    )
    mapped = result2.scalar_one()
    assert mapped.label == "Known Concept"
    assert mapped.is_unmapped is False
