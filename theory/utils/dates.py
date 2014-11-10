"Commonly-used date structures"

from theory.utils.translation import ugettextLazy as _, pgettextLazy

WEEKDAYS = {
  0: _('Monday'), 1: _('Tuesday'), 2: _('Wednesday'), 3: _('Thursday'), 4: _('Friday'),
  5: _('Saturday'), 6: _('Sunday')
}
WEEKDAYS_ABBR = {
  0: _('Mon'), 1: _('Tue'), 2: _('Wed'), 3: _('Thu'), 4: _('Fri'),
  5: _('Sat'), 6: _('Sun')
}
WEEKDAYS_REV = {
  'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4,
  'saturday': 5, 'sunday': 6
}
MONTHS = {
  1: _('January'), 2: _('February'), 3: _('March'), 4: _('April'), 5: _('May'), 6: _('June'),
  7: _('July'), 8: _('August'), 9: _('September'), 10: _('October'), 11: _('November'),
  12: _('December')
}
MONTHS_3 = {
  1: _('jan'), 2: _('feb'), 3: _('mar'), 4: _('apr'), 5: _('may'), 6: _('jun'),
  7: _('jul'), 8: _('aug'), 9: _('sep'), 10: _('oct'), 11: _('nov'), 12: _('dec')
}
MONTHS_3_REV = {
  'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
  'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}
MONTHS_AP = {  # month names in Associated Press style
  1: pgettextLazy('abbrev. month', 'Jan.'),
  2: pgettextLazy('abbrev. month', 'Feb.'),
  3: pgettextLazy('abbrev. month', 'March'),
  4: pgettextLazy('abbrev. month', 'April'),
  5: pgettextLazy('abbrev. month', 'May'),
  6: pgettextLazy('abbrev. month', 'June'),
  7: pgettextLazy('abbrev. month', 'July'),
  8: pgettextLazy('abbrev. month', 'Aug.'),
  9: pgettextLazy('abbrev. month', 'Sept.'),
  10: pgettextLazy('abbrev. month', 'Oct.'),
  11: pgettextLazy('abbrev. month', 'Nov.'),
  12: pgettextLazy('abbrev. month', 'Dec.')
}
MONTHS_ALT = {  # required for long date representation by some locales
  1: pgettextLazy('alt. month', 'January'),
  2: pgettextLazy('alt. month', 'February'),
  3: pgettextLazy('alt. month', 'March'),
  4: pgettextLazy('alt. month', 'April'),
  5: pgettextLazy('alt. month', 'May'),
  6: pgettextLazy('alt. month', 'June'),
  7: pgettextLazy('alt. month', 'July'),
  8: pgettextLazy('alt. month', 'August'),
  9: pgettextLazy('alt. month', 'September'),
  10: pgettextLazy('alt. month', 'October'),
  11: pgettextLazy('alt. month', 'November'),
  12: pgettextLazy('alt. month', 'December')
}
