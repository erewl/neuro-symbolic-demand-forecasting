import logging
from typing import Any

import pandas as pd
import torch
import torch.nn as nn
import pytorch_lightning as pl
from pytorch_lightning.utilities.types import STEP_OUTPUT


class CustomPLModule(pl.LightningModule):
    """
    This Module ensures that not only the target tensor but also the input tensors
    of the training batch are passed into the loss function
    """

    def training_step(self, train_batch, batch_idx) -> torch.Tensor:
        """performs the training step"""
        output = self._produce_train_output(train_batch[:-1])
        target = train_batch[-1]  # By convention target is always the last element returned by datasets,
        # but we skip this step here and move it to the loss function
        # in order to retrieve context-related data inside the loss function
        # saves tensors to a file for further inspection
        # pd.DataFrame(output.detach().numpy()[:, :, 0, 0]).to_csv(
        #     f"debug_03/{batch_idx}_encoded_output.csv", index=False)
        # pd.DataFrame(target.numpy()[:, :, 0]).to_csv(
        #     f"debug_03/{batch_idx}_encoded_target.csv", index=False)
        # for i, x in enumerate(train_batch):
        #     logging.info(x.shape)
        #     for j in range(x.shape[-1]):
        #         slice_tensor = x[:, :, j]
        #         logging.debug(f"{i}, {j}")
        #         # save to file
        #         pd.DataFrame(slice_tensor.numpy()).to_csv(
        #             f"debug_03/{batch_idx}_encoded_batch_0{i}_tensor_0{j}_slice.csv", index=False)
        # raise Exception("jKFJSDKLFJDKL")
        loss = self._compute_loss(output, train_batch)
        self.log(
            "train_loss",
            loss,
            batch_size=train_batch[0].shape[0],
            prog_bar=True,
            sync_dist=True,
        )
        self._calculate_metrics(output, target, self.train_metrics)
        return loss


class CustomLoss(nn.Module):

    def print_debugs(self, tensor):
        if type(tensor) == tuple:
            logging.debug(f"{len(tensor)}")
            for i, t in enumerate(tensor):
                logging.debug(f"{i}, {t.shape}")
        else:
            logging.debug(f"{len(tensor)}")

    def __init__(self, feature_mappings: dict, weights: dict, thresholds: dict):
        logging.debug('Initializing custom loss')
        self.feature_mappings = feature_mappings
        self.weights = weights
        self.thresholds = thresholds
        super(CustomLoss, self).__init__()

    def _get_loss_for_night(self, output, target):
        tensor_idx, tensor_pos = self.feature_mappings['future_part_of_day']
        part_of_day_tensor = target[tensor_idx][:, :, tensor_pos]

        output_at_night = output[part_of_day_tensor == 0]
        return torch.mean(torch.relu(-output_at_night))

    def _get_loss_for_non_pv(self, output, target):
        # atm we only have one static_covariate feature (PV/Non_PV)
        tensor_idx, tensor_pos = self.feature_mappings['is_pv']
        static_covariate = target[tensor_idx][:, :, tensor_pos]
        non_pv_timeseries_mask = (static_covariate == 0).reshape(-1)
        non_pv_predictions = output[non_pv_timeseries_mask]
        non_pv_negative_predictions = non_pv_predictions[non_pv_predictions < 0]
        if not non_pv_negative_predictions.numel():  # empty tensor, so we are not calculating but just returning 0 for this penalty term
            return 0
        else:
            non_pv_negative_predictions = -non_pv_negative_predictions  # flipping to make values positive (for loss term)
            penalty_loss = non_pv_negative_predictions.mean()  # taking the mean of the negative predictions as a penalty term
            return penalty_loss

    def _get_loss_for_airco_usage(self, output, target):
        return 0

    def _get_loss_for_peaks(self, output, target):
        tensor_idx, tensor_pos = self.feature_mappings['future_part_of_day']
        part_of_day_tensor = target[tensor_idx][:, :, tensor_pos]
        # 0.25 -> morning, 0.75 -> evening
        peaks_mask = ((part_of_day_tensor == 0.25) | (part_of_day_tensor == 0.75))
        output_at_peak_times = output[peaks_mask]
        target_at_peak_times = target[-1][peaks_mask]
        # take RMSE from these
        return torch.mean((output_at_peak_times - target_at_peak_times) ** 2)

    def forward(self, output, target):
        real_target = target[-1]  # last element is the target element

        loss = torch.mean((output - real_target) ** 2)
        # for PTUs that are between sunset and sunrise penalize negative predictions
        penalty_term_no_production_at_night = 0
        # for PTUs in the morning and evening peaks we want to penalize errors in any direction
        penalty_term_morning_evening_peaks = 0
        # for PTUs in summer months where global_radiation and humidity are high, we want to avoid underpredictions
        penalty_term_air_co_on_humid_summer_days = 0
        # no negative predictions for a no-solar-panels dataset
        penalty_non_pv_negative_predictions = 0

        if type(target) == tuple:
            # self.print_debugs(target)
            # no negative predictions at night
            if self.weights['no_neg_pred_night'] > 0:
                penalty_term_no_production_at_night = self._get_loss_for_night(output, target)
            # no negative predictions for non_pv timeseries
            if self.weights['no_neg_pred_nonpv'] > 0:
                penalty_non_pv_negative_predictions = self._get_loss_for_non_pv(output, target)
            # special attention to peak hours (morning and evenings)
            if self.weights['morning_evening_peaks'] > 0:
                penalty_term_morning_evening_peaks = self._get_loss_for_peaks(output, target)
            if self.weights['air_co'] > 0:
                penalty_term_air_co_on_humid_summer_days = self._get_loss_for_airco_usage(output, target)

        sum_ = loss + \
               self.weights['no_neg_pred_night'] * penalty_term_no_production_at_night + \
               self.weights['no_neg_pred_nonpv'] * penalty_non_pv_negative_predictions + \
               self.weights['morning_evening_peaks'] * penalty_term_morning_evening_peaks + \
               self.weights['air_co'] * penalty_term_air_co_on_humid_summer_days
        logging.debug(
            f"Lossterms without weights : {loss} "
            f"+ {penalty_term_no_production_at_night} "
            f"+ {penalty_non_pv_negative_predictions} "
            f"+ {penalty_term_air_co_on_humid_summer_days} "
            f"+ {penalty_term_morning_evening_peaks}"
            f"= {loss + penalty_term_no_production_at_night + penalty_non_pv_negative_predictions + penalty_term_morning_evening_peaks + penalty_term_air_co_on_humid_summer_days}")
        logging.debug(
            f"Lossterms with weights: {loss} "
            f"+ {self.weights['no_neg_pred_night'] * penalty_term_no_production_at_night} "
            f"+ {self.weights['no_neg_pred_nonpv'] * penalty_non_pv_negative_predictions} "
            f"+ {penalty_term_air_co_on_humid_summer_days} + {penalty_term_morning_evening_peaks}"
            f"+ {self.weights['air_co'] * penalty_term_air_co_on_humid_summer_days}"
            f"= {sum_}")
        return sum_
