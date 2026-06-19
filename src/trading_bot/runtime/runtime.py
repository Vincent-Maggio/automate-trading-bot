class Runtime:
    def __init__(self, clock, control_store, run_cycle, send_report,
                 morning_hour: int, nightly_hour: int):
        self.clock = clock
        self.control_store = control_store
        self.run_cycle = run_cycle
        self.send_report = send_report
        self.morning_hour = morning_hour
        self.nightly_hour = nightly_hour
        self._last_morning = None
        self._last_nightly = None

    def tick(self, now) -> dict:
        reports_sent = []
        today = now.date()
        if now.hour == self.morning_hour and self._last_morning != today:
            self.send_report("morning")
            self._last_morning = today
            reports_sent.append("morning")
        if now.hour == self.nightly_hour and self._last_nightly != today:
            self.send_report("nightly")
            self._last_nightly = today
            reports_sent.append("nightly")

        if self.control_store.is_killed():
            return {"cycle_ran": False, "reports_sent": reports_sent, "halted": True}

        if self.clock.is_open(now):
            self.run_cycle()
            return {"cycle_ran": True, "reports_sent": reports_sent, "halted": False}
        return {"cycle_ran": False, "reports_sent": reports_sent, "halted": False}

    def run_forever(self, now_fn, sleep_fn, interval: int) -> None:
        while True:
            self.tick(now_fn())
            sleep_fn(interval)
