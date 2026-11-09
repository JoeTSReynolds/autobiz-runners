"""UK legal checks on reported text, in code rather than prompts.

active_case(texts): under the Contempt of Court Act 1981, once someone is charged and until a verdict, reporting beyond the bare
facts can prejudice a trial. A case file is an explainer, so it is refused while the articles show a charge or a trial and no
verdict, plea of guilty or dropped case. After a verdict (sentencing pending) the jury risk is gone and the case file may run.
shortcut: keyword reading of the articles, not legal advice; the owner still reviews every case file before it is published.
"""
import re

_ACTIVE = re.compile(r"\b(has been charged|have been charged|was charged|were charged|charged with|is due to appear|are due to appear|"
                     r"will appear (at|in) court|appeared (at|in) .{0,40}court|remanded|on bail|pleaded not guilty|pleads not guilty|"
                     r"trial (is |was )?(due|set|expected|scheduled)|will stand trial|faces trial|awaiting trial|trial continues|"
                     r"jury (was |has been )?sworn)\b", re.I)
_RESOLVED = re.compile(r"\b(found guilty|found him guilty|found her guilty|found them guilty|convicted|acquitted|found not guilty|"
                       r"cleared of|jailed|sentenced to|was sentenced|pleaded guilty|pleads guilty|charges (were |have been )?dropped|"
                       r"case (was |has been )?dropped|no further action)\b", re.I)


def active_case(texts):
    """A reason string when the articles show active proceedings (a charge or a trial and no verdict), else None."""
    text = ' '.join(texts)
    m = _ACTIVE.search(text)
    if not m or _RESOLVED.search(text):
        return None
    return (f'active court case ("{m.group(0)}" and no verdict): under UK contempt of court rules only the bare facts can be '
            'reported until a verdict, so no case file')
