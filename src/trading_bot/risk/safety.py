class SafetyState:
    def __init__(self, max_daily_loss_pct: float):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.killed = False
        self.tripped = False
        self.day_start_equity = None

    def start_day(self, equity: float) -> None:
        self.day_start_equity = equity
        self.tripped = False

    def kill(self) -> None:
        self.killed = True

    def reset_kill(self) -> None:
        self.killed = False

    def update(self, equity: float) -> bool:
        if self.day_start_equity:
            change = (equity - self.day_start_equity) / self.day_start_equity
            if change <= -self.max_daily_loss_pct:
                self.tripped = True
        return self.tripped

    def can_trade(self) -> bool:
        return not self.killed and not self.tripped
