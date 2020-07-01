# coding=utf-8
# Copyright 2020 The TensorFlow Datasets Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Script which parse registered repositories and save datasets found."""

import csv
import pathlib
from typing import Dict, List

import tensorflow as tf
from tensorflow_datasets.core import github_api
import toml


DatasetDict = Dict[str, List[github_api.GithubPath]]


def _is_dataset_path(ds_path: github_api.GithubPath) -> bool:
  """Returns True if the given path correspond to a dataset.

  Currently a simple heuristic is used. This function checks the path has the
  following structure:

  ```
  <ds_name>/
      <ds_name>.py
  ```

  Args:
    ds_path: Path of the dataset module

  Returns:
    True if the path match the expected file structure
  """
  return ds_path.is_dir() and (ds_path / f'{ds_path.name}.py').exists()


def _list_datasets_from_dir(
    path: github_api.GithubPath
) -> List[github_api.GithubPath]:
  """Returns the dataset names found in a specific directory.

  The directory should have the following structure:

  ```
  <path>/
      <dataset0>/
      <dataset1>/
      ...
  ```

  Additional files or folders which are not detected as datasets will be
  ignored (e.g. `__init__.py`).

  Args:
    path: The directory path containing the datasets.

  Returns:
    ds_names: The dataset names found in the directory (sorted for determinism).

  Raises:
    FileNotFoundError: If the path cannot be reached.
  """
  if not path.exists():
    # Should be fault-tolerant in the future
    raise FileNotFoundError(f'Could not find datasets at {path}')
  return sorted([ds for ds in path.iterdir() if _is_dataset_path(ds)])


def _find_community_datasets(config_path: pathlib.Path) -> DatasetDict:
  """Find all namepaces/dataset from the config.

  Config should contain the instructions in the following format:

  ```
  [Namespace]
  <namespace0> = '<owner0>/<github_repo0>/tree/<path/to/dataset/dir>'
  <namespace1> = '<owner1>/<github_repo1>/tree/<path/to/dataset/dir>'
  ```

  Args:
    config_path: Path to the config file containing lookup instructions.

  Returns:
    community datasets: A dict mapping namespace -> list of dataset path.
  """
  config = toml.load(config_path)
  return {
      namespace_name:
      _list_datasets_from_dir(github_api.GithubPath(org_repo_path))
      for namespace_name, org_repo_path in config['Namespaces'].items()
  }


def _save_community_datasets(file_path: str, datasets: DatasetDict) -> None:
  """Save all loaded datasets.

  Saved file will have the following `.tsv` format:

  ```
  namespace0/dataset0 /path/to/dataset/file.py
  namespace0/dataset1 /path/to/dataset/file.py
  ...
  ```

  Args:
    file_path: destination to which save the dataset
    datasets: Dataset paths to save
  """
  # TODO(tfds): Replace GFile by a pathlib-like abstraction for GCS.
  with tf.io.gfile.GFile(file_path, 'w') as f:
    writer = csv.DictWriter(
        f, fieldnames=['namespace', 'name', 'path'], delimiter='\t'
    )
    writer.writeheader()
    for namespace, dataset_paths in datasets.items():
      for dataset_path in dataset_paths:
        writer.writerow({
            'namespace': namespace,
            'name': dataset_path.name,
            'path': str(dataset_path)
        })


def export_community_datasets(in_path: pathlib.Path, out_path: str) -> None:
  """Exports community datasets.

  Args:
    in_path: Config path containing the namespaces and dataset lookup
      instructions.
    out_path: File containing all detected datasets. Detected dataset will
      be saved to this file. Previous content is erased.
  """
  datasets = _find_community_datasets(in_path)
  _save_community_datasets(out_path, datasets)


def main(_):
  config_path = pathlib.Path(__file__).parent.parent / 'community-datasets.toml'
  exported_path = 'gs://tfds-data/community-datasets-list.tsv'
  export_community_datasets(in_path=config_path, out_path=exported_path)


if __name__ == '__main__':
  main(None)
