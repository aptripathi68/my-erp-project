COLUMN_RULES = {
    "item_description": ["item", "section", "member", "description"],
    "grade": ["grade", "material"],
    "mark_no": ["mark", "mark no"],
    "item_no": ["item no", "part"],
    "qty_all": ["qty", "quantity", "nos"],
    "length": ["length", "len"],
    "width": ["width"],
    "thk": ["thk", "thickness"],
    "unit_wt": ["unit weight", "weight", "wt"]
}

# Header detection file
def detect_header_row(ws, max_scan=10):

    for r in range(1, max_scan + 1):

        values = [
            str(ws.cell(row=r, column=c).value or "").lower()
            for c in range(1, 30)
        ]

        text = " ".join(values)

        if "mark" in text or "item" in text:
            return r

    return None

# Auto Column Mapping

def detect_column_mapping(headers):

    mapping = {}

    for field, keywords in COLUMN_RULES.items():

        for h in headers:

            h_norm = h.lower()

            if any(k in h_norm for k in keywords):
                mapping[field] = h
                break

    return mapping

# def extract_headers(ws, header_row):

    headers = []

    for c in range(1, ws.max_column + 1):

        v = ws.cell(header_row, c).value

        if v:
            headers.append(str(v).strip())

    return headers
