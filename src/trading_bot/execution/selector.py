from trading_bot.execution.simulated import SimulatedExecutor
from trading_bot.execution.alpaca_exec import AlpacaPaperExecutor


def select_executor(mode: str, live_config: bool, live_env: str,
                    api_key: str, secret_key: str):
    if mode == "sim":
        return SimulatedExecutor()
    live = (live_config is True) and (str(live_env).lower() == "true")
    return AlpacaPaperExecutor(api_key, secret_key, paper=not live)
