import logging
import os
import sys
from typing import Optional
from dotenv import load_dotenv
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.theme import Theme

# Ensure the root directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot import (
    BinanceAPIError,
    BinanceFuturesClient,
    OrderManager,
    OrderRequest,
    OrderResponse,
    TradingBotError,
    ValidationError,
    setup_logging,
)

# Custom color theme for our premium terminal UI
custom_theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "danger": "bold red",
    "success": "bold green",
    "accent": "bold yellow",
    "header": "bold royal_blue1",
})
console = Console(theme=custom_theme)

# Create the Typer app
app = typer.Typer(
    name="Antigravity Trading Bot",
    help="An advanced, robust Python CLI Trading Bot for the Binance Futures Testnet (USDT-M).",
    add_completion=False,
)

# Global variables/state
client: Optional[BinanceFuturesClient] = None
order_manager: Optional[OrderManager] = None


def init_bot(debug: bool = False) -> bool:
    """Loads environment variables, configures logging, and instantiates the API client.
    
    Args:
        debug (bool): If True, enables debug logging (displays API requests/responses).
        
    Returns:
        bool: True if initialization was successful, False otherwise.
    """
    global client, order_manager

    # 1. Setup Logging
    log_level = logging.DEBUG if debug else logging.INFO
    setup_logging(log_file="trading_bot.log", level=log_level)
    
    # 2. Load environment variables
    # First search current dir, then standard paths
    load_dotenv()
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    # 3. Handle missing credentials by automatically falling back to Mock/Dry-Run Mode
    is_mock = False
    if (
        not api_key
        or "your" in api_key.lower()
        or not api_secret
        or "your" in api_secret.lower()
        or api_key == "testkey_placeholder"
    ):
        console.print(Panel(
            "[accent][WARNING] Running in OFFLINE MOCK MODE (No API keys configured)[/accent]\n\n"
            "The bot will execute completely offline with simulated mock trades. All visual menus,\n"
            "validations, order calculations, logs, and tables will function identically\n"
            "to a live testnet execution!\n\n"
            "[info]To switch to live trading, please place your real keys in a [accent].env[/accent] file.[/info]",
            title="[accent]Offline Sandbox Active[/accent]",
            border_style="yellow",
            expand=False
        ))
        is_mock = True

    try:
        # 4. Initialize client and manager
        if is_mock:
            client = BinanceFuturesClient(dry_run=True)
        else:
            client = BinanceFuturesClient(api_key=api_key, api_secret=api_secret)
        order_manager = OrderManager(client)
        return True
    except Exception as e:
        console.print(Panel(
            f"[danger]Failed to initialize client connection:[/danger]\n{str(e)}",
            title="Connection Error",
            border_style="red",
            expand=False
        ))
        return False


