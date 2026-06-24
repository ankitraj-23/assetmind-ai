ASSETS = [
    {"tag": "P-101",   "name": "Cooling Water Pump",          "type": "centrifugal_pump"},
    {"tag": "P-102",   "name": "Feed Transfer Pump",          "type": "centrifugal_pump"},
    {"tag": "P-201",   "name": "Condensate Extraction Pump",  "type": "centrifugal_pump"},
    {"tag": "TK-482",  "name": "Feed Storage Tank",           "type": "tank"},
    {"tag": "M-017",   "name": "Boiler Feed Motor",           "type": "motor"},
    {"tag": "HX-305",  "name": "Shell and Tube Heat Exchanger", "type": "heat_exchanger"},
    {"tag": "R-201",   "name": "Process Reactor",             "type": "reactor"},
    {"tag": "BLR-118", "name": "Package Boiler",              "type": "boiler"},
]

TAG_TO_ASSET = {a["tag"]: a for a in ASSETS}

TYPE_TO_TAGS = {}
for a in ASSETS:
    TYPE_TO_TAGS.setdefault(a["type"], []).append(a["tag"])
