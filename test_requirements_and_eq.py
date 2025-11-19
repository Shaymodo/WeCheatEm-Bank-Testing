import pytest

# =========================================================
#                 SHARED HELPER (DO NOT DUPLICATE)
# =========================================================
import subprocess
def run_bank_with_inputs(inputs: list[str]) -> str:
    proc = subprocess.Popen(
        ["java", "-jar", "WeCheatEmBank.jar"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    for line in inputs:
        proc.stdin.write(line + "\n")
    proc.stdin.close()
    output = proc.stdout.read()
    proc.wait()
    return output


# =========================================================
#        SAVINGS APR TESTS (BLACK-BOX, INDIRECT)
# =========================================================
def test_savings_interest_correct_for_12_percent_loan_rate():
    """
    INDIRECT TEST:
    Savings APR should equal loanAPR/4.
    Loan APR = 12% → Savings APR = 3% → monthly = 0.25%.
    1500 deposit should grow to 1503.75 after one month.
    """
    out = run_bank_with_inputs([
        "12.0",
        "1", "Alice",       # create customer
        "2", "1000", "1500",# deposit to savings
        "6",                # advance month
        "7",                # print statements
        "0"                 # exit
    ])

    assert "Savings balance: $1503.75" in out

def test_savings_interest_correct_for_6_percent_loan_rate():
    out = run_bank_with_inputs([
        "6.0",
        "1", "Bob",
        "2", "1000", "2000",
        "6",
        "7",
        "0"
    ])

    assert "Savings balance: $2002.50" in out

def test_savings_interest_correct_for_18_percent_loan_rate():
    out = run_bank_with_inputs([
        "18.0",
        "1", "Carol",
        "2", "1000", "1000",
        "6",
        "7",
        "0"
    ])

    assert "Savings balance: $1003.75" in out


# =========================================================
#        MONTHLY PROCESSING: INTEREST + STATEMENTS
# =========================================================

def test_monthly_processing_loan_interest_and_statement():
    """
    TRUE TEST — Requirement #5 (Monthly Processing)
    Verifies that:
      • Monthly interest is applied to loans
      • Statement is generated
      • Statement contains correct fields and activity
    """
    out = run_bank_with_inputs([
        "12",             # Loan APR
        "1", "Dan",       # Create customer
        "4", "1000", "10000",  # Create loan for $10,000
        "6",              # Advance month
        "7",              # Print statements
        "0"               # Exit
    ])

    assert "--- Month 2 Statements ---" in out
    assert "Customer: Dan (Account #1000)" in out
    assert "Savings balance: $0.00" in out
    assert "Loan #1 balance: $10100.00" in out       # interest applied: 1%
    assert "Minimum payment due: $201.00" in out
    assert "Recent Activity:" in out
    assert "Opened loan #1 for $10000.00" in out

def test_monthly_processing_statement_missing_required_fields_would_fail():
    # chatGuPTa told me to include this one but im not sure if it's necessary
    """
    FALSE TEST — Requirement #5 (Monthly Processing)

    This test documents what WOULD constitute a failure if the program
    ever produced an incorrect statement. This cannot be triggered
    intentionally because the provided program does not allow invalid
    internal states.

    Requirements violations include:
      • Interest NOT applied
      • Missing 'Recent Activity'
      • Missing loan balance or minimum payment
      • Missing '-- Month X Statements --' header
      • Ending balance not updated
    """
    out = run_bank_with_inputs([
        "12",
        "1", "TestUser",
        "4", "1000", "8000",
        "6",
        "7",
        "0",
    ])

    # These are the things that MUST be present.
    # If any are missing, the requirement fails.
    required_fields = [
        "-- Month",   # statement header
        "Savings balance:",
        "Loan #1 balance:",
        "Minimum payment due:",
        "Recent Activity:",
    ]

    for field in required_fields:
        assert field in out, f"Missing required field in statement: {field}"


# =========================================================
#                 INITIATE LOAN — EQ / BV
# =========================================================
def test_loan_limit_3_at_boundary():
    out = run_bank_with_inputs([
        "12",
        "1", "Brad",
        "4", "1000", "5000",
        "4", "1000", "5000",
        "4", "1000", "5000",
        "0"
    ])
    assert "Created loan ID #1" in out
    assert "Created loan ID #2" in out
    assert "Created loan ID #3" in out
    assert "You already have 3 loans!" not in out

def test_loan_limit_3_within_range():
    out = run_bank_with_inputs([
        "12",
        "1", "Brad",
        "4", "1000", "5000",
        "4", "1000", "5000",
        "0"
    ])
    assert "Created loan ID #1" in out
    assert "Created loan ID #2" in out
    assert "You already have 3 loans!" not in out

def test_loan_limit_3_above_range():
    out = run_bank_with_inputs([
        "12",
        "1", "Brad",
        "4", "1000", "5000",
        "4", "1000", "5000",
        "4", "1000", "5000",
        "4", "1000", "5000",
        "0"
    ])
    # print(out)
    assert "Created loan ID #1" in out
    assert "Created loan ID #2" in out
    assert "Created loan ID #3" in out
    assert "You already have 3 loans!" in out

def test_loan_amount_below_minimum():
    """
    BV TEST — Loan amount below minimum (499)
    Expected behavior: program prints the re-prompt
      'Enter a value between 500.0 and 50000.0:'
    """
    out = run_bank_with_inputs([
        "12",               # valid APR
        "1", "Dan",         # create customer
        "4", "1000",        # initiate loan
        "499",              # invalid amount
        "500",              # valid after reprompt
        "0"                 # exit
    ])

    assert "Enter a value between 500.0 and 50000.0:" in out
    assert "Created loan ID #1" in out


def test_loan_amount_above_maximum():
    """
    BV TEST — Loan amount above maximum (50001)
    Expected behavior: program prints the same re-prompt.
    """
    out = run_bank_with_inputs([
        "12",
        "1", "Bill",
        "4", "1000",
        "50001",           # invalid
        "49999",           # valid retry
        "0"
    ])

    assert "Enter a value between 500.0 and 50000.0:" in out
    assert "Created loan ID #1" in out


def test_loan_amount_valid_in_range():
    """
    EQ TEST — Loan amount within valid range (5000)
    Should create loan without showing the error prompt.
    """
    out = run_bank_with_inputs([
        "12",
        "1", "Alice",
        "4", "1000",
        "5000",
        "0"
    ])

    assert "Created loan ID #1" in out
    assert "Enter a value between 500.0 and 50000.0:" not in out

@pytest.mark.xfail(reason="Program does not enforce requirement: APR must be divisible by 0.25%")
def test_interest_rate_invalid_increment_should_fail_requirement():
    """
    REQUIREMENT TEST: APR must be divisible by 0.25%.
    Example of invalid APR: 6.3%

    Expected behavior from requirements: REJECT invalid APR.
    Actual program behavior: ACCEPTS it.

    This test is intentionally xfail because the system violates this requirement.
    """
    out = run_bank_with_inputs([
        "6.3",
        "0"   # exit
    ])

    # Requirement says menu should NOT appear for invalid APR.
    assert "--- Main Menu ---" not in out

def test_loan_interest_range_below():
    out = run_bank_with_inputs([
        "5.75"
    ])
    assert "Enter a value between 6.0 and 18.0:" in out

def test_loan_interest_range_above():
    out = run_bank_with_inputs([
        "18.25"
    ])
    assert "Enter a value between 6.0 and 18.0:" in out

def test_loan_interest_range_within():
    out = run_bank_with_inputs([
        "12.25"
    ])
    assert "Enter a value between 6.0 and 18.0:" not in out
    assert "Main Menu" in out


# =========================================================
#                 MAKE LOAN PAYMENT TESTS
# =========================================================

def test_make_payment_within_balance():
    """
    Boundary Value — valid case:
    Payment > 0 and <= balance should be accepted.
    """
    out = run_bank_with_inputs([
        "10",                 # loan APR
        "1", "Dan",           # create customer #1000
        "4", "1000", "500",   # loan 500
        "5", "1000", "1", "11",  # pay 11 (valid)
        "7",
        "0"
    ])

    assert "Paid $11.00 on loan #1" in out


@pytest.mark.xfail(reason="Program incorrectly accepts payment of $0. Requirement says payment must be > 0.")
def test_make_payment_zero_amount_should_fail():
    """
    Boundary Value — below range:
    Payment = 0 should be rejected (but program incorrectly accepts it).
    """
    out = run_bank_with_inputs([
        "10",
        "1", "Lily",
        "4", "1000", "1000",    # loan 1000
        "5", "1000", "1", "0",  # invalid: 0 payment
        "7",
        "0"
    ])

    assert "Paid $0.00 on loan #1" not in out   # will xfail


@pytest.mark.xfail(reason="Program allows overpayment > balance and closes loan early. Should be rejected.")
def test_make_payment_above_balance_should_fail():
    """
    Boundary Value — above range:
    Payment > balance should be rejected (but program accepts it).
    """
    out = run_bank_with_inputs([
        "10",
        "1", "Lily",
        "4", "1000", "1000",  # loan 1000
        "6",                  # advance month so balance increases
        "5", "1000", "1", "1009",  # invalid: overpay
        "7",
        "0"
    ])

    assert "Loan #1 closed." not in out   # will xfail

def test_payment_selection_validity_false_customer():
    out = run_bank_with_inputs([
        "10",
        "5", "1000" # should fail - no customers
    ])
    assert "No such customer." in out

@pytest.mark.xfail(reason="Program incorrectly asks for loan ID and payment amount after declaring there are no active loans.")
def test_payment_selection_validity_false_load_number():
    out = run_bank_with_inputs([
        "10",
        "1", "Brad",
        "5", "1000", "1", "100" # should fail- no active loans
    ])
    assert "No active loans." in out
    assert "Loan ID to pay:" not in out
    assert "Payment amount:" not in out
    assert "Loan not found." in out 


# =========================================================
#                 SAVINGS DEPOSIT TESTS
# =========================================================

def test_savings_deposit_positive_amount_updates_balance():
    """
    Boundary Value — valid case:
    Deposit > 0 should increase savings balance.
    """
    out = run_bank_with_inputs([
        "12",
        "1", "Dan",
        "2", "1000", "1565",
        "7",
        "0"
    ])

    assert "Savings balance: $1565.00" in out
    assert "Deposited $1565.00" in out


@pytest.mark.xfail(reason="Program incorrectly accepts a deposit of $0. Requirement says deposit must be > 0.")
def test_savings_deposit_zero_amount_should_fail_requirement():
    """
    Boundary Value — below range:
    Deposit = 0 should be rejected (but program accepts it).
    """
    out = run_bank_with_inputs([
        "12",
        "1", "Dan",
        "2", "1000", "0",
        "7",
        "0"
    ])

    assert "Deposited $0.00" not in out  # will xfail

# =========================================================
#                 SAVINGS WITHDRAW TESTS
# =========================================================

def test_savings_withdraw_positive_amount_above_balance():
    out = run_bank_with_inputs([
        "12",
        "1", "Brad",
        "2", "1000", "5000",
        "3", "1000", "6000",
        "7",
        "0"
    ])
    assert "Failed withdrawal" in out

def test_savings_withdraw_positive_amount_below_balance():
    out = run_bank_with_inputs([
        "12",
        "1", "Brad",
        "2", "1000", "5000",
        "3", "1000", "600",
        "7",
        "0"
    ])
    assert "Failed withdrawal" not in out
    assert "Withdrew $600.00" in out

def test_savings_withdraw_negative_amount_from_balance():
    out = run_bank_with_inputs([
        "12",
        "1", "Brad",
        "2", "1000", "1565",
        "3", "1000", "-100", 
        "7",
        "0"
    ])
    assert "Enter a value between 0.0 and 1.7976931348623157E308:" in out

# =========================================================
#                 MENU RANGE TESTS
# =========================================================

def test_menu_selection_below_range_reprompts():
    """
    Boundary Value — below range:
    Selecting -1 should trigger the out-of-range prompt.
    """
    out = run_bank_with_inputs([
        "12",
        "-1",  # invalid
        "0"    # exit after reprompt
    ])

    assert "Enter a number between 0 and 7:" in out


def test_menu_selection_above_range_reprompts():
    """
    Boundary Value — above range:
    Selecting 8 should trigger the same prompt.
    """
    out = run_bank_with_inputs([
        "12",
        "8",   # invalid
        "0"    # exit
    ])

    assert "Enter a number between 0 and 7:" in out


def test_menu_selection_valid_option_5_processes_payment_flow():
    """
    Boundary Value — in range:
    Selecting option 5 should immediately go to the payment workflow (no reprompt)
    and successfully apply the payment when prerequisites are satisfied.
    """
    out = run_bank_with_inputs([
        "12",
        "1", "Dan",              # create customer
        "4", "1000", "5000",     # create loan
        "5", "1000", "1", "100", # choose menu option 5 and pay
        "7",                     # print statements to confirm payment
        "0"
    ])

    assert "Loan ID to pay:" in out
    assert "Paid $100.00 on loan #1" in out


# =========================================================
#                 REQUIREMENT TESTS
# =========================================================

def test_setting_interest_rate_at_startup_true_input():
    out = run_bank_with_inputs([
        "12",
        "0"
    ])
    assert "Enter loan annual interest rate" in out
    assert "Main Menu" in out 

def test_setting_interest_rate_at_startup_false_input():
    out = run_bank_with_inputs([
        "",
        ""
    ])
    assert "Enter loan annual interest rate" in out
    assert "Main Menu" not in out 

def test_advance_next_month_true_input():
    out = run_bank_with_inputs([
        "12",
        "6",
        "0"
    ])
    assert "Advancing to next month..." in out

def test_advance_next_month_false_input():
    out = run_bank_with_inputs([
        "12", # interest rate
        "1", "Brad", # testing main menu option 1
        "2", "1000", "100", # testing main menu option 2
        "3", "1000", "2" # testing main menu option 3
        "4", "1000", "5000",     # testing main menu option 4
        "5", "1000", "1", "100", # testing main menu option 5
        "7",                     # testing main menu option 7
        "0" # testing main menu option 0
    ])
    assert "Advancing to next month..." not in out

def test_rounding_cent_up():
    out = run_bank_with_inputs([
        "12", # interest rate
        "1", "Brad", 
        "2", "1000", "99.996", 
        "7", 
        "0"
    ])
    assert "Deposited $100.00" in out

def test_rounding_cent_down():
    out = run_bank_with_inputs([
        "12", # interest rate
        "1", "Brad", 
        "2", "1000", "99.994", 
        "7", 
        "0"
    ])
    assert "Deposited $99.99" in out
    
