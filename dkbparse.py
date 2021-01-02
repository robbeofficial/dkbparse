import subprocess
import re
import logging
import csv
import os
from datetime import datetime
from decimal import Decimal

# TODO allow multiline comments for VISA statements
# TODO statement and transaction always have same structure (regardless if account or visa)

# patterns that are re-used in regular expressions
DATE = r"\d\d\.\d\d\.(\d\d\b|\d\d\d\d\b)" 
DECIMAL = r"[\d.]+,\d*" # TODO more explicit (dot after every three digits)
CURRENCY = r"[A-Z]{3}"
TEXT = r"\S.*\S"
SIGN = r"[+-SH]"

re_visa_filename = re.compile(r"Kreditkartenabrechnung_\d\d\d\dxxxxxxxx\d\d\d\d_per_\d\d\d\d_\d\d_\d\d.pdf")
re_filename = re.compile(r"Kontoauszug_\d{10}_Nr_\d\d\d\d_\d\d\d_per_\d\d\d\d_\d\d_\d\d.pdf")

re_range = re.compile(rf"Kontoauszug Nummer (?P<no>\d*) / (?P<year>\d*) vom (?P<from>{DATE}) bis (?P<to>{DATE})")
re_account = re.compile(r"Kontonummer (?P<account>[0-9]*) / IBAN (?P<iban>[A-Z0-9 ]*)")
re_balance_old = re.compile(rf"ALTER KONTOSTAND\s*(?P<old>{DECIMAL}) (?P<sign>{SIGN}) EUR")
re_balance_new = re.compile(rf"NEUER KONTOSTAND\s*(?P<new>{DECIMAL}) (?P<sign>{SIGN}) EUR")
re_table_header = re.compile(r"(?P<booked>Bu.Tag)\s+(?P<valued>Wert)\s+(?P<comment>Wir haben für Sie gebucht)\s+(?P<minus>Belastung in EUR)\s+(?P<plus>Gutschrift in EUR)")
re_transaction = re.compile(r"\s*(?P<booked>[0-9.]+)\s{3,}(?P<valued>[0-9.]+)\s{3,}(?P<type>.+)\s{3,}(?P<value>[0-9.]+,\d\d)\Z")
re_transaction_details = re.compile(r"\s{3,}(?P<line>\S.+)")

# re_visa_table_header = re.compile(r"(?P<booked>Datum)\s+(?P<valued>Datum Angabe des Unternehmens /)\s+(?P<curency>Währung)\s+(?P<foreign_value>Betrag)\s+(?P<rate>Kurs)\s+(?P<value>Betrag in)")
re_visa_balance_new = re.compile(rf"\s*Neuer Saldo\s*(?P<value>{DECIMAL})\s*(?P<sign>{SIGN})")
re_visa_balance_old = re.compile(rf"\s*(?P<valued>{DATE})\s+Saldo letzte Abrechnung\s+(?P<value>{DECIMAL})\s*(?P<sign>{SIGN})")

re_visa_subtotal = re.compile(rf"\s*(Zwischensumme|Übertrag von) Seite \d+\s+(?P<value>{DECIMAL})\s*(?P<sign>{SIGN})")

re_visa_range = re.compile(r"\s+Abrechnung:\s+(?P<month>\b\S*\b) (?P<year>\d\d\d\d)")

re_visa_transaction_foreign = re.compile(
    rf"(?P<booked>{DATE})\s+"
    rf"(?P<valued>{DATE})\s+"
    rf"(?P<comment>{TEXT})\s+"
    rf"(?P<currency>{CURRENCY})\s+"
    rf"(?P<foreign>{DECIMAL})\s+"
    rf"(?P<rate>{DECIMAL})\s+"
    rf"(?P<value>{DECIMAL})\s*"
    rf"(?P<sign>{SIGN})"
)

re_visa_transaction = re.compile(
    rf"(?P<booked>{DATE})?\s+"
    rf"(?P<valued>{DATE})?\s+"
    rf"(?P<comment>{TEXT})\s+"    
    rf"(?P<value>{DECIMAL})\s*"
    rf"(?P<sign>{SIGN})"
)

# re_visa_account = re.compile(r"\s*(?:DKB-VISA-Card:)\s*(?P<account>\S{4}\s\S{4}\s\S{4}\s\S{4})")
# re_visa_owner = re.compile(r"\s*(?:Karteninhaber:)\s*(?P<owner>.*)")

def write_csv(fname, transactions):
    """writes transactions into a CSV file"""
    keys = transactions[0].keys()
    with open(fname, 'w', newline='')  as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(transactions)

def scan_dir(dirpath):
    """Recursively scans dirpath for DKB bank or visa statements and returns all parsed transactions and statements"""
    transactions = []
    statements = []
    for dirpath, unused_dirnames, filenames in os.walk(dirpath):
        logging.info(f"scanning {dirpath} ...")
        for filename in filenames:
            if re_visa_filename.match(filename):
                transactions_statement, statement = read_visa_statement(f"{dirpath}/{filename}")
                statements.append(statement)
                transactions.extend(transactions_statement)
            elif re_filename.match(filename):
                transactions_statement, statement = read_bank_statement(f"{dirpath}/{filename}")
                statements.append(statement)
                transactions.extend(transactions_statement)

    return transactions, statements

