"""Bounded, offline PNG views of fixed analysis data (no analysis or storage).

Public API: ``visual_data_hash(data)``, ``validate_visual_spec(spec, *,
expected_run_id, expected_run_hash, expected_input_hash, expected_data_hash)`` and
``render_visual_png`` with the same arguments. Hashes are lowercase SHA-256;
the data hash uses sorted, compact, UTF-8 JSON (allow_nan=False). Expected
provenance must come from the caller's trusted saved run, not from the spec.
Validation binds identifiers/hashes, not the scientific truth of the data.

Version 1 requires exactly the top-level fields in _FIELDS. Denominator is
{label, value}, missingness is {count, reason}; their numeric values may be
None (unknown). Every slot's data shape is specified in _validate_data below.
None cells stay unknown; no imputation, binning, correlation or inference is
performed. Evidence IDs are opaque local identifiers, never URLs or paths.
PNG Description contains the complete validated spec, including alt text.

The existing slide renderer is PPTX-specific; this follows its bounded
preflight approach while using the already-locked Matplotlib Agg backend.
No user-selected font/path/style/backend or file output is accepted. Byte
reproducibility is within the same Matplotlib/font/Pillow runtime; provenance
records these versions. Callers own persistence and application integration.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
import threading
import warnings

SCHEMA_VERSION = "analysis-visual-1"
RENDERER_VERSION = "analysis-png-2"
SLOTS = ("thematic", "participation", "distribution", "correlation",
         "crosstab", "parallel", "dependency", "coverage")
_FIELDS = {"schema_version", "renderer_version", "slot", "run_id", "run_hash",
           "input_hash", "data_hash", "title", "unit", "denominator",
           "missingness", "evidence_ids", "alt_text", "data"}
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,47}\Z")
_UNSAFE = re.compile(r"[<>\\/`{};]|(?:https?|file|data|javascript|ftp):|www\.", re.I)
_LOCK = threading.RLock()
MAX_BYTES = 65536


class VisualSpecError(ValueError):
    """A spec is unsafe, unsupported, inconsistent or too large to render."""


def _require(condition, message):
    if not condition:
        raise VisualSpecError(message)


def _object(value, fields):
    _require(type(value) is dict and set(value) == set(fields), "unexpected fields")


def _text(value, maximum=120):
    _require(type(value) is str and 0 < len(value) <= maximum
             and value.strip() == value and not _UNSAFE.search(value)
             and all(c.isprintable() for c in value), "unsafe or oversized text")


def _identifier(value):
    _text(value, 48)
    _require(_ID.fullmatch(value) is not None, "invalid identifier")


def _list(value, maximum=12, minimum=1):
    _require(type(value) is list and minimum <= len(value) <= maximum, "list size")


def _number(value, low=0, high=1e9, nullable=True):
    if value is None and nullable:
        return
    _require(type(value) in (int, float), "number required")
    _require(low <= value <= high and math.isfinite(value), "number bounds")


def _count(value):
    _number(value)
    _require(value is None or type(value) is int, "integer count required")


def _labels(value, maximum=12):
    _list(value, maximum)
    for item in value:
        _text(item, 32)
    _require(len(set(value)) == len(value), "duplicate labels")


def _ids(value, maximum=128, minimum=0):
    _list(value, maximum, minimum)
    for item in value:
        _identifier(item)
    _require(len(value) == len(set(value)), "duplicate evidence IDs")


def _bounded_json(value):
    # Check depth/types before serialization: no custom objects, cycles, or
    # attacker-controlled repr/iterators. Size bounds apply to UTF-8 bytes too.
    budget = [2000]

    def walk(item, depth):
        budget[0] -= 1
        _require(budget[0] >= 0 and depth <= 8, "structure limit")
        if type(item) is dict:
            _require(len(item) <= 32, "object size")
            for key, child in item.items():
                _text(key, 48)
                walk(child, depth + 1)
        elif type(item) is list:
            _list(item, 128, 0)
            for child in item:
                walk(child, depth + 1)
        elif type(item) is str:
            _text(item, 240)
        elif item is not None:
            _number(item, -1e9, 1e9, nullable=False)
    walk(value, 0)
    result = json.dumps(value, sort_keys=True, separators=(",", ":"),
                        ensure_ascii=False, allow_nan=False).encode("utf-8")
    _require(len(result) <= MAX_BYTES, "byte limit")
    return result


def visual_data_hash(data):
    """Hash bounded plain JSON data; slot semantics are checked separately."""
    return hashlib.sha256(_bounded_json(data)).hexdigest()


def _matrix(data, row_labels, column_labels, low=0, high=1e9):
    _list(data, len(row_labels))
    _require(len(data) == len(row_labels), "matrix row count")
    for row in data:
        _list(row, len(column_labels))
        _require(len(row) == len(column_labels), "matrix column count")
        for cell in row:
            _number(cell, low, high)


def _validate_data(slot, data, evidence_ids):
    if slot == "thematic":
        _object(data, {"rows"})
        _list(data["rows"], 8)
        themes = []
        for row in data["rows"]:
            _object(row, {"theme", "support_ids", "counterevidence_ids"})
            _text(row["theme"], 32)
            themes.append(row["theme"])
            for key in ("support_ids", "counterevidence_ids"):
                _ids(row[key], 16)
                _require(set(row[key]) <= set(evidence_ids), "unbound evidence")
            _require(not set(row["support_ids"]) & set(row["counterevidence_ids"]),
                     "conflicting evidence roles")
        _require(len(themes) == len(set(themes)), "duplicate themes")
    elif slot == "participation":
        _object(data, {"labels", "values", "timeline"})
        _labels(data["labels"], 8)
        _list(data["values"], 8)
        _require(len(data["values"]) == len(data["labels"]), "bar length")
        for value in data["values"]:
            _number(value)
        _list(data["timeline"], 32)
        previous = -1
        for row in data["timeline"]:
            _object(row, {"time_seconds", "value"})
            _number(row["time_seconds"], nullable=False)
            _number(row["value"])
            _require(row["time_seconds"] > previous, "timeline order")
            previous = row["time_seconds"]
    elif slot == "distribution":
        _object(data, {"bin_unit", "bins"})
        _text(data["bin_unit"], 32)
        _list(data["bins"], 12)
        previous = -1e9
        for row in data["bins"]:
            _object(row, {"lower", "upper", "count"})
            _number(row["lower"], -1e9, nullable=False)
            _number(row["upper"], -1e9, nullable=False)
            _count(row["count"])
            _require(previous <= row["lower"] < row["upper"], "bin order or overlap")
            previous = row["upper"]
    elif slot in ("correlation", "crosstab"):
        fields = {"labels", "values"} if slot == "correlation" else {
            "row_labels", "column_labels", "values"}
        _object(data, fields)
        rows = data["labels"] if slot == "correlation" else data["row_labels"]
        cols = data["labels"] if slot == "correlation" else data["column_labels"]
        _labels(rows, 6)
        _labels(cols, 6)
        _matrix(data["values"], rows, cols, -1 if slot == "correlation" else 0,
                1 if slot == "correlation" else 1e9)
        if slot == "correlation":
            for i in range(len(rows)):
                _require(data["values"][i][i] in (None, 1), "correlation diagonal")
                for j in range(len(rows)):
                    _require(data["values"][i][j] == data["values"][j][i],
                             "correlation symmetry")
    elif slot == "parallel":
        _object(data, {"labels", "series"})
        _labels(data["labels"], 6)
        _list(data["series"], 4)
        names = []
        for row in data["series"]:
            _object(row, {"name", "values"})
            _text(row["name"], 32)
            names.append(row["name"])
            _list(row["values"], 6)
            _require(len(row["values"]) == len(data["labels"]), "series length")
            for value in row["values"]:
                _number(value, -1e9)
        _require(len(names) == len(set(names)), "duplicate series")
    elif slot == "dependency":
        _object(data, {"nodes", "edges"})
        _list(data["nodes"], 8)
        _list(data["edges"], 16, 0)
        ids = []
        for node in data["nodes"]:
            _object(node, {"id", "label"})
            _identifier(node["id"])
            _text(node["label"], 24)
            ids.append(node["id"])
        _require(len(ids) == len(set(ids)), "duplicate nodes")
        pairs = []
        for edge in data["edges"]:
            _object(edge, {"source", "target", "weight"})
            _identifier(edge["source"])
            _identifier(edge["target"])
            _require(edge["source"] in ids and edge["target"] in ids
                     and edge["source"] != edge["target"], "invalid edge")
            _number(edge["weight"])
            pairs.append((edge["source"], edge["target"]))
        _require(len(pairs) == len(set(pairs)), "duplicate edges")
    else:  # coverage: explicit row denominators, never infer unknown totals.
        _object(data, {"rows"})
        _list(data["rows"], 12)
        labels = []
        for row in data["rows"]:
            _object(row, {"label", "covered", "total"})
            _text(row["label"], 32)
            labels.append(row["label"])
            _count(row["covered"])
            _count(row["total"])
            _require(row["covered"] is None or row["total"] is None
                     or row["covered"] <= row["total"], "coverage exceeds total")
        _require(len(labels) == len(set(labels)), "duplicate coverage labels")


def validate_visual_spec(spec, *, expected_run_id, expected_run_hash, expected_input_hash, expected_data_hash):
    """Fail closed and return an independent validated plain-JSON snapshot."""
    spec = json.loads(_bounded_json(spec))
    _object(spec, _FIELDS)
    _require(spec["schema_version"] == SCHEMA_VERSION, "schema version")
    _require(spec["renderer_version"] == RENDERER_VERSION, "renderer version")
    _require(spec["slot"] in SLOTS, "unsupported slot")
    _identifier(spec["run_id"])
    for key in ("run_hash", "input_hash", "data_hash"):
        _require(type(spec[key]) is str and _HASH.fullmatch(spec[key]), "invalid hash")
    _require(spec["run_id"] == expected_run_id and spec["run_hash"] == expected_run_hash
             and spec["input_hash"] == expected_input_hash
             and spec["data_hash"] == expected_data_hash, "provenance mismatch")
    _require(spec["data_hash"] == visual_data_hash(spec["data"]), "data hash mismatch")
    _text(spec["title"], 80)
    _text(spec["unit"], 32)
    _text(spec["alt_text"], 240)
    _ids(spec["evidence_ids"], minimum=1)
    _object(spec["denominator"], {"label", "value"})
    _text(spec["denominator"]["label"], 40)
    _number(spec["denominator"]["value"])
    _object(spec["missingness"], {"count", "reason"})
    _count(spec["missingness"]["count"])
    _text(spec["missingness"]["reason"], 120)
    total, missing = spec["denominator"]["value"], spec["missingness"]["count"]
    _require(total is None or missing is None or missing <= total, "missing exceeds denominator")
    _validate_data(spec["slot"], spec["data"], spec["evidence_ids"])
    return spec


def _display(value):
    return "unknown" if value is None else str(value)


def _bars(ax, labels, values):
    # Do not hand None to bar(), or replace unknown values with zero-height bars.
    for index, value in enumerate(values):
        if value is None:
            ax.text(index, 0, "unknown", va="bottom", ha="center", fontsize=8)
        else:
            ax.bar(index, value, color="#1c6b50")
    ax.set_xticks(range(len(labels)), labels, rotation=20, ha="right")
    ax.set_xlim(-.6, len(labels) - .4)
    ax.set_ylim(bottom=0)


def _table(ax, headings, rows):
    ax.axis("off")
    table = ax.table(cellText=rows, colLabels=headings, loc="center", cellLoc="left")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.8)


# Fixed priority, never a caller-provided family or path. Names come from the
# installed font registry; no downloading, font installation or OS mutation.
_FONT_FAMILIES = ("Noto Sans CJK JP", "Noto Sans JP", "IPAexGothic", "IPAGothic",
                  "Meiryo", "Yu Gothic", "Yu Gothic UI", "MS Gothic",
                  "Hiragino Sans", "Hiragino Kaku Gothic ProN", "DejaVu Sans")


def _select_font(text):
    """Resolve an installed regular face that actually covers all shown glyphs."""
    from matplotlib import font_manager
    from matplotlib.ft2font import FT2Font

    # Include generated ticks, signs and renderer labels, not merely user text.
    required = {ord(char) for char in text if not char.isspace()}
    required.update(range(32, 127))
    required.add(0x2212)  # Matplotlib's Unicode minus on numeric axes.
    available = {font.name for font in font_manager.fontManager.ttflist}
    for family in _FONT_FAMILIES:
        if family not in available:
            continue
        try:
            path = font_manager.findfont(font_manager.FontProperties(family=[family]),
                                         fallback_to_default=False)
            if required <= set(FT2Font(path).get_charmap()):
                return family, path
        except (OSError, RuntimeError, ValueError):
            continue  # Unreadable or stale registry entry: try the next family.
    raise VisualSpecError("no installed font covers supplied text")


def render_visual_png(spec, *, expected_run_id, expected_run_hash, expected_input_hash, expected_data_hash):
    """Render fixed 1200x800 PNG bytes, after full validation, without file output."""
    spec = validate_visual_spec(spec, expected_run_id=expected_run_id,
                                expected_run_hash=expected_run_hash,
                                expected_input_hash=expected_input_hash, expected_data_hash=expected_data_hash)
    # Lazy imports keep validation usable without graphics dependencies.
    import matplotlib
    import numpy as np
    import PIL
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.text import Text
    from matplotlib.table import Table

    with _LOCK, matplotlib.rc_context(rc=matplotlib.rcParamsDefault):
        fig = Figure(figsize=(12, 8), dpi=100)
        FigureCanvasAgg(fig)
        data, slot = spec["data"], spec["slot"]
        axes = fig.subplots(2, 1) if slot in ("participation", "crosstab") else [fig.subplots()]
        ax = axes[0]
        dependency_labels = []
        if slot == "thematic":
            _table(ax, ["Theme", "Support evidence count", "Counterevidence count"],
                   [[r["theme"], len(r["support_ids"]), len(r["counterevidence_ids"])]
                    for r in data["rows"]])
        elif slot == "participation":
            _bars(ax, data["labels"], data["values"])
            timeline = data["timeline"]
            axes[1].plot([r["time_seconds"] for r in timeline],
                         [np.nan if r["value"] is None else r["value"] for r in timeline], "o-")
            for r in timeline:
                if r["value"] is None:
                    axes[1].text(r["time_seconds"], 0, "unknown", fontsize=8)
            start, end = timeline[0]["time_seconds"], timeline[-1]["time_seconds"]
            pad = max((end - start) * .05, 1)
            axes[1].set_xlim(start - pad, end + pad)
            axes[1].set_xlabel("Time (seconds)")
            axes[1].set_ylim(bottom=0)
        elif slot == "distribution":
            _bars(ax, [f'{r["lower"]} to {r["upper"]}' for r in data["bins"]],
                  [r["count"] for r in data["bins"]])
            ax.set_xlabel(data["bin_unit"] + " (lower inclusive, upper exclusive)")
        elif slot == "correlation":
            values = np.array([[np.nan if x is None else x for x in r] for r in data["values"]])
            cmap = matplotlib.colormaps["coolwarm"].copy()
            cmap.set_bad("#dddddd")
            fig.colorbar(ax.imshow(values, vmin=-1, vmax=1, cmap=cmap), ax=ax)
            ax.set_xticks(range(len(data["labels"])), data["labels"], rotation=20)
            ax.set_yticks(range(len(data["labels"])), data["labels"])
            for i, row in enumerate(data["values"]):
                for j, value in enumerate(row):
                    ax.text(j, i, _display(value), ha="center", va="center", fontsize=9)
        elif slot in ("crosstab", "parallel"):
            labels = data["row_labels"] if slot == "crosstab" else data["labels"]
            series = ([{"name": name, "values": [r[i] for r in data["values"]]}
                       for i, name in enumerate(data["column_labels"])]
                      if slot == "crosstab" else data["series"])
            width = .8 / len(series)
            for i, row in enumerate(series):
                x = np.arange(len(labels)) + (i - (len(series) - 1) / 2) * width
                valid = [j for j, value in enumerate(row["values"]) if value is not None]
                ax.bar(x[valid], [row["values"][j] for j in valid], width, label=row["name"])
                for j, value in enumerate(row["values"]):
                    if value is None:
                        ax.text(x[j], 0, "unknown", rotation=90, fontsize=7, ha="center")
            ax.set_xticks(range(len(labels)), labels, rotation=20)
            ax.set_xlim(-.6, len(labels) - .4)
            ax.legend(fontsize=8)
            if slot == "crosstab":
                _table(axes[1], ["Category"] + data["column_labels"],
                       [[label] + [_display(v) for v in row]
                        for label, row in zip(labels, data["values"])])
        elif slot == "dependency":
            nodes = data["nodes"]
            positions = {n["id"]: (math.cos(i * 2 * math.pi / len(nodes)),
                                    math.sin(i * 2 * math.pi / len(nodes)))
                         for i, n in enumerate(nodes)}
            pairs = {(edge["source"], edge["target"]) for edge in data["edges"]}
            for edge in data["edges"]:
                start, end = positions[edge["source"]], positions[edge["target"]]
                # A positive Arc3 radius in both directions yields opposite
                # curves. Place each weight at its own Bezier midpoint.
                radius = .22 if (edge["target"], edge["source"]) in pairs else 0
                dx, dy = end[0] - start[0], end[1] - start[1]
                ax.annotate("", xy=end, xytext=start,
                            arrowprops={"arrowstyle": "->", "shrinkA": 20, "shrinkB": 20,
                                        "connectionstyle": f"arc3,rad={radius}"})
                dependency_labels.append(ax.text(
                    (start[0] + end[0]) / 2 + radius * dy / 2,
                    (start[1] + end[1]) / 2 - radius * dx / 2,
                    _display(edge["weight"]), fontsize=9, ha="center", va="center",
                    bbox={"facecolor": "white", "edgecolor": "none", "pad": 1}))
            for node in nodes:
                dependency_labels.append(ax.text(
                    *positions[node["id"]], node["label"], ha="center", va="center",
                    bbox={"facecolor": "#eeeeee", "edgecolor": "#1c6b50"}))
            ax.set(xlim=(-1.5, 1.5), ylim=(-1.5, 1.5), aspect="equal")
            ax.axis("off")
            ax.set_title("Recorded dependencies; arrows do not establish causation", fontsize=10)
        else:
            _bars(ax, [r["label"] for r in data["rows"]], [r["covered"] for r in data["rows"]])
            for i, row in enumerate(data["rows"]):
                ax.annotate("total " + _display(row["total"]),
                            xy=(i, row["covered"] if row["covered"] is not None else 0),
                            xytext=(0, 12), textcoords="offset points",
                            va="bottom", ha="center", fontsize=8)
        for axis in axes:
            if axis.axison:
                axis.set_ylabel(spec["unit"])
        fig.suptitle(spec["title"], fontsize=16)
        footer = (f'Run {spec["run_id"]} | Unit: {spec["unit"]} | '
                  f'Denominator {spec["denominator"]["label"]}: {_display(spec["denominator"]["value"])}\n'
                  f'Missing: {_display(spec["missingness"]["count"])} | {spec["missingness"]["reason"]}\n'
                  f'Evidence: {", ".join(spec["evidence_ids"][:3])}'
                  + (" (all IDs in PNG metadata)" if len(spec["evidence_ids"]) > 3 else ""))
        fig.text(.05, .035, footer, fontsize=8)
        fig.subplots_adjust(left=.12, right=.92, bottom=.20, top=.90, hspace=.7)
        texts = fig.findobj(Text)
        # Table cells are not reliably included by Figure.findobj(Text).
        # Include them in both glyph coverage and verified-face assignment.
        for table in fig.findobj(Table):
            for cell in table.get_celld().values():
                text = cell.get_text()
                if text not in texts:
                    texts.append(text)
        family, font_path = _select_font("\n".join(text.get_text() for text in texts))
        matplotlib.rcParams["font.family"] = [family]
        for text in texts:
            # Pin the verified face rather than re-resolving an unverified
            # bold/italic variant. The registry alone supplies font_path.
            properties = text.get_fontproperties().copy()
            properties.set_file(font_path)
            text.set_fontproperties(properties)
            text.set_usetex(False)
            text.set_parse_math(False)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", UserWarning)
            fig.canvas.draw()
        _require(not any("missing from font" in str(item.message) for item in caught),
                 "font cannot display supplied text")
        renderer = fig.canvas.get_renderer()
        dependency_boxes = [text.get_bbox_patch().get_window_extent(renderer)
                            for text in dependency_labels]
        _require(not any(a.overlaps(b) for i, a in enumerate(dependency_boxes)
                         for b in dependency_boxes[i + 1:]), "dependency labels overlap")
        visible_texts = list(fig.texts)
        for axis in axes:
            visible_texts.extend(axis.texts)
            visible_texts.append(axis.title)
            if axis.axison:
                visible_texts.extend((axis.xaxis.label, axis.yaxis.label))
                for dimension, limits in ((axis.xaxis, axis.get_xlim()),
                                          (axis.yaxis, axis.get_ylim())):
                    low, high = sorted(limits)
                    labels = [label for tick in dimension.get_major_ticks()
                              if low <= tick.get_loc() <= high
                              for label in (tick.label1, tick.label2)
                              if label.get_visible() and label.get_text()]
                    visible_texts.extend(labels)
                    boxes = [label.get_window_extent(renderer) for label in labels]
                    _require(not any(a.overlaps(b) for i, a in enumerate(boxes)
                                     for b in boxes[i + 1:]), "tick labels overlap")
        for text in visible_texts:
            if text.get_visible() and text.get_text():
                box = text.get_window_extent(renderer)
                _require(box.x0 >= 0 and box.y0 >= 0 and box.x1 <= 1200
                         and box.y1 <= 800, "text does not fit canvas")
        for table in fig.findobj(Table):
            for cell in table.get_celld().values():
                box = cell.get_text().get_window_extent(renderer)
                bounds = cell.get_window_extent(renderer)
                _require(box.width <= bounds.width * .9 and box.height <= bounds.height,
                         "text does not fit table")
        description = json.dumps({"spec": spec, "runtime": {
            "matplotlib": matplotlib.__version__, "pillow": PIL.__version__, "font_family": family}},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        output = io.BytesIO()
        fig.canvas.print_png(output, metadata={"Software": RENDERER_VERSION, "Description": description})
        fig.clear()
        return output.getvalue()
