"""
src/cdpipe/db.py
Project : Campaign Donations
Date    : 2026-10-26
Purpose : Render the site from the "site" schema built by sql/20_site.sql.
          Pages are streamed one at a time with server-side cursors, so memory
          stays flat even with millions of donors.
Usage   : build_from_db(site, flags, dsn="dbname=fec")
Change log:
  2026-10-26  0.1.0  Initial version.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from itertools import groupby

import psycopg
from psycopg import sql

from cdpipe import states
from cdpipe.flags import Flags
from cdpipe.models import Candidate, CandidateTotals, Donor, Gift
from cdpipe.render import Site

DONOR_ROWS_PER_CYCLE = 500  # donor rows listed on a candidate page, per cycle
DONOR_COLS = (
    "d.donor_key, d.name, d.kind, d.city, d.state, d.employer, d.occupation, d.cmte_id, d.has_page"
)


def _donor(r) -> Donor:
    return Donor(r[0], r[1] or r[0], r[2], r[3], r[4], r[5], r[6], r[7], bool(r[8]))


def _candidates(cur, schema: str) -> dict[str, Candidate]:
    cur.execute(
        sql.SQL(
            """SELECT cand_id, array_agg(cycle ORDER BY cycle),
                      (array_agg(name ORDER BY cycle DESC))[1],
                      (array_agg(party ORDER BY cycle DESC))[1],
                      (array_agg(office ORDER BY cycle DESC))[1],
                      (array_agg(state ORDER BY cycle DESC))[1],
                      (array_agg(district ORDER BY cycle DESC))[1],
                      bool_or(incumbent)
               FROM {}.candidate GROUP BY cand_id"""
        ).format(sql.Identifier(schema))
    )
    return {
        r[0]: Candidate(r[0], r[2], r[3], r[4], r[5], r[6], bool(r[7]), tuple(r[1]))
        for r in cur.fetchall()
    }


def _totals(cur, schema: str) -> dict[tuple[str, int], CandidateTotals]:
    cur.execute(
        sql.SQL(
            "SELECT cand_id, cycle, individual, committee, ie_support, ie_oppose, "
            "other_individual FROM {}.cand_totals"
        ).format(sql.Identifier(schema))
    )
    return {(r[0], r[1]): CandidateTotals(*map(float, r[2:])) for r in cur.fetchall()}


def _candidate_rows(conn, schema: str, cand_id: str):
    """Donor rows for one candidate: combined per donor, capped per cycle."""
    q = sql.SQL(
        """WITH g AS (
             SELECT cycle, donor_key, via, support, sum(amount) AS amount, count(*) AS n,
                    max(gift_date) AS last_date,
                    (array_agg(source_url ORDER BY gift_date DESC NULLS LAST))[1] AS src
             FROM {s}.gift WHERE cand_id = %s
             GROUP BY cycle, donor_key, via, support
           ), r AS (
             SELECT g.*, row_number() OVER (PARTITION BY cycle ORDER BY amount DESC) AS rn
             FROM g
           )
           SELECT r.cycle, r.via, r.support, r.amount, r.n, r.last_date, r.src, r.rn, {cols}
           FROM r JOIN {s}.donor d USING (donor_key)
           ORDER BY r.cycle, r.rn"""
    ).format(s=sql.Identifier(schema), cols=sql.SQL(DONOR_COLS))
    with conn.cursor() as cur:
        cur.execute(q, (cand_id,))
        return cur.fetchall()


def _iter_donor_gifts(conn, schema: str, cands: dict[str, Candidate]) -> Iterator[tuple]:
    q = sql.SQL(
        """SELECT {cols}, g.cand_id, g.cycle, g.amount, g.support, g.gift_date,
                  g.source_url, g.via
           FROM {s}.gift g JOIN {s}.donor d USING (donor_key)
           WHERE d.has_page
           ORDER BY d.donor_key, g.cycle DESC, g.amount DESC"""
    ).format(s=sql.Identifier(schema), cols=sql.SQL(DONOR_COLS))
    with conn.cursor(name="donor_gifts") as cur:
        cur.itersize = 20_000
        cur.execute(q)
        yield from cur


def _top_donors(conn, schema: str, state: str) -> list[tuple[Donor, float]]:
    q = sql.SQL(
        """SELECT {cols}, t.total FROM (
             SELECT donor_key, sum(amount) AS total FROM {s}.gift
             WHERE support GROUP BY donor_key) t
           JOIN {s}.donor d USING (donor_key)
           WHERE d.state = %s AND d.has_page
           ORDER BY t.total DESC LIMIT 100"""
    ).format(s=sql.Identifier(schema), cols=sql.SQL(DONOR_COLS))
    with conn.cursor() as cur:
        cur.execute(q, (state,))
        return [(_donor(r), float(r[9])) for r in cur.fetchall()]


def build_from_db(site: Site, flags: Flags, dsn: str | None = None, schema: str = "site") -> dict:
    dsn = dsn or os.environ.get("CD_DSN", "dbname=fec")
    counts = {"candidates": 0, "donors": 0}
    site.common_pages()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cands = _candidates(cur, schema)
            totals = _totals(cur, schema)

        for s in states.STATES:
            mine = [c for c in cands.values() if c.state == s.code]
            site.state_page(s, mine, _top_donors(conn, schema, s.code))

        for c in cands.values():
            details: dict[int, list[Gift]] = {}
            more: dict[int, tuple[int, float]] = {}
            for r in _candidate_rows(conn, schema, c.cand_id):
                cycle, via, support, amount, n, last, src, rn = r[:8]
                if rn > DONOR_ROWS_PER_CYCLE:
                    cnt, amt = more.get(cycle, (0, 0.0))
                    more[cycle] = (cnt + 1, amt + float(amount))
                    continue
                date = last.isoformat() if last else None
                g = Gift(_donor(r[8:]), c, cycle, float(amount), support, date, src, via, n)
                details.setdefault(cycle, []).append(g)
            cand_totals = {
                cy: totals[(c.cand_id, cy)] for cy in c.cycles if (c.cand_id, cy) in totals
            }
            site.candidate_page(c, cand_totals, details, more)
            counts["candidates"] += 1

        for _, rows in groupby(_iter_donor_gifts(conn, schema, cands), key=lambda r: r[0]):
            rows = list(rows)
            d = _donor(rows[0])
            gifts = []
            for r in rows:
                cand = cands.get(r[9])
                if cand is None:
                    continue
                date = r[13].isoformat() if r[13] else None
                gifts.append(Gift(d, cand, r[10], float(r[11]), r[12], date, r[14], r[15]))
            site.donor_page(d, gifts)
            counts["donors"] += 1
    return counts
