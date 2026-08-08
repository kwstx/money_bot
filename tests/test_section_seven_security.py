import pytest
from datetime import datetime, timezone

from src.security import (
    ContractScanner,
    OwnershipSystem,
    HoneypotEngine,
    RugDetector,
    SectionSevenSecurityEngine,
    ContractScanResult,
    OwnershipEvaluation,
    HoneypotSimulationResult,
    LPLockDetails,
    HolderConcentration,
    RugRiskReport,
    ComprehensiveSecurityAssessment,
    SecurityContext,
    security_context
)


@pytest.fixture
def scanner():
    return ContractScanner()


@pytest.fixture
def ownership_system():
    return OwnershipSystem()


@pytest.fixture
def honeypot_engine():
    return HoneypotEngine()


@pytest.fixture
def rug_detector():
    return RugDetector()


@pytest.fixture
def section_seven_engine():
    return SectionSevenSecurityEngine()


def test_security_context_backwards_compatibility():
    """Ensures existing SecurityContext functionality remains unaffected."""
    context = SecurityContext()
    context.assert_execution_permission("Execution")
    with pytest.raises(PermissionError):
        context.assert_execution_permission("Research")

    safe = context.get_safe_metadata({"ip_address": "127.0.0.1", "auth_token": "secret", "user": "alice"})
    assert "ip_address" not in safe
    assert "auth_token" not in safe
    assert safe["user"] == "alice"
    assert security_context is not None


def test_contract_scanner_bytecode_and_permissions(scanner):
    """Tests contract bytecode scanning, signature extraction, proxy detection, and permission matrix."""
    token_addr = "0x1111222233334444555566667777888899990000"

    # Simulated bytecode containing mint (0x40c10f19), freeze (0x6b004245), and blacklist (0x42e05739)
    mock_bytecode = "0x608060405240c10f196b00424542e057393659cfe6"

    res = scanner.scan_contract(
        token_address=token_addr,
        chain="ethereum",
        bytecode=mock_bytecode,
        source_code="contract Token { function mint() public; function upgradeTo(address) public; }",
        metadata={
            "storage_slots": {
                "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc": "0x9999999999999999999999999999999999999999"
            }
        }
    )

    assert isinstance(res, ContractScanResult)
    assert res.is_verified is True
    assert res.permissions.can_mint is True
    assert res.permissions.can_freeze is True
    assert res.permissions.can_blacklist is True
    assert res.permissions.can_upgrade_logic is True

    # Proxy check
    assert res.proxy_info.is_proxy is True
    assert res.proxy_info.proxy_type == "EIP-1967"
    assert res.proxy_info.implementation_address == "0x9999999999999999999999999999999999999999"

    # Risk flags check
    assert "UNBOUNDED_MINTING_PRIVILEGE" in res.risk_flags
    assert "BLACKLIST_PRIVILEGE_DETECTED" in res.risk_flags


def test_ownership_system_fake_renouncement(ownership_system, scanner):
    """Tests owner resolution, renouncement status, and fake/bypassed renouncement detection."""
    token_addr = "0x2222333344445555666677778888999900001111"

    # 1. Genuine Renouncement
    res_genuine = ownership_system.analyze_ownership(
        token_address=token_addr,
        chain="ethereum",
        override_metadata={
            "owner_address": "0x0000000000000000000000000000000000000000",
            "privileged_roles": {}
        }
    )
    assert res_genuine.is_renounced is True
    assert res_genuine.is_fake_renouncement is False
    assert res_genuine.governance_type == "RENOUNCED"

    # 2. Fake Renouncement (Owner set to 0x0, but Proxy Admin is active)
    mock_scan = scanner.scan_contract(
        token_address=token_addr,
        chain="ethereum",
        metadata={
            "is_proxy": True,
            "implementation_address": "0x8888888888888888888888888888888888888888",
            "proxy_admin": "0x5555555555555555555555555555555555555555",
            "can_mint": True
        }
    )

    res_fake = ownership_system.analyze_ownership(
        token_address=token_addr,
        chain="ethereum",
        scan_result=mock_scan,
        override_metadata={
            "owner_address": "0x0000000000000000000000000000000000000000",
            "proxy_admin": "0x5555555555555555555555555555555555555555"
        }
    )
    assert res_fake.is_renounced is True
    assert res_fake.is_fake_renouncement is True
    assert res_fake.governance_type == "FAKE_RENOUNCED_BYPASSED"
    assert len(res_fake.fake_renouncement_reasons) > 0
    assert res_fake.upgradeability_risk == "CRITICAL"


