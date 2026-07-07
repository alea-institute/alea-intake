"""Graph traversal and adjacency discovery via hierarchy and object properties.

Discovers adjacent concepts by traversing both the class hierarchy
(subClassOf/parentClassOf) and OWL object properties (find_connections).
Returns a graph structure with nodes and edges (not a flat list).

For unmapped concepts, adjacency uses nearest mapped FOLIO concepts as
traversal anchors, then merges results.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from folio import FOLIO
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class AdjacencyConfig:
    """Configuration for adjacency discovery traversal.

    Attributes:
        max_depth: Maximum traversal depth for hierarchy walks.
            Defaults to 2, matching folio-python DEFAULT_SEARCH_MAX_DEPTH.
        include_hierarchy: Whether to traverse subClassOf/parentClassOf.
        include_properties: Whether to traverse OWL object properties.
        max_nodes: Safety cap to prevent graph explosion on broad ontology areas.
    """

    max_depth: int = 2
    include_hierarchy: bool = True
    include_properties: bool = True
    max_nodes: int = 200


def discover_adjacent_concepts(
    folio: FOLIO,
    concept_iri: str,
    config: AdjacencyConfig | None = None,
) -> dict:
    """Discover adjacent concepts via class hierarchy and OWL object properties.

    Traverses children (subClassOf), parents (parentClassOf), and object
    properties (find_connections) to build a local concept graph around
    the given IRI.

    Args:
        folio: The FOLIO instance for ontology traversal.
        concept_iri: The starting IRI to discover adjacencies for.
        config: Optional traversal configuration. Uses defaults if None.

    Returns:
        Graph structure dict with keys:
        - "nodes": list of dicts {iri, label, branch, is_unmapped, depth}
        - "edges": list of dicts {source_iri, target_iri, relationship, traversal_depth}
    """
    config = config or AdjacencyConfig()
    nodes: dict[str, dict] = {}  # IRI -> node dict (dedup by IRI)
    edges: list[dict] = []

    # Add the source node
    from app.services.folio.folio_service import get_owl_class

    source_cls = get_owl_class(folio, concept_iri)
    if source_cls:
        nodes[concept_iri] = {
            "iri": concept_iri,
            "label": source_cls.label,
            "branch": None,  # Branch detection done by caller
            "is_unmapped": False,
            "depth": 0,
        }

    if config.include_hierarchy:
        # Children traversal (subClassOf)
        try:
            children = folio.get_children(concept_iri, max_depth=config.max_depth)
            for child in children:
                if len(nodes) >= config.max_nodes:
                    break
                if child.iri not in nodes:
                    nodes[child.iri] = {
                        "iri": child.iri,
                        "label": child.label,
                        "branch": None,
                        "is_unmapped": False,
                        "depth": 1,
                    }
                edges.append({
                    "source_iri": concept_iri,
                    "target_iri": child.iri,
                    "relationship": "rdfs:subClassOf",
                    "traversal_depth": 1,
                })
        except (KeyError, ValueError):
            pass  # IRI not found in ontology

        # Parents traversal (parentClassOf)
        try:
            parents = folio.get_parents(concept_iri, max_depth=config.max_depth)
            for parent in parents:
                if len(nodes) >= config.max_nodes:
                    break
                if parent.iri not in nodes:
                    nodes[parent.iri] = {
                        "iri": parent.iri,
                        "label": parent.label,
                        "branch": None,
                        "is_unmapped": False,
                        "depth": 1,
                    }
                edges.append({
                    "source_iri": parent.iri,
                    "target_iri": concept_iri,
                    "relationship": "rdfs:subClassOf",
                    "traversal_depth": 1,
                })
        except (KeyError, ValueError):
            pass

    if config.include_properties:
        # Object property traversal via find_connections
        try:
            connections = folio.find_connections(concept_iri)
            for subject, prop, obj in connections:
                if len(nodes) >= config.max_nodes:
                    break
                # Add object node
                if obj.iri not in nodes:
                    nodes[obj.iri] = {
                        "iri": obj.iri,
                        "label": obj.label,
                        "branch": None,
                        "is_unmapped": False,
                        "depth": 1,
                    }
                # Add subject node if different from source
                if subject.iri not in nodes:
                    nodes[subject.iri] = {
                        "iri": subject.iri,
                        "label": subject.label,
                        "branch": None,
                        "is_unmapped": False,
                        "depth": 1,
                    }
                edges.append({
                    "source_iri": subject.iri,
                    "target_iri": obj.iri,
                    "relationship": prop.label,
                    "traversal_depth": 1,
                })
        except (KeyError, ValueError):
            pass

    return {"nodes": list(nodes.values()), "edges": edges}


def discover_adjacent_for_unmapped(
    folio: FOLIO,
    unmapped: "UnmappedConceptData",
    config: AdjacencyConfig | None = None,
) -> dict:
    """Discover adjacencies for an unmapped concept using nearest mapped concepts as anchors.

    Since unmapped concepts don't exist in the FOLIO ontology, we can't
    traverse their hierarchy directly. Instead, we use the nearest mapped
    concepts (from the matching stage) as traversal entry points, then merge
    the results and add the unmapped concept as a node with edges to its anchors.

    Args:
        folio: The FOLIO instance for ontology traversal.
        unmapped: The UnmappedConceptData with nearest_concepts as anchors.
        config: Optional traversal configuration.

    Returns:
        Graph structure dict with the unmapped concept node included.
    """
    # Import here to avoid circular dependency
    from app.services.folio.unmapped import UnmappedConceptData

    config = config or AdjacencyConfig()
    all_nodes: dict[str, dict] = {}
    all_edges: list[dict] = []

    # Use each nearest concept as a traversal anchor
    for nearest in unmapped.nearest_concepts:
        anchor_iri = nearest["iri"]
        result = discover_adjacent_concepts(folio, anchor_iri, config)
        for node in result["nodes"]:
            if node["iri"] not in all_nodes:
                all_nodes[node["iri"]] = node
        all_edges.extend(result["edges"])

    # Add the unmapped concept as a node
    all_nodes[unmapped.local_iri] = {
        "iri": unmapped.local_iri,
        "label": unmapped.original_text,
        "branch": unmapped.suggested_branch,
        "is_unmapped": True,
        "depth": 0,
    }

    # Add edges from unmapped to its nearest concepts
    for nearest in unmapped.nearest_concepts:
        all_edges.append({
            "source_iri": unmapped.local_iri,
            "target_iri": nearest["iri"],
            "relationship": "nearest_mapped_concept",
            "traversal_depth": 0,
        })

    return {"nodes": list(all_nodes.values()), "edges": all_edges}


async def persist_concept_graph(
    session: AsyncSession,
    intake_id: int,
    graph: dict,
) -> tuple[list, list]:
    """Persist concept graph nodes and edges to tenant DB.

    Creates ConceptGraphNode and ConceptGraphEdge records from the graph
    structure returned by discover_adjacent_concepts or discover_adjacent_for_unmapped.

    Args:
        session: Async SQLAlchemy session (tenant-scoped).
        intake_id: The intake this graph belongs to.
        graph: Dict with "nodes" and "edges" lists.

    Returns:
        Tuple of (node_records, edge_records) lists.
    """
    from app.models.folio_concepts import ConceptGraphEdge, ConceptGraphNode

    node_records = []
    for node in graph["nodes"]:
        record = ConceptGraphNode(
            intake_id=intake_id,
            iri=node["iri"],
            label=node["label"],
            branch=node.get("branch"),
            is_unmapped=node.get("is_unmapped", False),
            confidence=node.get("confidence"),
            metadata_json=node.get("metadata"),
        )
        session.add(record)
        node_records.append(record)

    edge_records = []
    for edge in graph["edges"]:
        record = ConceptGraphEdge(
            intake_id=intake_id,
            source_iri=edge["source_iri"],
            target_iri=edge["target_iri"],
            relationship=edge["relationship"],
            traversal_depth=edge.get("traversal_depth", 0),
        )
        session.add(record)
        edge_records.append(record)

    await session.flush()
    return node_records, edge_records
