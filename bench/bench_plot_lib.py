#!/usr/bin/env python3
# Plot helpers for benchmark results

import logging
import os
from copy import deepcopy
from typing import Dict, List, Tuple, Callable, Union

import numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt

# Embed fonts as TrueType so PDFs are editable in Illustrator/Inkscape
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

from bench_lib import BenchRun

log = logging.getLogger(__name__)

# Default color cycle for series — human-readable matplotlib named colors
DEFAULT_COLORS = [
    "steelblue",
    "darkorange",
    "firebrick",
    "forestgreen",
    "mediumpurple",
    "saddlebrown",
    "deeppink",
    "dimgray",
    "olive",
    "teal",
]


def exists_config_in_results(results: List[BenchRun], config: Dict) -> bool:
    for r in results:
        if r.config == config:
            return True
    return False


def configs_select(results: List[BenchRun], config_match: Dict) -> List[Dict]:
    return [r.config for r in results if config_match.items() <= r.config.items()]


def results_select(
    results: List[BenchRun], config_match: Dict, select_fn: Callable
) -> List[BenchRun]:
    # Select results based on partial config match
    return [
        select_fn(r.results)
        for r in results
        if config_match.items() <= r.config.items()
    ]


def single_result_select(
    results: List[BenchRun], config_match: Dict, select_fn: Callable
) -> BenchRun:
    # Select results based on partial config match
    results = results_select(results, config_match, select_fn)
    if len(results) != 1:
        raise ValueError("Expected 1 result, got %s" % results)
    return results[0]


def config_combinations(results: List[BenchRun], fields: List[str]) -> List[Dict]:
    """Get all unique config combinations for the given fields."""
    configs = []
    for r in results:
        if not set(r.config.keys()) >= set(fields):
            continue
        new_combination = {}
        for field in fields:
            new_combination[field] = r.config[field]
        if new_combination not in configs:
            configs.append(new_combination)
    return configs


def filter_lists(l1: List, l2: List, f: callable) -> Tuple[List, List]:
    """Filter two lists based on a filter function."""
    good_idxs = []
    if len(l1) != len(l2):
        raise ValueError("Lists must be of same length")
    for i in range(len(l1)):
        if f(l1[i], l2[i]):
            good_idxs.append(i)
    return [l1[i] for i in good_idxs], [l2[i] for i in good_idxs]


def assert_only_differs_in_fields(configs: List[Dict], fields: List[str]):
    copied_configs = [deepcopy(config) for config in configs]
    copied_configs = [
        {k: v for k, v in config.items() if k not in fields}
        for config in copied_configs
    ]
    for config in copied_configs:
        assert copied_configs[0] == config, (
            f"Configs differ in fields other than {fields}. Configs: {configs}"
        )


class GrouppedBarPlot(object):
    def __init__(
        self,
        names: List[str],
        y_values: List[List],
        groups: List[str],
        colors: List[str],
        y_label=None,
    ) -> None:
        assert len(names) == len(y_values)
        assert len(y_values) > 0
        self.names = names
        self.y_values = y_values
        self.groups = groups
        self.num_bars = len(y_values)
        self.colors = colors
        self.y_label = y_label


