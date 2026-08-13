import shared_pages

EXCEPTIONS = [
    ("1", "Customer name in CLS differs from Application Form / SSM", "KCT-00001"),
    ("2", "Company registration number incorrectly keyed in CLS", "KCT-00002"),
    ("3", "Registered address differs from SSM records", "KCT-00003"),
    ("4", "Business nature / industry information incorrectly captured", "KCT-00004"),
    ("5", "Director information differs from Application Form or SSM", "KCT-00005"),
    ("6", "Guarantor information differs from Guarantor Form", "KCT-00006"),
    ("7", "CCRIS information does not match CCRIS Form", "KCT-00007"),
    ("8", "Mandatory CIF supporting documents are missing", "—"),
    ("9", "CIF approved without sufficient Maker-Checker verification evidence", "—"),
]

shared_pages.render_reports("case2", "Accounts", EXCEPTIONS, "Value A", "Value B")