def test_honeypot_engine_cannot_sell_and_tax(honeypot_engine):
    """Tests honeypot detection for un-sellable tokens, high taxes, and wallet-specific behavior."""
    token_addr = "0x3333444455556666777788889999000011112222"

    # 1. Standard Token Honeypot Simulation (cannot sell)
    res_honeypot = honeypot_engine.simulate_honeypot(
        token_address=token_addr,
        chain="bsc",
        advertised_buy_tax=5.0,
        advertised_sell_tax=5.0,
        simulation_override={"cannot_sell": True}
    )

    assert isinstance(res_honeypot, HoneypotSimulationResult)
    assert res_honeypot.is_honeypot is True
    assert res_honeypot.overall_honeypot_risk_score == 99.0
    assert "Sell failed" in res_honeypot.honeypot_reason

    # 2. Dynamic / Wallet-Specific Tax Detection
    res_dynamic = honeypot_engine.simulate_honeypot(
        token_address=token_addr,
        chain="ethereum",
        advertised_buy_tax=2.0,
        advertised_sell_tax=2.0,
        simulation_override={"fresh_wallet_high_tax": True, "dynamic_tax_detected": True}
    )

    assert res_dynamic.is_wallet_specific_tax is True
    assert res_dynamic.is_dynamic_tax is True
    assert res_dynamic.overall_honeypot_risk_score >= 75.0


def test_honeypot_engine_simulation_failure_as_risk(honeypot_engine):
    """Verifies requirement that simulation failure is treated as explicit risk signal."""
    token_addr = "0x4444555566667777888899990000111122223333"

    res_failed = honeypot_engine.simulate_honeypot(
        token_address=token_addr,
        chain="solana",
        simulation_override={"force_simulation_failure": True}
    )

    assert res_failed.simulation_failed is True
    assert res_failed.simulation_failure_as_risk is True
    assert res_failed.is_honeypot is True
    assert res_failed.overall_honeypot_risk_score >= 90.0


def test_rug_detector_immediate_risk_escalation(rug_detector, scanner, ownership_system, honeypot_engine):
    """Tests rug pull risk scoring and execution gatekeeper blocking on critical threat signals."""
    token_addr = "0x5555666677778888999900001111222233334444"

    scan_res = scanner.scan_contract(token_addr, "ethereum")
    ownership_res = ownership_system.analyze_ownership(token_addr, "ethereum")
    honeypot_res = honeypot_engine.simulate_honeypot(token_addr, "ethereum")

    lp_details = LPLockDetails(
        is_lp_locked=False,
        lock_percentage=0.0
    )
    concentration = HolderConcentration(
        top10_percentage=75.0,
        dev_wallet_percentage=25.0
    )

    # 1. Normal risk evaluation
    normal_report = rug_detector.evaluate_rug_risk(
        token_address=token_addr,
        chain="ethereum",
        scan_result=scan_res,
        ownership_eval=ownership_res,
        honeypot_res=honeypot_res,
        lp_details=lp_details,
        concentration=concentration
    )
    assert isinstance(normal_report, RugRiskReport)
    assert normal_report.rug_risk_score > 30.0

    # 2. Sudden LP Removal Escalation -> Immediate Execution Block
    lp_removal_report = rug_detector.evaluate_rug_risk(
        token_address=token_addr,
        chain="ethereum",
        scan_result=scan_res,
        ownership_eval=ownership_res,
        honeypot_res=honeypot_res,
        lp_details=lp_details,
        concentration=concentration,
        override_signals={"sudden_lp_removal_detected": True}
    )

    assert lp_removal_report.sudden_lp_removal_detected is True
    assert lp_removal_report.block_execution is True
    assert lp_removal_report.risk_level == "CRITICAL"
    assert lp_removal_report.rug_risk_score >= 95.0
    assert any("LP Removal" in r for r in lp_removal_report.execution_blocking_reasons)

    # 3. Developer Dump Event -> Immediate Execution Block
    dev_dump_report = rug_detector.evaluate_rug_risk(
        token_address=token_addr,
        chain="ethereum",
        scan_result=scan_res,
        ownership_eval=ownership_res,
        honeypot_res=honeypot_res,
        lp_details=lp_details,
        concentration=concentration,
        override_signals={"developer_sell_detected": True}
    )

    assert dev_dump_report.developer_sell_detected is True
    assert dev_dump_report.block_execution is True
    assert dev_dump_report.risk_level == "CRITICAL"


def test_section_seven_unified_orchestrator(section_seven_engine):
    """Tests the unified orchestrator running end-to-end security assessment."""
    token_addr = "0x6666777788889999000011112222333344445555"

    assessment = section_seven_engine.run_comprehensive_security_assessment(
        token_address=token_addr,
        chain="ethereum",
        bytecode="0x6080604052",
        source_code="contract SafeToken { string public name = 'SafeToken'; }",
        metadata={
            "owner_address": "0x0000000000000000000000000000000000000000",
            "privileged_roles": {},
            "buy_tax": 2.0,
            "sell_tax": 2.0,
            "is_verified": True
        },
        lp_details=LPLockDetails(is_lp_locked=True, lock_percentage=100.0),
        concentration=HolderConcentration(top10_percentage=15.0, dev_wallet_percentage=2.0)
    )

    assert isinstance(assessment, ComprehensiveSecurityAssessment)
    assert assessment.token_address == token_addr
    assert assessment.contract_scan is not None
    assert assessment.ownership_eval is not None
    assert assessment.honeypot_res is not None
    assert assessment.rug_report is not None
    assert assessment.is_safe_for_trading is True
    assert "Risk Level: LOW" in assessment.summary
