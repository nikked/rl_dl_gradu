"""

Pre-processing of the poloniex (crypto-currencies) data used to produce the input tensors of the neural network. <br>
For each crypto, the input is a raw time series of the prices (High, Low, Open, Close). <i>Please note for crypto-currencies, the market never closes, so Close(t) = Open(t+1). </i><br>
The output is a matrix of 3 rows and n (number of available data points) columns. <br>
The columns correspond to:
- High(t-1)/Open(t-1)
- Low(t-1)/Open(t-1)
- Open(t)/Open(t-1)

We don't need to normalize the data since it's already of ratio of 2 prices closed to one.

    # The shape corresponds to:
    # - 3: Number of features
    # - 10: Number of cryptos
    # - 17030: Number of data points

"""

import os
from pprint import pprint

import pandas as pd
import numpy as np

from data_pipelines.get_data_from_poloniex_api import download_crypto_data, DATA_DIR


def main(
    no_of_cryptos=5,
    start_date="20190101",
    end_date="20190319",
    trading_period_length="2h",
):

    cryptos_dict = {}

    chosen_cryptos = ["ETH", "XMR", "XRP", "LTC", "DASH", "DOGE", "ETC"][:no_of_cryptos]

    for crypto in chosen_cryptos:
        cryptos_dict[crypto] = os.path.join(
            f"BTC_{crypto}",
            f"{start_date}-{end_date}",
            f"BTC_{crypto}_{start_date}-{end_date}_{trading_period_length}.csv",
        )

    for crypto_ticker, crypto_data_fp in cryptos_dict.items():
        if not os.path.isfile(crypto_data_fp):
            download_crypto_data(
                f"BTC_{crypto_ticker}", start_date, end_date, trading_period_length
            )

    chosen_crypto_fps = []

    for crypto in chosen_cryptos:
        chosen_crypto_fps.append(cryptos_dict[crypto])

    crypto_tensor = _make_crypto_tensor(chosen_crypto_fps, no_of_cryptos)

    print("Returning dataset")
    print(chosen_cryptos)
    pprint(crypto_tensor.shape)
    print()

    return crypto_tensor, chosen_cryptos


def _make_crypto_tensor(kept_cryptos, no_of_cryptos):
    list_open = list()
    list_close = list()
    list_high = list()
    list_low = list()

    for idx, crypto in enumerate(kept_cryptos):

        if idx >= no_of_cryptos:
            break

        data_fp = os.path.join(os.getcwd(), DATA_DIR, crypto)

        data = pd.read_csv(data_fp).fillna("bfill").copy()
        data = data[["open", "close", "high", "low"]]
        list_open.append(data.open.values)
        list_close.append(data.close.values)
        list_high.append(data.high.values)
        list_low.append(data.low.values)

    array_open = np.transpose(np.array(list_open))[:-1]
    array_open_of_the_day = np.transpose(np.array(list_open))[1:]
    array_high = np.transpose(np.array(list_high))[:-1]
    array_low = np.transpose(np.array(list_low))[:-1]

    crypto_tensor = np.transpose(
        np.array(
            [
                array_high / array_open,
                array_low / array_open,
                array_open_of_the_day / array_open,
            ]
        ),
        axes=(0, 2, 1),
    )

    return crypto_tensor


if __name__ == "__main__":
    main()