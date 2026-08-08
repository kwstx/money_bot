from src.intelligence.probability.schemas import ExpectedValueConfig, ExpectedValueResult

class ExpectedValueCalculator:
    """
    Calculates expected value incorporating probability, payoff, downside, liquidity, 
    execution costs, and time horizon.
    """
    
    def calculate(self, config: ExpectedValueConfig) -> ExpectedValueResult:
        # Check for extreme tail outcomes
        is_rare_tail = config.target_multiple > 50.0
        
        # Adjust probabilities if rare tail - market tends to overestimate these
        effective_prob = config.probability_of_target
        if is_rare_tail:
            # Discount the probability heavily for extreme tail events
            effective_prob = effective_prob * 0.1
            
        # Calculate gross upside and downside
        gross_upside = config.position_size * config.target_multiple
        gross_downside = config.position_size * config.downside_loss_pct
        
        # Calculate execution costs
        execution_cost = (gross_upside * config.execution_cost_pct) + (config.position_size * config.execution_cost_pct)
        
        # Calculate liquidity penalty (slippage beyond standard fees)
        # If position size is large relative to liquidity, penalty increases non-linearly
        liquidity_ratio = config.position_size / max(1.0, config.liquidity_available)
        liquidity_penalty = 0.0
        if liquidity_ratio > 0.01: # position is > 1% of liquidity
            # Penalty scales up quickly
            liquidity_penalty = gross_upside * (liquidity_ratio * 2.0)
            
        # Net upside
        net_upside = gross_upside - execution_cost - liquidity_penalty - config.position_size
        
        # EV = (Prob * Upside) - (DownsideProb * Downside)
        expected_value_usd = (effective_prob * net_upside) - (config.downside_probability * gross_downside)
        
        expected_value_pct = expected_value_usd / config.position_size
        
        warning = None
        if expected_value_pct > 10.0 and config.time_horizon_days < 30:
            warning = (
                "WARNING: Implied probability guarantee detected. Turning a small account into a "
                "much larger account within a short timeframe is statistically highly improbable. "
                "These targets should be treated as rare-tail scenarios, not baseline expectations."
            )
            
        return ExpectedValueResult(
            expected_value_usd=expected_value_usd,
            expected_value_pct=expected_value_pct,
            is_rare_tail=is_rare_tail,
            liquidity_penalty=liquidity_penalty,
            execution_cost=execution_cost,
            implied_guarantee_warning=warning
        )
