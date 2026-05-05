from __future__ import annotations

import json

from rag.ingest.cve_feed import _parse_nvd_json


def test_parse_nvd_json_extracts_cve_description_reference_and_weakness() -> None:
    records = _parse_nvd_json(
        json.dumps(
            {
                "vulnerabilities": [
                    {
                        "cve": {
                            "id": "CVE-2099-0042",
                            "published": "2099-02-03T00:00:00.000",
                            "descriptions": [
                                {
                                    "lang": "en",
                                    "value": "Reflected cross-site scripting in the demo search page.",
                                }
                            ],
                            "weaknesses": [
                                {"description": [{"lang": "en", "value": "CWE-79"}]}
                            ],
                            "references": [
                                {"url": "https://vendor.example/advisory/CVE-2099-0042"}
                            ],
                        }
                    }
                ]
            }
        ),
        limit=10,
    )

    assert len(records) == 1
    record = records[0]
    assert record.cve_id == "CVE-2099-0042"
    assert record.title == "CVE-2099-0042"
    assert record.description == "Reflected cross-site scripting in the demo search page."
    assert record.link == "https://vendor.example/advisory/CVE-2099-0042"
    assert record.published == "2099-02-03T00:00:00.000"
    assert record.source == "nvd"
    assert record.tags == ["CWE-79"]


def test_parse_nvd_json_supports_legacy_cve_items_shape() -> None:
    records = _parse_nvd_json(
        json.dumps(
            {
                "CVE_Items": [
                    {
                        "cve": {
                            "CVE_data_meta": {"ID": "CVE-2099-0043"},
                            "description": {
                                "description_data": [
                                    {"lang": "en", "value": "SQL injection in a legacy endpoint."}
                                ]
                            },
                            "problemtype": {
                                "problemtype_data": [
                                    {"description": [{"lang": "en", "value": "CWE-89"}]}
                                ]
                            },
                            "references": {
                                "referenceData": [
                                    {"url": "https://vendor.example/advisory/CVE-2099-0043"}
                                ]
                            },
                        },
                        "publishedDate": "2099-02-04T00:00Z",
                    }
                ]
            }
        ),
        limit=10,
    )

    assert len(records) == 1
    assert records[0].cve_id == "CVE-2099-0043"
    assert records[0].description == "SQL injection in a legacy endpoint."
    assert records[0].link == "https://vendor.example/advisory/CVE-2099-0043"
    assert records[0].published == "2099-02-04T00:00Z"
    assert records[0].tags == ["CWE-89"]
