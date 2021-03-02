#!/bin/python3

import subprocess
import re
import logging
import csv
import os
import sys
from datetime import datetime
from decimal import Decimal
from os import getcwd
from os.path import isfile

# https://www.bonify.de/abkuerzungen-im-verwendungszweck
# TODO statementa always have same structure (regardless if account or visa)

# patterns that are re-used in regular expressions
DATE = r"(\d\d)\.(\d\d)\.(\d\d\b|\d\d\d\d\b)"
DATE_NO_YEAR = r"(\d\d)\.(\d\d)\."
DECIMAL = r"\d{1,3}(?:\.\d{3})*(?:,\d+)?"
DECIMAL_FIXED_POINT = r"\d{1,3}(?:\.\d{3})*(?:,\d{2})"
CURRENCY = r"AED|AFN|ALL|AMD|ANG|AOA|ARS|AUD|AWG|AZN|BAM|BBD|BDT|BGN|BHD|BIF|BMD|BND|BOB|BRL|BSD|BTN|BWP|BYR|BZD|CAD|CDF|CHF|CLP|CNY|COP|CRC|CUC|CUP|CVE|CZK|DJF|DKK|DOP|DZD|EGP|ERN|ETB|EUR|FJD|FKP|GBP|GEL|GGP|GHS|GIP|GMD|GNF|GTQ|GYD|HKD|HNL|HRK|HTG|HUF|IDR|ILS|IMP|INR|IQD|IRR|ISK|JEP|JMD|JOD|JPY|KES|KGS|KHR|KMF|KPW|KRW|KWD|KYD|KZT|LAK|LBP|LKR|LRD|LSL|LYD|MAD|MDL|MGA|MKD|MMK|MNT|MOP|MRO|MUR|MVR|MWK|MXN|MYR|MZN|NAD|NGN|NIO|NOK|NPR|NZD|OMR|PAB|PEN|PGK|PHP|PKR|PLN|PYG|QAR|RON|RSD|RUB|RWF|SAR|SBD|SCR|SDG|SEK|SGD|SHP|SLL|SOS|SPL|SRD|STD|SVC|SYP|SZL|THB|TJS|TMT|TND|TOP|TRY|TTD|TVD|TWD|TZS|UAH|UGX|USD|UYU|UZS|VEF|VND|VUV|WST|XAF|XCD|XDR|XOF|XPF|YER|ZAR|ZMW|ZWD"  # ISO 4217
TEXT = r"\S.*\S"
SIGN = r"[\+\-SH]"
CARD_NO = r"\b[0-9X]{4}\s[0-9X]{4}\s[0-9X]{4}\s[0-9X]{4}\b"
BLANK = r"\s{3,}"

re_visa_filename = re.compile(
    r"Kreditkartenabrechnung_\d\d\d\dxxxxxxxx\d\d\d\d_per_\d\d\d\d_\d\d_\d\d.pdf"
)
re_filename = re.compile(
    r"Kontoauszug_\d{10}_Nr_\d\d\d\d_\d\d\d_per_\d\d\d\d_\d\d_\d\d.pdf"
)

re_range = re.compile(
    rf"Kontoauszug Nummer (?P<no>\d*) / (?P<year>\d*) vom (?P<from>{DATE}) bis (?P<to>{DATE})"
)
re_account = re.compile(r"Kontonummer (?P<account>[0-9]*) / IBAN (?P<iban>[A-Z0-9 ]*)")
re_balance_old = re.compile(
    rf"ALTER KONTOSTAND\s*(?P<old>{DECIMAL}) (?P<sign>{SIGN}) EUR"
)
re_balance_new = re.compile(
    rf"NEUER KONTOSTAND\s*(?P<new>{DECIMAL}) (?P<sign>{SIGN}) EUR"
)
re_table_header = re.compile(
    r"(?P<booked>Bu.Tag)\s+(?P<valued>Wert)\s+(?P<comment>Wir haben für Sie gebucht)\s+(?P<minus>Belastung in EUR)\s+(?P<plus>Gutschrift in EUR)"
)
re_transaction = re.compile(
    rf"^\s*(?P<booked>{DATE_NO_YEAR}){BLANK}"
    rf"(?P<valued>{DATE_NO_YEAR}){BLANK}"
    rf"(?P<type>{TEXT}){BLANK}"
    rf"(?P<value>{DECIMAL_FIXED_POINT})$"
)
re_transaction_details = re.compile(
    rf"((?:{BLANK})|(?:{DATE_NO_YEAR}\s+{DATE_NO_YEAR}\s+))" rf"(?P<line>{TEXT})"
)

