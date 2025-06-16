from utils.buy_sell_handler import create_buy_order,create_sell_order,open_orders,FUTURE_ORDER_TYPE_LIMIT,FUTURE_ORDER_TYPE_STOP
from utils.config import BINANCE_API_KEY, BINANCE_API_SECRET, TEST
from binance.client import Client

















symbol = "ETCUSDT"
quantity = 1
price= 17.26
Trigger_price = 17.28
# sell_price = 17.24
client = Client(BINANCE_API_KEY, BINANCE_API_SECRET, testnet=TEST)

# buy = create_buy_order(
#     symbol=symbol,
#     quantity=1,
#     price=17.28,
#     stop_price=17.25,  # Trigger price for stop-loss
#     order_type=FUTURE_ORDER_TYPE_LIMIT,
#     client=client
# )

# print(buy)


# sell = create_sell_order(
#     symbol=symbol,
#     quantity=quantity,
#     price=sell_price,
#     order_type=FUTURE_ORDER_TYPE_LIMIT,
#     client=client
# )

# print(sell)


# orders_open = open_orders(
#     symbol=symbol,
# )

# print(orders_open)

stop_loss_order = create_sell_order(
    symbol="ETCUSDT",
    quantity=1,
    price=price,  # Price at which the stop-loss order will be triggered
    stop_price=Trigger_price,  # Trigger price for stop-loss
    order_type=FUTURE_ORDER_TYPE_STOP,  # Or FUTURE_ORDER_TYPE_STOP_MARKET
    client=client
)

print(stop_loss_order)

