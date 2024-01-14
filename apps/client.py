# Copyright 2023 AstroLab Software
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
from apps import __file__ as apps_loc
import os
import jpype
import jpype.imports

import numpy as np
import glob

import yaml


def initialise_jvm(path=None, classpath=None):
    """ Start a JVM

    Parameters
    ----------
    path: str, optional
        Path to the HBase client. Default is relative to apps/
    """
    if not jpype.isJVMStarted():
        if path is None:
            path = os.path.dirname(apps_loc) + '/../bin/Lomikel.exe.jar'

        classpaths = [path]
        if classpath is not None:
            if isinstance(classpath, list):
                # List of paths
                classpaths += classpath
            else:
                # Single path or glob expression or a set of these separated by colons
                for _ in  classpath.split(':'):
                    classpaths += glob.glob(_)

        jpype.startJVM(jpype.getDefaultJVMPath(), classpath=classpaths, convertStrings=True)

    jpype.attachThreadToJVM()

def connect_to_hbase_table(tablename: str, schema_name=None, nlimit=10000, setphysicalrepo=False, config_path=None, timeout=100000):
    """ Return a client connected to a HBase table

    Parameters
    ----------
    tablename: str
        The name of the table
    schema_name: str, optional
        Name of the rowkey in the table containing the schema. Default is given by the config file.
    nlimit: int, optional
        Maximum number of objects to return. Default is 10000
    setphysicalrepo: bool, optional
        If True, store cutouts queried on disk ("/tmp/Lomikel/HBaseClientBinaryDataRepository")
        Needs client 02.01+. Default is False
    config_path: str, optional
        Path to the config file. Default is None (relative to the apps/ folder)
    """
    if config_path is None:
        config_path = os.path.dirname(apps_loc) + '/../config.yml'
    args = yaml.load(
        open(config_path),
        yaml.Loader
    )

    initialise_jvm(classpath=args.get('CLASSPATH'))

    import com.Lomikel.HBaser
    from com.Lomikel.Utils import Init

    Init.init()

    client = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT'])

    if schema_name is None:
        schema_name = args['SCHEMAVER']
    client.connect(tablename, schema_name, timeout)
    if setphysicalrepo:
        import com.Lomikel.HBaser.FilesBinaryDataRepository
        client.setRepository(com.Lomikel.HBaser.FilesBinaryDataRepository())
    client.setLimit(nlimit)

    return client

def create_or_update_hbase_table(tablename: str, families: list, schema_name: str, schema: dict, create=False, config_path=None):
    """ Create or update a table in HBase

    By default (create=False), it will only update the schema of the table
    otherwise it will create the table in HBase and push the schema. The schema
    has a rowkey `schema`.

    Currently accepts only a single family name

    Parameters
    ----------
    tablename: str
        The name of the table
    families: list
        List of family names, e.g. ['d']
    schema_name: str
        Rowkey value for the schema
    schema: dict
        Dictionary with column names (keys) and column types (values)
    create: bool
        If true, create the table. Default is False (only update schema)
    config_path: str, optional
        Path to the config file. Default is None (relative to the apps/ folder)
    """
    if len(np.unique(families)) != 1:
        raise NotImplementedError("`create_hbase_table` only accepts one family name")

    if config_path is None:
        config_path = os.path.dirname(apps_loc) + '/../config.yml'
    args = yaml.load(
        open(config_path),
        yaml.Loader
    )

    initialise_jvm(classpath=args.get('CLASSPATH'))

    import com.Lomikel.HBaser
    from com.Lomikel.Utils import Init

    Init.init()

    client = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT'])

    if create:
        # Create the table and connect without schema
        client.create(tablename, families)
        client.connect(tablename)
    else:
        # Connect by ignoring the current schema
        client.connect(tablename, None)

    # Push the schema
    out = ['{}:{}:{}'.format(families[0], colname, coltype) for colname, coltype in schema.items()]
    client.put(schema_name, out)

    client.close()
