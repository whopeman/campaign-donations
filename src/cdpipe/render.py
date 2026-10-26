"""
src/cdpipe/render.py
Project : Campaign Donations
Date    : 2026-10-26
Purpose : Write the static site: home page with the clickable state map,
          one page per state, candidate and donor, plus CSS and .htaccess.
          All links are relative so the site works under any folder
          (it is served from https://hopemanhorde.com/campaign-donations/).
Usage   : Site(out_dir=Path("site"), cycles=(2024,), generated="2026-10-26")
              .build(candidates, donors, gifts, totals)
Change log:
  2026-10-26  0.1.0  Initial version.
"""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from cdpipe import __version__, states
from cdpipe.charts import Bar, Slice, pie_svg, stacked_bars_svg
from cdpipe.format import pct, usd
from cdpipe.models import Candidate, CandidateTotals, Donor, Gift, party_kind, party_name

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
MAP_FILE = ROOT / "data" / "us-states-paths.json"

CSP = (
    "default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self' data:; "
    "base-uri 'none'; form-action 'none'; object-src 'none'"
)


def _svg(markup: str) -> Markup:
    """Mark SVG we generated as safe. charts.py and map_svg escape every data value."""
    return Markup(markup)  # noqa: S704


def map_svg(root: str) -> Markup:
    data = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{data["viewBox"]}" role="img" '
        f'class="us-map" aria-labelledby="map-title"><title id="map-title">Map of the United '
        f"States. Select a state to see its candidates and donors.</title>"
    ]
    for fips, st in sorted(data["states"].items(), key=lambda kv: kv[1]["name"]):
        s = states.BY_FIPS.get(fips)
        if not s:
            continue
        parts.append(
            f'<a href="{root}states/{s.code.lower()}/index.html" aria-label="{escape(s.name)}">'
            f'<path class="state" d="{st["d"]}"><title>{escape(s.name)}</title></path></a>'
        )
    parts.append(f'<path class="borders" d="{data["borders"]}"/>')
    parts.append("</svg>")
    return _svg("".join(parts))


@dataclass
class Site:
    out_dir: Path
    cycles: tuple[int, ...]
    generated: str

    def __post_init__(self):
        self.env = Environment(
            loader=FileSystemLoader(TEMPLATES),
            autoescape=select_autoescape(["html", "j2"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["usd"] = usd
        self.env.filters["party"] = party_name
        self.env.globals.update(version=__version__, generated=self.generated, csp=CSP, pct=pct)

    # -- helpers ---------------------------------------------------------------
    def _write(self, rel: str, template: str, **ctx) -> None:
        depth = rel.count("/")
        root = "../" * depth
        html = self.env.get_template(template).render(root=root, **ctx)
        dest = self.out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8", newline="\n")

    # -- build -----------------------------------------------------------------
    def build(
        self,
        candidates: list[Candidate],
        donors: list[Donor],
        gifts: list[Gift],
        totals: dict[tuple[str, int], CandidateTotals],
    ) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._static()
        by_cand: dict[str, list[Gift]] = defaultdict(list)
        by_donor: dict[str, list[Gift]] = defaultdict(list)
        for g in gifts:
            by_cand[g.candidate.cand_id].append(g)
            by_donor[g.donor.key].append(g)

        self._write(
            "index.html",
            "home.html.j2",
            map_svg=map_svg(""),
            states=states.STATES,
            cycles=self.cycles,
        )
        self._write("about.html", "about.html.j2")
        for s in states.STATES:
            self._state(s, candidates, donors, by_donor)
        for c in candidates:
            self._candidate(c, by_cand.get(c.cand_id, []), totals)
        for d in donors:
            self._donor(d, by_donor.get(d.key, []))

    def _static(self) -> None:
        css = self.out_dir / "css"
        css.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STATIC / "css" / "site.css", css / "site.css")
        shutil.copyfile(STATIC / "htaccess", self.out_dir / ".htaccess")

    def _state(self, s, candidates, donors, by_donor) -> None:
        mine = [c for c in candidates if c.state == s.code]
        rows = defaultdict(list)  # (cycle, office) -> candidates
        for c in mine:
            for cy in c.cycles:
                rows[(cy, c.office)].append(c)
        sections = []
        for cy in sorted(self.cycles, reverse=True):
            offices = []
            for off, label in (("S", "Senate"), ("H", "House")):
                cs = sorted(rows.get((cy, off), []), key=lambda c: (c.district or "", c.name))
                if cs:
                    offices.append((label, cs))
            if offices:
                sections.append((cy, offices))
        top = []
        for d in donors:
            if d.state != s.code:
                continue
            total = sum(g.amount for g in by_donor.get(d.key, []))
            if total:
                top.append((d, total))
        top.sort(key=lambda t: -t[1])
        self._write(
            f"states/{s.code.lower()}/index.html",
            "state.html.j2",
            state=s,
            sections=sections,
            top_donors=top[:100],
        )

    def _candidate(self, c: Candidate, gifts: list[Gift], totals) -> None:
        cycles = []
        for cy in sorted(c.cycles, reverse=True):
            t = totals.get((c.cand_id, cy))
            if t is None:
                continue
            slices = [
                Slice("Individuals (itemized)", t.individual, "indiv"),
                Slice("Individuals (under $200)", t.other_individual, "unitemized"),
                Slice("PACs and party committees", t.committee, "pac"),
                Slice("Outside spending for", t.ie_support, "support"),
                Slice("Outside spending against", t.ie_oppose, "oppose"),
            ]
            chart = _svg(
                pie_svg(slices, title=f"Money for and against {c.name}, {cy}", uid=f"c{cy}")
            )
            details = sorted((g for g in gifts if g.cycle == cy), key=lambda g: -g.amount)
            cycles.append((cy, t, slices, chart, details))
        self._write(f"candidates/{c.slug}.html", "candidate.html.j2", c=c, cycles=cycles)

    def _donor(self, d: Donor, gifts: list[Gift]) -> None:
        # cycle -> party -> [for, against]
        per = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
        for g in gifts:
            per[g.cycle][g.candidate.party or "UNK"][0 if g.support else 1] += g.amount
        bars = []
        summary = []
        for cy in sorted(per, reverse=True):
            parts = [
                Slice(party_name(p), v[0], party_kind(p))
                for p, v in sorted(per[cy].items(), key=lambda kv: -kv[1][0])
            ]
            against = sum(v[1] for v in per[cy].values())
            parts.append(Slice("Against candidates (any party)", against, "oppose"))
            bars.append(Bar(str(cy), parts))
            summary.append((cy, sorted(per[cy].items(), key=lambda kv: -(kv[1][0] + kv[1][1]))))
        title = f"Money for and against candidates from {d.name}, by party and cycle"
        chart = _svg(stacked_bars_svg(bars, title=title, uid="d"))
        details = sorted(gifts, key=lambda g: (-g.cycle, -g.amount))
        self._write(d.path, "donor.html.j2", d=d, chart=chart, summary=summary, details=details)
