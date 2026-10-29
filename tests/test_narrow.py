"""
tests/test_narrow.py
Project : Campaign Donations
Date    : 2026-10-28
Purpose : Column projection of pg_restore COPY output (narrow Schedule A load).
Change log:
  2026-10-28  0.1.0  Initial tests.
  2026-10-28  0.1.0  Row filter on a column's value (--where-in).
"""

import pytest

from cdpipe.narrow import header_columns, load_set, project

HEADER = (
    b"COPY disclosure.fec_fitem_sched_a_2015_2016 "
    b"(cmte_id, contbr_nm, memo_cd, sub_id) FROM stdin;\n"
)
DUMP = [
    b"--\n",
    b"-- Data for Name: fec_fitem_sched_a_2015_2016; Type: TABLE DATA\n",
    b"SET statement_timeout = 0;\n",
    HEADER,
    b"C001\tSMITH, JOHN\t\\N\t11\n",
    b"C002\tO'NEIL\\tPAT\tX\t12\n",
    b"\\.\n",
    b"\n",
]


def test_header_columns():
    assert header_columns(HEADER) == ["cmte_id", "contbr_nm", "memo_cd", "sub_id"]


def test_header_columns_with_quoted_names():
    line = b'COPY disclosure.t ("order", cmte_id) FROM stdin;\n'
    assert header_columns(line) == ["order", "cmte_id"]


def test_project_keeps_requested_columns_in_requested_order():
    out = list(project(DUMP, ["sub_id", "cmte_id", "memo_cd"]))
    assert out == [b"11\tC001\t\\N\n", b"12\tC002\tX\n"]


def test_project_keeps_escaped_tabs_inside_a_field():
    out = list(project(DUMP, ["contbr_nm"]))
    assert out == [b"SMITH, JOHN\n", b"O'NEIL\\tPAT\n"]


def test_project_keeps_only_rows_whose_value_is_in_the_set():
    out = list(project(DUMP, ["sub_id"], where=("cmte_id", {b"C002"})))
    assert out == [b"12\n"]


def test_project_filter_column_need_not_be_kept():
    out = list(project(DUMP, ["contbr_nm"], where=("cmte_id", {b"C001", b"C002"})))
    assert len(out) == 2


def test_project_rejects_unknown_filter_column():
    with pytest.raises(ValueError, match="cmte_idx"):
        list(project(DUMP, ["sub_id"], where=("cmte_idx", {b"C001"})))


def test_load_set_reads_one_value_per_line(tmp_path):
    p = tmp_path / "ids.txt"
    p.write_bytes(b"C001\n\nC002\r\n  C003  \n")
    assert load_set(p) == {b"C001", b"C002", b"C003"}


def test_project_rejects_unknown_column():
    with pytest.raises(ValueError, match="pdf_urlx"):
        list(project(DUMP, ["cmte_id", "pdf_urlx"]))


def test_project_rejects_rows_with_wrong_field_count():
    bad = [HEADER, b"C001\tSMITH\n", b"\\.\n"]
    with pytest.raises(ValueError, match="2 fields"):
        list(project(bad, ["cmte_id"]))


def test_project_fails_when_no_copy_block():
    with pytest.raises(ValueError, match="COPY"):
        list(project([b"--\n", b"SET x = 0;\n"], ["cmte_id"]))


def test_project_fails_when_copy_block_is_cut_short():
    with pytest.raises(ValueError, match="end"):
        list(project([HEADER, b"C001\tA\t\\N\t1\n"], ["cmte_id"]))
