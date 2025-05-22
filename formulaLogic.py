def buildFormulaString(baseCharge, tiers):
    formula = "base"
    for tier in tiers:
        rate = f"{tier['rate']:.3f}"  # Format rate to 3 decimal places
        if tier['max'] is not None:
            formula += f" + min(max(usage - {tier['min'] - 1}, 0), {tier['max'] - tier['min'] + 1}) * {rate}"
        else:
            formula += f" + max(usage - {tier['min'] - 1}, 0) * {rate}"
    return f"({formula}) / 100"

def evaluateFormula(usage_kwh, baseCharge, formula_str):
    localVariables = {'usage': usage_kwh, 'base': baseCharge*100, 'min': min, 'max': max}
    return round(eval(formula_str, {}, localVariables), 2)
