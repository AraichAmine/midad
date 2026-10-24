"""Skeleton extraction and prototype export for Arabic glyph trunks.

The skeletonizer separates a shaped glyph into its *rasm* (trunk) and *i'jam*
(dots), reduces the trunk to a one-pixel medial axis, fits a continuous cubic
Bézier path through it and calibrates the stroke width needed to reconstruct
the original trunk outline.
"""

from __future__ import annotations

import json
import math
from collections import deque
from pathlib import Path
from typing import Any, Iterable, Sequence

import networkx as nx
import numpy as np
from shapely.geometry import LineString, Point, Polygon, mapping, shape
from shapely.ops import unary_union
from skimage.draw import polygon as draw_polygon
from skimage.morphology import medial_axis

try:  # pragma: no cover - import style depends on how the module is loaded
    from .extractor import (
        Contour,
        contour_polygons,
        contours_for_letter_form,
        font_units_per_em,
    )
except ImportError:  # pragma: no cover
    from extractor import (  # type: ignore
        Contour,
        contour_polygons,
        contours_for_letter_form,
        font_units_per_em,
    )

try:  # pragma: no cover
    from .rules import ARABIC_CHARACTER_RULES
except ImportError:  # pragma: no cover
    from rules import ARABIC_CHARACTER_RULES  # type: ignore

try:  # pragma: no cover - import style depends on how the module is loaded
    from . import extractor
except ImportError:  # pragma: no cover
    import extractor  # type: ignore


Point2D = tuple[float, float]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FONT_PATH = REPO_ROOT / "fixtures" / "fonts" / "NotoNaskhArabic-Regular.ttf"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "fixtures" / "skeletons" / "prototype_5.json"

PROTOTYPE_LETTERS: tuple[str, ...] = ("ا", "ب", "ج", "د", "ر")
FORM_ORDER: tuple[str, ...] = ("isolated", "initial", "medial", "final")
LOOP_LETTERS: frozenset[str] = frozenset({"ص", "ض", "ط", "ظ", "ف", "ق", "م", "ه", "و", "ة"})


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _as_polygon(value: Any) -> Polygon:
    if isinstance(value, Polygon):
        polygon = value
    elif isinstance(value, Contour):
        polygon = value.polygon
    elif isinstance(value, dict):
        if "points" in value:
            polygon = Polygon(value["points"])
        elif "geometry" in value:
            polygon = shape(value["geometry"])
        elif "type" in value:
            polygon = shape(value)
        else:
            raise TypeError(f"cannot interpret contour dict: {sorted(value)}")
    elif isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple, np.ndarray)):
        polygon = Polygon(value)
    elif isinstance(value, (list, tuple)) and value and isinstance(value[0], Contour):
        polygon = unary_union([item.polygon for item in value])
    else:
        raise TypeError(f"cannot convert {type(value)!r} to a polygon")

    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    return polygon


def _as_polygons(values: Any) -> list[Polygon]:
    if isinstance(values, Polygon):
        return [values]
    if isinstance(values, Contour):
        return [values.polygon]
    if isinstance(values, dict):
        return [_as_polygon(values)]
    if isinstance(values, (list, tuple)):
        polygons: list[Polygon] = []
        for value in values:
            if isinstance(value, Contour):
                polygons.append(value.polygon)
            elif isinstance(value, Polygon):
                polygons.append(value)
            elif isinstance(value, (list, tuple, np.ndarray)):
                polygons.append(_as_polygon(value))
            else:
                polygons.append(_as_polygon(value))
        return [polygon for polygon in polygons if not polygon.is_empty]
    raise TypeError(f"cannot convert {type(values)!r} to polygons")


def _union(polygons: Sequence[Polygon]) -> Polygon:
    if not polygons:
        raise ValueError("at least one polygon is required")
    geometry = unary_union(polygons)
    if geometry.geom_type == "MultiPolygon":
        # For a single connected trunk the union is normally one polygon.  A
        # MultiPolygon can occur when a glyph is composed of disconnected
        # pieces; use the convex-free union hull only as a last resort.
        merged = unary_union(list(geometry.geoms))
        if merged.geom_type == "Polygon":
            return merged
        return max(geometry.geoms, key=lambda item: item.area)
    return geometry


def _rasterize(
    polygon: Polygon, target_pixels: int = 320, padding: int = 3
) -> tuple[np.ndarray, float, float, float]:
    """Rasterize a polygon (with holes) using an even-odd fill rule."""

    minx, miny, maxx, maxy = polygon.bounds
    width = max(maxx - minx, 1e-6)
    height = max(maxy - miny, 1e-6)
    scale = min(4.0, max(0.5, target_pixels / max(width, height)))
    pixel_width = max(4, int(math.ceil(width * scale)) + 2 * padding)
    pixel_height = max(4, int(math.ceil(height * scale)) + 2 * padding)
    mask = np.zeros((pixel_height, pixel_width), dtype=bool)

    rings: list[Iterable[Point2D]] = [polygon.exterior.coords]
    rings.extend(interior.coords for interior in polygon.interiors)
    for ring in rings:
        xs = np.array([(x - minx) * scale + padding for x, y in ring], dtype=float)
        ys = np.array([(maxy - y) * scale + padding for x, y in ring], dtype=float)
        rows, cols = draw_polygon(ys, xs, shape=mask.shape)
        ring_mask = np.zeros_like(mask)
        ring_mask[rows, cols] = True
        mask ^= ring_mask

    return mask, scale, minx, maxy


def _skeleton_graph(
    skeleton: np.ndarray,
) -> tuple[np.ndarray, list[list[int]]]:
    coordinates = np.argwhere(skeleton)
    index_by_pixel = {tuple(pixel): index for index, pixel in enumerate(coordinates)}
    adjacency: list[list[int]] = [[] for _ in coordinates]
    for (row, col), index in index_by_pixel.items():
        for delta_row in (-1, 0, 1):
            for delta_col in (-1, 0, 1):
                if delta_row == 0 and delta_col == 0:
                    continue
                neighbor = index_by_pixel.get((row + delta_row, col + delta_col))
                if neighbor is not None:
                    adjacency[index].append(neighbor)
    return coordinates, adjacency


