from datetime import date

import pytest
from pydantic import ValidationError

from aivms_shared.payloads import CommandType
from app.schemas.report import ReportFilters, ReportOptions
from app.services.report_service import _filename


def _filters(**kw):
    return ReportFilters(**{"start_date": "2026-10-23", "end_date": "2026-10-23", **kw})


def test_filename_follows_the_edge_export_pattern():
    assert _filename(_filters()) == "attendance_all_2026-10-23_2026-10-23.pdf"
    assert _filename(_filters(employee_id="E001", end_date="2026-10-24")) == "attendance_E001_2026-10-23_2026-10-24.pdf"
    # nothing from the filter can escape the file name
    assert _filename(_filters(employee_id='../"x"')) == "attendance_x_2026-10-23_2026-10-23.pdf"


def test_period_must_be_ordered_and_at_most_366_days():
    with pytest.raises(ValidationError):
        _filters(start_date="2026-10-24", end_date="2026-10-23")
    with pytest.raises(ValidationError):
        _filters(start_date="2025-01-01", end_date="2026-01-02")
    assert _filters(start_date="2025-01-01", end_date="2025-12-31").end_date == date(2025, 12, 31)


def test_fixed_codes_are_checked():
    assert _filters(attendance_status="late_confirmed", vlm="supported", review="pending", face="matched")
    with pytest.raises(ValidationError):
        _filters(attendance_status="late")


def test_options_default_to_empty_lists():
    assert all(v == [] for v in ReportOptions().model_dump().values())


def test_generate_report_is_a_command():
    assert CommandType("generate_report") is CommandType.GENERATE_REPORT
