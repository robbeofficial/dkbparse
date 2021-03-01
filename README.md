# dkbparse
PDF parser for DKB bank and VISA statements

## Requirements
You will need to have Python 3 and pdftotext installed.

## Usage

### Shell Script
You can run `dkbparse.py` as shell script and pass a list of directories that contain DKB PDF statements. The script will write all parsed transactions as CSV to stdout:
```bash
$ ./dkbparse.py ~/dkb/account/1234567890/ ~/dkb/visa/4998xxxxxxxx1234/ > transactions.csv
```

### Library
Alternatively, you can pass a list of direcotries that contains DKB PDF files (VISA and/or bank statements) to `dkbparse.scan_dir()`. All directories are scanned recursively. The function returns a list of transactions and a list of bank statements that were parsed:

```python
import os
from dkbparse import scan_dir

# folder with DKB PDFs
dirpath = os.path.expanduser('~/dkb/visa/4998xxxxxxxx1234') 
transactions, statements = dkbparse.scan_dirs([dirpath])
```

A transaction dict looks like this
```
{   
    'booked': '01.07.2020',
    'comment': 'PayPal Europe S.a.r.l. et Cie S.C.A EREF+1957843284592 '
               'PP.7951.PP PAYPALMREF+46W5544NCY2RUCRED+LU84YYY495162 '
               '00000000000184521+PP.7951.PP . SHOP, Ihr Einkauf bei '
               'SHOP-MELDEPFLICHT BEACHTENHOTLINE BUNDESBANK.(0800) '
               '1234-111',
    'statement': '7/2020',
    'type': 'Basislastschrift',
    'value': Decimal('-0.69'),
    'valued': '01.07.2020
}
```

A statement dict looks like this
```
{   
    'account': 9451359782,
    'balance_new': Decimal('487.33'),
    'balance_old': Decimal('1443.81'),
    'from': datetime.datetime(2018, 12, 29, 0, 0),
    'iban': 'DE82 1234 0000 9451 3597 82',
    'no': 1,
    'to': datetime.datetime(2019, 1, 3, 0, 0),
    'year': 2019
}
```

The script will output an error if the sum of all transactions of a statement does not correspond to the stated balance difference. This will help you to identify cases where the parser fails to parse a statement.

## Performance

The script scans around 100 PDF files (or 2500 transactions) per second.

## Limitations

The main limitation of this approach is that the output depends on the version of the installed `pdftotext` ([Poppler](https://poppler.freedesktop.org/)). Different results on different platforms can not be excluded. For example, using pdftotext version 0.86.1, I occasionally get the following error, which appears to be a known issue.
```
Syntax Warning: FoFiType1::parse a line has more than 255 characters, we don't support this
```