"""
Copyright (c) 2018, INRIA
Copyright (c) 2018, University of Lille
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of the copyright holder nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import csv
import os

from powerapi.database.base_db import BaseDB
from powerapi.report_model.report_model import KEYS_COMMON
from powerapi.utils import utils, Error

# Array of field that will not be considered as a group
COMMON_ROW = ['timestamp', 'sensor', 'target', 'socket', 'cpu']


class CsvBadFilePathError(Error):
    """
    Error raised when file is not found
    """


class CsvBadCommonKeysError(Error):
    """
    Error raised when a common keys is not found
    """


class HeaderAreNotTheSameError(Error):
    """
    Error raised when the header read in a file doesn't fit the input data
    """


class CsvDB(BaseDB):
    """
    CsvDB class herited from BaseDB

    This class define the behaviour for reading some csv file.
    a CsvDB instance can be define by his ReportModel and its current path
    """

    def __init__(self, report_model, current_path="/tmp/csvdbtest"):
        """
        :param current_path: Current path where read/write files
        :param report_model: object that herit from ReportModel and define
                             the type of Report
        :type report_model: martwatts.ReportModel
        """
        BaseDB.__init__(self, report_model, False)

        #: (list): list of file name .csv
        self.filenames = []

        #: (str): current path
        self.current_path = current_path if current_path[-1] == '/' else current_path + '/'

        # intern memory for reading
        # path_file: {
        #     'next_line': [],
        #     'reader': None,
        #     'file': None
        # }
        self.tmp_read = {}

        #: (int): allow to know if we read a new report, or the same
        #: current timestamp
        self.saved_timestamp = utils.timestamp_to_datetime(0)

    ###########################################################################
    # Specific CsvDB
    ###########################################################################

    def _next(self, path_file):
        """
        Get next row, None otherwise

        :param str path_file: file name we want to read
        """
        try:
            return self.tmp_read[path_file]['reader'].__next__()
        except StopIteration:
            return None

    def add_file(self, filename):
        """
        Add a file in the filenames list (it can be relative or absolute path)
        :param filename: Path to file
        """
        # If absolute path
        if filename[0] == '/':
            self.filenames.append(filename)
        else:
            filename = self.current_path + filename
            self.filenames.append(filename)

        # Add it in the tmp
        self.tmp_read[filename] = {
            'next_line': [],
            'reader': None,
            'file': None
        }

    def add_files(self, filenames):
        """
        Add list of files in the filenames list (it can be relative or absolute path)
        :param filenames: List of path to file
        """
        for filename in filenames:
            self.add_file(filename)

    def clean_files(self):
        """
        Clean the filenames list
        """
        self.filenames.clear()
        self.tmp_read.clear()

    ###########################################################################
    # Override from BaseDB
    ###########################################################################

    def __iter__(self):
        """
        Create the iterator for get the data
        """
        self.connect()
        return self

    def __next__(self):
        """
        Allow to get the next data
        """
        # Dict to return
        json = {}

        # Get the current timestamp
        current_timestamp = self.saved_timestamp

        # For all files
        for path_file in self.filenames:

            # While timestamp is lower or equal
            while True:

                # Get the next line
                row = self.tmp_read[path_file]['next_line']

                # If nothing more, break
                if row is None:
                    break

                # Get the timestamp as datetime
                row_timestamp = utils.timestamp_to_datetime(
                    int(row['timestamp']))

                # If timestamp is higher, we stop here
                if row_timestamp > current_timestamp:
                    if path_file == self.filenames[0]:
                        self.saved_timestamp = row_timestamp
                    break

                # Else if it's the same, we merge
                elif row_timestamp == current_timestamp:
                    utils.dict_merge(
                        json,
                        self.report_model.from_csvdb(path_file.split('/')[-1],
                                                     row))

                # Next line
                self.tmp_read[path_file]['next_line'] = self._next(path_file)

        if not json:
            raise StopIteration()
        return json

    def connect(self):
        """
        Override from BaseDB.

        Close file if already open
        Read first line of all the .csv file and check if the pattern is good.
        """
        # Close file if already opened
        for path_file in self.filenames:
            if self.tmp_read[path_file]['file'] is not None:
                self.tmp_read[path_file]['file'].close()

        # Open all files with csv and read first line
        for path_file in self.filenames:
            try:
                self.tmp_read[path_file]['file'] = open(path_file)
                self.tmp_read[path_file]['reader'] = csv.DictReader(
                    self.tmp_read[path_file]['file'])
            except FileNotFoundError as error:
                raise CsvBadFilePathError(error)
            self.tmp_read[path_file]['next_line'] = self._next(path_file)

            # Check common key
            for key in KEYS_COMMON:
                if key not in self.tmp_read[path_file]['next_line']:
                    raise CsvBadCommonKeysError("Wrong columns keys")

        # Save the first timestamp
        if self.filenames:
            self.saved_timestamp = utils.timestamp_to_datetime(
                int(self.tmp_read[self.filenames[0]]['next_line']['timestamp']))

    def save(self, serialized_report):
        """
        Allow to save a serialized_report in the db

        :param dict serialized_report: serialized Report
        """
        data = self.report_model.to_csvdb(serialized_report)

        # If the repository doesn't exist, create it
        rep_path = self.current_path + serialized_report['sensor'] + "-" + serialized_report['target']
        try:
            os.makedirs(rep_path)
        except FileExistsError:
            pass

        for filename, values in data.items():
            rep_path_with_file = rep_path + '/' + filename + '.csv'

            # Get the header and check if it's ok
            header = KEYS_COMMON + sorted(list(set([event_key for event_key, _ in values.items()]) - set(KEYS_COMMON)))
            header_exist = False
            try:
                with open(rep_path_with_file) as csvfile:
                    reader = csv.DictReader(csvfile)
                    if reader.fieldnames:
                        header_exist = True

                    if header != reader.fieldnames:
                        raise HeaderAreNotTheSameError("Header are not the same in " + rep_path_with_file)
                    csvfile.close()
            except FileNotFoundError:
                pass

            # Write
            with open(rep_path_with_file, 'a') as csvfile:
                writer = csv.DictWriter(csvfile, header)
                if not header_exist:
                    writer.writeheader()
                writer.writerow(values)
                csvfile.close()

    def save_many(self, serialized_reports):
        """
        Allow to save a batch of data

        :param [Dict] serialized_reports: Batch of data.
        """
        # TODO: Inefficient
        for serialized_report in serialized_reports:
            self.save(serialized_report)