# re_visa_table_header = re.compile(r"(?P<booked>Datum)\s+(?P<valued>Datum Angabe des Unternehmens /)\s+(?P<curency>Währung)\s+(?P<foreign_value>Betrag)\s+(?P<rate>Kurs)\s+(?P<value>Betrag in)")
re_visa_balance_new = re.compile(
    rf"\s*Neuer Saldo\s*(?P<value>{DECIMAL})\s*(?P<sign>{SIGN})?"
)
re_visa_balance_old = re.compile(
    rf"\s*(?P<valued>{DATE})\s+Saldo letzte Abrechnung\s+(?P<value>{DECIMAL})\s*(?P<sign>{SIGN})"
)
re_visa_subtotal = re.compile(
    rf"\s*(Zwischensumme|Übertrag von) Seite \d+\s+(?P<value>{DECIMAL})\s*(?P<sign>{SIGN})"
)
re_visa_month_year = re.compile(r"\s+Abrechnung:\s+(?P<month>\b\S*\b) (?P<year>\d\d\d\d)")

re_visa_range = re.compile(rf"Ihre Abrechnung vom (?P<from>{DATE}) bis (?P<to>{DATE})")

re_visa_comment_extended = re.compile(r"^\s{18}(?P<comment_extended>\S.*)$")

re_visa_transaction_foreign = re.compile(
    rf"^(?P<booked>{DATE})\s+"
    rf"(?P<valued>{DATE})\s+"
    rf"(?P<comment>{TEXT})\s+"
    rf"(?P<currency>{CURRENCY})\s+"
    rf"(?P<foreign>{DECIMAL})\s+"
    rf"(?P<rate>{DECIMAL})\s+"
    rf"(?P<value>{DECIMAL})\s*"
    rf"(?P<sign>{SIGN})$"
)

re_visa_transaction = re.compile(
    rf"^(?P<booked>{DATE})?\s+"
    rf"(?P<valued>{DATE})?\s+"
    rf"(?P<comment>{TEXT})\s+"
    rf"(?P<value>{DECIMAL})\s*"
    rf"(?P<sign>{SIGN})$"
)

re_visa_account = re.compile(
    rf".*((?:DKB-VISA-Card\:)|(?:VISA\sCard-Nummer\:))\s*(?P<account>{CARD_NO})"
)
# VISA Card-Nummer:
# re_visa_owner = re.compile(r"\s*(?:Karteninhaber:)\s*(?P<owner>.*)")


def transactions_to_csv(f, transactions):
    """writes transactions as CSV to f"""
    keys = ['account','statement','booked','valued','type','value','tag','comment']
    transactions = sorted(transactions, key=lambda t: t["booked"], reverse=True)
    dict_writer = csv.DictWriter(f, keys)
    dict_writer.writeheader()
    dict_writer.writerows(transactions)

def csv_to_transactions(f):
    """Reads transactions as CSV from f"""    
    Date = lambda s: datetime.strptime(s, '%Y-%m-%d').date()
    decimal_accuracy = Decimal('0.01')
    converters={'valued': Date, 'booked': Date, 'value': lambda s: Decimal(s).quantize(decimal_accuracy), 'tag': lambda s: s if s else None}
    reader = csv.DictReader(f)
    transactions = []
    for row in reader:        
        for key, func in converters.items():
            row[key] = func(row[key])
        transactions.append(row)
    return transactions

