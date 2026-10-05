"""The name table: renaming a family a build has changed, or writing one outright.

A family is named twice over. The family, full and typographic family names spell it
with spaces ("Inter Fix RA Bold"); the unique and PostScript names join it up
("InterFixRA-Bold"). A rename that misses either leaves the old face and the new one
answering to the same name, and an application picks whichever it met first.
"""

COPYRIGHT, FAMILY, SUBFAMILY, UNIQUE_ID, FULL_NAME, VERSION, POSTSCRIPT = 0, 1, 2, 3, 4, 5, 6
TYPO_FAMILY, TYPO_SUBFAMILY = 16, 17
COMPATIBLE_FULL, CID_FINDFONT, WWS_FAMILY, WWS_SUBFAMILY, VARIATIONS_PREFIX = 18, 20, 21, 22, 25

SPACED = (FAMILY, FULL_NAME, TYPO_FAMILY)
JOINED = (UNIQUE_ID, POSTSCRIPT)
# What an instance cut from a variable font, or a face made from another, still says
# about the font it came from.
INHERITED = (COMPATIBLE_FULL, CID_FINDFONT, WWS_FAMILY, WWS_SUBFAMILY)

WINDOWS = (3, 1, 0x409)  # platform, encoding, US English
MAC = (1, 0, 0)  # platform, Roman, English


def rename_family(font, old, new):
    """Call the family `new` wherever it was called `old`, spaced and joined alike."""
    table = font["name"]
    for record in table.names:
        if record.nameID in SPACED:
            value = str(record).replace(old, new)
        elif record.nameID in JOINED:
            value = str(record).replace(old.replace(" ", ""), new.replace(" ", ""))
        else:
            continue
        table.setName(value, record.nameID, record.platformID, record.platEncID, record.langID)


def set_names(font, strings, drop=()):
    """Write each `{name id: string}` for Windows and Mac, after removing every record of
    the ids in `drop` on every platform and in every language."""
    table = font["name"]
    for name_id in drop:
        table.removeNames(nameID=name_id)
    for name_id, value in strings.items():
        table.setName(value, name_id, *WINDOWS)
        table.setName(value, name_id, *MAC)
