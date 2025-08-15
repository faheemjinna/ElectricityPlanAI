def buildFormulaString(baseCharge, tiers):
    formula = f"{baseCharge}"
    for tier in tiers:
        rate = f"{float(tier['rate']):.3f}"
        if tier['max'] is not None:
            formula += f" + min(max(usage - {tier['min'] - 1}, 0), {tier['max'] - tier['min'] + 1}) * {rate}"
        else:
            formula += f" + max(usage - {tier['min'] - 1}, 0) * {rate}"
    
    # Wrap the base formula and apply TXU taxes and PUC fee
    # Sales tax 8.25% + MGRT 1.997% (example for a big city), PUC fee $0.50
    taxed_formula = f"(({formula}) / 100) * (1 + 0.0825 + 0.01997) + 0.50"
    
    return taxed_formula


def evaluateFormula(usageInputArray, baseCharge, formula_str):
    localVariables = {'usage': usageInputArray, 'base': baseCharge*100, 'min': min, 'max': max}
    return round(eval(formula_str, {}, localVariables), 2)
