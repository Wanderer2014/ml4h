import pytest
import numpy as np
import pandas as pd
import tensorflow as tf
from collections import defaultdict

from ml4cvd.new_tensor_generator import dataset_from_tensor_maps, _hd5_path_to_sample_id, sample_getter_from_tensor_maps
from ml4cvd.new_tensor_generator import dataset_from_sample_getter, DataFrameTensorGetter, SampleGetter, SampleIdStateSetter
from ml4cvd.new_tensor_generator import TensorMapTensorGetter
from ml4cvd import new_tensor_generator
from ml4cvd.new_tensor_generator import HD5StateSetter, find_working_ids, ERROR_COL, TensorGetter, _format_error
from ml4cvd.defines import SAMPLE_ID
from ml4cvd.test_utils import TMAPS_UP_TO_4D
from ml4cvd.test_utils import build_hdf5s
from ml4cvd.models import make_multimodal_multitask_model, BottleneckType


@pytest.fixture(scope='session')
def expected_tensors(tmpdir_factory):
    temp_dir = tmpdir_factory.mktemp('explore_tensors')
    tmaps = TMAPS_UP_TO_4D
    return build_hdf5s(temp_dir, tmaps, n=pytest.N_TENSORS)


def test_tensor_generator_from_tensor_maps(expected_tensors):
    paths = [path for path, _ in expected_tensors]
    gen = new_tensor_generator.test_dataset_from_tensor_maps(
        hd5_paths=list(paths),
        tensor_maps_in=TMAPS_UP_TO_4D, tensor_maps_out=TMAPS_UP_TO_4D,
        num_workers=3,
        batch_size=1,
    )
    sample_id_to_path = {_hd5_path_to_sample_id(path): path for path in paths}
    for (inp, out), sample_id in zip(gen, sorted(sample_id_to_path.keys())):
        path = sample_id_to_path[sample_id]
        for tmap in TMAPS_UP_TO_4D:
            assert np.array_equal(expected_tensors[path, tmap], inp[tmap.input_name()][0])
            assert np.array_equal(expected_tensors[path, tmap], out[tmap.output_name()][0])


def test_sample_getter_from_tensor_maps(expected_tensors):
    paths = [path for path, _ in expected_tensors]
    sample_id_to_path = {_hd5_path_to_sample_id(path): path for path in paths}
    path_to_sample_id = {path: sample_id for sample_id, path in sample_id_to_path.items()}
    getter = sample_getter_from_tensor_maps(sample_id_to_path, TMAPS_UP_TO_4D, TMAPS_UP_TO_4D, False)
    for (path, tm), value in expected_tensors.items():
        fetched = getter(path_to_sample_id[path])
        assert (fetched[0][tm.input_name()] == value).all()
        assert (fetched[1][tm.output_name()] == value).all()


