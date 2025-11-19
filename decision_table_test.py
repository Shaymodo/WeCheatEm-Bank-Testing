import subprocess
import pytest
import csv
import re
from pathlib import Path

# --- Configuration ---
JAR_PATH = "WeCheatEmBank.jar"              # Path to the Java program JAR file
JAVA_COMMAND = ["java", "-jar", JAR_PATH]
LOAN_RATE = "12" # Annual interest rate used in the CSV test cases (1% monthly)
CUSTOMER_ACCOUNT_NUMBER = "1000"

def load_decision_table(file_path="decision_table_cases.csv"):
    """Loads test cases from the decision table CSV file."""
    csv_path = Path(__file__).parent / file_path
    test_cases = []
    
    with open(csv_path, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        # Skip the header row
        next(reader, None) 
        
        for row in reader:
            (rule, c1_past_delin, c2_min_over_10, c3_actual_meets,
            loan_amount, input_pay_amount, expected_min, expected_late_fee) = row
            
            test_cases.append((
                rule, c1_past_delin, c2_min_over_10, c3_actual_meets,
                float(loan_amount), float(input_pay_amount), float(expected_min), expected_late_fee
            ))

            
    return test_cases

# --- Pytest Parameterization ---
TEST_CASES = load_decision_table()
@pytest.mark.parametrize(
    "rule,c1_min_over_10,c2_past_delin,c3_actual_meets,loan_amount,input_pay_amount,expected_min,expected_late_fee",
    TEST_CASES
)
def test_loan_logic_via_decision_table(
    rule, c1_min_over_10, c2_past_delin, c3_actual_meets, loan_amount, input_pay_amount, expected_min, expected_late_fee
):
    """
    Tests the late fee and minimum payment logic based on a decision table rule.
    """
    
    # 1. Base Commands
    customer_name = f"Test_{rule}"
    commands = [
        LOAN_RATE,
        "1", customer_name, # 1. Create new customer
        "4", CUSTOMER_ACCOUNT_NUMBER, str(loan_amount), # 4. Initiate loan
    ]
    
    # --- 2. Phase 1: Setup for Delinquency (C2: Yes cases: R1, R2, R4, R6) ---
    if c2_past_delin == 'Y':
        # To make a loan delinquent, we skip the payment step, resulting in a $0.00 payment
        # (which misses the minimum), then advance the month.
        
        commands.extend([
            # Note: Payment is skipped here (implicitly $0.00)
            "6", # Advance to next month (Should set C2: Yes/Delinquent status)
            "7"  # Print statement to establish Month 2 initial state
        ])
        
    # --- 3. Phase 2: Execute the Current Month's Test ---
    
    # The payment amount for the actual test month
    commands.extend([
        "5", CUSTOMER_ACCOUNT_NUMBER, "1", str(input_pay_amount), # Make the test payment
        "6", # Advance to next month (Triggers final interest/fee calculation)
        "7", # Print final statement for verification
        "0"  # Exit
    ])
    
    input_str = '\n'.join(commands) + '\n'

    # --- 4. Execute the Java Program ---
    
    try:
        result = subprocess.run(
            JAVA_COMMAND,
            input=input_str,
            capture_output=True,
            text=True,
            timeout=10,
            check=True
        )
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Program exited with error. Stderr: {e.stderr}", pytrace=False)
    except subprocess.TimeoutExpired:
        pytest.fail("Program timed out.", pytrace=False)

    output = result.stdout
    
    # --- 5. Verification: Extract Data ---
    
    # Find all balance and min payment occurrences
    balance_match = re.findall(r"Loan #1 balance: \$([\d,]+\.\d{2})", output)
    min_pay_match = re.findall(r"Minimum payment due: \$([\d,]+\.\d{2})", output)
    
    if not balance_match or not min_pay_match:
        pytest.fail(f"Could not find final loan balance or minimum payment in output. Output:\n{output}", pytrace=False)

    final_balance_str = balance_match[-1].replace(',', '')
    final_min_pay_str = min_pay_match[-1].replace(',', '')
    final_balance = float(final_balance_str)
    
    # --- 6. Assertion Logic: Calculate Expected Balance ---
    
    # Determine the starting balance for the test month (Month 1 for C2:N, Month 2 for C2:Y)
    if c2_past_delin == 'N':
        # Test starts in Month 1: Start balance is the initial loan amount.
        start_balance = loan_amount
    else:
        # Test starts in Month 2: We need the balance *after* the delinquency setup in Month 1.
        # Month 1 action: $0.00 payment made, interest applied, NO LATE FEE (due to bug)
        if len(balance_match) < 2:
             pytest.fail(f"Could not find intermediate balance for C2: Y test setup.", pytrace=False)
             
        # The balance after the first advance (element -2) is the starting balance for the test payment.
        start_balance = float(balance_match[-2].replace(',', ''))
        
        # We must recalculate the expected start balance based on zero payment and interest applied 
        # (this is for robustness, but the extraction above is likely simpler if the program is consistent)
        # Expected Start Balance (Month 2) = Initial Loan + Interest (on initial loan, due to $0 pay)
        # expected_start_balance = round(loan_amount + (loan_amount * 0.01), 2)
        # Use extracted start_balance for flexibility against program's balance calculation method.
        
    # Calculate expected balance WITHOUT the $50 late fee (Base Balance):
    balance_after_pay = start_balance - input_pay_amount
    interest_applied = round(balance_after_pay * 0.01, 2)
    expected_base_final_balance = round(balance_after_pay + interest_applied, 2)
    
    # --- Assertion 1: Late Fee (O2) and Next Delinquent Status (O3) ---
    if expected_late_fee == 'Y':
        # EXPECTED: Late fee added (Base Balance + 50.00)
        expected_final_balance = round(expected_base_final_balance + 50.00, 2)
        assert final_balance == expected_final_balance, (
            f"FAIL: Rule {rule} (EXPECTED LATE FEE). "
            f"Actual final balance {final_balance} != Expected final balance {expected_final_balance} "
            f"(Base: {expected_base_final_balance} + $50.00 Late Fee)."
        )
    else:
        # EXPECTED: No late fee added (Base Balance)
        expected_final_balance = expected_base_final_balance
        assert final_balance == expected_final_balance, (
            f"FAIL: Rule {rule} (EXPECTED NO LATE FEE). "
            f"Actual final balance {final_balance} != Expected final balance {expected_final_balance}."
        )
        
    # --- Assertion 2: Delinquency Penalty on Next Minimum Payment (O1) ---
    
    # The minimum payment expected (expected_min from CSV) includes the $50 penalty if C2='Y' OR if the
    # current test was a failure (expected_late_fee == 'Y').
    
    # The assertion must check if the program's reported min payment matches the CSV expected min.
    assert float(final_min_pay_str) == round(expected_min, 2), (
        f"FAIL: Rule {rule} (MINIMUM PAYMENT CHECK). "
        f"Actual next min payment {final_min_pay_str} != Expected min payment {expected_min}. "
        f"This checks both the base minimum formula and the $50 delinquency penalty."
    )