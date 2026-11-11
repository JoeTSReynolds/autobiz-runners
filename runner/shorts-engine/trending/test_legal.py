# UK contempt of court: a case file is refused while proceedings are active (charged, no verdict). Run: python3 test_legal.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trending import legal

assert legal.active_case(['The actor has been charged with assault and is due to appear at Westminster Magistrates\' Court.'])
assert legal.active_case(['He pleaded not guilty and the trial is expected to last three weeks.', 'Police said nothing more.'])
assert legal.active_case(['The jury was sworn in on Monday; the trial continues.'])
# a verdict ends the risk of prejudicing a jury: Brand (found guilty, sentencing pending) stays possible
assert not legal.active_case(['A jury found him guilty of one count of rape. Sentencing is set for Monday.', 'He was charged in 2025.'])
assert not legal.active_case(['She was cleared of all charges.', 'She had been charged with fraud.'])
assert not legal.active_case(['He was sentenced to six years.'])
assert not legal.active_case(['Allegations were made in a newspaper investigation; he denies them.'])   # no charge: not active
# a sentence saying there is no charge is not a charge (live 2026-11-10: "Neither Jensen Huang nor Alice Huang has been charged
# with any crimes" blocked the Huang case file)
assert not legal.active_case(['Neither Jensen Huang nor Alice Huang has been charged with any crimes.'])
assert not legal.active_case(['He has not been charged with any offence.', 'No one has been charged.', 'She was never charged with a crime.'])
assert legal.active_case(['He has not been charged.', 'His assistant was charged with fraud on Friday.'])   # another sentence still counts
assert legal.active_case(['He pleaded not guilty.'])                                                         # "not" inside the phrase itself
why = legal.active_case(['He has been charged with fraud.'])
assert 'charged' in why and 'contempt' in why, why
print('ok')