def compute_loop_count(
    coordinates: np.ndarray, adjacency: list[list[int]]
) -> int:
    """Topological loop count (cycle rank) of a skeleton graph.

    For an undirected graph the cycle rank is ``E - V + C`` where ``V`` is the
    number of vertices, ``E`` the number of (de-duplicated) edges and ``C`` the
    number of connected components.  A connected skeleton that is a plain tree
    has a loop count of 0; each independent cycle (e.g. a closed calligraphic
    bowl) adds one.

    The value is a *structural* signal: the authoritative calligraphic loop
    count for a letter comes from the orthography rules
    (``expected_loop_count``), because a near-closed calligraphic bowl need not
    correspond to a polygon hole and the 8-connected medial axis can contain
    sub-pixel spurious cycles.
    """

    node_count = len(coordinates)
    if node_count == 0:
        return 0

    edges: set[tuple[int, int]] = set()
    for u in range(node_count):
        for v in adjacency[u]:
            if u < v:
                edges.add((u, v))

    visited = [False] * node_count
    components = 0
    for start in range(node_count):
        if visited[start]:
            continue
        components += 1
        stack = [start]
        visited[start] = True
        while stack:
            node = stack.pop()
            for neighbor in adjacency[node]:
                if not visited[neighbor]:
                    visited[neighbor] = True
                    stack.append(neighbor)

    return len(edges) - node_count + components


def _covering_trail(
    coordinates: np.ndarray, adjacency: list[list[int]], form: str = ""
) -> list[int]:
    """Return a continuous vertex trail that covers every skeleton vertex.

    Glyph trunks are frequently Y- or T-shaped.  A single longest path would
    drop one arm, so the trail walks up each branch and retraces it.  The walk
    starts at the rightmost skeleton pixel and finishes at the leftmost one,
    matching the right-to-left writing direction.
    """

    node_count = len(coordinates)
    if node_count == 0:
        return []

    rows = coordinates[:, 0]
    cols = coordinates[:, 1]
    span_r = float(np.max(rows) - np.min(rows))
    span_c = float(np.max(cols) - np.min(cols))
    if span_r > 1.5 * (span_c + 1.0) and form == "isolated":
        # Isolated vertical stroke (e.g. isolated Alef): top-to-bottom ductus
        start = int(np.argmin(rows))  # smallest row = topmost in font units
        end = int(np.argmax(rows))    # largest row = bottommost in font units
    else:
        # Standard cursive / horizontal stroke: right-to-left ductus (starts at rightmost entry)
        start = max(
            range(node_count), key=lambda index: (coordinates[index][1], -coordinates[index][0])
        )

        end = min(
            range(node_count), key=lambda index: (coordinates[index][1], coordinates[index][0])
        )


    # A BFS tree is enough: all skeleton pixels remain reachable from it.
    parent = [-1] * node_count
    order = [start]
    parent[start] = start
    for node in order:
        for neighbor in adjacency[node]:
            if parent[neighbor] < 0:
                parent[neighbor] = node
                order.append(neighbor)

    children: list[list[int]] = [[] for _ in range(node_count)]
    for node in order[1:]:
        children[parent[node]].append(node)

    next_on_path: dict[int, int] = {}
    node = end
    while node != start:
        next_on_path[parent[node]] = node
        node = parent[node]

    trail: list[int] = [start]

    def ordered_children(node: int) -> list[int]:
        node_children = children[node][:]
        deferred = next_on_path.get(node)
        if deferred is not None and deferred in node_children:
            node_children.remove(deferred)
            node_children.append(deferred)
        return node_children

    # Iterative DFS: avoiding recursion keeps deep, snake-like skeletons safe.
    frames: list[tuple[int, int, list[int]]] = [(start, 0, ordered_children(start))]
    while frames:
        node, child_index, node_children = frames[-1]
        if child_index < len(node_children):
            child = node_children[child_index]
            frames[-1] = (node, child_index + 1, node_children)
            trail.append(child)
            frames.append((child, 0, ordered_children(child)))
        else:
            frames.pop()
            if frames:
                parent = frames[-1][0]
                # Do not backtrack from the final edge on the start->end path.
                if node != next_on_path.get(parent):
                    trail.append(parent)

    return trail


def _resample_trail(
    points: Sequence[Point2D], widths: Sequence[float], num_samples: int
) -> tuple[list[Point2D], list[float]]:
    """Resample a polyline trail by arc length while keeping local widths."""

    if not points:
        return [], []
    if len(points) == 1 or num_samples <= 1:
        return [tuple(points[0])], [float(widths[0])]

    cumulative = [0.0]
    for first, second in zip(points, points[1:]):
        cumulative.append(cumulative[-1] + math.dist(first, second))
    total = cumulative[-1]
    if total == 0.0:
        return [tuple(points[0])], [float(widths[0])]

    result_points: list[Point2D] = []
    result_widths: list[float] = []
    segment = 0
    for index in range(num_samples):
        target = total * index / (num_samples - 1)
        while segment + 1 < len(cumulative) and cumulative[segment + 1] < target:
            segment += 1
        if segment + 1 >= len(cumulative):
            result_points.append(tuple(points[-1]))
            result_widths.append(float(widths[-1]))
            continue
        span = cumulative[segment + 1] - cumulative[segment]
        fraction = 0.0 if span == 0.0 else (target - cumulative[segment]) / span
        x = points[segment][0] + (points[segment + 1][0] - points[segment][0]) * fraction
        y = points[segment][1] + (points[segment + 1][1] - points[segment][1]) * fraction
        width = widths[segment] + (widths[segment + 1] - widths[segment]) * fraction
        result_points.append((x, y))
        result_widths.append(float(width))

    result_points[0] = tuple(points[0])
    result_widths[0] = float(widths[0])
    result_points[-1] = tuple(points[-1])
    result_widths[-1] = float(widths[-1])
    return result_points, result_widths


