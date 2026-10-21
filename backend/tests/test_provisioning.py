import pytest
from pydantic import ValidationError

from app.services.provisioning import UnprocessableError, device_uuid_for_mac, normalize_mac
from app.services.site_profile import SiteProfile


@pytest.mark.parametrize("raw", ["aa:bb:cc:dd:ee:f0", "AA-BB-CC-DD-EE-F0", "aabb.ccdd.eef0", "AABBCCDDEEF0"])
def test_mac_normalisation(raw):
    assert normalize_mac(raw) == "aa:bb:cc:dd:ee:f0"
    assert device_uuid_for_mac(normalize_mac(raw)) == "REACH-AABBCCDDEEF0"


@pytest.mark.parametrize("raw", ["00:00:00:00:00:00", "01:00:5e:00:00:01", "ff:ff:ff:ff:ff:ff", "not-a-mac", "",
                                 "aa:bb:cc:dd:ee"])
def test_invalid_macs(raw):
    with pytest.raises(UnprocessableError):
        normalize_mac(raw)


def test_site_profile_rules_match_the_contract():
    ok = SiteProfile.model_validate({"tax_id": "12345678", "term_years": 3, "license_until": "2027-10-31",
                                     "transaction_type": "lease", "profile": "office", "company_phone": "02-0000-0000"})
    assert ok.payload()["term_years"] == 3
    assert SiteProfile().payload() is None  # nothing known -> null, never {}
    for bad in ({"tax_id": "1234"}, {"term_years": True}, {"term_years": "3"}, {"term_years": 100},
                {"license_until": "2027/10/31"}, {"profile": "home"}, {"transaction_type": "rent"},
                {"company_phone": "abc"}, {"owner_id": "x"}, {"site_name": "x" * 129}):
        with pytest.raises(ValidationError):
            SiteProfile.model_validate(bad)