def test_model_trains(expected_tensors):
    paths = list({path for path, _ in expected_tensors})
    epochs = 5
    batch_size = 7
    tmaps_in, tmaps_out = TMAPS_UP_TO_4D, TMAPS_UP_TO_4D,
    gen = new_tensor_generator.train_dataset_from_tensor_maps(
        hd5_paths=list(paths),
        tensor_maps_in=tmaps_in, tensor_maps_out=tmaps_out,
        batch_size=7,
        epochs=epochs,
        num_workers=1,
    )
    model_params = {  # TODO: this shouldn't be here
        'activation': 'relu',
        'dense_layers': [4, 2],
        'dense_blocks': [5, 3],
        'block_size': 3,
        'conv_width': 3,
        'learning_rate': 1e-3,
        'optimizer': 'adam',
        'conv_type': 'conv',
        'conv_layers': [6, 5, 3],
        'conv_x': [3],
        'conv_y': [3],
        'conv_z': [2],
        'padding': 'same',
        'max_pools': [],
        'pool_type': 'max',
        'pool_x': 1,
        'pool_y': 1,
        'pool_z': 1,
        'conv_regularize': 'spatial_dropout',
        'conv_regularize_rate': .1,
        'conv_normalize': 'batch_norm',
        'dense_regularize': 'dropout',
        'dense_regularize_rate': .1,
        'dense_normalize': 'batch_norm',
        'bottleneck_type': BottleneckType.FlattenRestructure,
    }
    m = make_multimodal_multitask_model(
        tmaps_in, tmaps_out,
        **model_params,
    )
    m.fit(gen, epochs=epochs, steps_per_epoch=len(paths) // batch_size)


def test_data_frame_tensor_getter():
    col = 'nice_col'
    df = pd.DataFrame({col: np.random.randn(pytest.N_TENSORS)})
    tensor_getter = DataFrameTensorGetter(df, col)
    sample_getter = SampleGetter([tensor_getter], [], [SampleIdStateSetter()])
    for i in range(pytest.N_TENSORS):
        assert (df.loc[i] == sample_getter(i)[0][0][col]).all()


def test_combine_tensor_maps_data_frame(expected_tensors):
    """
    Makes SampleGetter from dataframe and tmaps
    The dataframe's columns are the means of the tmaps
    """
    df = defaultdict(list)
    for (path, tm), value in expected_tensors.items():
        sample_id = _hd5_path_to_sample_id(path)
        if sample_id not in df[SAMPLE_ID]:
            df[SAMPLE_ID].append(sample_id)
        df[tm.input_name()].append(value.mean())
    df = pd.DataFrame(df)
    df.index = df[SAMPLE_ID]
    del df[SAMPLE_ID]

    hd5_paths = [path for path, _ in expected_tensors]
    sample_id_to_path = {_hd5_path_to_sample_id(path): path for path in hd5_paths}
    output_types = tensor_maps_to_output_types(TMAPS_UP_TO_4D, [])
    output_shapes = tensor_maps_to_output_shapes(TMAPS_UP_TO_4D, [])
    for col in df.columns:
        output_types[1][col] = tf.float32
        output_shapes[1][col] = tuple()

    sample_getter = SampleGetter(
        [TensorMapTensorGetter(tmap, is_input=True, augment=False) for tmap in TMAPS_UP_TO_4D],
        [DataFrameTensorGetter(df, col) for col in df.columns],
        [SampleIdStateSetter(), HD5StateSetter(sample_id_to_path)],
    )
    dataset = dataset_from_sample_getter(
        sample_getter, list(sample_id_to_path.keys()), output_types, output_shapes,
    )
    for inp, out in dataset.as_numpy_iterator():
        for name, val in inp.items():
            assert pytest.approx(out[name]) == val.mean()


class FailSometimesTensorGetter(TensorGetter):
    def __init__(self):
        self.name = 'flaky_flakester'
        self.required_state = SampleIdStateSetter.get_name()
        self.required_states = {self.required_state}

    def get_tensor(self, evaluated_states) -> np.ndarray:
        sample_id = evaluated_states[self.required_state]
        if sample_id % 3 == 0:
            return np.ones(1)
        if sample_id % 3 == 1:
            raise ValueError(sample_id)
        if sample_id % 3 == 2:
            raise IndexError(sample_id)


def test_find_working_ids():
    sample_getter = SampleGetter(
        [FailSometimesTensorGetter()],
        [],
        [SampleIdStateSetter()],
    )
    sample_ids = list(range(pytest.N_TENSORS))
    df = find_working_ids(sample_getter, sample_ids, 3)
    df.index = df[SAMPLE_ID]
    for sample_id in sample_ids:
        error = df.loc[sample_id][ERROR_COL]
        if sample_id % 3 == 0:
            assert error == ''
        if sample_id % 3 == 1:
            assert error == _format_error(ValueError(sample_id))
        if sample_id % 3 == 2:
            assert error == _format_error(IndexError(sample_id))