def scan_dirs(dirpaths):
    """Recursively scans dirpath for DKB bank or visa statements and returns all parsed transactions and statements"""
    transactions = []
    statements = []
    for dirpath in dirpaths:
        for dirpath, unused_dirnames, filenames in os.walk(dirpath):
            logging.info(f"scanning {dirpath} ...")
            for filename in filenames:
                if re_visa_filename.match(filename):
                    transactions_statement, statement = read_visa_statement(
                        f"{dirpath}/{filename}"
                    )
                    statements.append(statement)
                    transactions.extend(transactions_statement)
                elif re_filename.match(filename):
                    transactions_statement, statement = read_bank_statement(
                        f"{dirpath}/{filename}"
                    )
                    statements.append(statement)
                    transactions.extend(transactions_statement)

    return transactions, statements

def apply_tags(transactions, fun):
    """Adds the reult of tagging function fun(comment) as new tag field"""
    return list(map(lambda t: dict(t, **dict(tag=fun(t['comment']))) , transactions))

def apply_annotations(transactions, annotations):
    """Applies tags that are present in annotations also to transactions"""
    def transaction_hash(t):
            keys = ['account','statement','booked','valued','type','value','comment']
            return ''.join(map(lambda key: str(t[key]), keys)).replace(' ','')
        
    # build an index of transactions to avoid linear search for each annotation
    index = {}
    for i, t in enumerate(transactions):
        key = transaction_hash(t)
        if key in index:
            logging.error(f'Hash collision for key {key}')
            pass
        index[key] = i
    
    # apply annotations to transactions
    for annotation in annotations:            
        key = transaction_hash(annotation)
        if key not in index:                
            logging.error(f'Transaction not found "{key}"')
        else:
            transactions[index[key]] = annotation

    return transactions

