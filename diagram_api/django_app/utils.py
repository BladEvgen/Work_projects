import openpyxl


def count_debtors(file):
    wb: openpyxl.Workbook = openpyxl.load_workbook(file)
    result: dict[str, dict] = {}
    for sheet_name in wb.sheetnames:
        if sheet_name != "Лист1":
            sheet: openpyxl.Worksheet = wb[sheet_name]
            data: list = [cell.value for cell in sheet["B"] if cell.value is not None]
            result[transliterate(sheet_name.lower())] = len(data)
    return result


def transliterate(name):
    slovar = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        " ": " ",
        "-": "-",
        ".": ".",
        ",": ",",
        "!": "!",
        "?": "?",
        ":": ":",
    }

    name = name.lower()

    translit = ""
    for letter in name:
        if letter in slovar:
            translit += slovar[letter]
        else:
            translit += letter

    return translit
