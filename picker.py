from math import floor
from pick import Picker as PickerUpstream


class Picker(PickerUpstream):

    def __init__(self, options, title=None, indicator='*', default_index=0,
                 line_count=1):

        if len(options) == 0:
            raise ValueError('options should not be an empty list')

        self.options = options
        self.title = title
        self.indicator = indicator

        if default_index >= len(options):
            raise ValueError('default_index should be less than the length of options')

        self.index = default_index
        self.custom_handlers = {}
        self.line_count = line_count

    def draw(self):
        """draw the curses ui on the screen, handle scroll if needed"""
        self.screen.clear()

        x, y = 1, 1  # start point
        max_y, max_x = self.screen.getmaxyx()
        # the max rows we can draw
        max_rows = floor((max_y - y) / self.line_count)

        lines, current_line = self.get_lines()

        # calculate how many lines we should scroll, relative to the top
        scroll_top = getattr(self, 'scroll_top', 0)
        if current_line <= scroll_top:
            scroll_top = 0
        elif current_line - scroll_top > max_rows:
            scroll_top = current_line - max_rows
        self.scroll_top = scroll_top

        lines_to_draw = lines[scroll_top:scroll_top+max_rows]

        for line in lines_to_draw:
            self.screen.addstr(y, x, line)
            if line in self.get_title_lines():
                y += 1
            else:
                y += self.line_count

        self.screen.refresh()


def pick(options, title=None, indicator='*', default_index=0, line_count=1):
    """Construct and start a :class:`Picker <Picker>`.

    Usage::

      >>> from pick import pick
      >>> title = 'Please choose an option: '
      >>> options = ['option1', 'option2', 'option3']
      >>> option, index = pick(options, title)
    """
    picker = Picker(options, title, indicator, default_index, line_count)
    return picker.start()
