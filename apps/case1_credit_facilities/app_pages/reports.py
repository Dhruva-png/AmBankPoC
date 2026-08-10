import shared_pages

EXCEPTIONS = [
    ("1", "Facility amount in LO differs from approved amount", "KCT-00001"),
    ("2", "Facility purpose differs from approved purpose", "KCT-00002"),
    ("3", "Pricing/Profit rate differs from approved rate", "KCT-00003"),
    ("4", "Tenure differs from approved tenure", "KCT-00004"),
    ("5", "Approved special conditions omitted from LO", "KCT-00005"),
    ("6", "LO issued before Maker-Checker approval completed", "KCT-00006"),
    ("7", "No evidence of Maker-Checker review and approval", "KCT-00007"),
    ("8", "Incorrect customer details in LO", "—"),
    ("9", "Wrong letterhead used (Conventional/Islamic)", "—"),
]

shared_pages.render_reports("case1", "Credit Facilities", EXCEPTIONS)
