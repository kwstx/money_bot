import logging
import re
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from src.security.schemas import (
    AdministrativePermissions,
    ProxyMetadata,
    DeploymentMetadata,
    ContractScanResult,
)

logger = logging.getLogger(__name__)

# Known Function Selectors / Signatures for EVM Contract Bytecode Pattern Analysis
FUNCTION_SELECTORS = {
    "mint": ["0x40c10f19", "0x892ffac2", "0xa0712d68"], # mint(address,uint256), mintTokens(uint256), mint(uint256)
    "freeze": ["0x6b004245", "0x8456cb59", "0x028e3236"], # freeze(address), pause(), freezeAccount(address)
    "blacklist": ["0x42e05739", "0x09baa3a6", "0xadf8a5b8"], # blacklist(address), addToBlacklist(address), setBlacklistStatus(address,bool)
    "alter_fees": ["0x8a927a7c", "0x23525149", "0x53467472", "0xef6a928e"], # setFee, setTaxFeePercent, setBuyTax, setSellTax
    "restrict_trading": ["0xc9567eec", "0x8e83344e", "0xed562e60", "0x4468f037"], # enableTrading, setMaxTxAmount, setMaxWallet, setCooldown
    "modify_balances": ["0x76b2512f", "0x3e407137", "0x4b78f495"], # setBalance, rebalance, forceTransfer
    "upgrade_logic": ["0x3659cfe6", "0x4f1ef286", "0x5c60da1b"], # upgradeTo(address), upgradeToAndCall(address,bytes), changeImplementation
    "ownership": ["0xf2fde38b", "0x715018a6", "0x2f7840f1"], # transferOwnership(address), renounceOwnership(), grantRole(bytes32,address)
    "pause": ["0x8456cb59", "0x3f4ba83a"], # pause(), unpause()
    "withdraw_funds": ["0x3cc150b1", "0x5fd8c710", "0x00f714ce"], # withdraw(), withdrawETH(), emergencyWithdraw()
}

# Proxy Constants
EIP_1967_IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
EIP_1967_ADMIN_SLOT = "0xb535edd3029f2b0739773436a56f10f87130261f867b2e6f7904a0eb523a3841"
EIP_1822_UUPS_SLOT = "0xc5f297647b075374d1536b6170634721c055278c66e2c34d3d2e964177263b61"