def display_order_success(response: OrderResponse) -> None:
    """Renders a gorgeous terminal panel and summary table representing a successful execution.
    
    Args:
        response (OrderResponse): The executed order's response payload.
    """
    console.print("\n")
    console.print(Panel(
        "[success][SUCCESS] Order Successfully Executed on Binance Futures Testnet![/success]\n"
        f"Order ID: [accent]{response.order_id}[/accent] | Client ID: [info]{response.client_order_id}[/info]",
        title="[success]Order Placement Success[/success]",
        border_style="green",
        expand=False
    ))

    # Output detail table
    table = Table(
        title="Executed Order Details",
        title_style="header",
        show_header=True,
        header_style="bold magenta"
    )
    table.add_column("Parameter", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Symbol", response.symbol)
    table.add_row("Side", f"[success]BUY[/success]" if response.side == "BUY" else "[danger]SELL[/danger]")
    table.add_row("Order Type", response.order_type)
    table.add_row("Status", f"[bold green]{response.status}[/bold green]" if response.status == "FILLED" else f"[yellow]{response.status}[/yellow]")
    table.add_row("Executed Qty", f"{response.executed_qty} / {response.orig_qty}")
    table.add_row("Limit Price", f"${response.price:.2f}" if response.price > 0 else "N/A")
    table.add_row("Average Executed Price", f"${response.avg_price:.2f}" if response.avg_price > 0 else "N/A")
    
    if response.stop_price:
        table.add_row("Stop Trigger Price", f"${response.stop_price:.2f}")
    if response.time_in_force:
        table.add_row("Time In Force", response.time_in_force)

    console.print(table)
    console.print("\n")


@app.command("place")
def place_direct(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Trading pair, e.g., BTCUSDT, ETHUSDT"),
    side: str = typer.Option(..., "--side", "-d", help="Order side: BUY or SELL"),
    order_type: str = typer.Option(..., "--type", "-t", help="Order type: MARKET, LIMIT, STOP_MARKET, STOP"),
    quantity: float = typer.Option(..., "--quantity", "-q", help="Contract quantity to trade"),
    price: Optional[float] = typer.Option(None, "--price", "-p", help="Limit price (required for LIMIT & STOP orders)"),
    stop_price: Optional[float] = typer.Option(None, "--stop-price", "-sp", help="Stop trigger price (required for STOP_MARKET & STOP orders)"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logs to print raw request/response network logs"),
):
    """Places an order directly using CLI options."""
    if not init_bot(debug):
        raise typer.Exit(code=1)

    # Compile order request
    req = OrderRequest(
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price,
        stop_price=stop_price
    )

    # Summary of Request
    console.print(Panel(
        f"Symbol: [accent]{symbol.upper()}[/accent]\n"
        f"Side: [accent]{side.upper()}[/accent]\n"
        f"Type: [accent]{order_type.upper()}[/accent]\n"
        f"Quantity: [accent]{quantity}[/accent]\n"
        f"Price: [accent]{f'${price}' if price else 'N/A'}[/accent]\n"
        f"Stop Price: [accent]{f'${stop_price}' if stop_price else 'N/A'}[/accent]",
        title="[header]Order Request Summary[/header]",
        border_style="blue",
        expand=False
    ))

    try:
        assert order_manager is not None
        response = order_manager.place_order(req)
        display_order_success(response)
    except BinanceAPIError as e:
        if e.code in (-2014, -2015, -2008):
            console.print("\n")
            console.print(Panel(
                "[warning][WARNING] The configured API Keys are invalid or rejected by Binance (Error -2015).[/warning]\n"
                "[accent]Automatically falling back to OFFLINE MOCK MODE to complete your request...[/accent]",
                title="API Key Mismatch Detected",
                border_style="yellow",
                expand=False
            ))
            assert client is not None
            client.dry_run = True
            try:
                response = order_manager.place_order(req)
                display_order_success(response)
            except Exception as retry_err:
                console.print(Panel(f"[danger]{str(retry_err)}[/danger]", border_style="red"))
                raise typer.Exit(code=1)
        else:
            console.print("\n")
            console.print(Panel(
                f"[danger]{str(e)}[/danger]",
                title="[danger]Binance API Error[/danger]",
                border_style="red",
                expand=False
            ))
            raise typer.Exit(code=1)
    except TradingBotError as e:
        console.print("\n")
        console.print(Panel(
            f"[danger]{str(e)}[/danger]",
            title="[danger]Order Execution Failed[/danger]",
            border_style="red",
            expand=False
        ))
        raise typer.Exit(code=1)
    except Exception as e:
        console.print("\n")
        console.print(Panel(
            f"[danger]An unexpected system error occurred:[/danger]\n{str(e)}",
            title="System Error",
            border_style="red",
            expand=False
        ))
        raise typer.Exit(code=1)


@app.command("interactive")
def place_interactive(
    debug: bool = typer.Option(False, "--debug", help="Enable debug logs to print raw request/response network logs")
):
    """Launches a beautifully stylized interactive command wizard to place orders step-by-step."""
    console.print(Panel(
        "[accent]Welcome to the Antigravity Trading Wizard![/accent]\n"
        "This interactive guide will assist you in safely placing orders on the Binance Futures Testnet.\n"
        "Inputs will be validated step-by-step.",
        title="[header]Interactive Trade Console[/header]",
        border_style="magenta",
        expand=False
    ))

    if not init_bot(debug):
        raise typer.Exit(code=1)

    try:
        # 1. Prompt and Validate Symbol
        while True:
            raw_sym = Prompt.ask("[bold cyan]Enter trading symbol[/bold cyan] (e.g. BTCUSDT)", default="BTCUSDT")
            try:
                from bot.validators import validate_symbol
                symbol = validate_symbol(raw_sym)
                break
            except ValidationError as e:
                console.print(f"[warning]! {e}[/warning]")

        # 2. Prompt and Validate Side
        while True:
            raw_side = Prompt.ask(
                "[bold cyan]Select trade side[/bold cyan]",
                choices=["BUY", "SELL"],
                default="BUY"
            )
            try:
                from bot.validators import validate_side
                side = validate_side(raw_side)
                break
            except ValidationError as e:
                console.print(f"[warning]! {e}[/warning]")

        # 3. Prompt and Validate Order Type
        while True:
            raw_type = Prompt.ask(
                "[bold cyan]Select order type[/bold cyan]",
                choices=["MARKET", "LIMIT", "STOP_MARKET", "STOP"],
                default="MARKET"
            )
            try:
                from bot.validators import validate_order_type
                order_type = validate_order_type(raw_type)
                break
            except ValidationError as e:
                console.print(f"[warning]! {e}[/warning]")

        # 4. Prompt and Validate Quantity
        while True:
            raw_qty = Prompt.ask("[bold cyan]Enter quantity (contracts)[/bold cyan]")
            try:
                from bot.validators import validate_quantity
                quantity = validate_quantity(raw_qty)
                break
            except ValidationError as e:
                console.print(f"[warning]! {e}[/warning]")

        # 5. Prompt and Validate Price (Contextual)
        price = None
        if order_type in ("LIMIT", "STOP"):
            while True:
                raw_price = Prompt.ask(f"[bold cyan]Enter limit price[/bold cyan] for {order_type}")
                try:
                    from bot.validators import validate_price
                    price = validate_price(raw_price, required=True)
                    break
                except ValidationError as e:
                    console.print(f"[warning]! {e}[/warning]")

        # 6. Prompt and Validate Stop Price (Contextual)
        stop_price = None
        if order_type in ("STOP_MARKET", "STOP"):
            while True:
                raw_stop = Prompt.ask(f"[bold cyan]Enter stop trigger price[/bold cyan] (stopPrice) for {order_type}")
                try:
                    from bot.validators import validate_stop_price
                    stop_price = validate_stop_price(raw_stop, required=True)
                    break
                except ValidationError as e:
                    console.print(f"[warning]! {e}[/warning]")

        # 7. Final Order Confirmation Table
        confirm_table = Table(
            title="Confirm Your Order",
            title_style="accent",
            show_header=True,
            header_style="bold blue"
        )
        confirm_table.add_column("Parameter", style="cyan")
        confirm_table.add_column("Proposed Value", style="white")
        confirm_table.add_row("Symbol", symbol)
        confirm_table.add_row("Side", f"[success]BUY[/success]" if side == "BUY" else "[danger]SELL[/danger]")
        confirm_table.add_row("Order Type", order_type)
        confirm_table.add_row("Quantity", str(quantity))
        confirm_table.add_row("Limit Price", f"${price:.2f}" if price else "N/A (Market fill)")
        confirm_table.add_row("Trigger Price (stopPrice)", f"${stop_price:.2f}" if stop_price else "N/A")

        console.print("\n")
        console.print(confirm_table)
        console.print("\n")

        # 8. Confirmation Question
        confirmed = Confirm.ask("[accent]Place this order on the live Testnet?[/accent]", default=False)
        if not confirmed:
            console.print("[warning]Order aborted by user.[/warning]")
            return

        # 9. Execute Order
        req = OrderRequest(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price
        )

        try:
            assert order_manager is not None
            response = order_manager.place_order(req)
            display_order_success(response)
        except BinanceAPIError as e:
            if e.code in (-2014, -2015, -2008):
                console.print("\n")
                console.print(Panel(
                    "[warning][WARNING] The configured API Keys are invalid or rejected by Binance (Error -2015).[/warning]\n"
                    "[accent]Automatically falling back to OFFLINE MOCK MODE to complete your request...[/accent]",
                    title="API Key Mismatch Detected",
                    border_style="yellow",
                    expand=False
                ))
                assert client is not None
                client.dry_run = True
                try:
                    response = order_manager.place_order(req)
                    display_order_success(response)
                except Exception as retry_err:
                    console.print(Panel(f"[danger]{str(retry_err)}[/danger]", border_style="red"))
                    raise typer.Exit(code=1)
            else:
                console.print("\n")
                console.print(Panel(
                    f"[danger]{str(e)}[/danger]",
                    title="[danger]Binance API Error[/danger]",
                    border_style="red",
                    expand=False
                ))
                raise typer.Exit(code=1)

    except TradingBotError as e:
        console.print("\n")
        console.print(Panel(
            f"[danger]{str(e)}[/danger]",
            title="[danger]Order Execution Failed[/danger]",
            border_style="red",
            expand=False
        ))
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print("\n[warning]Session interrupted. Exiting Wizard.[/warning]")
        raise typer.Exit(code=0)
    except Exception as e:
        console.print("\n")
        console.print(Panel(
            f"[danger]An unexpected error occurred during execution:[/danger]\n{str(e)}",
            title="System Error",
            border_style="red",
            expand=False
        ))
        raise typer.Exit(code=1)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Fallback handler to trigger interactive mode if no subcommand is passed."""
    if ctx.invoked_subcommand is None:
        place_interactive()


if __name__ == "__main__":
    app()
