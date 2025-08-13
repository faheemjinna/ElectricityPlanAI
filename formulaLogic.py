def buildFormulaString(baseCharge, tiers):
    formula = "base"
    for tier in tiers:
        rate = f"{float(tier['rate']):.3f}"  # Convert to float before formatting
        if tier['max'] is not None:
            formula += f" + min(max(usage - {tier['min'] - 1}, 0), {tier['max'] - tier['min'] + 1}) * {rate}"
        else:
            formula += f" + max(usage - {tier['min'] - 1}, 0) * {rate}"
    return f"({formula}) / 100"

def evaluateFormula(usageInputArray, baseCharge, formula_str):
    localVariables = {'usage': usageInputArray, 'base': baseCharge*100, 'min': min, 'max': max}
    return round(eval(formula_str, {}, localVariables), 2)