def _catmull_rom_path(points: Sequence[Point2D]) -> tuple[str, list[dict[str, Any]]]:
    """Convert a polyline into one continuous cubic Bézier path."""

    if not points:
        return "", []
    if len(points) == 1:
        x, y = points[0]
        return f"M {x:.3f} {y:.3f}", []

    padded = [points[0]] + list(points) + [points[-1]]
    segments: list[dict[str, Any]] = []
    commands = [f"M {points[0][0]:.3f} {points[0][1]:.3f}"]
    for index in range(len(points) - 1):
        p0 = padded[index]
        p1 = padded[index + 1]
        p2 = padded[index + 2]
        p3 = padded[index + 3]
        control1 = (
            p1[0] + (p2[0] - p0[0]) / 6.0,
            p1[1] + (p2[1] - p0[1]) / 6.0,
        )
        control2 = (
            p2[0] - (p3[0] - p1[0]) / 6.0,
            p2[1] - (p3[1] - p1[1]) / 6.0,
        )
        commands.append(
            f"C {control1[0]:.3f} {control1[1]:.3f} "
            f"{control2[0]:.3f} {control2[1]:.3f} "
            f"{p2[0]:.3f} {p2[1]:.3f}"
        )
        segments.append(
            {
                "start": (round(p1[0], 3), round(p1[1], 3)),
                "control1": (round(control1[0], 3), round(control1[1], 3)),
                "control2": (round(control2[0], 3), round(control2[1], 3)),
                "end": (round(p2[0], 3), round(p2[1], 3)),
            }
        )
    return " ".join(commands), segments


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def separate_trunk_and_dots(
    contours: Sequence[Any],
    expected_dot_count: int,
    dot_placement: str,
    rule: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Partition contours into trunk (*rasm*) and dot (*i'jam*) contours.

    Dot contours are identified by their small area relative to the largest
    contour.  When ``expected_dot_count`` is non-zero the selected dots are
    also checked against the requested placement (``above``/``below``).

    When ``rule`` carries ``has_inner_mark`` (e.g. Kaf) the contour fully
    contained inside the largest trunk contour is promoted to a dot/inner-mark
    contour instead of being merged into the trunk union.  When ``rule`` carries
    ``has_hamza`` or ``has_madda`` (Alef variants and Lam-Alif ligatures) the
    small separate mark contour is likewise promoted to a dot contour.
    """

    if dot_placement not in {"above", "below", "inside", "none"}:
        raise ValueError(f"invalid dot placement {dot_placement!r}")
    if expected_dot_count < 0:
        raise ValueError("expected_dot_count must be non-negative")

    rule = rule or {}
    has_inner_mark = bool(rule.get("has_inner_mark", False))
    has_hamza = bool(rule.get("has_hamza", False))
    has_madda = bool(rule.get("has_madda", False))

    items: list[tuple[Any, Polygon]] = []
    for contour in contours:
        polygon = _as_polygon(contour)
        if not polygon.is_empty and polygon.area > 0:
            items.append((contour, polygon))
    if not items:
        raise ValueError("no non-empty contours supplied")

    # Sort by area descending so the largest contour is the primary trunk.
    order = sorted(range(len(items)), key=lambda i: items[i][1].area, reverse=True)
    largest_polygon = items[order[0]][1]
    largest_area = largest_polygon.area

    # Identify mark contours (inner mark, hamza, madda) that must be kept out
    # of the trunk union regardless of ``expected_dot_count``.
    mark_indices: set[int] = set()
    for index in order[1:]:
        contour_obj, polygon = items[index]
        centroid = polygon.centroid
        area_ratio = polygon.area / largest_area
        if has_inner_mark and area_ratio < 0.45:
            # Inner miniature mark (e.g. Kaf) drawn inside the trunk bowl; the
            # trunk is a thin stroke outline so the mark need not overlap it.
            mark_indices.add(index)
        elif (has_hamza or has_madda) and area_ratio < 0.4 and not largest_polygon.intersects(polygon):
            # Hamza / Madda mark placed above or below the trunk; a real mark
            # is a small contour that does not touch the trunk outline.
            mark_indices.add(index)

    largest_area = largest_polygon.area
    if expected_dot_count == 0:
        dot_indices: list[int] = []
    else:
        candidate_indices = [
            index
            for index in range(len(items))
            if index not in mark_indices
            and items[index][1].area < 0.45 * largest_area
        ]
        if len(candidate_indices) < expected_dot_count:
            # Some fonts merge multiple dots into one contour or produce very
            # small trunks; fall back to the smallest available contours.
            candidate_indices = sorted(
                (i for i in range(len(items)) if i not in mark_indices),
                key=lambda index: items[index][1].area,
            )
        dot_indices = sorted(
            candidate_indices, key=lambda index: items[index][1].area
        )[:expected_dot_count]

    # Merge mark contours into the dot set (they are delayed marks, not trunk).
    all_dot_indices = sorted(set(dot_indices) | mark_indices)
    trunk_indices = [index for index in range(len(items)) if index not in all_dot_indices]
    if not trunk_indices:
        raise ValueError("no trunk contour left after dot separation")

    # Identify inner hole contours (counters contained within larger outer contours)
    # in TrueType font outlines; we must subtract them via CSG difference.
    sorted_trunk_items = sorted(
        [(index, items[index][0], items[index][1]) for index in trunk_indices],
        key=lambda item: item[2].area,
        reverse=True,
    )
    outer_items = []
    hole_items = []
    for index, contour_obj, poly in sorted_trunk_items:
        is_hole = False
        for _, _, outer_poly in outer_items:
            if outer_poly.contains(poly.centroid) or outer_poly.buffer(1).contains(poly):
                is_hole = True
                break
        if is_hole:
            hole_items.append((index, contour_obj, poly))
        else:
            outer_items.append((index, contour_obj, poly))

    outer_polys = [p for _, _, p in outer_items]
    hole_polys = [p for _, _, p in hole_items]
    if hole_polys:
        trunk_polygon = unary_union(outer_polys).difference(unary_union(hole_polys))
    else:
        trunk_polygon = unary_union(outer_polys)

    trunk_polygons = [trunk_polygon]
    dot_polygons = [items[index][1] for index in all_dot_indices]

    # Annotate dot contours with their role for the exporter / audit harness.
    dot_roles: list[str] = []
    for index in all_dot_indices:
        if index in mark_indices:
            if has_inner_mark and index in mark_indices:
                dot_roles.append("inner_mark")
            elif has_hamza:
                dot_roles.append("hamza")
            elif has_madda:
                dot_roles.append("madda")
            else:
                dot_roles.append("dot")
        else:
            dot_roles.append("dot")

    if dot_polygons and dot_placement in {"above", "below"}:
        trunk_centroid = trunk_polygon.centroid
        for dot in dot_polygons:
            centroid = dot.centroid
            if dot_placement == "below":
                valid = centroid.y < 0 or centroid.y < trunk_centroid.y
            else:
                valid = centroid.y > 0 or centroid.y > trunk_centroid.y
            if not valid:
                raise ValueError(
                    f"dot at {centroid.coords[0]} is not {dot_placement} the trunk"
                )

    return {
        "trunk_contours": [item[1] for item in outer_items],
        "hole_contours": [item[1] for item in hole_items],
        "dot_contours": [items[index][0] for index in all_dot_indices],
        "dot_roles": dot_roles,
        "trunk_polygons": trunk_polygons,
        "dot_polygons": dot_polygons,
        "trunk_polygon": trunk_polygon,
        "expected_dot_count": expected_dot_count,
        "actual_dot_count": len(dot_polygons),
        "dot_placement": dot_placement,
    }



def _calligraphic_loop_trail(
    coordinates: np.ndarray,
    adjacency: list[list[int]],
    minx: float,
    maxy: float,
    scale: float,
    char: str = "",
    form: str = "",
) -> list[int] | None:
    """Traverse a calligraphic loop so the cycle closes completely at the baseline junction."""
    G = nx.Graph()
    for i, pt in enumerate(coordinates):
        x = minx + (pt[1] - 3) / scale
        y = maxy - (pt[0] - 3) / scale
        G.add_node(i, pos=(x, y))
    for u in range(len(coordinates)):
        for v in adjacency[u]:
            if u < v:
                G.add_edge(u, v)

    for c in nx.cycle_basis(G):
        if len(c) <= 5:
            G.remove_edge(c[0], c[1])

    cycles = [c for c in nx.cycle_basis(G) if len(c) > 10]
    if not cycles:
        return None

    start_node = max(G.nodes, key=lambda n: (G.nodes[n]["pos"][0], -abs(G.nodes[n]["pos"][1])))
    end_node = min(G.nodes, key=lambda n: (G.nodes[n]["pos"][0], G.nodes[n]["pos"][1]))

    protected = {start_node, end_node}
    tooth = None
    if char in {"ص", "ض"}:
        xs = [G.nodes[n]["pos"][0] for n in G.nodes]
        min_x, max_x = min(xs), max(xs)
        candidates = [
            n for n in G.nodes
            if min_x + 0.3 * (max_x - min_x) <= G.nodes[n]["pos"][0] <= min_x + 0.7 * (max_x - min_x)
        ]
        if candidates:
            tooth = max(candidates, key=lambda n: G.nodes[n]["pos"][1])
            protected.add(tooth)

    # Prune short dead-end spurs (< 18 pixels)
    changed = True
    while changed:
        changed = False
        leaves = [n for n in G.nodes if G.degree(n) == 1 and n not in protected]
        for leaf in leaves:
            path = [leaf]
            curr = leaf
            while True:
                nbrs = [n for n in G.neighbors(curr) if n not in path]
                if len(nbrs) == 1:
                    nxt = nbrs[0]
                    path.append(nxt)
                    if G.degree(nxt) > 2 or nxt in protected:
                        break
                    curr = nxt
                else:
                    break
            if len(path) < 18 and G.degree(path[-1]) > 2:
                for n in path[:-1]:
                    G.remove_node(n)
                changed = True
                break

    cycles = [c for c in nx.cycle_basis(G) if len(c) > 10]
    if not cycles:
        return None

    def walk_cycle(cycle_nodes, entry_junction, prefer_higher_y=True):
        cycle_set = set(cycle_nodes)
        nbrs = [n for n in G.neighbors(entry_junction) if n in cycle_set]
        if not nbrs:
            return [entry_junction]
        if len(nbrs) == 1:
            nxt = nbrs[0]
        else:
            nxt = max(nbrs, key=lambda n: G.nodes[n]["pos"][1]) if prefer_higher_y else min(nbrs, key=lambda n: G.nodes[n]["pos"][1])
        cycle_walk = [entry_junction, nxt]
        curr = nxt
        prev = entry_junction
        while curr != entry_junction:
            step_nbrs = [n for n in G.neighbors(curr) if n in cycle_set and n != prev]
            if not step_nbrs:
                break
            nxt = step_nbrs[0]
            cycle_walk.append(nxt)
            prev = curr
            curr = nxt
        return cycle_walk

    if len(cycles) >= 2 and char == "ه" and form == "medial":
        # Figure eight: sort top to bottom
        cycles = sorted(cycles, key=lambda c: sum(G.nodes[n]["pos"][1] for n in c) / len(c), reverse=True)
        top_cycle, bot_cycle = cycles[0], cycles[1]
        j_top = min(top_cycle, key=lambda n: nx.shortest_path_length(G, start_node, n))
        path_to_top = nx.shortest_path(G, start_node, j_top)
        top_walk = walk_cycle(top_cycle, j_top, prefer_higher_y=True)
        j_bot = min(bot_cycle, key=lambda n: nx.shortest_path_length(G, j_top, n))
        path_top_to_bot = nx.shortest_path(G, j_top, j_bot)
        bot_walk = walk_cycle(bot_cycle, j_bot, prefer_higher_y=False)
        path_bot_to_end = nx.shortest_path(G, j_bot, end_node)
        return path_to_top + top_walk[1:] + path_top_to_bot[1:] + bot_walk[1:] + path_bot_to_end[1:]

    cycle = max(cycles, key=len)
    cycle_j_in = min(cycle, key=lambda n: nx.shortest_path_length(G, start_node, n))
    path_to_j = nx.shortest_path(G, start_node, cycle_j_in)
    cycle_walk = walk_cycle(cycle, cycle_j_in, prefer_higher_y=True)

    if char in {"ص", "ض"} and tooth is not None:
        path_j_to_end = nx.shortest_path(G, cycle_j_in, tooth)[1:] + nx.shortest_path(G, tooth, end_node)[1:]
    else:
        path_j_to_end = nx.shortest_path(G, cycle_j_in, end_node)[1:]

    return path_to_j + cycle_walk[1:] + path_j_to_end


def _extract_tah_strokes(
    trunk_polygon: Polygon, form: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Extract Tah/Zah multi-stroke ductus: Stroke 1 (base loop) and Stroke 2 (mast)."""
    mask, scale, minx, maxy = _rasterize(trunk_polygon)
    skel, dist = medial_axis(mask, return_distance=True, rng=0)
    coords, adj = _skeleton_graph(skel)

    G = nx.Graph()
    for i, pt in enumerate(coords):
        x = minx + (pt[1] - 3) / scale
        y = maxy - (pt[0] - 3) / scale
        G.add_node(i, pos=(x, y))
    for u in range(len(coords)):
        for v in adj[u]:
            if u < v:
                G.add_edge(u, v)

    for c in nx.cycle_basis(G):
        if len(c) <= 5:
            G.remove_edge(c[0], c[1])

    top_mast = max(G.nodes, key=lambda n: G.nodes[n]["pos"][1])
    cycles = [c for c in nx.cycle_basis(G) if len(c) > 10]
    cycle = max(cycles, key=len)
    cycle_set = set(cycle)

    start_node = max(G.nodes, key=lambda n: (G.nodes[n]["pos"][0], -abs(G.nodes[n]["pos"][1])))
    end_node = min([n for n in G.nodes if G.nodes[n]["pos"][1] < 300], key=lambda n: G.nodes[n]["pos"][0])

    mast_junction = min(cycle, key=lambda n: nx.shortest_path_length(G, top_mast, n))
    mast_indices = nx.shortest_path(G, top_mast, mast_junction)

    cycle_j_in = min(cycle, key=lambda n: nx.shortest_path_length(G, start_node, n))
    path_to_j = nx.shortest_path(G, start_node, cycle_j_in)

    nbrs = [n for n in G.neighbors(cycle_j_in) if n in cycle_set]
    nxt = max(nbrs, key=lambda n: G.nodes[n]["pos"][1]) if nbrs else cycle_j_in
    cycle_walk = [cycle_j_in, nxt]
    curr = nxt
    prev = cycle_j_in
    while curr != cycle_j_in:
        step_nbrs = [n for n in G.neighbors(curr) if n in cycle_set and n != prev]
        if not step_nbrs:
            break
        nxt = step_nbrs[0]
        cycle_walk.append(nxt)
        prev = curr
        curr = nxt

    path_j_to_end = nx.shortest_path(G, cycle_j_in, end_node)
    base_indices = path_to_j + cycle_walk[1:] + path_j_to_end[1:]

    def make_stroke(indices, n_samples=100):
        pts = [G.nodes[n]["pos"] for n in indices]
        w = [max(0.5, float(dist[coords[n][0], coords[n][1]]) / scale) for n in indices]
        s_pts, s_w = _resample_trail(pts, w, n_samples)
        d, segs = _catmull_rom_path(s_pts)
        length = sum(math.dist(a, b) for a, b in zip(s_pts, s_pts[1:]))
        return {
            "points": s_pts,
            "widths": s_w,
            "path_d": d,
            "segments": segs,
            "length": float(length),
            "num_samples": len(s_pts),
            "stroke_width": float(2.0 * float(np.mean(s_w))),
            "bbox": (
                min(p[0] for p in s_pts), min(p[1] for p in s_pts),
                max(p[0] for p in s_pts), max(p[1] for p in s_pts),
            ),
            "ordered": "right_to_left",
        }

    stroke1 = make_stroke(base_indices, 100)
    stroke2 = make_stroke(mast_indices, 60)
    combined = {
        "points": stroke1["points"] + stroke2["points"],
        "widths": stroke1["widths"] + stroke2["widths"],
        "path_d": stroke1["path_d"] + " " + stroke2["path_d"],
        "length": stroke1["length"] + stroke2["length"],
        "entry_point": stroke1["points"][0],
        "exit_point": stroke1["points"][-1],
    }
    return stroke1, stroke2, combined


def extract_centerline(
    trunk_contour: Any,
    num_samples: int = 100,
    char: str = "",
    form: str = "",
    is_loop: bool = False,
) -> dict[str, Any]:
    """Extract an ordered medial-axis skeleton and fit a cubic Bézier path.

    The returned dictionary contains sampled ``points`` (font units), local
    stroke ``widths``, a single continuous ``path_d``, the fitted Bézier
    ``segments``, the path ``length`` and a nominal ``stroke_width``.
    """

    if num_samples < 2:
        raise ValueError("num_samples must be at least 2")
    polygon = _as_polygon(trunk_contour)
    if polygon.is_empty or polygon.area == 0:
        raise ValueError("trunk contour has no area")

    mask, scale, minx, maxy = _rasterize(polygon)
    # Fix the tie-breaking RNG: medial_axis otherwise chooses between
    # equidistant candidate pixels randomly, making the exported JSON unstable.
    skeleton, distance = medial_axis(mask, return_distance=True, rng=0)
    if not skeleton.any():
        raise ValueError("could not extract a medial axis from the trunk")

    coordinates, adjacency = _skeleton_graph(skeleton)
    trail = None
    if (is_loop or (char and (char in LOOP_LETTERS or (char in {"ع", "غ"} and form in {"medial", "final"})))) and not (char == "ه" and form == "isolated"):
        trail = _calligraphic_loop_trail(coordinates, adjacency, minx, maxy, scale, char, form)


    if not trail:
        trail = _covering_trail(coordinates, adjacency, form=form)
    if not trail:

        raise ValueError("empty skeleton trail")


    trail_points: list[Point2D] = [
        (minx + (coordinates[index][1] - 3) / scale,
         maxy - (coordinates[index][0] - 3) / scale)
        for index in trail
    ]
    trail_widths = [
        max(0.5, float(distance[coordinates[index][0], coordinates[index][1]]) / scale)
        for index in trail
    ]

    # Merge consecutive duplicates (branch retracing can visit the same pixel).
    points: list[Point2D] = []
    widths: list[float] = []
    for point, width in zip(trail_points, trail_widths):
        if points and math.dist(points[-1], point) < 1e-9:
            widths[-1] = max(widths[-1], width)
            continue
        points.append(point)
        widths.append(width)

    sampled_points, sampled_widths = _resample_trail(points, widths, num_samples)
    path_d, segments = _catmull_rom_path(sampled_points)
    length = sum(
        math.dist(first, second)
        for first, second in zip(sampled_points, sampled_points[1:])
    )
    bbox = (
        min(point[0] for point in sampled_points),
        min(point[1] for point in sampled_points),
        max(point[0] for point in sampled_points),
        max(point[1] for point in sampled_points),
    )

    return {
        "points": sampled_points,
        "widths": sampled_widths,
        "path_d": path_d,
        "segments": segments,
        "length": float(length),
        "stroke_width": float(2.0 * float(np.mean(sampled_widths))),
        "num_samples": len(sampled_points),
        "bbox": tuple(float(value) for value in bbox),
        "ordered": "right_to_left",
    }


def compute_anchors(trunk_skeleton: Any, form: str) -> dict[str, list[float] | None]:
    """Compute entry/exit connection anchors for a joining form.

    ``initial`` has an exit anchor at the left extremity, ``final`` has an
    entry anchor at the right extremity and ``medial`` has both.  ``isolated``
    has neither.
    """

    if form not in FORM_ORDER:
        raise ValueError(f"unknown form {form!r}")
    if isinstance(trunk_skeleton, dict):
        points = trunk_skeleton.get("points", [])
    elif isinstance(trunk_skeleton, LineString):
        points = list(trunk_skeleton.coords)
    else:
        points = list(trunk_skeleton)
    if not points:
        return {"entry": None, "exit": None}

    rightmost = max(points, key=lambda point: (point[0], -abs(point[1])))
    leftmost = min(points, key=lambda point: (point[0], -abs(point[1])))

    anchors: dict[str, list[float] | None] = {"entry": None, "exit": None}
    if form in {"medial", "final"}:
        anchors["entry"] = [round(float(rightmost[0]), 3), round(float(rightmost[1]), 3)]
    if form in {"medial", "initial"}:
        anchors["exit"] = [round(float(leftmost[0]), 3), round(float(leftmost[1]), 3)]
    return anchors


def _skeleton_geometry(
    skeleton_path: Any,
) -> tuple[list[Point2D], list[float] | None]:
    if isinstance(skeleton_path, dict):
        raw_points = skeleton_path.get("points", [])
        widths = skeleton_path.get("widths")
        points = [(float(x), float(y)) for x, y in raw_points]
        return points, ([float(width) for width in widths] if widths else None)
    if isinstance(skeleton_path, LineString):
        return [(float(x), float(y)) for x, y in skeleton_path.coords], None
    if isinstance(skeleton_path, (list, tuple)):
        points = []
        for point in skeleton_path:
            if isinstance(point, (list, tuple, np.ndarray)) and len(point) >= 2:
                points.append((float(point[0]), float(point[1])))
            else:
                raise TypeError("skeleton points must be (x, y) pairs")
        return points, None
    raise TypeError(f"unsupported skeleton path {type(skeleton_path)!r}")


def compute_dilation_iou(
    trunk_polygon: Any, skeleton_path: Any, stroke_width: float | None = None
) -> float:
    """Intersection-over-union between a buffered skeleton and the trunk.

    When the skeleton carries local ``widths`` (as produced by
    :func:`extract_centerline`), each sample is buffered by its own calibrated
    radius.  Passing an explicit ``stroke_width`` uses a constant width
    instead.  Without either, a constant width is searched to maximize IoU.
    """

    if isinstance(trunk_polygon, dict) and "trunk_polygon" in trunk_polygon:
        trunk_polygon = trunk_polygon["trunk_polygon"]
    if isinstance(trunk_polygon, (list, tuple)) and trunk_polygon and isinstance(
        trunk_polygon[0], (Polygon, Contour)
    ):
        trunk = _union(_as_polygons(trunk_polygon))
    else:
        trunk = _as_polygon(trunk_polygon)
    if trunk.is_empty or trunk.area == 0:
        return 0.0

    points, widths = _skeleton_geometry(skeleton_path)
    if len(points) < 2:
        return 0.0

    def iou_for(rendered: Any) -> float:
        if rendered.is_empty:
            return 0.0
        intersection = rendered.intersection(trunk).area
        union = rendered.union(trunk).area
        return float(intersection / union) if union > 0 else 0.0

    if stroke_width is None and widths is not None:
        circles = [
            Point(point).buffer(radius, quad_segs=12)
            for point, radius in zip(points, widths)
            if radius > 0
        ]
        return iou_for(unary_union(circles))

    line = LineString(points)
    if stroke_width is not None:
        return iou_for(
            line.buffer(
                max(0.0, float(stroke_width)) / 2.0,
                cap_style="round",
                join_style="round",
                quad_segs=16,
            )
        )

    # No local widths: search for the best constant-width reconstruction.
    estimated_width = trunk.area / max(line.length, 1e-9)
    best = 0.0
    for multiplier in np.linspace(0.35, 1.8, 40):
        rendered = line.buffer(
            max(0.1, estimated_width * float(multiplier)) / 2.0,
            cap_style="round",
            join_style="round",
            quad_segs=12,
        )
        best = max(best, iou_for(rendered))
    return best


# ---------------------------------------------------------------------------
# Prototype export
# ---------------------------------------------------------------------------


def _valid_forms(char: str) -> tuple[str, ...]:
    rule = ARABIC_CHARACTER_RULES[char]
    joining = rule["joining_type"]
    if joining == "D":
        return ("isolated", "initial", "medial", "final")
    if joining == "R":
        return ("isolated", "final")
    return ("isolated",)


def _geometry_payload(geometry: Any) -> dict[str, Any]:
    if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        raise TypeError(f"unsupported geometry type {geometry.geom_type!r}")
    return dict(mapping(geometry))


def _build_instance(font_path: Path, char: str, form: str) -> dict[str, Any]:
    rule = ARABIC_CHARACTER_RULES[char]
    contours = contours_for_letter_form(font_path, char, form)
    partition = separate_trunk_and_dots(
        contours, rule["dot_count"], rule["dot_placement"], rule
    )
    trunk_polygon = partition["trunk_polygon"]
    skeleton = extract_centerline(trunk_polygon, num_samples=100)
    iou = compute_dilation_iou(trunk_polygon, skeleton)
    if iou < 0.80:
        raise RuntimeError(
            f"IoU {iou:.3f} below 0.80 for {char!r} / {form} "
            f"(trunk area {trunk_polygon.area:.1f})"
        )

    return {
        "char": char,
        "name": rule["name"],
        "form": form,
        "joining_type": rule["joining_type"],
        "base_unicode": rule["base_unicode"],
        "expected_dot_count": int(rule["dot_count"]),
        "dot_count": int(partition["actual_dot_count"]),
        "dot_placement": rule["dot_placement"],
        "expected_loop_count": int(rule["expected_loop_count"]),
        "glyph_ids": [
            int(glyph["glyph_id"])
            for glyph in _shaped_glyphs(font_path, char, form)
        ],
        "glyph_names": [
            glyph["glyph_name"]
            for glyph in _shaped_glyphs(font_path, char, form)
        ],
        "trunk_contours": [
            contour.to_list() for contour in partition["trunk_contours"]
        ],
        "dot_contours": [
            contour.to_list() for contour in partition["dot_contours"]
        ],
        "trunk_polygon": _geometry_payload(trunk_polygon),
        "skeleton": {
            "path_d": skeleton["path_d"],
            "points": [[round(x, 3), round(y, 3)] for x, y in skeleton["points"]],
            "widths": [round(width, 3) for width in skeleton["widths"]],
            "segments": [
                {key: list(value) for key, value in segment.items()}
                for segment in skeleton["segments"]
            ],
            "length": round(float(skeleton["length"]), 3),
            "stroke_width": round(float(skeleton["stroke_width"]), 3),
            "num_samples": int(skeleton["num_samples"]),
            "bbox": [round(float(value), 3) for value in skeleton["bbox"]],
            "ordered": skeleton["ordered"],
        },
        "anchors": compute_anchors(skeleton, form),
        "iou": round(float(iou), 4),
    }


def _shaped_glyphs(font_path: Path, char: str, form: str) -> list[dict[str, Any]]:
    try:
        from .extractor import shape_letter_form
    except ImportError:  # pragma: no cover
        from extractor import shape_letter_form  # type: ignore

    return shape_letter_form(font_path, char, form)["glyphs"]


def build_prototype_data(font_path: str | Path | None = None) -> dict[str, Any]:
    """Build the in-memory prototype payload for the five letters."""

    font_path = Path(font_path) if font_path is not None else DEFAULT_FONT_PATH
    if not font_path.is_file():
        raise FileNotFoundError(f"font not found: {font_path}")

    glyphs: list[dict[str, Any]] = []
    letters: dict[str, Any] = {}
    for char in PROTOTYPE_LETTERS:
        forms = _valid_forms(char)
        letters[char] = {
            "name": ARABIC_CHARACTER_RULES[char]["name"],
            "forms": list(forms),
        }
        for form in forms:
            glyphs.append(_build_instance(font_path, char, form))

    return {
        "version": 1,
        "description": "DAY-1 prototype: five letters, all valid positional forms",
        "font": str(font_path.relative_to(REPO_ROOT))
        if font_path.is_relative_to(REPO_ROOT)
        else str(font_path),
        "font_family": "Noto Naskh Arabic",
        "font_units_per_em": font_units_per_em(font_path),
        "letters": letters,
        "num_instances": len(glyphs),
        "glyphs": glyphs,
    }


def generate_prototype_5_json(
    output_path: str | Path | None = None,
    font_path: str | Path | None = None,
) -> Path:
    """Generate ``fixtures/skeletons/prototype_5.json`` and return its path."""

    target = Path(output_path) if output_path is not None else DEFAULT_OUTPUT_PATH
    data = build_prototype_data(font_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return target


# ---------------------------------------------------------------------------
# Full-catalog export (MILESTONE 1)
# ---------------------------------------------------------------------------


def _font_rel_path(font_path: Path) -> str:
    if font_path.is_relative_to(REPO_ROOT):
        return str(font_path.relative_to(REPO_ROOT))
    return str(font_path)


def _shaped_records(
    font_path: Path, char: str, form: str
) -> tuple[list[dict[str, Any]], list[Any]]:
    """Shaped glyph records and positioned contours for one letter/ligature form.

    Ligatures (``لا``, ``لأ``, ...) are multi-character keys, so they cannot be
    shaped through :func:`extractor.shape_letter_form` (single character only).
    They are shaped directly with a tatweel lead-in for the joined form.
    """

    if len(char) == 1:
        shaped = extractor.shape_letter_form(font_path, char, form)
        contours = extractor.contours_for_letter_form(font_path, char, form)
        return shaped["glyphs"], contours

    text = char if form == "isolated" else "\u0640" + char
    glyphs = extractor.shape_text(text, font_path)
    contours = extractor.extract_text_contours(font_path, text)
    return glyphs, contours


def _contour_stroke(contour: Any) -> dict[str, Any]:
    """A minimal stroke dict for a single contour (used for delayed/dot strokes)."""

    points = [[round(float(x), 3), round(float(y), 3)] for x, y in contour.points]
    length = 0.0
    for first, second in zip(contour.points, contour.points[1:] + contour.points[:1]):
        length += math.dist(first, second)
    return {
        "d": contour.path_d,
        "points": points,
        "length": round(float(length), 3),
    }


def _build_all_glyphs_entry(font_path: Path, char: str, form: str) -> dict[str, Any]:
    """Build one all_glyphs catalog entry for a letter/ligature presentation form.

    The trunk may be split into one skeleton stroke per separated trunk contour
    (so compound letters such as Tah, Zah and the Lam-Alif ligatures expose
    multiple strokes).  The dilation IoU and anchors are computed on the whole
    trunk union so existing topology gates still apply.
    """

    rule = ARABIC_CHARACTER_RULES[char]
    glyphs, contours = _shaped_records(font_path, char, form)
    partition = separate_trunk_and_dots(
        contours, rule["dot_count"], rule["dot_placement"], rule
    )
    trunk_polygon = partition["trunk_polygon"]
    trunk_contours = partition["trunk_contours"]

    is_loop = int(rule["expected_loop_count"]) >= 1 or (char in {"ع", "غ"} and form in {"medial", "final"})

    if char in {"ط", "ظ"}:
        stroke1, stroke2, combined_skeleton = _extract_tah_strokes(trunk_polygon, form)
        trunk_strokes = [
            {"d": stroke1["path_d"], "points": stroke1["points"], "length": stroke1["length"]},
            {"d": stroke2["path_d"], "points": stroke2["points"], "length": stroke2["length"]},
        ]
        anchors = compute_anchors(stroke1, form)
    elif char in {"لا", "لأ", "لإ", "لآ"}:
        polys = [_as_polygon(c) for c in trunk_contours if _as_polygon(c).area > 0]
        if len(polys) >= 3:
            # Final form has [lam, alef, tatweel]. Merge tatweel into Lam.
            tatweel_poly = max(polys, key=lambda p: max(pt[0] for pt in p.exterior.coords))
            other_polys = [p for p in polys if p != tatweel_poly]
            lam_poly = min(other_polys, key=lambda p: p.distance(tatweel_poly))
            alef_poly = [p for p in other_polys if p != lam_poly][0]
            lam_merged = unary_union([lam_poly, tatweel_poly])
            final_polys = [lam_merged, alef_poly]
        else:
            final_polys = polys

        trunk_strokes = []
        combined_pts = []
        combined_w = []
        for p in final_polys:
            stroke = extract_centerline(p, num_samples=100)
            trunk_strokes.append(
                {
                    "d": stroke["path_d"],
                    "points": stroke["points"],
                    "length": float(stroke["length"]),
                }
            )
            combined_pts.extend(stroke["points"])
            combined_w.extend(stroke["widths"])
        combined_skeleton = {"points": combined_pts, "widths": combined_w}
        anchors = compute_anchors(trunk_strokes[0] if trunk_strokes else combined_skeleton, form)


    else:
        combined_skeleton = extract_centerline(
            trunk_polygon, num_samples=100, char=char, form=form, is_loop=is_loop
        )
        trunk_strokes = [
            {
                "d": combined_skeleton["path_d"],
                "points": combined_skeleton["points"],
                "length": float(combined_skeleton["length"]),
            }
        ]
        anchors = compute_anchors(combined_skeleton, form)

    # Authoritative calligraphic loop count from the orthography rules.
    loop_count = int(rule["expected_loop_count"])
    iou_threshold = 0.70 if loop_count >= 1 else 0.80
    iou = compute_dilation_iou(trunk_polygon, combined_skeleton)
    if iou < iou_threshold:
        raise RuntimeError(
            f"dilation IoU {iou:.3f} below threshold {iou_threshold:.2f} "
            f"for {char!r} / {form} (loop_count={loop_count})"
        )


    trunk_glyph = max(glyphs, key=lambda glyph: glyph["x_advance"])
    dot_roles = partition.get("dot_roles") or ["dot"] * len(partition["dot_contours"])
    delayed_strokes = []
    for contour, role in zip(partition["dot_contours"], dot_roles):
        stroke = _contour_stroke(contour)
        stroke["role"] = role
        delayed_strokes.append(stroke)

    return {
        "char": char,
        "name": rule["name"],
        "form": form,
        "glyph_id": int(trunk_glyph["glyph_id"]),
        "glyph_name": trunk_glyph["glyph_name"],
        "advance_x": float(trunk_glyph["x_advance"]),
        "entry_anchor": anchors["entry"],
        "exit_anchor": anchors["exit"],
        "loop_count": loop_count,
        "expected_loop_count": loop_count,
        "dilation_iou": round(float(iou), 4),
        "joining_type": rule["joining_type"],
        "base_unicode": rule["base_unicode"],
        "dot_count": int(rule["dot_count"]),
        "dot_placement": rule["dot_placement"],
        "has_inner_mark": bool(rule.get("has_inner_mark", False)),
        "has_hamza": bool(rule.get("has_hamza", False)),
        "has_madda": bool(rule.get("has_madda", False)),
        "actual_dot_count": int(partition["actual_dot_count"]),
        "num_trunk_strokes": len(trunk_strokes),
        "trunk_strokes": trunk_strokes,
        "delayed_strokes": delayed_strokes,
    }


def build_all_glyphs_data(font_path: str | Path | None = None) -> dict[str, Any]:
    """Build the full all_glyphs catalog across every character rule and form."""

    font_path = Path(font_path) if font_path is not None else DEFAULT_FONT_PATH
    if not font_path.is_file():
        raise FileNotFoundError(f"font not found: {font_path}")

    glyphs: dict[str, Any] = {}
    for char in ARABIC_CHARACTER_RULES:
        for form in _valid_forms(char):
            key = f"{char}_{form}"
            glyphs[key] = _build_all_glyphs_entry(font_path, char, form)

    return {
        "font": _font_rel_path(font_path),
        "font_family": "Noto Naskh Arabic",
        "font_units_per_em": font_units_per_em(font_path),
        "total_glyphs": len(glyphs),
        "glyphs": glyphs,
    }


DEFAULT_ALL_GLYPHS_PATH = REPO_ROOT / "fixtures" / "skeletons" / "all_glyphs.json"


def generate_all_glyphs_json(
    output_path: str | Path | None = None,
    font_path: str | Path | None = None,
) -> Path:
    """Generate ``fixtures/skeletons/all_glyphs.json`` and return its path."""

    target = Path(output_path) if output_path is not None else DEFAULT_ALL_GLYPHS_PATH
    data = build_all_glyphs_data(font_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return target


if __name__ == "__main__":
    written = generate_prototype_5_json()
    print(f"Wrote prototype with 14 glyph instances to {written}")
