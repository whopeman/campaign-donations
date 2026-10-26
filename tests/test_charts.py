"""
tests/test_charts.py
Project : Campaign Donations
Date    : 2026-10-26
Purpose : Pie and bar SVGs must be readable without colour vision: every
          slice has a pattern fill, a text legend and a percentage.
Change log:
  2026-10-26  0.1.0  Initial tests.
"""

import re
import xml.etree.ElementTree as ET

from cdpipe.charts import Bar, Slice, pie_svg, stacked_bars_svg

NS = {"s": "http://www.w3.org/2000/svg"}


def _parse(svg):
    return ET.fromstring(svg)


def test_pie_has_one_path_per_nonzero_slice():
    svg = pie_svg(
        [Slice("Support", 300, "support"), Slice("Oppose", 100, "oppose"), Slice("Zero", 0, "x")],
        title="Spending for and against",
    )
    root = _parse(svg)
    assert len(root.findall(".//s:path[@class='slice']", NS)) == 2


def test_each_slice_uses_a_distinct_pattern():
    svg = pie_svg([Slice("Support", 1, "support"), Slice("Oppose", 1, "oppose")], title="t")
    fills = re.findall(r'class="slice"[^>]*fill="url\(#([^)]+)\)"', svg)
    assert len(fills) == 2
    assert len(set(fills)) == 2
    for pid in fills:
        assert f'<pattern id="{pid}"' in svg


def test_legend_lists_labels_amounts_and_percentages():
    svg = pie_svg([Slice("Support", 750, "support"), Slice("Oppose", 250, "oppose")], title="t")
    assert "Support" in svg and "$750" in svg and "75.0%" in svg
    assert "Oppose" in svg and "$250" in svg and "25.0%" in svg


def test_is_accessible():
    svg = pie_svg([Slice("Support", 1, "support")], title="Money for Jane Doe")
    root = _parse(svg)
    assert root.get("role") == "img"
    assert root.find("s:title", NS).text == "Money for Jane Doe"


def test_single_slice_draws_full_circle():
    svg = pie_svg([Slice("Support", 10, "support")], title="t")
    root = _parse(svg)
    assert root.findall(".//s:circle[@class='slice']", NS)


def test_empty_data_says_so():
    svg = pie_svg([], title="t")
    assert "No reported spending" in svg


def test_stacked_bars_one_row_per_cycle_with_party_patterns():
    svg = stacked_bars_svg(
        [
            Bar("2024", [Slice("Democratic", 300, "DEM"), Slice("Republican", 100, "REP")]),
            Bar("2022", [Slice("Republican", 50, "REP")]),
        ],
        title="Giving by party",
        uid="b1",
    )
    root = _parse(svg)
    assert len(root.findall(".//s:rect[@class='seg']", NS)) == 3
    assert "$400" in svg and "$50" in svg
    assert svg.count("<pattern ") == 2  # one per party, shared across cycles


def test_two_charts_on_one_page_have_unique_ids():
    a = pie_svg([Slice("Support", 1, "support"), Slice("Oppose", 1, "oppose")], "t", uid="a")
    b = pie_svg([Slice("Support", 1, "support"), Slice("Oppose", 1, "oppose")], "t", uid="b")
    ids_a = set(re.findall(r'<pattern id="([^"]+)"', a))
    ids_b = set(re.findall(r'<pattern id="([^"]+)"', b))
    assert not ids_a & ids_b


def test_labels_are_escaped():
    svg = pie_svg([Slice("<script>alert(1)</script>", 1, "support")], title="<b>")
    assert "<script>" not in svg
    _parse(svg)  # still well-formed XML
