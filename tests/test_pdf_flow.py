"""Putting the blocks of a brief on pages: what moves whole, what may be cut and where."""

import pytest

import pdf_flow
from pdf_flow import Block, PageFrame

# A page whose content runs from 20 to 120: a hundred units of room.
FRAME = PageFrame(first_top=20, top=20, bottom=120)


def _block(height, **options):
    return Block(height=height, paint=lambda pdf, y: None, **options)


def _placed(slices):
    return [(piece.page, piece.y, piece.start, piece.end) for piece in slices]


def test_blocks_that_fit_follow_one_another_each_after_its_space():
    slices = pdf_flow.paginate([_block(30), _block(20, space_before=5), _block(10, space_before=5)], FRAME)
    assert _placed(slices) == [(0, 20, 0, 30), (0, 55, 0, 20), (0, 80, 0, 10)]
    assert pdf_flow.page_count(slices) == 1


def test_the_first_page_can_start_lower_than_the_rest():
    frame = PageFrame(first_top=50, top=20, bottom=120)
    slices = pdf_flow.paginate([_block(60), _block(60)], frame)
    assert _placed(slices) == [(0, 50, 0, 60), (1, 20, 0, 60)]


def test_a_block_that_does_not_fit_moves_whole_to_the_next_page_and_drops_its_space():
    slices = pdf_flow.paginate([_block(70), _block(40, space_before=8)], FRAME)
    assert _placed(slices) == [(0, 20, 0, 70), (1, 20, 0, 40)]


def test_a_heading_is_never_left_at_the_foot_of_a_page_without_what_it_heads():
    heading = _block(10, space_before=5, keep_with_next=True)
    slices = pdf_flow.paginate([_block(70), heading, _block(30, space_before=2)], FRAME)
    assert _placed(slices) == [(0, 20, 0, 70), (1, 20, 0, 10), (1, 32, 0, 30)]


def test_a_heading_stays_where_it_is_when_what_it_heads_fits_below_it():
    heading = _block(10, space_before=5, keep_with_next=True)
    slices = pdf_flow.paginate([_block(40), heading, _block(30, space_before=2)], FRAME)
    assert _placed(slices) == [(0, 20, 0, 40), (0, 65, 0, 10), (0, 77, 0, 30)]


def test_a_list_is_cut_at_the_last_break_that_fits_and_goes_on_at_the_top_of_the_next_page():
    rows = _block(90, breaks=(30, 50, 70), splits_freely=True)
    slices = pdf_flow.paginate([_block(40), rows], FRAME)
    assert _placed(slices) == [(0, 20, 0, 40), (0, 60, 0, 50), (1, 20, 50, 90)]


def test_a_list_whose_first_row_does_not_fit_starts_on_the_next_page():
    rows = _block(90, breaks=(30, 60), splits_freely=True)
    slices = pdf_flow.paginate([_block(80), rows], FRAME)
    assert _placed(slices) == [(0, 20, 0, 80), (1, 20, 0, 90)]


def test_a_card_that_fits_on_a_page_is_never_cut_even_though_it_has_breaks():
    angle = _block(80, breaks=(40, 60))
    slices = pdf_flow.paginate([_block(40), angle], FRAME)
    assert _placed(slices) == [(0, 20, 0, 40), (1, 20, 0, 80)]


def test_a_card_longer_than_a_page_is_cut_at_its_breaks():
    angle = _block(150, breaks=(60, 90, 130))
    slices = pdf_flow.paginate([angle], FRAME)
    assert _placed(slices) == [(0, 20, 0, 90), (1, 20, 90, 150)]


def test_a_block_longer_than_a_page_with_no_break_is_cut_at_the_foot_and_nothing_is_lost():
    slices = pdf_flow.paginate([_block(250)], FRAME)
    assert _placed(slices) == [(0, 20, 0, 100), (1, 20, 100, 200), (2, 20, 200, 250)]
    assert pdf_flow.page_count(slices) == 3


def test_no_blocks_still_make_one_page():
    assert pdf_flow.paginate([], FRAME) == []
    assert pdf_flow.page_count([]) == 1


class _Recorder:
    """Stands in for the PDF: records what is painted, on which page, inside which clip."""

    w = 200.0

    def __init__(self):
        self.calls = []
        self.page = 0
        self.clip = None

    def add_page(self):
        self.page += 1

    def rect_clip(self, x, y, w, h):
        recorder = self

        class _Clip:
            def __enter__(self):
                recorder.clip = (y, h)

            def __exit__(self, *exc):
                recorder.clip = None

        return _Clip()


def test_a_whole_block_is_painted_once_and_a_cut_block_once_on_each_page_inside_its_slice():
    pdf = _Recorder()
    whole = Block(height=40, paint=lambda doc, y: doc.calls.append(("whole", doc.page, y, doc.clip)))
    cut = Block(height=90, breaks=(30, 50, 70), splits_freely=True,
                paint=lambda doc, y: doc.calls.append(("cut", doc.page, y, doc.clip)))
    pdf_flow.paint(pdf, pdf_flow.paginate([whole, cut], FRAME))
    assert pdf.calls == [
        ("whole", 1, 20, None),
        ("cut", 1, 60, (60, 50)),       # its first fifty units, from where it starts
        ("cut", 2, 20 - 50, (20, 40)),  # the rest, drawn so that offset fifty sits at the top
    ]


@pytest.mark.parametrize("height", [0, 0.0])
def test_an_empty_block_takes_no_room_and_no_space(height):
    slices = pdf_flow.paginate([_block(30), _block(height, space_before=10), _block(10, space_before=5)], FRAME)
    assert _placed(slices) == [(0, 20, 0, 30), (0, 55, 0, 10)]