def plot_groupped_bars(
    gpplot: GrouppedBarPlot,
    output="groupped_bars.pdf",
    show_measurements=True,
    measurement_fontsize=10,
    measurement_rotation=0,
    measurement_offset=1000,
    bar_width=0.7,
    ylimit=None,
    hide_y_ticks=False,
    fontsize=12,
    legend_fontsize=12,
    label_fontsize=None,
    legend_loc="best",
    text_center_list=None,
):
    if label_fontsize is None:
        label_fontsize = fontsize

    num_bars = gpplot.num_bars
    step = bar_width
    start = -bar_width * (num_bars - 1) / 2
    end = start + bar_width * (num_bars - 1)
    offsets = np.arange(start, end + step, step)
    xticks = np.arange(0, 4 * len(gpplot.groups), step=4)
    for i in range(num_bars):
        plt.bar(
            xticks + offsets[i],
            gpplot.y_values[i],
            width=bar_width,
            label=gpplot.names[i],
            color=gpplot.colors[i],
        )
        if show_measurements:
            for j, v in enumerate(xticks + offsets[i]):
                if text_center_list and j in text_center_list:
                    plt.text(
                        v + 0.1 * bar_width,
                        ylimit / 2,
                        str(int(gpplot.y_values[i][j] / 1000)) + "K",
                        ha="center",
                        rotation=measurement_rotation,
                        fontsize=measurement_fontsize,
                        color="white",
                        weight="bold",
                    )
                else:
                    plt.text(
                        v + 0.1 * bar_width,
                        gpplot.y_values[i][j] + measurement_offset,
                        str(int(gpplot.y_values[i][j] / 1000)) + "K",
                        ha="center",
                        rotation=measurement_rotation,
                        fontsize=measurement_fontsize,
                        color=gpplot.colors[i],
                        weight="bold",
                    )
    plt.xticks(xticks, gpplot.groups, fontsize=fontsize)
    if gpplot.y_label:
        plt.ylabel(gpplot.y_label, fontsize=label_fontsize)

    if ylimit:
        plt.ylim(0, ylimit)

    if hide_y_ticks:
        plt.tick_params(axis="y", which="both", labelleft=False)

    plt.yticks(fontsize=fontsize)
    plt.legend(fontsize=legend_fontsize, loc=legend_loc)
    plt.tight_layout()
    plt.savefig(output, bbox_inches="tight", metadata={"creationDate": None})
    plt.clf()


def bench_plot_groupped_results(
    config_matches: List[Dict],
    results: List[BenchRun],
    colors=["salmon", "maroon", "peru"],
    filename="groupped_bars.pdf",
    name_func=None,
    bench_types=None,
    bench_type_to_group: Union[None, Dict[str, str]] = None,
    result_select_fn=lambda r: r["throughput_avg"],
    y_label="Total Throughput (req/sec)",
    ylimit=None,
    hide_y_ticks=False,
    show_measurements=True,
    measurement_rotation=90,
    measurement_fontsize=12,
    fontsize=12,
    legend_fontsize=12,
    measurement_offset=1000,
    bar_width=1,
    label_fontsize=None,
    legend_loc="best",
    normalize_per_group=False,
    text_center_list=None,
):
    """Plot grouped bar chart results.

    Config match dicts should contain the fields needed to select results,
    plus a "benchmark" field that will be iterated over bench_types.
    """
    if bench_types is None:
        bench_types = []
    if name_func is None:
        name_func = lambda c: str(c)

    if not bench_type_to_group:
        bench_type_to_group = {}
        for idx in range(len(bench_types)):
            bench_type_to_group[bench_types[idx]] = f"Benchmark {idx}"
    groups = [bench_type_to_group[bench_type] for bench_type in bench_types]
    names = []
    y_values = []

    for config_match in config_matches:
        names.append(name_func(config_match))
        ys = []

        for bench_type in bench_types:
            config_match["benchmark"] = bench_type
            y_res = results_select(results, config_match, result_select_fn)
            cm_res = configs_select(results, config_match)
            if len(y_res) > 1:
                assert_only_differs_in_fields(cm_res, ["iteration"])
                y_res = [np.mean(y_res)]
            elif len(y_res) == 0:
                raise Exception(f"No results for {config_match}")
            assert len(y_res) == 1, "len(y_res) = %d" % len(y_res)
            ys.append(y_res[0])
        assert len(ys) == len(groups), "len(ys) = %d" % len(ys)
        y_values.append(ys)

    if normalize_per_group:
        for idx in range(len(y_values[0])):
            max_value_for_idx = max([ys[idx] for ys in y_values])
            for ys in y_values:
                ys[idx] = ys[idx] / max_value_for_idx * 100

    gpplot = GrouppedBarPlot(names, y_values, groups, colors, y_label=y_label)
    assert gpplot.num_bars == len(colors), "gpplot.num_bars = %d, len(colors) = %d" % (
        gpplot.num_bars,
        len(colors),
    )

    plot_groupped_bars(
        gpplot,
        filename,
        measurement_offset=measurement_offset,
        bar_width=bar_width,
        show_measurements=show_measurements,
        measurement_fontsize=measurement_fontsize,
        measurement_rotation=measurement_rotation,
        ylimit=ylimit,
        hide_y_ticks=hide_y_ticks,
        fontsize=fontsize,
        legend_fontsize=legend_fontsize,
        label_fontsize=label_fontsize,
        legend_loc=legend_loc,
        text_center_list=text_center_list,
    )


