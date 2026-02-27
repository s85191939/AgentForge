"""Unit tests for the domain-specific verification module."""

from __future__ import annotations

from agent.core.verification import (
    DISCLAIMER,
    VerificationResult,
    check_allocation_sum,
    check_negative_values,
    check_prohibited_advice,
    check_tool_data_completeness,
    verify_response,
)

# ---------------------------------------------------------------------------
# Prohibited advice checks
# ---------------------------------------------------------------------------


class TestCheckProhibitedAdvice:
    def test_clean_response_no_violations(self):
        response = "Your portfolio has 5 holdings worth $50,000 total."
        cleaned, violations = check_prohibited_advice(response)
        assert cleaned == response
        assert violations == []

    def test_detects_recommend_buying(self):
        response = "I recommend buying AAPL at the current price."
        cleaned, violations = check_prohibited_advice(response)
        assert len(violations) == 1
        assert "Prohibited phrase" in violations[0]
        assert DISCLAIMER in cleaned

    def test_detects_you_should_sell(self):
        response = "Based on the data, you should sell your TSLA position."
        cleaned, violations = check_prohibited_advice(response)
        assert len(violations) >= 1
        assert DISCLAIMER in cleaned

    def test_detects_guaranteed_returns(self):
        response = "This investment offers guaranteed returns of 20%."
        cleaned, violations = check_prohibited_advice(response)
        assert len(violations) >= 1
        assert DISCLAIMER in cleaned

    def test_detects_risk_free(self):
        response = "This is a risk-free investment opportunity."
        cleaned, violations = check_prohibited_advice(response)
        assert len(violations) >= 1

    def test_detects_cant_lose(self):
        response = "You can't lose with this stock."
        cleaned, violations = check_prohibited_advice(response)
        assert len(violations) >= 1

    def test_does_not_double_add_disclaimer(self):
        response = (
            "I recommend buying AAPL. "
            "This is not investment advice. Consult a financial advisor."
        )
        cleaned, violations = check_prohibited_advice(response)
        assert len(violations) >= 1
        # Disclaimer should NOT be appended because "not investment advice" is already present
        assert cleaned == response

    def test_my_advice_is(self):
        response = "My advice is to hold your current positions."
        cleaned, violations = check_prohibited_advice(response)
        assert len(violations) >= 1

    def test_sure_thing(self):
        response = "NVDA is a sure thing right now."
        cleaned, violations = check_prohibited_advice(response)
        assert len(violations) >= 1


# ---------------------------------------------------------------------------
# Allocation sum checks
# ---------------------------------------------------------------------------


class TestCheckAllocationSum:
    def test_valid_allocation_sums_to_100(self):
        response = "AAPL: 30%, MSFT: 25%, GOOGL: 20%, AMZN: 15%, NVDA: 10%"
        is_valid, warning = check_allocation_sum(response)
        assert is_valid is True
        assert warning is None

    def test_too_few_percentages_skipped(self):
        response = "Your portfolio is up 12.5% this year."
        is_valid, warning = check_allocation_sum(response)
        assert is_valid is True
        assert warning is None

    def test_allocation_off_by_large_amount(self):
        response = "AAPL: 50%, MSFT: 40%, GOOGL: 30%"
        is_valid, warning = check_allocation_sum(response)
        assert is_valid is False
        assert warning is not None
        assert "120.0%" in warning

    def test_within_tolerance(self):
        response = "AAPL: 33%, MSFT: 34%, GOOGL: 34%"
        is_valid, warning = check_allocation_sum(response)
        assert is_valid is True


# ---------------------------------------------------------------------------
# Negative value checks
# ---------------------------------------------------------------------------


class TestCheckNegativeValues:
    def test_no_negative_values(self):
        response = "Your portfolio value is $50,000 with 100 shares of AAPL."
        is_valid, warning = check_negative_values(response)
        assert is_valid is True
        assert warning is None

    def test_negative_portfolio_value(self):
        response = "Value: -$5000 for your AAPL position."
        is_valid, warning = check_negative_values(response)
        assert is_valid is False
        assert "Negative portfolio value" in warning

    def test_negative_shares(self):
        response = "You hold -100 shares of TSLA."
        is_valid, warning = check_negative_values(response)
        assert is_valid is False
        assert "Negative share quantity" in warning


# ---------------------------------------------------------------------------
# Tool data completeness checks
# ---------------------------------------------------------------------------


class TestCheckToolDataCompleteness:
    def test_no_tool_results_passes(self):
        is_valid, warning = check_tool_data_completeness("response", None)
        assert is_valid is True

    def test_tool_returned_data_and_response_has_data(self):
        response = "Your portfolio holds $50,000 in AAPL."
        tool_results = ["Holdings: AAPL - 100 shares at $500"]
        is_valid, warning = check_tool_data_completeness(response, tool_results)
        assert is_valid is True

    def test_tool_returned_empty_but_response_claims_data(self):
        response = "Your portfolio is worth $50,000 with these positions:\n- AAPL\n- MSFT"
        tool_results = ["No holdings found"]
        is_valid, warning = check_tool_data_completeness(response, tool_results)
        assert is_valid is False
        assert "empty/error" in warning

    def test_tool_error_but_response_claims_data(self):
        response = "Your portfolio has $25,000 invested."
        tool_results = ["Error fetching portfolio data"]
        is_valid, warning = check_tool_data_completeness(response, tool_results)
        assert is_valid is False

    def test_tool_error_without_data_claims_passes(self):
        response = "I was unable to retrieve your portfolio data."
        tool_results = ["Error fetching portfolio data"]
        is_valid, warning = check_tool_data_completeness(response, tool_results)
        assert is_valid is True


# ---------------------------------------------------------------------------
# Full verify_response orchestrator
# ---------------------------------------------------------------------------


class TestVerifyResponse:
    def test_clean_response_all_pass(self):
        result = verify_response("Your portfolio has 5 holdings.")
        assert result.passed is True
        assert result.warnings == []
        assert result.advice_violations == []
        assert result.cleaned_response == "Your portfolio has 5 holdings."

    def test_advice_violation_sets_passed_false(self):
        result = verify_response("I recommend buying AAPL.")
        assert result.passed is False
        assert len(result.advice_violations) >= 1
        assert DISCLAIMER in result.cleaned_response

    def test_allocation_warning(self):
        result = verify_response("AAPL: 50%, MSFT: 40%, GOOGL: 30%")
        assert len(result.warnings) >= 1
        assert "Allocation" in result.warnings[0]

    def test_summary_no_issues(self):
        result = VerificationResult()
        result.passed = True
        assert "passed" in result.summary()

    def test_summary_with_issues(self):
        result = VerificationResult()
        result.passed = False
        result.advice_violations = ["violation1"]
        result.warnings = ["warning1"]
        summary = result.summary()
        assert "Advice violations: 1" in summary
        assert "Warnings: 1" in summary

    def test_has_warnings_property(self):
        result = VerificationResult()
        assert result.has_warnings is False
        result.warnings.append("test")
        assert result.has_warnings is True
