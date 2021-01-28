# ActivitySim
# See full license in LICENSE.txt

import logging

import numpy as np
import pandas as pd

from activitysim.core import logit
from activitysim.core import config
from activitysim.core import inject
from activitysim.core import tracing
from activitysim.core import chunk
from activitysim.core import pipeline

from activitysim.core.util import reindex

from .util import probabilistic_scheduling as ps


logger = logging.getLogger(__name__)


def run_tour_scheduling_probabilistic(
        tours_df, scheduling_probs, probs_join_cols, model_settings, chunk_size,
        trace_label, trace_hh_id):
    row_size = chunk_size and ps.calc_row_size(
            tours_df, scheduling_probs, probs_join_cols, trace_label, 'tour')

    result_list = []
    for i, chooser_chunk, chunk_trace_label \
        in chunk.adaptive_chunked_choosers(tours_df, chunk_size, row_size, trace_label):
            choices = ps.probabilistic_scheduling(
                chooser_chunk, scheduling_probs, probs_join_cols, model_settings,
                chunk_trace_label, trace_hh_id, trace_choice_col_name='depart_return')
            result_list.append(choices)

    choices = pd.concat(result_list)
    return choices


@inject.step()
def tour_scheduling_probabilistic(
        tours,
        chunk_size,
        trace_hh_id):
    
    trace_label = "tour_scheduling_probabilistic"
    model_settings = config.read_model_settings('tour_scheduling_probabilistic.yaml')
    scheduling_probs_filepath = config.config_file_path(model_settings['SCHEDULING_PROBS'])
    scheduling_probs = pd.read_csv(scheduling_probs_filepath)
    probs_join_cols = model_settings['PROBS_JOIN_COLS']
    tours_df = tours.to_frame()

    choices = run_tour_scheduling_probabilistic(
        tours_df, scheduling_probs, probs_join_cols, model_settings, chunk_size,
        trace_label, trace_hh_id)

    # convert alt index choices to depart/return times
    probs_cols = pd.Series([c for c in scheduling_probs.columns if c not in probs_join_cols])
    dep_ret_choices = probs_cols.loc[choices]
    dep_ret_choices.index = choices.index
    choices.update(dep_ret_choices)
    departures = choices.str.split('_').str[0]
    returns = choices.str.split('_').str[1]
    tours_df['depart'] = departures
    tours_df['return'] = returns

    assert not tours_df['depart'].isnull().any()
    assert not tours_df['return'].isnull().any()

    pipeline.replace_table("tours", tours_df)