# -------------------------------------------------------------------
#  Line chart
# -------------------------------------------------------------------

def plot_line_chart(
    results: List[BenchRun],
    series_field: str,
    x_field: str,
    y_select_fn: Callable,
    output: str = "line_chart.pdf",
    y_transform: Callable = None,
    series_order: List[str] = None,
    series_labels: Dict[str, str] = None,
    series_colors: Dict[str, str] = None,
    x_label: str = "",
    y_label: str = "",
    title: str = "",
    xscale_log2: bool = False,
    figsize: Tuple[int, int] = (10, 6),
    fontsize: int = 16,
    label_fontsize: int = None,
    title_fontsize: int = None,
    legend_fontsize: int = None,
    legend_loc: str = "best",
    grid: bool = True,
    x_tick_rotation: int = 45,
    error_bars: bool = True,
    linewidth: float = 2.5,
    markersize: float = 7,
    yscale_log: bool = False,
):
    """Plot a line chart from benchmark results.

    Each unique value of ``series_field`` in the config becomes one line.
    The x-axis is ``x_field``.  Multiple results for the same
    (series, x) pair (e.g. rounds) are averaged, with stddev error bars.

    Args:
        results:        List of BenchRun objects.
        series_field:   Config key that defines the series (one line per
                        unique value, e.g. "mode").
        x_field:        Config key for the x-axis (e.g. "threads").
        y_select_fn:    Callable to extract a y value from a BenchResults
                        object (e.g. ``lambda r: r["wall_ns"]``).
        output:         Output file path (pdf/png/svg).
        y_transform:    Optional transform applied to each y value before
                        aggregation (e.g. ``lambda ns: ns / 1e6``).
        series_order:   Explicit ordering and filter.  Only listed series
                        are plotted, in the given order.
        series_labels:  Display name overrides, keyed by series value.
        series_colors:  Color overrides, keyed by series value.
                        Use matplotlib named colors (e.g. "steelblue").
        fontsize:       Base font size for tick labels (default 16).
        label_fontsize: Axis label font size (default: fontsize + 2).
        title_fontsize: Title font size (default: fontsize + 4).
        legend_fontsize: Legend font size (default: fontsize).
        linewidth:      Line width (default 2.5).
        markersize:     Marker size (default 7).
        error_bars:     Show stddev error bars (default True).
    """
    if label_fontsize is None:
        label_fontsize = fontsize + 2
    if title_fontsize is None:
        title_fontsize = fontsize + 4
    if legend_fontsize is None:
        legend_fontsize = fontsize
    combos = config_combinations(results, [series_field, x_field])
    all_series = list(dict.fromkeys(c[series_field] for c in combos))
    x_values = sorted(set(c[x_field] for c in combos))

    # Order and filter series
    if series_order:
        all_series = [s for s in series_order if s in all_series]

    if series_labels is None:
        series_labels = {}
    if series_colors is None:
        series_colors = {}

    fig, ax = plt.subplots(figsize=figsize)

    for idx, series_val in enumerate(all_series):
        xs, ys, yerr = [], [], []
        for xv in x_values:
            raw = results_select(
                results,
                {series_field: series_val, x_field: xv},
                y_select_fn,
            )
            if not raw:
                continue
            if y_transform:
                raw = [y_transform(v) for v in raw]
            xs.append(xv)
            ys.append(np.mean(raw))
            yerr.append(np.std(raw))

        label = series_labels.get(series_val, series_val)
        color = series_colors.get(series_val,
                                  DEFAULT_COLORS[idx % len(DEFAULT_COLORS)])
        kwargs = dict(marker="o", label=label, color=color,
                      linewidth=linewidth, markersize=markersize)
        if error_bars:
            ax.errorbar(xs, ys, yerr=yerr, capsize=3, **kwargs)
        else:
            ax.plot(xs, ys, **kwargs)

    ax.set_xlabel(x_label, fontsize=label_fontsize)
    ax.set_ylabel(y_label, fontsize=label_fontsize)
    if title:
        ax.set_title(title, fontsize=title_fontsize)
    ax.legend(fontsize=legend_fontsize, loc=legend_loc)
    if grid:
        ax.set_axisbelow(True)
        ax.grid(True, alpha=0.3)
    if yscale_log:
        ax.set_yscale("log")
    if xscale_log2:
        ax.set_xscale("log", base=2)
        ax.set_xticks(x_values)
        ax.set_xticklabels([str(v) for v in x_values],
                           fontsize=fontsize, rotation=x_tick_rotation)
    ax.tick_params(axis="x", labelsize=fontsize)
    ax.tick_params(axis="y", labelsize=fontsize)

    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    fig.savefig(output, bbox_inches="tight", metadata={"creationDate": None})
    plt.close(fig)
    log.info("Plot saved to %s", output)


