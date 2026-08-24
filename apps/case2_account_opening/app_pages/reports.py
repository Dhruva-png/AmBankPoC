import shared_pages

EXCEPTIONS = [
    ("1", "Applicant name on Account Opening Form differs from Identity Document", "KCT-00001"),
    ("2", "NRIC on Account Opening Form differs from Identity Document", "KCT-00002"),
    ("3", "Residential address on Account Opening Form differs from Identity Document", "KCT-00003"),
    ("4", "FATCA/CRS Declaration not signed by the applicant", "KCT-00004"),
    ("5", "Vulnerable Client Assessment not signed by the applicant", "KCT-00005"),
    ("6", "AML/sanctions screening was run against the wrong subject", "KCT-00006"),
    ("7", "AML/sanctions screening returned an unresolved match", "KCT-00007"),
    ("8", "Mandatory account-opening documents are missing", "—"),
]

shared_pages.render_reports("case2", "Accounts", EXCEPTIONS, "Value A", "Value B")
