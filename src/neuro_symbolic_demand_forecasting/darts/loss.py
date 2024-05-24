import logging

import pandas as pd
import torch
import torch.nn as nn
import pytorch_lightning as pl


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
        #     f"debug_02/{batch_idx}_encoded_output.csv", index=False)
        # pd.DataFrame(target.numpy()[:, :, 0]).to_csv(
        #     f"debug_02/{batch_idx}_encoded_target.csv", index=False)
        # for i, x in enumerate(train_batch[:-1]):
        #     logging.info(x.shape)
        #     for j in range(x.shape[-1]):
        #         slice_tensor = x[:, :, j]
        #         logging.debug(f"{i}, {j}")
        #         # save to file
        #         pd.DataFrame(slice_tensor.numpy()).to_csv(
        #             f"debug_02/{batch_idx}_encoded_batch_0{i}_tensor_0{j}_slice.csv", index=False)
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
    def __init__(self, feature_mappings: dict, thresholds: dict):
        logging.debug('Initializing custom loss')
        self.feature_mappings = feature_mappings
        super(CustomLoss, self).__init__()

    def forward(self, output, target):
        real_target = target[-1]  # last element is the target element
        logging.debug(f'Calculating loss, having these shapes, {output.shape}, {real_target.shape}')
        loss = torch.mean((output - real_target) ** 2)
        penalty_term_no_production_at_night, pan_alpha = 0, 40000  # for PTUs that are between sunset and sunrise penalize negative predictions
        penalty_term_morning_evening_peaks, mep_alpha = 0, 0  # for PTUs in the morning and evening peaks we want to penalize errors in any direction
        penalty_term_air_co_on_humid_summer_days, hsd_alpha = 0, 0  # for PTUs in summer months where global_radiation and humidity are high, we want to avoid underpredictions

        if type(target) == tuple:
            # no negative predictions at night
            tensor_idx, tensor_pos = self.feature_mappings['future_part_of_day']
            part_of_day_tensor = target[tensor_idx][:, :, tensor_pos]
            output_at_night = output[part_of_day_tensor == 0]
            penalty_term_no_production_at_night = torch.mean(torch.relu(-output_at_night))

            # humid_summer_days and air co (need to define thresholds

        return loss + \
               pan_alpha * penalty_term_no_production_at_night  # + \
        # penalty_term_morning_evening_peaks + \
        # penalty_term_air_co_on_humid_summer_days