# -------------------------------------------------------------------
#  Grouped bar chart
# -------------------------------------------------------------------

def plot_grouped_bar_chart(
    results: List[BenchRun],
    group_field: str,
    series_field: str,
    y_select_fn: Callable,
    output: str = "bars.pdf",
    y_transform: Callable = None,
    group_order: List[str] = None,
    group_labels: Dict[str, str] = None,
    series_order: List[str] = None,
    series_labels: Dict[str, str] = None,
    series_colors: Dict[str, str] = None,
    y_label: str = "",
    title: str = "",
    figsize: Tuple[int, int] = (10, 6),
    fontsize: int = 16,
    label_fontsize: int = None,
    title_fontsize: int = None,
    legend_fontsize: int = None,
    legend_loc: str = "best",
    bar_width: float = 0.8,
    grid: bool = True,
    show_values: bool = False,
    value_fmt: str = "{:.0f}",
    error_bars: bool = True,
    ylimit: float = None,
    skip_missing: bool = True,
    log_scale: bool = False,
    hlines: List[Dict] = None,
    ylimit_top: float = None,
    legend_ncol: int = None,
    legend_columnspacing: float = None,
):
    """Plot a grouped bar chart from benchmark results.

    Each unique value of ``group_field`` becomes a group on the x-axis.
    Each unique value of ``series_field`` becomes one bar per group.
    Multiple results for the same (group, series) pair (e.g. rounds) are
    averaged, with stddev error bars.

    Args:
        results:        List of BenchRun objects.
        group_field:    Config key for x-axis groups (e.g. "fault_type").
        series_field:   Config key for bars within each group (e.g. "mode").
        y_select_fn:    Callable to extract a y value from BenchResults.
        output:         Output file path.
        y_transform:    Optional transform applied to each y value.
        group_order:    Explicit ordering and filter for groups.
        group_labels:   Display name overrides for groups.
        series_order:   Explicit ordering and filter for series (bars).
        series_labels:  Display name overrides for series.
        series_colors:  Color overrides for series.
        show_values:    Annotate bar tops with values.
        value_fmt:      Format string for value annotations.
        skip_missing:   When True (default), omit bars with no data and
                        compress remaining bars so there are no gaps.
    """
    if label_fontsize is None:
        label_fontsize = fontsize + 2
    if title_fontsize is None:
        title_fontsize = fontsize + 4
    if legend_fontsize is None:
        legend_fontsize = fontsize
    if group_labels is None:
        group_labels = {}
    if series_labels is None:
        series_labels = {}
    if series_colors is None:
        series_colors = {}

    combos = config_combinations(results, [group_field, series_field])
    all_groups = list(dict.fromkeys(c[group_field] for c in combos))
    all_series = list(dict.fromkeys(c[series_field] for c in combos))

    if group_order:
        all_groups = [g for g in group_order if g in all_groups]
    if series_order:
        all_series = [s for s in series_order if s in all_series]

    n_groups = len(all_groups)
    n_series = len(all_series)

    # Pre-compute data: data[group_idx][series_idx] = (mean, std) or None
    data = []
    for group_val in all_groups:
        row = []
        for series_val in all_series:
            raw = results_select(
                results,
                {group_field: group_val, series_field: series_val},
                y_select_fn,
            )
            if y_transform:
                raw = [y_transform(v) for v in raw]
            if raw:
                row.append((np.mean(raw), np.std(raw)))
            else:
                row.append(None)
        data.append(row)

    fig, ax = plt.subplots(figsize=figsize)
    x = np.arange(n_groups)
    width = bar_width / max(n_series, 1)
    legend_added = set()

    for gi, group_val in enumerate(all_groups):
        if skip_missing:
            present = [(si, s) for si, s in enumerate(all_series)
                       if data[gi][si] is not None]
        else:
            present = list(enumerate(all_series))

        n_bars = len(present)

        for bi, (si, series_val) in enumerate(present):
            mean, std = data[gi][si] if data[gi][si] else (0, 0)
            offset = (bi - (n_bars - 1) / 2) * width
            label_text = series_labels.get(series_val, series_val)
            color = series_colors.get(
                series_val, DEFAULT_COLORS[si % len(DEFAULT_COLORS)])

            bar_kwargs = dict(color=color, width=width)
            if series_val not in legend_added:
                bar_kwargs["label"] = label_text
                legend_added.add(series_val)
            if error_bars and data[gi][si]:
                bar_kwargs.update(yerr=std, capsize=3)

            bars = ax.bar(x[gi] + offset, mean, **bar_kwargs)

            if show_values and mean > 0:
                ax.text(x[gi] + offset, mean,
                        value_fmt.format(mean),
                        ha="center", va="bottom", fontsize=fontsize - 2,
                        color=color, weight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([group_labels.get(g, g) for g in all_groups],
                       fontsize=fontsize)
    ax.tick_params(axis="y", labelsize=fontsize)
    ax.set_ylabel(y_label, fontsize=label_fontsize)
    if title:
        ax.set_title(title, fontsize=title_fontsize)
    legend_kwargs = dict(fontsize=legend_fontsize, loc=legend_loc)
    if legend_ncol:
        legend_kwargs["ncol"] = legend_ncol
    if legend_columnspacing is not None:
        legend_kwargs["columnspacing"] = legend_columnspacing
    ax.legend(**legend_kwargs)
    if log_scale:
        ax.set_yscale("log")
        ax.set_ylim(bottom=0.8, top=ylimit_top)
    if grid:
        ax.set_axisbelow(True)
        ax.grid(True, alpha=0.3, axis="y")
    if ylimit is not None:
        ax.set_ylim(0, ylimit)
    if hlines:
        for hl in hlines:
            ax.axhline(y=hl["y"], color=hl.get("color", "gray"),
                        linestyle=hl.get("linestyle", "--"),
                        linewidth=hl.get("linewidth", 1.5),
                        alpha=hl.get("alpha", 0.7),
                        label=hl.get("label", None), zorder=10)
        if any("label" in hl for hl in hlines):
            ax.legend(**legend_kwargs)

    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    fig.savefig(output, bbox_inches="tight", metadata={"creationDate": None})
    plt.close(fig)
    log.info("Plot saved to %s", output)
