# -*- coding: utf-8 -*-
# ***********************************************************************
# ******************  CANADIAN ASTRONOMY DATA CENTRE  *******************
# *************  CENTRE CANADIEN DE DONNÉES ASTRONOMIQUES  **************
#
#  (c) 2019.                            (c) 2019.
#  Government of Canada                 Gouvernement du Canada
#  National Research Council            Conseil national de recherches
#  Ottawa, Canada, K1A 0R6              Ottawa, Canada, K1A 0R6
#  All rights reserved                  Tous droits réservés
#
#  NRC disclaims any warranties,        Le CNRC dénie toute garantie
#  expressed, implied, or               énoncée, implicite ou légale,
#  statutory, of any kind with          de quelque nature que ce
#  respect to the software,             soit, concernant le logiciel,
#  including without limitation         y compris sans restriction
#  any warranty of merchantability      toute garantie de valeur
#  or fitness for a particular          marchande ou de pertinence
#  purpose. NRC shall not be            pour un usage particulier.
#  liable in any event for any          Le CNRC ne pourra en aucun cas
#  damages, whether direct or           être tenu responsable de tout
#  indirect, special or general,        dommage, direct ou indirect,
#  consequential or incidental,         particulier ou général,
#  arising from the use of the          accessoire ou fortuit, résultant
#  software.  Neither the name          de l'utilisation du logiciel. Ni
#  of the National Research             le nom du Conseil National de
#  Council of Canada nor the            Recherches du Canada ni les noms
#  names of its contributors may        de ses  participants ne peuvent
#  be used to endorse or promote        être utilisés pour approuver ou
#  products derived from this           promouvoir les produits dérivés
#  software without specific prior      de ce logiciel sans autorisation
#  written permission.                  préalable et particulière
#                                       par écrit.
#
#  This file is part of the             Ce fichier fait partie du projet
#  OpenCADC project.                    OpenCADC.
#
#  OpenCADC is free software:           OpenCADC est un logiciel libre ;
#  you can redistribute it and/or       vous pouvez le redistribuer ou le
#  modify it under the terms of         modifier suivant les termes de
#  the GNU Affero General Public        la “GNU Affero General Public
#  License as published by the          License” telle que publiée
#  Free Software Foundation,            par la Free Software Foundation
#  either version 3 of the              : soit la version 3 de cette
#  License, or (at your option)         licence, soit (à votre gré)
#  any later version.                   toute version ultérieure.
#
#  OpenCADC is distributed in the       OpenCADC est distribué
#  hope that it will be useful,         dans l’espoir qu’il vous
#  but WITHOUT ANY WARRANTY;            sera utile, mais SANS AUCUNE
#  without even the implied             GARANTIE : sans même la garantie
#  warranty of MERCHANTABILITY          implicite de COMMERCIALISABILITÉ
#  or FITNESS FOR A PARTICULAR          ni d’ADÉQUATION À UN OBJECTIF
#  PURPOSE.  See the GNU Affero         PARTICULIER. Consultez la Licence
#  General Public License for           Générale Publique GNU Affero
#  more details.                        pour plus de détails.
#
#  You should have received             Vous devriez avoir reçu une
#  a copy of the GNU Affero             copie de la Licence Générale
#  General Public License along         Publique GNU Affero avec
#  with OpenCADC.  If not, see          OpenCADC ; si ce n’est
#  <http://www.gnu.org/licenses/>.      pas le cas, consultez :
#                                       <http://www.gnu.org/licenses/>.
#
#  $Revision: 4 $
#
# ***********************************************************************
#

"""
Implements the default entry point functions for the workflow 
application.

'run' executes based on either provided lists of work, or files on disk.
'run_by_state' executes incrementally, usually based on time-boxed 
intervals.
"""

import logging
import sys
import traceback

from caom2pipe import client_composable as clc
from caom2pipe import data_source_composable as dsc
from caom2pipe import manage_composable as mc
from caom2pipe import name_builder_composable as nbc
from caom2pipe import reader_composable as rdc
from caom2pipe import run_composable as rc
from caom2pipe import transfer_composable as tc
from racs2caom2 import fits2caom2_augmentation, main_app
from vos import Client


RACS_BOOKMARK = 'racs_timestmap'
META_VISITORS = [fits2caom2_augmentation]
DATA_VISITORS = []


def _run():
    """
    Uses a todo file to identify the work to be done.

    :return 0 if successful, -1 if there's any sort of failure. Return status
        is used by airflow for task instance management and reporting.
    """
    config = mc.Config()
    config.get_executors()
    clients = None
    reader = None
    source_transfer = None
    vo_client = Client(vospace_certfile=config.proxy_fqn)
    if mc.TaskType.STORE in config.task_types:
        clients = clc.ClientCollection(config)
        source_transfer = tc.VoFitsTransfer(vo_client)
    else:
        reader = rdc.VaultReader(vo_client)
    name_builder = nbc.EntryBuilder(main_app.RACSName)
    return rc.run_by_todo(
        config=config,
        name_builder=name_builder,
        meta_visitors=META_VISITORS,
        data_visitors=DATA_VISITORS,
        store_transfer=source_transfer,
        clients=clients,
        metadata_reader=reader,
    )


def run():
    """Wraps _run in exception handling, with sys.exit calls."""
    try:
        result = _run()
        sys.exit(result)
    except Exception as e:
        logging.error(e)
        tb = traceback.format_exc()
        logging.debug(tb)
        sys.exit(-1)


def _run_state():
    """Uses a state file with a timestamp to control which entries will be
    processed.
    """
    config = mc.Config()
    config.get_executors()
    clients = None
    reader = None
    source_transfer = None
    vo_client = Client(vospace_certfile=config.proxy_fqn)
    if mc.TaskType.STORE in config.task_types:
        clients = clc.ClientCollection(config)
        source_transfer = tc.VoFitsTransfer(vo_client)
    else:
        reader = rdc.VaultReader(vo_client)
    name_builder = nbc.EntryBuilder(main_app.RACSName)
    return rc.run_by_state(
        config=config,
        bookmark_name=RACS_BOOKMARK,
        meta_visitors=META_VISITORS,
        data_visitors=DATA_VISITORS,
        store_transfer=source_transfer,
        metadata_reader=reader,
        name_builder=name_builder,
        clients=clients,
    )


def run_state():
    """Wraps _run_state in exception handling."""
    try:
        _run_state()
        sys.exit(0)
    except Exception as e:
        logging.error(e)
        tb = traceback.format_exc()
        logging.debug(tb)
        sys.exit(-1)


def _run_remote():
    """
    Uses a VOSpace directory listing to identify the work to be done.

    :return 0 if successful, -1 if there's any sort of failure. Return status
        is used by airflow for task instance management and reporting.
    """
    config = mc.Config()
    config.get_executors()
    vo_client = Client(vospace_certfile=config.proxy_fqn)
    source_transfer = tc.VoFitsTransfer(vo_client)
    source = dsc.VaultDataSource(vo_client, config)
    name_builder = nbc.EntryBuilder(main_app.RACSName)
    reader = rdc.VaultReader(vo_client)
    return rc.run_by_todo(
        config=config,
        name_builder=name_builder,
        meta_visitors=META_VISITORS,
        data_visitors=DATA_VISITORS,
        source=source,
        store_transfer=source_transfer,
        metadata_reader=reader,
    )


def run_remote():
    """Wraps _run_remote in exception handling, with sys.exit calls."""
    try:
        result = _run_remote()
        sys.exit(result)
    except Exception as e:
        logging.error(e)
        tb = traceback.format_exc()
        logging.debug(tb)
        sys.exit(-1)