def read_pdf_table(fname):
    """Reads contents of a PDF table into a string using pdftotext"""
    completed_process = subprocess.run(
        ["pdftotext", "-layout", fname, "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    err_lines = completed_process.stderr.decode().split("\n")
    for err_line in err_lines:
        logging.debug(f"pdftotext.stderr: {err_line}")
    return completed_process.stdout.decode()


def check_match(re, line, result):
    """calls re.match(line) but also writes the return value to result['match'] and writes match to log"""
    match = re.match(line)
    if match:
        result["match"] = match
        logging.debug(f"'{line}'\t{match.groupdict()}\t{re.pattern}")
    return match


def decimal(s):
    return Decimal(s.replace(".", "").replace(",", "."))


def date(s, format="%d.%m.%Y"):
    return datetime.strptime(s, format).date()


def sign(s):
    return -1 if s in ["-", "S"] else 1


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
            match = res["match"]
            statement["no"] = int(match.group("no"))
            statement["year"] = int(match.group("year"))
            statement["from"] = date(match.group("from"))
            statement["to"] = date(match.group("to"))
        elif check_match(re_account, line, res):
            match = res["match"]
            statement["account"] = match.group("account")
            statement["iban"] = match.group("iban")
        elif check_match(re_balance_old, line, res):
            match = res["match"]
            statement["balance_old"] = decimal(match.group("old")) * sign(
                match.group("sign")
            )
        elif check_match(re_balance_new, line, res):
            match = res["match"]
            statement["balance_new"] = decimal(match.group("new")) * sign(
                match.group("sign")
            )
        elif check_match(re_table_header, line, res):
            match_table_header = res["match"]
        elif check_match(re_transaction, line, res):
            match = res["match"]
            value = decimal(match.group("value"))
            if match.start("value") < match_table_header.end("minus"):
                value = -value
            transactions.append(
                {
                    "account": statement["account"],
                    "statement": f"{statement['no']}/{statement['year']}",
                    "booked": date(match.group("booked") + str(statement["year"])),
                    "valued": date(match.group("valued") + str(statement["year"])),
                    "type": match.group("type").strip(),
                    "value": value,
                    "comment": "",
                }
            )
        elif check_match(re_transaction_details, line, res) and match_table_header:
            match = res["match"]
            if match.start("line") == match_table_header.start("comment"):
                if not transactions[-1]["comment"]:
                    transactions[-1]["comment"] = match.group("line")
                else:
                    transactions[-1]["comment"] += " " + match.group("line")
        else:
            logging.debug(f"'{line}'\tNOT MATCHED")

    # check for parsing errors
    transactions_sum = sum(map(lambda t: t["value"], transactions))
    balance_difference = statement["balance_new"] - statement["balance_old"]
    if transactions_sum != balance_difference:
        logging.error(
            f"parsed balance difference of {balance_difference} and transaction sum of {transactions_sum} for {pdf}!"
        )

    return transactions, statement


def read_visa_statement_lines(lines):
    """returns transactions list and statement summary extracted from a DKB VISA card statement text lines"""
    statement = {}
    transactions = []
    statement["balance_old"] = 0
    res = {}

    for line in lines:
        if check_match(re_visa_balance_old, line, res):
            match = res["match"]
            value = decimal(match.group("value")) * sign(match.group("sign"))
            statement["balance_old"] = value
        elif check_match(re_visa_month_year, line, res):
            match = res["match"]
            statement["month"] = match.group("month")
            statement["year"] = match.group("year")
        elif check_match(re_visa_range, line, res):
            match = res["match"]
            statement["from"] = date(match.group("from"))
            statement["to"] = date(match.group("to"))
        elif check_match(re_visa_balance_new, line, res):
            match = res["match"]
            value = decimal(match.group("value")) * sign(match.group("sign"))
            statement["balance_new"] = value
        elif check_match(re_visa_subtotal, line, res):
            pass
        elif check_match(re_visa_transaction_foreign, line, res) or check_match(
            re_visa_transaction, line, res
        ):
            match = res["match"]
            value = decimal(match.group("value")) * sign(match.group("sign"))
            if match.group("booked"):
                booked = match.group("booked")
                booked = date(booked[:6] + "20" + booked[6:])
            if match.group("valued"):
                valued = match.group("valued")
                valued = date(valued[:6] + "20" + valued[6:])
            transactions.append(
                {
                    "account": statement["account"],
                    "statement": f"{statement['month']}/{statement['year']}",
                    "booked": booked,
                    "valued": valued,
                    "type": "VISA",
                    "value": value,
                    "comment": match.group("comment"),
                }
            )
        elif check_match(re_visa_comment_extended, line, res):
            match = res["match"]
            transactions[-1]["comment"] += " " + match["comment_extended"]
        else:
            logging.debug(f"'{line}'\tNOT MATCHED")
        if check_match(re_visa_account, line, res):
            match = res["match"]
            statement["account"] = match["account"]

    return transactions, statement


def read_visa_statement(pdf):
    """returns transactions list and statement summary extracted from a DKB VISA card statement PDF file"""
    logging.info(f"reading VISA statement {pdf} ...")
    table = read_pdf_table(pdf)
    lines = table.splitlines()

    transactions, statement = read_visa_statement_lines(lines)

    # check for parsing errors
    transactions_sum = sum(map(lambda t: t["value"], transactions))
    balance_difference = statement["balance_new"] - statement["balance_old"]
    if transactions_sum != balance_difference:
        logging.error(
            f"parsed balance difference of {balance_difference} and transaction sum of {transactions_sum} for {pdf}!"
        )

    return transactions, statement

if __name__ == '__main__':
    transactions, statements = scan_dirs(sys.argv[1:])
    
    # apply autotagging if tags-auto.yaml is present
    tags_auto = getcwd() + '/tags-auto.yaml'
    if isfile(tags_auto):
        from tagging import RegTag
        regtag = RegTag(open(tags_auto, 'r'))
        transactions = apply_tags(transactions, regtag.tag)
    
    # apply manual tagging if tags-manual.csv is present
    tags_manual = getcwd() + '/tags-manual.csv' 
    if isfile(tags_manual):
        annotations = csv_to_transactions(open(tags_manual))
        transactions = apply_annotations(transactions, annotations)        

    logging.error(transactions[0])
    
    # write transactions as CSV to stdout
    transactions_to_csv(sys.stdout, transactions)
