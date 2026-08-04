"""Explicit suspended-state adapter for the Serbian source."""

from .base import AdapterResult, SourceAdapter, ValidationIssue


class HidmetAdapter(SourceAdapter):
    source_id = "hidmet_rs"
    provider_id = "hidmet_rs"
    country_code = "RS"
    expected_min_stations = 0

    def initial_requests(self):
        return []

    def parse(self, payloads):
        return AdapterResult(
            source_id=self.source_id, country_code="RS", status="suspended",
            stations=[], observations=[], forecasts=[],
            issues=[ValidationIssue(
                "critical", "tls_certificate_validation",
                "The audited HTTPS certificate chain could not be validated. TLS verification is never disabled.",
            )],
            notes=["No request is made and no data is published until the official TLS chain validates normally."],
        )