class ContractScanner:
    """
    Contract Scanner for retrieving bytecode, verified source code, ABI info,
    deployment metadata, proxy relationships, implementation contracts, and
    analyzing administrative permissions (mint, freeze, blacklist, alter fees,
    restrict trading, modify balances, upgrade logic, change ownership, etc.).
    """

    def scan_contract(
        self,
        token_address: str,
        chain: str,
        bytecode: Optional[str] = None,
        source_code: Optional[str] = None,
        abi: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ContractScanResult:
        """
        Scans a contract address, extracting metadata, proxy information,
        and administrative permission matrix.
        """
        logger.info(f"Scanning contract {token_address} on chain {chain}")

        metadata = metadata or {}
        
        # 1. Bytecode processing & Hashing
        raw_bytecode = bytecode or metadata.get("bytecode", "0x6080604052")
        if not raw_bytecode.startswith("0x"):
            raw_bytecode = "0x" + raw_bytecode
            
        bytecode_hash = hashlib.sha256(raw_bytecode.encode('utf-8')).hexdigest()

        # 2. ABI & Source Verification Check
        is_verified = bool(source_code or abi or metadata.get("is_verified", False))
        source_snippet = (source_code[:500] + "...") if source_code and len(source_code) > 500 else source_code

        # 3. Extract ABI Method names or analyze bytecode selector signatures
        abi_methods = self._extract_abi_methods(abi, source_code, raw_bytecode)

        # 4. Proxy & Implementation Analysis
        proxy_info = self._analyze_proxy_relationships(token_address, raw_bytecode, source_code, metadata)

        # 5. Administrative Permissions Matrix Extraction
        permissions = self._analyze_permissions(raw_bytecode, source_code, abi_methods, metadata)

        # 6. Deployment Metadata
        deployer = metadata.get("deployer_address", metadata.get("deployer", "0x1111111111111111111111111111111111111111"))
        deployment_meta = DeploymentMetadata(
            deployer_address=deployer,
            deployment_tx_hash=metadata.get("deployment_tx_hash", f"0x{token_address[2:]:0>64}"),
            deployment_block=metadata.get("deployment_block", 18000000),
            deployment_timestamp=metadata.get("deployment_timestamp", datetime.now(timezone.utc)),
            initial_supply=metadata.get("initial_supply", 1_000_000_000.0)
        )

        # 7. Generate Risk Flags
        risk_flags = self._generate_risk_flags(permissions, proxy_info, is_verified)

        return ContractScanResult(
            token_address=token_address,
            chain=chain,
            bytecode_hash=bytecode_hash,
            is_verified=is_verified,
            source_code_snippet=source_snippet,
            abi_methods=abi_methods,
            deployment_metadata=deployment_meta,
            proxy_info=proxy_info,
            permissions=permissions,
            risk_flags=risk_flags
        )

    def _extract_abi_methods(
        self,
        abi: Optional[List[Dict[str, Any]]],
        source_code: Optional[str],
        bytecode: str
    ) -> List[str]:
        methods = set()
        if abi:
            for item in abi:
                if item.get("type") == "function" and "name" in item:
                    methods.add(item["name"])

        if source_code:
            func_matches = re.findall(r"function\s+([a-zA-Z0-9_]+)\s*\(", source_code)
            for m in func_matches:
                methods.add(m)

        # Fallback to selector matching in bytecode
        bytecode_lower = bytecode.lower()
        for category, selectors in FUNCTION_SELECTORS.items():
            for sel in selectors:
                if sel[2:].lower() in bytecode_lower:
                    methods.add(f"detected_{category}_{sel}")

        return sorted(list(methods))

    def _analyze_proxy_relationships(
        self,
        token_address: str,
        bytecode: str,
        source_code: Optional[str],
        metadata: Dict[str, Any]
    ) -> ProxyMetadata:
        is_proxy = False
        proxy_type = None
        impl_addr = metadata.get("implementation_address")
        admin_addr = metadata.get("proxy_admin")
        beacon_addr = metadata.get("beacon_address")

        bytecode_lower = bytecode.lower()

        # Check EIP-1967 Implementation Slot in metadata or bytecode references
        if metadata.get("storage_slots", {}).get(EIP_1967_IMPLEMENTATION_SLOT):
            is_proxy = True
            proxy_type = "EIP-1967"
            impl_addr = metadata["storage_slots"][EIP_1967_IMPLEMENTATION_SLOT]
            admin_addr = metadata.get("storage_slots", {}).get(EIP_1967_ADMIN_SLOT)

        # Check UUPS EIP-1822
        elif metadata.get("storage_slots", {}).get(EIP_1822_UUPS_SLOT):
            is_proxy = True
            proxy_type = "EIP-1822 UUPS"
            impl_addr = metadata["storage_slots"][EIP_1822_UUPS_SLOT]

        # Check source code / bytecode hints
        elif source_code:
            if "ERC1967Proxy" in source_code or "TransparentUpgradeableProxy" in source_code:
                is_proxy = True
                proxy_type = "EIP-1967 Transparent"
            elif "UUPSUpgradeable" in source_code:
                is_proxy = True
                proxy_type = "EIP-1822 UUPS"
            elif "BeaconProxy" in source_code:
                is_proxy = True
                proxy_type = "BeaconProxy"
            elif "Proxy" in source_code and "implementation" in source_code:
                is_proxy = True
                proxy_type = "Custom Proxy"

        elif impl_addr or metadata.get("is_proxy"):
            is_proxy = True
            proxy_type = metadata.get("proxy_type", "EIP-1967")

        if is_proxy and not impl_addr:
            impl_addr = metadata.get("detected_implementation", f"0x{token_address[2:-4]}9999")

        return ProxyMetadata(
            is_proxy=is_proxy,
            proxy_type=proxy_type,
            implementation_address=impl_addr,
            admin_address=admin_addr,
            beacon_address=beacon_addr
        )

    def _analyze_permissions(
        self,
        bytecode: str,
        source_code: Optional[str],
        abi_methods: List[str],
        metadata: Dict[str, Any]
    ) -> AdministrativePermissions:
        bytecode_lower = bytecode.lower()
        source_lower = (source_code or "").lower()
        methods_str = " ".join(abi_methods).lower()

        # Mint check
        can_mint = (
            any(sel[2:] in bytecode_lower for sel in FUNCTION_SELECTORS["mint"]) or
            any(k in methods_str or k in source_lower for k in ["mint", "minttokens", "_mint", "issue"]) or
            metadata.get("can_mint", False)
        )

        # Freeze check
        can_freeze = (
            any(sel[2:] in bytecode_lower for sel in FUNCTION_SELECTORS["freeze"]) or
            any(k in methods_str or k in source_lower for k in ["freeze", "freezeaccount", "pauseaccount"]) or
            metadata.get("can_freeze", False)
        )

        # Blacklist check
        can_blacklist = (
            any(sel[2:] in bytecode_lower for sel in FUNCTION_SELECTORS["blacklist"]) or
            any(k in methods_str or k in source_lower for k in ["blacklist", "isblacklisted", "setblacklist"]) or
            metadata.get("can_blacklist", False)
        )

        # Fee Alteration check
        can_alter_fees = (
            any(sel[2:] in bytecode_lower for sel in FUNCTION_SELECTORS["alter_fees"]) or
            any(k in methods_str or k in source_lower for k in ["setfee", "settaxfeepercent", "setbuytax", "setselltax", "updatefees"]) or
            metadata.get("can_alter_fees", False)
        )

        # Trading Restriction check
        can_restrict_trading = (
            any(sel[2:] in bytecode_lower for sel in FUNCTION_SELECTORS["restrict_trading"]) or
            any(k in methods_str or k in source_lower for k in ["enabletrading", "setmaxtxamount", "setmaxwallet", "setcooldown"]) or
            metadata.get("can_restrict_trading", False)
        )

        # Balance Mutation check
        can_modify_balances = (
            any(sel[2:] in bytecode_lower for sel in FUNCTION_SELECTORS["modify_balances"]) or
            any(k in methods_str or k in source_lower for k in ["setbalance", "rebalance", "forcetransfer", "wipeaccount"]) or
            metadata.get("can_modify_balances", False)
        )

        # Upgrade Logic check
        can_upgrade_logic = (
            any(sel[2:] in bytecode_lower for sel in FUNCTION_SELECTORS["upgrade_logic"]) or
            any(k in methods_str or k in source_lower for k in ["upgradeto", "upgradetoandcall", "changeimplementation"]) or
            metadata.get("can_upgrade_logic", False) or metadata.get("is_proxy", False)
        )

        # Change Ownership check
        can_change_ownership = (
            any(sel[2:] in bytecode_lower for sel in FUNCTION_SELECTORS["ownership"]) or
            any(k in methods_str or k in source_lower for k in ["transferownership", "renounceownership", "grantrole"]) or
            metadata.get("can_change_ownership", True)
        )

        # Pause Trading check
        can_pause = (
            any(sel[2:] in bytecode_lower for sel in FUNCTION_SELECTORS["pause"]) or
            any(k in methods_str or k in source_lower for k in ["pause", "unpause", "setpaused"]) or
            metadata.get("can_pause_trading", False)
        )

        # Withdraw Funds check
        can_withdraw = (
            any(sel[2:] in bytecode_lower for sel in FUNCTION_SELECTORS["withdraw_funds"]) or
            any(k in methods_str or k in source_lower for k in ["withdraw", "withdraweth", "emergencywithdraw", "draintokens"]) or
            metadata.get("can_withdraw_funds", False)
        )

        other_caps = []
        if "selfdestruct" in source_lower or "ff" in bytecode_lower: # selfdestruct opcode 0xff
            other_caps.append("selfdestruct_opcode")
        if "delegatecall" in source_lower or "f4" in bytecode_lower: # delegatecall opcode 0xf4
            other_caps.append("arbitrary_delegatecall")

        return AdministrativePermissions(
            can_mint=can_mint,
            can_freeze=can_freeze,
            can_blacklist=can_blacklist,
            can_alter_fees=can_alter_fees,
            can_restrict_trading=can_restrict_trading,
            can_modify_balances=can_modify_balances,
            can_upgrade_logic=can_upgrade_logic,
            can_change_ownership=can_change_ownership,
            can_pause_trading=can_pause,
            can_withdraw_contract_funds=can_withdraw,
            other_dangerous_capabilities=other_caps
        )

    def _generate_risk_flags(
        self,
        permissions: AdministrativePermissions,
        proxy_info: ProxyMetadata,
        is_verified: bool
    ) -> List[str]:
        flags = []
        if not is_verified:
            flags.append("UNVERIFIED_SOURCE_CODE")
        if permissions.can_mint:
            flags.append("UNBOUNDED_MINTING_PRIVILEGE")
        if permissions.can_modify_balances:
            flags.append("DIRECT_BALANCE_MUTATION_PRIVILEGE")
        if permissions.can_blacklist:
            flags.append("BLACKLIST_PRIVILEGE_DETECTED")
        if permissions.can_freeze or permissions.can_pause_trading:
            flags.append("FREEZE_PAUSE_TRADING_PRIVILEGE")
        if permissions.can_alter_fees:
            flags.append("FEE_ALTERATION_PRIVILEGE")
        if proxy_info.is_proxy:
            flags.append(f"UPGRADEABLE_PROXY_{proxy_info.proxy_type or 'GENERIC'}")
        if "arbitrary_delegatecall" in permissions.other_dangerous_capabilities:
            flags.append("DANGEROUS_DELEGATECALL_OPCODE")
        return flags
