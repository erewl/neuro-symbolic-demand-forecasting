import argparse
import logging
from typing import Tuple, List

import pandas as pd
import torch
import yaml
from darts import TimeSeries
from darts.models import RNNModel, TFTModel
from darts.dataprocessing.transformers import Scaler
from darts.metrics import mape, smape, mae
from darts.models.forecasting.torch_forecasting_model import TorchForecastingModel
from pytorch_lightning import Callback
from pytorch_lightning.callbacks import EarlyStopping

from neuro_symbolic_demand_forecasting.darts.custom_modules import ExtendedTFTModel, ExtendedRNNModel
from neuro_symbolic_demand_forecasting.darts.loss import CustomLoss

from sklearn.preprocessing import MinMaxScaler


def _load_csvs(_config: dict, _smart_meter_files: list[str], _weather_forecast_files: list[str],
               _weather_actuals_files: list[str]) -> Tuple[list[pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    sms = [pd.read_csv(s, index_col=None, parse_dates=['readingdate']).set_index('readingdate') for s in
           _smart_meter_files]

    wf = pd.read_csv(_weather_forecast_files[0], index_col=None, parse_dates=['valid_datetime']).set_index(
        'valid_datetime')
    wf = wf[_config['weather_forecast_features']]
    wf = wf.resample('15min').ffill()

    wa = pd.read_csv(_weather_actuals_files[0], index_col=None, parse_dates=['datetime_from']).set_index(
        'datetime_from')
    wa = wa[_config['weather_actuals_features']]
    wa = wa.resample('15min').mean()

    return sms, wf, wa


def _adjust_start_date(sm_ts: TimeSeries, min_weather, min_actuals) -> TimeSeries:
    min_smart_meter = sm_ts.time_index.min()
    overall_min_date = max(min_smart_meter, min_weather, min_actuals)
    logging.info(f'Adjusting start dates of smart meter timeseries from {min_smart_meter} to {overall_min_date}')
    # set index to the latest start (min) date
    return sm_ts[sm_ts.get_index_at_point(overall_min_date):]


def _init_model(model_config: dict, callbacks: List[Callback], optimizer_kwargs=None) -> TorchForecastingModel:
    # throughout training we'll monitor the validation loss for early stopping
    early_stopper = EarlyStopping("val_loss", min_delta=0.001, patience=3, verbose=True)
    if callbacks is None or len(callbacks) == 0:
        callbacks = [early_stopper]
    else:
        callbacks = callbacks.append(early_stopper)

    # detect if a GPU is available
    if torch.cuda.is_available() and model_config['gpu_enable']:
        pl_trainer_kwargs = {
            "accelerator": "gpu",
            "gpus": -1,
            "auto_select_gpus": True,
            "callbacks": callbacks,
        }
        num_workers = 4
    else:
        pl_trainer_kwargs = {"callbacks": callbacks}
        num_workers = 0

    match model_config['model_class']:
        case "TFT":
            tft_config: dict = model_config['tft_config']
            if not model_config['run_learning_rate_finder'] and tft_config.get('optimizer_kwargs') is not None:
                optimizer_kwargs = tft_config['optimizer_kwargs']
            logging.info(f"Initiating the Temporal Fusion Transformer with these arguments: \n {tft_config}")
            if tft_config['loss_fn'] and tft_config['loss_fn'] == 'Custom':
                logging.info("Using TFTModel with Custom Module for custom Loss")
                return ExtendedTFTModel(
                    input_chunk_length=tft_config['input_chunk_length'],
                    output_chunk_length=tft_config['output_chunk_length'],
                    loss_fn=CustomLoss(),  # custom loss here
                    # pl_trainer_kwargs={
                    #     "accelerator": "gpu",
                    #     "devices": [0]
                    # },
                    optimizer_kwargs=optimizer_kwargs,
                    pl_trainer_kwargs=pl_trainer_kwargs,
                    **{k: v for k, v in tft_config.items() if
                       k not in ['input_chunk_length', 'output_chunk_length', 'loss_fn', 'optimizer_kwargs']}
                )
            else:
                return TFTModel(
                    input_chunk_length=tft_config['input_chunk_length'],
                    output_chunk_length=tft_config['output_chunk_length'],
                    optimizer_kwargs=optimizer_kwargs,
                    pl_trainer_kwargs=pl_trainer_kwargs,
                    **{k: v for k, v in tft_config.items() if
                       k not in ['input_chunk_length', 'output_chunk_length', 'optimizer_kwargs']}
                )
        case "LSTM":
            lstm_config: dict = model_config['lstm_config']
            if not model_config['run_learning_rate_finder'] and lstm_config.get('optimizer_kwargs') is not None:
                optimizer_kwargs = lstm_config['optimizer_kwargs']
            logging.info(f"Initiating the LSTM with these arguments: \n {lstm_config}")
            if lstm_config.get('loss_fn') == 'Custom':
                logging.info("Using TFTModel with Custom Module for custom Loss")
                return ExtendedRNNModel(
                    model="LSTM",
                    loss_fn=CustomLoss(),  # custom loss here
                    optimizer_kwargs=optimizer_kwargs,
                    pl_trainer_kwargs=pl_trainer_kwargs,
                    **{k: v for k, v in lstm_config.items() if
                       k not in ['loss_fn', 'optimizer_kwargs']}
                )
            else:
                return RNNModel(
                    model="LSTM",
                    optimizer_kwargs=optimizer_kwargs,
                    pl_trainer_kwargs=pl_trainer_kwargs,
                    **{k: v for k, v in lstm_config.items() if k not in ['optimizer_kwargs']}
                )


def main_train(smart_meter_files: list[str], weather_forecast_files: list[str], weather_actuals_files: list[str],
               model_config_path: str, save_model_path: str):
    # load_dotenv()
    logging.info('Starting training!')
    with open(model_config_path, 'r') as file:
        logging.info(f'Loading config from {model_config_path}')
        model_config = yaml.safe_load(file)

    # loading
    sm, wf, wa = _load_csvs(model_config, smart_meter_files, weather_forecast_files, weather_actuals_files)

    # scaling
    weather_forecast_scaler = Scaler(MinMaxScaler(feature_range=(0, 1)))
    weather_actuals_scaler = Scaler(MinMaxScaler(feature_range=(0, 1)))
    smart_meter_scaler = Scaler(MinMaxScaler(feature_range=(0, 1)))

    weather_forecast_ts = weather_forecast_scaler.fit_transform(TimeSeries.from_dataframe(wf))
    weather_actuals_ts = weather_actuals_scaler.fit_transform(TimeSeries.from_dataframe(wa))
    smart_meter_tss = smart_meter_scaler.fit_transform([TimeSeries.from_dataframe(s) for s in sm])

    logging.info("Dtypes of SM, WF, WA")
    logging.info(smart_meter_tss[0].values().dtype)
    logging.info(weather_forecast_ts.values().dtype)
    logging.info(weather_actuals_ts.values().dtype)

    # creating a series of the same length as smart_meter_ts
    weather_forecast_tss = [weather_forecast_ts for _ in sm]
    weather_actuals_tss = [weather_actuals_ts for _ in sm]
    smart_meter_tss = [_adjust_start_date(s, weather_forecast_ts.time_index.min(),
                                          weather_actuals_ts.time_index.min()) for s in smart_meter_tss]
    # smart_meter_tss = [s.add_datetime_attribute('weekday', one_hot=True) for s in smart_meter_tss]

    # training
    model = _init_model(model_config, [], {})
    logging.info("Initialized model, beginning with fitting...")

    match model_config['model_class']:
        case 'LSTM':
            if model_config['run_with_validation']:
                train_tss, val_tss = zip(*[sm.split_after(0.7) for sm in smart_meter_tss])
                if model_config['run_learning_rate_finder']:
                    results = model.lr_find(series=train_tss,
                                            val_series=val_tss,
                                            future_covariates=weather_forecast_tss,
                                            val_future_covariates=weather_forecast_tss
                                            )
                    logging.info(f"Suggested Learning rate: {results.suggestion()}")
                    # re-initialzing model with updated learning params
                    model = _init_model(model_config, callbacks=[],
                                        optimizer_kwargs={
                                            'lr': results.suggestion()})
                model.fit(
                    train_tss,
                    future_covariates=weather_forecast_tss,
                    val_series=val_tss,
                    # val_past_covariates=weather_actuals_ts, # doesnt support past covariates
                    val_future_covariates=weather_forecast_ts,
                    verbose=True,
                    # trainer=pl_trainer_kwargs # would be nice to have early stopping here
                )
            else:
                if model_config['run_learning_rate_finder']:
                    results = model.lr_find(series=smart_meter_tss, future_covariates=weather_forecast_tss)
                    logging.info(f"Suggested Learning rate: {results.suggestion()}")
                    # re-initialzing model with updated learning params
                    model = _init_model(model_config, callbacks=[],
                                        optimizer_kwargs={
                                            'lr': results.suggestion()})
                model.fit(
                    smart_meter_tss,
                    future_covariates=weather_forecast_tss,
                    verbose=True,
                    # trainer=pl_trainer_kwargs # would be nice to have early stopping here
                )
        case 'TFT':
            if model_config['run_with_validation']:
                train_tss, val_tss = zip(*[sm.split_after(0.7) for sm in smart_meter_tss])
                if model_config['run_learning_rate_finder']:
                    results = model.lr_find(series=train_tss,
                                            past_covariates=weather_actuals_tss,
                                            val_series=val_tss,
                                            val_past_covariates=weather_actuals_tss,
                                            future_covariates=weather_forecast_tss,
                                            val_future_covariates=weather_forecast_tss
                                            )
                    logging.info(f"Suggested Learning rate: {results.suggestion()}")
                    model = _init_model(model_config, callbacks=[],
                                        optimizer_kwargs={
                                            'lr': results.suggestion()})  # re-initialzing model with updated learning params
                model.fit(
                    train_tss,
                    past_covariates=weather_actuals_tss,
                    future_covariates=weather_forecast_tss,
                    val_series=val_tss,
                    val_past_covariates=weather_actuals_ts,
                    val_future_covariates=weather_forecast_ts,
                    verbose=True,
                    # trainer=pl_trainer_kwargs # would be nice to have early stopping here
                )
            else:
                if model_config['run_learning_rate_finder']:
                    results = model.lr_find(series=smart_meter_tss,
                                            past_covariates=weather_actuals_ts,
                                            future_covariates=weather_forecast_tss)
                    logging.info(f"Suggested Learning rate: {results.suggestion()}")
                    model = _init_model(model_config, callbacks=[],
                                        optimizer_kwargs={
                                            'lr': results.suggestion()})  # re-initialzing model with updated learning params
                model.fit(
                    smart_meter_tss,
                    past_covariates=weather_actuals_tss,
                    future_covariates=weather_forecast_tss,
                    verbose=True,
                    # trainer=pl_trainer_kwargs # would be nice to have early stopping here
                )
        case other:
            raise Exception(f'Training for {other} not implemented yet')

    # validate
    forecast, actual = smart_meter_tss[0][:-96], smart_meter_tss[0][-96:]

    pred = model.predict(n=96, series=forecast,
                         future_covariates=weather_forecast_ts)

    logging.info("MAPE = {:.2f}%".format(mape(actual, pred)))
    logging.info("SMAPE = {:.2f}%".format(smape(actual, pred)))
    logging.info("MAE = {:.2f}%".format(mae(actual, pred)))

    logging.info(f"Saving model at {save_model_path}")
    model.save(save_model_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Train the model with smart meter data')
    parser.add_argument('-l', '--log_file', type=str, default=None, help='Path to the log file.')
    parser.add_argument('-smd', '--smart-meter-data', metavar='SMD_FILES', type=str, nargs='+',
                        help='comma-separated list of smart meter data csv files to be used for training')
    parser.add_argument('-wfd', '--weather-forecast-data', metavar='WFD_FILES', type=str, nargs='+',
                        help='comma-separated list of weather forecast csv files to be used for training')
    parser.add_argument('-wad', '--weather-actuals-data', metavar='WAD_FILES', type=str, nargs='+',
                        help='comma-separated list of weather actuals csv files to be used for training')
    parser.add_argument('-md', '--model-configuration', metavar='MODEL_CONFIG_PATH', type=str,
                        help='path to the model configuration YAML file')
    parser.add_argument('-sv', '--save-model-as', metavar='MODEL_SAVE_PATH', type=str,
                        help='path where model should be saved')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    smd_files, wfd_files, wad_files = [], [], []
    if args.smart_meter_data:
        smd_files = [file.strip() for file in ','.join(args.smart_meter_data).split(',')]
    if args.weather_forecast_data:
        wfd_files = [file.strip() for file in ','.join(args.weather_forecast_data).split(',')]
    if args.weather_actuals_data:
        wad_files = [file.strip() for file in ','.join(args.weather_actuals_data).split(',')]

    main_train(smd_files, wfd_files, wad_files, args.model_configuration, args.save_model_as)
