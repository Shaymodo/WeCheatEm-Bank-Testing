import subprocess
import pytest

JAR_PATH = "WeCheatEmBank.jar"
JAVA_COMMAND = ["java", "-jar", JAR_PATH]

def run_bank_with_inputs(inputs: list[str]) -> str:
    proc = subprocess.Popen(
        JAVA_COMMAND,
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


class LoanState:
    OPEN = "Open"
    DELINQUENT = "Delinquent"
    CLOSED = "Closed"



def scenario_open_with_new_loan():
    return run_bank_with_inputs([
        "10",          # enter interest rate
        "1",           # create customer
        "Collin",      # customer name
        "4",           # initiate loan
        "1000",        # customer ID
        "1000",        # loan amount
        "7",           # print statements
        "0",           # exit
    ])


def scenario_open_to_delinquent():
    return run_bank_with_inputs([
        "10",            # interest rate
        "1",             # create customer
        "collin",        # name
        "4",             # initiate loan
        "1000",          # account number
        "1000",          # loan amount

        "5",             # make loan payment
        "1000",          # account number
        "1",             # loan ID
        "6",             # underpayment (<18.33)

        "6",             # advance to next month

        "7",             # print statements
        "0",             # exit
    ])



def scenario_delinquent_to_open():
    return run_bank_with_inputs([
        "10",            # interest rate
        "1",             # create customer
        "collin",        # name

        "4",             # initiate loan
        "1000",          # account number
        "1000",          # loan amount

        # ---- DELINQUENCY STEP ----
        "5",             # make loan payment
        "1000",          # account number
        "1",             # loan ID
        "6",             # underpayment (<18.33)

        "6",             # advance month (now Delinquent)

        # ---- PAY FULL DELINQUENT MINIMUM ----
        "5",             # make loan payment
        "1000",          # account number
        "1",             # loan ID
        "18.35",         # full delinquent minimum (min + late fee)

        "6",             # advance month (becomes Open again)

        "7",             # print statements
        "0",             # exit
    ])


def scenario_repeated_delinquent():
    return run_bank_with_inputs([
        "10",            # interest rate

        # Create customer + loan
        "1",             # create customer
        "collin",        # name

        "4",             # initiate loan
        "1000",          # account number
        "1000",          # loan amount

        # ---- 1st underpayment + advance -> "delinquent" month 2 ----
        "5",             # make loan payment
        "1000",          # account number
        "1",             # loan ID
        "6",             # underpayment (< 18.33)

        "6",             # advance to next month

        # ---- 2nd underpayment + advance -> stays "delinquent" month 3 ----
        "5",             # make loan payment
        "1000",          # account number
        "1",             # loan ID
        "6",             # another underpayment

        "6",             # advance to next month

        # ---- 3rd underpayment + advance -> still not paid off ----
        "5",             # make loan payment
        "1000",          # account number
        "1",             # loan ID
        "6",             # another underpayment

        "6",             # advance to next month

        # Final: print statements and exit
        "7",             # print all statements
        "0",             # exit
    ])


def scenario_overpayment_rejected():
    return run_bank_with_inputs([
        "10",            # interest rate
        "1",             # create customer
        "collin",        # name

        "4",             # initiate loan
        "1000",          # account number
        "1000",          # loan amount

        # ---- OVERPAYMENT ATTEMPT ----
        "5",             # make loan payment
        "1000",          # account number
        "1",             # loan ID
        "2000",          # overpayment (> balance 1000)

        # ---- PRINT STATEMENTS ----
        "7",             # print all statements
        "0",             # exit
    ])


def scenario_exact_payoff_from_any_state(start_state):
    """
    Drive loan into the requested state ("Open" or "Delinquent"),
    then pay the exact remaining balance and print statements.
    """
    if start_state == LoanState.OPEN:
        # create a normal loan and pay off the full $1000
        return run_bank_with_inputs([
            "10",          # interest rate
            "1",           # create customer
            "collin",      # name
            "4",           # initiate loan
            "1000",        # account number
            "1000",        # loan amount

            "5",           # make loan payment
            "1000",        # account number
            "1",           # loan ID
            "1000",        # pay exact remaining balance

            "7",           # print statements
            "0",           # exit
        ])

    elif start_state == LoanState.DELINQUENT:
        # 1) Create loan
        # 2) Underpay (6) and advance → balance 1002.28, min 18.35 
        # 3) Pay exact 1002.28
        return run_bank_with_inputs([
            "10",          # interest rate
            "1",           # create customer
            "collin",      # name

            "4",           # initiate loan
            "1000",        # account number
            "1000",        # loan amount

            # ---- Make it Delinquent ----
            "5",           # make loan payment
            "1000",        # account number
            "1",           # loan ID
            "6",           # underpay

            "6",           # advance to next month (delinquent now, balance ~1002.28)

            # ---- Pay off exact remaining balance ----
            "5",           # make loan payment
            "1000",        # account number
            "1",           # loan ID
            "1002.28",     # exact remaining balance from output

            "7",           # print statements
            "0",           # exit
        ])

    else:
        raise ValueError(f"Unknown start_state: {start_state}")


def scenario_closed_is_terminal():
    return run_bank_with_inputs([
        "10",              # interest rate

        # --- Create customer ---
        "1",
        "collin",

        # --- Create loan ---
        "4",
        "1000",            # account number
        "1000",            # loan amount

        # --- Pay full balance to close loan ---
        "5",               # make loan payment
        "1000",            # account number
        "1",               # loan ID
        "1000",            # exact payoff -> CLOSED

        # --- Attempt extra payments (should have no effect) ---
        "5",
        "1000",
        "1",
        "50",              # attempt to pay after closed

        # --- Advance month multiple times ---
        "6",               # month +1
        "6",               # month +1
        "6",               # month +1

        # --- Print statements ---
        "7",

        # --- Exit ---
        "0",
    ])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_loan_initial_state_is_open():
    output = scenario_open_with_new_loan()
    assert "Loan" in output
    assert "(Delinquent)" not in output     # loan is Open


def test_open_to_delinquent_when_minimum_not_met():
    output = scenario_open_to_delinquent()

    # The original minimum is 18.33
    assert "$18.33" in output or "18.33" in output

    # The new month should show a slightly higher minimum, around 18.35
    assert "$18.35" in output or "18.35" in output


def test_delinquent_to_open_when_min_with_late_fee_paid():
    output = scenario_delinquent_to_open()

    # Delinquent month should show higher minimum:
    assert "18.35" in output or "$18.35" in output

    # After paying full delinquent minimum,
    # next month minimum should DROP back down (ex: 18.27)
    assert "18.27" in output or "$18.27" in output

def test_delinquent_stays_delinquent_with_repeated_underpayment():
    """
    Delinquent → (still effectively Delinquent) when the customer keeps
    underpaying across multiple months. We verify this by checking that
    multiple small payments were made and the loan still has a balance.
    """
    output = scenario_repeated_delinquent()

    # underpay $6.00 three times; all should show up in Recent Activity.
    assert output.count("Paid $6.00 on loan #1") >= 2

    # Loan should still be active with a positive balance.
    assert "Loan #1 balance: $" in output
    assert "Minimum payment due:" in output

def test_open_overpayment_rejected_state_and_balance_unchanged():
    """
    Open → (no change) when attempting a payment above the loan balance.
    Overpayment attempts should NOT change the loan balance.
    """
    output = scenario_overpayment_rejected()

    # Loan should still show the original balance and min due
    assert "Loan #1 balance: $1000.00" in output
    assert "Minimum payment due: $18.33" in output

    # There should NOT be a record of paying $2000.00
    assert "Paid $2000.00 on loan #1" not in output


@pytest.mark.parametrize("start_state", [LoanState.OPEN, LoanState.DELINQUENT])
def test_any_state_closes_on_exact_remaining_balance(start_state):
    """
    Any state → Closed when the exact remaining balance is paid.
    """
    output = scenario_exact_payoff_from_any_state(start_state)

    assert "Loan #1 closed." in output


def test_closed_is_terminal():
    output = scenario_closed_is_terminal()

    # Loan should close at some point
    assert "closed" in output.lower()

    # After closing, it should never become delinquent
    assert "(Delinquent)" not in output

    assert "Loan #1 closed." in output

