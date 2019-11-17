class BackpressureManager:

    def __init__(self, max):
        self.max = max
        self.pressure = 0

    def register_pressure(self):
        self.pressure += 1

    def unregister_pressure(self):
        self.pressure -= 1

    def reached(self) -> bool:
        return self.pressure >= self.max
