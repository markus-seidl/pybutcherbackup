import tqdm

TYPE = None  # set below
CURRENT_LEVEL = 0

def set_simple():
    global TYPE
    TYPE = "simple"


def set_tqdm():
    global TYPE
    TYPE = "tqdm"


def set_slient():
    global TYPE
    TYPE = "silent"


set_tqdm()


def set_pg_type(new_type):
    if new_type == 'simple':
        set_simple()
    elif new_type == 'tqdm':
        set_tqdm()
    elif new_type == 'silent':
        set_slient()

    raise ValueError("Unknown " + (new_type or 'unset?'))


def create_pg(desc=None, total=None, leave=True, unit='it', unit_scale=False, unit_divisor=1000):
    global TYPE
    if TYPE == 'simple':
        return ProgressBarSimple(desc, total, leave, unit, unit_scale, unit_divisor)
    elif TYPE == 'tqdm':
        return ProgressBarTqdm(desc, total, leave, unit, unit_scale, unit_divisor)
    elif TYPE == 'silent':
        return ProgressBar()

    raise ValueError("Unknown " + (TYPE or 'unset?'))


class ProgressBar:
    def __enter__(self):
        return self

    def update(self, value):
        pass

    def set_postfix(self, ordered_dict=None, refresh=True, **kwargs):
        # TODO needed here?
        pass

    def unpause(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class ProgressBarSimple(ProgressBar):
    def __init__(self, desc, total, leave, unit, unit_scale, unit_divisor):
        global CURRENT_LEVEL
        self.desc = desc or ''
        self.total = total or -1
        self.leave = leave
        self.unit = unit
        self.unit_scale = unit_scale
        self.unit_divisor = unit_divisor
        self.indentation_level = CURRENT_LEVEL
        CURRENT_LEVEL += 1
        self.indentation_str = "\t" * self.indentation_level
        self.current = 0

    def update(self, value):
        # TODO redirect to log
        self.current += value
        print("%s%s: %i/%i" % (self.indentation_str, self.desc, self.current, self.total))

    def __exit__(self, exc_type, exc_val, exc_tb):
        global CURRENT_LEVEL
        CURRENT_LEVEL -= 1

class ProgressBarTqdm(ProgressBar):
    def __init__(self, desc, total, leave, unit, unit_scale, unit_divisor):
        self.tqdm = tqdm.tqdm(desc=desc, total=total, leave=leave, unit=unit, unit_scale=unit_scale,
                              unit_divisor=unit_divisor)

    @property
    def total(self):
        return self.tqdm.total

    @total.setter
    def total(self, total):
        self.tqdm.total = total

    def update(self, value):
        self.tqdm.update(value)

    def unpause(self):
        self.tqdm.unpause()

    def set_postfix(self, ordered_dict=None, refresh=True, **kwargs):
        self.tqdm.set_postfix(ordered_dict=ordered_dict, refresh=refresh, **kwargs)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tqdm.close()
