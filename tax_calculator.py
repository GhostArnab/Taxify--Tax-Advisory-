def calculate_tax_old(data):
    # Extract values
    gross = float(data.get('gross_salary', 0))
    basic = float(data.get('basic_salary', 0))
    hra = float(data.get('hra_received', 0))
    rent = float(data.get('rent_paid', 0))
    ded_80c = float(data.get('deduction_80c', 0))
    ded_80d = float(data.get('deduction_80d', 0))
    std_ded = float(data.get('standard_deduction', 0))
    
    # Apply default standard deduction if missing
    if std_ded == 0:
        std_ded = 50000
        
    prof_tax = float(data.get('professional_tax', 0))

    # HRA exemption (simplified)
    hra_exempt = 0
    if rent > 0.1 * basic and hra > 0 and basic > 0:
        hra_exempt = min(hra, 0.5 * basic, rent - 0.1 * basic)

    total_deductions = std_ded + prof_tax + ded_80c + ded_80d + hra_exempt
    taxable_income = max(gross - total_deductions, 0)

    # Tax Rebate u/s 87A: Income up to 5L is tax-free in Old Regime
    if taxable_income <= 500000:
        return 0.0

    # Old regime slabs
    tax = 0
    if taxable_income > 250000:
        if taxable_income <= 500000:
            tax = 0.05 * (taxable_income - 250000)
        elif taxable_income <= 1000000:
            tax = 0.05 * 250000 + 0.2 * (taxable_income - 500000)
        else:
            tax = 0.05 * 250000 + 0.2 * 500000 + 0.3 * (taxable_income - 1000000)
            
    # 4% cess
    tax = tax * 1.04
    return round(tax, 2)

def calculate_tax_new(data):
    gross = float(data.get('gross_salary', 0))
    std_ded = float(data.get('standard_deduction', 0))
    
    # FY 2025-26 standard deduction under new regime is 75,000
    if std_ded == 0:
        std_ded = 75000
        
    taxable_income = max(gross - std_ded, 0)
    
    # Tax Rebate u/s 87A: Income up to 12L is tax-free in New Regime (FY 2025-26)
    if taxable_income <= 1200000:
        return 0.0

    # New regime slabs (FY 2025-26)
    tax = 0
    slabs = [
        (400000, 0.0),
        (800000, 0.05),
        (1200000, 0.10),
        (1600000, 0.15),
        (2000000, 0.20),
        (2400000, 0.25),
        (float('inf'), 0.30)
    ]
    prev = 0
    for limit, rate in slabs:
        if taxable_income > limit:
            tax += (limit - prev) * rate
            prev = limit
        else:
            tax += (taxable_income - prev) * rate
            break
            
    # 4% cess
    tax = tax * 1.04
    return round(tax, 2)