def read_pdf_table(fname):
    """Reads contents of a PDF table into a string using pdftotext"""
    return subprocess.run(["pdftotext", "-layout", fname, "-"], stdout=subprocess.PIPE).stdout.decode()

def check_match(re, line, result):
    """calls re.match(line) but also writes the return value to result['match'] and writes match to log"""
    match = re.match(line)    
    if match:
        result['match'] = match
        logging.debug(f"'{line}'\t{match.groupdict()}\t{re.pattern}")
    return match

def decimal(s):    
    return Decimal(s.replace('.','').replace(',','.'))

def date(s):    
    return datetime.strptime(s, '%d.%m.%Y')

def sign(s):
    return -1 if s in ['-','S'] else 1

def read_bank_statement(pdf):
    """returns transactions list and statement summary extracted from a DKB bank statement"""

    statement = {}
    transactions = []
    res = {}

    table = read_pdf_table(pdf)
    lines = table.splitlines()

    match_table_header = None

    for line in lines:        
        if check_match(re_range, line, res):
            match = res['match']
            statement['no'] = int(match.group('no'))
            statement['year'] = int(match.group('year'))
            statement['from'] = date(match.group('from'))
            statement['to'] = date(match.group('to'))     
        elif check_match(re_account, line, res):
            match = res['match']
            statement['account'] = int(match.group('account'))
            statement['iban'] = match.group('iban')        
        elif check_match(re_balance_old, line, res):
            match = res['match']
            statement['balance_old'] = decimal(match.group('old')) * sign(match.group('sign'))        
        elif check_match(re_balance_new, line, res):
            match = res['match']
            statement['balance_new'] = decimal(match.group('new')) * sign(match.group('sign'))
        elif check_match(re_table_header, line, res):
            match_table_header = res['match']
        elif check_match(re_transaction, line, res):
            match = res['match']
            value = decimal(match.group('value'))
            if match.start('value') < match_table_header.end('minus'):
                value = -value
            transactions.append({
                'statement': f"{statement['no']}/{statement['year']}",
                'booked': match.group('booked') + str(statement['year']), 
                'valued': match.group('valued') + str(statement['year']),
                'type': match.group('type').strip(),
                'value': value,
                'comment': '',
            })        
        elif check_match(re_transaction_details, line, res) and match_table_header:
            match = res['match']
            if match.start('line') == match_table_header.start('comment'):
                if not transactions[-1]['comment']:
                    transactions[-1]['comment'] = match.group('line')
                else:
                    transactions[-1]['comment'] += (" " + match.group('line'))
        else:
            logging.debug(f"'{line}'\tNOT MATCHED")
    
    # check for parsing errors
    transactions_sum = sum(map(lambda t : t['value'], transactions))
    balance_difference = statement['balance_new'] - statement['balance_old']
    if (transactions_sum != balance_difference):
        logging.error(f"parsed balance difference of {balance_difference} and transaction sum of {transactions_sum} for {pdf}!")
    
    return transactions, statement

def read_visa_statement_lines(lines):
    """returns transactions list and statement summary extracted from a DKB VISA card statement text lines"""
    statement = {}
    transactions = []
    statement['balance_old'] = 0
    res = {}
    
    for line in lines:
        if check_match(re_visa_balance_old, line, res):
            match = res['match']
            value = decimal(match.group('value')) * sign(match.group('sign'))
            statement['balance_old'] = value
        elif check_match(re_visa_range, line, res):
            match = res['match']
            statement['month'] = match.group('month')
            statement['year'] = match.group('year')
        elif check_match(re_visa_balance_new, line, res):
            match = res['match']
            value = decimal(match.group('value')) * sign(match.group('sign'))
            statement['balance_new'] = value
        elif check_match(re_visa_subtotal, line, res):
            pass
        elif check_match(re_visa_transaction_foreign, line, res) or check_match(re_visa_transaction, line, res):
            match = res['match']
            value = decimal(match.group('value')) * sign(match.group('sign'))
            if match.group('booked'):
                booked = match.group('booked') 
            if match.group('valued'):
                valued = match.group('valued')
            transactions.append({
                'statement': f"{statement['month']}/{statement['year']}",
                'booked': booked, 
                'valued': valued,
                #'type': match_transaction.group('type').strip(),
                'value': value,
                'comment': match.group('comment'),
            })
        else:
            logging.debug(f"'{line}'\tNOT MATCHED")

    return transactions, statement


def read_visa_statement(pdf):
    """returns transactions list and statement summary extracted from a DKB VISA card statement PDF file"""
    table = read_pdf_table(pdf)
    lines = table.splitlines()
    
    transactions, statement = read_visa_statement_lines(lines)

    # check for parsing errors
    transactions_sum = sum(map(lambda t : t['value'], transactions))
    balance_difference = statement['balance_new'] - statement['balance_old']
    if (transactions_sum != balance_difference):
        logging.error(f"parsed balance difference of {balance_difference} and transaction sum of {transactions_sum} for {pdf}!")

    return transactions, statement