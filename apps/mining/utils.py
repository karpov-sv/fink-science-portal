# Copyright 2023-2024 AstroLab Software
# Author: Julien Peloton
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
import json

import requests


def upload_file_hdfs(code, webhdfs, namenode, user, filename):
    """Upload a file to HDFS

    Parameters
    ----------
    code: str
        Code as string
    webhdfs: str
        Location of the code on webHDFS in the format
        http://<IP>:<PORT>/webhdfs/v1/<path>
    namenode: str
        Namenode and port in the format
        <IP>:<PORT>
    user: str
        User name in HDFS
    filename: str
        Name on the file to be created

    Returns
    -------
    status_code: int
        HTTP status code. 201 is a success.
    text: str
        Additional information on the query (log).
    """
    try:
        response = requests.put(
            f"{webhdfs}/{filename}?op=CREATE&user.name={user}&namenoderpcaddress={namenode}&createflag=&createparent=true&overwrite=true",
            data=code,
        )
        status_code = response.status_code
        text = response.text
    except (requests.exceptions.ConnectionError, ConnectionRefusedError) as e:
        status_code = -1
        text = e

    if status_code != 201:
        print(f"Status code: {status_code}")
        print(f"Log: {text}")

    return status_code, text


def submit_spark_job(livyhost, filename, spark_conf, job_args):
    """Submit a job on the Spark cluster via Livy (batch mode)

    Parameters
    ----------
    livyhost: str
        IP:HOST for the Livy service
    filename: str
        Path on HDFS with the file to submit. Format:
        hdfs://<path>/<filename>
    spark_conf: dict
        Dictionary with Spark configuration
    job_args: list of str
        Arguments for the Spark job in the form
        ['-arg1=val1', '-arg2=val2', ...]

    Returns
    -------
    batchid: int
        The number of the submitted batch
    response.status_code: int
        HTTP status code
    response.text: str
        Payload
    """
    headers = {"Content-Type": "application/json"}

    data = {
        "conf": spark_conf,
        "file": filename,
        "args": job_args,
    }
    response = requests.post(
        "http://" + livyhost + "/batches",
        data=json.dumps(data),
        headers=headers,
    )

    batchid = response.json()["id"]

    if response.status_code != 201:
        print(f"Batch ID {batchid}")
        print(f"Status code: {response.status_code}")
        print(f"Log: {response.text}")

    return batchid, response.status_code, response.text


def estimate_size_gb_ztf(trans_content):
    """Estimate the size of the data to download

    Parameters
    ----------
    trans_content: str
        Name as given by content_tab
    """
    if trans_content == "Full packet":
        sizeGb = 55.0 / 1024 / 1024
    elif trans_content == "Lightcurve":
        sizeGb = 1.4 / 1024 / 1024
    elif trans_content == "Cutouts":
        sizeGb = 41.0 / 1024 / 1024

    return sizeGb


def estimate_size_gb_elasticc(trans_content):
    """Estimate the size of the data to download

    Parameters
    ----------
    trans_content: str
        Name as given by content_tab
    """
    if trans_content == "Full packet":
        sizeGb = 1.4 / 1024 / 1024

    return sizeGb
